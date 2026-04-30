# -*- coding: utf-8 -*-
"""
王阳明工具 - 三阶段整合器
功能：整合Phase 1/2/3结果 → 交叉验证 → 生成心智模型 → 生成决策启发式
设计原则：女娲式方法论 + 自我认知偏差检测
"""

import json
import re
from typing import Any
from dataclasses import dataclass, asdict


@dataclass
class MentalModel:
    """单个心智模型"""
    name: str
    description: str
    evidence: list[str]
    prediction: str
    confidence: str


@dataclass
class DecisionHeuristic:
    """单个决策启发式"""
    number: int
    title: str
    description: str
    scene: str
    source: str
    reasoning_chain: str


@dataclass
class BiasFlag:
    """偏差标注"""
    type: str
    description: str
    evidence: list[str]
    severity: str
    mitigation: str


@dataclass
class PersonalityPortrait:
    """综合人物画像"""
    one_line: str
    core_traits: list[str]
    decision_style: str
    communication_style: str
    growth_edge: str
    self_other_gap: str


@dataclass
class IntegratedResult:
    """整合后的完整结果"""
    phase1_summary: dict
    phase2_summary: dict
    phase3_summary: dict
    mental_models: list[MentalModel]
    decision_heuristics: list[DecisionHeuristic]
    bias_flags: list[BiasFlag]
    portrait: PersonalityPortrait | None
    cross_phase_consistency: float
    overall_confidence: str
    warnings: list[str]


def _get_dimension(phase1: dict, dim_key: str) -> float | None:
    """从Phase 1结果中提取指定维度的得分"""
    dim_scores = phase1.get("dimension_scores", [])
    dim_map = {
        "introversion": ["内省", "反思", "自省"],
        "risk": ["风险", "风险偏好"],
        "autonomy": ["自主", "自主性"],
        "social": ["社会", "关系", "归属"],
    }
    targets = dim_map.get(dim_key, [])
    for d in dim_scores:
        label = d.get("label", "")
        if any(t in label for t in targets):
            return d.get("normalized")
    return None


def _get_reflection_depth(phase2: dict) -> float | None:
    """从Phase 2结果中推断反思深度"""
    motivation = phase2.get("motivation_analysis", {})
    if isinstance(motivation, dict):
        fear_count = len(motivation.get("fear_signals", []))
        value_count = len(motivation.get("value_signals", []))
        if fear_count > value_count * 2:
            return 4.0
        elif value_count > 0:
            return 6.0 + value_count * 0.5
    return 5.0


def _get_risk_behavior(phase2: dict) -> float | None:
    """从Phase 2结果中推断实际风险行为"""
    decision = phase2.get("decision_pattern", {})
    if isinstance(decision, dict):
        risk_attitude = decision.get("risk_attitude", "")
        speed = decision.get("decision_speed", "")
        if "冲动" in risk_attitude or "快速" in speed:
            return 7.5
        elif "保守" in risk_attitude or "犹豫" in speed:
            return 3.5
    return 5.0


def _get_dependency_signal(phase2: dict) -> float | None:
    """从Phase 2结果中推断依赖性"""
    value = phase2.get("value_signals", {})
    if isinstance(value, dict):
        autonomy = value.get("autonomy_signals", [])
        if isinstance(autonomy, list):
            dependency_keywords = ["别人", "他人", "陪", "一起", "大家", "共识"]
            dep_count = sum(1 for sig in autonomy if any(k in str(sig) for k in dependency_keywords))
            return 3.0 + dep_count * 2.0 if dep_count else 5.0
    return 5.0


