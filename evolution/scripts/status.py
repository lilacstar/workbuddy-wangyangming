"""
王阳明进化模块 - 状态查看脚本
查看当前进化模块的状态
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "collectors"))
sys.path.insert(0, str(Path(__file__).parent.parent / "analyzers"))
from feedback_collector import FeedbackCollector
from stats_analyzer import StatsAnalyzer

def main():
    print("\n" + "="*50)
    print("王阳明进化模块 - 状态概览")
    print("="*50)
    
    collector = FeedbackCollector()
    analyzer = StatsAnalyzer()
    
    # 获取统计数据
    stats = collector.get_stats()
    
    print(f"\n总反馈数: {stats.get('total_sessions', 0)}")
    print(f"平均评分: {stats.get('avg_overall_score', 0)}")
    
    print("\n维度平均分:")
    dim_scores = stats.get('avg_dimension_scores', {})
    if dim_scores:
        for dim, score in dim_scores.items():
            if score > 0:
                print(f"  {dim}: {score}")
    else:
        print("  暂无数据")
    
    # 获取题目统计
    q_stats = analyzer.get_question_stats()
    
    print(f"\n高置信题目数: {len(q_stats.get('high_confidence_questions', []))}")
    print(f"需审核题目数: {len(q_stats.get('needs_review_questions', []))}")
    
    if q_stats.get('needs_review_questions'):
        print("\n需审核的题目:")
        for qid in q_stats.get('needs_review_questions', [])[:5]:
            q = q_stats.get('questions', {}).get(qid, {})
            if q:
                print(f"  - {qid}: {q.get('dimension', '未知')} (区分度:{q.get('discrimination_score', 0)})")
    
    print("\n" + "="*50)
    print("可用命令:")
    print("  python scripts/collect.py   - 收集反馈")
    print("  python scripts/analyze.py   - 运行分析")
    print("  python scripts/report.py    - 生成报告")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
