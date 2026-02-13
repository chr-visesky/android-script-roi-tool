# -*- coding: utf-8 -*-
"""
图像画布组件
支持：框选ROI、拖动、调整大小、删除、坐标显示
三种模式：manual(手动框选)、superpixel(超像素合并)、auto_detect(自动检测)

交互矩阵：
┌─────────────┬──────────┬─────────────┬────────────────────┬──────────────┐
│    模式     │ Ctrl状态 │    光标     │      左键操作      │   右键操作   │
├─────────────┼──────────┼─────────────┼────────────────────┼──────────────┤
│ 手动框选    │ 松开     │ ArrowCursor │ 选择/拖拽/调整ROI  │ 菜单         │
│             │ 按住     │ CrossCursor │ 拖拽框选新ROI      │ 菜单         │
├─────────────┼──────────┼─────────────┼────────────────────┼──────────────┤
│ 超像素合并  │ 松开     │ ArrowCursor │ 选择/拖拽/调整ROI  │ 菜单         │
│             │ 按住     │ CrossCursor │ 点击添加区域       │ 点击取消区域 │
├─────────────┼──────────┼─────────────┼────────────────────┼──────────────┤
│ 自动检测    │ 松开     │ ArrowCursor │ 选择/拖拽/调整ROI  │ 菜单         │
│             │ 按住     │ CrossCursor │ 点击位置检测       │ 取消检测预览 │
└─────────────┴──────────┴─────────────┴────────────────────┴──────────────┘
"""

from PyQt5.QtWidgets import QWidget, QMenu, QAction, QMessageBox, QInputDialog, QApplication
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QPolygon, QPainter, QPen, QColor, QBrush, QFont, QPixmap, QCursor
from ..models.roi import ROI, ROICollection


