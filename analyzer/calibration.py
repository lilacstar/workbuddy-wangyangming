# -*- coding: utf-8 -*-
"""
王阳明工具 - 校准模块
功能：生成校准测试问题 → 收集评分 → 计算准确度 → 决定是否追加问卷
设计原则：借鉴女娲Phase 4"已知案例测试"，用反向问题验证生成质量
"""

import json
import re
import random
from typing import Any, TypedDict
from dataclasses import dataclass, asdict


# ============================================================
# 数据结构
# ============================================================

@dataclass
class CalibrationQuestion:
    """校准测试问题"""
    question_id: str
    question: str
    expected_answer: str      # 从心智模型/启发式推导出的预期回答
    alternative_answer: str    # 替代性回答（如果用户不是那样的人会怎么答）
    validation_dimension: str  # 验证哪个维度


@dataclass
class CalibrationResponse:
    """用户对校准问题的回答"""
    question_id: str
    user_answer: str
    choice: str               # "expected" | "alternative" | "neither"
    confidence: int           # 1-5，用户对自己回答的自信程度


@dataclass
class CalibrationResult:
    """校准结果"""
    total_questions: int
    answered_questions: int
    expected_chosen: int
    alternative_chosen: int
    neither_chosen: int
    accuracy: float            # 与预期一致的比例
    confidence_avg: float     # 平均自信程度
    assessment: str           # 评估结论
    followup_recommendation: str  # 建议
    followup_questions: list[str]  # 建议追加的问题


# ============================================================
# 校准问题生成
# ============================================================

def generate_calibration_questions(
    mental_models: list[dict],
    decision_heuristics: list[dict],
    bias_flags: list[dict],
    count: int = 5
) -> list[CalibrationQuestion]:
    """
    基于心智模型和决策启发式，生成校准测试问题

    方法：
    1. 从每个心智模型的"预测"推导出一个反向测试场景
    2. 设计一个"陷阱题"：描述一个符合/不符合该心智模型的情境
    3. 用户二选一，验证模型是否准确

    参数:
        mental_models: 心智模型列表
        decision_heuristics: 决策启发式列表
        bias_flags: 偏差标注列表
        count: 生成数量
    """
    questions = []

    # 从心智模型生成测试问题
    for i, model in enumerate(mental_models[:min(3, len(mental_models))]):
        model_name = model.get("name", f"心智模型{i+1}")
        prediction = model.get("prediction", "")
        confidence = model.get("confidence", "medium")

        q = _build_model_test_question(
            question_id=f"Q{i+1}",
            model_name=model_name,
            prediction=prediction,
            confidence=confidence
        )
        if q:
            questions.append(q)

    # 从决策启发式生成测试问题
    for i, heuristic in enumerate(decision_heuristics[:min(3, len(decision_heuristics))]):
        title = heuristic.get("title", f"启发式{i+1}")
        scene = heuristic.get("scene", "")
        description = heuristic.get("description", "")

        q = _build_heuristic_test_question(
            question_id=f"Q{len(questions)+1}",
            title=title,
            scene=scene,
            description=description
        )
        if q:
            questions.append(q)

    # 从偏差标注生成验证问题
    for i, bias in enumerate(bias_flags[:2]):
        bias_type = bias.get("type", "")
        description = bias.get("description", "")

        q = _build_bias_test_question(
            question_id=f"Q{len(questions)+1}",
            bias_type=bias_type,
            description=description
        )
        if q:
            questions.append(q)

    # 随机打乱，选择足够数量
    random.shuffle(questions)
    return questions[:count]


def _build_model_test_question(
    question_id: str,
    model_name: str,
    prediction: str,
    confidence: str
) -> CalibrationQuestion | None:
    """从心智模型构建测试问题"""
    if not prediction:
        return None

    # 构建一个测试场景（从预测推导）
    # 简化版：直接用预测描述作为问题
    question = f"假设遇到这样的情境：{prediction}，你会怎么做？"
    expected = f"按照{model_name}的方式行动（{prediction}）"
    alternative = "采取不同于上述预测的方式行动"

    return CalibrationQuestion(
        question_id=question_id,
        question=question,
        expected_answer=expected,
        alternative_answer=alternative,
        validation_dimension=model_name
    )


