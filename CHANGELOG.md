# 王阳明·普通人思维蒸馏工具 更新日志

> 所有版本变更遵循语义化版本（SemVer）。

---

## [v1.3.1] - 2026-04-29

### 新增

- **`conversation_flow.py`**：对话流程控制器
  - 负责任务加载、题目展示、答案收集、条件追问、状态管理
  - 支持 Phase1（选择题）→ Phase2（情境题+追问）→ Phase3（写作任务）完整链路
  - `_demo_fill()` 支持 mock 数据快速测试

- **`wangyangming.py`**：WorkBuddy Skill 主入口
  - `WangYangmingSession` 封装类，对外暴露简化的蒸馏 API
  - `start_distillation()` 快捷函数
  - 支持 `run_analysis()` 和 `generate_skill()` 端到端调用
  - Session 持久化（`save_session()` / `load_session()`）
  - `get_calibration_prompt()` + `submit_calibration_and_forward_to_evolution()` API

- **`verify_p2.py`**：P2 代码验证脚本（62项检查全通过）

### 修复

- **`questionnaire/phase3.json`**：修复中文引号打断 JSON 字符串的问题（共5处）
- **`questionnaire/phase1.json`**：`questionCount: 39 → 38`
- **`questionnaire/phase2.json`**：`coreScenarios: 6 → 7`

### 文档

- 补充 `plan.md`：`conversation_flow.py` 和 `wangyangming.py` 架构设计文档

---

## [v1.3.0] - 2026-04-26

### 新增

- **`analyzer/` 模块**：规则计算 + LLM 混合评分系统
  - `phase1_scorer.py`：Phase 1 计分与雷达图数据构建
  - `phase2_analyzer.py`：情境题分析与动机探测
  - `phase3_analyzer.py`：语料采样分析
  - `integrator.py`：三阶段整合与心智模型构建
  - `calibration.py`：校准测试问题生成与准确度计算
  - `SKILL.md` Step 5/6 绑定实际 analyzer 模块调用

- **`generator/` 模块**：Skill 生成引擎
  - `skill_generator.py`：`DistillationSession` 管理三阶段数据 → 分析 → 整合 → Skill 生成的完整流程
  - `run_calibration_with_evolution()`：calibration → evolution 反馈链路打通

- **`evolution/config.json`**：进化模块配置，支持自动触发和阈值转发

---

## [v1.2.0] - 2026-04-24

### 新增

- **`evolution/` 模块**：用户反馈驱动的问卷迭代系统
  - 借鉴阳明心学"反求诸己"理念，通过用户评分持续优化问卷题目
  - `collectors/feedback_collector.py`：`FeedbackCollector` 类，支持快速打分和维度细分
  - `analyzers/stats_analyzer.py`：题目区分度统计分析
  - `reports/report_generator.py`：改进报告生成
  - `scripts/collect.py` / `analyze.py` / `report.py` / `status.py`：CLI 入口脚本
  - `EVOLUTION_GUIDE.md`：完整使用指南

### 与达尔文的区别

| 维度 | 达尔文（女娲） | 进化模块（王阳明） |
|------|---------------|-------------------|
| 优化对象 | 生成内容的风格一致性 | 问卷题目的区分度 |
| 评估标准 | 有 ground truth 可对比 | 用户主观反馈 |
| 自动化程度 | 批量实验 + AI 评分 | 用户反馈 + 人工决策 |

---

## [v1.1.0] - 2026-04-24

### 新增

- **素材导入模块**：支持 PDF、Word、Markdown、纯文本、链接抓取
- 双模式蒸馏：问卷主导 vs 素材主导
- 新增触发词：我的视角、提取我的风格、我是一个怎样的人、照见自我

---

## [v1.0.0] - 2026-04-24

### 初始版本

- **三阶蒸馏法**完整实现：
  - Phase 1：观点探测（38道选择题，约10分钟）
  - Phase 2：情境反应（7个情境题 + 追问，约15分钟）
  - Phase 3：语料采样（2个写作任务，约5分钟）
  - **可选扩展**：素材导入（上传已有文章/论文）
- **问卷结构**：38题问卷 + 7场景情境题 + 3个写作任务
- 名字渊源：取自王阳明"致良知""知行合一""反求诸己"理念
