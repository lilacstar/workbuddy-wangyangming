# -*- coding: utf-8 -*-
"""
王阳明工具 - 对话流程控制器
功能：问卷加载、题目展示、答案收集、条件追问、会话状态管理
设计原则：WorkBuddy AI 作为对话界面，Python 作为分析引擎，两层分离
"""

import json
import uuid
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any, Literal


# ============================================================
# 数据结构
# ============================================================

@dataclass
class Phase1Answer:
    """Phase 1 单题答案"""
    question_id: str
    question_type: str          # single_choice | ranking | text_input
    raw_answer: Any             # 用户原始回答
    selected_value: str | None  # 选项字母（如 "A"）
    selected_label: str | None  # 选项标签（如 "靠谱/稳重"）
    normalized_score: float     # 归一化分数（0-10）
    # ranking 时
    ranking_order: list[str] | None = None  # 排序顺序 ["B", "A", "C", "D"]


@dataclass
class Phase2Answer:
    """Phase 2 情境题答案"""
    scenario_id: str
    main_answers: list[str]      # 主问题回答列表
    followup_answers: list[str] = field(default_factory=list)  # 追问回答
    triggered: bool = False      # 是否触发了追问


@dataclass
class Phase3Answer:
    """Phase 3 写作任务答案"""
    task_id: str
    task_title: str
    text: str
    char_count: int


@dataclass
class ConversationState:
    """完整会话状态"""
    session_id: str
    current_phase: int           # 1 | 2 | 3 | "calibration" | "generating" | "done"
    phase1_index: int           # Phase1 当前题目索引
    phase1_answers: list[Phase1Answer] = field(default_factory=list)
    phase2_index: int = 0        # Phase2 当前情境索引
    phase2_answers: list[Phase2Answer] = field(default_factory=list)
    phase2_followup_active: bool = False  # 追问是否进行中
    phase3_index: int = 0        # Phase3 当前任务索引
    phase3_answers: list[Phase3Answer] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)  # 扩展字段


# ============================================================
# 题库加载器
# ============================================================

class QuestionnaireLoader:
    """加载并解析三阶段问卷 JSON"""

    BASE_DIR = Path(__file__).parent / "questionnaire"

    def __init__(self):
        self.phase1 = self._load("phase1.json")
        self.phase2 = self._load("phase2.json")
        self.phase3 = self._load("phase3.json")

    def _load(self, filename: str) -> dict:
        path = self.BASE_DIR / filename
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def get_phase1_question(self, question_id: str) -> dict | None:
        for q in self.phase1.get("questions", []):
            if q["id"] == question_id:
                return q
        return None

    def get_phase1_all(self) -> list[dict]:
        return self.phase1.get("questions", [])

    def get_phase2_all(self) -> list[dict]:
        return self.phase2.get("scenarios", [])

    def get_phase3_all(self) -> list[dict]:
        return self.phase3.get("tasks", [])

    @property
    def phase1_dimensions(self) -> list[dict]:
        return self.phase1.get("dimensions", [])

    @property
    def phase2_framework(self) -> dict:
        return self.phase2.get("analysisFramework", {})


# ============================================================
# 对话提示构建器
# ============================================================

