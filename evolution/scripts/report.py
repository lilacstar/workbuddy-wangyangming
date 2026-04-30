"""
王阳明进化模块 - 报告生成脚本
生成改进建议报告
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "reports"))
from report_generator import generate_report

if __name__ == "__main__":
    generate_report()
