# 🛠️ 方舟自动备份工具（Win）

> **关于本项目**：本程序由 AI 辅助编写完成（基于豆包 AI 编程助手），代码经过实际测试可正常使用。作者在此基础上进行了需求定义、调试与验证。

可视化界面 + 云盘自动上传的「方舟/存档自动备份、自动清洗、一键恢复」工具。

> 低资源占用 · 小体积 · 美观流畅（CustomTkinter 暗色主题）

## ✨ 功能
- ✅ **一键备份**：方舟存档 → 本地自定义目录（流式压缩，低占用）
- ✅ **自动清洗**：保留策略 `按份数/按天数/混合` 可切换，不足安全下限不删
- ✅ **一键恢复**：引导选择备份 → 覆盖确认 → 恢复前自动备份当前存档作安全网
- ✅ **自定义路径**：备份源、存储目录均可界面选择
- ☁️ **云盘自动上传**：内置坚果云/WebDAV、百度网盘、阿里云盘、OneDrive，备份完成后自动上传
- ⚙️ **config.json 持久化**：界面所有改动自动保存，重启后恢复
- 🕒 **计划任务**：界面一键注册 Windows 计划任务，每日定时无界面自动备份（程序不常驻）

## 🚀 运行
```bash
pip install -r requirements.txt
python app.py
```

### 无界面备份（供计划任务 / 命令行）
```bash
python app.py --backup      # 读取 config.json 执行全部任务并追加日志到 backup_log.txt
```

## 📦 打包 exe（体积最小化）
双击 `build_windows.bat`，生成 `dist/方舟自动备份工具.exe`（单文件、仅含所需模块）。

## 🗂️ 目录结构
```
auto_backup/
├─ app.py              入口（GUI / --backup 无界面两种模式）
├─ config.json         配置（程序自动读写，界面改动即持久化）
├─ requirements.txt    依赖（仅 customtkinter + requests）
├─ build_windows.bat   PyInstaller 单文件打包
├─ build_all.bat       exe + Inno Setup 安装向导
├─ installer.iss       Inno Setup 安装脚本
├─ assets/             图标与截图生成脚本
├─ core/
│  ├─ backup.py        备份（流式、ZIP_STORED 低占用）
│  ├─ cleaner.py       清洗策略（count/days/both + min_keep）
│  ├─ restore.py       一键恢复（安全快照）
│  ├─ config.py        config.json 加载/保存（含默认值、路径处理）
│  ├─ runner.py        备份流程编排（备份→清洗→云盘上传）
│  └─ scheduler.py     Windows 计划任务封装（schtasks）
├─ cloud/
│  ├─ base.py          CloudUploader 抽象基类 + Field + 插件注册中心
│  ├─ webdav.py        坚果云 / 自定义 WebDAV 插件
│  ├─ baidu.py         百度网盘插件（superfile2 分片上传）
│  ├─ aliyun.py        阿里云盘插件（Open API + refresh_token 刷新）
│  ├─ onedrive.py      OneDrive 插件（Graph API）
│  └─ __init__.py      自动收集所有 @register 插件
├─ gui/
│  ├─ main_window.py  主界面（备份/恢复/策略/计划任务/云盘/日志）
│  └─ cloud_page.py    云盘设置窗口（卡片式字段，动态渲染插件字段）
└─ docs/               使用说明与打包说明
```

## ☁️ 云盘设置与凭证获取

点击主界面「☁ 云盘设置」→ 左侧选择云盘 → 按右侧提示填写凭证 → 勾选「启用自动上传」→「保存」。备份完成后会自动上传到对应云端目录。

### 坚果云 / WebDAV（推荐，最简单）
| 字段 | 必填 | 说明 |
|------|:---:|------|
| 服务器地址 | ✅ | 坚果云：`https://dav.jianguoyun.com/dav/`（可加子目录，如 `.../dav/ARK/`） |
| 账号 | ✅ | 坚果云注册邮箱 / 登录名 |
| 应用密码 | ✅ | **必须用应用密码（非登录密码）**，在坚果云「账户信息 → 安全选项 → 添加应用密码」生成 |

> 也兼容任意标准 WebDAV 服务器，地址填 `https://主机/路径/` 即可。

### 百度网盘
| 字段 | 必填 | 说明 |
|------|:---:|------|
| access_token | ✅ | 从百度开放平台 `https://pan.baidu.com/oauth` 走 OAuth 授权获取 |
| 云端路径 | — | 建议以 `/apps/` 开头，如 `/apps/ARK_BACKUP`（留空则用应用默认目录） |

### 阿里云盘
| 字段 | 必填 | 说明 |
|------|:---:|------|
| refresh_token | ✅ | 阿里云盘开放平台获取（可自动换新 access_token） |
| drive_id | ✅ | 云盘空间 ID（开放平台 API 查询） |
| client_id / client_secret | — | 开放平台应用凭据，用于自动刷新 token |
| access_token | — | 可选，二选一；填了 refresh_token 会自动刷新，一般无需手填 |

### OneDrive
| 字段 | 必填 | 说明 |
|------|:---:|------|
| access_token | ✅ | 微软 Graph 授权获取 `https://graph.microsoft.com` 的 access_token |
| 云端目录 | — | 留空 = OneDrive 根目录 |

> ⚠️ OneDrive/百度 access_token 有时效（OneDrive 约 1 小时），过期后需重新获取；阿里云盘若填写 client_id/secret + refresh_token 可自动续期。

## ☁️ 扩展云盘插件
新增一个云盘只需在 `cloud/` 下新建一个 `.py` 并 `@register`，再在 `cloud/__init__.py` 里 import 它，GUI 云盘页会自动列出、自动渲染卡片式字段——无需改动其他代码。参见 `cloud/webdav.py` 示例。

## 🕒 计划任务
界面「计划任务」卡片：设置时间（HH:MM）→ 勾选启用 → 点「应用」，即调用 `schtasks` 注册每日任务，到点执行 `exe --backup`（无界面）。程序自身不常驻，平时占用为 0。

## 🔐 安全设计
- 清洗删除前预览 + `min_keep` 安全下限
- 恢复前自动备份当前存档，可回退
- 覆盖/删除均需用户确认
- 云盘密码字段以密文输入，仅存本地 config.json
