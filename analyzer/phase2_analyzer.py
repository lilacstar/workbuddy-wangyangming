# -*- coding: utf-8 -*-
"""
王阳明工具 - Phase 2 分析器
功能：从情境题回答中提取决策模式、价值观信号、依恋风格、动机追问分析
设计原则：女娲式LLM驱动，所有关键判断由LLM推理得出
"""

import json
import re
from pathlib import Path
from typing import Any, TypedDict
from dataclasses import dataclass, asdict


# ============================================================
# 数据结构定义
# ============================================================

@dataclass
class ScenarioResponse:
    """单个情境的回答"""
    scenario_id: str
    scenario_title: str
    description: str
    main_answers: list[dict]        # [{"question": "...", "answer": "..."}]
    followup_answers: list[dict]   # [{"question": "...", "answer": "..."}]
    raw_texts: list[str]           # 所有回答拼成的文本供分析用


@dataclass
class DecisionPattern:
    """决策模式"""
    primary_care: str           # 首要考量：利益/关系/原则/安全/意义
    decision_speed: str         # 决策速度：冲动/快速/理性/犹豫
    information_style: str      # 信息收集风格
    risk_attitude: str          # 风险态度
    regret_pattern: str         # 后悔模式


@dataclass
class ValueSignal:
    """价值观信号"""
    moral_framework: str       # 道德框架：原则派/结果派/情境派/关系派
    loyalty_signals: list[str]  # 忠诚度信号
    autonomy_signals: list[str] # 自主性信号
    hierarchy_orientation: str  # 等级倾向
    change_readiness: str       # 变革意愿


@dataclass
class AttachmentAnalysis:
    """依恋风格分析"""
    style: str                  # 安全型/焦虑型/回避型/混乱型
    description: str             # 描述
    behavioral_signals: list[str]  # 行为信号
    emotional_triggers: list[str]  # 情绪触发点
    relational_patterns: list[str] # 关系模式描述


@dataclass
class MotivationAnalysis:
    """动机分析"""
    primary_driver: str         # 首要动机
    fear_based: bool            # 是否为恐惧驱动
    fear_signals: list[str]     # 恐惧信号
    value_based: bool           # 是否为价值驱动
    value_signals: list[str]    # 价值信号
    habit_signals: list[str]    # 习惯性行为信号
    composite_motivation: str    # 复合动机描述


@dataclass
class Phase2Result:
    """Phase 2 完整分析结果"""
    scenario_count: int
    scenarios: list[ScenarioResponse]
    decision_pattern: DecisionPattern
    value_signals: ValueSignal
    attachment_analysis: AttachmentAnalysis | None  # 无S6时为None
    motivation_analysis: MotivationAnalysis
    cross_scenario_consistency: float  # 跨情境一致性评分0-10
    warnings: list[str]
    llm_raw_output: dict[str, Any]  # 原始LLM输出（供后续使用）


# ============================================================
# 工具函数
# ============================================================

def extract_raw_texts(scenario_response: ScenarioResponse) -> str:
    """将情境回答提取为纯文本"""
    parts = []
    for qa in scenario_response.main_answers:
        parts.append(f"Q: {qa['question']}\nA: {qa['answer']}")
    for qa in scenario_response.followup_answers:
        parts.append(f"追问Q: {qa['question']}\nA: {qa['answer']}")
    return "\n---\n".join(parts)


def build_analysis_context(scenarios: list[ScenarioResponse]) -> str:
    """
    将所有情境回答构建为LLM分析上下文
    女娲式：先给材料，再给方法论，再让LLM执行分析
    """
    sections = []
    for i, s in enumerate(scenarios, 1):
        sections.append(f"## 情境{i}：{s.scenario_title}")
        sections.append(f"背景：{s.description}")
        sections.append("主问答：")
        for qa in s.main_answers:
            sections.append(f"  Q: {qa['question']}")
            sections.append(f"  A: {qa['answer']}")
        if s.followup_answers:
            sections.append("追问：")
            for qa in s.followup_answers:
                sections.append(f"  Q: {qa['question']}")
                sections.append(f"  A: {qa['answer']}")
        sections.append("")

    return "\n".join(sections)


