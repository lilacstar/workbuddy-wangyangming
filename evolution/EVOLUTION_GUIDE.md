# 王阳明进化模块 (WangYangming Evolution Module)

> 版本：v1.0.0
> 更新：2026-04-26
> 设计理念：用户反馈驱动迭代，让问卷题目越用越精准

---

## 一、模块定位

进化模块是王阳明的"自我反思"机制，借鉴阳明心学"反求诸己"的思想：

> 用户使用王阳明 → 生成Skill → 反馈像不像 → 统计分析 → 改进建议 → 人工确认 → 更新题目

### 与达尔文的区别

| 维度 | 达尔文 (女娲) | 进化模块 (王阳明) |
|------|---------------|-------------------|
| 优化对象 | 生成内容的风格一致性 | 问卷题目的区分度 |
| 评估标准 | 有ground truth可对比 | 用户主观反馈 |
| 自动化程度 | 批量实验 + AI评分 | 用户反馈 + 人工决策 |
| 适用场景 | 内容生成器 | 问卷工具 |

---

## 二、核心组件

```
evolution/
├── feedback/
│   ├── ratings.json          # 用户评分记录
│   ├── question_stats.json   # 题目区分度统计
│   └── improvement_log.md    # 改进建议日志
│
├── collectors/
│   └── feedback_collector.py  # 收集用户反馈
│
├── analyzers/
│   └── stats_analyzer.py       # 统计分析模块
│
├── reports/
│   └── report_generator.py     # 生成改进报告
│
├── scripts/
│   ├── collect.py              # 交互式收集反馈
│   ├── analyze.py              # 运行统计分析
│   └── report.py               # 生成改进报告
│
└── EVOLUTION_GUIDE.md          # 使用指南
```

---

## 三、数据结构

### 3.1 ratings.json - 评分记录

```json
{
  "sessions": [
    {
      "id": "session_20260426_001",
      "timestamp": "2026-04-26T17:45:00",
      "user_id": "anonymous",
      "overall_score": 4,
      "dimension_scores": {
        "准确度": 4,
        "风格一致性": 5,
        "识别度": 4
      },
      "feedback_text": "整体很像我，但决策启发式有点抽象",
      "suggestions": [
        "决策启发式可以更具体一些",
        "加入一些口头禅"
      ]
    }
  ],
  "stats": {
    "total_sessions": 1,
    "avg_overall_score": 4.0,
    "avg_dimension_scores": {
      "准确度": 4.0,
      "风格一致性": 5.0,
      "识别度": 4.0
    }
  }
}
```

### 3.2 question_stats.json - 题目统计

```json
{
  "questions": {
    "G1_openness": {
      "question_id": "G1",
      "dimension": "开放性",
      "total_answers": 15,
      "skip_rate": 0.05,
      "confusion_rate": 0.10,
      "discrimination_score": 0.85,
      "feedback_flags": []
    }
  },
  "high_confidence_questions": ["G1_openness", "F1_ranking"],
  "needs_review_questions": ["S3_ethical"]
}
```

### 3.3 improvement_log.md - 改进日志

```markdown
# 王阳明改进日志

## 2026-04-26

### 新增题目

- **Q_creativity**: 新增关于创造力的追问
  - 来源：用户反馈"希望了解更多关于创造力的维度"
  - 状态：待审核

### 修改题目

- **F1_ranking**: 将6项扩展为8项
  - 原因：多用户反馈排序不够细致
  - 状态：已采纳

### 删除题目

- ~~**S3_dilemma_legacy**~~: 删除
  - 原因：与社会赞许效应探测重复
  - 状态：已采纳
```

---

## 四、工作流程

### 4.1 反馈收集流程

```
蒸馏完成 → 询问"生成的Skill像不像你？" 
                      ↓
              1-5分快速打分
                      ↓
              维度细分打分（可选）
                      ↓
              文字反馈（可选）
                      ↓
              记录到ratings.json
```

### 4.2 统计分析流程

```
定期运行 stats_analyzer.py
                      ↓
              读取ratings.json
                      ↓
              计算各维度平均分
                      ↓
              分析题目区分度
                      ↓
              标记需要审核的题目
                      ↓
              更新question_stats.json
```

### 4.3 改进决策流程

```
定期运行 report_generator.py
                      ↓
              读取question_stats.json
                      ↓
              生成改进建议列表
                      ↓
              输出改进报告
                      ↓
              人工审核建议
                      ↓
              采纳/拒绝/修改
                      ↓
              更新改进日志
                      ↓
              更新问卷题目
```

---

## 五、使用方式

### 5.1 交互式收集反馈

```bash
python evolution/scripts/collect.py
```

### 5.2 运行统计分析

```bash
python evolution/scripts/analyze.py
```

### 5.3 生成改进报告

```bash
python evolution/scripts/report.py
```

### 5.4 查看当前状态

```bash
python evolution/scripts/status.py
```

---

## 六、评估维度

| 维度 | 说明 | 评分标准 |
|------|------|----------|
| 准确度 | Skill是否准确反映你的思维模式 | 1-5分 |
| 风格一致性 | 表达风格是否像你 | 1-5分 |
| 识别度 | 使用Skill时是否感觉"这就是我" | 1-5分 |
| 可用性 | Skill在实际场景中是否实用 | 1-5分 |

---

## 七、题目区分度指标

| 指标 | 说明 | 健康范围 |
|------|------|----------|
| skip_rate | 用户跳过率 | < 5% |
| confusion_rate | 用户表示困惑率 | < 10% |
| discrimination_score | 区分度分数 | > 0.7 |
| feedback_flags | 负面反馈标记数 | < 3 |

---

## 八、版本历史

### v1.0.0 (2026-04-26)

初始版本发布

- 反馈收集系统
- 统计分析模块
- 改进报告生成器
