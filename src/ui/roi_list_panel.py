# -*- coding: utf-8 -*-
"""
ROI列表面板
显示所有ROI的列表，支持选择、删除、复制
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QListWidget, QListWidgetItem, QLabel, QAbstractItemView
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from ..models.roi import ROICollection, ROI


class ROIListPanel(QWidget):
    """
    ROI列表面板
    
    信号:
        roi_selected: 选中了ROI
        roi_deleted: 删除了ROI
        roi_copied: 复制了ROI
    """
    
    roi_selected = pyqtSignal(int)
    roi_deleted = pyqtSignal(int)
    roi_copied = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.roi_collection = None
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 标题
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("📋 ROI列表"))
        self.label_count = QLabel("(0)")
        title_layout.addWidget(self.label_count)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # ROI列表
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #e9ecef;
            }
            QListWidget::item:selected {
                background-color: #007bff;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #e3f2fd;
            }
        """)
        layout.addWidget(self.list_widget)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        self.btn_copy = QPushButton("📋 复制")
        self.btn_copy.setToolTip("复制选中的ROI (Ctrl+C)")
        self.btn_copy.clicked.connect(self.copy_selected)
        btn_layout.addWidget(self.btn_copy)
        
        self.btn_delete = QPushButton("🗑️ 删除")
        self.btn_delete.setToolTip("删除选中的ROI (Del)")
        self.btn_delete.clicked.connect(self.delete_selected)
        btn_layout.addWidget(self.btn_delete)
        
        self.btn_clear = QPushButton("🧹 清空")
        self.btn_clear.setToolTip("清空所有ROI")
        self.btn_clear.clicked.connect(self.clear_all)
        btn_layout.addWidget(self.btn_clear)
        
        layout.addLayout(btn_layout)
        
        # 信息显示
        self.label_info = QLabel("点击选中ROI，拖拽调整位置")
        self.label_info.setStyleSheet("color: #6c757d; font-size: 11px;")
        layout.addWidget(self.label_info)
    
    def set_roi_collection(self, collection: ROICollection):
        """设置ROI集合"""
        self.roi_collection = collection
        self.refresh_list()
    
    def refresh_list(self):
        """刷新列表显示"""
        self.list_widget.clear()
        
        if not self.roi_collection:
            self.label_count.setText("(0)")
            return
        
        for i, roi in enumerate(self.roi_collection):
            item = QListWidgetItem()
            
            # 显示信息
            center = roi.center
            text = f"{i+1}. {roi.name}\n"
            text += f"   位置: ({roi.x}, {roi.y}) 大小: {roi.width}x{roi.height}\n"
            text += f"   中心: ({center[0]}, {center[1]})"
            
            item.setText(text)
            item.setData(Qt.UserRole, i)  # 存储索引
            
            # 设置颜色标识
            color = QColor(roi.color)
            item.setForeground(color)
            
            self.list_widget.addItem(item)
        
        self.label_count.setText(f"({len(self.roi_collection)})")
        
        # 保持选中状态
        if self.roi_collection.selected_index >= 0:
            self.list_widget.setCurrentRow(self.roi_collection.selected_index)
    
    def on_item_clicked(self, item: QListWidgetItem):
        """列表项被点击"""
        idx = item.data(Qt.UserRole)
        self.roi_selected.emit(idx)
    
    def select_item(self, index: int):
        """选中指定项"""
        if 0 <= index < self.list_widget.count():
            self.list_widget.setCurrentRow(index)
    
    def copy_selected(self):
        """复制选中的ROI"""
        idx = self.list_widget.currentRow()
        if idx >= 0 and self.roi_collection:
            roi = self.roi_collection.get(idx)
            if roi:
                new_roi = roi.copy()
                self.roi_copied.emit(new_roi)
    
    def delete_selected(self):
        """删除选中的ROI"""
        idx = self.list_widget.currentRow()
        if idx >= 0:
            self.roi_deleted.emit(idx)
    
    def clear_all(self):
        """清空所有"""
        from PyQt5.QtWidgets import QMessageBox
        
        if self.roi_collection and len(self.roi_collection) > 0:
            reply = QMessageBox.question(
                self, "确认",
                f"确定要删除所有 {len(self.roi_collection)} 个ROI吗?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.roi_collection.clear()
                self.refresh_list()
