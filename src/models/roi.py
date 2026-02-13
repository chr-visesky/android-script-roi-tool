# -*- coding: utf-8 -*-
"""
ROI数据模型
"""

import uuid
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from PyQt5.QtCore import QRect, QPoint


@dataclass
class ROI:
    """ROI数据类 - 支持图片切图和功能区域"""
    # 基础坐标
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

    # 命名（向后兼容）
    name: str = ""

    # 新字段：节点名和图片名分开
    node_name: str = ""      # 节点/逻辑名称（如：home_button, username_input）
    image_name: str = ""     # 图片文件名（如：icon_home.png）

    # 新字段：ROI类型和动作
    roi_type: str = "image"  # 'image'(图片) 或 'region'(区域)
    action: str = ""         # 'click'(点击), 'ocr'(文字识别), 'swipe'(滑动), ''(无动作)

    # 点击动作详细配置
    click_mode: str = "single"      # 'single'(单次), 'loop'(循环)
    click_count: int = 1            # 点击次数，-1表示无限
    click_interval: int = 500       # 点击间隔(毫秒)，默认500ms

    # 滑动动作详细配置
    swipe_direction: str = "top_to_bottom"  # 'top_to_bottom', 'bottom_to_top', 'left_to_right', 'right_to_left'
    swipe_speed: int = 400          # 滑动速度(像素/秒)，默认400px/s

    # 图片类型动作配置
    image_action: str = "detect"    # 'detect'(判断存在), 'detect_and_click'(判断存在后点击)

    roi_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    color: str = "#00FF00"
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    image_path: str = ""
    
    @property
    def rect(self) -> QRect:
        """获取QRect对象"""
        return QRect(self.x, self.y, self.width, self.height)
    
    @rect.setter
    def rect(self, rect: QRect):
        """从QRect设置"""
        self.x = rect.x()
        self.y = rect.y()
        self.width = rect.width()
        self.height = rect.height()
        self.modified_at = time.time()
    
    @property
    def center(self) -> Tuple[int, int]:
        """获取中心点坐标"""
        return (self.x + self.width // 2, self.y + self.height // 2)
    
    @property
    def area(self) -> int:
        """获取面积"""
        return self.width * self.height
    
    @property
    def right(self) -> int:
        """右边界"""
        return self.x + self.width
    
    @property
    def bottom(self) -> int:
        """下边界"""
        return self.y + self.height
    
    def contains(self, point: QPoint) -> bool:
        """检查点是否在ROI内"""
        return self.rect.contains(point)
    
    def translate(self, dx: int, dy: int):
        """平移ROI"""
        self.x += dx
        self.y += dy
        self.modified_at = time.time()
    
    def resize(self, new_rect: QRect):
        """调整大小"""
        self.rect = new_rect
    
    def copy(self) -> 'ROI':
        """复制ROI"""
        new_roi = ROI(
            x=self.x,
            y=self.y,
            width=self.width,
            height=self.height,
            name=f"{self.name}_copy",
            color=self.color,
            tags=self.tags.copy()
        )
        return new_roi
    
    def to_dict(self) -> Dict:
        """转换为字典 - 只包含相关字段"""
        # 基础字段（所有类型都有）
        result = {
            "id": self.roi_id,
            "name": self.name,
            "node_name": self.node_name,
            "roi_type": self.roi_type,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "center": self.center
        }

        # 根据类型添加特定字段
        if self.roi_type == "image":
            # 图片类型：添加图片相关配置
            result["image_name"] = self.image_name
            result["image_action"] = self.image_action
        else:
            # 区域类型：添加动作
            result["action"] = self.action

            # 根据动作添加详细配置
            if self.action == "click":
                result["click_mode"] = self.click_mode
                result["click_count"] = self.click_count
                result["click_interval"] = self.click_interval
            elif self.action == "swipe":
                result["swipe_direction"] = self.swipe_direction
                result["swipe_speed"] = self.swipe_speed
            # OCR动作不需要额外配置

        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ROI':
        """从字典创建"""
        roi = cls()
        roi.roi_id = data.get("id", str(uuid.uuid4())[:8])
        roi.name = data.get("name", "")

        # 新字段（兼容旧数据）
        roi.node_name = data.get("node_name", "")
        roi.image_name = data.get("image_name", "")
        roi.roi_type = data.get("roi_type", "image")
        roi.action = data.get("action", "")

        # 点击配置（兼容旧数据）
        roi.click_mode = data.get("click_mode", "single")
        roi.click_count = data.get("click_count", 1)
        roi.click_interval = data.get("click_interval", 500)

        # 滑动配置（兼容旧数据）
        roi.swipe_direction = data.get("swipe_direction", "top_to_bottom")
        roi.swipe_speed = data.get("swipe_speed", 400)

        # 图片配置（兼容旧数据）
        roi.image_action = data.get("image_action", "detect")

        roi.x = data.get("x", 0)
        roi.y = data.get("y", 0)
        roi.width = data.get("width", 0)
        roi.height = data.get("height", 0)
        roi.color = data.get("color", "#00FF00")
        roi.created_at = data.get("created_at", time.time())
        roi.modified_at = data.get("modified_at", time.time())
        roi.tags = data.get("tags", [])
        roi.image_path = data.get("image_path", "")
        return roi
    
    def __str__(self) -> str:
        return f"ROI({self.name}: {self.x},{self.y} {self.width}x{self.height})"


class ROICollection:
    """ROI集合管理"""
    
    def __init__(self):
        self.rois: List[ROI] = []
        self.selected_index: int = -1
        self._name_counter = 0
    
    def add(self, roi: ROI) -> int:
        """添加ROI，返回索引"""
        if not roi.name:
            self._name_counter += 1
            roi.name = f"ROI_{self._name_counter:03d}"
        self.rois.append(roi)
        return len(self.rois) - 1
    
    def remove(self, index: int) -> bool:
        """删除指定索引的ROI"""
        if 0 <= index < len(self.rois):
            del self.rois[index]
            if self.selected_index == index:
                self.selected_index = -1
            elif self.selected_index > index:
                self.selected_index -= 1
            return True
        return False
    
    def remove_selected(self) -> bool:
        """删除选中的ROI"""
        if self.selected_index >= 0:
            return self.remove(self.selected_index)
        return False
    
    def get(self, index: int) -> Optional[ROI]:
        """获取指定索引的ROI"""
        if 0 <= index < len(self.rois):
            return self.rois[index]
        return None
    
    def get_selected(self) -> Optional[ROI]:
        """获取选中的ROI"""
        return self.get(self.selected_index)
    
    def select(self, index: int):
        """选中指定索引"""
        if 0 <= index < len(self.rois):
            self.selected_index = index
        else:
            self.selected_index = -1
    
    def select_by_point(self, point: QPoint) -> int:
        """根据点选ROI，返回索引"""
        for i, roi in enumerate(self.rois):
            if roi.contains(point):
                self.selected_index = i
                return i
        self.selected_index = -1
        return -1
    
    def copy_selected(self) -> Optional[ROI]:
        """复制选中的ROI"""
        roi = self.get_selected()
        if roi:
            new_roi = roi.copy()
            # 偏移一点避免重叠
            new_roi.translate(20, 20)
            self.add(new_roi)
            self.selected_index = len(self.rois) - 1
            return new_roi
        return None
    
    def clear(self):
        """清空所有ROI"""
        self.rois.clear()
        self.selected_index = -1
        self._name_counter = 0
    
    def get_resize_handle(self, point: QPoint, roi_index: int) -> int:
        """
        获取调整手柄索引
        返回: 0-7表示8个方向，-1表示不在手柄上
        """
        if roi_index < 0 or roi_index >= len(self.rois):
            return -1
        
        roi = self.rois[roi_index]
        rect = roi.rect
        handle_size = 8
        half = handle_size // 2
        
        handles = [
            (rect.left(), rect.top()),           # 0: 左上
            (rect.center().x(), rect.top()),     # 1: 上中
            (rect.right(), rect.top()),          # 2: 右上
            (rect.left(), rect.center().y()),    # 3: 左中
            (rect.right(), rect.center().y()),   # 4: 右中
            (rect.left(), rect.bottom()),        # 5: 左下
            (rect.center().x(), rect.bottom()),  # 6: 下中
            (rect.right(), rect.bottom())        # 7: 右下
        ]
        
        for i, (hx, hy) in enumerate(handles):
            if abs(point.x() - hx) <= half and abs(point.y() - hy) <= half:
                return i
        return -1
    
    def resize_roi(self, roi_index: int, handle: int, new_pos: QPoint):
        """调整ROI大小"""
        if roi_index < 0 or roi_index >= len(self.rois):
            return
        
        roi = self.rois[roi_index]
        rect = roi.rect
        
        if handle == 0:  # 左上
            rect.setLeft(new_pos.x())
            rect.setTop(new_pos.y())
        elif handle == 1:  # 上中
            rect.setTop(new_pos.y())
        elif handle == 2:  # 右上
            rect.setRight(new_pos.x())
            rect.setTop(new_pos.y())
        elif handle == 3:  # 左中
            rect.setLeft(new_pos.x())
        elif handle == 4:  # 右中
            rect.setRight(new_pos.x())
        elif handle == 5:  # 左下
            rect.setLeft(new_pos.x())
            rect.setBottom(new_pos.y())
        elif handle == 6:  # 下中
            rect.setBottom(new_pos.y())
        elif handle == 7:  # 右下
            rect.setRight(new_pos.x())
            rect.setBottom(new_pos.y())
        
        roi.rect = rect.normalized()
    
    def move_roi(self, roi_index: int, delta: QPoint):
        """移动ROI"""
        if roi_index < 0 or roi_index >= len(self.rois):
            return
        self.rois[roi_index].translate(delta.x(), delta.y())
    
    def to_list(self) -> List[Dict]:
        """转换为列表"""
        return [roi.to_dict() for roi in self.rois]
    
    def from_list(self, data_list: List[Dict]):
        """从列表加载"""
        self.clear()
        for data in data_list:
            self.add(ROI.from_dict(data))
    
    def __len__(self) -> int:
        return len(self.rois)
    
    def __iter__(self):
        return iter(self.rois)
    
    def __getitem__(self, index: int) -> ROI:
        return self.rois[index]
