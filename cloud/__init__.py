"""云盘插件包
导入本包即自动注册所有内置插件（@register）。
新增插件：在 cloud/ 下新建一个 .py 并 @register，再把模块 import 到这里即可被自动收集。
"""
from .base import (
    CloudUploader,
    Field,
    register,
    REGISTRY,
)

# 显式导入以触发 @register（保证 PyInstaller 能收集到模块）
from . import aliyun  # noqa: E402,F401
from . import baidu  # noqa: E402,F401
from . import onedrive  # noqa: E402,F401
from . import webdav  # noqa: E402,F401

__all__ = [
    "CloudUploader",
    "Field",
    "register",
    "REGISTRY",
]


def all_plugins():
    """返回所有已注册插件类列表（按 key 排序）"""
    return REGISTRY.all()


def get_plugin(key):
    """按 key 返回插件类，不存在返回 None"""
    return REGISTRY.get(key)
