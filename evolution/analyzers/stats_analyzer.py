"""
王阳明进化模块 - 统计分析器
分析反馈数据，识别问题题目，生成改进建议
"""

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

# 数据目录
DATA_DIR = Path(__file__).parent.parent / "feedback"
RATINGS_FILE = DATA_DIR / "ratings.json"
QUESTION_STATS_FILE = DATA_DIR / "question_stats.json"

# 已知题目ID列表
KNOWN_QUESTIONS = {
    "G1_openness": {"dimension": "开放性", "phase": 1},
    "G2_conscientiousness": {"dimension": "尽责性", "phase": 1},
    "G3_neuroticism": {"dimension": "情绪稳定性", "phase": 1},
    "F1_ranking": {"dimension": "价值排序", "phase": 1},
    "G5_implicit": {"dimension": "内隐偏好", "phase": 1},
    "H1_autonomy": {"dimension": "自主感", "phase": 1},
    "H2_competence": {"dimension": "能力感", "phase": 1},
    "H3_relatedness": {"dimension": "关联感", "phase": 1},
    "S1_interest_conflict": {"dimension": "利益冲突", "phase": 2},
    "S2_authority_challenge": {"dimension": "权威挑战", "phase": 2},
    "S3_ethical_dilemma": {"dimension": "道德困境", "phase": 2},
    "S4_career_choice": {"dimension": "长期选择", "phase": 2},
    "S5_cognitive_conflict": {"dimension": "认知冲突", "phase": 2},
    "S6A_attachment_romantic": {"dimension": "依恋(亲密)", "phase": 2},
    "S6B_attachment_family": {"dimension": "依恋(家庭)", "phase": 2},
}


