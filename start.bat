@echo off
chcp 65001 >nul
title 安卓脚本切图神器 v3.0
echo ==========================================
echo  安卓脚本切图神器 v3.0
echo ==========================================
echo.

:: 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请确保Python已安装并添加到PATH
    pause
    exit /b 1
)

echo [1/3] 检查依赖...
python -c "import PyQt5" >nul 2>&1
if errorlevel 1 (
    echo [2/3] 安装依赖...
    python -m pip install PyQt5>=5.15.0 Pillow>=9.0.0 opencv-python>=4.5.0 numpy>=1.21.0
) else (
    echo [2/3] 依赖已安装
)

echo [3/3] 启动程序...
echo.
python main.py

if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出
    pause
)