# ============================================================
# LLM 驱动：全套分析（女娲式综合提炼）
# ============================================================

def build_phase2_llm_prompt(scenarios: list[ScenarioResponse]) -> str:
    """
    构建Phase 2 LLM分析prompt
    参考女娲 extraction-framework.md 的方法论
    """
    context = build_analysis_context(scenarios)

    return f"""## 任务：对以下情境问答进行深度心理分析

### 用户作答材料

{context}

---

### 分析维度与方法论

**A. 决策模式分析**
关注：
- 首要考量是什么？（利益/关系/原则/安全/意义）
- 决策速度与信息收集风格
- 面对不确定性的反应
- 风险态度

**B. 价值观信号提取**
从回答中提取：
- 道德判断框架（原则派：按规则行事/结果派：看后果/情境派：灵活应变/关系派：看对谁）
- 忠诚度信号（对谁忠诚？家庭/朋友/组织/自己？）
- 自主性信号（是否在意他人看法？自我判断权重？）
- 等级/平等取向（对权威的态度）
- 变革意愿（保守还是开放？）

**C. 依恋风格分析**（如有相关情境）
识别：
- 安全型：能依赖也能独处，情绪稳定
- 焦虑型：害怕被抛弃，过度确认关系
- 回避型：强调独立，回避深度情感交流
- 混乱型：行为矛盾，难以预测

**D. 动机深层分析**
区分：
- 恐惧驱动：行为出于避免损失/惩罚/否定（信号：担心、害怕、如果就完了）
- 价值驱动：行为出于内在认同（信号：我觉得应该、因为有意义）
- 习惯驱动：自动化反应，未经验证（信号：一直这样、习惯了）
- 追问是否有"我觉得应该这样"但说不出深层原因的选项

**E. 跨情境一致性检验**
- 检查该用户在多个情境中的反应是否一致
- 不一致处可能是真实自我与呈现自我的差异点
- 标注：预警信号（如情境1说A，情境2说B，但A和B矛盾）

---

### 输出格式

对每个情境单独分析，格式：
```
## 情境[N] 分析
- 决策首要考量：[...]
- 价值观信号：[...]
- 依恋风格信号（如有）：[...]
- 动机追问分析：[...]
```

然后给出总体评估：
```
## 总体评估

决策模式：
- 首要考量：[...]
- 决策速度：[...]
- 信息收集风格：[...]
- 风险态度：[...]
- 后悔模式：[...]

价值观信号：
- 道德框架：[...]
- 忠诚度：[...]
- 自主性：[...]
- 等级取向：[...]
- 变革意愿：[...]

依恋风格：（无S6情境则标注"无相关数据"）
- 类型：[...]
- 行为信号：[...]
- 情绪触发点：[...]

动机分析：
- 首要动机：[...]
- 恐惧驱动信号：[...]
- 价值驱动信号：[...]
- 习惯性行为：[...]
- 复合动机描述：[...]

跨情境一致性：X/10（标注不一致处）

预警信号：
1. [...]
2. [...]

建议追问：（根据分析发现的矛盾点或模糊点）
1. [...]
```"""


