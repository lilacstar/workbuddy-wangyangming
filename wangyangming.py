# -*- coding: utf-8 -*-
"""
王阳明·普通人思维蒸馏工具
============================

主入口模块。WorkBuddy AI 在识别触发词后加载本文件，
通过本模块提供的方法与用户完成蒸馏对话并生成 Skill。

触发词：蒸馏我、蒸馏自己、认识自己、王阳明、向内看、思维镜像

使用方式（WorkBuddy AI 调用）：
    from wangyangming import start_distillation

    flow, session = start_distillation()
    # AI 向用户展示 flow.start() 的内容
    # 用户回答后调用 flow.submit_answer()
    # 流程结束后调用 generate_skill() 生成 Skill
"""

import json
import sys
from pathlib import Path

# 确保 analyzer 和 generator 在路径中
_root = Path(__file__).parent
for _p in [_root / "analyzer", _root / "generator"]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from conversation_flow import ConversationFlow, _default_flow
from generator.skill_generator import DistillationSession
from analyzer.calibration import format_calibration_report


# ============================================================
# WorkBuddy Skill 触发入口
# ============================================================

class WangYangmingSession:
    """
    王阳明蒸馏会话封装。

    WorkBuddy AI 通过这个类管理完整的蒸馏流程：
    1. start() → 启动会话
    2. 循环 get_next_prompt() / submit_answer() → 收集数据
    3. generate_skill() → 生成 Skill
    """

    def __init__(self, session_id: str | None = None):
        self.flow = ConversationFlow(session_id=session_id)
        self._distill_session: DistillationSession | None = None
        self._analysis_done = False

    # ---------- 对话 API ----------

    def start(self) -> str:
        """返回欢迎语和启动说明"""
        return self.flow.start()

    def get_next_prompt(self) -> str | None:
        """获取下一步要展示给用户的提示"""
        return self.flow.get_next_prompt()

    def submit_answer(self, raw_answer: str) -> str:
        """提交用户回答，返回反馈"""
        return self.flow.submit_answer(raw_answer)

    def current_phase(self) -> int | str:
        """返回当前阶段标识"""
        return self.flow.state.current_phase

    def progress(self) -> dict:
        """返回各阶段进度"""
        s = self.flow.state
        p1_total = len(self.flow.loader.get_phase1_all())
        p2_total = len(self.flow.loader.get_phase2_all())
        p3_total = len(self.flow.loader.get_phase3_all())
        return {
            "phase": s.current_phase,
            "phase1": f"{len(s.phase1_answers)}/{p1_total}",
            "phase2": f"{len(s.phase2_answers)}/{p2_total}",
            "phase3": f"{len(s.phase3_answers)}/{p3_total}",
        }

    # ---------- 分析与生成 API ----------

    def run_analysis(self, llm_provider: callable) -> dict:
        """
        触发分析流程（Phase 1→2→3 分析 + 整合）。
        在所有问卷数据收集完成后调用。
        """
        if self._distill_session is None:
            self._distill_session = self.flow.to_distillation_session()

        p1 = self._distill_session.analyze_phase1(llm_provider)
        p2 = self._distill_session.analyze_phase2(llm_provider)
        p3 = self._distill_session.analyze_phase3(llm_provider)
        integrated = self._distill_session.integrate_all_phases(llm_provider)

        self._analysis_done = True
        return {
            "phase1": p1,
            "phase2": p2,
            "phase3": p3,
            "integrated": self._distill_session._dict_from_dataclass(integrated),
        }

    # ---------- 校准 API ----------

    def get_calibration_prompt(self) -> str:
        """
        获取校准对话文本（用于向用户提问）。
        需要先调用 run_analysis()。
        """
        if not self._analysis_done:
            return "请先调用 run_analysis()"
        return self._distill_session.get_calibration_prompt()

    def submit_calibration_and_forward_to_evolution(
        self,
        user_responses: str,
        skill_name: str = "anonymous"
    ) -> dict:
        """
        运行校准并将结果推送到 evolution 模块。

        链路：run_calibration() → 准确度计算 → 映射到 evolution 评分
              → FeedbackCollector.add_feedback() → evolution/feedback/ratings.json

        触发条件（由 evolution/config.json 控制）：
        - forward_on_low_accuracy = True
        - accuracy < threshold (默认 0.5)

        参数:
            user_responses: 用户对校准问题的回答，如 "1A 2B 3A" 或 "A B A"
            skill_name: Skill 名称（用于 evolution 记录）

        返回 dict: {calibration_result, evolution_pushed, questions}
        """
        if not self._analysis_done:
            return {"error": "请先调用 run_analysis()"}

        questions, result = self._distill_session.run_calibration_with_evolution(
            user_responses=user_responses,
            skill_name=skill_name
        )

        if result is None:
            return {"error": "无法生成校准结果"}

        return {
            "accuracy": result.accuracy,
            "expected_chosen": result.expected_chosen,
            "alternative_chosen": result.alternative_chosen,
            "neither_chosen": result.neither_chosen,
            "assessment": result.assessment,
            "followup_recommendation": result.followup_recommendation,
            "followup_questions": result.followup_questions,
            "evolution_pushed": True,  # 由内部逻辑判断是否推送
            "report": format_calibration_report(result),
        }

    def generate_skill(
        self,
        skill_name: str,
        llm_provider: callable,
        output_dir: str | None = None,
    ) -> str:
        """
        生成最终 Skill 文件。
        必须先调用 run_analysis()。
        """
        if not self._analysis_done:
            # 自动触发分析
            self.run_analysis(llm_provider)

        path = self._distill_session.generate_skill(
            skill_name=skill_name,
            llm_provider=llm_provider,
            output_dir=output_dir,
        )
        return path

    # ---------- 持久化 ----------

    def save(self, path: str | None = None) -> str:
        """保存会话到文件"""
        return self.flow.save(path)

    @classmethod
    def load(cls, path: str) -> "WangYangmingSession":
        """从文件恢复会话"""
        flow = ConversationFlow.load(path)
        session = cls(session_id=flow.state.session_id)
        session.flow = flow
        return session

    def to_distillation_session(self) -> DistillationSession:
        """导出为 DistillationSession（用于高级用法）"""
        if self._distill_session is None:
            self._distill_session = self.flow.to_distillation_session()
        return self._distill_session


