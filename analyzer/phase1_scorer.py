# -*- coding: utf-8 -*-
"""
王阳明工具 - Phase 1 分析器
功能：从用户问卷答案计算维度得分、生成雷达图数据、识别组合模式
设计原则：女娲式LLM驱动 + 规则计算辅助，不做过度工程
"""

import json
import re
from pathlib import Path
from typing import Any, TypedDict
from dataclasses import dataclass, asdict
from fractions import Fraction


# ============================================================
# 数据结构定义
# ============================================================

class DimensionScore(TypedDict):
    """单个维度得分"""
    dimension: str
    label: str
    raw_score: float       # 原始平均分（1-5）
    normalized: float      # 归一化到0-10
    answer_count: int
    answer_detail: list[tuple[str, float]]  # [(选项文本, 得分), ...]


class RadarChartData(TypedDict):
    """雷达图数据（用于可视化）"""
    dimensions: list[str]
    labels: list[str]
    values: list[float]
    labels_cn: list[str]


class Phase1Result(TypedDict):
    """Phase 1 分析结果"""
    total_questions: int
    answered_questions: int
    completion_rate: float
    dimension_scores: list[DimensionScore]
    radar_chart: RadarChartData
    pattern_analysis: dict[str, Any]  # LLM识别出的组合模式
    warnings: list[str]  # 异常信号（如大量中间值）


@dataclass
class UserAnswer:
    """用户单题作答记录"""
    question_id: str
    question_type: str    # single | sort | binary
    raw_answer: Any       # 原始答案
    normalized_score: float  # 归一化得分（0-10）


# ============================================================
# 核心计算逻辑
# ============================================================

def normalize_sort_score(rank: int, total: int) -> float:
    """
    将排序题排名转换为归一化得分（满分10分）
    排名第1得10分，排名第N得 10*(N-1)/N 分衰减
    公式：10 * (1 - (rank-1) / total) = 10 * (total - rank + 1) / total
    """
    if rank < 1 or rank > total:
        return 0.0
    return round(10.0 * (total - rank + 1) / total, 3)


def normalize_single_score(option_score: int | float, scale: int = 5) -> float:
    """将单选选项得分（通常是1-5）归一化到0-10"""
    return round((float(option_score) / scale) * 10, 3)


def calculate_dimension_scores(
    answers: dict[str, UserAnswer],
    scoring: dict[str, Any],
    question_metadata: dict[str, dict[str, Any]]
) -> list[DimensionScore]:
    """
    根据用户作答计算各维度得分

    参数:
        answers: {题目ID: UserAnswer}
        scoring: phase1.json中的scoring字段
        question_metadata: 从phase1.json提取的题目元数据 {题目ID: {dimension, trait, weight, ...}}

    返回:
        各维度的计算得分列表
    """
    # 按维度聚合
    dim_answers: dict[str, list[tuple[str, float]]] = {}
    for q_id, answer in answers.items():
        if q_id not in question_metadata:
            continue
        meta = question_metadata[q_id]
        dim = meta.get("dimension", "unknown")
        if dim not in dim_answers:
            dim_answers[dim] = []
        dim_answers[dim].append((answer.raw_answer, answer.normalized_score))

    results: list[DimensionScore] = []
    dim_labels = scoring.get("dimensionLabels", {})

    for dim, answer_list in sorted(dim_answers.items()):
        if not answer_list:
            continue
        # 计算平均分
        raw_avg = sum(score for _, score in answer_list) / len(answer_list)
        normalized = raw_avg  # 已经是0-10归一化的

        label = dim_labels.get(dim, dim)
        results.append(DimensionScore(
            dimension=dim,
            label=label,
            raw_score=round(raw_avg, 3),
            normalized=round(normalized, 3),
            answer_count=len(answer_list),
            answer_detail=answer_list
        ))

    return results


