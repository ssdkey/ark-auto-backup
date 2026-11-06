"""云盘插件架构
- Field: 描述一个配置字段（凭证/参数）
- CloudUploader: 云盘上传器抽象基类
- register + 插件注册中心: 自动收集所有 @register 装饰的插件

新增一个云盘只需新增一个 .py 文件并 @register，无需改动其他代码。
"""
from abc import ABC, abstractmethod


class Field:
    """一个配置字段的描述。GUI 据此自动渲染输入控件。"""

    def __init__(self, key, label, placeholder="", secret=False,
                 required=True, default=""):
        self.key = key
        self.label = label
        self.placeholder = placeholder
        self.secret = secret          # 是否密码类（界面密文输入、保存到本地）
        self.required = required
        self.default = default

    def to_dict(self):
        return {
            "key": self.key,
            "label": self.label,
            "placeholder": self.placeholder,
            "secret": self.secret,
            "required": self.required,
            "default": self.default,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            key=d.get("key", ""),
            label=d.get("label", ""),
            placeholder=d.get("placeholder", ""),
            secret=d.get("secret", False),
            required=d.get("required", True),
            default=d.get("default", ""),
        )


class CloudUploader(ABC):
    """云盘上传器抽象基类。
    子类需设置类属性，并实现 test_connection 与 upload。
    """
    key = ""                 # 唯一标识，如 "webdav"
    name = ""                # 界面显示名，如 "坚果云 / WebDAV"
    desc = ""                # 说明文字
    fields = []              # list[Field]，用于渲染凭证表单

    def __init__(self, **kwargs):
        # 仅保留插件自身声明的字段值
        valid = {f.key: f.default for f in self.fields}
        valid.update({k: v for k, v in kwargs.items() if k in valid})
        self.config = valid

    # ---- 配置存取 ----
    @property
    def config_dict(self):
        return dict(self.config)

    def set_config(self, **kwargs):
        for k, v in kwargs.items():
            if k in self.config:
                self.config[k] = v

    @classmethod
    def required_fields(cls):
        return [f.key for f in cls.fields if f.required]

    def validate(self):
        """校验必填字段是否齐全，返回 (ok, missing_list)"""
        missing = [f.key for f in self.fields
                   if f.required and not str(self.config.get(f.key, "")).strip()]
        return (not missing), missing

    # ---- 抽象能力 ----
    @abstractmethod
    def test_connection(self):
        """测试连通性/凭证，返回 (ok: bool, message: str)"""
        raise NotImplementedError

    @abstractmethod
    def upload(self, local_path, remote_dir=""):
        """上传本地文件到云端，成功返回云端路径字符串"""
        raise NotImplementedError


# ---------- 插件注册中心 ----------
class _Registry:
    def __init__(self):
        self._plugins = {}

    def register(self, cls):
        if not (cls.key and cls.name):
            # 无效插件静默跳过（基类本身无 key）
            return cls
        self._plugins[cls.key] = cls
        return cls

    def all(self):
        """返回按 key 排序的插件类列表"""
        return [self._plugins[k] for k in sorted(self._plugins)]

    def get(self, key):
        return self._plugins.get(key)

    def keys(self):
        return list(self._plugins.keys())

    def __contains__(self, key):
        return key in self._plugins


REGISTRY = _Registry()


def register(cls):
    """类装饰器：注册一个云盘插件到注册中心"""
    REGISTRY.register(cls)
    return cls