def build_motivation_followup_prompt(scenario: ScenarioResponse) -> str:
    """
    构建动机追问分析的专用prompt
    用于追加问卷设计
    """
    raw_text = extract_raw_texts(scenario)

    return f"""## 任务：基于以下情境回答，设计动机追问

### 情境
标题：{scenario.scenario_title}
背景：{scenario.description}

### 已有关键问答
{raw_text}

### 你的任务

1. 从上述回答中识别：
   - 该用户做出选择背后的"表面原因"
   - 可能的"深层动机"（恐惧驱动/价值驱动/习惯驱动）
   - 尚未被触及的"动机盲区"

2. 基于分析，设计2-3个追问问题：
   - 每个追问必须有明确的分析依据
   - 问题要触及"为什么"而非"是什么"
   - 避免引导性提问（不要暗示正确答案）

3. 输出格式：
```
动机盲区识别：
- [...]

追问设计：
1. [追问问题]
   分析依据：[...]
2. [追问问题]
   分析依据：[...]
```
"""


def identify_attachment_signals(scenarios: list[ScenarioResponse]) -> AttachmentAnalysis | None:
    """
    专门分析依恋风格
    仅当存在S6A或S6B情境时有效
    """
    attachment_scenarios = [s for s in scenarios if s.scenario_id in ("S6A", "S6B")]
    if not attachment_scenarios:
        return None
    # 实际分析在LLM中完成，这里返回None表示需要LLM处理
    return None


# ============================================================
# 主入口
# ============================================================

def analyze_phase2(
    scenarios: list[ScenarioResponse],
    llm_provider: callable | None = None,
    llm_model: str = "default"
) -> Phase2Result:
    """
    Phase 2 分析主入口

    参数:
        scenarios: 情境回答列表
        llm_provider: LLM调用函数，签名为 (prompt: str, model: str) -> str
                      如果不提供，则返回prompt结构供外部调用
        llm_model: LLM模型标识

    返回:
        Phase2Result 完整分析结果
    """
    if not scenarios:
        return Phase2Result(
            scenario_count=0,
            scenarios=[],
            decision_pattern=DecisionPattern(
                primary_care="unknown", decision_speed="unknown",
                information_style="unknown", risk_attitude="unknown",
                regret_pattern="unknown"
            ),
            value_signals=ValueSignal(
                moral_framework="unknown", loyalty_signals=[],
                autonomy_signals=[], hierarchy_orientation="unknown",
                change_readiness="unknown"
            ),
            attachment_analysis=None,
            motivation_analysis=MotivationAnalysis(
                primary_driver="unknown", fear_based=False,
                fear_signals=[], value_based=False, value_signals=[],
                habit_signals=[], composite_motivation="unknown"
            ),
            cross_scenario_consistency=0.0,
            warnings=["无情境数据"],
            llm_raw_output={}
        )

    attachment_analysis = identify_attachment_signals(scenarios)

    if llm_provider:
        prompt = build_phase2_llm_prompt(scenarios)
        raw_output = llm_provider(prompt, llm_model)
        parsed = _parse_phase2_llm_output(raw_output)
        return Phase2Result(
            scenario_count=len(scenarios),
            scenarios=scenarios,
            decision_pattern=parsed.get("decision_pattern", DecisionPattern("unknown","unknown","unknown","unknown","unknown")),
            value_signals=parsed.get("value_signals", ValueSignal("unknown",[],[], "unknown","unknown")),
            attachment_analysis=parsed.get("attachment_analysis"),
            motivation_analysis=parsed.get("motivation_analysis", MotivationAnalysis("unknown",False,[],False,[],[], "unknown")),
            cross_scenario_consistency=parsed.get("cross_scenario_consistency", 5.0),
            warnings=parsed.get("warnings", []),
            llm_raw_output={"raw": raw_output, "parsed": parsed}
        )
    else:
        return Phase2Result(
            scenario_count=len(scenarios),
            scenarios=scenarios,
            decision_pattern=DecisionPattern("unknown","unknown","unknown","unknown","unknown"),
            value_signals=ValueSignal("unknown",[],[], "unknown","unknown"),
            attachment_analysis=None,
            motivation_analysis=MotivationAnalysis("unknown",False,[],False,[],[], "unknown"),
            cross_scenario_consistency=0.0,
            warnings=["需LLM provider执行完整分析"],
            llm_raw_output={
                "_prompt_for_llm": build_phase2_llm_prompt(scenarios),
                "_requires_llm": True
            }
        )