def detect_anomalies(answers: dict[str, UserAnswer]) -> list[str]:
    """
    检测作答异常信号
    - 大量连续中间值（3/10≈3/10的标准化分布）
    - 所有题目答案相同
    - 排序题中有明显不合逻辑的排序
    """
    warnings = []

    if not answers:
        return ["无作答数据"]

    # 检测"全部选C"模式
    middle_count = sum(
        1 for a in answers.values()
        if a.question_type == "single" and 2.5 <= a.normalized_score <= 3.5
    )
    if middle_count / len(answers) > 0.6:
        warnings.append(f"高比例中间值作答（{middle_count}/{len(answers)}），可能存在社会赞许倾向或选择疲劳")

    # 检测所有答案完全相同
    unique_scores = set(a.normalized_score for a in answers.values())
    if len(unique_scores) == 1:
        warnings.append("所有题目答案完全相同，区分度不足")

    return warnings


def build_radar_chart_data(dimension_scores: list[DimensionScore]) -> RadarChartData:
    """
    生成雷达图数据结构
    用于前端可视化或markdown图表
    """
    dimensions = [d["dimension"] for d in dimension_scores]
    labels = [d["dimension"] for d in dimension_scores]
    labels_cn = [d["label"] for d in dimension_scores]
    values = [d["normalized"] for d in dimension_scores]

    return RadarChartData(
        dimensions=dimensions,
        labels=labels,
        values=values,
        labels_cn=labels_cn
    )


def extract_high_low_dimensions(dimension_scores: list[DimensionScore], top_n: int = 3) -> tuple[list[DimensionScore], list[DimensionScore]]:
    """提取最高和最低的N个维度"""
    sorted_scores = sorted(dimension_scores, key=lambda x: x["normalized"], reverse=True)
    return sorted_scores[:top_n], sorted_scores[-top_n:]


def build_pattern_input(dimension_scores: list[DimensionScore]) -> str:
    """
    将维度得分格式化为字符串，用于LLM识别组合模式
    """
    lines = []
    for d in sorted(dimension_scores, key=lambda x: x["dimension"]):
        bar = "█" * int(d["normalized"]) + "░" * (10 - int(d["normalized"]))
        lines.append(f"  {d['label']:<20} {d['normalized']:5.1f}/10  {bar}")
    return "\n".join(lines)


# ============================================================
# LLM 驱动：组合模式识别（女娲式方法论）
# ============================================================

def identify_personality_patterns(dimension_scores: list[DimensionScore]) -> dict[str, Any]:
    """
    使用女娲式方法论，通过LLM识别人格组合模式
    """
    prompt = _build_pattern_prompt(dimension_scores)
    return {
        "_prompt_for_llm": prompt,
        "_requires_llm": True,
        "_dimensions": [dict(d) for d in dimension_scores]
    }


