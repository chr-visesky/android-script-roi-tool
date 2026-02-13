# -*- coding: utf-8 -*-
"""
导出管理器
负责导出各种格式的数据
"""

import json
import os
import time
from typing import Dict, List, Optional
from ..models.roi import ROI, ROICollection


class ExportManager:
    """导出管理器"""
    
    def __init__(self, output_dir: str = "./res_output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def export_json(self, rois: ROICollection, source_info: Dict = None) -> str:
        """
        导出为JSON格式
        
        Returns:
            导出的文件路径
        """
        data = {
            "version": "1.0.0",
            "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source": "安卓脚本切图神器",
            "roi_count": len(rois),
            "rois": rois.to_list()
        }
        
        if source_info:
            data["source_info"] = source_info
        
        filename = f"roi_data_{int(time.time())}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def export_autojs(self, rois: ROICollection, source_info: Dict = None) -> str:
        """
        导出为Auto.js格式
        
        Returns:
            导出的文件路径
        """
        lines = [
            "// Auto.js 脚本",
            f"// 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "// ROI区域定义",
            "const REGIONS = {"
        ]
        
        for roi in rois:
            lines.append(f'    "{roi.name}": {{'
                        f'x: {roi.x}, y: {roi.y}, '
                        f'w: {roi.width}, h: {roi.height}}},')
        
        lines.extend([
            "};",
            "",
            "// 点击函数"
        ])
        
        for roi in rois:
            center = roi.center
            lines.extend([
                f"function click_{roi.name}() {{",
                f'    click({center[0]}, {center[1]});',
                "}"
            ])
        
        lines.extend([
            "",
            "// 找图函数"
        ])
        
        for roi in rois:
            if roi.image_path:
                filename = os.path.basename(roi.image_path)
                lines.extend([
                    f"function find_{roi.name}() {{",
                    f'    return images.findImage(captureScreen(), images.read("./res/{filename}"));',
                    "}"
                ])
        
        filename = f"auto_script_{int(time.time())}.js"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        return filepath
    
    def export_python(self, rois: ROICollection, source_info: Dict = None) -> str:
        """
        导出为Python格式（OpenCV模板匹配）
        
        Returns:
            导出的文件路径
        """
        lines = [
            "# Python OpenCV 脚本",
            f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "import cv2",
            "import numpy as np",
            "",
            "# ROI区域定义",
            "ROI_DATA = {"
        ]
        
        for roi in rois:
            lines.append(f'    "{roi.name}": {{'
                        f'"x": {roi.x}, "y": {roi.y}, '
                        f'"w": {roi.width}, "h": {roi.height}}},')
        
        lines.extend([
            "}",
            "",
            "# 模板路径"
        ])
        
        for roi in rois:
            if roi.image_path:
                filename = os.path.basename(roi.image_path)
                lines.append(f'# {roi.name}: ./res/{filename}')
        
        lines.extend([
            "",
            "def match_template(screen, template_path, threshold=0.8):",
            "    \"\"\"模板匹配\"\"\"",
            "    template = cv2.imread(template_path)",
            "    if template is None:",
            "        return None",
            "    ",
            "    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)",
            "    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)",
            "    ",
            "    if max_val >= threshold:",
            "        return max_loc",
            "    return None",
            "",
            "def click(x, y):",
            "    \"\"\"点击坐标\"\"\"",
            "    print(f'点击: ({x}, {y})')",
        ])
        
        # 为每个ROI生成点击函数
        for roi in rois:
            center = roi.center
            lines.extend([
                "",
                f"def click_{roi.name}(screen=None):",
                f'    \"\"\"点击 {roi.name}\"\"\"',
                f'    click({center[0]}, {center[1]})',
            ])
            
            if roi.image_path:
                filename = os.path.basename(roi.image_path)
                lines.extend([
                    f'    # 如需匹配图片:',
                    f'    # pos = match_template(screen, "./res/{filename}")',
                    f'    # if pos: click(pos[0] + {roi.width//2}, pos[1] + {roi.height//2})',
                ])
        
        filename = f"auto_script_{int(time.time())}.py"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        return filepath
    
    def generate_code_snippet(self, roi: ROI, format: str = "autojs") -> str:
        """
        生成单个ROI的代码片段
        
        Args:
            roi: ROI对象
            format: 格式 (autojs, python, raw)
            
        Returns:
            代码字符串
        """
        x, y, w, h = roi.x, roi.y, roi.width, roi.height
        cx, cy = roi.center
        
        if format == "autojs":
            lines = [
                f"// ROI: {roi.name}",
                f"var roi_{roi.name} = {{{x}, {y}, {w}, {h}}};",
                f"click({cx}, {cy});"
            ]
            if roi.image_path:
                filename = os.path.basename(roi.image_path)
                lines.append(f'// findImage("./res/{filename}");')
            return '\n'.join(lines)
        
        elif format == "python":
            lines = [
                f"# ROI: {roi.name}",
                f'{roi.name}_bbox = ({x}, {y}, {w}, {h})',
                f'click({cx}, {cy})'
            ]
            return '\n'.join(lines)
        
        else:  # raw
            return f"{roi.name}: ({x}, {y}, {w}, {h}) -> center: ({cx}, {cy})"
    
    def export_all(self, rois: ROICollection, source_info: Dict = None) -> Dict[str, str]:
        """
        导出所有格式
        
        Returns:
            格式名到文件路径的映射
        """
        results = {}
        
        try:
            results['json'] = self.export_json(rois, source_info)
        except Exception as e:
            print(f"导出JSON失败: {e}")
        
        try:
            results['autojs'] = self.export_autojs(rois, source_info)
        except Exception as e:
            print(f"导出Auto.js失败: {e}")
        
        try:
            results['python'] = self.export_python(rois, source_info)
        except Exception as e:
            print(f"导出Python失败: {e}")
        
        return results
