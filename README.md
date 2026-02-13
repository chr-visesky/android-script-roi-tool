# 安卓脚本切图神器 v3.0

一款专为安卓游戏脚本开发设计的可视化切图工具。

## 功能特点

- **📁 文件夹浏览** - 左侧显示图片列表，点击即可加载
- **🎯 ROI框选** - 拖拽创建、8方向调整、自由移动
- **📋 复制ROI** - 支持Ctrl+C复制，右键菜单复制
- **✂️ 自动切图** - 框选完成自动保存切图
- **💻 代码生成** - 自动生成Auto.js/Python代码
- **📦 批量导出** - 一键导出JSON/XML/脚本

## 安装

```bash
pip install -r requirements.txt
```

## 使用

```bash
python main.py
```

## 操作指南

### 基本流程
1. 打开文件夹 或 粘贴剪贴板图片
2. 点击"框选模式"，拖拽创建ROI
3. 自动切图并生成代码
4. 导出所有数据

### 快捷键
| 快捷键 | 功能 |
|--------|------|
| `Ctrl+V` | 粘贴图片 |
| `Ctrl+O` | 打开文件夹 |
| `Delete` | 删除选中ROI |
| `Ctrl+C` | 复制ROI |
| `方向键` | 切换图片/微调位置 |
| `Shift+方向键` | 大幅微调(10px) |

## 项目结构

```
android_script_tool/
├── main.py                 # 主入口
├── src/
│   ├── models/            # 数据模型
│   │   └── roi.py         # ROI类
│   ├── core/              # 核心功能
│   │   ├── screenshot.py  # 截图管理
│   │   ├── crop_engine.py # 切图引擎
│   │   └── export_manager.py # 导出管理
│   ├── ui/                # UI界面
│   │   ├── main_window.py # 主窗口
│   │   ├── image_canvas.py # 图像画布
│   │   └── roi_list_panel.py # ROI列表
│   └── utils/             # 工具函数
│       └── helpers.py
├── config/                # 配置文件
├── requirements.txt
└── README.md
```

## 输出格式

- **切图**: PNG格式，自动命名
- **JSON**: 完整ROI数据
- **Auto.js**: 可直接运行的脚本
- **Python**: OpenCV模板匹配代码
