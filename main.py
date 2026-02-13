#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安卓游戏脚本切图工具 - 主入口
Android Game Script Crop Tool - Main Entry

功能：截图 → 框选ROI → 自动生成切图、坐标、代码
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from src.ui.main_window import MainWindow


def main():
    """应用程序入口"""
    # 启用高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName("安卓脚本切图神器")
    app.setApplicationVersion("3.0.0")
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
