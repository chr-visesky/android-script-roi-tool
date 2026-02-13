# -*- coding: utf-8 -*-
"""
超像素分割模块 - 适合游戏UI切图
基于SLIC算法，把图像切成边界贴合的小块
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional, Set
from dataclasses import dataclass
from PyQt5.QtGui import QPixmap
from ..models.roi import ROI


@dataclass
class SuperpixelRegion:
    """超像素区域"""
    label: int
    mask: np.ndarray  # 二值mask
    contour: np.ndarray  # 轮廓
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    area: int
    center: Tuple[int, int]  # 中心点
    avg_color: Tuple[float, float, float]  # 平均颜色


class SuperpixelSegmenter:
    """超像素分割器"""

    def __init__(self, region_size: int = 30, ruler: float = 10.0):
        """
        初始化

        Args:
            region_size: 超像素区域大小（像素数）
            ruler: 颜色与空间距离的权衡参数（越大越平滑）
        """
        self.region_size = region_size
        self.ruler = ruler
        self.slic = None
        self.labels = None
        self.regions: List[SuperpixelRegion] = []

    def segment(self, pixmap: QPixmap) -> List[SuperpixelRegion]:
        """
        执行超像素分割

        Returns:
            超像素区域列表
        """
        img = self._qpixmap_to_cv2(pixmap)
        if img is None:
            return []

        # 优先使用scikit-image（效果更好），失败时回退到OpenCV
        try:
            self.labels = self._segment_skimage(img)
            print("[Superpixel] 使用 scikit-image SLIC (效果更好)")
        except Exception as e:
            print(f"[Superpixel] scikit-image 失败 ({e}), 尝试 OpenCV")
            self.labels = self._segment_opencv(img)

        if self.labels is None:
            return []

        # 提取每个超像素区域
        self.regions = self._extract_regions(img, self.labels)

        return self.regions

    def _segment_opencv(self, img: np.ndarray) -> np.ndarray:
        """使用OpenCV ximgproc进行SLIC分割"""
        lab_img = cv2.cvtColor(img, cv2.COLOR_BGR2Lab)

        try:
            slic = cv2.ximgproc.createSuperpixelSLIC(
                lab_img,
                algorithm=cv2.ximgproc.SLICO,
                region_size=self.region_size,
                ruler=self.ruler
            )
        except cv2.error:
            slic = cv2.ximgproc.createSuperpixelSLIC(
                lab_img,
                algorithm=cv2.ximgproc.SLIC,
                region_size=self.region_size,
                ruler=self.ruler
            )

        slic.iterate(10)
        return slic.getLabels()

    def _segment_skimage(self, img: np.ndarray) -> np.ndarray:
        """使用scikit-image进行SLIC分割（备选）"""
        try:
            from skimage.segmentation import slic as sk_slic
            from skimage.util import img_as_float

            # 转换为float并归一化到[0, 1]
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            float_img = img_as_float(rgb_img)

            # 计算n_segments (基于图片大小和region_size)
            h, w = img.shape[:2]
            n_segments = max((h * w) // (self.region_size ** 2), 10)

            # 执行SLIC - 优化参数以获得更好的边界保持
            labels = sk_slic(
                float_img,
                n_segments=n_segments,
                compactness=15.0,  # 增加紧致性，区域更均匀
                sigma=0.5,  # 降低平滑，保持更多边界细节
                start_label=0,
                max_num_iter=20  # 增加迭代次数，收敛更好
            )

            return labels.astype(np.int32)

        except ImportError:
            raise RuntimeError(
                "需要安装 scikit-image:\n"
                "  uv pip install scikit-image\n"
                "或安装完整OpenCV:\n"
                "  uv pip install opencv-contrib-python"
            )

    def _extract_regions(self, img: np.ndarray, labels: np.ndarray) -> List[SuperpixelRegion]:
        """从标签图提取超像素区域"""
        regions = []
        unique_labels = np.unique(labels)

        for label in unique_labels:
            if label < 0:  # 跳过无效标签
                continue

            # 创建mask
            mask = (labels == label).astype(np.uint8) * 255

            # 找轮廓
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue

            contour = max(contours, key=cv2.contourArea)

            # 边界框
            x, y, w, h = cv2.boundingRect(contour)

            # 面积
            area = cv2.contourArea(contour)

            # 中心点
            M = cv2.moments(contour)
            # 检查m00是否有效（大于0且不是NaN/无穷大）
            m00 = M["m00"]
            if m00 > 0 and np.isfinite(m00):
                cx = int(M["m10"] / m00)
                cy = int(M["m01"] / m00)
            else:
                cx, cy = x + w // 2, y + h // 2

            # 平均颜色
            mask_bool = mask > 0
            if len(img.shape) == 3 and img.shape[2] >= 3:
                # 处理前3个通道（BGR或RGB）
                avg_color = (
                    float(np.mean(img[:, :, 0][mask_bool])),
                    float(np.mean(img[:, :, 1][mask_bool])),
                    float(np.mean(img[:, :, 2][mask_bool]))
                )
            else:
                avg_color = (128.0, 128.0, 128.0)

            region = SuperpixelRegion(
                label=int(label),
                mask=mask,
                contour=contour,
                bbox=(x, y, w, h),
                area=int(area),
                center=(cx, cy),
                avg_color=avg_color
            )
            regions.append(region)

        # 按面积排序（大到小）
        regions.sort(key=lambda r: r.area, reverse=True)

        return regions

    def get_region_at_point(self, x: int, y: int) -> Optional[SuperpixelRegion]:
        """获取指定点所在的超像素区域"""
        if self.labels is None:
            return None

        h, w = self.labels.shape
        if x < 0 or x >= w or y < 0 or y >= h:
            return None

        label = self.labels[y, x]
        for region in self.regions:
            if region.label == label:
                return region
        return None

    def get_regions_in_rect(self, x1: int, y1: int, x2: int, y2: int) -> List[SuperpixelRegion]:
        """获取矩形框内的所有超像素区域"""
        if self.labels is None:
            return []

        # 确保坐标顺序
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)

        # 裁剪到有效范围
        h, w = self.labels.shape
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)

        # 获取区域内的所有标签
        region_labels = self.labels[y1:y2, x1:x2]
        unique_labels = set(np.unique(region_labels))

        # 找到对应的区域
        regions = []
        for region in self.regions:
            if region.label in unique_labels:
                regions.append(region)

        return regions

    def merge_regions(self, regions: List[SuperpixelRegion]) -> Optional[ROI]:
        """
        合并多个超像素区域为一个ROI

        Args:
            regions: 要合并的区域列表

        Returns:
            合并后的ROI
        """
        if not regions:
            return None

        if len(regions) == 1:
            r = regions[0]
            roi = ROI(x=r.bbox[0], y=r.bbox[1], width=r.bbox[2], height=r.bbox[3])
            roi.contour = r.contour
            roi.is_segmented = True
            return roi

        # 合并所有mask
        merged_mask = np.zeros_like(regions[0].mask)
        for r in regions:
            merged_mask = cv2.bitwise_or(merged_mask, r.mask)

        # 找合并后的轮廓
        contours, _ = cv2.findContours(merged_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        best_contour = max(contours, key=cv2.contourArea)
        bx, by, bw, bh = cv2.boundingRect(best_contour)

        roi = ROI(x=bx, y=by, width=bw, height=bh)
        roi.name = f"superpixel_merge_{len(regions)}"
        roi.is_segmented = True
        roi.contour = best_contour

        return roi

    def filter_regions(self,
                      min_area: int = 100,
                      max_area: Optional[int] = None,
                      min_wh: int = 10) -> List[SuperpixelRegion]:
        """
        过滤超像素区域

        Args:
            min_area: 最小面积
            max_area: 最大面积（None表示不限制）
            min_wh: 最小宽高

        Returns:
            过滤后的区域列表
        """
        filtered = []
        for r in self.regions:
            if r.area < min_area:
                continue
            if max_area and r.area > max_area:
                continue
            if r.bbox[2] < min_wh or r.bbox[3] < min_wh:
                continue
            filtered.append(r)
        return filtered

    def visualize(self, img: np.ndarray, alpha: float = 0.5) -> np.ndarray:
        """可视化超像素分割结果"""
        if self.labels is None:
            return img

        # 创建彩色标签图
        h, w = self.labels.shape
        vis = np.zeros((h, w, 3), dtype=np.uint8)

        # 为每个标签分配随机颜色
        np.random.seed(42)
        colors = np.random.randint(0, 255, size=(np.max(self.labels) + 2, 3), dtype=np.uint8)

        for i in range(h):
            for j in range(w):
                label = self.labels[i, j]
                if label >= 0:
                    vis[i, j] = colors[label]

        # 混合
        result = cv2.addWeighted(img, 1 - alpha, vis, alpha, 0)

        # 画边界
        boundary = self._get_boundary_mask()
        result[boundary > 0] = [0, 0, 255]  # 红色边界

        return result

    def _get_boundary_mask(self) -> np.ndarray:
        """获取超像素边界mask"""
        if self.labels is None:
            return np.zeros((10, 10), dtype=np.uint8)

        h, w = self.labels.shape
        boundary = np.zeros((h, w), dtype=np.uint8)

        # 检查每个像素的4邻域
        for i in range(1, h - 1):
            for j in range(1, w - 1):
                label = self.labels[i, j]
                # 如果邻居有不同标签，就是边界
                if (self.labels[i-1, j] != label or
                    self.labels[i+1, j] != label or
                    self.labels[i, j-1] != label or
                    self.labels[i, j+1] != label):
                    boundary[i, j] = 255

        return boundary

    def _qpixmap_to_cv2(self, pixmap: QPixmap) -> Optional[np.ndarray]:
        """QPixmap转OpenCV格式"""
        if pixmap.isNull():
            return None

        from PyQt5.QtGui import QImage

        image = pixmap.toImage()
        if image.format() != QImage.Format_RGB888:
            image = image.convertToFormat(QImage.Format_RGB888)

        width = image.width()
        height = image.height()
        ptr = image.bits()
        ptr.setsize(image.byteCount())

        # 创建副本确保数据安全，避免悬空指针
        arr = np.array(ptr).reshape(height, width, 3).copy()
        arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

        return arr


class SuperpixelMergeTool:
    """超像素合并工具 - 支持框选和连点合并"""

    def __init__(self, segmenter: SuperpixelSegmenter):
        self.segmenter = segmenter
        self.selected_labels: Set[int] = set()
        self.merged_rois: List[ROI] = []

    def clear_selection(self):
        """清除选择"""
        self.selected_labels.clear()

    def click_select(self, x: int, y: int, additive: bool = False) -> Optional[SuperpixelRegion]:
        """
        点击选择超像素

        Args:
            x, y: 点击坐标
            additive: 是否 additive 模式（True=添加，False=替换）

        Returns:
            选中的区域
        """
        region = self.segmenter.get_region_at_point(x, y)
        if region is None:
            if not additive:
                self.selected_labels.clear()
            return None

        if additive:
            if region.label in self.selected_labels:
                self.selected_labels.remove(region.label)
            else:
                self.selected_labels.add(region.label)
        else:
            self.selected_labels.clear()
            self.selected_labels.add(region.label)

        return region

    def rect_select(self, x1: int, y1: int, x2: int, y2: int) -> List[SuperpixelRegion]:
        """框选区域内的所有超像素"""
        regions = self.segmenter.get_regions_in_rect(x1, y1, x2, y2)
        for r in regions:
            self.selected_labels.add(r.label)
        return regions

    def get_selected_regions(self) -> List[SuperpixelRegion]:
        """获取所有选中的区域"""
        return [r for r in self.segmenter.regions if r.label in self.selected_labels]

    def merge_selected(self) -> Optional[ROI]:
        """合并选中的区域"""
        regions = self.get_selected_regions()
        if len(regions) < 2:
            return None

        roi = self.segmenter.merge_regions(regions)
        if roi:
            self.merged_rois.append(roi)
            self.selected_labels.clear()
        return roi

    def auto_merge_all(self,
                      min_area: int = 500,
                      color_threshold: float = 30.0) -> List[ROI]:
        """
        自动合并相似颜色的相邻超像素

        Args:
            min_area: 最小合并面积
            color_threshold: 颜色相似度阈值

        Returns:
            合并后的ROI列表
        """
        regions = list(self.segmenter.regions)
        merged = [False] * len(regions)
        rois = []

        for i, r1 in enumerate(regions):
            if merged[i] or r1.area >= min_area:
                continue

            # 找颜色相似的相邻区域
            to_merge = [r1]
            merged[i] = True

            for j, r2 in enumerate(regions[i+1:], i+1):
                if merged[j]:
                    continue

                # 颜色距离
                color_dist = np.sqrt(sum((a - b) ** 2
                    for a, b in zip(r1.avg_color, r2.avg_color)))

                if color_dist < color_threshold:
                    # 检查是否相邻（简化：中心点距离）
                    dx = r1.center[0] - r2.center[0]
                    dy = r1.center[1] - r2.center[1]
                    dist = np.sqrt(dx * dx + dy * dy)

                    if dist < max(r1.bbox[2], r1.bbox[3]) + max(r2.bbox[2], r2.bbox[3]):
                        to_merge.append(r2)
                        merged[j] = True

            if len(to_merge) >= 2:
                roi = self.segmenter.merge_regions(to_merge)
                if roi:
                    rois.append(roi)

        return rois