def _build_heuristic_test_question(
    question_id: str,
    title: str,
    scene: str,
    description: str
) -> CalibrationQuestion | None:
    """从决策启发式构建测试问题"""
    if not scene:
        return None

    question = f"在以下场景中：{scene}，你通常会怎么做？"
    expected = f"按照\"{title}\"的启发式（{description}）"
    alternative = "采取与上述启发式不同的方式"

    return CalibrationQuestion(
        question_id=question_id,
        question=question,
        expected_answer=expected,
        alternative_answer=alternative,
        validation_dimension=title
    )


def _build_bias_test_question(
    question_id: str,
    bias_type: str,
    description: str
) -> CalibrationQuestion | None:
    """从偏差标注构建验证问题（反向测试）"""
    # 使用反向问题来验证偏差是否真实存在
    if "社会赞许" in bias_type:
        question = "你有没有曾经为了维护关系而说了一些违心的话？"
        expected = "有，说过违心的话"
        alternative = "没有，一直说真话"
        return CalibrationQuestion(
            question_id=question_id, question=question,
            expected_answer=expected, alternative_answer=alternative,
            validation_dimension=bias_type
        )
    elif "情境依赖" in bias_type:
        question = "你在不同场合（工作/家庭/朋友）会有完全不同的表现吗？"
        expected = "是的，差异很大"
        alternative = "差不多，我表现一致"
        return CalibrationQuestion(
            question_id=question_id, question=question,
            expected_answer=expected, alternative_answer=alternative,
            validation_dimension=bias_type
        )
    return None


# ============================================================
# 校准问题格式化（供对话使用）
# ============================================================

def format_calibration_for_conversation(questions: list[CalibrationQuestion]) -> str:
    """
    将校准问题格式化为对话文本
    用于在蒸馏完成后，向用户发送校准问题
    """
    lines = [
        "## 🎯 校准测试",
        "",
        "为了验证我们对你思维模式的理解是否准确，请回答以下几个小问题。"
        "每个问题有两个选项，没有对错之分。",
        "",
    ]

    for i, q in enumerate(questions, 1):
        lines.append(f"**{i}. {q.question}**")
        lines.append(f"   A. {q.expected_answer}")
        lines.append(f"   B. {q.alternative_answer}")
        lines.append("")

    lines.extend([
        "请回复选项字母（A或B），我会根据你的回答调整最终的思维画像。",
        "如果都不符合你的实际情况，可以回复\"都不是\"。"
    ])

    return "\n".join(lines)


def parse_calibration_response(
    user_input: str,
    questions: list[CalibrationQuestion]
) -> dict[str, CalibrationResponse]:
    """
    解析用户对校准问题的回答
    user_input: 格式如 "1A 2B 3A 4B 5C" 或 "A B A B 都不是"
    """
    responses = {}
    # 清理输入
    raw = re.sub(r"\s+", " ", user_input.strip())

    # 尝试多种格式解析
    # 格式1: "1A 2B 3C" (题号+选项)
    matches = re.findall(r"(\d+)([AaBb])", raw)
    if matches:
        for q_num, choice in matches:
            q_id = f"Q{q_num}"
            if q_id in [q.question_id for q in questions]:
                q = next(x for x in questions if x.question_id == q_id)
                responses[q_id] = CalibrationResponse(
                    question_id=q_id,
                    user_answer=choice.upper(),
                    choice="expected" if choice.upper() == "A" else "alternative",
                    confidence=3
                )
        return responses

    # 格式2: "A B A B" (纯选项，假设按顺序对应)
    choices = re.findall(r"[AaBb]", raw)
    for i, choice in enumerate(choices[:len(questions)]):
        q = questions[i]
        responses[q.question_id] = CalibrationResponse(
            question_id=q.question_id,
            user_answer=choice.upper(),
            choice="expected" if choice.upper() == "A" else "alternative",
            confidence=3
        )

    # 检查"都不是"
    if "都不是" in raw or "C" in raw.upper():
        # 将C解释为"neither"
        for i, choice in enumerate(choices):
            if choice.upper() == "C":
                q = questions[i]
                responses[q.question_id] = CalibrationResponse(
                    question_id=q.question_id,
                    user_answer="neither",
                    choice="neither",
                    confidence=2
                )

    return responses