class PromptBuilder:
    """将题库数据转换为 AI 对话提示"""

    @staticmethod
    def phase1_intro(total: int) -> str:
        return (
            "## Phase 1：观点探测\n\n"
            f"共 {total} 道选择题，请跟随直觉作答。\n"
            "每道题会显示选项，回答选项字母（如 A / B / C）即可。"
        )

    @staticmethod
    def phase1_question(q: dict, index: int, total: int) -> str:
        lines = [
            f"\n**题目 {index}/{total}**\n"
            f"{q['text']}\n"
        ]
        if q.get("type") == "single_choice":
            for opt in q.get("options", []):
                lines.append(f"- **{opt['value']}**. {opt['label']}")
        elif q.get("type") == "ranking":
            lines.append("请将以下选项按重要性排序（从高到低），用字母表示（如：B > A > C > D）")
            for opt in q.get("items", []):
                # items may use 'id' (e.g. "F1-1") or 'value' (e.g. "A")
                key = opt.get('id', opt.get('value', '?'))
                lines.append(f"- **{key}**. {opt['label']}")
        elif q.get("type") == "text_input":
            lines.append("（请直接输入你的想法）")
        return "\n".join(lines)

    @staticmethod
    def phase1_feedback(question_id: str, selected: str, label: str) -> str:
        return f"已记录：**{question_id}** → {selected}. {label} ✓"

    @staticmethod
    def phase2_intro(total: int) -> str:
        return (
            "## Phase 2：情境反应\n\n"
            f"共 {total} 道情境题。请根据每个情境，详细描述你的想法和决策过程。\n"
            "建议回答 100 字以上，这样我能更准确地理解你的思维模式。\n"
            "如果回答较短，我会追加一两个追问。"
        )

    @staticmethod
    def phase2_scenario(s: dict, index: int, total: int) -> str:
        lines = [
            f"\n### 情境 {index}/{total}：{s['title']}\n"
            f"**场景**：{s['scenario']}\n"
        ]
        if s.get("description"):
            lines.append(f"_{s['description']}_")
        for i, q in enumerate(s.get("mainQuestions", [])):
            lines.append(f"\n**问题 {i+1}**：{q}")
        lines.append("\n（请详细描述你的想法和决策过程）")
        return "\n".join(lines)

    @staticmethod
    def phase2_followup(scenario_id: str, followup: dict) -> str:
        qs = followup.get("questions", [])
        if not qs:
            return ""
        lines = ["\n**追问**："]
        for q in qs:
            lines.append(f"\n{q}")
        return "\n".join(lines)

    @staticmethod
    def phase3_intro(total: int) -> str:
        return (
            "## Phase 3：语料采样\n\n"
            f"共 {total} 个写作任务。这些任务没有对错之分，真实最重要。\n"
            "请像平时写东西一样自然表达，不需要在意文采。"
        )

    @staticmethod
    def phase3_task(t: dict, index: int, total: int) -> str:
        limits = t.get("wordLimit", {})
        word_str = ""
        if limits:
            word_str = f"（建议 {limits.get('min', 100)}-{limits.get('max', 300)} 字）"
        lines = [
            f"\n### 任务 {index}/{total}：{t['title']}\n"
            f"**话题**：{t['topic']}\n"
        ]
        if t.get("description"):
            lines.append(f"\n{t['description']}")
        lines.append(f"\n{word_str}")
        for g in t.get("guidance", []):
            lines.append(f"\n- {g}")
        lines.append("\n（请直接开始写）")
        return "\n".join(lines)

    @staticmethod
    def phase_complete(phase: int, stats: dict) -> str:
        if phase == 1:
            return f"\n✅ **Phase 1 完成！** 已回答 {stats.get('answered', 0)}/{stats.get('total', 0)} 题。"
        elif phase == 2:
            return f"\n✅ **Phase 2 完成！** 完成了 {stats.get('answered', 0)} 个情境分析。"
        elif phase == 3:
            return f"\n✅ **Phase 3 完成！** 收集了 {stats.get('answered', 0)} 篇写作样本。"
        return ""

    @staticmethod
    def analyzing() -> str:
        return (
            "\n\n---\n\n"
            "🔍 **数据收集完成，正在分析中...**\n"
            "接下来我会：\n"
            "1. 计算你的价值观维度得分\n"
            "2. 分析你的决策模式和思维框架\n"
            "3. 提取你的表达风格 DNA\n"
            "4. 整合三个阶段的发现\n"
            "5. 生成你的思维镜像 Skill\n\n"
            "请稍候..."
        )


# ============================================================
# 分数映射器
# ============================================================

