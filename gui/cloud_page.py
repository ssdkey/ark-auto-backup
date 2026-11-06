"""云盘设置窗口
- 左侧列出所有已注册云盘插件
- 右侧动态渲染该插件的字段（含密码类字段掩码）
- 卡片式字段布局：字段名 / 说明 / 输入框 分行显示，避免文字遮挡
- 支持测试连接、启用/保存配置
"""
import threading

import customtkinter as ctk

import cloud


class CloudPage(ctk.CTkToplevel):
    def __init__(self, master, task_config, on_saved=None):
        super().__init__(master)
        self.task_config = task_config      # config.json 中当前任务的 cloud 段引用
        self.on_saved = on_saved
        self._fields = {}                   # key -> StringVar
        self._busy = False

        self.title("云盘设置")
        self.geometry("760x620")
        self.transient(master)
        # 不使用 grab_set：模态锁会锁死事件循环，导致窗口无响应/无法关闭
        self.protocol("WM_DELETE_WINDOW", self.destroy)  # 点X可正常关闭

        self._build_ui()
        self._load_initial()

    # ---------- UI ----------
    def _build_ui(self):
        # 头部说明（整行显示，说明如何获取凭证）
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(header, text="☁ 上传到云盘",
                     font=ctk.CTkFont(size=19, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(header, text="选择云盘 → 按右侧提示填写凭证 → 启用自动上传，备份完成后会自动传到云端。",
                     font=ctk.CTkFont(size=12), text_color="gray",
                     wraplength=700, justify="left").pack(anchor="w", pady=(2, 0))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(10, 6))
        body.grid_columnconfigure(1, weight=1)  # 右侧占满剩余宽度
        body.grid_rowconfigure(0, weight=1)

        # 左侧：插件列表
        left = ctk.CTkFrame(body, width=200, fg_color=("gray92", "gray17"), corner_radius=12)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 14))
        left.grid_propagate(False)
        ctk.CTkLabel(left, text="云盘", font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="w").pack(fill="x", padx=14, pady=(12, 6))

        self.plugins = cloud.all_plugins()
        self.plugin_buttons = {}
        for cls in self.plugins:
            b = ctk.CTkButton(left, text=cls.name, anchor="w", height=38,
                              fg_color="transparent", hover_color=("gray85", "gray22"),
                              corner_radius=8,
                              command=lambda k=cls.key: self._select(k))
            b.pack(fill="x", padx=10, pady=3)
            self.plugin_buttons[cls.key] = b

        # 右侧：字段表单（可滚动，与左侧并排占满剩余宽度）
        right = ctk.CTkScrollableFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        self.right = right

        # 底部操作
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=20, pady=(8, 16))
        self.status = ctk.CTkLabel(bottom, text="", font=ctk.CTkFont(size=12))
        self.status.pack(side="left")
        ctk.CTkButton(bottom, text="测试连接", width=110, command=self._do_test,
                      fg_color="gray30", hover_color="gray25").pack(side="right", padx=6)
        self.enable_switch = ctk.CTkSwitch(bottom, text="启用自动上传")
        self.enable_switch.pack(side="right", padx=16)
        ctk.CTkButton(bottom, text="保存", width=100, command=self._do_save,
                      fg_color="#2563eb", hover_color="#1d4ed8").pack(side="right", padx=6)
        ctk.CTkButton(bottom, text="关闭", width=90, fg_color="gray30", hover_color="gray25",
                      command=self.destroy).pack(side="right", padx=6)

        self._selected_key = None

    def _render_fields(self, cls, values):
        """清空右侧并渲染指定插件的字段（卡片式：字段名/说明/输入框分行）"""
        for w in self.right.winfo_children():
            w.destroy()
        self._fields = {}

        # 插件说明卡
        desc_card = ctk.CTkFrame(self.right, corner_radius=10,
                                 fg_color=("gray92", "gray20"))
        desc_card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(desc_card, text=cls.name, font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="w").pack(anchor="w", padx=14, pady=(10, 2))
        ctk.CTkLabel(desc_card, text=cls.desc, font=ctk.CTkFont(size=12),
                     text_color="gray", wraplength=470, justify="left",
                     anchor="w").pack(anchor="w", padx=14, pady=(0, 10))

        # 每个字段一张卡
        for f in cls.fields:
            card = ctk.CTkFrame(self.right, corner_radius=10,
                                fg_color=("gray93", "gray19"))
            card.pack(fill="x", pady=5)
            # 第一行：字段名 + 必填标签
            head = ctk.CTkFrame(card, fg_color="transparent")
            head.pack(fill="x", padx=14, pady=(10, 0))
            ctk.CTkLabel(head, text=f.label, font=ctk.CTkFont(size=13, weight="bold"),
                         anchor="w").pack(side="left")
            tag = "必填" if f.required else "选填"
            ctk.CTkLabel(head, text=tag,
                         font=ctk.CTkFont(size=10),
                         text_color="#f87171" if f.required else "gray",
                         fg_color="transparent").pack(side="left", padx=(8, 0))
            # 第二行：说明文字（用 placeholder 作为填写指引，独立成行不遮挡）
            hint = f.placeholder or f"填写 {f.label}"
            ctk.CTkLabel(card, text=hint, font=ctk.CTkFont(size=11),
                         text_color="gray", wraplength=470, justify="left",
                         anchor="w").pack(anchor="w", padx=(30, 14), pady=(2, 6))
            # 第三行：输入框
            show = "*" if f.secret else ""
            var = ctk.StringVar(value=str(values.get(f.key, f.default or "")))
            entry = ctk.CTkEntry(card, textvariable=var, show=show, height=34,
                                 fg_color=("white", "gray21"),
                                 border_color=("gray80", "gray27"))
            entry.pack(fill="x", padx=14, pady=(0, 12))
            self._fields[f.key] = var

    def _load_initial(self):
        """根据 config 里的 provider 选中已有插件"""
        provider = self.task_config.get("provider", "")
        saved = self.task_config.get("config", {})
        self.enable_switch.select() if self.task_config.get("enabled") else self.enable_switch.deselect()
        if provider and provider in self.plugin_buttons:
            self._select(provider, values=saved)
        elif self.plugins:
            self._select(self.plugins[0].key, values=saved)

    def _select(self, key, values=None):
        self._selected_key = key
        for k, b in self.plugin_buttons.items():
            if k == key:
                b.configure(fg_color="#2563eb", text_color="white")
            else:
                b.configure(fg_color="transparent", text_color=("gray15", "gray95"))
        cls = cloud.get_plugin(key)
        if values is None:
            values = self.task_config.get("config", {}) if self.task_config.get("provider") == key else {}
        self._render_fields(cls, values)
        self._set_status("")

    # ---------- 逻辑 ----------
    def _set_status(self, msg, ok=True):
        color = "#4ade80" if ok else "#f87171"
        self.status.configure(text=msg, text_color=color)

    def _collect_values(self):
        cls = cloud.get_plugin(self._selected_key)
        inst = cls(**{k: v.get() for k, v in self._fields.items()})
        return cls, inst

    def _do_test(self):
        if self._busy or not self._selected_key:
            return
        cls, inst = self._collect_values()
        ok, missing = inst.validate()
        if not ok:
            self._set_status("缺少必填: " + ", ".join(missing), ok=False)
            return
        self._busy = True
        self._set_status("测试中…")
        threading.Thread(target=self._test_worker, args=(inst,), daemon=True).start()

    def _test_worker(self, inst):
        try:
            tok, msg = inst.test_connection()
            self.after(0, lambda: self._set_status(msg, ok=tok))
        except Exception as e:
            self.after(0, lambda: self._set_status(f"异常: {e}", ok=False))
        finally:
            self._busy = False

    def _do_save(self):
        if not self._selected_key:
            return
        cls, inst = self._collect_values()
        # 保存到 task_config；启用状态一并写入
        self.task_config["provider"] = self._selected_key
        self.task_config["enabled"] = self.enable_switch.get() == 1
        self.task_config["config"] = inst.config_dict
        if self.on_saved:
            self.on_saved()
        self._set_status("✅ 已保存")
