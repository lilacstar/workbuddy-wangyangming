"""
王阳明进化模块 - 反馈收集器
收集用户对Skill输出的评分和反馈
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# 数据目录
DATA_DIR = Path(__file__).parent.parent / "feedback"
RATINGS_FILE = DATA_DIR / "ratings.json"


class FeedbackCollector:
    """收集用户对王阳明生成的Skill的反馈"""
    
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir:
            self.data_dir = data_dir
        else:
            self.data_dir = DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.ratings_file = self.data_dir / "ratings.json"
        self._ensure_ratings_file()
    
    def _ensure_ratings_file(self):
        """确保ratings.json文件存在"""
        if not self.ratings_file.exists():
            default_data = {
                "sessions": [],
                "stats": {
                    "total_sessions": 0,
                    "avg_overall_score": 0,
                    "avg_dimension_scores": {
                        "准确度": 0,
                        "风格一致性": 0,
                        "识别度": 0,
                        "可用性": 0
                    }
                }
            }
            with open(self.ratings_file, "w", encoding="utf-8") as f:
                json.dump(default_data, f, ensure_ascii=False, indent=2)
    
    def _load_ratings(self) -> dict:
        """加载评分数据"""
        with open(self.ratings_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _save_ratings(self, data: dict):
        """保存评分数据"""
        with open(self.ratings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _update_stats(self, data: dict):
        """更新统计数据"""
        sessions = data.get("sessions", [])
        if not sessions:
            return
        
        # 计算总体平均分
        total_scores = [s.get("overall_score", 0) for s in sessions]
        data["stats"]["total_sessions"] = len(sessions)
        data["stats"]["avg_overall_score"] = round(sum(total_scores) / len(total_scores), 2)
        
        # 计算各维度平均分
        dimensions = ["准确度", "风格一致性", "识别度", "可用性"]
        for dim in dimensions:
            dim_scores = [s.get("dimension_scores", {}).get(dim, 0) for s in sessions]
            valid_scores = [s for s in dim_scores if s > 0]
            if valid_scores:
                data["stats"]["avg_dimension_scores"][dim] = round(sum(valid_scores) / len(valid_scores), 2)
            else:
                data["stats"]["avg_dimension_scores"][dim] = 0
    
    def add_feedback(
        self,
        overall_score: int,
        dimension_scores: Optional[dict] = None,
        feedback_text: Optional[str] = None,
        suggestions: Optional[list] = None,
        user_id: str = "anonymous"
    ) -> str:
        """
        添加一条反馈
        
        Args:
            overall_score: 总体评分 (1-5)
            dimension_scores: 各维度评分 {"准确度": 4, "风格一致性": 5, ...}
            feedback_text: 文字反馈
            suggestions: 改进建议列表
            user_id: 用户标识
        
        Returns:
            session_id: 本次反馈的ID
        """
        data = self._load_ratings()
        
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        session = {
            "id": session_id,
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "overall_score": overall_score,
            "dimension_scores": dimension_scores or {},
            "feedback_text": feedback_text or "",
            "suggestions": suggestions or []
        }
        
        data["sessions"].append(session)
        self._update_stats(data)
        self._save_ratings(data)
        
        return session_id
    
    def quick_feedback(self, score: int) -> str:
        """
        快速反馈：只记录总分
        
        Args:
            score: 评分 (1-5)
        
        Returns:
            session_id
        """
        return self.add_feedback(overall_score=score)
    
    def get_stats(self) -> dict:
        """获取当前统计信息"""
        data = self._load_ratings()
        return data.get("stats", {})
    
    def get_recent_sessions(self, limit: int = 10) -> list:
        """获取最近的反馈记录"""
        data = self._load_ratings()
        sessions = data.get("sessions", [])
        return sorted(sessions, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]
    
    def get_all_sessions(self) -> list:
        """获取所有反馈记录"""
        data = self._load_ratings()
        return data.get("sessions", [])
    
    def delete_session(self, session_id: str) -> bool:
        """删除一条反馈记录"""
        data = self._load_ratings()
        sessions = data.get("sessions", [])
        original_len = len(sessions)
        sessions = [s for s in sessions if s.get("id") != session_id]
        
        if len(sessions) == original_len:
            return False
        
        data["sessions"] = sessions
        self._update_stats(data)
        self._save_ratings(data)
        return True


def interactive_collect():
    """交互式收集反馈"""
    print("\n" + "="*50)
    print("王阳明进化模块 - 反馈收集")
    print("="*50)
    
    collector = FeedbackCollector()
    
    # 获取总分
    print("\n请对生成的Skill进行评分（1-5分）:")
    print("1 - 完全不像我")
    print("2 - 大部分不像")
    print("3 - 一般")
    print("4 - 比较像我")
    print("5 - 非常像我")
    
    while True:
        try:
            score = int(input("\n你的评分: "))
            if 1 <= score <= 5:
                break
            print("请输入1-5之间的数字")
        except ValueError:
            print("请输入有效的数字")
    
    # 可选：维度评分
    print("\n各维度评分（直接回车跳过）:")
    dimension_scores = {}
    
    for dim in ["准确度", "风格一致性", "识别度", "可用性"]:
        val = input(f"  {dim} (1-5): ")
        if val.strip():
            try:
                s = int(val)
                if 1 <= s <= 5:
                    dimension_scores[dim] = s
            except ValueError:
                pass
    
    # 可选：文字反馈
    print("\n文字反馈（直接回车跳过）:")
    feedback_text = input("  你觉得这个Skill哪里不像你？: ").strip()
    
    # 可选：改进建议
    print("\n改进建议（输入q结束）:")
    suggestions = []
    while True:
        s = input("  建议: ").strip()
        if s.lower() == 'q':
            break
        if s:
            suggestions.append(s)
    
    # 保存反馈
    session_id = collector.add_feedback(
        overall_score=score,
        dimension_scores=dimension_scores if dimension_scores else None,
        feedback_text=feedback_text if feedback_text else None,
        suggestions=suggestions if suggestions else None
    )
    
    print(f"\n反馈已保存！Session ID: {session_id}")
    
    # 显示更新后的统计
    stats = collector.get_stats()
    print(f"\n当前统计:")
    print(f"  总反馈数: {stats.get('total_sessions', 0)}")
    print(f"  平均评分: {stats.get('avg_overall_score', 0)}")


if __name__ == "__main__":
    interactive_collect()
