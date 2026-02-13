# -*- coding: utf-8 -*-
"""
主窗口 - 重写版
优化脚本切图工作流程
"""

import os
import sys
import time

# 抑制OpenCV/libpng警告
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import warnings
warnings.filterwarnings('ignore', category=UserWarning)
import cv2
import numpy as np

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QFileDialog,
    QMessageBox, QMenuBar, QMenu, QAction, QToolBar,
    QStatusBar, QScrollArea, QFrame, QShortcut,
    QInputDialog, QApplication, QListWidget, QListWidgetItem,
    QGroupBox, QFormLayout, QSplitter, QComboBox, QCheckBox,
    QProgressBar, QDialog, QDialogButtonBox, QProgressDialog,
    QSpinBox, QStackedWidget
)
from PyQt5.QtCore import Qt, QDir, QSize
from PyQt5.QtGui import QKeySequence, QPixmap, QIcon, QFont

from .image_canvas import ImageCanvas
from ..core.screenshot import ScreenshotManager
from ..core.crop_engine import CropEngine
from ..core.export_manager import ExportManager
from ..core.auto_detect import AutoDetector
from ..core.smart_segment import SmartSegmenter
from ..core.superpixel_segment import SuperpixelSegmenter, SuperpixelMergeTool
from ..models.roi import ROI


