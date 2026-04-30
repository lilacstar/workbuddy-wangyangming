# -*- coding: utf-8 -*-
"""
王阳明工具 - Skill 生成器
功能：读取三阶段分析结果 + LLM整合 → 生成可运行的WorkBuddy人物Skill
设计原则：女娲式LLM驱动 + 模板填充，analyzer模块提供结构化输入
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Any

# 导入analyzer模块（analyzer和generator是兄弟目录，都位于wangyangming/下）
_analyzer_path = str(Path(__file__).parent.parent / "analyzer")
if _analyzer_path not in sys.path:
    sys.path.insert(0, _analyzer_path)

from analyzer.phase1_scorer import (
    analyze_phase1, UserAnswer, build_radar_chart_data,
    build_pattern_input, extract_high_low_dimensions
)
from analyzer.phase2_analyzer import (
    analyze_phase2, ScenarioResponse, build_decision_style_summary,
    detect_self_bias, generate_motivation_followup, build_phase2_llm_prompt
)
from analyzer.phase3_analyzer import (
    analyze_phase3, summarize_for_generator
)
from analyzer.integrator import (
    integrate_three_phases, result_to_dict, generate_summary_markdown
)
from analyzer.calibration import (
    run_calibration, format_calibration_for_conversation,
    format_calibration_report
)

# evolution 模块路径（与 analyzer 同级）
_evolution_path = str(Path(__file__).parent.parent / "evolution" / "collectors")
if _evolution_path not in sys.path:
    sys.path.insert(0, _evolution_path)

from feedback_collector import FeedbackCollector

# evolution 配置路径
_EVOLUTION_CONFIG_PATH = Path(__file__).parent.parent / "evolution" / "config.json"


def _load_evolution_config() -> dict:
    """加载 evolution 配置"""
    if _EVOLUTION_CONFIG_PATH.exists():
        with open(_EVOLUTION_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"calibration_integration": {"forward_accuracy_threshold": 0.5}}


# ============================================================
# 主生成流程
# ============================================================

class DistillationSession:
    """
    蒸馏会话管理器
    管理三阶段数据收集 → 分析 → 整合 → Skill生成的完整流程
    """

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or self._generate_session_id()
        self.created_at = datetime.now().isoformat()
        self.phase1_answers: dict[str, UserAnswer] = {}
        self.phase2_scenarios: list[ScenarioResponse] = []
        self.phase3_texts: list[str] = []
        self._phase1_result = None
        self._phase2_result = None
        self._phase3_result = None
        self._integrated_result = None

    @staticmethod
    def _generate_session_id() -> str:
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"wy_{ts}"

    # ---------- Phase 1 ----------

    def add_phase1_answer(self, question_id: str, answer: Any,
                          question_type: str = "single",
                          normalized_score: float = 5.0):
        """添加 Phase 1 作答记录"""
        self.phase1_answers[question_id] = UserAnswer(
            question_id=question_id,
            question_type=question_type,
            raw_answer=answer,
            normalized_score=normalized_score
        )

    def analyze_phase1(self, llm_provider: callable | None = None) -> dict:
        """
        执行 Phase 1 分析
        返回结构化结果供后续使用
        """
        self._phase1_result = analyze_phase1(self.phase1_answers)

        if llm_provider and self._phase1_result.get("pattern_analysis", {}).get("_requires_llm"):
            prompt = self._phase1_result["pattern_analysis"]["_prompt_for_llm"]
            llm_output = llm_provider(prompt, "default")
            self._phase1_result["pattern_analysis"]["llm_output"] = llm_output
            self._phase1_result["pattern_analysis"]["_requires_llm"] = False

        return self._phase1_result

    # ---------- Phase 2 ----------

    def add_phase2_scenario(self, scenario_response: ScenarioResponse):
        """添加 Phase 2 情境回答"""
        self.phase2_scenarios.append(scenario_response)

    def analyze_phase2(self, llm_provider: callable | None = None) -> dict:
        """执行 Phase 2 分析"""
        self._phase2_result = analyze_phase2(
            self.phase2_scenarios, llm_provider=llm_provider
        )
        return self._dict_from_dataclass(self._phase2_result)

    # ---------- Phase 3 ----------

    def add_phase3_text(self, text: str):
        """添加 Phase 3 写作样本"""
        self.phase3_texts.append(text)

    def analyze_phase3(self, llm_provider: callable | None = None) -> dict:
        """执行 Phase 3 分析"""
        self._phase3_result = analyze_phase3(
            self.phase3_texts, llm_provider=llm_provider
        )
        return self._dict_from_dataclass(self._phase3_result)

    # ---------- 三阶段整合 ----------

    def integrate_all_phases(self, llm_provider: callable | None = None) -> dict:
        """执行三阶段整合"""
        p1 = self._phase1_to_dict()
        p2 = self._phase2_to_dict()
        p3 = self._phase3_to_dict()

        self._integrated_result = integrate_three_phases(
            p1, p2, p3, llm_provider=llm_provider
        )
        return result_to_dict(self._integrated_result)

    # ---------- 校准 ----------

    def run_calibration(self, user_responses: str | None = None) -> tuple[list, dict | None]:
        """运行校准流程"""
        if self._integrated_result is None:
            return [], None

        ir = self._integrated_result
        mental_models = [dict(m) for m in (ir.mental_models or [])]
        heuristics = [dict(h) for h in (ir.decision_heuristics or [])]
        # bias_flags: 防御性处理，可能为 list[BiasFlag] / 单个 BiasFlag / 其他类型
        _raw_bias = ir.bias_flags if ir.bias_flags is not None else []
        try:
            # 优先按列表处理（正常情况）
            bias_flags = [dict(b) for b in _raw_bias]
        except TypeError:
            # 单个 BiasFlag 对象（异常情况）
            bias_flags = []

        questions, result = run_calibration(
            mental_models, heuristics, bias_flags,
            user_responses=user_responses
        )
        return questions, result

    def get_calibration_prompt(self) -> str:
        """获取校准对话文本"""
        questions, _ = self.run_calibration()
        if not questions:
            return "分析数据不足，无法生成校准问题"
        return format_calibration_for_conversation(questions)

    # ---------- 校准 → 进化 链路 ----------

    def run_calibration_with_evolution(
        self,
        user_responses: str,
        skill_name: str = "anonymous"
    ) -> tuple[list, dict | None]:
        """
        运行校准并将结果自动推送到 evolution 模块。

        工作流程：
        1. run_calibration() → 计算准确度
        2. 根据准确度映射到 evolution 评分
        3. 通过 FeedbackCollector 持久化到 evolution/feedback/ratings.json
        4. 返回 (校准问题, 校准结果)

        参数:
            user_responses: 用户对校准问题的回答
            skill_name: Skill 名称（用于 evolution 记录）

        返回:
            (校准问题列表, CalibrationResult | None)
        """
        questions, result = self.run_calibration(user_responses=user_responses)

        if result is None or not self._integrated_result:
            return questions, None

        # 从配置读取阈值
        cfg = _load_evolution_config()
        cal_cfg = cfg.get("calibration_integration", {})
        threshold = cal_cfg.get("forward_accuracy_threshold", 0.5)

        # 仅当开启自动推送且准确度低于阈值时推送
        if not cal_cfg.get("forward_on_low_accuracy", True):
            return questions, result

        if result.accuracy >= threshold:
            # 准确度足够，无需推送（用户认可模型质量）
            return questions, result

        # ---------- 映射准确度 → evolution 评分 ----------
        mapping = cfg.get("calibration_result_mapping", {}).get(
            "accuracy_to_evolution_score", {}
        )

        if result.accuracy >= 0.7:
            mapping_key = "0.7_and_above"
        elif result.accuracy >= 0.5:
            mapping_key = "0.5_to_0.7"
        else:
            mapping_key = "below_0.5"

        mapped = mapping.get(mapping_key, {})
        evolution_score = mapped.get("evolution_score", 3)
        feedback_text = mapped.get("feedback_text", result.assessment)
        suggestions = mapped.get("suggestions", [])

        # 追加校准追问建议
        if result.followup_questions:
            suggestions = suggestions + result.followup_questions

        # ---------- 推送到 FeedbackCollector ----------
        try:
            collector = FeedbackCollector()
            collector.add_feedback(
                overall_score=evolution_score,
                dimension_scores={
                    "准确度": evolution_score,
                    "风格一致性": evolution_score,
                    "识别度": evolution_score,
                    "可用性": 3
                },
                feedback_text=f"[校准驱动] {feedback_text} | 准确度: {result.accuracy:.0%}",
                suggestions=suggestions,
                user_id=f"calibration-{self.session_id}"
            )
        except Exception:
            # evolution 模块异常不影响主流程
            pass

        return questions, result

    # ---------- Skill生成 ----------

    def generate_skill(
        self,
        skill_name: str,
        llm_provider: callable,
        output_dir: str | None = None
    ) -> str:
        """生成最终Skill文件"""
        if self._integrated_result is None:
            self.integrate_all_phases(llm_provider=llm_provider)

        ir = self._integrated_result

        # 构建生成prompt
        prompt = self._build_skill_generation_prompt(skill_name)

        # 调用LLM生成Skill内容
        skill_content = llm_provider(prompt, "default")

        # 保存
        if output_dir is None:
            output_dir = Path.home() / ".workbuddy" / "skills" / f"wuyangming-{skill_name}"
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)
        skill_path = output_dir / "SKILL.md"

        content = self._extract_skill_content(skill_content)
        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(content)

        # 生成配套文件
        self._generate_supporting_files(output_dir, skill_name)

        return str(skill_path)

    def _build_skill_generation_prompt(self, skill_name: str) -> str:
        """构建Skill生成的LLM prompt"""
        ir = self._integrated_result

        # Phase 1 雷达图
        p1 = self._phase1_to_dict()
        radar = ""
        if p1.get("radar_chart"):
            dims = p1["radar_chart"].get("dimensions", [])
            vals = p1["radar_chart"].get("values", [])
            radar = "\n".join(f"- {d}: {v}/10" for d, v in zip(dims, vals))

        # Phase 2 决策摘要
        decision_summary = ""
        if ir.decision_pattern:
            dp = ir.decision_pattern
            decision_summary = (f"首要考量{dp.primary_care}、"
                              f"决策{dp.decision_speed}、"
                              f"信息收集{dp.information_style}、"
                              f"风险{dp.risk_attitude}")

        # Phase 3 表达摘要
        phase3_text = ""
        if self._phase3_result:
            phase3_text = summarize_for_generator(self._phase3_result)

        # 心智模型
        mental_models_text = ""
        if ir.mental_models:
            for m in ir.mental_models:
                mental_models_text += (f"\n### {m.name}\n"
                                       f"{m.description}\n"
                                       f"证据: {' | '.join(m.evidence)}\n"
                                       f"预测: {m.prediction}\n")

        # 决策启发式
        heuristics_text = ""
        if ir.decision_heuristics:
            for h in ir.decision_heuristics:
                heuristics_text += (f"\n**{h.number}. {h.title}** - "
                                   f"{h.description}（场景: {h.scene}）\n")

        # 偏差标注
        bias_text = ""
        if ir.bias_flags:
            for b in ir.bias_flags:
                bias_text += f"\n- [{b.severity}] {b.type}：{b.description}"

        # 画像
        portrait_text = ""
        if ir.portrait:
            p = ir.portrait
            portrait_text = (f"**{p.one_line}**\n"
                             f"核心特质：{' / '.join(p.core_traits)}\n"
                             f"决策风格：{p.decision_style}\n"
                             f"沟通风格：{p.communication_style}\n"
                             f"成长盲区：{p.growth_edge}")

        return f"""## 任务：为用户"{skill_name}"生成个性化思维Skill