class ScoreMapper:
    """将用户选项映射为归一化分数（0-10）"""

    # 通用映射规则（根据 dimension 类型）
    DIMENSION_WEIGHTS = {
        "self_cognition":  {"A": 8.0, "B": 7.0, "C": 6.5, "D": 6.0, "E": 5.0},
        "attribution":      {"A": 8.0, "B": 6.5, "C": 5.5, "D": 4.0},
        "risk_preference":  {"A": 9.0, "B": 7.0, "C": 5.0, "D": 3.0},
        "interpersonal":    {"A": 8.0, "B": 7.0, "C": 6.0, "D": 4.0},
        "cognitive_style":   {"A": 7.5, "B": 6.5, "C": 5.5, "D": 4.5},
        "value_priority":   {"A": 8.0, "B": 6.5, "C": 5.0, "D": 3.5},
        "big_five_supplement": {"A": 8.0, "B": 7.0, "C": 6.0, "D": 5.0},
        "motivation_structure": {"A": 8.0, "B": 6.5, "C": 5.0},
    }

    # 排序题权重（按排名顺序给分，越靠前越高）
    RANKING_WEIGHTS = {
        1: 10.0,   # 第一名
        2: 8.0,
        3: 6.0,
        4: 4.0,
    }

    @classmethod
    def map_single_choice(cls, q: dict, selected_value: str) -> float:
        dim = q.get("dimension", "")
        # 先尝试 dimension 专用映射
        if dim in cls.DIMENSION_WEIGHTS:
            return cls.DIMENSION_WEIGHTS[dim].get(selected_value, 5.0)
        # 通用：从选项 weight 求均值
        for opt in q.get("options", []):
            if opt["value"] == selected_value:
                w = opt.get("weight", {})
                if w:
                    return sum(w.values()) / len(w) * 5  # 放大到 0-10
                return 5.0
        return 5.0

    @classmethod
    def map_ranking(cls, order: list[str]) -> float:
        """
        排序得分：计算每个选项的排名分之和，归一化到 0-10
        order: ["B", "A", "C", "D"] 表示第一是 B，第二是 A...
        """
        total = 0.0
        n = len(order)
        for rank, value in enumerate(order, 1):
            # 排名越靠前，分数越高（n=4时：第1名=10分，第2名=7.5，第3名=5，第4名=2.5）
            pos_score = 10.0 - (rank - 1) * (10.0 / (n + 1))
            total += pos_score
        return total / n  # 取平均

    @classmethod
    def map_text_input(cls, text: str) -> float:
        """文本输入：根据长度和内容丰富度估算分数"""
        if not text:
            return 5.0
        length = len(text)
        if length > 200:
            return 8.0
        elif length > 100:
            return 7.0
        elif length > 50:
            return 6.0
        else:
            return 5.0


# ============================================================
# 主对话流程管理器
# ============================================================

