# -*- coding: utf-8 -*-
"""
工具函数
"""

import os
import random


def generate_color() -> str:
    """生成随机颜色"""
    colors = [
        "#FF5733", "#33FF57", "#3357FF", "#FF33F6",
        "#F6FF33", "#33FFF6", "#FF8033", "#8033FF",
        "#33FF80", "#FF3380", "#80FF33", "#3380FF"
    ]
    return random.choice(colors)


def ensure_dir(path: str) -> bool:
    """确保目录存在"""
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except:
        return False


def get_file_extension(filename: str) -> str:
    """获取文件扩展名"""
    return os.path.splitext(filename)[1].lower()


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