def check_cross_phase_consistency(
    phase1: dict, phase2: dict, phase3: dict
) -> tuple[float, list[str]]:
    """检测三个阶段的交叉一致性"""
    warnings = []
    consistency_checks = []

    p1_introversion = _get_dimension(phase1, "introversion")
    p2_reflection_depth = _get_reflection_depth(phase2)
    if p1_introversion and p2_reflection_depth:
        gap = abs(p1_introversion - p2_reflection_depth)
        if gap > 3:
            warnings.append(
                f"Phase 1内省({p1_introversion})与Phase 2反思深度({p2_reflection_depth})差距较大"
                f"，可能存在过度美化自我认知"
            )
            consistency_checks.append(5.0)
        else:
            consistency_checks.append(8.0)

    p1_risk = _get_dimension(phase1, "risk")
    p2_risk_behavior = _get_risk_behavior(phase2)
    if p1_risk and p2_risk_behavior:
        gap = abs(p1_risk - p2_risk_behavior)
        if gap > 4:
            warnings.append(
                f"Phase 1风险偏好({p1_risk})与Phase 2实际风险行为({p2_risk_behavior})不一致"
            )
            consistency_checks.append(4.0)
        else:
            consistency_checks.append(8.0)

    p1_autonomy = _get_dimension(phase1, "autonomy")
    p2_dependency = _get_dependency_signal(phase2)
    if p1_autonomy and p2_dependency:
        if p1_autonomy > 7 and p2_dependency > 7:
            warnings.append(
                f"Phase 1自主性很高({p1_autonomy})但Phase 2显示依赖信号({p2_dependency})，"
                f"可能存在理想自我与实际自我的落差"
            )
            consistency_checks.append(3.0)

    phase2_consistency = phase2.get("cross_scenario_consistency", 5.0)
    consistency_checks.append(phase2_consistency)

    avg_consistency = sum(consistency_checks) / len(consistency_checks) if consistency_checks else 5.0
    return round(avg_consistency, 1), warnings


def detect_cognitive_bias(
    phase1: dict, phase2: dict, phase3: dict, cross_consistency: float
) -> list[BiasFlag]:
    """检测自我认知偏差"""
    flags = []

    if cross_consistency < 5.0:
        flags.append(BiasFlag(
            type="整体一致性偏低",
            description="三个阶段的回答一致性较差，可能存在刻意表现或情境切换",
            evidence=[f"跨阶段一致性评分仅{cross_consistency}/10"],
            severity="high",
            mitigation="建议增加追问和边缘案例测试"
        ))

    warnings = phase2.get("warnings", [])
    for w in warnings:
        if "社会赞许" in w or "粉饰" in w:
            flags.append(BiasFlag(
                type="社会赞许偏差",
                description="可能存在过度展现正面形象、隐藏负面特质的倾向",
                evidence=[w],
                severity="medium",
                mitigation="追问时使用反向问法来对冲"
            ))

    phase2_consistency = phase2.get("cross_scenario_consistency", 10.0)
    if phase2_consistency < 4.0:
        flags.append(BiasFlag(
            type="情境依赖性",
            description="在不同情境中表现差异较大，可能存在角色切换",
            evidence=[f"Phase 2跨情境一致性{phase2_consistency}/10"],
            severity="medium",
            mitigation="标注高情境依赖的特质，不强行归类为稳定特质"
        ))

    phase3_warnings = phase3.get("warnings", [])
    for w in phase3_warnings:
        if "套路" in w or "模式化" in w:
            flags.append(BiasFlag(
                type="表达套路化",
                description="写作呈现套路化倾向，可能在刻意维持某种人设",
                evidence=[w],
                severity="low",
                mitigation="关注是否有突破套路的时刻"
            ))

    return flags