class ConversationFlow:
    """
    对话流程管理器

    使用方式（AI 作为对话界面）：
    1. AI 识别触发词 → 加载本模块
    2. session = ConversationFlow()  # 新会话
    3. while True:
           prompt = session.get_next_prompt()  # 获取下一步提示
           if prompt is None: break            # 流程结束
           # AI 将 prompt 显示给用户
           user_answer = ...                    # 收集用户回答
           result = session.submit_answer(user_answer)  # 提交答案
           # AI 显示 result（反馈或下一题）
    """

    def __init__(self, session_id: str | None = None):
        self.loader = QuestionnaireLoader()
        self.state = ConversationState(
            session_id=session_id or str(uuid.uuid4())[:8],
            current_phase=1,
            phase1_index=0,
            phase2_index=0,
            phase3_index=0,
        )
        self._prompt_cache: str | None = None  # 当前缓存的提示

    # ---------- 公开 API：对话循环调用 ----------

    def start(self) -> str:
        """启动会话，返回欢迎语"""
        return (
            f"我将带你深入认识自己。整个过程约30分钟，包含三个阶段：\n"
            "1. **Phase 1**：观点探测（选择题，39题，约12分钟）\n"
            "2. **Phase 2**：情境反应（问答题，6个情境，约18分钟）\n"
            "3. **Phase 3**：语料采样（写作任务，3个任务，约5分钟）\n\n"
            "另外，如果你有自己写过的文章或笔记，可以一并提供——"
            "这些真实的表达比即兴回答更能体现你的风格。\n\n"
            "**所有回答仅用于生成你的思维镜像，绝不对外公开。准备好了吗？**\n\n"
            "(回复「开始」继续，或直接进入 Phase 1)"
        )

    def get_next_prompt(self) -> str | None:
        """
        获取下一步要显示给用户的提示。
        返回 None 表示流程结束。
        """
        phase = self.state.current_phase

        if phase == 1:
            return self._get_phase1_prompt()
        elif phase == 2:
            return self._get_phase2_prompt()
        elif phase == 3:
            return self._get_phase3_prompt()
        elif phase == "calibration":
            return None  # 校准阶段由上层调用 calibration 模块
        elif phase == "done":
            return None
        return None

    def submit_answer(self, raw_answer: str) -> str:
        """
        提交用户回答，返回反馈信息。
        反馈信息用于告知用户答案已记录，以及下一步是什么。
        """
        phase = self.state.current_phase
        if phase == 1:
            return self._handle_phase1_answer(raw_answer)
        elif phase == 2:
            return self._handle_phase2_answer(raw_answer)
        elif phase == 3:
            return self._handle_phase3_answer(raw_answer)
        return "未知阶段。"

    def get_session_summary(self) -> dict:
        """获取会话摘要，用于传给 DistillationSession"""
        return {
            "session_id": self.state.session_id,
            "phase1_answers": [asdict(a) for a in self.state.phase1_answers],
            "phase2_answers": [asdict(a) for a in self.state.phase2_answers],
            "phase3_answers": [asdict(a) for a in self.state.phase3_answers],
            "progress": {
                "phase1": f"{len(self.state.phase1_answers)}/{len(self.loader.get_phase1_all())}",
                "phase2": f"{len(self.state.phase2_answers)}/{len(self.loader.get_phase2_all())}",
                "phase3": f"{len(self.state.phase3_answers)}/{len(self.loader.get_phase3_all())}",
            }
        }

    def to_distillation_session(self):
        """
        将对话数据转换为 DistillationSession 格式。
        需要 DistillationSession 类，通过懒加载避免循环导入。
        """
        from generator.skill_generator import DistillationSession
        session = DistillationSession(session_id=self.state.session_id)

        # Phase 1
        for ans in self.state.phase1_answers:
            session.add_phase1_answer(
                question_id=ans.question_id,
                answer=ans.selected_value or ans.raw_answer,
                question_type=ans.question_type,
                normalized_score=ans.normalized_score,
            )

        # Phase 2
        from analyzer.phase2_analyzer import ScenarioResponse
        for ans in self.state.phase2_answers:
            # Build main_answers list of dicts
            main_list = [{"answer": a} for a in ans.main_answers]
            followup_list = [{"answer": a} for a in ans.followup_answers]
            all_texts = ans.main_answers + ans.followup_answers
            session.add_phase2_scenario(
                ScenarioResponse(
                    scenario_id=ans.scenario_id,
                    scenario_title="",
                    description="",
                    main_answers=main_list,
                    followup_answers=followup_list,
                    raw_texts=all_texts,
                )
            )

        # Phase 3
        for ans in self.state.phase3_answers:
            session.add_phase3_text(ans.text)

        return session

    def save(self, path: str | None = None) -> str:
        """将会话状态保存到 JSON 文件"""
        import json
        if path is None:
            path = str(Path.home() / ".workbuddy" / "wangyangming_sessions" / f"{self.state.session_id}.json")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._state_to_dict(), f, ensure_ascii=False, indent=2)
        return path

    @classmethod
    def load(cls, path: str) -> "ConversationFlow":
        """从 JSON 文件恢复会话"""
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        flow = cls(session_id=data["session_id"])
        flow.state.current_phase = data.get("current_phase", 1)
        flow.state.phase1_index = data.get("phase1_index", 0)
        flow.state.phase2_index = data.get("phase2_index", 0)
        flow.state.phase3_index = data.get("phase3_index", 0)
        return flow

    # ---------- 内部方法 ----------

    def _state_to_dict(self) -> dict:
        return {
            "session_id": self.state.session_id,
            "current_phase": self.state.current_phase,
            "phase1_index": self.state.phase1_index,
            "phase1_answers": [asdict(a) for a in self.state.phase1_answers],
            "phase2_index": self.state.phase2_index,
            "phase2_answers": [asdict(a) for a in self.state.phase2_answers],
            "phase3_index": self.state.phase3_index,
            "phase3_answers": [asdict(a) for a in self.state.phase3_answers],
        }

    def _get_phase1_prompt(self) -> str:
        questions = self.loader.get_phase1_all()
        if self.state.phase1_index == 0:
            # 第一次进入 Phase 1
            return PromptBuilder.phase1_intro(len(questions)) + "\n" + \
                   PromptBuilder.phase1_question(questions[0], 1, len(questions))
        # 检查是否已完成
        if self.state.phase1_index >= len(questions):
            return PromptBuilder.phase_complete(1, {
                "answered": len(self.state.phase1_answers),
                "total": len(questions),
            }) + "\n\n" + self._transition_to_phase2()
        # 下一题
        q = questions[self.state.phase1_index]
        return PromptBuilder.phase1_question(q, self.state.phase1_index + 1, len(questions))

    def _get_phase2_prompt(self) -> str:
        scenarios = self.loader.get_phase2_all()
        if self.state.phase2_index == 0:
            return PromptBuilder.phase2_intro(len(scenarios)) + "\n" + \
                   PromptBuilder.phase2_scenario(scenarios[0], 1, len(scenarios))
        if self.state.phase2_index >= len(scenarios):
            return PromptBuilder.phase_complete(2, {
                "answered": len(self.state.phase2_answers),
                "total": len(scenarios),
            }) + "\n\n" + self._transition_to_phase3()
        s = scenarios[self.state.phase2_index]
        return PromptBuilder.phase2_scenario(s, self.state.phase2_index + 1, len(scenarios))

    def _get_phase3_prompt(self) -> str:
        tasks = self.loader.get_phase3_all()
        if self.state.phase3_index == 0:
            return PromptBuilder.phase3_intro(len(tasks)) + "\n" + \
                   PromptBuilder.phase3_task(tasks[0], 1, len(tasks))
        if self.state.phase3_index >= len(tasks):
            return PromptBuilder.phase_complete(3, {
                "answered": len(self.state.phase3_answers),
                "total": len(tasks),
            }) + PromptBuilder.analyzing()
        t = tasks[self.state.phase3_index]
        return PromptBuilder.phase3_task(t, self.state.phase3_index + 1, len(tasks))

    def _handle_phase1_answer(self, raw: str) -> str:
        questions = self.loader.get_phase1_all()
        idx = self.state.phase1_index
        q = questions[idx]

        answer_text = raw.strip()
        selected_value = None
        selected_label = None
        score = 5.0

        if q.get("type") == "single_choice":
            selected_value = answer_text[0].upper() if answer_text else "?"
            selected_label = None
            for opt in q.get("options", []):
                if opt["value"] == selected_value:
                    selected_label = opt["label"]
                    break
            if selected_label is None:
                selected_label = selected_value  # fallback to value itself
            score = ScoreMapper.map_single_choice(q, selected_value)

        elif q.get("type") == "ranking":
            # 支持格式：B>A>C>D 或 B A C D 或 B, A, C, D
            raw_input = answer_text.replace(",", " ").replace(">", " ").replace("<", " ")
            order = [c.strip().upper() for c in raw_input.split() if c.strip()]
            selected_value = " ".join(order)
            selected_label = "排序：" + selected_value
            score = ScoreMapper.map_ranking(order)

        elif q.get("type") == "text_input":
            selected_value = answer_text[:20]
            score = ScoreMapper.map_text_input(answer_text)

        answer = Phase1Answer(
            question_id=q["id"],
            question_type=q.get("type", "single_choice"),
            raw_answer=answer_text,
            selected_value=selected_value,
            selected_label=selected_label,
            normalized_score=score,
        )
        self.state.phase1_answers.append(answer)

        feedback = PromptBuilder.phase1_feedback(q["id"], selected_value or "-", selected_label or answer_text[:20])

        # 移动到下一题
        self.state.phase1_index += 1
        if self.state.phase1_index >= len(questions):
            feedback += "\n\n" + PromptBuilder.phase_complete(1, {
                "answered": len(self.state.phase1_answers),
                "total": len(questions),
            }) + "\n\n" + self._transition_to_phase2()
            self.state.current_phase = 2
        else:
            next_q = questions[self.state.phase1_index]
            feedback += "\n\n" + PromptBuilder.phase1_question(
                next_q, self.state.phase1_index + 1, len(questions)
            )

        return feedback

    def _handle_phase2_answer(self, raw: str) -> str:
        scenarios = self.loader.get_phase2_all()
        idx = self.state.phase2_index
        s = scenarios[idx]
        text = raw.strip()

        # 查找当前情境的未完成答案对象
        current = None
        for ans in self.state.phase2_answers:
            if ans.scenario_id == s["id"]:
                current = ans
                break

        if current is None:
            # 主问题回答
            current = Phase2Answer(
                scenario_id=s["id"],
                main_answers=[text],
            )
            self.state.phase2_answers.append(current)
        else:
            # 追问回答
            current.followup_answers.append(text)
            self.state.phase2_followup_active = False

        # 判断是否需要追问
        need_followup = len(text) < 50 and s.get("followUpQuestions")
        if need_followup and not self.state.phase2_followup_active:
            followup = s["followUpQuestions"][0]
            self.state.phase2_followup_active = True
            return (
                f"明白了。记录已保存 ✓\n"
                + PromptBuilder.phase2_followup(s["id"], followup)
            )

        # 进入下一情境
        self.state.phase2_index += 1
        if self.state.phase2_index >= len(scenarios):
            feedback = PromptBuilder.phase_complete(2, {
                "answered": len(self.state.phase2_answers),
                "total": len(scenarios),
            }) + "\n\n" + self._transition_to_phase3()
            self.state.current_phase = 3
        else:
            next_s = scenarios[self.state.phase2_index]
            feedback = f"记录已保存 ✓\n\n" + PromptBuilder.phase2_scenario(
                next_s, self.state.phase2_index + 1, len(scenarios)
            )

        return feedback

    def _handle_phase3_answer(self, raw: str) -> str:
        tasks = self.loader.get_phase3_all()
        idx = self.state.phase3_index
        t = tasks[idx]
        text = raw.strip()

        answer = Phase3Answer(
            task_id=t["id"],
            task_title=t["title"],
            text=text,
            char_count=len(text),
        )
        self.state.phase3_answers.append(answer)

        self.state.phase3_index += 1
        if self.state.phase3_index >= len(tasks):
            feedback = PromptBuilder.phase_complete(3, {
                "answered": len(self.state.phase3_answers),
                "total": len(tasks),
            }) + PromptBuilder.analyzing()
            self.state.current_phase = "calibration"
        else:
            next_t = tasks[self.state.phase3_index]
            feedback = f"已记录（{len(text)} 字）✓\n\n" + PromptBuilder.phase3_task(
                next_t, self.state.phase3_index + 1, len(tasks)
            )

        return feedback

    def _transition_to_phase2(self) -> str:
        scenarios = self.loader.get_phase2_all()
        s = scenarios[0]
        return (
            f"---\n\n"
            f"## 进入 Phase 2：情境反应\n\n"
            f"共 {len(scenarios)} 个情境。请根据每个情境，详细描述你的想法和决策过程。\n"
            f"如果回答较短，我会追加追问。\n\n"
            + PromptBuilder.phase2_scenario(s, 1, len(scenarios))
        )

    def _transition_to_phase3(self) -> str:
        tasks = self.loader.get_phase3_all()
        t = tasks[0]
        return (
            f"---\n\n"
            f"## 进入 Phase 3：语料采样\n\n"
            f"共 {len(tasks)} 个写作任务。像平时写东西一样自然表达即可。\n\n"
            + PromptBuilder.phase3_task(t, 1, len(tasks))
        )


