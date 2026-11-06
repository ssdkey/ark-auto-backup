#!/usr/bin/env python3
"""程序入口
- 无参数：启动 GUI（交互使用）
- --backup：无界面执行一次全部备份任务（供 Windows 计划任务调用）
"""
import os
import sys

# 确保能导入本地包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _cli_backup():
    """无界面备份：依次执行 config.json 中所有任务，日志写回控制台/文件。"""
    from core import config as cfg
    from core import runner
    from datetime import datetime

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_lines = [f"[{ts}] 自动备份开始"]

    def safe_print(s):
        """stdout 可能是 GBK（Windows 控制台），把编码不了的字符替换而非崩溃"""
        try:
            print(s)
        except UnicodeEncodeError:
            print(s.encode("gbk", errors="replace").decode("gbk", errors="replace"))

    def log(msg):
        # 界面版日志保留 emoji；文件用 UTF-8 完整记录
        try:
            safe_print(msg)
        except Exception:
            pass
        log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    ok = True
    try:
        ok = runner.run_all_logged(log)
    except Exception as e:
        log(f"运行异常: {e}")
        ok = False

    log_lines.append(f"[{'成功' if ok else '失败'}] 自动备份结束")
    # 把本次运行日志追加到日志文件（UTF-8，便于排查）
    try:
        log_path = os.path.join(cfg.config_dir(), "backup_log.txt")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(log_lines) + "\n")
    except OSError:
        pass

    return 0 if ok else 1


def _entry():
    args = [a.lower() for a in sys.argv[1:]]
    if "--backup" in args:
        sys.exit(_cli_backup())
    from gui.main_window import main
    main()


if __name__ == "__main__":
    _entry()