# ============================================================
# 校准结果计算
# ============================================================

def calculate_calibration_result(
    questions: list[CalibrationQuestion],
    responses: dict[str, CalibrationResponse],
    mental_models: list[dict],
    bias_flags: list[dict]
) -> CalibrationResult:
    """
    计算校准结果，决定是否需要追加问卷

    决策逻辑：
    - 准确度 >= 70%：生成质量良好，无需追加
    - 准确度 50%-70%：基本准确，建议部分追问
    - 准确度 < 50%：质量不足，建议追加问卷
    """
    if not responses:
        return CalibrationResult(
            total_questions=len(questions),
            answered_questions=0,
            expected_chosen=0,
            alternative_chosen=0,
            neither_chosen=0,
            accuracy=0.0,
            confidence_avg=0.0,
            assessment="无法评估（无回答）",
            followup_recommendation="请回答校准问题",
            followup_questions=[]
        )

    total = len(responses)
    expected_count = sum(1 for r in responses.values() if r.choice == "expected")
    alternative_count = sum(1 for r in responses.values() if r.choice == "alternative")
    neither_count = sum(1 for r in responses.values() if r.choice == "neither")
    confidence_sum = sum(r.confidence for r in responses.values())
    accuracy = expected_count / total if total > 0 else 0.0
    confidence_avg = confidence_sum / total if total > 0 else 0.0

    # 决策
    followup_questions = []

    if accuracy >= 0.7:
        assessment = f"理解准确（{accuracy:.0%}一致），生成质量良好"
        followup_recommendation = "无需追加问卷，可以直接使用生成的Skill"
    elif accuracy >= 0.5:
        assessment = f"基本准确（{accuracy:.0%}一致），存在偏差但可控"
        followup_recommendation = "建议追加1-2个追问以提高准确度"
        followup_questions = _generate_followup_for_mismatch(
            questions, responses, mental_models, bias_flags
        )
    else:
        assessment = f"理解偏差较大（{accuracy:.0%}一致），建议重新校准"
        followup_recommendation = "建议追加完整的Phase 2追问或重新进行部分问卷"
        followup_questions = _generate_followup_for_mismatch(
            questions, responses, mental_models, bias_flags
        )

    return CalibrationResult(
        total_questions=len(questions),
        answered_questions=total,
        expected_chosen=expected_count,
        alternative_chosen=alternative_count,
        neither_chosen=neither_count,
        accuracy=accuracy,
        confidence_avg=round(confidence_avg, 1),
        assessment=assessment,
        followup_recommendation=followup_recommendation,
        followup_questions=followup_questions
    )


def _generate_followup_for_mismatch(
    questions: list[CalibrationQuestion],
    responses: dict[str, CalibrationResponse],
    mental_models: list[dict],
    bias_flags: list[dict]
) -> list[str]:
    """为不匹配的维度生成追问"""
    followups = []

    # 找出哪些维度和预期不一致
    mismatched = [
        q for q in questions
        if q.question_id in responses
        and responses[q.question_id].choice != "expected"
    ]

    for q in mismatched:
        dim = q.validation_dimension
        # 找到对应的模型/启发式
        matching_model = next((m for m in mental_models if m.get("name") == dim), None)
        if matching_model:
            evidence = matching_model.get("evidence", [])
            followups.append(
                f"关于「{dim}」：你之前提到过{evidence[0] if evidence else '这一点'}。"
                f"能再详细说说你在这种情况下通常会怎么想、怎么做吗？"
            )

    # 如果没有具体模型，提供通用追问
    if not followups:
        followups.append("你对上面一些问题的回答和我们的理解不太一致。能具体说说你在这些情境中通常是怎么想的吗？")

    return followups


