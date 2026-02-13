# -*- coding: utf-8 -*-
"""
截图管理模块
支持ADB截图和PC截图，增强雷电模拟器支持
"""

import subprocess
import os
import tempfile
import time
import glob
from typing import Optional, List
from PyQt5.QtGui import QPixmap


class ScreenshotManager:
    """截图管理器"""

    # 雷电模拟器常见安装路径
    LD_PLAYER_PATHS = [
        r"C:\leidian\LDPlayer9",
        r"C:\leidian\LDPlayer4",
        r"C:\leidian\LDPlayer",
        r"C:\Program Files\leidian\LDPlayer9",
        r"C:\Program Files\leidian\LDPlayer4",
        r"C:\Program Files (x86)\leidian\LDPlayer9",
        r"D:\leidian\LDPlayer9",
        r"D:\leidian\LDPlayer4",
        r"D:\leidian\LDPlayer",
        r"E:\leidian\LDPlayer9",
    ]

    # 雷电模拟器常见ADB端口
    LD_PORTS = [5555, 5557, 5559, 5561, 5563, 5565]

    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.adb_path = self._find_adb()
        self.adb_available = self.adb_path is not None
        print(f"[ADB] Path: {self.adb_path}")
        print(f"[ADB] Available: {self.adb_available}")

    def _get_builtin_adb_path(self) -> Optional[str]:
        """获取内置ADB的路径"""
        # 获取项目根目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 向上两级到项目根目录 (src/core -> src -> root)
        project_root = os.path.dirname(os.path.dirname(current_dir))

        # 内置ADB路径
        builtin_adb = os.path.join(project_root, "tools", "platform-tools", "adb.exe")

        if os.path.exists(builtin_adb):
            print(f"[ADB] Found builtin ADB: {builtin_adb}")
            return builtin_adb

        return None

    def _find_adb(self) -> Optional[str]:
        """查找ADB可执行文件"""
        # 0. 优先使用内置ADB
        builtin_adb = self._get_builtin_adb_path()
        if builtin_adb:
            return builtin_adb

        # 1. 检查系统PATH中的adb
        try:
            result = subprocess.run(
                ['adb', 'version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return 'adb'
        except:
            pass

        # 2. 查找雷电模拟器自带的adb
        for ld_path in self.LD_PLAYER_PATHS:
            adb_exe = os.path.join(ld_path, "adb.exe")
            if os.path.exists(adb_exe):
                print(f"[ADB] 找到雷电模拟器ADB: {adb_exe}")
                return adb_exe

            # 也可能在子目录中
            for adb_sub in ['.', 'bin', 'tools']:
                adb_exe = os.path.join(ld_path, adb_sub, "adb.exe")
                if os.path.exists(adb_exe):
                    print(f"[ADB] 找到雷电模拟器ADB: {adb_exe}")
                    return adb_exe

        # 3. 全盘搜索（仅Windows）
        try:
            for drive in ['C:', 'D:', 'E:']:
                pattern = f"{drive}\\\**\\adb.exe"
                matches = glob.glob(pattern, recursive=True)
                for match in matches:
                    if 'leidian' in match.lower() or 'ldplayer' in match.lower():
                        print(f"[ADB] 找到ADB: {match}")
                        return match
        except Exception as e:
            print(f"[ADB] 全盘搜索失败: {e}")

        return None

    def _run_adb(self, args: List[str], timeout: int = 10, binary: bool = False) -> tuple:
        """
        运行ADB命令

        Args:
            args: ADB命令参数
            timeout: 超时时间
            binary: 是否返回二进制数据（截图时使用）

        Returns:
            (returncode, stdout, stderr)
        """
        if not self.adb_path:
            return -1, b"" if binary else "", "ADB not found"

        try:
            cmd = [self.adb_path] + args
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=not binary,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return -1, b"" if binary else "", str(e)

    def get_devices(self) -> List[str]:
        """获取连接的设备列表"""
        returncode, stdout, stderr = self._run_adb(['devices'])

        if returncode != 0:
            print(f"[ADB] 获取设备失败: {stderr}")
            return []

        devices = []
        lines = stdout.strip().split('\n')[1:]  # 跳过标题行
        for line in lines:
            if line.strip() and '\t' in line:
                parts = line.split('\t')
                device_id = parts[0].strip()
                status = parts[1].strip() if len(parts) > 1 else ""
                if status == 'device':
                    devices.append(device_id)

        return devices

    def connect_device(self, host: str = "127.0.0.1", port: int = 5555) -> bool:
        """
        通过adb connect连接设备

        Args:
            host: 主机地址
            port: 端口号

        Returns:
            是否连接成功
        """
        print(f"[ADB] 尝试连接 {host}:{port}")
        returncode, stdout, stderr = self._run_adb(
            ['connect', f'{host}:{port}'],
            timeout=10
        )

        stdout_str = stdout or ""
        success = returncode == 0 and ('connected' in stdout_str.lower() or 'already connected' in stdout_str.lower())
        if success:
            print(f"[ADB] 连接成功: {host}:{port}")
        else:
            print(f"[ADB] 连接失败: {stderr or stdout}")

        return success

    def connect_ld_player(self) -> bool:
        """
        自动连接雷电模拟器

        Returns:
            是否连接成功
        """
        try:
            print("[ADB] 尝试连接雷电模拟器...")

            # 尝试常见端口
            for port in self.LD_PORTS:
                if self.connect_device("127.0.0.1", port):
                    return True

            # 如果都不行，尝试从模拟器配置文件中读取端口
            ld_ports = self._get_ld_player_ports_from_config()
            for port in ld_ports:
                if port not in self.LD_PORTS:
                    if self.connect_device("127.0.0.1", port):
                        return True

            print("[ADB] 无法连接到雷电模拟器，请检查:")
            print("  1. 雷电模拟器是否已启动")
            print("  2. 雷电模拟器的ADB调试是否开启")
            print("  3. 尝试手动运行: adb connect 127.0.0.1:5555")

            return False
        except Exception as e:
            print(f"[ADB] 连接雷电模拟器异常: {e}")
            return False

    def _get_ld_player_ports_from_config(self) -> List[int]:
        """从雷电模拟器配置文件中读取端口"""
        ports = []

        for ld_path in self.LD_PLAYER_PATHS:
            # 查找配置文件
            config_paths = [
                os.path.join(ld_path, "vms", "config", "leidian0.config"),
                os.path.join(ld_path, "vms", "config", "leidian1.config"),
                os.path.join(ld_path, "vms", "leidian0", "leidian0.config"),
            ]

            for config_path in config_paths:
                if os.path.exists(config_path):
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # 查找adb端口配置
                            if 'adb_port' in content:
                                import re
                                matches = re.findall(r'adb_port[=:]\s*(\d+)', content)
                                for match in matches:
                                    ports.append(int(match))
                    except Exception as e:
                        print(f"[ADB] 读取配置失败: {e}")

        return ports

    def capture_adb(self, device_id: Optional[str] = None) -> Optional[QPixmap]:
        """
        使用ADB截图

        Args:
            device_id: 设备ID，None则使用第一个可用设备

        Returns:
            QPixmap对象或None
        """
        if not self.adb_available:
            print("[ADB] ADB不可用")
            return None

        # 如果没有指定设备，尝试获取一个
        if not device_id:
            devices = self.get_devices()
            if not devices:
                # 尝试连接雷电模拟器
                if self.connect_ld_player():
                    devices = self.get_devices()
                if not devices:
                    print("[ADB] 没有可用设备")
                    return None
            device_id = devices[0]

        print(f"[ADB] 截图设备: {device_id}")

        try:
            # 构建命令
            args = ['-s', device_id, 'shell', 'screencap', '-p']

            # 执行截图（使用二进制模式）
            returncode, stdout, stderr = self._run_adb(args, timeout=15, binary=True)

            if returncode != 0:
                print(f"[ADB] 截图失败: {stderr}")
                return None

            if not stdout:
                print("[ADB] 截图返回空数据")
                return None

            # 保存临时文件
            timestamp = int(time.time())
            temp_path = os.path.join(self.temp_dir, f'adb_screenshot_{timestamp}.png')

            # ADB输出可能有Windows换行符问题，需要处理
            data = stdout.replace(b'\r\n', b'\n')

            with open(temp_path, 'wb') as f:
                f.write(data)

            # 加载图片
            pixmap = QPixmap(temp_path)

            # 清理临时文件
            try:
                os.remove(temp_path)
            except:
                pass

            if pixmap.isNull():
                print("[ADB] 截图加载失败")
                return None

            print(f"[ADB] 截图成功: {pixmap.width()}x{pixmap.height()}")
            return pixmap

        except Exception as e:
            print(f"[ADB] 截图异常: {e}")
            import traceback
            traceback.print_exc()
            return None

    def capture_pc_screen(self) -> Optional[QPixmap]:
        """
        截取PC屏幕（需要PyQt5的grabWindow）
        注意：此功能需要QApplication的屏幕对象
        """
        try:
            from PyQt5.QtWidgets import QApplication
            from PyQt5.QtGui import QScreen

            app = QApplication.instance()
            if not app:
                print("[PC] QApplication not available")
                return None

            screen = app.primaryScreen()
            if screen:
                pixmap = screen.grabWindow(0)  # 0表示整个屏幕
                if pixmap and not pixmap.isNull():
                    print(f"[PC] 屏幕截图: {pixmap.width()}x{pixmap.height()}")
                    return pixmap
                else:
                    print("[PC] 截图返回空图像")
            else:
                print("[PC] 无法获取屏幕对象")
        except Exception as e:
            print(f"[PC] 截图失败: {e}")
            import traceback
            traceback.print_exc()
        return None

    def quick_capture(self) -> Optional[QPixmap]:
        """
        快速截图
        优先使用ADB，如果失败则使用PC截图
        """
        # 先尝试ADB
        if self.adb_available:
            devices = self.get_devices()
            if not devices:
                # 尝试连接雷电模拟器
                self.connect_ld_player()
                devices = self.get_devices()

            if devices:
                pixmap = self.capture_adb(devices[0])
                if pixmap and not pixmap.isNull():
                    return pixmap

        # 尝试PC截图
        return self.capture_pc_screen()

    def capture_ld_player(self, index: int = 0) -> Optional[QPixmap]:
        """
        截图雷电模拟器

        Args:
            index: 模拟器实例索引，默认0

        Returns:
            QPixmap对象或None
        """
        try:
            print(f"[LD] 截图雷电模拟器实例 {index}")

            if not self.adb_available:
                print("[LD] ADB不可用，尝试自动查找...")
                self.adb_path = self._find_adb()
                self.adb_available = self.adb_path is not None

            if not self.adb_available:
                print("[LD] 无法找到ADB")
                return None

            # 先尝试连接
            connected = self.connect_ld_player()

            # 获取设备列表
            devices = self.get_devices()

            if not devices:
                if not connected:
                    print("[LD] 没有检测到设备，请确保雷电模拟器已启动")
                return None

            # 如果有多个设备，尝试找到雷电模拟器
            for device in devices:
                if 'emulator-' in device or '127.0.0.1' in device:
                    print(f"[LD] 使用设备: {device}")
                    return self.capture_adb(device)

            # 使用第一个可用设备
            return self.capture_adb(devices[0])

        except Exception as e:
            print(f"[LD] 截图异常: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_ld_player_devices(self) -> List[str]:
        """获取雷电模拟器设备列表"""
        all_devices = self.get_devices()
        ld_devices = []
        for device in all_devices:
            # 雷电模拟器通常以 emulator- 或 127.0.0.1 开头
            if 'emulator-' in device or '127.0.0.1' in device:
                ld_devices.append(device)
        return ld_devices

    def get_adb_info(self) -> dict:
        """获取ADB信息"""
        return {
            'adb_path': self.adb_path,
            'adb_available': self.adb_available,
            'devices': self.get_devices(),
            'ld_devices': self.get_ld_player_devices(),
        }
