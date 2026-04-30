"""
王阳明进化模块 - 反馈收集脚本
交互式收集用户反馈
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "collectors"))
from feedback_collector import interactive_collect

if __name__ == "__main__":
    interactive_collect()