# ============================================================
# 校准报告格式化
# ============================================================

def format_calibration_report(result: CalibrationResult) -> str:
    """格式化校准报告"""
    lines = [
        "## 校准结果",
        "",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 答题数 | {result.answered_questions}/{result.total_questions} |",
        f"| 与预期一致 | {result.expected_chosen}题 |",
        f"| 与预期不符 | {result.alternative_chosen}题 |",
        f"| 都不符合 | {result.neither_chosen}题 |",
        f"| 准确度 | {result.accuracy:.0%} |",
        f"| 平均自信度 | {result.confidence_avg}/5 |",
        "",
        f"**评估：{result.assessment}**",
        "",
        f"**建议：{result.followup_recommendation}**",
    ]

    if result.followup_questions:
        lines.extend(["", "### 建议追问", ""])
        for i, q in enumerate(result.followup_questions, 1):
            lines.append(f"{i}. {q}")

    return "\n".join(lines)


# ============================================================
# 主入口
# ============================================================

def run_calibration(
    mental_models: list[dict],
    decision_heuristics: list[dict],
    bias_flags: list[dict],
    user_responses: str | None = None,
    question_count: int = 5
) -> tuple[list[CalibrationQuestion], CalibrationResult | None]:
    """
    校准主入口

    参数:
        mental_models: 心智模型列表
        decision_heuristics: 决策启发式列表
        bias_flags: 偏差标注列表
        user_responses: 用户回答（可选，不提供则返回问题供对话使用）
        question_count: 生成校准问题数量
    """
    questions = generate_calibration_questions(
        mental_models, decision_heuristics, bias_flags, question_count
    )

    if user_responses is None:
        return questions, None

    responses = parse_calibration_response(user_responses, questions)
    result = calculate_calibration_result(questions, responses, mental_models, bias_flags)
    return questions, result


# ============================================================
# 工具：生成追问（用于追加问卷）
# ============================================================

def generate_targeted_followup(
    dimension: str,
    question: str,
    context: str
) -> str:
    """
    为特定维度生成精准追问
    用于追加问卷中
    """
    templates = {
        "内省": f"你提到过{context}。能具体说说，当时你心里是怎么想的吗？有没有一些没有说出口的考量？",
        "风险": f"关于{context}，如果你面临更大的风险（比如损失翻倍），你会做出不同的选择吗？",
        "动机": f"你选择了{context}。我想追问：如果当时没有外部压力，你会做同样的选择吗？",
        "关系": f"你在{context}的情况下，通常会怎么处理？你最在意的是什么？",
    }

    # 通用模板
    default = f"关于{context}，还有没有什么是你想补充的，或者之前没有机会说到的？"

    for key, template in templates.items():
        if key in dimension:
            return template

    return default


if __name__ == "__main__":
    # 测试
    test_models = [
        {
            "name": "损失规避型",
            "description": "面对同等收益和损失时，对损失更敏感",
            "evidence": ["Phase1风险偏好低", "Phase2情境中选择保守方案"],
            "prediction": "面对投资亏损时，倾向于提前止损而非等待反弹",
            "confidence": "high"
        }
    ]
    test_heuristics = [
        {
            "number": 1,
            "title": "先想最坏情况",
            "description": "做决定前先想清楚最坏结果能否接受",
            "scene": "面对一个新机会时",
            "source": "Phase2情境1"
        }
    ]

    questions, _ = run_calibration(test_models, test_heuristics, [], question_count=3)
    print("生成校准问题:")
    print(format_calibration_for_conversation(questions))

    # 测试解析
    test_response = "1A 2B 3A"
    parsed = parse_calibration_response(test_response, questions)
    print("\n解析回答:", {k: v.choice for k, v in parsed.items()})

    result = calculate_calibration_result(questions, parsed, test_models, [])
    print("\n校准结果:")
    print(format_calibration_report(result))