def _build_pattern_prompt(dimension_scores: list[DimensionScore]) -> str:
    """
    构建组合模式识别的LLM prompt
    参考女娲 extraction-framework.md 的三重验证法
    """
    scores_text = build_radar_chart_data(dimension_scores)
    high_dims, low_dims = extract_high_dimensions(dimension_scores)

    high_text = "\n".join(f"- {d['label']}: {d['normalized']}/10" for d in high_dims)
    low_text = "\n".join(f"- {d['label']}: {d['normalized']}/10" for d in low_dims)

    return f"""## 任务：识别人格组合模式

### 用户维度得分
{scores_text}

### 高分区（Top 3）
{high_text}

### 低分区（Bottom 3）
{low_text}

### 已知维度组合类型（参考，非强制匹配）

**A. 自省驱动型**
信号：内省↑ + 反思↑ + 神经质↑ + 风险偏好↓
特征：深思熟虑型，对不确定性敏感，容易陷入过度思考

**B. 行动优先型**
信号：尽责性↑ + 关系处理↑ + 决策速度↑
特征：快速响应，先行动后调整，执行力强但可能忽视细节

**C. 关系中心型**
信号：社会需求↑ + 归属感↑ + 冲突回避↑
特征：以关系和谐为优先，容易为他人调整自己

**D. 外部归因型**
信号：内省↓ + 反思↓ + 归因外部↑
特征：倾向于外部归因，对自我认知可能有盲区

**E. 高自主动机型**
信号：自主↑ + 能力感↑ + 风险偏好↓
特征：内在驱动，追求自我实现但相对保守

**F. 挑战驱动型**
信号：能力感（挑战）↑ + 神经质↑ + 自主↓
特征：享受挑战带来的能力感，但情绪波动较大

### 你的任务

1. **模式识别**：上述组合与哪个已知类型最接近？或者是否存在新的组合？
2. **三重验证**：
   - 跨域复现：高分/低分特质是否在不同维度上形成一致叙事？
   - 生成力：从这些得分，能否预测该用户在典型情境中的反应？
   - 排他性：这个组合能排除哪些类型？
3. **核心画像**：用1-2句话描述此人的核心特征
4. **潜在偏差标注**：是否有Phase 1得分与Phase 2回答不一致的预警信号？
5. **追问建议**：是否有维度得分存在矛盾需要通过Phase 2追问验证的？

### 输出格式

```json
{{
  "primary_pattern": "类型名/未识别",
  "pattern_description": "对该模式的描述",
  "confidence": "high/medium/low",
  "cross_domain_consistency": "一致性评估",
  "prediction_ability": "能否预测未见情境",
  "exclusion_claims": ["排除的类型及理由"],
  "core_portrait": "1-2句话核心画像",
  "bias_flags": ["潜在偏差信号"],
  "followup_questions": ["建议追问的问题"]
}}
```"""


def extract_high_dimensions(dimension_scores: list[DimensionScore], top_n: int = 3) -> tuple[list[DimensionScore], list[DimensionScore]]:
    """提取最高和最低的N个维度"""
    sorted_scores = sorted(dimension_scores, key=lambda x: x["normalized"], reverse=True)
    return sorted_scores[:top_n], sorted_scores[-top_n:]


# ============================================================
# 主入口
# ============================================================

def analyze_phase1(
    answers: dict[str, UserAnswer],
    questionnaire_path: str | None = None
) -> Phase1Result:
    """
    Phase 1 分析主入口

    参数:
        answers: 用户作答数据 {题目ID: UserAnswer}
        questionnaire_path: 可选，phase1.json 路径，不提供则用默认路径

    返回:
        Phase1Result 完整分析结果
    """
    # 加载问卷元数据
    if questionnaire_path is None:
        base = Path(__file__).parent.parent
        questionnaire_path = base / "questionnaire" / "phase1.json"
    else:
        questionnaire_path = Path(questionnaire_path)

    if questionnaire_path.exists():
        with open(questionnaire_path, encoding="utf-8") as f:
            q_data = json.load(f)
        scoring = q_data.get("scoring", {})
        questions_meta = {
            q["id"]: q for q in q_data.get("questions", [])
        }
    else:
        # 无问卷文件时使用默认空的scoring
        scoring = {"dimensionLabels": {}}
        questions_meta = {}

    # 计算维度得分
    dim_scores = calculate_dimension_scores(answers, scoring, questions_meta)

    # 生成雷达图数据
    radar = build_radar_chart_data(dim_scores)

    # 检测异常
    warnings = detect_anomalies(answers)

    # LLM驱动：组合模式识别（返回prompt结构，实际LLM调用在skill_generator中）
    pattern_analysis = identify_personality_patterns(dim_scores)

    total_q = len(questions_meta)
    answered_q = len(answers)
    completion = answered_q / total_q if total_q > 0 else 0.0

    return Phase1Result(
        total_questions=total_q,
        answered_questions=answered_q,
        completion_rate=round(completion, 3),
        dimension_scores=dim_scores,
        radar_chart=radar,
        pattern_analysis=pattern_analysis,
        warnings=warnings
    )


# ============================================================
# 工具函数：外部调用
# ============================================================