class ImageCanvas(QWidget):
    """图像画布 - 安卓脚本切图工具"""

    # 信号定义
    roi_created = pyqtSignal(object)
    roi_selected = pyqtSignal(int)
    roi_modified = pyqtSignal(int)
    roi_deleted = pyqtSignal(int)
    roi_copied = pyqtSignal(object)
    mouse_moved = pyqtSignal(int, int)
    point_clicked = pyqtSignal(int, int, bool)  # x, y, continuous
    superpixel_merge_clicked = pyqtSignal(int, int)
    superpixel_cancel_clicked = pyqtSignal(int, int)
    superpixel_merge_finished = pyqtSignal(object)
    auto_detect_clicked = pyqtSignal(int, int)
    auto_detect_finished = pyqtSignal(object)
    statusbar_msg = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # ROI管理
        self.roi_collection = ROICollection()

        # 图片
        self.pixmap = None
        self.pixmap_display = None
        self.scale = 1.0
        self.offset = QPoint(0, 0)

        # 模式状态
        self.mode = "select"  # select: 选择模式, draw: 绘制模式
        self.crop_mode = "manual"  # manual, superpixel, auto_detect

        # 绘制状态
        self.is_drawing = False
        self.draw_start = QPoint()
        self.draw_current = QPoint()

        # 拖拽/调整状态
        self.is_dragging = False
        self.is_resizing = False
        self.drag_start_screen = QPoint()
        self.drag_start_img = QPoint()
        self.resize_start_pos = QPoint()
        self.resize_start_rect = QRect()
        self.resize_handle = -1

        # 超像素相关
        self.superpixel_overlay = None
        self.superpixel_selected = set()
        self.show_superpixel = False
        self.pending_merge_labels = set()

        # 自动检测相关
        self.temp_roi = None

        # Ctrl激活标志（用于auto_detect和superpixel模式）
        self._ctrl_active = False

        # 显示设置
        self.fit_to_window = False
        self.min_scale = 0.1

        # Ctrl状态检测定时器（100ms）
        self._last_ctrl_state = False
        self._ctrl_timer = QTimer(self)
        self._ctrl_timer.timeout.connect(self._check_ctrl_state)

        # 窗口设置
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e; border: 2px solid #333;")

    def start_ctrl_timer(self):
        """启动Ctrl检测定时器"""
        self._ctrl_timer.start(100)

    def stop_ctrl_timer(self):
        """停止Ctrl检测定时器"""
        self._ctrl_timer.stop()

    def _is_ctrl_pressed(self) -> bool:
        """读取键盘Ctrl状态"""
        return bool(QApplication.keyboardModifiers() & Qt.ControlModifier)

    def _check_ctrl_state(self):
        """定时检测Ctrl状态（100ms）"""
        current_ctrl = self._is_ctrl_pressed()

        if current_ctrl != self._last_ctrl_state:
            self._last_ctrl_state = current_ctrl
            self._on_ctrl_changed(current_ctrl)

    def _on_ctrl_changed(self, ctrl_pressed: bool):
        """Ctrl状态变化处理 - 严格按照交互矩阵"""
        if self.crop_mode == "manual":
            self._handle_manual_ctrl(ctrl_pressed)
        elif self.crop_mode == "superpixel":
            self._handle_superpixel_ctrl(ctrl_pressed)
        elif self.crop_mode == "auto_detect":
            self._handle_auto_detect_ctrl(ctrl_pressed)

    def _handle_manual_ctrl(self, ctrl_pressed: bool):
        """手动框选模式Ctrl处理"""
        if ctrl_pressed:
            # 按住Ctrl - 进入框选模式
            if self.mode != "draw":
                self.set_mode("draw")
            self.setCursor(Qt.CrossCursor)
            self.statusbar_msg.emit("框选模式: 拖动创建ROI，松开鼠标完成")
        else:
            # 松开Ctrl - 如果不在绘制中，回到选择模式
            if self.mode == "draw" and not self.is_drawing:
                self.set_mode("select")
                self.setCursor(Qt.ArrowCursor)
                self.statusbar_msg.emit("选择模式: 点击选中ROI，拖拽移动，手柄调整大小")
        self.update()

    def _handle_superpixel_ctrl(self, ctrl_pressed: bool):
        """超像素合并模式Ctrl处理"""
        self._ctrl_active = ctrl_pressed
        if ctrl_pressed:
            # 按住Ctrl - 进入合并模式
            self.setCursor(Qt.CrossCursor)
            self.statusbar_msg.emit("合并模式: 左键添加区域，右键取消，松开Ctrl完成")
        else:
            # 松开Ctrl - 触发完成
            self.setCursor(Qt.ArrowCursor)
            self.statusbar_msg.emit("选择模式")
            if self.pending_merge_labels:
                self.superpixel_merge_finished.emit(self.pending_merge_labels)
        self.update()

    def _handle_auto_detect_ctrl(self, ctrl_pressed: bool):
        """自动检测模式Ctrl处理"""
        self._ctrl_active = ctrl_pressed
        if ctrl_pressed:
            # 按住Ctrl - 进入检测模式
            self.setCursor(Qt.CrossCursor)
            self.statusbar_msg.emit("检测模式: 左键点击检测，右键取消，松开Ctrl完成")
        else:
            # 松开Ctrl - 触发完成
            self.setCursor(Qt.ArrowCursor)
            self.statusbar_msg.emit("选择模式")
            if self.temp_roi:
                self.auto_detect_finished.emit(self.temp_roi)
                self.temp_roi = None
        self.update()

    def set_pixmap(self, pixmap: QPixmap):
        """设置图片"""
        self.pixmap = pixmap
        self.roi_collection.clear()
        self._update_display()
        self.update()

    def get_pixmap(self) -> QPixmap:
        """获取当前图片"""
        return self.pixmap

    def set_mode(self, mode: str):
        """设置模式: select/draw"""
        self.mode = mode
        if mode == "draw":
            self.roi_collection.selected_index = -1
            self.roi_selected.emit(-1)
        self.update()

    def _update_display(self):
        """更新显示（缩放计算）"""
        if not self.pixmap:
            return

        if self.fit_to_window:
            # 适应窗口模式
            widget_w = self.width()
            widget_h = self.height()
            img_w = self.pixmap.width()
            img_h = self.pixmap.height()

            scale_w = widget_w / img_w
            scale_h = widget_h / img_h
            self.scale = max(self.min_scale, min(scale_w, scale_h))

            self.pixmap_display = self.pixmap.scaled(
                int(img_w * self.scale), int(img_h * self.scale),
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.offset = QPoint(0, 0)
            self.setMinimumSize(200, 150)
        else:
            # 1:1显示模式
            self.scale = 1.0
            self.pixmap_display = self.pixmap
            self.setFixedSize(self.pixmap.width(), self.pixmap.height())

    def toggle_fit_mode(self):
        """切换适应窗口/1:1显示"""
        self.fit_to_window = not self.fit_to_window
        self._update_display()
        self.update()
        return self.fit_to_window

    def resizeEvent(self, event):
        """窗口大小改变"""
        super().resizeEvent(event)
        self._update_display()

    # ==================== 鼠标事件 ====================

    def mousePressEvent(self, event):
        """鼠标按下 - 根据当前模式处理"""
        if not self.pixmap:
            return

        img_pos = self._screen_to_image(event.pos())
        screen_pos = event.pos()

        if event.button() == Qt.LeftButton:
            # 根据当前模式处理
            if self.crop_mode == "manual" and self.mode == "draw":
                # 手动框选模式的绘制模式
                self.is_drawing = True
                self.draw_start = img_pos
                self.draw_current = img_pos
                self.update()

            elif self.crop_mode == "superpixel" and self._ctrl_active:
                # 超像素模式 - 只有Ctrl按下时才触发
                self.superpixel_merge_clicked.emit(img_pos.x(), img_pos.y())

            elif self.crop_mode == "auto_detect" and self._ctrl_active:
                # 自动检测模式 - 只有Ctrl按下时才触发
                self.auto_detect_clicked.emit(img_pos.x(), img_pos.y())

            else:
                # 选择模式 - 处理ROI选择/拖拽/调整
                self._handle_select_mode_press(screen_pos, img_pos)

        elif event.button() == Qt.RightButton:
            # 右键处理
            if self.crop_mode == "superpixel" and self._ctrl_active:
                # 超像素模式 - 只有Ctrl按下时才触发取消
                self.superpixel_cancel_clicked.emit(img_pos.x(), img_pos.y())
            elif self.crop_mode == "auto_detect" and self._ctrl_active and self.temp_roi:
                # 自动检测模式 - 只有Ctrl按下时才触发取消
                self.temp_roi = None
                self.statusbar_msg.emit("已取消检测")
                self.update()
            elif self.crop_mode in ("manual", "superpixel", "auto_detect") and not self._ctrl_active:
                # Ctrl松开时显示右键菜单
                self._show_context_menu(event.pos())

    def _handle_select_mode_press(self, screen_pos: QPoint, img_pos: QPoint):
        """选择模式的鼠标按下处理"""
        # 1. 检查是否点击了调整手柄
        selected_idx = self.roi_collection.selected_index
        if selected_idx >= 0:
            handle = self._get_resize_handle_at(screen_pos)
            if handle >= 0:
                self.is_resizing = True
                self.resize_handle = handle
                self.resize_start_pos = screen_pos
                roi = self.roi_collection.get_selected()
                self.resize_start_rect = QRect(roi.rect)
                return

        # 2. 检查是否点击了ROI内部
        idx = self._select_roi_at(img_pos)
        if idx >= 0:
            self.roi_collection.selected_index = idx
            self.roi_selected.emit(idx)
            self.is_dragging = True
            self.drag_start_screen = screen_pos
            self.drag_start_img = img_pos
            self.update()
        else:
            # 点击空白处
            self.roi_collection.selected_index = -1
            self.roi_selected.emit(-1)
            self.update()

    def mouseMoveEvent(self, event):
        """鼠标移动"""
        if not self.pixmap:
            return

        img_pos = self._screen_to_image(event.pos())
        screen_pos = event.pos()

        # 发送鼠标位置
        self.mouse_moved.emit(img_pos.x(), img_pos.y())

        # 处理绘制
        if self.is_drawing:
            self.draw_current = img_pos
            self.update()
            return

        # 处理调整大小
        if self.is_resizing:
            self._do_resize(screen_pos)
            return

        # 处理拖拽
        if self.is_dragging:
            self._do_drag(img_pos)
            return

        # 更新光标（仅选择模式）
        if self.mode == "select":
            self._update_cursor(screen_pos)

    def _do_drag(self, img_pos: QPoint):
        """执行拖拽"""
        dx = img_pos.x() - self.drag_start_img.x()
        dy = img_pos.y() - self.drag_start_img.y()

        selected_idx = self.roi_collection.selected_index
        if selected_idx >= 0:
            roi = self.roi_collection.get(selected_idx)
            new_rect = QRect(roi.rect)
            new_rect.translate(dx, dy)

            # 限制在图片范围内
            if self.pixmap:
                img_w = self.pixmap.width()
                img_h = self.pixmap.height()
                new_x = max(0, min(new_rect.x(), img_w - roi.width))
                new_y = max(0, min(new_rect.y(), img_h - roi.height))
                new_rect.moveTo(new_x, new_y)

            roi.rect = new_rect
            self.drag_start_img = img_pos
            self.roi_modified.emit(selected_idx)
            self.update()

    def mouseReleaseEvent(self, event):
        """鼠标释放"""
        if event.button() == Qt.LeftButton:
            # 完成绘制
            if self.is_drawing:
                self._finish_drawing()

            # 完成拖拽
            if self.is_dragging:
                self.is_dragging = False
                # 重新检测光标下的内容
                self._update_cursor(event.pos())

            # 完成调整
            if self.is_resizing:
                self.is_resizing = False
                self.resize_handle = -1
                self._update_cursor(event.pos())

    def _finish_drawing(self):
        """完成框选"""
        self.is_drawing = False
        rect = QRect(self.draw_start, self.draw_current).normalized()

        # 过滤太小的区域
        if rect.width() >= 5 and rect.height() >= 5:
            rect = self._constrain_rect(rect)

            roi = ROI()
            roi.rect = rect
            idx = self.roi_collection.add(roi)
            self.roi_collection.selected_index = idx

            self.roi_created.emit(roi)
            self.roi_selected.emit(idx)

            # 完成绘制后，如果Ctrl已松开，回到选择模式
            if not self._is_ctrl_pressed() and self.crop_mode == "manual":
                self.set_mode("select")
                self.setCursor(Qt.ArrowCursor)

        self.update()

    def _constrain_rect(self, rect: QRect) -> QRect:
        """限制矩形在图片范围内"""
        if not self.pixmap:
            return rect

        img_w = self.pixmap.width()
        img_h = self.pixmap.height()

        left = max(0, min(rect.left(), img_w - 5))
        top = max(0, min(rect.top(), img_h - 5))
        right = max(5, min(rect.right(), img_w))
        bottom = max(5, min(rect.bottom(), img_h))

        return QRect(left, top, right - left, bottom - top)

    def _do_resize(self, screen_pos: QPoint):
        """执行调整大小"""
        dx = int((screen_pos.x() - self.resize_start_pos.x()) / self.scale)
        dy = int((screen_pos.y() - self.resize_start_pos.y()) / self.scale)

        new_rect = QRect(self.resize_start_rect)

        # 根据手柄调整
        if self.resize_handle == 0:  # 左上
            new_rect.setLeft(new_rect.left() + dx)
            new_rect.setTop(new_rect.top() + dy)
        elif self.resize_handle == 1:  # 上中
            new_rect.setTop(new_rect.top() + dy)
        elif self.resize_handle == 2:  # 右上
            new_rect.setRight(new_rect.right() + dx)
            new_rect.setTop(new_rect.top() + dy)
        elif self.resize_handle == 3:  # 左中
            new_rect.setLeft(new_rect.left() + dx)
        elif self.resize_handle == 4:  # 右中
            new_rect.setRight(new_rect.right() + dx)
        elif self.resize_handle == 5:  # 左下
            new_rect.setLeft(new_rect.left() + dx)
            new_rect.setBottom(new_rect.bottom() + dy)
        elif self.resize_handle == 6:  # 下中
            new_rect.setBottom(new_rect.bottom() + dy)
        elif self.resize_handle == 7:  # 右下
            new_rect.setRight(new_rect.right() + dx)
            new_rect.setBottom(new_rect.bottom() + dy)

        # 限制最小尺寸和边界
        if new_rect.width() >= 5 and new_rect.height() >= 5:
            selected_idx = self.roi_collection.selected_index
            if selected_idx >= 0:
                roi = self.roi_collection.get(selected_idx)
                roi.rect = self._constrain_rect(new_rect)
                self.roi_modified.emit(selected_idx)
                self.update()

    def _screen_to_image(self, pos: QPoint) -> QPoint:
        """屏幕坐标转图片坐标"""
        x = int((pos.x() - self.offset.x()) / self.scale)
        y = int((pos.y() - self.offset.y()) / self.scale)
        return QPoint(x, y)

    def _image_to_screen(self, pos: QPoint) -> QPoint:
        """图片坐标转屏幕坐标"""
        x = int(pos.x() * self.scale + self.offset.x())
        y = int(pos.y() * self.scale + self.offset.y())
        return QPoint(x, y)

    def _select_roi_at(self, img_pos: QPoint) -> int:
        """获取点击位置的ROI索引"""
        for i in range(len(self.roi_collection) - 1, -1, -1):
            if self.roi_collection[i].contains(img_pos):
                return i
        return -1

    def _get_resize_handle_at(self, screen_pos: QPoint) -> int:
        """获取调整手柄索引"""
        selected_idx = self.roi_collection.selected_index
        if selected_idx < 0:
            return -1

        roi = self.roi_collection[selected_idx]
        screen_rect = QRect(
            self._image_to_screen(QPoint(roi.x, roi.y)),
            QSize(int(roi.width * self.scale), int(roi.height * self.scale))
        )

        handle_size = 10
        half = handle_size // 2
        half_hit = 8

        handles = [
            (screen_rect.left(), screen_rect.top()),
            (screen_rect.center().x(), screen_rect.top()),
            (screen_rect.right(), screen_rect.top()),
            (screen_rect.left(), screen_rect.center().y()),
            (screen_rect.right(), screen_rect.center().y()),
            (screen_rect.left(), screen_rect.bottom()),
            (screen_rect.center().x(), screen_rect.bottom()),
            (screen_rect.right(), screen_rect.bottom())
        ]

        for i, (hx, hy) in enumerate(handles):
            if abs(screen_pos.x() - hx) <= half_hit and abs(screen_pos.y() - hy) <= half_hit:
                return i
        return -1

    def _update_cursor(self, screen_pos: QPoint):
        """更新光标（仅选择模式）"""
        if self.mode != "select":
            return

        handle = self._get_resize_handle_at(screen_pos)
        if handle >= 0:
            cursors = [
                Qt.SizeFDiagCursor, Qt.SizeVerCursor, Qt.SizeBDiagCursor,
                Qt.SizeHorCursor, Qt.SizeHorCursor,
                Qt.SizeBDiagCursor, Qt.SizeVerCursor, Qt.SizeFDiagCursor
            ]
            self.setCursor(cursors[handle])
        else:
            img_pos = self._screen_to_image(screen_pos)
            if self._select_roi_at(img_pos) >= 0:
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

    # ==================== ROI操作 ====================

    def delete_selected_roi(self):
        """删除选中的ROI"""
        selected_idx = self.roi_collection.selected_index
        if selected_idx >= 0:
            self.roi_collection.remove(selected_idx)
            self.roi_deleted.emit(selected_idx)
            self.update()
            return True
        return False

    def copy_selected_roi(self):
        """复制选中的ROI"""
        selected = self.roi_collection.get_selected()
        if selected:
            new_roi = selected.copy()
            new_roi.translate(20, 20)
            idx = self.roi_collection.add(new_roi)
            self.roi_collection.selected_index = idx
            self.roi_copied.emit(new_roi)
            self.roi_selected.emit(idx)
            self.update()
            return True
        return False

    def undo_last_roi(self):
        """撤销最后一个ROI"""
        if len(self.roi_collection) > 0:
            last_idx = len(self.roi_collection) - 1
            self.roi_collection.remove(last_idx)
            self.roi_deleted.emit(last_idx)
            self.update()
            return True
        return False

    def clear_all_rois(self):
        """清空所有ROI"""
        self.roi_collection.clear()
        self.update()

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)

        action_copy = QAction("复制ROI (Ctrl+C)", self)
        action_copy.triggered.connect(self.copy_selected_roi)
        menu.addAction(action_copy)

        action_undo = QAction("撤销最后一个ROI (Ctrl+Z)", self)
        action_undo.triggered.connect(self.undo_last_roi)
        menu.addAction(action_undo)

        menu.addSeparator()

        action_clear = QAction("清空所有ROI", self)
        action_clear.triggered.connect(self.clear_all_rois)
        menu.addAction(action_clear)

        menu.exec_(self.mapToGlobal(pos))

    # ==================== 键盘事件 ====================

    def keyPressEvent(self, event):
        """键盘按下 - 处理快捷键（不处理Ctrl）"""
        key = event.key()
        modifiers = event.modifiers()

        # Delete - 删除选中ROI
        if key == Qt.Key_Delete:
            if self.delete_selected_roi():
                return

        # Ctrl+C - 复制ROI
        elif key == Qt.Key_C and modifiers == Qt.ControlModifier:
            if self.copy_selected_roi():
                return

        # Ctrl+Z - 撤销
        elif key == Qt.Key_Z and modifiers == Qt.ControlModifier:
            if self.undo_last_roi():
                return

        # 方向键 - 微调位置
        elif key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            roi = self.roi_collection.get_selected()
            if roi:
                step = 10 if modifiers == Qt.ShiftModifier else 1

                if key == Qt.Key_Left:
                    roi.translate(-step, 0)
                elif key == Qt.Key_Right:
                    roi.translate(step, 0)
                elif key == Qt.Key_Up:
                    roi.translate(0, -step)
                elif key == Qt.Key_Down:
                    roi.translate(0, step)

                self.roi_modified.emit(self.roi_collection.selected_index)
                self.update()
                return

        super().keyPressEvent(event)

    # ==================== 绘制 ====================

    def paintEvent(self, event):
        """绘制"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制背景
        painter.fillRect(self.rect(), QColor("#1e1e1e"))

        if not self.pixmap or not self.pixmap_display:
            painter.setPen(QColor("#666"))
            font = QFont("Microsoft YaHei", 12)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, "请加载图片或截图")
            return

        # 绘制图片阴影
        shadow_rect = QRect(self.offset.x() + 3, self.offset.y() + 3,
                           self.pixmap_display.width(), self.pixmap_display.height())
        painter.fillRect(shadow_rect, QColor(0, 0, 0, 100))

        # 绘制图片
        painter.drawPixmap(self.offset.x(), self.offset.y(), self.pixmap_display)

        # 绘制图片边框
        img_rect = QRect(self.offset.x(), self.offset.y(),
                        self.pixmap_display.width(), self.pixmap_display.height())
        painter.setPen(QPen(QColor("#444"), 1))
        painter.drawRect(img_rect)

        # 绘制原点标记
        origin = self._image_to_screen(QPoint(0, 0))
        painter.setPen(QPen(QColor(255, 0, 0), 2))
        painter.drawLine(origin.x() - 5, origin.y(), origin.x() + 5, origin.y())
        painter.drawLine(origin.x(), origin.y() - 5, origin.x(), origin.y() + 5)

        # 绘制ROI
        for i, roi in enumerate(self.roi_collection):
            self._draw_roi(painter, roi, i == self.roi_collection.selected_index)

        # 绘制超像素边界
        if self.show_superpixel and self.superpixel_overlay and not self.superpixel_overlay.isNull():
            painter.drawPixmap(self.offset.x(), self.offset.y(), self.superpixel_overlay)

            # 高亮选中的超像素
            if self.pending_merge_labels:
                painter.setBrush(QColor(255, 255, 0, 100))
                painter.setPen(QPen(QColor(255, 200, 0), 2))

                for label in self.pending_merge_labels:
                    if hasattr(self, '_superpixel_contours') and label in self._superpixel_contours:
                        contour = self._superpixel_contours[label]
                        if contour is not None and len(contour) > 0:
                            points = []
                            for pt in contour:
                                sx = int(pt[0][0] * self.scale + self.offset.x())
                                sy = int(pt[0][1] * self.scale + self.offset.y())
                                points.append(QPoint(sx, sy))
                            if len(points) >= 3:
                                polygon = QPolygon(points)
                                painter.drawPolygon(polygon)

            # 显示合并模式提示（只在有选中区域时显示）
            if self.pending_merge_labels:
                painter.setPen(QColor(255, 255, 0))
                font = QFont("Microsoft YaHei", 10, QFont.Bold)
                painter.setFont(font)
                status_text = f"合并模式: 已选{len(self.pending_merge_labels)}个区域"
                painter.drawText(10, 30, status_text)

        # 绘制正在绘制的ROI
        if self.is_drawing:
            rect = QRect(self.draw_start, self.draw_current).normalized()
            screen_rect = QRect(
                self._image_to_screen(rect.topLeft()),
                self._image_to_screen(rect.bottomRight())
            )
            painter.setPen(QPen(QColor(0, 200, 255), 2, Qt.DashLine))
            painter.drawRect(screen_rect)

            size_text = f"{rect.width()} x {rect.height()}"
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(screen_rect.left(), screen_rect.top() - 5, size_text)

        # 绘制自动检测预览ROI
        if self.temp_roi:
            roi = self.temp_roi
            screen_rect = QRect(
                self._image_to_screen(QPoint(roi.x, roi.y)),
                QSize(int(roi.width * self.scale), int(roi.height * self.scale))
            )
            painter.setPen(QPen(QColor(255, 255, 0), 2, Qt.DashLine))
            painter.setBrush(QColor(255, 255, 0, 50))
            painter.drawRect(screen_rect)

            painter.setPen(QColor(255, 255, 0))
            font = QFont("Microsoft YaHei", 10, QFont.Bold)
            painter.setFont(font)
            painter.drawText(10, 30, f"预览: 松开Ctrl完成 ({roi.width}x{roi.height})")

    def _draw_roi(self, painter: QPainter, roi: ROI, is_selected: bool):
        """绘制单个ROI"""
        screen_rect = QRect(
            self._image_to_screen(QPoint(roi.x, roi.y)),
            QSize(int(roi.width * self.scale), int(roi.height * self.scale))
        )

        # 边框颜色
        if is_selected:
            pen = QPen(QColor(0, 200, 255), 2, Qt.SolidLine)
        else:
            pen = QPen(QColor(roi.color), 2, Qt.SolidLine)
        painter.setPen(pen)

        # 填充
        if is_selected:
            painter.setBrush(QColor(0, 200, 255, 30))
        else:
            painter.setBrush(QColor(roi.color))
            painter.setBrush(QBrush())

        painter.drawRect(screen_rect)

        # 绘制标签
        label = roi.node_name or roi.name
        if label:
            text_rect = painter.fontMetrics().boundingRect(label)
            text_w = text_rect.width() + 10
            text_h = text_rect.height() + 4

            label_rect = QRect(screen_rect.left(), screen_rect.top() - text_h, text_w, text_h)
            painter.fillRect(label_rect, QColor(0, 0, 0, 180))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(label_rect, Qt.AlignCenter, label)

        # 绘制调整手柄（仅选中时）
        if is_selected:
            handle_size = 10
            half = handle_size // 2

            handles = [
                (screen_rect.left(), screen_rect.top()),
                (screen_rect.center().x(), screen_rect.top()),
                (screen_rect.right(), screen_rect.top()),
                (screen_rect.left(), screen_rect.center().y()),
                (screen_rect.right(), screen_rect.center().y()),
                (screen_rect.left(), screen_rect.bottom()),
                (screen_rect.center().x(), screen_rect.bottom()),
                (screen_rect.right(), screen_rect.bottom())
            ]

            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.setBrush(QColor(0, 200, 255))

            for hx, hy in handles:
                painter.drawRect(hx - half, hy - half, handle_size, handle_size)
