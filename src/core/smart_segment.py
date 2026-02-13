# -*- coding: utf-8 -*-
"""
智能图像分割模块
使用GrabCut和区域生长算法实现点击分割
支持不规则边界和透明背景输出
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List
from PyQt5.QtGui import QPixmap, QImage
from ..models.roi import ROI


class SmartSegmenter:
    """智能分割器 - 基于点击点分割任意形状"""

    def __init__(self):
        self.iterations = 5  # GrabCut迭代次数

    def segment_at_point(self, pixmap: QPixmap, x: int, y: int,
                        expansion: int = 50) -> Optional[Tuple[ROI, np.ndarray]]:
        """
        在点击位置进行智能分割

        使用GrabCut算法，基于点击点自动分割前景和背景

        Args:
            pixmap: 输入图片
            x, y: 点击位置
            expansion: 初始区域扩展大小

        Returns:
            (ROI, mask) 或 None
            - ROI: 边界框信息
            - mask: 分割掩码（0=背景, 255=前景）
        """
        img = self._qpixmap_to_cv2(pixmap)
        if img is None:
            return None

        h, w = img.shape[:2]
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))

        # 创建初始掩码
        mask = np.zeros((h, w), np.uint8)

        # 定义矩形区域（以点击点为中心）
        rect_x = max(0, x - expansion)
        rect_y = max(0, y - expansion)
        rect_w = min(w - rect_x, expansion * 2)
        rect_h = min(h - rect_y, expansion * 2)
        rect = (rect_x, rect_y, rect_w, rect_h)

        # 背景模型和前景模型
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)

        try:
            # 运行GrabCut
            cv2.grabCut(img, mask, rect, bgd_model, fgd_model,
                       self.iterations, cv2.GC_INIT_WITH_RECT)

            # 创建最终掩码：0和2是背景，1和3是前景
            mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')

            # 找到前景区域的轮廓
            contours, _ = cv2.findContours(mask2 * 255, cv2.RETR_EXTERNAL,
                                          cv2.CHAIN_APPROX_SIMPLE)

            if not contours:
                return None

            # 找到包含点击点的轮廓
            best_contour = None
            best_area = 0

            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 100:  # 过滤太小的
                    continue

                # 检查点击点是否在这个轮廓内
                if cv2.pointPolygonTest(contour, (x, y), False) >= 0:
                    if area > best_area:
                        best_area = area
                        best_contour = contour

            # 如果没有轮廓包含点击点，选择离点击点最近的
            if best_contour is None:
                min_dist = float('inf')
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area < 100:
                        continue
                    # 计算轮廓中心到点击点的距离
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        dist = np.sqrt((x - cx)**2 + (y - cy)**2)
                        if dist < min_dist:
                            min_dist = dist
                            best_contour = contour

            if best_contour is None:
                return None

            # 获取边界框
            bx, by, bw, bh = cv2.boundingRect(best_contour)

            # 创建ROI
            roi = ROI(x=bx, y=by, width=bw, height=bh)
            roi.name = "segmented"
            roi.is_segmented = True
            roi.contour = best_contour

            # 创建精细掩码（只保留选中的轮廓）
            final_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(final_mask, [best_contour], -1, 255, -1)

            return roi, final_mask

        except Exception as e:
            print(f"GrabCut failed: {e}")
            return None

    def segment_with_refinement(self, pixmap: QPixmap, x: int, y: int,
                                expansion: int = 80) -> Optional[Tuple[ROI, np.ndarray]]:
        """
        带精细化处理的分割
        先运行GrabCut，然后用形态学操作优化边缘
        """
        result = self.segment_at_point(pixmap, x, y, expansion)
        if result is None:
            return None

        roi, mask = result

        # 形态学优化
        kernel = np.ones((5, 5), np.uint8)

        # 开运算去除小噪点
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

        # 闭运算填充小孔
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        # 高斯模糊平滑边缘
        mask = cv2.GaussianBlur(mask, (5, 5), 0)

        # 重新二值化
        _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)

        return roi, mask

    def create_transparent_crop(self, img: np.ndarray, mask: np.ndarray,
                                roi: ROI) -> np.ndarray:
        """
        创建带透明背景的裁剪图

        Args:
            img: 原始图片 (BGR格式)
            mask: 分割掩码
            roi: ROI区域

        Returns:
            带Alpha通道的图片 (BGRA格式)
        """
        # 提取ROI区域
        x, y, w, h = roi.x, roi.y, roi.width, roi.height
        roi_img = img[y:y+h, x:x+w]
        roi_mask = mask[y:y+h, x:x+w]

        # 转换为BGRA
        if len(roi_img.shape) == 3:
            bgra = cv2.cvtColor(roi_img, cv2.COLOR_BGR2BGRA)
        else:
            bgra = cv2.cvtColor(roi_img, cv2.COLOR_GRAY2BGRA)

        # 设置Alpha通道
        bgra[:, :, 3] = roi_mask

        return bgra

    def _qpixmap_to_cv2(self, pixmap: QPixmap) -> Optional[np.ndarray]:
        """QPixmap转OpenCV格式"""
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