def load_answers_from_json(answers_json_path: str) -> dict[str, UserAnswer]:
    """
    从JSON文件加载用户作答记录
    用于测试或历史数据回放
    """
    with open(answers_json_path, encoding="utf-8") as f:
        raw = json.load(f)

    result = {}
    for q_id, item in raw.items():
        answer_type = item.get("type", "single")
        raw_ans = item.get("answer")
        norm_score = item.get("normalized_score", 5.0)

        result[q_id] = UserAnswer(
            question_id=q_id,
            question_type=answer_type,
            raw_answer=raw_ans,
            normalized_score=norm_score
        )
    return result


def scores_to_dict(result: Phase1Result) -> dict:
    """将Phase1Result转为普通dict（用于JSON序列化）"""
    import copy
    d = copy.deepcopy(dict(result))
    # 递归处理嵌套dict
    def _serialize(obj):
        if isinstance(obj, dict):
            return {k: _serialize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_serialize(i) for i in obj]
        elif hasattr(obj, "__dataclass_fields__"):
            return {f: _serialize(getattr(obj, f)) for f in obj.__dataclass_fields__}
        else:
            return obj
    return _serialize(d)


if __name__ == "__main__":
    # 简单测试
    import pprint
    test_answers = {
        "A1": UserAnswer("A1", "single", "独自旅行，看不一样的风景", 7.5),
        "A2": UserAnswer("A2", "single", "深入聊1-2个问题", 8.0),
        "A3": UserAnswer("A3", "single", "写下来，整理成文章或日记", 8.5),
        "A4": UserAnswer("A4", "single", "先按计划走，边走边调整", 6.0),
        "A5": UserAnswer("A5", "single", "自己决定，不怎么问别人", 7.0),
        "B1": UserAnswer("B1", "single", "做这件事本身有意义", 8.0),
        "B2": UserAnswer("B2", "single", "担心结果会不如预期", 6.5),
        "B3": UserAnswer("B3", "single", "我应该可以", 6.0),
        "B4": UserAnswer("B4", "single", "有人陪会比较安心", 5.0),
        "B5": UserAnswer("B5", "single", "会，说到做到", 8.0),
        "C1": UserAnswer("C1", "single", "我会把利弊全列出来，权衡", 9.0),
        "C2": UserAnswer("C2", "single", "直觉判断，相信自己经验", 7.5),
        "C3": UserAnswer("C3", "single", "我会去问那个更专业的人", 6.5),
        "C4": UserAnswer("C4", "single", "看情况，复杂就快刀斩乱麻", 7.0),
        "C5": UserAnswer("C5", "single", "先问一圈人的意见再决定", 4.5),
        "D1": UserAnswer("D1", "single", "先道歉，缓和气氛", 8.0),
        "D2": UserAnswer("D2", "single", "我会被对方的话戳到，但不会当场发火", 7.0),
        "D3": UserAnswer("D3", "single", "我会直接说明我看到了什么", 7.5),
        "D4": UserAnswer("D4", "single", "当面聊清楚，不喜欢冷战", 8.5),
        "D5": UserAnswer("D5", "single", "说出来，否则心里过不去", 9.0),
        "E1": UserAnswer("E1", "single", "差不多，我运气还行", 5.0),
        "E2": UserAnswer("E2", "single", "环境、机遇的影响更大", 6.0),
        "E3": UserAnswer("E3", "single", "我通常是对的", 4.5),
        "E4": UserAnswer("E4", "single", "我对自己还是有比较清醒认识的", 7.5),
        "E5": UserAnswer("E5", "single", "我觉得自己还行", 6.5),
        "F1": UserAnswer("F1", "sort", ["成就感", "安全感", "自由", "归属感"], 7.5),
    }
    result = analyze_phase1(test_answers)
    print(f"完成率: {result['answered_questions']}/{result['total_questions']} ({result['completion_rate']:.1%})")
    print("\n维度得分:")
    for d in result["dimension_scores"]:
        bar = "█" * int(d["normalized"]) + "░" * (10 - int(d["normalized"]))
        print(f"  {d['label']:<16} {d['normalized']:4.1f}/10  {bar}")
    print(f"\n预警信号: {result['warnings'] or '无'}")
    print("\n雷达图维度顺序:", result["radar_chart"]["dimensions"])
