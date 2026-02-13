# -*- coding: utf-8 -*-
"""
应用程序设置
"""

import os
import json


class Settings:
    """应用设置"""
    
    DEFAULTS = {
        "output_dir": "./res_output",
        "naming_prefix": "target_",
        "image_format": "png",
        "image_quality": 95,
        "auto_copy_code": True,
        "show_labels": True,
        "show_handles": True,
        "snap_to_grid": False,
        "grid_size": 10,
        "default_export_format": "json"
    }
    
    def __init__(self):
        self.config_file = "config.json"
        self.settings = self.DEFAULTS.copy()
        self.load()
    
    def load(self):
        """加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.settings.update(loaded)
            except Exception as e:
                print(f"加载配置失败: {e}")
    
    def save(self):
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    def get(self, key: str, default=None):
        """获取设置项"""
        return self.settings.get(key, default)
    
    def set(self, key: str, value):
        """设置配置项"""
        self.settings[key] = value
        self.save()
    
    def reset(self):
        """重置为默认"""
        self.settings = self.DEFAULTS.copy()
        self.save()