class ROIDialog(QDialog):
    """
    ROI配置对话框 - 支持详细配置
    - 图片：判断存在 / 判断存在后点击
    - 区域-点击：单次/循环，点击次数和频率
    - 区域-滑动：方向、速度
    """

    def __init__(self, parent=None, default_name="", roi_type="image", action=""):
        super().__init__(parent)
        self.setWindowTitle("配置ROI")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # 基础信息组
        basic_group = QGroupBox("基础信息")
        basic_layout = QFormLayout()

        self.node_name_input = QLineEdit(default_name)
        self.node_name_input.setPlaceholderText("如：home_button, username_input")
        basic_layout.addRow("节点名称:", self.node_name_input)

        # ROI类型选择
        self.type_combo = QComboBox()
        self.type_combo.addItem("图片（需要切图导出）", "image")
        self.type_combo.addItem("区域（功能区域，无图片）", "region")
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        basic_layout.addRow("类型:", self.type_combo)

        # 设置默认类型
        if roi_type == "region":
            self.type_combo.setCurrentIndex(1)

        # 区域动作选择（仅区域类型显示）
        self.action_combo = QComboBox()
        self.action_combo.addItem("点击", "click")
        self.action_combo.addItem("OCR文字识别", "ocr")
        self.action_combo.addItem("滑动", "swipe")
        self.action_combo.currentIndexChanged.connect(self.on_action_changed)
        basic_layout.addRow("区域动作:", self.action_combo)

        # 保存标签引用以便显示/隐藏
        self._action_label = None

        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)

        # 动态配置区域
        self.config_stack = QStackedWidget()

        # 1. 图片配置页面
        self.image_page = self._create_image_page()
        self.config_stack.addWidget(self.image_page)

        # 2. 区域-点击配置页面
        self.click_page = self._create_click_page()
        self.config_stack.addWidget(self.click_page)

        # 3. 区域-OCR配置页面（简单，无额外配置）
        self.ocr_page = self._create_ocr_page()
        self.config_stack.addWidget(self.ocr_page)

        # 4. 区域-滑动配置页面
        self.swipe_page = self._create_swipe_page()
        self.config_stack.addWidget(self.swipe_page)

        layout.addWidget(self.config_stack)

        # 说明文字
        self.desc_label = QLabel()
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #666; font-size: 12px; margin: 10px 0;")
        layout.addWidget(self.desc_label)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.on_type_changed()  # 初始化状态

        # 所有UI创建完成后，再连接信号（确保image_name_input已创建）
        self.node_name_input.textChanged.connect(self.on_node_name_changed)
        # 初始化图片文件名（如果节点名称有默认值）
        if default_name:
            self.on_node_name_changed(default_name)

    def _create_image_page(self):
        """创建图片配置页面"""
        page = QWidget()
        layout = QFormLayout(page)

        self.image_action_combo = QComboBox()
        self.image_action_combo.addItem("仅判断存在", "detect")
        self.image_action_combo.addItem("判断存在后点击", "detect_and_click")
        layout.addRow("图片动作:", self.image_action_combo)

        self.image_name_input = QLineEdit()
        self.image_name_input.setPlaceholderText("可选，如：icon_home.png")
        layout.addRow("图片文件名:", self.image_name_input)

        return page

    def _create_click_page(self):
        """创建点击配置页面"""
        page = QWidget()
        layout = QFormLayout(page)

        self.click_mode_combo = QComboBox()
        self.click_mode_combo.addItem("单次点击", "single")
        self.click_mode_combo.addItem("循环点击", "loop")
        self.click_mode_combo.currentIndexChanged.connect(self.on_click_mode_changed)
        layout.addRow("点击模式:", self.click_mode_combo)

        # 循环点击配置
        self.click_config_widget = QWidget()
        click_config_layout = QFormLayout(self.click_config_widget)

        self.click_count_spin = QSpinBox()
        self.click_count_spin.setRange(-1, 9999)
        self.click_count_spin.setValue(1)
        self.click_count_spin.setSpecialValueText("无限")  # -1显示为"无限"
        click_config_layout.addRow("点击次数(-1=无限):", self.click_count_spin)

        self.click_interval_spin = QSpinBox()
        self.click_interval_spin.setRange(100, 60000)
        self.click_interval_spin.setValue(500)  # 默认500ms
        self.click_interval_spin.setSuffix(" ms")
        click_config_layout.addRow("点击间隔:", self.click_interval_spin)

        layout.addRow(self.click_config_widget)

        return page

    def _create_ocr_page(self):
        """创建OCR配置页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("OCR文字识别：脚本会在此区域进行文字识别。\n无需额外配置。"))
        layout.addStretch()
        return page

    def _create_swipe_page(self):
        """创建滑动配置页面"""
        page = QWidget()
        layout = QFormLayout(page)

        self.swipe_direction_combo = QComboBox()
        self.swipe_direction_combo.addItem("从上到下", "top_to_bottom")
        self.swipe_direction_combo.addItem("从下到上", "bottom_to_top")
        self.swipe_direction_combo.addItem("从左到右", "left_to_right")
        self.swipe_direction_combo.addItem("从右到左", "right_to_left")
        layout.addRow("滑动方向:", self.swipe_direction_combo)

        self.swipe_speed_spin = QSpinBox()
        self.swipe_speed_spin.setRange(100, 5000)
        self.swipe_speed_spin.setValue(400)  # 默认400像素/秒
        self.swipe_speed_spin.setSuffix(" px/s")
        layout.addRow("滑动速度:", self.swipe_speed_spin)

        return page

    def on_node_name_changed(self, text):
        """节点名称改变时，自动更新图片文件名（仅在图片类型时）"""
        # 只在图片类型时同步
        if self.type_combo.currentData() != "image":
            return

        current_img_name = self.image_name_input.text().strip()
        if not current_img_name:
            # 空值，直接设置
            self.image_name_input.setText(f"{text}.png" if text else "")
        elif current_img_name.endswith('.png'):
            # 图片名以.png结尾，直接更新为节点名.png
            self.image_name_input.setText(f"{text}.png" if text else "")

    def on_type_changed(self):
        """类型改变时更新UI"""
        roi_type = self.type_combo.currentData()
        is_region = roi_type == "region"

        # 显示/隐藏区域动作选择
        self.action_combo.setVisible(is_region)

        if roi_type == "image":
            self.config_stack.setCurrentIndex(0)  # 图片页面
            self.desc_label.setText(
                "图片类型：导出透明PNG，用于脚本中的找图匹配。\n"
                "- 判断存在：仅检测图片是否出现\n"
                "- 判断存在后点击：检测到后执行点击"
            )
        else:
            # 区域类型，根据动作显示不同页面
            self.on_action_changed()

    def on_action_changed(self):
        """区域动作改变时更新UI"""
        action = self.action_combo.currentData()

        action_desc = {
            "click": "点击：在区域中心执行点击操作，可配置单次或循环。",
            "ocr": "OCR：识别区域内的文字内容。",
            "swipe": "滑动：在区域内执行滑动手势。"
        }
        self.desc_label.setText(action_desc.get(action, ""))

        # 切换对应页面
        page_map = {"click": 1, "ocr": 2, "swipe": 3}
        self.config_stack.setCurrentIndex(page_map.get(action, 2))

    def on_click_mode_changed(self):
        """点击模式改变"""
        is_loop = self.click_mode_combo.currentData() == "loop"
        self.click_config_widget.setVisible(is_loop)

    def showEvent(self, event):
        """显示时初始化状态"""
        super().showEvent(event)
        self.on_click_mode_changed()

    def get_config(self):
        """获取配置结果"""
        roi_type = self.type_combo.currentData()

        config = {
            "node_name": self.node_name_input.text().strip(),
            "roi_type": roi_type,
            "action": "",
            "image_name": "",
            # 默认值
            "image_action": "detect",
            "click_mode": "single",
            "click_count": 1,
            "click_interval": 500,
            "swipe_direction": "top_to_bottom",
            "swipe_speed": 400
        }

        if roi_type == "image":
            config["image_action"] = self.image_action_combo.currentData()
            config["image_name"] = self.image_name_input.text().strip()
        else:
            # 区域类型，根据动作选择获取配置
            action = self.action_combo.currentData()
            config["action"] = action

            if action == "click":
                config["click_mode"] = self.click_mode_combo.currentData()
                config["click_count"] = self.click_count_spin.value()
                config["click_interval"] = self.click_interval_spin.value()
            elif action == "swipe":
                config["swipe_direction"] = self.swipe_direction_combo.currentData()
                config["swipe_speed"] = self.swipe_speed_spin.value()
            elif action == "ocr":
                # OCR无额外配置
                pass

        return config


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("安卓脚本切图工具 v3.0")
        self.resize(1400, 900)

        # 初始化组件
        self.screenshot_mgr = ScreenshotManager()
        self.crop_engine = CropEngine()
        self.export_mgr = ExportManager()
        self.auto_detector = AutoDetector()
        self.smart_segmenter = SmartSegmenter()
        self.superpixel_segmenter = SuperpixelSegmenter()
        self.superpixel_merge = None

        # 切图模式: "superpixel" | "auto_detect" | "manual"
        self.crop_mode = "manual"
        self.superpixel_generated = False  # 是否已生成超像素
        self.superpixel_mode = False  # 超像素显示模式

        # 临时选择状态（用于Ctrl模式）
        self.temp_selection = {
            'regions': [],  # 超像素合并时选中的区域
            'roi': None,    # 自动检测时选中的ROI
        }

        # 待导出切图列表
        self.pending_crops = []

        # 当前状态
        self.current_image_path = ""
        self.current_folder = ""
        self.image_files = []
        self.current_image_index = -1

        # 输出目录
        self.output_dir = os.path.join(os.getcwd(), "res_output")
        os.makedirs(self.output_dir, exist_ok=True)
        self.crop_engine.set_output_dir(self.output_dir)
        self.export_mgr.output_dir = self.output_dir

        self.init_ui()
        self.init_menu()
        self.init_toolbar()
        self.init_shortcuts()
        self.init_statusbar()

        # 连接信号
        self.connect_canvas_signals()

        # 初始化默认模式（确保画布状态一致）
        self.set_crop_mode("manual")

    def init_ui(self):
        """初始化UI"""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 左侧面板
        left_panel = self.create_left_panel()
        main_layout.addWidget(left_panel, 0)

        # 中间画布区域（带滚动条和悬浮工具条）
        canvas_container = QWidget()
        canvas_container.setLayout(QVBoxLayout())
        canvas_container.layout().setContentsMargins(0, 0, 0, 0)
        canvas_container.layout().setSpacing(0)

        self.canvas = ImageCanvas()
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.canvas)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #1e1e1e; }")
        canvas_container.layout().addWidget(self.scroll_area)

        # 悬浮工具条（固定左上角）
        self.create_floating_toolbar(canvas_container)

        main_layout.addWidget(canvas_container, 1)

        # 右侧面板
        right_panel = self.create_right_panel()
        main_layout.addWidget(right_panel, 0)

    def create_left_panel(self) -> QWidget:
        """创建左侧面板 - 截图和选图"""
        panel = QFrame()
        panel.setFixedWidth(240)
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        # === 截图功能 ===
        shot_group = QGroupBox("截图")
        shot_layout = QVBoxLayout()

        btn_ld = QPushButton("雷电模拟器截图")
        btn_ld.setStyleSheet("background-color: #6f42c1; color: white;")
        btn_ld.clicked.connect(self.capture_ld_player)
        shot_layout.addWidget(btn_ld)

        btn_pc = QPushButton("桌面全屏截图")
        btn_pc.clicked.connect(self.capture_pc_screen)
        shot_layout.addWidget(btn_pc)

        self.label_adb_status = QLabel("ADB: 检测中...")
        shot_layout.addWidget(self.label_adb_status)

        shot_group.setLayout(shot_layout)
        layout.addWidget(shot_group)

        # === 图片列表（放在底部，占据剩余高度）===
        list_group = QGroupBox("图片列表")
        list_layout = QVBoxLayout()

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_image_selected)
        list_layout.addWidget(self.list_widget)

        nav_layout = QHBoxLayout()
        btn_prev = QPushButton("上一张")
        btn_prev.clicked.connect(self.prev_image)
        nav_layout.addWidget(btn_prev)

        btn_next = QPushButton("下一张")
        btn_next.clicked.connect(self.next_image)
        nav_layout.addWidget(btn_next)

        list_layout.addLayout(nav_layout)

        self.label_image_count = QLabel("共 0 张")
        list_layout.addWidget(self.label_image_count)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group, 1)  # stretch factor = 1，占据剩余空间

        return panel

    def create_right_panel(self) -> QWidget:
        """创建右侧面板 - 已切图列表和ROI预览"""
        panel = QFrame()
        panel.setFixedWidth(260)
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        # === ROI坐标预览 ===
        preview_group = QGroupBox("ROI坐标预览")
        preview_layout = QFormLayout()

        self.label_preview_name = QLabel("无")
        preview_layout.addRow("名称:", self.label_preview_name)

        self.label_preview_pos = QLabel("-")
        preview_layout.addRow("位置:", self.label_preview_pos)

        self.label_preview_size = QLabel("-")
        preview_layout.addRow("尺寸:", self.label_preview_size)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # === 输出设置 ===
        output_group = QGroupBox("输出设置")
        output_layout = QFormLayout()

        self.prefix_input = QLineEdit("target_")
        output_layout.addRow("前缀:", self.prefix_input)

        btn_change = QPushButton("更改目录")
        btn_change.clicked.connect(self.change_output_dir)
        output_layout.addRow(btn_change)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # 鼠标位置显示
        self.label_mouse_pos = QLabel("X: 0, Y: 0")
        self.label_mouse_pos.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.label_mouse_pos)

        # === 已切图列表（放在底部，占据剩余高度）===
        crop_group = QGroupBox("已切图列表")
        crop_layout = QVBoxLayout()

        self.crop_list_widget = QListWidget()
        self.crop_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.crop_list_widget.customContextMenuRequested.connect(self.on_crop_list_menu)
        self.crop_list_widget.itemClicked.connect(self.on_crop_item_selected)
        crop_layout.addWidget(self.crop_list_widget)

        # 列表操作按钮
        btn_layout = QHBoxLayout()
        btn_export = QPushButton("导出")
        btn_export.setStyleSheet("background-color: #28a745; color: white;")
        btn_export.clicked.connect(self.export_all_crops)
        btn_layout.addWidget(btn_export)

        btn_clear = QPushButton("清空")
        btn_clear.clicked.connect(self.clear_pending_crops)
        btn_layout.addWidget(btn_clear)

        crop_layout.addLayout(btn_layout)
        crop_group.setLayout(crop_layout)
        layout.addWidget(crop_group, 1)  # stretch factor = 1，占据剩余空间

        return panel

    def create_floating_toolbar(self, parent):
        """创建悬浮工具条（默认可拖动，默认右上角）"""
        # 创建浮动窗口，作为父容器的子窗口
        self.floating_toolbar = QWidget(parent)
        self.floating_toolbar.setFixedSize(340, 42)
        # 默认放到右上角（预留滚动条空间）
        toolbar_x = max(12, parent.width() - 340 - 20)
        self.floating_toolbar.move(toolbar_x, 12)
        # 启用鼠标跟踪，支持拖动
        self.floating_toolbar.setMouseTracking(True)
        self.floating_toolbar.mousePressEvent = self._toolbar_mouse_press
        self.floating_toolbar.mouseMoveEvent = self._toolbar_mouse_move
        self.floating_toolbar.mouseReleaseEvent = self._toolbar_mouse_release
        self._toolbar_drag_pos = None
        # 保持为普通子窗口，不使用Qt.Tool，这样不会跑到主窗口外面
        self.floating_toolbar.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border-radius: 6px;
                border: 1px solid #444;
            }
            QComboBox {
                background-color: #3d3d3d;
                color: white;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 3px;
                min-width: 100px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #3d3d3d;
                color: white;
                selection-background-color: #007bff;
            }
            QPushButton {
                background-color: #0d6efd;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #0b5ed7;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
            QLabel {
                color: #ddd;
                background: transparent;
                border: none;
                font-size: 12px;
            }
        """)

        layout = QHBoxLayout(self.floating_toolbar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # 模式选择下拉框
        layout.addWidget(QLabel("模式:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["超像素合并", "自动识别", "手动框选"])
        self.combo_mode.setCurrentIndex(2)  # 默认手动框选
        self.combo_mode.currentIndexChanged.connect(self.on_mode_changed)
        layout.addWidget(self.combo_mode)

        # 分隔线
        line = QLabel("|")
        line.setStyleSheet("color: #666;")
        layout.addWidget(line)

        # 超像素大小选择（仅超像素模式显示）
        self.label_sp_size = QLabel("粒度:")
        layout.addWidget(self.label_sp_size)
        self.combo_sp_size = QComboBox()
        self.combo_sp_size.addItems(["小", "中", "大", "超大"])
        self.combo_sp_size.setCurrentIndex(1)
        layout.addWidget(self.combo_sp_size)

        # 重新生成按钮（仅超像素模式显示）
        self.btn_regenerate_sp = QPushButton("重新生成")
        self.btn_regenerate_sp.setFixedWidth(70)
        self.btn_regenerate_sp.clicked.connect(self.run_superpixel)
        layout.addWidget(self.btn_regenerate_sp)

        layout.addStretch()

        # 初始状态：非超像素模式隐藏相关控件
        self.update_toolbar_visibility()

    def on_mode_changed(self, index):
        """模式切换"""
        modes = ["superpixel", "auto_detect", "manual"]
        self.set_crop_mode(modes[index])
        self.update_toolbar_visibility()

    def update_toolbar_visibility(self):
        """根据当前模式更新工具条控件可见性"""
        is_superpixel = self.crop_mode == "superpixel"
        self.label_sp_size.setVisible(is_superpixel)
        self.combo_sp_size.setVisible(is_superpixel)
        self.btn_regenerate_sp.setVisible(is_superpixel)

    def _toolbar_mouse_press(self, event):
        """工具条鼠标按下 - 开始拖动"""
        if event.button() == Qt.LeftButton:
            self._toolbar_drag_pos = event.globalPos() - self.floating_toolbar.frameGeometry().topLeft()
            event.accept()

    def _toolbar_mouse_move(self, event):
        """工具条鼠标移动 - 执行拖动"""
        if event.buttons() == Qt.LeftButton and self._toolbar_drag_pos is not None:
            new_pos = event.globalPos() - self._toolbar_drag_pos
            # 限制在父容器范围内
            parent_rect = self.floating_toolbar.parent().rect()
            toolbar_rect = self.floating_toolbar.rect()
            # 确保不超出边界
            new_pos.setX(max(0, min(new_pos.x(), parent_rect.width() - toolbar_rect.width())))
            new_pos.setY(max(0, min(new_pos.y(), parent_rect.height() - toolbar_rect.height())))
            self.floating_toolbar.move(new_pos)
            event.accept()

    def _toolbar_mouse_release(self, event):
        """工具条鼠标释放 - 结束拖动"""
        if event.button() == Qt.LeftButton:
            self._toolbar_drag_pos = None
            event.accept()

    def connect_canvas_signals(self):
        """连接画布信号"""
        self.canvas.roi_created.connect(self.on_roi_created)
        self.canvas.roi_selected.connect(self.on_roi_selected)
        self.canvas.roi_modified.connect(self.on_roi_modified)
        self.canvas.roi_deleted.connect(self.on_roi_deleted)
        self.canvas.roi_copied.connect(self.on_roi_copied)
        self.canvas.mouse_moved.connect(self.on_mouse_moved)
        self.canvas.point_clicked.connect(self.on_point_clicked)
        # 三种切图模式的信号
        self.canvas.superpixel_merge_clicked.connect(self.on_superpixel_merge_click)
        self.canvas.superpixel_cancel_clicked.connect(self.on_superpixel_cancel_click)
        self.canvas.superpixel_merge_finished.connect(self.on_superpixel_merge_finish)
        self.canvas.auto_detect_clicked.connect(self.on_auto_detect_click)
        self.canvas.auto_detect_finished.connect(self.on_auto_detect_finish)
        self.canvas.statusbar_msg.connect(self.statusbar.showMessage)

    # ==================== 信号处理 ====================

    def on_mouse_moved(self, x, y):
        """鼠标移动"""
        self.label_mouse_pos.setText(f"X: {x}, Y: {y}")

    def on_point_clicked(self, x: int, y: int, continuous: bool = False):
        """点选识别 - 使用颜色连通区域检测，添加命名和待导出列表

        Args:
            x, y: 点击位置
            continuous: 是否连续模式（Ctrl按住时不显示消息）
        """
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import Qt

        pixmap = self.canvas.get_pixmap()
        if not pixmap:
            return

        # 检测是否按住Shift - 合并所有相似颜色
        modifiers = QApplication.keyboardModifiers()
        merge_all = modifiers & Qt.ShiftModifier

        mode_text = "合并相似颜色" if merge_all else "识别连通区域"
        if not continuous:
            self.statusbar.showMessage(f"正在{mode_text} ({x}, {y})...")

        try:
            roi = self.auto_detector.detect_at_point(pixmap, x, y, merge_all=merge_all)

            if roi:
                # 检查是否已存在相同位置的ROI（避免连续模式下重复添加）
                if continuous:
                    for existing in self.canvas.roi_collection:
                        if (abs(existing.x - roi.x) < 5 and
                            abs(existing.y - roi.y) < 5 and
                            abs(existing.width - roi.width) < 5 and
                            abs(existing.height - roi.height) < 5):
                            return  # 已存在，跳过

                # 弹出命名对话框
                if not continuous:
                    name, ok = QInputDialog.getText(
                        self, "命名切图", "请输入切图名称:",
                        text=f"auto_{len(self.pending_crops)+1}"
                    )
                    if ok and name:
                        roi.name = name
                    else:
                        roi.name = f"auto_{len(self.pending_crops)+1}"

                    # 自动检测模式默认是图片类型
                    roi.roi_type = "image"
                    roi.node_name = roi.name

                # 添加到画布
                idx = self.canvas.roi_collection.add(roi)
                self.canvas.roi_collection.selected_index = idx
                self.canvas.update()

                # 添加到待导出列表
                self.pending_crops.append({
                    'roi': roi,
                    'regions': None,  # 自动检测没有regions
                    'name': roi.name,
                    'type': 'auto_detect'
                })
                self.update_pending_crop_list()

                if not continuous:
                    self.statusbar.showMessage(
                        f"已{mode_text}: {roi.name} ({roi.width}x{roi.height})，已添加到待导出"
                    )
            else:
                if not continuous:
                    self.statusbar.showMessage(f"位置 ({x}, {y}) 未能识别，请尝试其他位置")

        except Exception as e:
            if not continuous:
                self.statusbar.showMessage(f"识别失败: {str(e)}")
            import traceback
            traceback.print_exc()

    def on_auto_detect_click(self, x: int, y: int):
        """自动检测模式：点击立即检测并显示预览"""
        pixmap = self.canvas.get_pixmap()
        if not pixmap:
            return

        # 显示进度提示
        self.statusbar.showMessage(f"正在检测位置 ({x}, {y})...")
        QApplication.processEvents()

        try:
            roi = self.auto_detector.detect_at_point(pixmap, x, y, merge_all=False)
            if roi:
                self.canvas.temp_roi = roi
                self.statusbar.showMessage(f"检测到区域: {roi.width}x{roi.height}, 松开Ctrl完成命名")
                self.canvas.update()
            else:
                self.statusbar.showMessage(f"位置 ({x}, {y}) 未能识别")
        except Exception as e:
            self.statusbar.showMessage(f"检测失败: {str(e)}")

    def on_auto_detect_finish(self, roi: ROI):
        """自动检测完成（Ctrl释放）：添加ROI到画布并弹出配置对话框"""
        if not roi:
            return

        # 先添加到画布
        idx = self.canvas.roi_collection.add(roi)
        self.canvas.roi_collection.selected_index = idx
        self.canvas.update()

        # 触发roi_created信号流程（弹出配置对话框）
        self.on_roi_created(roi)

    def on_roi_created(self, roi: ROI):
        """ROI创建（框选模式）- 使用新对话框配置类型和动作"""
        pixmap = self.canvas.get_pixmap()
        if not pixmap:
            return

        # 弹出ROI配置对话框
        default_name = f"roi_{len(self.pending_crops)+1}"
        dialog = ROIDialog(self, default_name=default_name)

        if dialog.exec_() != QDialog.Accepted:
            # 用户取消，删除刚创建的ROI
            # 找到并删除刚创建的ROI（通过roi_id匹配）
            for i, existing_roi in enumerate(self.canvas.roi_collection):
                if existing_roi.roi_id == roi.roi_id:
                    self.canvas.roi_collection.remove(i)
                    break
            self.canvas.update()
            # 重置画布状态（对话框期间可能丢失键盘事件）
            self._reset_canvas_state()
            return

        # 获取配置
        config = dialog.get_config()

        # 设置ROI基础属性
        roi.node_name = config["node_name"] or default_name
        roi.name = roi.node_name  # 保持兼容
        roi.roi_type = config["roi_type"]
        roi.action = config["action"]
        roi.image_name = config["image_name"]

        # 设置详细配置
        if roi.roi_type == "image":
            roi.image_action = config["image_action"]
        elif roi.roi_type == "region":
            if roi.action == "click":
                roi.click_mode = config["click_mode"]
                roi.click_count = config["click_count"]
                roi.click_interval = config["click_interval"]
            elif roi.action == "swipe":
                roi.swipe_direction = config["swipe_direction"]
                roi.swipe_speed = config["swipe_speed"]

        # 检查重名（基于node_name）
        base_name = roi.node_name
        existing_names = {c['name'] for c in self.pending_crops}
        final_name = base_name
        suffix = 1
        while final_name in existing_names:
            final_name = f"{base_name}_{suffix}"
            suffix += 1

        if final_name != base_name:
            roi.node_name = final_name
            roi.name = final_name
            self.statusbar.showMessage(f"名称已自动更改为: {final_name}")

        # 构建描述
        if roi.roi_type == "image":
            action_desc = "检测" if roi.image_action == "detect" else "检测并点击"
            type_desc = f"图片({action_desc})"
        elif roi.action == "click":
            click_desc = "单次" if roi.click_mode == "single" else f"循环({roi.click_count}次)"
            type_desc = f"点击({click_desc})"
        elif roi.action == "swipe":
            dir_map = {"top_to_bottom": "↓", "bottom_to_top": "↑", "left_to_right": "→", "right_to_left": "←"}
            type_desc = f"滑动({dir_map.get(roi.swipe_direction, '')})"
        elif roi.action == "ocr":
            type_desc = "OCR"
        else:
            type_desc = "区域(无动作)"

        # 添加到待导出列表
        self.pending_crops.append({
            'roi_id': roi.roi_id,
            'roi': roi,
            'regions': None,
            'name': roi.node_name,
            'type': roi.roi_type,
            'action': roi.action
        })
        self.update_pending_crop_list()

        self.statusbar.showMessage(
            f"已创建{type_desc}: {roi.node_name} ({roi.width}x{roi.height})"
        )

        # 更新UI
        self.update_roi_info()
        self.update_code_preview()

        # 重置画布状态（对话框期间可能丢失键盘事件，导致Ctrl状态未更新）
        self._reset_canvas_state()

    def _reset_canvas_state(self):
        """重置画布到初始状态（选择模式）"""
        self.canvas.is_drawing = False
        self.canvas.set_mode("select")
        self.canvas.setCursor(Qt.ArrowCursor)
        self.canvas.update()

    def on_roi_selected(self, index: int):
        """ROI选中"""
        self.update_roi_info()
        self.update_code_preview()

    def on_roi_modified(self, index: int):
        """ROI修改"""
        self.update_roi_info()

    def on_roi_deleted(self, index: int):
        """ROI删除 - 同步删除右边待导出列表中的对应项"""
        # 找到对应的待导出项并删除（使用roi_id关联）
        roi_to_delete = None
        if 0 <= index < len(self.canvas.roi_collection):
            roi_to_delete = self.canvas.roi_collection.get(index)

        if roi_to_delete:
            # 使用roi_id匹配，避免对象引用问题
            original_count = len(self.pending_crops)
            self.pending_crops = [crop for crop in self.pending_crops if crop.get('roi_id') != roi_to_delete.roi_id]
            if len(self.pending_crops) < original_count:
                self.update_pending_crop_list()

        self.update_roi_info()

    def on_roi_copied(self, roi: ROI):
        """ROI复制"""
        self.update_roi_info()

    def update_roi_info(self):
        """更新ROI信息显示 - 包含类型和动作"""
        selected = self.canvas.roi_collection.get_selected()
        if selected:
            # 显示节点名（优先）或旧name字段
            display_name = selected.node_name or selected.name
            self.label_preview_name.setText(display_name)

            # 显示坐标
            self.label_preview_pos.setText(f"({selected.x}, {selected.y})")

            # 显示尺寸和类型
            type_icon = "📷" if selected.roi_type == "image" else "📍"
            action_info = f"/{selected.action}" if selected.action else ""
            self.label_preview_size.setText(
                f"{selected.width} x {selected.height}  {type_icon} {selected.roi_type}{action_info}"
            )

    def update_code_preview(self):
        """更新代码预览（已移除代码预览区域，此方法保留但不执行操作）"""
        pass

    # ==================== 超像素分割 ====================

    def run_superpixel(self):
        """执行超像素分割"""
        pixmap = self.canvas.get_pixmap()
        if not pixmap:
            QMessageBox.warning(self, "错误", "请先加载图片")
            return

        # 获取区域大小设置
        region_sizes = [20, 30, 50, 80]
        region_size = region_sizes[self.combo_sp_size.currentIndex()]

        # 显示进度对话框
        progress = QProgressDialog("正在生成超像素...\n这可能需要几秒钟", None, 0, 0, self)
        progress.setWindowTitle("处理中")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        progress.show()
        QApplication.processEvents()

        self.statusbar.showMessage(f"正在生成超像素 (区域大小: {region_size}px)...")
        self.btn_regenerate_sp.setEnabled(False)
        self.btn_regenerate_sp.setText("处理中...")
        QApplication.processEvents()

        try:
            # 创建新的分割器
            self.superpixel_segmenter = SuperpixelSegmenter(region_size=region_size, ruler=10.0)
            regions = self.superpixel_segmenter.segment(pixmap)

            progress.close()

            if regions:
                # 创建合并工具
                self.superpixel_merge = SuperpixelMergeTool(self.superpixel_segmenter)

                # 生成可视化叠加图
                img = self._qpixmap_to_cv2(pixmap)
                if img is not None:
                    vis = self.superpixel_segmenter.visualize(img, alpha=0.3)
                    self.superpixel_overlay = self._cv2_to_qpixmap(vis)

                self.superpixel_mode = True
                self.superpixel_generated = True
                self.btn_regenerate_sp.setText("重新生成")

                # 同步到画布
                self.canvas.show_superpixel = True
                self.canvas.superpixel_overlay = self.superpixel_overlay
                self.canvas.superpixel_selected = set()

                self.statusbar.showMessage(f"超像素生成完成: {len(regions)} 个区域")
            else:
                QMessageBox.warning(self, "错误", "超像素分割失败")
                self.btn_regenerate_sp.setText("生成")

        except Exception as e:
            progress.close()
            QMessageBox.warning(self, "错误", f"超像素分割失败: {str(e)}")
            import traceback
            traceback.print_exc()
            self.btn_regenerate_sp.setText("生成")

        self.btn_regenerate_sp.setEnabled(True)
        self.canvas.update()

    def toggle_sp_boundary(self, state):
        """切换超像素边界显示"""
        self.superpixel_mode = (state == Qt.Checked)
        # 同步到画布
        self.canvas.show_superpixel = self.superpixel_mode
        self.canvas.superpixel_overlay = self.superpixel_overlay
        self.canvas.update()

    def on_superpixel_merge_click(self, x: int, y: int):
        """Ctrl合并模式：点击添加超像素"""
        # 添加超像素到合并列表
        region = self.superpixel_segmenter.get_region_at_point(x, y)
        if not region:
            return

        # 检查是否已选中
        if region.label in self.canvas.pending_merge_labels:
            return

        # 直接添加（放宽相邻限制）
        self._add_superpixel_to_merge(region)

    def _add_superpixel_to_merge(self, region):
        """添加超像素到合并列表并更新显示"""
        self.canvas.pending_merge_labels.add(region.label)
        self.canvas.superpixel_selected = set(self.canvas.pending_merge_labels)

        # 存储轮廓信息用于绘制
        if not hasattr(self.canvas, '_superpixel_contours'):
            self.canvas._superpixel_contours = {}
        self.canvas._superpixel_contours[region.label] = region.contour

        count = len(self.canvas.pending_merge_labels)
        self.statusbar.showMessage(f"合并模式: 已添加区域 #{region.label} (本次共{count}个)")
        self.canvas.update()

    def on_superpixel_cancel_click(self, x: int, y: int):
        """Ctrl合并模式：右键取消超像素"""
        region = self.superpixel_segmenter.get_region_at_point(x, y)
        if region and region.label in self.canvas.pending_merge_labels:
            self.canvas.pending_merge_labels.remove(region.label)
            self.canvas.superpixel_selected = set(self.canvas.pending_merge_labels)
            count = len(self.canvas.pending_merge_labels)
            self.statusbar.showMessage(f"合并模式: 已取消区域 #{region.label} (本次剩余{count}个)")
            self.canvas.update()

    def on_superpixel_merge_finish(self, labels_set):
        """Ctrl释放：合并选中的超像素生成ROI"""
        if not labels_set or len(labels_set) == 0:
            self.statusbar.showMessage("合并模式结束，未选择区域")
            self.canvas.superpixel_selected = set()
            self.canvas.update()
            return

        # 检查超像素分割器是否初始化
        if self.superpixel_segmenter is None or not hasattr(self.superpixel_segmenter, 'regions'):
            self.statusbar.showMessage("错误：超像素未初始化")
            return

        # 显示进度提示
        progress = QProgressDialog("正在合并超像素区域...", None, 0, 0, self)
        progress.setWindowTitle("处理中")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        progress.show()
        QApplication.processEvents()

        # 获取选中的区域（使用字典优化查找）
        region_map = {r.label: r for r in self.superpixel_segmenter.regions}
        regions = [region_map[label] for label in labels_set if label in region_map]

        if len(regions) < 1:
            progress.close()
            self.statusbar.showMessage("合并模式结束，未找到有效区域")
            return

        # 合并生成ROI
        roi = self.superpixel_segmenter.merge_regions(regions)
        progress.close()
        if roi:
            # 检查重名
            base_name = f"crop_{len(self.pending_crops)+1}"
            existing_names = {c['name'] for c in self.pending_crops}
            suggested_name = base_name
            suffix = 1
            while suggested_name in existing_names:
                suggested_name = f"{base_name}_{suffix}"
                suffix += 1

            # 弹出ROI配置对话框（与自动检测/手动框选统一）
            dialog = ROIDialog(self, default_name=suggested_name, roi_type="image")

            if dialog.exec_() == QDialog.Accepted:
                config = dialog.get_config()

                # 应用配置
                roi.name = config["node_name"] or suggested_name
                roi.node_name = roi.name
                roi.roi_type = config["roi_type"]
                roi.action = config["action"]
                roi.image_name = config["image_name"]

                # 设置详细配置
                if roi.roi_type == "image":
                    roi.image_action = config["image_action"]
                elif roi.roi_type == "region":
                    if roi.action == "click":
                        roi.click_mode = config["click_mode"]
                        roi.click_count = config["click_count"]
                        roi.click_interval = config["click_interval"]
                    elif roi.action == "swipe":
                        roi.swipe_direction = config["swipe_direction"]
                        roi.swipe_speed = config["swipe_speed"]

                # 添加到待导出列表
                self.pending_crops.append({
                    'roi_id': roi.roi_id,
                    'roi': roi,
                    'regions': regions,
                    'name': roi.node_name,
                    'type': roi.roi_type,
                    'action': roi.action
                })

                # 更新列表显示
                self.update_pending_crop_list()

                # 添加到画布显示
                idx = self.canvas.roi_collection.add(roi)
                self.canvas.roi_collection.selected_index = idx

                # 构建描述
                if roi.roi_type == "image":
                    action_desc = "检测" if roi.image_action == "detect" else "检测并点击"
                    type_desc = f"图片({action_desc})"
                elif roi.action == "click":
                    click_desc = "单次" if roi.click_mode == "single" else f"循环({roi.click_count}次)"
                    type_desc = f"点击({click_desc})"
                elif roi.action == "swipe":
                    dir_map = {"top_to_bottom": "↓", "bottom_to_top": "↑", "left_to_right": "→", "right_to_left": "←"}
                    type_desc = f"滑动({dir_map.get(roi.swipe_direction, '')})"
                elif roi.action == "ocr":
                    type_desc = "OCR"
                else:
                    type_desc = "区域(无动作)"

                self.statusbar.showMessage(f"已创建{type_desc}: {roi.node_name} ({roi.width}x{roi.height})")

                # 更新UI
                self.update_roi_info()
                self.update_code_preview()

                # 重置画布状态
                self._reset_canvas_state()
            else:
                # 用户取消命名
                self.statusbar.showMessage("已取消命名")
                # 重置画布状态
                self._reset_canvas_state()
        else:
            self.statusbar.showMessage("合并失败")

        # 清除选择状态
        self.canvas.superpixel_selected = set()
        self.canvas.pending_merge_labels.clear()
        self.canvas.update()

    def _is_superpixel_adjacent(self, label: int, selected_labels: set) -> bool:
        """检查超像素是否与已选区域相邻（使用8邻域）"""
        if not selected_labels:
            return True  # 第一个区域，直接允许

        labels_map = self.superpixel_segmenter.labels
        if labels_map is None:
            return False

        h, w = labels_map.shape

        # 获取目标区域的坐标
        target_coords = np.argwhere(labels_map == label)
        if len(target_coords) == 0:
            return False

        # 检查8邻域是否有已选区域
        for cy, cx in target_coords[::10]:  # 采样加速
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dy == 0 and dx == 0:
                        continue
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w:
                        neighbor_label = labels_map[ny, nx]
                        if neighbor_label in selected_labels:
                            return True

        return False

    def merge_selected_superpixels(self):
        """手动合并按钮（备用）"""
        if not self.superpixel_merge:
            QMessageBox.warning(self, "错误", "请先生成超像素")
            return

        roi = self.superpixel_merge.merge_selected()
        if roi:
            idx = self.canvas.roi_collection.add(roi)
            self.canvas.roi_collection.selected_index = idx
            self.canvas.roi_created.emit(roi)
            self.canvas.update()

            selected_count = len(self.superpixel_merge.selected_labels)
            self.statusbar.showMessage(f"已合并 {selected_count} 个区域为 ROI: {roi.name}")
        else:
            QMessageBox.information(self, "提示", "请至少选择2个区域进行合并")

    def clear_superpixel_selection(self):
        """清除超像素选择"""
        self.canvas.superpixel_selected = set()
        self.canvas.pending_merge_labels.clear()
        if hasattr(self.canvas, '_superpixel_contours'):
            self.canvas._superpixel_contours.clear()
        self.canvas.update()
        self.statusbar.showMessage("已清除选择")

    def _qpixmap_to_cv2(self, pixmap: QPixmap) -> np.ndarray:
        """QPixmap转OpenCV格式"""
        from PyQt5.QtGui import QImage

        if pixmap.isNull():
            return None

        image = pixmap.toImage()
        if image.format() != QImage.Format_RGB888:
            image = image.convertToFormat(QImage.Format_RGB888)

        width = image.width()
        height = image.height()
        ptr = image.bits()
        ptr.setsize(image.byteCount())

        arr = np.array(ptr).reshape(height, width, 3)
        arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

        return arr

    def _cv2_to_qpixmap(self, img: np.ndarray) -> QPixmap:
        """OpenCV格式转QPixmap"""
        from PyQt5.QtGui import QImage

        if len(img.shape) == 3:
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

        h, w = rgb.shape[:2]
        bytes_per_line = 3 * w
        qt_image = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        return QPixmap.fromImage(qt_image)

    def _save_superpixel_crop(self, pixmap: QPixmap, roi: ROI, regions: list = None, filename: str = None):
        """保存透明背景切图 - 支持超像素和普通ROI"""
        try:
            # 转换图片
            img = self._qpixmap_to_cv2(pixmap)
            if img is None:
                return None

            h, w = img.shape[:2]

            # 创建mask
            if regions:
                # 超像素模式：合并所有region的mask
                merged_mask = np.zeros((h, w), dtype=np.uint8)
                for region in regions:
                    if region.mask.shape == (h, w):
                        merged_mask = cv2.bitwise_or(merged_mask, region.mask)
            else:
                # 普通ROI模式：使用ROI的轮廓或矩形
                merged_mask = np.zeros((h, w), dtype=np.uint8)
                x, y, rw, rh = roi.x, roi.y, roi.width, roi.height
                # 确保在范围内
                x = max(0, x)
                y = max(0, y)
                rw = min(rw, w - x)
                rh = min(rh, h - y)
                # 填充矩形区域
                if hasattr(roi, 'contour') and roi.contour is not None:
                    # 有不规则轮廓，使用轮廓填充
                    cv2.drawContours(merged_mask, [roi.contour], -1, 255, -1)
                else:
                    # 矩形ROI
                    merged_mask[y:y+rh, x:x+rw] = 255

            # 裁剪到ROI区域
            x, y, rw, rh = roi.x, roi.y, roi.width, roi.height
            x = max(0, x)
            y = max(0, y)
            rw = min(rw, w - x)
            rh = min(rh, h - y)

            roi_img = img[y:y+rh, x:x+rw].copy()
            roi_mask = merged_mask[y:y+rh, x:x+rw].copy()

            # 创建BGRA透明图片
            bgra = np.zeros((rh, rw, 4), dtype=np.uint8)
            bgra[:, :, :3] = roi_img
            bgra[:, :, 3] = roi_mask

            # 使用传入的filename或从ROI名字生成
            if filename is None:
                # 使用node_name或name作为文件名，保留中文字符
                name = roi.node_name or roi.name
                # 移除文件名中的非法字符
                import re
                safe_name = re.sub(r'[\\/:*?"<>|]', '_', name).strip()
                if not safe_name:
                    safe_name = f"crop_{int(time.time())}"
                filename = f"{safe_name}.png"

            # 添加前缀
            prefix = self.prefix_input.text().strip()
            if prefix:
                filename = f"{prefix}{filename}"

            filepath = os.path.join(self.output_dir, filename)

            # 使用Python文件写入支持中文路径（cv2.imwrite不支持中文）
            # cv2.imencode将图像编码为内存缓冲区，然后Python写入文件
            ext = os.path.splitext(filename)[1].lower()
            if ext == '.png':
                retval, buffer = cv2.imencode('.png', bgra)
            else:
                retval, buffer = cv2.imencode('.png', bgra)  # 默认PNG

            if retval:
                with open(filepath, 'wb') as f:
                    f.write(buffer)
                print(f"[Transparent Crop] 保存: {filepath}")
                return filepath
            else:
                print(f"[Transparent Crop] 图像编码失败")
                return None

        except Exception as e:
            print(f"保存切图失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    # ==================== 待导出切图管理 ====================

    def update_pending_crop_list(self):
        """更新待导出切图列表显示 - 包含类型信息"""
        self.crop_list_widget.clear()
        for i, crop in enumerate(self.pending_crops):
            roi = crop['roi']
            # 显示类型图标
            if roi.roi_type == 'image':
                type_icon = "📷"
                type_info = "图片"
            else:
                action_icons = {'click': '🖱️', 'ocr': '📝', 'swipe': '👆', '': '📍'}
                type_icon = action_icons.get(roi.action, '📍')
                action_names = {'click': '点击', 'ocr': 'OCR', 'swipe': '滑动', '': '区域'}
                type_info = action_names.get(roi.action, '区域')

            item_text = f"{i+1}. {type_icon} {roi.node_name or roi.name} ({roi.width}x{roi.height}) [{type_info}]"
            self.crop_list_widget.addItem(item_text)

    def on_crop_list_menu(self, pos):
        """切图列表右键菜单"""
        item = self.crop_list_widget.itemAt(pos)
        if item:
            menu = QMenu()
            action_delete = QAction("删除", self)
            action_delete.triggered.connect(lambda: self.delete_pending_crop(self.crop_list_widget.row(item)))
            menu.addAction(action_delete)
            menu.exec_(self.crop_list_widget.mapToGlobal(pos))

    def delete_pending_crop(self, index: int):
        """删除待导出切图"""
        if 0 <= index < len(self.pending_crops):
            del self.pending_crops[index]
            self.update_pending_crop_list()
            self.statusbar.showMessage(f"已删除，剩余{len(self.pending_crops)}个待导出")

    def on_crop_item_selected(self, item):
        """选中已切图列表项时显示ROI坐标预览"""
        index = self.crop_list_widget.row(item)
        if 0 <= index < len(self.pending_crops):
            crop = self.pending_crops[index]
            roi = crop.get('roi')
            # 如果roi对象丢失，通过roi_id查找
            if roi is None:
                roi_id = crop.get('roi_id')
                for canvas_roi in self.canvas.roi_collection:
                    if canvas_roi.roi_id == roi_id:
                        roi = canvas_roi
                        break

            if roi:
                # 显示节点名和类型
                display_name = roi.node_name or roi.name
                self.label_preview_name.setText(display_name)
                self.label_preview_pos.setText(f"({roi.x}, {roi.y})")

                type_icon = "📷" if roi.roi_type == "image" else "📍"
                action_info = f"/{roi.action}" if roi.action else ""
                self.label_preview_size.setText(
                    f"{roi.width} x {roi.height}  {type_icon} {roi.roi_type}{action_info}"
                )

                # 在画布上选中对应的ROI（使用roi_id匹配）
                for i, canvas_roi in enumerate(self.canvas.roi_collection):
                    if canvas_roi.roi_id == roi.roi_id:
                        self.canvas.roi_collection.selected_index = i
                        self.canvas.update()
                        break

    def export_all_crops(self):
        """导出所有待导出切图 - 图片类型导出PNG，区域类型只导JSON"""
        if not self.pending_crops:
            QMessageBox.information(self, "提示", "没有待导出的切图")
            return

        # 统计需要导出的图片数量
        image_crops = [c for c in self.pending_crops
                       if c.get('roi') and c['roi'].roi_type == 'image']

        # 检查图片文件是否已存在
        prefix = self.prefix_input.text().strip()
        existing_files = []
        for crop in image_crops:
            name = crop['name']
            filename = f"{prefix}{name}.png" if prefix else f"{name}.png"
            filepath = os.path.join(self.output_dir, filename)
            if os.path.exists(filepath):
                existing_files.append(filename)

        # 如果有已存在的文件，询问用户
        if existing_files:
            msg = f"以下 {len(existing_files)} 个文件已存在，是否覆盖？\n"
            msg += "\n".join(existing_files[:5])  # 最多显示5个
            if len(existing_files) > 5:
                msg += f"\n... 等共 {len(existing_files)} 个文件"
            reply = QMessageBox.question(self, "确认覆盖", msg,
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return

        # 显示进度
        total_items = len(self.pending_crops)
        progress = QProgressDialog("正在导出...", None, 0, total_items, self)
        progress.setWindowTitle("导出进度")
        progress.setWindowModality(Qt.WindowModal)
        progress.show()

        pixmap = self.canvas.get_pixmap()
        png_exported = 0  # 图片导出计数
        region_count = 0  # 区域计数
        failed_items = []

        for i, crop in enumerate(self.pending_crops):
            progress.setValue(i)
            QApplication.processEvents()

            roi = crop.get('roi')
            # 如果roi对象丢失，通过roi_id查找
            if roi is None:
                roi_id = crop.get('roi_id')
                for canvas_roi in self.canvas.roi_collection:
                    if canvas_roi.roi_id == roi_id:
                        roi = canvas_roi
                        break

            if roi is None:
                failed_items.append(f"{crop.get('name', 'unknown')} (ROI不存在)")
                continue

            # 根据类型决定导出方式
            if roi.roi_type == 'image':
                # 图片类型：导出PNG
                regions = crop['regions']
                # 使用roi.node_name作为文件名（支持中文）
                name = roi.node_name or roi.name
                filename = f"{name}.png"
                filepath = self._save_superpixel_crop(pixmap, roi, regions, filename)
                if filepath:
                    png_exported += 1
                    crop['exported'] = True
                else:
                    failed_items.append(name)
            else:
                # 区域类型：只计数，不导PNG
                region_count += 1
                crop['exported'] = True

        progress.setValue(total_items)

        # 导出ROI坐标JSON（包含图片和区域）
        json_exported = False
        if png_exported > 0 or region_count > 0:
            try:
                # 构建ROI集合用于导出JSON
                from ..models.roi import ROICollection
                export_collection = ROICollection()
                for crop in self.pending_crops:
                    roi = crop.get('roi')
                    if roi is None:
                        roi_id = crop.get('roi_id')
                        for canvas_roi in self.canvas.roi_collection:
                            if canvas_roi.roi_id == roi_id:
                                roi = canvas_roi
                                break
                    if roi:
                        export_collection.add(roi)

                if len(export_collection) > 0:
                    json_path = self.export_mgr.export_json(
                        export_collection,
                        source_info={
                            "image": os.path.basename(self.current_image_path) if self.current_image_path else "unknown",
                            "export_count": png_exported + region_count
                        }
                    )
                    json_exported = True
            except Exception as e:
                print(f"导出JSON失败: {e}")

        # 导出完成后不清空列表，让用户确认后再手动清空
        self.update_pending_crop_list()

        # 显示结果
        total_exported = png_exported + region_count

        if failed_items:
            msg = f"成功导出 {total_exported}/{len(self.pending_crops)} 个ROI\n"
            msg += f"  - 图片(PNG): {png_exported}个\n"
            msg += f"  - 区域(JSON): {region_count}个\n"
            msg += f"失败 {len(failed_items)} 个:\n" + "\n".join(failed_items[:5])
            QMessageBox.warning(self, "导出完成（部分失败）", msg)
        else:
            msg = f"成功导出 {total_exported} 个ROI到\n{self.output_dir}\n\n"
            msg += f"📷 图片切图: {png_exported}个\n"
            msg += f"📍 功能区域: {region_count}个"
            if json_exported:
                msg += "\n\n同时导出了 roi_data_*.json 坐标文件"
            QMessageBox.information(self, "导出完成", msg)

        status_msg = f"已导出 {png_exported}个图片"
        if region_count > 0:
            status_msg += f", {region_count}个区域"
        if json_exported:
            status_msg += " 和JSON坐标"
        self.statusbar.showMessage(status_msg + "，列表保留")

    def clear_pending_crops(self):
        """清空待导出列表"""
        if not self.pending_crops:
            return

        reply = QMessageBox.question(self, "确认", f"确定要清空 {len(self.pending_crops)} 个待导出切图吗?")
        if reply == QMessageBox.Yes:
            self.pending_crops.clear()
            self.update_pending_crop_list()
            self.statusbar.showMessage("已清空待导出列表")

    # ==================== 模式切换 ====================

    def set_crop_mode(self, crop_mode: str):
        """切换切图模式: superpixel | auto_detect | manual"""
        self.crop_mode = crop_mode
        self.canvas.crop_mode = crop_mode

        # 同步下拉框（如果不是从下拉框触发的）
        mode_map = {"superpixel": 0, "auto_detect": 1, "manual": 2}
        if hasattr(self, 'combo_mode') and self.combo_mode.currentIndex() != mode_map.get(crop_mode, 2):
            self.combo_mode.setCurrentIndex(mode_map.get(crop_mode, 2))

        # 重置画布状态
        self.canvas.set_mode("select")
        self.canvas.setCursor(Qt.ArrowCursor)

        # 启动Ctrl状态检测定时器（100ms）
        self.canvas.start_ctrl_timer()

        if crop_mode == "superpixel":
            self.canvas.show_superpixel = True
            self.statusbar.showMessage("超像素合并模式: 按住Ctrl点击合并，松开完成命名")
            # 自动生成超像素（如果图片已加载）
            if self.canvas.get_pixmap() and not self.superpixel_generated:
                self.run_superpixel()
        elif crop_mode == "auto_detect":
            self.canvas.show_superpixel = False
            self.statusbar.showMessage("自动检测模式: 按住Ctrl点击检测，松开完成命名")
        elif crop_mode == "manual":
            self.canvas.show_superpixel = False
            self.statusbar.showMessage("手动框选模式: 按住Ctrl拖动框选，松开完成")

        # 更新工具条可见性
        if hasattr(self, 'update_toolbar_visibility'):
            self.update_toolbar_visibility()

        self.canvas.update()

    def set_mode(self, mode: str):
        """切换选择/框画模式"""
        self.canvas.set_mode(mode)

    # ==================== 文件操作 ====================

    def open_folder_dialog(self):
        """打开文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹", self.current_folder)
        if folder:
            self.load_folder(folder)

    def load_folder(self, folder_path: str):
        """加载文件夹"""
        self.current_folder = folder_path

        # 获取图片文件
        image_exts = ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp']
        self.image_files = []

        try:
            for filename in sorted(os.listdir(folder_path)):
                ext = os.path.splitext(filename)[1].lower()
                if ext in image_exts:
                    self.image_files.append(os.path.join(folder_path, filename))
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法读取文件夹: {str(e)}")
            return

        # 更新列表
        self.list_widget.clear()
        for img_path in self.image_files:
            item = QListWidgetItem(os.path.basename(img_path))
            item.setData(Qt.UserRole, img_path)
            item.setToolTip(img_path)
            self.list_widget.addItem(item)

        self.label_image_count.setText(f"共 {len(self.image_files)} 张")
        self.statusbar.showMessage(f"已加载文件夹: {folder_path}")

        # 加载第一张
        if self.image_files:
            self.load_image_by_index(0)

    def on_image_selected(self, item):
        """图片列表选择"""
        img_path = item.data(Qt.UserRole)
        self.load_image_from_path(img_path)
        self.current_image_index = self.list_widget.currentRow()

    def load_image_by_index(self, index: int):
        """通过索引加载图片"""
        if 0 <= index < len(self.image_files):
            self.list_widget.setCurrentRow(index)
            self.load_image_from_path(self.image_files[index])
            self.current_image_index = index

    def prev_image(self):
        """上一张"""
        if self.current_image_index > 0:
            self.load_image_by_index(self.current_image_index - 1)

    def next_image(self):
        """下一张"""
        if self.current_image_index < len(self.image_files) - 1:
            self.load_image_by_index(self.current_image_index + 1)

    def load_image_dialog(self):
        """加载单张图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        )
        if file_path:
            self.load_image_from_path(file_path)

    def load_image_from_path(self, file_path: str):
        """从路径加载图片"""
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            QMessageBox.warning(self, "错误", "无法加载图片")
            return

        self.canvas.set_pixmap(pixmap)
        self.current_image_path = file_path

        # 自动设置前缀
        basename = os.path.splitext(os.path.basename(file_path))[0]
        self.prefix_input.setText(f"{basename}_")

        self.statusbar.showMessage(f"已加载: {file_path} ({pixmap.width()}x{pixmap.height()})")

        # 更新ADB状态显示
        self.update_adb_status()

    def paste_image(self):
        """从剪贴板粘贴"""
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()

        if mime_data.hasImage():
            pixmap = QPixmap(mime_data.imageData())
            self.canvas.set_pixmap(pixmap)
            self.current_image_path = "clipboard"
            self.prefix_input.setText("clipboard_")
            self.statusbar.showMessage("已从剪贴板加载图片")
        else:
            QMessageBox.information(self, "提示", "剪贴板中没有图片")

    # ==================== 截图功能 ====================

    def update_adb_status(self):
        """更新ADB状态显示"""
        info = self.screenshot_mgr.get_adb_info()
        if info['adb_available']:
            self.label_adb_status.setText(f"ADB: 可用 ({len(info['devices'])}设备)")
            self.label_adb_status.setStyleSheet("color: #28a745;")
        else:
            self.label_adb_status.setText("ADB: 不可用")
            self.label_adb_status.setStyleSheet("color: #dc3545;")

    def capture_ld_player(self):
        """截图雷电模拟器"""
        try:
            self.statusbar.showMessage("正在连接雷电模拟器...")
            QApplication.processEvents()  # 更新UI

            pixmap = self.screenshot_mgr.capture_ld_player(0)

            if pixmap and not pixmap.isNull():
                self.canvas.set_pixmap(pixmap)
                self.current_image_path = "ld_player_screenshot"
                self.prefix_input.setText("ld_")
                self.statusbar.showMessage(f"已从雷电模拟器截图 ({pixmap.width()}x{pixmap.height()})")
                self.update_adb_status()
            else:
                QMessageBox.warning(
                    self, "截图失败",
                    "无法从雷电模拟器截图。\n\n请检查:\n1. 雷电模拟器是否已启动\n2. ADB调试是否开启"
                )
        except Exception as e:
            QMessageBox.critical(self, "截图错误", f"截图过程出错:\n{str(e)}")
            self.statusbar.showMessage(f"截图失败: {str(e)}")

    def capture_pc_screen(self):
        """桌面全屏截图"""
        try:
            pixmap = self.screenshot_mgr.capture_pc_screen()

            if pixmap and not pixmap.isNull():
                self.canvas.set_pixmap(pixmap)
                self.current_image_path = "pc_screenshot"
                self.prefix_input.setText("screen_")
                self.statusbar.showMessage(f"已截取桌面全屏 ({pixmap.width()}x{pixmap.height()})")
            else:
                QMessageBox.warning(self, "截图失败", "无法截取PC屏幕")
        except Exception as e:
            QMessageBox.critical(self, "截图错误", f"截图过程出错:\n{str(e)}")
            self.statusbar.showMessage(f"截图失败: {str(e)}")

    # ==================== ROI操作 ====================

    def undo_last_roi(self):
        """撤销最后一个ROI"""
        if self.canvas.undo_last_roi():
            self.statusbar.showMessage("已撤销最后一个ROI")
        else:
            QMessageBox.information(self, "提示", "没有可撤销的ROI")

    def delete_selected_roi(self):
        """删除选中ROI"""
        if self.canvas.delete_selected_roi():
            self.statusbar.showMessage("已删除选中ROI")
        else:
            QMessageBox.information(self, "提示", "请先选中一个ROI")

    def clear_all_rois(self):
        """清空所有ROI"""
        if len(self.canvas.roi_collection) == 0:
            return

        reply = QMessageBox.question(
            self, "确认",
            f"确定要删除所有 {len(self.canvas.roi_collection)} 个ROI吗?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.canvas.clear_all_rois()
            self.update_roi_info()
            self.statusbar.showMessage("已清空所有ROI")

    def change_output_dir(self):
        """更改输出目录"""
        folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹", self.output_dir)
        if folder:
            self.output_dir = folder
            self.crop_engine.set_output_dir(folder)
            self.export_mgr.output_dir = folder
            os.makedirs(folder, exist_ok=True)
            self.statusbar.showMessage(f"输出目录已更改: {folder}")

    # ==================== 导出 ====================

    def export_all_data(self):
        """导出所有数据"""
        collection = self.canvas.roi_collection

        if len(collection) == 0:
            QMessageBox.information(self, "提示", "没有ROI可导出")
            return

        # 询问导出模式
        from PyQt5.QtWidgets import QCheckBox, QDialog, QVBoxLayout, QDialogButtonBox, QLabel
        dialog = QDialog(self)
        dialog.setWindowTitle("导出选项")
        dialog.setMinimumWidth(300)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"即将导出 {len(collection)} 个ROI\n选择要导出的内容:"))

        # 复选框
        cb_images = QCheckBox("切图文件 (PNG)")
        cb_images.setChecked(True)
        cb_images.setEnabled(False)  # 必须导出切图
        layout.addWidget(cb_images)

        cb_json = QCheckBox("ROI数据 (JSON)")
        cb_json.setChecked(True)
        layout.addWidget(cb_json)

        cb_autojs = QCheckBox("Auto.js脚本")
        cb_autojs.setChecked(False)
        layout.addWidget(cb_autojs)

        cb_python = QCheckBox("Python脚本")
        cb_python.setChecked(False)
        layout.addWidget(cb_python)

        # 按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        if dialog.exec_() != QDialog.Accepted:
            return

        # 准备源信息
        source_info = {}
        pixmap = self.canvas.get_pixmap()
        if not pixmap:
            QMessageBox.warning(self, "错误", "没有图片可导出")
            return

        source_info = {
            "filename": os.path.basename(self.current_image_path) if self.current_image_path else "unknown",
            "width": pixmap.width(),
            "height": pixmap.height()
        }

        # 先执行切图
        prefix = self.prefix_input.text().strip()
        self.statusbar.showMessage("正在切图...")
        crop_results = self.crop_engine.crop_all(pixmap, collection.rois, prefix)

        # 根据选择导出
        results = {}
        if cb_json.isChecked():
            try:
                results['json'] = self.export_mgr.export_json(collection, source_info)
            except Exception as e:
                print(f"导出JSON失败: {e}")

        if cb_autojs.isChecked():
            try:
                results['autojs'] = self.export_mgr.export_autojs(collection, source_info)
            except Exception as e:
                print(f"导出Auto.js失败: {e}")

        if cb_python.isChecked():
            try:
                results['python'] = self.export_mgr.export_python(collection, source_info)
            except Exception as e:
                print(f"导出Python失败: {e}")

        # 显示结果
        msg = f"导出完成!\n\n已生成 {len(crop_results)} 个切图文件\n"
        if results:
            msg += "\n附加文件:\n"
            for fmt, path in results.items():
                msg += f"[{fmt.upper()}] {os.path.basename(path)}\n"

        msg += f"\n保存位置:\n{self.output_dir}"

        QMessageBox.information(self, "导出成功", msg)
        self.statusbar.showMessage(f"已导出 {len(crop_results)} 个切图{f'和{len(results)}个数据文件' if results else ''}到 {self.output_dir}")

    # ==================== 菜单和工具栏 ====================

    def init_menu(self):
        """初始化菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")

        action_open = QAction("打开文件夹", self)
        action_open.setShortcut(QKeySequence.Open)
        action_open.triggered.connect(self.open_folder_dialog)
        file_menu.addAction(action_open)

        action_load = QAction("加载图片", self)
        action_load.setShortcut("Ctrl+L")
        action_load.triggered.connect(self.load_image_dialog)
        file_menu.addAction(action_load)

        action_paste = QAction("从剪贴板粘贴", self)
        action_paste.setShortcut(QKeySequence.Paste)
        action_paste.triggered.connect(self.paste_image)
        file_menu.addAction(action_paste)

        file_menu.addSeparator()

        action_exit = QAction("退出", self)
        action_exit.setShortcut("Ctrl+Q")
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

        # 编辑菜单
        edit_menu = menubar.addMenu("编辑(&E)")

        action_undo = QAction("撤销", self)
        action_undo.setShortcut("Ctrl+Z")
        action_undo.triggered.connect(self.undo_last_roi)
        edit_menu.addAction(action_undo)

        action_delete = QAction("删除ROI", self)
        action_delete.setShortcut(QKeySequence.Delete)
        action_delete.triggered.connect(self.delete_selected_roi)
        edit_menu.addAction(action_delete)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")

        action_about = QAction("关于", self)
        action_about.triggered.connect(self.show_about)
        help_menu.addAction(action_about)

    def init_toolbar(self):
        """初始化工具栏"""
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        toolbar.addAction("打开", self.open_folder_dialog)
        toolbar.addAction("截图", self.capture_ld_player)
        toolbar.addSeparator()
        toolbar.addAction("撤销", self.undo_last_roi)
        toolbar.addAction("导出", self.export_all_data)

    def init_shortcuts(self):
        """初始化快捷键"""
        # 方向键切换图片
        shortcut_left = QShortcut(QKeySequence("Left"), self)
        shortcut_left.activated.connect(self.prev_image)

        shortcut_right = QShortcut(QKeySequence("Right"), self)
        shortcut_right.activated.connect(self.next_image)

    def init_statusbar(self):
        """初始化状态栏"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("就绪 - 请加载图片或截图")

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于",
            "<h2>安卓脚本切图工具 v3.0</h2>"
            "<p>专为安卓游戏脚本开发设计的切图工具</p>"
            "<p>功能：截图 → 框选ROI → 自动生成切图和代码</p>"
            "<hr>"
            "<p><b>快捷键：</b></p>"
            "<ul>"
            "<li>Ctrl+O - 打开文件夹</li>"
            "<li>Ctrl+V - 粘贴图片</li>"
            "<li>Ctrl+Z - 撤销</li>"
            "<li>Delete - 删除ROI</li>"
            "<li>方向键 - 切换图片/微调位置</li>"
            "</ul>"
        )
