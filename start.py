#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动脚本 - 检查并安装依赖，然后启动程序
"""

import sys
import subprocess
import os

def check_and_install_dependencies():
    """检查并安装依赖"""
    required_packages = [
        ("PyQt5", "PyQt5>=5.15.0"),
        ("PIL", "Pillow>=9.0.0"),
        ("cv2", "opencv-python>=4.5.0"),
        ("numpy", "numpy>=1.21.0"),
    ]

    missing = []
    for module, package in required_packages:
        try:
            __import__(module)
            print(f"[OK] {package} installed")
        except ImportError:
            missing.append(package)
            print(f"[MISSING] {package} not installed")

    if missing:
        print(f"\nInstalling missing dependencies: {', '.join(missing)}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user"] + missing)
            print("Dependencies installed!")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install dependencies: {e}")
            print("Please manually run: pip install " + " ".join(missing))
            sys.exit(1)
    else:
        print("\nAll dependencies installed, starting application...")

def main():
    """主函数"""
    print("=" * 50)
    print("Android Script ROI Tool v3.0 - Launcher")
    print("=" * 50)

    check_and_install_dependencies()

    # Import and start main application
    try:
        from main import main as app_main
        app_main()
    except Exception as e:
        print(f"Failed to start: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
