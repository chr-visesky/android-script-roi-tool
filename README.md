# 安卓脚本切图神器

一款专为安卓自动化脚本开发的视觉元素切图工具。支持截图、框选ROI、自动检测图标、超像素合并，一键导出透明PNG和坐标JSON。

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15%2B-green)
![OpenCV](https://img.shields.io/badge/OpenCV-4.5%2B-orange)

## 功能特性

### 三种切图模式

| 模式 | 说明 | 操作方式 |
|------|------|----------|
| **手动框选** | 自由拖拽框选任意区域 | 按住Ctrl + 拖拽鼠标 |
| **超像素合并** | 点击合并相邻相似区域 | 按住Ctrl + 左键添加，右键取消 |
| **自动检测** | 智能识别图标/按钮边界 | 按住Ctrl + 左键点击 |

### ROI类型系统

- **图片类型 (image)**：导出透明PNG + JSON坐标，用于模板匹配
- **区域类型 (region)**：仅导出JSON，用于点击/OCR/滑动操作

### 详细配置

每种ROI可配置：
- **图片类型**：检测动作（detect / detect_and_click）
- **区域类型**：
  - 点击：单次/循环，点击次数，间隔时间
  - 滑动：方向（上/下/左/右），速度
  - OCR：文字识别区域

### 导出格式

- **JSON**：完整ROI数据（坐标、类型、动作配置）
- **Auto.js**：生成可直接运行的脚本
- **Python**：OpenCV模板匹配代码
- **PNG**：透明背景切图（仅图片类型）

## 快速开始

### 安装依赖

```bash
# 使用uv（推荐）
uv sync

# 或使用pip
pip install -r requirements.txt
```

### 启动程序

```bash
# 方式1：使用启动器
python start.py

# 方式2：直接运行
python main.py
```

### 基本 workflow

1. **加载图片**：文件 → 打开文件夹，或直接截图（Ctrl+S）
2. **选择模式**：顶部下拉框选择切图模式
3. **框选ROI**：
   - 按住 **Ctrl** 进入操作模式
   - 手动框选：拖拽绘制矩形
   - 超像素/自动检测：左键点击目标
   - 松开 **Ctrl** 弹出配置对话框
4. **配置属性**：设置节点名称、类型、动作参数
5. **导出结果**：Ctrl+S 或点击"导出全部"按钮

## 交互说明

### 通用快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl + S | 导出所有ROI |
| Ctrl + C | 复制选中ROI |
| Ctrl + Z | 撤销最后一个ROI |
| Delete | 删除选中ROI |
| 方向键 | 微调ROI位置（1px） |
| Shift + 方向键 | 快速微调（10px） |
| F | 切换1:1显示/适应窗口 |

### 鼠标操作

| 模式 | 操作 | 说明 |
|------|------|------|
| 选择模式 | 左键点击 | 选中ROI |
| 选择模式 | 左键拖拽 | 移动ROI |
| 选择模式 | 拖拽手柄 | 调整大小 |
| 选择模式 | 右键 | 菜单（复制/撤销/清空） |
| 框选模式 | 左键拖拽 | 创建新ROI |
| 合并/检测 | 左键点击 | 添加区域/检测图标 |
| 合并/检测 | 右键点击 | 取消区域/取消预览 |

## 项目结构

```
android_script-roi-tool/
├── main.py                 # 程序入口
├── start.py               # 启动器（带依赖检查）
├── src/
│   ├── ui/
│   │   ├── main_window.py     # 主窗口（2000行）
│   │   ├── image_canvas.py    # 画布组件（800行）
│   │   └── roi_list_panel.py  # ROI列表面板
│   ├── core/
│   │   ├── screenshot.py       # ADB截图管理
│   │   ├── auto_detect.py      # 自动图标检测
│   │   ├── superpixel_segment.py # 超像素分割
│   │   ├── smart_segment.py    # 智能分割（GrabCut）
│   │   ├── crop_engine.py      # 切图引擎
│   │   └── export_manager.py   # 导出管理
│   ├── models/
│   │   └── roi.py             # ROI数据模型
│   └── utils/
│       └── helpers.py         # 工具函数
├── tools/platform-tools/   # ADB工具
├── config.json            # 配置文件
└── requirements.txt       # 依赖列表
```

## 核心代码量

| 模块 | 行数 | 说明 |
|------|------|------|
| main_window.py | 2006 | 主界面、工具栏、对话框 |
| image_canvas.py | 794 | 画布交互、绘制、模式切换 |
| auto_detect.py | 489 | 颜色连通区域检测 |
| superpixel_segment.py | 482 | SLIC超像素分割 |
| screenshot.py | 431 | ADB截图、设备管理 |
| roi.py | 349 | 数据模型、序列化 |
| export_manager.py | 243 | JSON/代码导出 |

**总计：约6000行Python代码**

## 依赖说明

核心依赖：
- **PyQt5**：GUI界面
- **OpenCV**：图像处理、分割算法
- **NumPy**：数值计算
- **Pillow**：图像加载/保存

可选依赖：
- **ADB**：安卓设备截图（已内置platform-tools）

## 注意事项

1. **Ctrl键机制**：所有特殊操作（框选、合并、检测）都需要按住Ctrl，这是为了避免与选择/拖拽操作冲突
2. **定时器检测**：程序使用100ms定时器检测键盘状态，不依赖鼠标移动事件
3. **中文支持**：节点名称、文件名均支持中文，导出时自动处理编码

## 许可证

MIT License

## 更新日志

### v3.0 (2026-02-13)
- 全新三种模式架构（手动/超像素/自动检测）
- ROI类型系统（图片/区域）
- 100ms定时器键盘状态检测
- 统一配置对话框
- 完整导出系统（JSON/Auto.js/Python）