你是WorkBuddy的人物Skill生成器。请基于以下分析结果，生成一个完整的、可运行的Skill文件。

### 用户画像
{portrait_text}

### 分析置信度
- 整体置信度：{ir.overall_confidence}
- 跨阶段一致性：{ir.cross_phase_consistency}/10

### Phase 1 维度得分
{radar}

### Phase 2 决策模式
{decision_summary}

### Phase 3 表达风格
{phase3_text}

### 心智模型
{mental_models_text}

### 决策启发式
{heuristics_text}

### 偏差标注
{bias_text}

---

### 输出要求

生成一个完整的 `SKILL.md` 文件，包含以下部分：

1. **元信息**：name, description, trigger words, perspective
2. **心智模型**：3-5个核心思维框架（来自分析结果）
3. **决策启发式**：5-8条可操作的思维原则
4. **表达DNA**：语气风格、句式偏好、标志性表达
5. **人物画像**：核心特质、决策风格、沟通风格、成长盲区
6. **典型场景**：3-5个具体场景下的反应模板
7. **边界说明**：这个Skill不适用的情况
8. **校准注释**：偏差标注和置信度说明

### 风格要求
- 用第一人称（"我"）撰写
- 语言风格要与Phase 3分析的表达DNA一致
- 每个心智模型要有具体的行为描述
- 决策启发式要可操作，不是空泛的道理
- 典型场景要有画面感