# ============================================================
# 快捷函数（供 WorkBuddy AI 直接调用）
# ============================================================

_active_session: WangYangmingSession | None = None


def start_distillation(session_id: str | None = None) -> tuple[WangYangmingSession, ConversationFlow]:
    """
    启动新的蒸馏会话。

    返回：(WangYangmingSession, ConversationFlow)
    - WangYangmingSession：主控制接口
    - ConversationFlow：对话流程（用于直接操作）
    """
    global _active_session
    _active_session = WangYangmingSession(session_id=session_id)
    return _active_session, _active_session.flow


def get_active() -> WangYangmingSession | None:
    """获取当前活跃会话"""
    return _active_session


def quick_run(
    skill_name: str,
    llm_provider: callable,
    output_dir: str | None = None,
    session_id: str | None = None,
) -> dict:
    """
    快速蒸馏（跳过对话，用模拟数据）。
    仅用于开发测试。真实场景请使用 start_distillation()。

    返回 dict：
        {
            "skill_path": str,    # Skill 文件路径
            "summary": str,       # 分析摘要
            "session_id": str,    # 会话 ID
        }
    """
    from conversation_flow import run_full_conversation

    summary, skill_path = run_full_conversation(
        llm_provider=llm_provider,
        output_dir=output_dir,
        session_id=session_id,
    )

    return {
        "skill_path": skill_path,
        "summary": summary,
        "session_id": session_id or "demo",
    }