# ============================================================
# 便捷函数（导出给 WorkBuddy AI 直接调用）
# ============================================================

_default_flow: ConversationFlow | None = None


def start_session(session_id: str | None = None) -> ConversationFlow:
    """启动新会话"""
    global _default_flow
    _default_flow = ConversationFlow(session_id=session_id)
    return _default_flow


def get_active_session() -> ConversationFlow | None:
    """获取当前活跃会话"""
    return _default_flow


def submit(raw_answer: str) -> str:
    """快捷提交答案"""
    global _default_flow
    if _default_flow is None:
        return "没有活跃会话，请先调用 start_session()。"
    return _default_flow.submit_answer(raw_answer)


def run_full_conversation(
    llm_provider: callable,
    output_dir: str | None = None,
    session_id: str | None = None,
) -> tuple[str, str]:
    """
    完整蒸馏流程：启动对话 → 逐题收集 → 分析生成 → 返回 Skill 路径

    参数：
        llm_provider: LLM 调用函数，签名为 fn(prompt: str, model: str) -> str
        output_dir: Skill 输出目录，默认 ~/.workbuddy/skills/{skill_name}/
        session_id: 会话 ID

    返回：
        (summary_markdown, skill_file_path)
    """
    flow = start_session(session_id)

    # 启动
    summary = ["# 蒸馏会话摘要\n"]
    summary.append(f"Session ID: `{flow.state.session_id}`")
    summary.append(f"\n{flow.start()}\n")

    # 预填充模拟答案用于演示（真实场景由用户逐步提交）
    # 这里仅用于测试流程可用性
    _demo_fill(flow)

    # 转换为 DistillationSession 并运行分析
    session = flow.to_distillation_session()

    # 保存会话
    session_path = flow.save()
    summary.append(f"\n会话已保存：{session_path}")

    # 运行分析
    integration = session.integrate_all_phases(llm_provider=llm_provider)

    # 校准
    from analyzer.calibration import run_calibration
    cal_result = run_calibration(
        integration_result=session._dict_from_dataclass(integration),
        calibration_responses={},
        followup_questions=[],
    )
    summary.append(f"\n## 校准结果")
    summary.append(f"- 准确度：{cal_result.accuracy:.1f}%")
    summary.append(f"- 等级：{cal_result.accuracy_level}")
    summary.append(f"- 追问建议：{cal_result.followup_needed}")

    # 生成 Skill
    skill_path = session.generate_skill(
        skill_name=f"wangyangming-{flow.state.session_id}",
        llm_provider=llm_provider,
        output_dir=output_dir,
    )

    summary_text = "\n".join(summary)
    return summary_text, skill_path