直接输出完整的SKILL.md内容，不要包含代码块标记。
"""

    @staticmethod
    def _extract_skill_content(llm_output: str) -> str:
        """从LLM输出中提取Skill内容"""
        content = re.sub(r"^```markdown\s*", "", llm_output.strip(), flags=re.MULTILINE)
        content = re.sub(r"```\s*$", "", content.strip(), flags=re.MULTILINE)
        return content.strip()

    def _generate_supporting_files(self, output_dir: Path, skill_name: str):
        """生成配套文件"""
        # 分析报告
        report_path = output_dir / "analysis_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(generate_summary_markdown(self._integrated_result))

        # 版本信息
        meta = {
            "version": "1.0.0",
            "generated_at": datetime.now().isoformat(),
            "session_id": self.session_id,
            "confidence": self._integrated_result.overall_confidence if self._integrated_result else "unknown",
            "phase_coverage": {
                "phase1": len(self.phase1_answers),
                "phase2": len(self.phase2_scenarios),
                "phase3": len(self.phase3_texts)
            }
        }
        meta_path = output_dir / ".meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    # ---------- 会话持久化 ----------

    def save(self, path: str | None = None) -> str:
        """保存会话数据"""
        if path is None:
            base = Path.home() / ".workbuddy" / "skills" / "wangyangming" / "sessions"
            base.mkdir(parents=True, exist_ok=True)
            path = str(base / f"{self.session_id}.json")

        data = {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "phase1_answers": {
                qid: {"type": a.question_type, "answer": a.raw_answer, "score": a.normalized_score}
                for qid, a in self.phase1_answers.items()
            },
            "phase2_scenarios": [
                {
                    "scenario_id": s.scenario_id,
                    "title": s.scenario_title,
                    "description": s.description,
                    "main_answers": s.main_answers,
                    "followup_answers": s.followup_answers
                }
                for s in self.phase2_scenarios
            ],
            "phase3_texts": self.phase3_texts
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    @classmethod
    def load(cls, path: str) -> "DistillationSession":
        """加载会话数据"""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        session = cls(session_id=data["session_id"])
        session.created_at = data["created_at"]

        for qid, item in data.get("phase1_answers", {}).items():
            session.phase1_answers[qid] = UserAnswer(
                question_id=qid,
                question_type=item["type"],
                raw_answer=item["answer"],
                normalized_score=item["score"]
            )

        for s in data.get("phase2_scenarios", []):
            session.phase2_scenarios.append(ScenarioResponse(
                scenario_id=s["scenario_id"],
                scenario_title=s["title"],
                description=s["description"],
                main_answers=s["main_answers"],
                followup_answers=s.get("followup_answers", []),
                raw_texts=[]
            ))

        session.phase3_texts = data.get("phase3_texts", [])
        return session

    # ---------- 内部辅助 ----------

    @staticmethod
    def _dict_from_dataclass(obj) -> dict:
        """将dataclass转为dict"""
        if obj is None:
            return {}
        if hasattr(obj, "__dataclass_fields__"):
            result = {}
            for f in obj.__dataclass_fields__:
                v = getattr(obj, f)
                if hasattr(v, "__dataclass_fields__"):
                    result[f] = DistillationSession._dict_from_dataclass(v)
                elif isinstance(v, list):
                    result[f] = [DistillationSession._dict_from_dataclass(x) if hasattr(x, "__dataclass_fields__") else x for x in v]
                else:
                    result[f] = v
            return result
        return dict(obj) if isinstance(obj, dict) else obj

    def _phase1_to_dict(self) -> dict:
        if self._phase1_result is None:
            return {}
        return self._dict_from_dataclass(self._phase1_result)

    def _phase2_to_dict(self) -> dict:
        if self._phase2_result is None:
            return {}
        return self._dict_from_dataclass(self._phase2_result)

    def _phase3_to_dict(self) -> dict:
        if self._phase3_result is None:
            return {}
        return self._dict_from_dataclass(self._phase3_result)


# ============================================================
# 快捷函数
# ============================================================

def create_session() -> DistillationSession:
    """创建一个新的蒸馏会话"""
    return DistillationSession()


def generate_calibration_text(session: DistillationSession) -> str:
    """获取校准对话文本"""
    return session.get_calibration_prompt()


def run_full_pipeline(
    phase1_answers: dict[str, dict],
    phase2_scenarios: list[dict],
    phase3_texts: list[str],
    llm_provider: callable,
    skill_name: str,
    output_dir: str | None = None
) -> tuple[str, dict]:
    """
    完整蒸馏流程（一键调用）

    参数:
        phase1_answers: {题目ID: {"type": "...", "answer": "...", "score": 5.0}}
        phase2_scenarios: [ScenarioResponse序列化后的dict]
        phase3_texts: [文本列表]
        llm_provider: LLM调用函数 (prompt: str) -> str
        skill_name: 生成的Skill名称
        output_dir: 输出目录

    返回:
        (skill文件路径, 整合分析结果dict)
    """
    session = DistillationSession()

    # Phase 1
    for qid, item in phase1_answers.items():
        session.add_phase1_answer(
            question_id=qid,
            answer=item.get("answer"),
            question_type=item.get("type", "single"),
            normalized_score=item.get("score", 5.0)
        )
    session.analyze_phase1(llm_provider=llm_provider)

    # Phase 2
    for s in phase2_scenarios:
        session.add_phase2_scenario(ScenarioResponse(
            scenario_id=s["scenario_id"],
            scenario_title=s["title"],
            description=s["description"],
            main_answers=s["main_answers"],
            followup_answers=s.get("followup_answers", []),
            raw_texts=[]
        ))
    session.analyze_phase2(llm_provider=llm_provider)

    # Phase 3
    for text in phase3_texts:
        session.add_phase3_text(text)
    session.analyze_phase3(llm_provider=llm_provider)

    # 整合
    integrated = session.integrate_all_phases(llm_provider=llm_provider)

    # 生成Skill
    skill_path = session.generate_skill(
        skill_name=skill_name,
        llm_provider=llm_provider,
        output_dir=output_dir
    )

    # 保存会话
    session.save()

    return skill_path, integrated


# ============================================================
# 入口测试
# =========================================================

if __name__ == "__main__":
    def mock_llm(prompt: str, model: str = "default") -> str:
        """测试用mock LLM"""
        return '{"mental_models":[{"name":"测试模型","description":"测试描述","evidence":["Phase1维度A","Phase2情境B"],"prediction":"预测结果","confidence":"medium"}],"decision_heuristics":[{"number":1,"title":"测试启发式","description":"描述","scene":"场景","source":"Phase2","reasoning_chain":"链"}],"portrait":{"one_line":"一句话","core_traits":["特质1"],"decision_style":"决策描述","communication_style":"沟通描述","growth_edge":"盲区","self_other_gap":"差距"},"integration_confidence":"medium"}'

    # 测试完整流程
    test_answers = {
        "A1": {"type": "single", "answer": "独自旅行", "score": 7.5},
        "B1": {"type": "single", "answer": "意义驱动", "score": 8.0},
        "C1": {"type": "single", "answer": "权衡利弊", "score": 9.0},
    }
    test_scenarios = [{
        "scenario_id": "S1",
        "title": "职场选择",
        "description": "猎头推荐高薪机会但要离开现有团队",
        "main_answers": [
            {"question": "你会怎么做？", "answer": "我会先跟领导谈，看有没有调整空间。"},
            {"question": "核心考量是什么？", "answer": "长期发展。"}
        ],
        "followup_answers": []
    }]
    test_texts = [
        "我觉得这个事要从两个角度看。短期看可能有波动，长期看方向是对的。"
    ]

    path, result = run_full_pipeline(
        test_answers, test_scenarios, test_texts,
        llm_provider=mock_llm,
        skill_name="test-user"
    )
    print(f"Skill生成路径: {path}")
    print(f"整合置信度: {result.get('overall_confidence', 'N/A')}")
    print(f"心智模型数: {len(result.get('mental_models', []))}")
