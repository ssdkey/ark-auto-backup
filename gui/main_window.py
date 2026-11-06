"""GUI 主窗口 - CustomTkinter，暗色现代风格
集成：
- 备份 / 恢复 / 自动清洗
- config.json 持久化（加载 + 自动保存）
- 云盘设置入口（插件化上传，备份后自动上传）
- Windows 计划任务（每日定时无界面备份）
"""
import os
import threading
import tkinter.filedialog as fd
from datetime import datetime

import customtkinter as ctk

from core import backup as bk
from core import cleaner as cl
from core import config as cfg
from core import restore as rs
from core import runner
from core import scheduler
from gui.cloud_page import CloudPage

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("方舟自动备份工具")
        self.geometry("880x700")
        self.minsize(760, 580)

        # 从 config.json 加载当前任务（单任务模式取 tasks[0]）
        self.cfg = cfg.load()
        self.task = self.cfg["tasks"][0]
        self.name = self.task.get("name", "方舟存档")
        self.retention = self.task.get(
            "retention", cfg.DEFAULT_CONFIG["tasks"][0]["retention"])
        self._busy = False

        self._build_ui()
        self._load_into_ui()
        self._refresh_schedule_label()
        self._log("程序已启动，就绪。配置已从 config.json 加载。")

    # ---------- UI 构建 ----------
    def _build_ui(self):
        self.top = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray90", "gray15"))
        self.top.pack(fill="x")
        ctk.CTkLabel(self.top, text="🔧 方舟自动备份",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(side="left", padx=20, pady=14)
        self.status_label = ctk.CTkLabel(self.top, text="● 就绪",
                                         text_color="#4ade80", font=ctk.CTkFont(size=13))
        self.status_label.pack(side="right", padx=20)

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=16, pady=12)

        self._make_card("📂 备份任务", self._init_task_card)
        self._make_card("🗑️ 保留策略", self._init_strategy_card)
        self._make_card("🕒 计划任务", self._init_schedule_card)
        self._make_card("⚡ 操作", self._init_button_card)

        self._make_card("📜 日志", self._init_log_card)

    def _make_card(self, title, init_fn):
        card = ctk.CTkFrame(self.body, corner_radius=12, fg_color=("white", "gray17"))
        card.pack(fill="x", pady=6)
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=15, weight="bold"),
                     anchor="w").pack(fill="x", padx=16, pady=(12, 4))
        init_fn(card)
        return card

    def _init_task_card(self, card):
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(row, text="备份源目录").grid(row=0, column=0, sticky="w", pady=3)
        self.src_var = ctk.StringVar()
        ctk.CTkEntry(row, textvariable=self.src_var,
                     placeholder_text="选择方舟存档目录 (.../ShooterGame/Saved)").grid(row=0, column=1, sticky="ew", padx=8)
        ctk.CTkButton(row, text="浏览…", width=70, command=self._pick_src).grid(row=0, column=2)
        row.grid_columnconfigure(1, weight=1)

        row2 = ctk.CTkFrame(card, fg_color="transparent"); row2.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(row2, text="备份存储目录").grid(row=0, column=0, sticky="w", pady=3)
        self.bak_var = ctk.StringVar()
        ctk.CTkEntry(row2, textvariable=self.bak_var,
                     placeholder_text="选择本地备份存放位置（可自定义）").grid(row=0, column=1, sticky="ew", padx=8)
        ctk.CTkButton(row2, text="浏览…", width=70, command=self._pick_bak).grid(row=0, column=2)
        row2.grid_columnconfigure(1, weight=1)

    def _init_strategy_card(self, card):
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(row, text="策略模式").grid(row=0, column=0, sticky="w")
        self.mode_var = ctk.StringVar(value="按份数")
        ctk.CTkOptionMenu(row, values=["按份数", "按天数", "混合"], variable=self.mode_var,
                          width=110, command=lambda _: self._save()).grid(row=0, column=1, sticky="w", padx=8)

        ctk.CTkLabel(row, text="保留份数").grid(row=0, column=2, sticky="e", padx=(16, 4))
        self.keep_spin = ctk.CTkEntry(row, width=60, justify="center"); self.keep_spin.insert(0, "10")
        self.keep_spin.grid(row=0, column=3)
        self.keep_spin.bind("<FocusOut>", lambda _: self._save())

        ctk.CTkLabel(row, text="安全下限").grid(row=0, column=4, sticky="e", padx=(16, 4))
        self.min_spin = ctk.CTkEntry(row, width=60, justify="center"); self.min_spin.insert(0, "5")
        self.min_spin.grid(row=0, column=5)
        self.min_spin.bind("<FocusOut>", lambda _: self._save())

        row2 = ctk.CTkFrame(card, fg_color="transparent"); row2.pack(fill="x", padx=16, pady=6)
        self.auto_clean = ctk.CTkSwitch(row2, text="备份后自动清洗旧备份", command=self._save)
        self.auto_clean.pack(side="left")

    def _init_schedule_card(self, card):
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=16, pady=2)
        self.schedule_switch = ctk.CTkSwitch(
            row, text="启用每日自动备份（注册 Windows 计划任务，程序不常驻）",
            command=self._toggle_schedule)
        self.schedule_switch.pack(side="left")

        ctk.CTkLabel(row, text="时间").pack(side="left", padx=(18, 4))
        self.schedule_time = ctk.CTkEntry(row, width=70, justify="center")
        self.schedule_time.insert(0, "03:00")
        self.schedule_time.pack(side="left")
        ctk.CTkButton(row, text="应用", width=60, height=26,
                      command=self._toggle_schedule).pack(side="left", padx=8)
        self.schedule_status = ctk.CTkLabel(row, text="", font=ctk.CTkFont(size=12))
        self.schedule_status.pack(side="left", padx=4)

    def _init_button_card(self, card):
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=16, pady=12)
        ctk.CTkButton(row, text="▶ 立即备份", command=self._do_backup, height=42, width=150,
                      fg_color="#2563eb", hover_color="#1d4ed8").pack(side="left", padx=4)
        ctk.CTkButton(row, text="♻ 一键恢复…", command=self._do_restore, height=42, width=150,
                      fg_color="#16a34a", hover_color="#15803d").pack(side="left", padx=4)
        ctk.CTkButton(row, text="☁ 云盘设置", command=self._open_cloud, height=42, width=120,
                      fg_color="#7c3aed", hover_color="#6d28d9").pack(side="left", padx=4)
        self.cloud_hint = ctk.CTkLabel(row, text="", font=ctk.CTkFont(size=12), text_color="#a78bfa")
        self.cloud_hint.pack(side="left", padx=8)

    def _init_log_card(self, card):
        self.log = ctk.CTkTextbox(card, height=150, font=ctk.CTkFont(size=12),
                                  fg_color=("gray92", "gray20"))
        self.log.pack(fill="both", expand=True, padx=10, pady=(2, 10))
        self.log.configure(state="disabled")

    # ---------- 配置读写 ----------
    def _load_into_ui(self):
        self.src_var.set(self.task.get("src_dir", ""))
        self.bak_var.set(self.task.get("backup_dir", ""))
        r = self.retention
        self.mode_var.set({"count": "按份数", "days": "按天数", "both": "混合"}
                          .get(r.get("mode", "count"), "按份数"))
        self.keep_spin.delete(0, "end"); self.keep_spin.insert(0, str(r.get("keep_count", 10)))
        self.min_spin.delete(0, "end"); self.min_spin.insert(0, str(r.get("min_keep", 5)))
        if r.get("auto_clean", True):
            self.auto_clean.select()
        else:
            self.auto_clean.deselect()

        if self.cfg["app"].get("schedule_enabled"):
            self.schedule_switch.select()
        else:
            self.schedule_switch.deselect()
        self.schedule_time.delete(0, "end")
        self.schedule_time.insert(0, self.cfg["app"].get("schedule_time", "03:00"))
        self._update_cloud_hint()

    def _sync_task_from_ui(self):
        self.task["src_dir"] = self.src_var.get()
        self.task["backup_dir"] = self.bak_var.get()
        r = self.retention
        r["mode"] = {"按份数": "count", "按天数": "days", "混合": "both"} \
            .get(self.mode_var.get(), "count")
        try:
            r["keep_count"] = max(1, int(self.keep_spin.get()))
            r["min_keep"] = max(1, int(self.min_spin.get()))
        except ValueError:
            pass
        r["auto_clean"] = self.auto_clean.get() == 1
        r.setdefault("keep_days", 30)

    def _save(self):
        self._sync_task_from_ui()
        cfg.save(self.cfg)
        return True

    def _update_cloud_hint(self):
        cloud_cfg = self.task.get("cloud", {})
        if cloud_cfg.get("enabled") and cloud_cfg.get("provider"):
            try:
                import cloud
                cls = cloud.get_plugin(cloud_cfg["provider"])
                name = cls.name if cls else cloud_cfg["provider"]
                self.cloud_hint.configure(text=f"已启用：{name}")
            except Exception:
                self.cloud_hint.configure(text="已启用")
        else:
            self.cloud_hint.configure(text="（未启用）")

    # ---------- 计划任务 ----------
    def _refresh_schedule_label(self):
        exists, msg = scheduler.query_task()
        self.schedule_status.configure(
            text=msg, text_color="#4ade80" if exists else "gray")

    def _toggle_schedule(self):
        time_str = self.schedule_time.get().strip()
        if not valid_time(time_str):
            self._log("❌ 时间格式应为 HH:MM（如 03:00）")
            self.schedule_status.configure(text="时间格式错误", text_color="#f87171")
            return
        enabled = self.schedule_switch.get() == 1
        ok, msg = scheduler.apply_schedule(enabled, time_str)
        self.cfg["app"]["schedule_enabled"] = enabled
        self.cfg["app"]["schedule_time"] = time_str
        cfg.save(self.cfg)
        self._save()
        self._log(("✅ " if ok else "❌ ") + msg)
        self._refresh_schedule_label()

    # ---------- 云盘 ----------
    def _open_cloud(self):
        old = getattr(self, "_cloud_page", None)
        if old is not None:
            try:
                old.destroy()
            except Exception:
                pass
            self._cloud_page = None
        page = CloudPage(self, self.task.get("cloud", {}), on_saved=self._on_cloud_saved)
        self._cloud_page = page
        page.protocol("WM_DELETE_WINDOW", self._close_cloud_page)

    def _close_cloud_page(self):
        old = getattr(self, "_cloud_page", None)
        if old is not None:
            try:
                old.destroy()
            except Exception:
                pass
            self._cloud_page = None

    def _on_cloud_saved(self):
        self._save()
        self._update_cloud_hint()
        self._log("云盘配置已保存")

    # ---------- 业务逻辑 ----------
    def _validate(self):
        if not os.path.isdir(self.src_var.get()):
            self._log("❌ 请先选择有效的备份源目录（浏览选择方舟存档文件夹）")
            return False
        if not self.bak_var.get():
            self.bak_var.set(os.path.join(os.path.expanduser("~"), "ARK_Backups"))
        os.makedirs(self.bak_var.get(), exist_ok=True)
        return True

    def _pick_src(self):
        p = fd.askdirectory(title="选择方舟存档目录")
        if p:
            self.src_var.set(p); self._save(); self._log(f"备份源: {p}")

    def _pick_bak(self):
        p = fd.askdirectory(title="选择本地备份存储目录")
        if p:
            self.bak_var.set(p); self._save(); self._log(f"备份存储: {p}")

    def _log(self, s):
        try:
            self.after(0, lambda: self._log_ui(s))
        except Exception:
            pass

    def _log_ui(self, s):
        try:
            self.log.configure(state="normal")
            self.log.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {s}\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        except Exception:
            pass

    def _set_busy(self, busy):
        self._busy = bool(busy)
        try:
            self.after(0, lambda b=busy: self._set_busy_ui(b))
        except Exception:
            pass

    def _set_busy_ui(self, busy):
        try:
            self.status_label.configure(text="⏳ 处理中…" if busy else "● 就绪",
                                        text_color="#facc15" if busy else "#4ade80")
        except Exception:
            pass

    def _do_backup(self):
        if self._busy:
            return
        if not self._validate():
            return
        self._save()
        self._set_busy(True)
        threading.Thread(target=self._backup_worker, daemon=True).start()

    def _backup_worker(self):
        try:
            ok, res = runner.run_task(self.task, log=self._log)
            if ok and res.get("uploaded"):
                self._log("✅ 备份并上传云盘完成")
            elif ok:
                self._log("✅ 备份完成")
        except FileNotFoundError as e:
            self._log(f"❌ {e}")
        except Exception as e:
            self._log(f"❌ {e}")
        finally:
            self._set_busy(False)

    def _do_restore(self):
        if self._busy:
            self._log("⏳ 正在处理中，请稍候…"); return
        if not os.path.isdir(self.bak_var.get()):
            self._log("❌ 请先设置备份存储目录"); return
        if not os.path.isdir(self.src_var.get()):
            self._log("❌ 请先设置备份源目录（恢复目标）"); return
        self._save()
        task = dict(self.task)
        bak_dir = task["backup_dir"]

        rows = bk.list_backups(bak_dir, task.get("name", "方舟存档"))
        if not rows:
            all_rows = bk.list_backups(bak_dir)
            if all_rows:
                rows = all_rows
                self._log(f"ℹ️ 未按任务名匹配到，已显示备份目录下全部 {len(rows)} 份备份")
        if not rows:
            self._log("❌ 没有找到可用备份（请确认备份存储目录正确，且目录里存在 ARK_backup_*.zip）"); return

        if getattr(self, "_restore_dlg", None) is not None:
            try:
                self._restore_dlg.destroy()
            except Exception:
                pass
            self._restore_dlg = None
        dlg = ctk.CTkToplevel(self)
        self._restore_dlg = dlg
        dlg.title("选择要恢复的备份")
        dlg.geometry("600x460")
        dlg.transient(self)
        dlg.protocol("WM_DELETE_WINDOW", self._close_restore_dlg)

        ctk.CTkLabel(dlg, text="点击下面任一备份即可选择并进入确认：",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=16, pady=(14, 6))
        box = ctk.CTkScrollableFrame(dlg, height=280); box.pack(fill="both", expand=True, padx=16)

        def choose(path):
            dlg.destroy()
            self._restore_dlg = None
            self._confirm_restore(path)

        for path, size, ts in reversed(rows):
            label = os.path.basename(path)
            sub = f"{datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')}  ·  {human_size(size)}"
            b = ctk.CTkButton(box, text=f"{label}\n{sub}", anchor="w",
                              height=48, fg_color=("gray89", "gray22"),
                              hover_color=("#dbeafe", "#1e3a5f"),
                              text_color=("gray15", "gray95"),
                              command=lambda p=path: choose(p))
            b.pack(fill="x", pady=3)

        ftr = ctk.CTkFrame(dlg, fg_color="transparent"); ftr.pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(ftr, text=f"共 {len(rows)} 份备份", font=ctk.CTkFont(size=12),
                     text_color="gray50").pack(side="left")
        ctk.CTkButton(ftr, text="关闭", fg_color="gray30", hover_color="gray25",
                      width=90, command=self._close_restore_dlg).pack(side="right")

    def _close_restore_dlg(self):
        dlg = getattr(self, "_restore_dlg", None)
        if dlg is not None:
            try:
                dlg.destroy()
            except Exception:
                pass
            self._restore_dlg = None

    def _confirm_restore(self, zip_path):
        if getattr(self, "_confirm_dlg", None) is not None:
            try:
                self._confirm_dlg.destroy()
            except Exception:
                pass
            self._confirm_dlg = None
        dlg = ctk.CTkToplevel(self)
        self._confirm_dlg = dlg
        dlg.title("确认恢复")
        dlg.geometry("480x280")
        dlg.transient(self)
        dlg.protocol("WM_DELETE_WINDOW", self._close_confirm_dlg)

        ctk.CTkLabel(dlg, text="⚠️ 请确认", font=ctk.CTkFont(size=17, weight="bold"),
                     text_color="#facc15").pack(pady=(18, 6))
        msg = (f"将用以下备份覆盖当前存档目录：\n{self.src_var.get()}\n\n"
               f"备份：{os.path.basename(zip_path)}\n\n"
               "恢复前会自动备份当前存档作为安全网。")
        ctk.CTkLabel(dlg, text=msg, justify="left", wraplength=430,
                     font=ctk.CTkFont(size=13)).pack(padx=20, pady=6)

        row = ctk.CTkFrame(dlg, fg_color="transparent"); row.pack(pady=12)

        def run():
            src = self.src_var.get()
            dlg.destroy()
            self._confirm_dlg = None
            self._set_busy(True)
            threading.Thread(target=self._restore_worker, args=(zip_path, src),
                             daemon=True).start()

        ctk.CTkButton(row, text="取消", fg_color="gray30", command=self._close_confirm_dlg,
                      width=100).pack(side="left", padx=6)
        ctk.CTkButton(row, text="确认恢复", fg_color="#dc2626", hover_color="#b91c1c",
                      command=run, width=120).pack(side="left", padx=6)

    def _close_confirm_dlg(self):
        dlg = getattr(self, "_confirm_dlg", None)
        if dlg is not None:
            try:
                dlg.destroy()
            except Exception:
                pass
            self._confirm_dlg = None

    def _restore_worker(self, zip_path, src_dir):
        try:
            self._log("正在恢复…（已自动备份当前存档作为安全网）")
            res = rs.restore_backup(zip_path, src_dir)
            if res["restored"]:
                self._log("✅ 恢复成功！")
                if res["snapshot"] and os.path.exists(res["snapshot"]):
                    self._log(f"🛟 恢复前存档已存至: {res['snapshot']}")
            else:
                self._log(f"❌ {res['message']}")
        except Exception as e:
            self._log(f"❌ {e}")
        finally:
            self._set_busy(False)


def valid_time(s):
    try:
        h, m = s.split(":")
        return 0 <= int(h) <= 23 and 0 <= int(m) <= 59
    except Exception:
        return False


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