def _demo_fill(flow: ConversationFlow) -> None:
    """
    用合理分布的模拟答案预填充会话。
    仅用于开发/测试。真实场景由用户逐步提交。
    """
    import random
    random.seed(flow.state.session_id or "demo")

    # Phase 1
    questions = flow.loader.get_phase1_all()
    for q in questions:
        if q.get("type") == "single_choice":
            opts = [o["value"] for o in q.get("options", [])]
            if opts:
                choice = random.choice(opts)
                flow.submit_answer(choice)
        elif q.get("type") == "ranking":
            items = [o.get('id', o.get('value', '?')) for o in q.get("items", [])]
            random.shuffle(items)
            flow.submit_answer(" > ".join(items))
        else:
            flow.submit_answer("我觉得这个问题需要从多个角度来看。")

    # Phase 2
    scenarios = flow.loader.get_phase2_all()
    for s in scenarios:
        flow.submit_answer(
            f"如果是我遇到这种情况，我会先冷静分析一下具体的情况。"
            f"我会考虑几个方面的因素：首先是对他人的影响，然后是自己的承受能力，"
            f"最后是长远的后果。在这个基础上做一个综合判断。"
        )

    # Phase 3
    flow.submit_answer(
        "成功不是外在的标准，而是内心的安定。我见过很多人事业有成但内心焦虑，"
        "也见过普通人生活简朴但非常满足。对我来说，成功就是能够按照自己的意愿生活，"
        "并且对自己诚实。"
    )
    flow.submit_answer(
        "要不要辞职创业，我觉得要看具体情况。如果已经有了清晰的方向和足够的储备，"
        "可以尝试。如果只是一时冲动，还是再等等看。"
    )
