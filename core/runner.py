"""备份执行器 - 把「备份、自动清洗、云盘上传」编排成一次完整流程
供 GUI 后台线程（带日志回调）与无界面 --backup 模式（命令行）共用。
"""
import traceback

from . import config as cfg
from . import cleaner
from .backup import make_backup
from . import scheduler  # noqa: F401  (确保模块可用)


def run_task(task=None, log=print, progress_every=10):
    """执行单个备份任务。
    task: 任务配置 dict；缺省取 config.json 的 tasks[0]
    log: 日志回调 log(message)
    返回 (ok, summary_dict)。
    """
    task = task or cfg.load()["tasks"][0]

    def logf(*a):
        try:
            log(" ".join(str(x) for x in a))
        except Exception:
            pass

    step = 0
    result = {"backup": None, "cleaned": 0, "kept": 0, "cloud": None, "uploaded": False}

    # 1) 备份
    logf("开始备份…")
    path = make_backup(task.get("name", "方舟存档"),
                       task.get("src_dir", ""),
                       task.get("backup_dir", ""))
    result["backup"] = path
    logf(f"✅ 备份完成: {path}")

    # 2) 自动清洗
    retention = task.get("retention", {})
    if retention.get("auto_clean", True):
        plan, total = cleaner.plan_clean(task.get("backup_dir", ""), retention,
                                         task.get("name"))
        if plan:
            logf(f"🧹 将清理 {len(plan)} 份（保留最近 {retention.get('keep_count',10)} 份）")
        deleted, kept, _ = cleaner.clean(task.get("backup_dir", ""), retention,
                                         task.get("name"))
        result["cleaned"], result["kept"] = deleted, kept
        logf(f"🗑️ 已清理 {deleted} 份，当前保留 {kept} 份")
    else:
        logf("自动清洗已关闭，未删除任何备份")

    # 3) 云盘上传
    cloud_cfg = task.get("cloud", {})
    if cloud_cfg.get("enabled") and cloud_cfg.get("provider") and cloud_cfg.get("config"):
        try:
            import cloud as cloud_mod
            cls = cloud_mod.get_plugin(cloud_cfg["provider"])
            if cls:
                inst = cls(**cloud_cfg.get("config", {}))
                ok, msg = inst.validate()
                if not ok:
                    logf(f"⚠️ 云盘凭证不完整: {', '.join(msg)}，跳过上传")
                else:
                    logf(f"☁️ 上传到 {cls.name} …")
                    remote = inst.upload(path, cloud_cfg["config"].get("remote_dir", ""))
                    result["cloud"], result["uploaded"] = remote, True
                    logf(f"☁️ 已上传: {remote}")
            else:
                logf(f"⚠️ 未找到云盘插件: {cloud_cfg['provider']}")
        except Exception as e:
            logf(f"⚠️ 云盘上传失败: {e}")
    else:
        logf("云盘上传未启用，跳过")

    return True, result


def run_all_logged(log=print):
    """执行 config.json 中所有任务（便于计划任务一次跑完）。"""
    cfg_data = cfg.load()
    all_ok = True
    for i, task in enumerate(cfg_data["tasks"]):
        try:
            log(f"===== 任务 {i + 1}/{len(cfg_data['tasks'])}: {task.get('name','')} =====")
            run_task(task, log=log)
        except FileNotFoundError as e:
            log(f"❌ {e}")
            all_ok = False
        except Exception as e:
            log(f"❌ 任务失败: {e}")
            if __debug__:
                log(traceback.format_exc(limit=3))
            all_ok = False
    return all_ok