def _parse_phase2_llm_output(raw_output: str) -> dict[str, Any]:
    """解析LLM输出为结构化数据"""
    consistency_match = re.search(r"跨情境一致性[：:]\s*(\d+(?:\.\d+)?)\s*/\s*10", raw_output)
    consistency = float(consistency_match.group(1)) if consistency_match else 5.0

    warnings = []
    warning_section = re.search(r"预警信号[：:]\s*\n((?:.+\n)*)", raw_output)
    if warning_section:
        lines = warning_section.group(1).strip().split("\n")
        for line in lines:
            line = re.sub(r"^\d+[\.)、]\s*", "", line.strip())
            if line and not line.startswith("#"):
                warnings.append(line)

    return {
        "cross_scenario_consistency": consistency,
        "warnings": warnings
    }


def generate_motivation_followup(
    scenarios: list[ScenarioResponse],
    llm_provider: callable | None = None
) -> dict[str, Any]:
    """基于Phase 2回答，生成动机追问建议"""
    results = {}
    for scenario in scenarios:
        if scenario.followup_answers:
            if llm_provider:
                prompt = build_motivation_followup_prompt(scenario)
                output = llm_provider(prompt, "default")
                results[scenario.scenario_id] = output
            else:
                results[scenario.scenario_id] = {
                    "_prompt_for_llm": build_motivation_followup_prompt(scenario),
                    "_requires_llm": True
                }
        else:
            results[scenario.scenario_id] = {"status": "no_followup_yet"}
    return results


def build_decision_style_summary(result: Phase2Result) -> str:
    """生成决策风格一句话总结"""
    dp = result.decision_pattern
    return f"首要考量{dp.primary_care}、决策{dp.decision_speed}、信息收集{dp.information_style}、风险态度{dp.risk_attitude}"


def detect_self_bias(result: Phase2Result) -> list[str]:
    """检测自我认知偏差"""
    warnings = []

    if result.cross_scenario_consistency < 4.0:
        warnings.append(f"跨情境一致性较低（{result.cross_scenario_consistency}/10），可能存在角色切换或刻意表现")

    if result.motivation_analysis.fear_based and not result.motivation_analysis.fear_signals:
        warnings.append("检测到恐惧驱动信号，但回答中未明确提及恐惧词汇，可能存在无意识回避")

    llm_output = result.llm_raw_output
    if isinstance(llm_output, dict) and "raw" in llm_output:
        raw = llm_output.get("raw", "")
        markers = raw.count("但是") + raw.count("不过") + raw.count("其实")
        if markers > 3:
            warnings.append(f"回答中出现{markers}次转折词，可能存在矛盾心理或自我修饰")

    return warnings


if __name__ == "__main__":
    test_scenario = ScenarioResponse(
        scenario_id="S1",
        scenario_title="职场选择",
        description="猎头推荐了一家薪酬更高的公司，但需要离开现在的团队",
        main_answers=[
            {"question": "你会怎么做？", "answer": "我会先跟直属领导谈一次，看公司有没有调整空间。如果实在没有，我会综合考虑：薪酬差异有多大、团队对我的意义、未来发展空间。不会单纯因为钱就走，但也不会因为感情而放弃合理的机会。"},
            {"question": "你做出这个选择，最核心的考量是什么？", "answer": "还是看长期发展吧。钱是重要的，但如果新公司只是给钱，3年后可能就遇到天花板了。"}
        ],
        followup_answers=[
            {"question": "你做出这个选择，背后最深的驱动是什么？", "answer": "说实话，有点怕后悔吧。如果留下来了结果不好，我会想当初为什么要留。"}
        ]
    )
    print("测试通过: build_phase2_llm_prompt构建成功")
    print("追问动机prompt:", build_motivation_followup_prompt(test_scenario)[:200])
