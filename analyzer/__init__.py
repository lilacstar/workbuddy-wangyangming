"""
王阳明工具 - 分析器模块
========================

analyzer 模块是王阳明蒸馏工具的核心分析引擎，负责从三阶段问卷数据中
提炼用户的思维框架与表达风格。

## 模块结构

    analyzer/
    ├── __init__.py          # 本文件：公共接口导出
    ├── phase1_scorer.py     # 维度得分 + 雷达图 + 组合模式识别
    ├── phase2_analyzer.py   # 决策模式 + 价值观信号 + 动机分析
    ├── phase3_analyzer.py   # 句式统计 + 词汇风格 + 表达DNA
    ├── integrator.py        # 三阶段整合 + 交叉验证 + 偏差检测
    └── calibration.py       # 校准问题 + 准确度评分 + 追问建议

## 快速使用

    from generator.skill_generator import DistillationSession, run_full_pipeline

    session = DistillationSession(session_id="my-session")
    session.add_phase1_answer("A1", "single", "独自旅行", 8.5)
    session.add_phase2_response(...)
    session.add_phase3_text("我觉得这事要从两个角度看...")
    result = run_full_pipeline(session)
    skill_md = session.generate_skill("我的视角", llm_provider=your_llm)

## DistillationSession 主要方法

    add_phase1_answer(qid, qtype, answer, score)
    add_phase2_response(scenario_id, response_text, followup_answers)
    add_phase3_text(text)

    analyze_phase1(llm_provider)    → dict  维度得分+雷达图+组合模式
    analyze_phase2(llm_provider)    → dict  决策模式+价值观+动机
    analyze_phase3(llm_provider)   → dict  句式+词汇+表达DNA
    integrate_all_phases(llm_provider) → dict  三阶段整合结果
    generate_skill(skill_name, llm_provider, output_dir) → str (文件路径)

    get_calibration_prompt()              → list[dict]
    run_calibration(user_responses)       → CalibrationResult
    get_calibration_summary()              → str
    save_session(path) / load_session(path)
"""

# 注意：DistillationSession 位于 generator/ 目录，
# 请通过 generator.skill_generator 显式导入，避免与 analyzer 子模块的加载顺序冲突
from calibration import (
    run_calibration,
    format_calibration_for_conversation,
    format_calibration_report,
)
from integrator import (
    integrate_three_phases,
    check_cross_phase_consistency,
    detect_cognitive_bias,
    generate_summary_markdown,
    result_to_dict,
)

__all__ = [
    # 校准
    "run_calibration",
    "format_calibration_for_conversation",
    "format_calibration_report",
    # 整合
    "integrate_three_phases",
    "check_cross_phase_consistency",
    "detect_cognitive_bias",
    "generate_summary_markdown",
    "result_to_dict",
]
