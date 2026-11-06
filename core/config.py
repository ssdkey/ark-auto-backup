"""配置读写模块 - 负责 config.json 的加载与保存
- 提供默认配置结构（多任务）
- load() / save() / 更新单个任务
- 处理 PyInstaller 冻结模式：配置放在 exe 同目录（可写），而非临时解包目录
"""
import json
import os
import sys
import threading

# 默认配置结构
DEFAULT_CONFIG = {
    "tasks": [
        {
            "name": "方舟存档",
            "src_dir": "",
            "backup_dir": "",
            "retention": {
                "mode": "count",      # count | days | both
                "keep_count": 10,
                "keep_days": 30,
                "min_keep": 5,
                "auto_clean": True,
            },
            "cloud": {
                "provider": "",       # 云盘插件 key，如 webdav
                "enabled": False,
                "config": {},         # 该云盘的凭证/参数
            },
        }
    ],
    "app": {
        "theme": "dark",
        "schedule_enabled": False,
        "schedule_time": "03:00",
    },
}

_lock = threading.Lock()


def config_dir():
    """返回可写的配置文件目录。
    - 冻结(exe)时：exe 所在目录，便于用户找到和备份
    - 非冻结(源码)时：项目根目录
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def config_path():
    return os.path.join(config_dir(), "config.json")


def _deep_merge(base, override):
    """递归合并 override 到 base（不改变 base 原对象）。"""
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            out[k] = _deep_merge(base[k], v)
        else:
            out[k] = v
    return out


def load():
    """加载 config.json；文件缺失时返回默认配置并落盘。"""
    path = config_path()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return _deep_merge(DEFAULT_CONFIG, data)
        except (json.JSONDecodeError, OSError, ValueError):
            # 文件损坏：先备份原文件，避免覆盖用户数据，再落盘默认
            try:
                bak = path + ".bak"
                with open(path, "r", encoding="utf-8", errors="replace") as src, \
                     open(bak, "w", encoding="utf-8") as dst:
                    dst.write(src.read())
            except OSError:
                pass
    # 缺文件或解析失败：落盘一份默认配置
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # 深拷贝
    save(cfg)
    return cfg


def save(cfg):
    """保存配置到 config.json（线程安全，防止并发写坏）。"""
    path = config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    with _lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_task(index=0):
    """加载指定索引的任务配置。"""
    return load()["tasks"][index]


def default_task():
    """返回默认任务结构（深拷贝）"""
    return json.loads(json.dumps(DEFAULT_CONFIG["tasks"][0]))


def get_schedule(cfg=None):
    cfg = cfg or load()
    return cfg.get("app", {}).get("schedule_enabled", False), \
        cfg.get("app", {}).get("schedule_time", "03:00")


def set_schedule(enabled, time_str, cfg=None):
    """更新计划任务配置并保存。返回 (enabled, time)。"""
    cfg = cfg or load()
    cfg.setdefault("app", {})["schedule_enabled"] = bool(enabled)
    cfg["app"]["schedule_time"] = time_str
    save(cfg)
    return cfg["app"]["schedule_enabled"], cfg["app"]["schedule_time"]
