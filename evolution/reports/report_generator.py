"""
王阳明进化模块 - 改进报告生成器
生成结构化的改进建议报告
"""

import json
from datetime import datetime
from pathlib import Path

# 导入分析器
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "analyzers"))
from stats_analyzer import StatsAnalyzer

# 数据目录
DATA_DIR = Path(__file__).parent.parent / "feedback"
IMPROVEMENT_LOG = DATA_DIR / "improvement_log.md"


class ReportGenerator:
    """生成改进建议报告"""
    
    def __init__(self):
        self.analyzer = StatsAnalyzer()
    
    def generate_markdown_report(self) -> str:
        """生成Markdown格式的改进报告"""
        analysis = self.analyzer.analyze_ratings()
        suggestions = self.analyzer.generate_improvement_suggestions()
        question_stats = self.analyzer.get_question_stats()
        
        report = []
        report.append("# 王阳明进化报告")
        report.append("")
        report.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report.append("")
        
        # 基础统计
        if analysis.get("status") == "success":
            report.append("## 基础统计")
            report.append("")
            report.append(f"- **总反馈数**: {analysis.get('total_sessions', 0)}")
            report.append(f"- **平均评分**: {analysis.get('avg_score', 0)}")
            report.append(f"- **高分(4-5分)数量**: {analysis.get('high_score_count', 0)}")
            report.append(f"- **低分(1-2分)数量**: {analysis.get('low_score_count', 0)}")
            report.append("")
            
            # 评分分布
            report.append("### 评分分布")
            report.append("")
            dist = analysis.get("score_distribution", {})
            for score in range(5, 0, -1):
                count = dist.get(score, 0)
                pct = (count / analysis.get('total_sessions', 1)) * 100
                bar = "=" * int(pct / 5)
                report.append(f"- {score}分: {bar} {count}票 ({pct:.1f}%)")
            report.append("")
            
            # 维度评分
            if analysis.get("dimension_averages"):
                report.append("### 维度评分")
                report.append("")
                for dim, avg in sorted(analysis.get("dimension_averages", {}).items()):
                    status = "GOOD" if avg >= 4 else "WARN" if avg >= 3 else "BAD"
                    report.append(f"- [{status}] {dim}: {avg}")
                report.append("")
        else:
            report.append("## 暂无数据")
            report.append("")
            report.append("还没有收到足够的反馈数据。")
            report.append("")
        
        # 改进建议
        if suggestions:
            report.append("## 改进建议")
            report.append("")
            for i, s in enumerate(suggestions, 1):
                priority = "[HIGH]" if s.get("priority") == "high" else "[MED]"
                report.append(f"### {i}. {priority} {s.get('suggestion', '')}")
                report.append("")
                if s.get("possible_reasons"):
                    report.append("**可能原因**:")
                    for reason in s.get("possible_reasons", []):
                        report.append(f"- {reason}")
                    report.append("")
                if s.get("reasons"):
                    report.append("**用户反馈**:")
                    for reason in s.get("reasons", []):
                        if reason:
                            report.append(f"- {reason}")
                    report.append("")
        else:
            report.append("## 改进建议")
            report.append("")
            report.append("暂无需要改进的地方，继续保持！")
            report.append("")
        
        # 题目统计
        if question_stats.get("needs_review_questions"):
            report.append("## 需要审核的题目")
            report.append("")
            for qid in question_stats.get("needs_review_questions", []):
                q = question_stats.get("questions", {}).get(qid, {})
                if q:
                    report.append(f"- **{qid}** ({q.get('dimension', '未知')})")
                    report.append(f"  - 回答数: {q.get('total_answers', 0)}")
                    report.append(f"  - 区分度: {q.get('discrimination_score', 0)}")
                    report.append(f"  - 跳过率: {q.get('skip_rate', 0)}")
                    report.append(f"  - 困惑率: {q.get('confusion_rate', 0)}")
            report.append("")
        
        report.append("---")
        report.append("")
        report.append("*本报告由王阳明进化模块自动生成*")
        
        return "\n".join(report)
    
    def save_report(self, filepath: Path = None) -> str:
        """保存报告到文件"""
        if not filepath:
            reports_dir = Path(__file__).parent.parent / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
            filepath = reports_dir / filename
        
        content = self.generate_markdown_report()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        return str(filepath)


def generate_report():
    """命令行生成报告"""
    print("\n" + "="*50)
    print("王阳明进化模块 - 改进报告生成")
    print("="*50)
    
    generator = ReportGenerator()
    
    # 生成分内报告到控制台
    print(generator.generate_markdown_report())
    
    # 保存到文件
    filepath = generator.save_report()
    print(f"\n报告已保存到: {filepath}")


if __name__ == "__main__":
    generate_report()