def build_integration_prompt(
    phase1_summary: dict, phase2_summary: dict, phase3_summary: dict,
    cross_consistency: float, bias_flags: list[BiasFlag]
) -> str:
    """构建三阶段整合的LLM prompt"""

    p1_dims = phase1_summary.get("dimension_scores", [])
    p1_text = "\n".join(f"- {d['label']}: {d['normalized']}/10" for d in p1_dims)
    p1_pattern = phase1_summary.get("pattern_analysis", {})
    p1_desc = p1_pattern.get("primary_pattern", "未识别")

    p2_decision = phase2_summary.get("decision_pattern", {})
    p2_value = phase2_summary.get("value_signals", {})
    p2_motivation = phase2_summary.get("motivation_analysis", {})

    p2_text = "\n".join([
        f"决策模式：首要考量={p2_decision.get('primary_care','unknown')} | "
        f"速度={p2_decision.get('decision_speed','unknown')} | "
        f"风险={p2_decision.get('risk_attitude','unknown')}",
        f"道德框架：{p2_value.get('moral_framework','unknown')}",
        f"变革意愿：{p2_value.get('change_readiness','unknown')}",
        f"动机：{'恐惧驱动' if p2_motivation.get('fear_based') else '价值驱动' if p2_motivation.get('value_based') else 'unknown'}",
    ])

    p3_dna = phase3_summary.get("expression_dna", {})
    p3_text = f"标签：{', '.join(p3_dna.get('composite_tags', []))} | 画像：{p3_dna.get('one_line_portrait', 'unknown')}"

    bias_text = "\n".join(
        f"- [{b.severity}] {b.type}：{b.description}"
        for b in bias_flags
    ) if bias_flags else "无明显偏差信号"

    return f"""## 任务：整合三个阶段，生成心智模型、决策启发式和综合画像

### Phase 1 人格维度
类型：**{p1_desc}**
{p1_text}

### Phase 2 情境行为
{p2_text}

### Phase 3 表达风格
{p3_text}

### 跨阶段一致性：**{cross_consistency}/10**
### 偏差信号
{bias_text}

### 要求
1. 保留张力，不强行化解矛盾
2. 心智模型必须能预测此人在新情境中的反应
3. 明确说明"不是什么"（排他性）
4. 避免空泛标签，要有具体行为和语言特征

### 输出：心智模型（3-5个）+ 决策启发式（5-8条）+ 人物画像
```json
{{
  "mental_models": [
    {{
      "name": "模型名称",
      "description": "一句话描述",
      "evidence": ["证据1", "证据2"],
      "prediction": "能预测...",
      "confidence": "high"
    }}
  ],
  "decision_heuristics": [
    {{
      "number": 1,
      "title": "启发式标题",
      "description": "含义",
      "scene": "适用场景",
      "source": "来自Phase X",
      "reasoning_chain": "推理链"
    }}
  ],
  "portrait": {{
    "one_line": "一句话总结",
    "core_traits": ["特质1", "特质2"],
    "decision_style": "描述",
    "communication_style": "描述",
    "growth_edge": "盲区",
    "self_other_gap": "差距"
  }},
  "integration_confidence": "high/medium/low"
}}
```"""


def _to_dict(obj) -> dict:
    """将dataclass转为dict"""
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    elif hasattr(obj, "__dataclass_fields__"):
        return {f: _to_dict(getattr(obj, f)) for f in obj.__dataclass_fields__}
    return obj


def _summarize_phase1(phase1_result: dict) -> dict:
    return {
        "dimension_scores": phase1_result.get("dimension_scores", []),
        "pattern_analysis": phase1_result.get("pattern_analysis", {}),
        "warnings": phase1_result.get("warnings", [])
    }


def _summarize_phase2(phase2_result: dict) -> dict:
    dp = phase2_result.get("decision_pattern", {})
    vs = phase2_result.get("value_signals", {})
    ma = phase2_result.get("motivation_analysis", {})
    return {
        "decision_pattern": _to_dict(dp),
        "value_signals": _to_dict(vs),
        "motivation_analysis": _to_dict(ma),
        "cross_scenario_consistency": phase2_result.get("cross_scenario_consistency", 5.0),
        "warnings": phase2_result.get("warnings", [])
    }


def _summarize_phase3(phase3_result: dict) -> dict:
    dna = phase3_result.get("expression_dna", {})
    if hasattr(dna, "__dataclass_fields__"):
        dna = {f: getattr(dna, f) for f in dna.__dataclass_fields__}
    return {
        "expression_dna": dna,
        "warnings": phase3_result.get("warnings", [])
    }


