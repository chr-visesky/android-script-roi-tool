# -*- coding: utf-8 -*-
"""
自动边界识别模块 - 重写版
支持圆形检测、红点检测、UI元素识别
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
from PyQt5.QtGui import QPixmap, QImage
from ..models.roi import ROI


class AutoDetector:
    """自动边界检测器 - 支持圆形和矩形"""

    def __init__(self):
        self.min_circle_radius = 5
        self.max_circle_radius = 100
        self.dp = 1.2
        self.param1 = 50
        self.param2 = 30

    def detect_circles(self, pixmap: QPixmap, min_radius: int = 5, max_radius: int = 100) -> List[ROI]:
        """
        使用霍夫圆变换检测圆形（适合图标、红点、按钮）

        Args:
            pixmap: 输入图片
            min_radius: 最小圆半径
            max_radius: 最大圆半径

        Returns:
            ROI列表（正方形边界框包含圆形）
        """
        img = self._qpixmap_to_cv2(pixmap)
        if img is None:
            return []

        # 转为灰度图
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img

        # 高斯模糊降噪
        gray_blur = cv2.medianBlur(gray, 5)

        rois = []

        # 霍夫圆检测
        circles = cv2.HoughCircles(
            gray_blur,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=20,
            param1=50,
            param2=30,
            minRadius=min_radius,
            maxRadius=max_radius
        )

        if circles is not None:
            circles = np.uint16(np.around(circles))
            for i, circle in enumerate(circles[0, :]):
                center_x, center_y, radius = circle

                # 创建包含圆的正方形ROI
                x = max(0, center_x - radius - 2)  # 留一点边距
                y = max(0, center_y - radius - 2)
                w = min(pixmap.width() - x, radius * 2 + 4)
                h = min(pixmap.height() - y, radius * 2 + 4)

                roi = ROI(x=x, y=y, width=w, height=h)
                roi.name = f"circle_{i+1:02d}"
                roi.is_circle = True
                roi.circle_center = (center_x, center_y)
                roi.circle_radius = radius
                rois.append(roi)

        return rois

    def detect_red_dots(self, pixmap: QPixmap) -> List[ROI]:
        """
        专门检测红色圆点（消息红点、通知标记等）

        Returns:
            ROI列表
        """
        img = self._qpixmap_to_cv2(pixmap)
        if img is None:
            return []

        # 转为HSV色彩空间
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # 定义红色的HSV范围（红色在HSV中跨越0度）
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([180, 255, 255])

        # 创建红色掩码
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        red_mask = cv2.bitwise_or(mask1, mask2)

        # 形态学操作连接相邻区域
        kernel = np.ones((3, 3), np.uint8)
        red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        # 查找轮廓
        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        rois = []
        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)

            # 过滤太小的（可能是噪点）和太大的
            if area < 30 or area > 5000:
                continue

            # 获取最小外接圆
            (x, y), radius = cv2.minEnclosingCircle(contour)
            center = (int(x), int(y))
            radius = int(radius)

            # 检查圆度（确保是圆形而不是不规则形状）
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                # 圆形的circularity接近1
                if circularity > 0.6:
                    x = max(0, center[0] - radius - 2)
                    y = max(0, center[1] - radius - 2)
                    w = min(pixmap.width() - x, radius * 2 + 4)
                    h = min(pixmap.height() - y, radius * 2 + 4)

                    roi = ROI(x=x, y=y, width=w, height=h)
                    roi.name = f"red_dot_{i+1:02d}"
                    roi.is_circle = True
                    roi.circle_center = center
                    roi.circle_radius = radius
                    rois.append(roi)

        return rois

    def detect_ui_buttons(self, pixmap: QPixmap) -> List[ROI]:
        """
        检测UI按钮（圆角矩形或圆形按钮）

        Returns:
            ROI列表
        """
        img = self._qpixmap_to_cv2(pixmap)
        if img is None:
            return []

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

        rois = []

        # 方法1: 检测高对比度的闭合区域
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # 自适应阈值
        thresh = cv2.adaptiveThreshold(
            blurred, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )

        # 形态学操作
        kernel = np.ones((5, 5), np.uint8)
        morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)

        # 查找轮廓
        contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)

            # 过滤太小或太大的
            if area < 200 or area > (pixmap.width() * pixmap.height() * 0.5):
                continue

            # 获取边界框
            x, y, w, h = cv2.boundingRect(contour)

            # 过滤太扁或太细的（可能是线条）
            aspect_ratio = float(w) / h if h > 0 else 0
            if aspect_ratio < 0.1 or aspect_ratio > 10:
                continue

            # 检查是否是圆角矩形（通过角点检测）
            approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)

            # 4个点可能是矩形，更多点可能是圆角矩形或圆形
            if len(approx) >= 4:
                roi = ROI(x=x, y=y, width=w, height=h)
                roi.name = f"button_{i+1:02d}"
                rois.append(roi)

        return rois

    def detect_icons(self, pixmap: QPixmap) -> List[ROI]:
        """
        检测图标（通常是正方形或圆形的独立元素）

        Returns:
            ROI列表
        """
        img = self._qpixmap_to_cv2(pixmap)
        if img is None:
            return []

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

        # 边缘检测
        edges = cv2.Canny(gray, 50, 150)

        # 膨胀连接边缘
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)

        # 查找轮廓
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        rois = []
        img_area = pixmap.width() * pixmap.height()

        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)

            # 过滤
            if area < 100 or area > img_area * 0.3:
                continue

            x, y, w, h = cv2.boundingRect(contour)

            # 图标通常接近正方形
            aspect_ratio = max(w, h) / min(w, h) if min(w, h) > 0 else 0
            if aspect_ratio > 2:  # 太扁的不是图标
                continue

            roi = ROI(x=x, y=y, width=w, height=h)
            roi.name = f"icon_{i+1:02d}"
            rois.append(roi)

        return rois

    def detect_all(self, pixmap: QPixmap) -> List[ROI]:
        """
        综合检测所有类型的元素

        Returns:
            ROI列表
        """
        all_rois = []

        # 1. 检测圆形（图标、按钮）
        circles = self.detect_circles(pixmap)
        all_rois.extend(circles)

        # 2. 检测红点
        red_dots = self.detect_red_dots(pixmap)
        all_rois.extend(red_dots)

        # 3. 检测UI按钮
        buttons = self.detect_ui_buttons(pixmap)
        all_rois.extend(buttons)

        # 4. 检测图标
        icons = self.detect_icons(pixmap)
        all_rois.extend(icons)

        # 合并重叠的ROI
        merged = self._merge_overlapping_rois(all_rois)

        # 重命名
        for i, roi in enumerate(merged):
            roi.name = f"auto_{i+1:02d}"

        return merged

    def detect_at_point(self, pixmap: QPixmap, x: int, y: int,
                       color_tolerance: int = 30, merge_all: bool = False) -> Optional[ROI]:
        """
        以点击位置为中心，识别颜色相同的最小封闭边界
        使用泛洪填充找到连通的颜色区域

        Args:
            pixmap: 输入图片
            x, y: 点击位置（图片坐标）
            color_tolerance: 颜色容差（0-255，越大包含的颜色范围越广）
            merge_all: 是否合并所有相似颜色的区域（默认只返回点击位置的连通区域）

        Returns:
            ROI或None
        """
        img = self._qpixmap_to_cv2(pixmap)
        if img is None:
            return None

        h, w = img.shape[:2]

        # 限制坐标范围
        x = int(max(0, min(x, w - 1)))
        y = int(max(0, min(y, h - 1)))

        # 在点击位置取样颜色
        seed_color = img[y, x].astype(np.int32)

        # 创建颜色差异掩码 - 计算每个像素与点击位置的颜色距离
        # 使用L2距离（欧几里得距离）
        diff = np.sqrt(np.sum((img.astype(np.float32) - seed_color) ** 2, axis=2))

        # 创建二值掩码：颜色相似的区域为255，其他为0
        mask = (diff <= color_tolerance).astype(np.uint8) * 255

        # 形态学操作清理小噪点
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        # 查找连通区域
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)

        if num_labels < 2:  # 只有背景
            return None

        if merge_all:
            # 合并所有非背景的相似颜色区域
            all_x1, all_y1, all_x2, all_y2 = w, h, 0, 0
            total_area = 0
            valid_count = 0

            for label_id in range(1, num_labels):  # 跳过背景(0)
                x1, y1, w1, h1, area = stats[label_id]
                if area < 20:  # 过滤小噪点
                    continue
                all_x1 = min(all_x1, x1)
                all_y1 = min(all_y1, y1)
                all_x2 = max(all_x2, x1 + w1)
                all_y2 = max(all_y2, y1 + h1)
                total_area += area
                valid_count += 1

            if valid_count == 0:
                return None

            # 创建合并后的ROI
            roi = ROI(x=int(all_x1), y=int(all_y1),
                     width=int(all_x2 - all_x1), height=int(all_y2 - all_y1))
            roi.name = "color_merged"

            # 提取所有相似区域的轮廓
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                # 找到最大的轮廓作为主轮廓
                roi.contour = max(contours, key=cv2.contourArea)

            return roi
        else:
            # 只返回包含点击位置的连通区域
            clicked_label = labels[y, x]
            if clicked_label == 0:  # 背景
                return None

            # 获取该连通区域的边界框
            x1, y1, w1, h1, area = stats[clicked_label]

            # 过滤太小的区域
            if area < 20:
                return None

            # 创建ROI
            roi = ROI(x=int(x1), y=int(y1), width=int(w1), height=int(h1))
            roi.name = "color_blob"

            # 提取该连通区域的轮廓（用于显示）
            component_mask = (labels == clicked_label).astype(np.uint8) * 255
            contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                roi.contour = max(contours, key=cv2.contourArea)

            return roi

    def _merge_overlapping_rois(self, rois: List[ROI], iou_threshold: float = 0.3) -> List[ROI]:
        """合并重叠的ROI"""
        if not rois:
            return []

        # 按面积排序
        sorted_rois = sorted(rois, key=lambda r: r.area, reverse=True)

        merged = []
        for roi in sorted_rois:
            should_merge = False
            for existing in merged:
                iou = self._calculate_iou(roi, existing)
                if iou > iou_threshold:
                    should_merge = True
                    break

            if not should_merge:
                merged.append(roi)

        return merged

    def _calculate_iou(self, roi1: ROI, roi2: ROI) -> float:
        """计算IoU（交并比）"""
        x1 = max(roi1.x, roi2.x)
        y1 = max(roi1.y, roi2.y)
        x2 = min(roi1.right, roi2.right)
        y2 = min(roi1.bottom, roi2.bottom)

        if x2 <= x1 or y2 <= y1:
            return 0.0

        intersection = (x2 - x1) * (y2 - y1)
        union = roi1.area + roi2.area - intersection

        return intersection / union if union > 0 else 0.0

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

    def _cv2_to_qpixmap(self, img: np.ndarray) -> QPixmap:
        """OpenCV格式转QPixmap"""
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb_img.shape
        bytes_per_line = channels * width
        q_image = QImage(rgb_img.data, width, height, bytes_per_line, QImage.Format_RGB888)
        return QPixmap.fromImage(q_image)

    def preview_detection(self, pixmap: QPixmap, rois: List[ROI]) -> QPixmap:
        """生成检测预览图"""
        img = self._qpixmap_to_cv2(pixmap)
        if img is None:
            return pixmap

        for i, roi in enumerate(rois):
            # 圆形用蓝色，其他用绿色
            if hasattr(roi, 'is_circle') and roi.is_circle:
                color = (255, 0, 0)  # 蓝色 - 圆形
                if roi.circle_center and roi.circle_radius:
                    cv2.circle(img, roi.circle_center, roi.circle_radius, color, 2)
            else:
                color = (0, 255, 0)  # 绿色 - 矩形

            # 绘制边界框
            cv2.rectangle(img, (roi.x, roi.y), (roi.right, roi.bottom), color, 2)

            # 绘制标签
            label = roi.name
            cv2.putText(img, label, (roi.x, roi.y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        # 确保图像是3通道BGR格式
        if len(img.shape) == 3 and img.shape[2] == 3:
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        elif len(img.shape) == 2:
            # 灰度图像转为RGB
            rgb_img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        else:
            return pixmap  # 不支持的格式，返回原始pixmap

        height, width, channels = rgb_img.shape
        bytes_per_line = channels * width
        q_image = QImage(rgb_img.data, width, height, bytes_per_line, QImage.Format_RGB888)

        return QPixmap.fromImage(q_image)
