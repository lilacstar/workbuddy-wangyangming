"""
王阳明进化模块 - 统计分析脚本
运行统计分析并输出结果
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "analyzers"))
from stats_analyzer import run_analysis

if __name__ == "__main__":
    run_analysis()