class StatsAnalyzer:
    def __init__(self, data_dir=None):
        if data_dir:
            self.data_dir = data_dir
        else:
            self.data_dir = DATA_DIR
        self.ratings_file = self.data_dir / "ratings.json"
        self.question_stats_file = self.data_dir / "question_stats.json"
    
    def _load_ratings(self):
        with open(self.ratings_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _load_question_stats(self):
        if self.question_stats_file.exists():
            with open(self.question_stats_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"questions": {}, "high_confidence_questions": [], "needs_review_questions": []}
    
    def _save_question_stats(self, data):
        with open(self.question_stats_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def analyze_ratings(self):
        ratings_data = self._load_ratings()
        sessions = ratings_data.get("sessions", [])
        
        if not sessions:
            return {"status": "no_data", "message": "暂无反馈数据"}
        
        total = len(sessions)
        scores = [s.get("overall_score", 0) for s in sessions]
        avg_score = sum(scores) / len(scores) if scores else 0
        score_dist = Counter(scores)
        
        dimension_scores = defaultdict(list)
        for session in sessions:
            dims = session.get("dimension_scores", {})
            for dim, score in dims.items():
                if score > 0:
                    dimension_scores[dim].append(score)
        
        dimension_avg = {
            dim: round(sum(scores) / len(scores), 2)
            for dim, scores in dimension_scores.items() if scores
        }
        
        all_suggestions = []
        low_score_reasons = []
        for session in sessions:
            if session.get("suggestions"):
                all_suggestions.extend(session["suggestions"])
            if session.get("overall_score", 5) <= 2 and session.get("feedback_text"):
                low_score_reasons.append(session["feedback_text"])
        
        return {
            "status": "success",
            "total_sessions": total,
            "avg_score": round(avg_score, 2),
            "score_distribution": dict(score_dist),
            "dimension_averages": dimension_avg,
            "low_score_count": len([s for s in sessions if s.get("overall_score", 5) <= 2]),
            "high_score_count": len([s for s in sessions if s.get("overall_score", 0) >= 4]),
            "total_suggestions": len(all_suggestions),
            "suggestion_samples": all_suggestions[:5],
            "low_score_reasons": low_score_reasons[:3]
        }
    
    def generate_improvement_suggestions(self):
        analysis = self.analyze_ratings()
        if analysis.get("status") == "no_data":
            return []
        
        suggestions = []
        dim_avgs = analysis.get("dimension_averages", {})
        
        for dim, avg in dim_avgs.items():
            if avg < 3.5:
                suggestions.append({
                    "type": "dimension_concern",
                    "priority": "high" if avg < 3.0 else "medium",
                    "dimension": dim,
                    "current_avg": avg,
                    "suggestion": f"「{dim}」维度平均分较低({avg})，需要重点优化",
                    "possible_reasons": [
                        "该维度的问卷题目可能不够精准",
                        "题目表述可能引起误解"
                    ]
                })
        
        low_score_reasons = analysis.get("low_score_reasons", [])
        if low_score_reasons:
            suggestions.append({
                "type": "user_feedback",
                "priority": "high",
                "suggestion": "存在低分反馈，需要关注",
                "reasons": low_score_reasons
            })
        
        avg_score = analysis.get("avg_score", 0)
        if avg_score < 3.5:
            suggestions.append({
                "type": "overall_concern",
                "priority": "high",
                "suggestion": f"整体平均分({avg_score})偏低，需要系统性检查问卷设计"
            })
        
        return suggestions
    
    def update_question_stats(self, question_id, skip=False, confusion=False, negative_feedback=False):
        stats = self._load_question_stats()
        
        if question_id not in stats["questions"]:
            info = KNOWN_QUESTIONS.get(question_id, {"dimension": "未知", "phase": 0})
            stats["questions"][question_id] = {
                "question_id": question_id,
                "dimension": info["dimension"],
                "phase": info["phase"],
                "total_answers": 0,
                "skip_count": 0,
                "confusion_count": 0,
                "negative_feedback_count": 0,
                "discrimination_score": 0,
                "feedback_flags": []
            }
        
        q = stats["questions"][question_id]
        q["total_answers"] += 1
        if skip: q["skip_count"] += 1
        if confusion: q["confusion_count"] += 1
        if negative_feedback:
            q["negative_feedback_count"] += 1
            q["feedback_flags"].append(datetime.now().isoformat())
        
        total = q["total_answers"]
        if total > 0:
            q["skip_rate"] = round(q["skip_count"] / total, 3)
            q["confusion_rate"] = round(q["confusion_count"] / total, 3)
            q["discrimination_score"] = round(1 - q["confusion_rate"] - q["skip_rate"] * 0.5, 3)
        
        stats["high_confidence_questions"] = [
            qid for qid, qdata in stats["questions"].items()
            if qdata.get("discrimination_score", 0) >= 0.8
        ]
        stats["needs_review_questions"] = [
            qid for qid, qdata in stats["questions"].items()
            if qdata.get("discrimination_score", 1) < 0.6 or qdata.get("skip_rate", 0) > 0.1
        ]
        
        self._save_question_stats(stats)
    
    def get_question_stats(self):
        return self._load_question_stats()


def run_analysis():
    print("\n" + "="*50)
    print("王阳明进化模块 - 统计分析")
    print("="*50)
    
    analyzer = StatsAnalyzer()
    analysis = analyzer.analyze_ratings()
    
    if analysis.get("status") == "no_data":
        print("\n暂无反馈数据，无法进行分析。")
        print("请先使用反馈收集功能")
        return
    
    print(f"\n总反馈数: {analysis.get('total_sessions', 0)}")
    print(f"平均评分: {analysis.get('avg_score', 0)}")
    
    print(f"\n评分分布")
    for score in range(1, 6):
        count = analysis.get("score_distribution", {}).get(score, 0)
        bar = "*" * count
        print(f"  {score}分: {bar} ({count})")
    
    if analysis.get("dimension_averages"):
        print(f"\n维度评分")
        for dim, avg in analysis.get("dimension_averages", {}).items():
            indicator = "OK" if avg >= 4 else "WARN" if avg >= 3 else "BAD"
            print(f"  [{indicator}] {dim}: {avg}")
    
    suggestions = analyzer.generate_improvement_suggestions()
    if suggestions:
        print(f"\n改进建议:")
        for i, s in enumerate(suggestions, 1):
            print(f"  {i}. {s.get('suggestion', '')}")
    else:
        print("\n暂无改进建议，继续保持！")


if __name__ == "__main__":
    run_analysis()