def _parse_integration_output(raw_output: str) -> dict[str, Any]:
    match = re.search(r"```json\s*(.*?)\s*```", raw_output, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return {}


def integrate_three_phases(
    phase1_result: dict,
    phase2_result: dict,
    phase3_result: dict,
    llm_provider: callable | None = None,
    llm_model: str = "default"
) -> IntegratedResult:
    """三阶段整合主入口"""
    cross_consistency, cross_warnings = check_cross_phase_consistency(
        phase1_result, phase2_result, phase3_result
    )
    bias_flags = detect_cognitive_bias(
        phase1_result, phase2_result, phase3_result, cross_consistency
    )

    phase1_summary = _summarize_phase1(phase1_result)
    phase2_summary = _summarize_phase2(phase2_result)
    phase3_summary = _summarize_phase3(phase3_result)

    mental_models = []
    decision_heuristics = []
    portrait = None

    if llm_provider:
        prompt = build_integration_prompt(
            phase1_summary, phase2_summary, phase3_summary,
            cross_consistency, bias_flags
        )
        raw_output = llm_provider(prompt, llm_model)
        parsed = _parse_integration_output(raw_output)
        mental_models = [MentalModel(**m) for m in parsed.get("mental_models", [])]
        decision_heuristics = [DecisionHeuristic(**h) for h in parsed.get("decision_heuristics", [])]
        portrait_dict = parsed.get("portrait", {})
        if portrait_dict:
            portrait = PersonalityPortrait(**portrait_dict)

    severity_map = {"high": 3, "medium": 2, "low": 1}
    bias_penalty = sum(severity_map.get(b.severity, 1) for b in bias_flags) * 0.5
    adjusted = max(0, cross_consistency - bias_penalty)
    confidence = "high" if adjusted >= 7.0 else "medium" if adjusted >= 4.0 else "low"

    all_warnings = cross_warnings + [b.description for b in bias_flags]

    return IntegratedResult(
        phase1_summary=phase1_summary,
        phase2_summary=phase2_summary,
        phase3_summary=phase3_summary,
        mental_models=mental_models,
        decision_heuristics=decision_heuristics,
        bias_flags=bias_flags,
        portrait=portrait,
        cross_phase_consistency=cross_consistency,
        overall_confidence=confidence,
        warnings=all_warnings
    )


def result_to_dict(result: IntegratedResult) -> dict:
    return _to_dict(asdict(result))


def generate_summary_markdown(result: IntegratedResult) -> str:
    lines = [
        "# 用户思维蒸馏报告",
        f"**整合置信度：{result.overall_confidence}**（跨阶段一致性 {result.cross_phase_consistency}/10）",
        "---",
    ]
    if result.portrait:
        p = result.portrait
        lines.extend([
            "## 综合画像",
            f"**{p.one_line}**",
            f"- 核心特质：{' / '.join(p.core_traits)}",
            f"- 决策风格：{p.decision_style}",
            f"- 沟通风格：{p.communication_style}",
            f"- 成长盲区：{p.growth_edge}",
        ])
    if result.mental_models:
        lines.extend(["## 心智模型", ""])
        for i, m in enumerate(result.mental_models, 1):
            lines.extend([
                f"### {i}. {m.name}",
                f"{m.description}",
                f"**证据**：{' | '.join(m.evidence)}",
                f"**预测**：{m.prediction} | 置信度：{m.confidence}",
                "",
            ])
    if result.decision_heuristics:
        lines.extend(["## 决策启发式", ""])
        for h in result.decision_heuristics:
            lines.extend([
                f"**{h.number}. {h.title}** - {h.description}",
                f"适用：{h.scene} | 来源：{h.source}",
                "",
            ])
    if result.bias_flags:
        lines.extend(["## 偏差标注", ""])
        for b in result.bias_flags:
            lines.append(f"- **[{b.severity}] {b.type}**：{b.description}（缓解：{b.mitigation}）")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    p1 = {"dimension_scores": [{"label": "内省", "normalized": 8.5}], "pattern_analysis": {}}
    p2 = {
        "decision_pattern": {"primary_care": "关系", "decision_speed": "犹豫", "risk_attitude": "保守"},
        "value_signals": {"autonomy_signals": ["依赖他人意见"], "change_readiness": "保守"},
        "motivation_analysis": {"fear_based": True, "fear_signals": ["怕失败"], "value_based": False, "value_signals": []},
        "cross_scenario_consistency": 6.5, "warnings": []
    }
    p3 = {
        "expression_dna": {"composite_tags": ["短句有力型"], "one_line_portrait": "短句有力"},
        "warnings": []
    }
    score, warnings = check_cross_phase_consistency(p1, p2, p3)
    print(f"交叉一致性: {score}/10")
    for w in warnings:
        print(f"  - {w}")
    bias = detect_cognitive_bias(p1, p2, p3, score)
    for b in bias:
        print(f"  [{b.severity}] {b.type}: {b.description}")
