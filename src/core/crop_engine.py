# -*- coding: utf-8 -*-
"""
切图引擎
负责根据ROI裁剪图片并保存
"""

import os
import time
from typing import Dict, List, Optional
from PyQt5.QtGui import QPixmap
from ..models.roi import ROI


class CropEngine:
    """切图引擎"""
    
    def __init__(self, output_dir: str = "./res_output"):
        self.output_dir = output_dir
        self.ensure_output_dir()
        
        # 命名模板
        self.naming_template = "{prefix}{roi_name}_{timestamp}.png"
        
    def ensure_output_dir(self):
        """确保输出目录存在"""
        os.makedirs(self.output_dir, exist_ok=True)
    
    def set_output_dir(self, path: str):
        """设置输出目录"""
        self.output_dir = path
        self.ensure_output_dir()
    
    def generate_filename(self, roi: ROI, prefix: str = "") -> str:
        """生成文件名"""
        timestamp = int(time.time())
        return self.naming_template.format(
            prefix=prefix,
            roi_name=roi.name,
            timestamp=timestamp
        )
    
    def crop(self, source_pixmap: QPixmap, roi: ROI, prefix: str = "") -> Optional[Dict]:
        """
        裁剪单个ROI
        
        Args:
            source_pixmap: 源图片
            roi: ROI对象
            prefix: 文件名前缀
            
        Returns:
            包含裁剪信息的字典，失败返回None
        """
        if not source_pixmap or source_pixmap.isNull():
            return None
        
        try:
            # 裁剪
            rect = roi.rect
            cropped = source_pixmap.copy(rect)
            
            if cropped.isNull():
                return None
            
            # 生成文件名
            filename = self.generate_filename(roi, prefix)
            filepath = os.path.join(self.output_dir, filename)
            
            # 保存
            success = cropped.save(filepath)
            if not success:
                return None
            
            # 更新ROI信息
            roi.image_path = filepath
            
            return {
                "roi_id": roi.roi_id,
                "roi_name": roi.name,
                "filename": filename,
                "filepath": filepath,
                "x": roi.x,
                "y": roi.y,
                "width": roi.width,
                "height": roi.height,
                "center_x": roi.center[0],
                "center_y": roi.center[1]
            }
            
        except Exception as e:
            print(f"裁剪失败: {e}")
            return None
    
    def crop_all(self, source_pixmap: QPixmap, rois: List[ROI], prefix: str = "") -> List[Dict]:
        """
        批量裁剪所有ROI
        
        Args:
            source_pixmap: 源图片
            rois: ROI列表
            prefix: 文件名前缀
            
        Returns:
            裁剪结果列表
        """
        results = []
        for roi in rois:
            result = self.crop(source_pixmap, roi, prefix)
            if result:
                results.append(result)
        return results
