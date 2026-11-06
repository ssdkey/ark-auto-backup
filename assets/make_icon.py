#!/usr/bin/env python3
"""生成应用图标 assets/app.ico（多分辨率）"""
import os
from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 背景圆角方块（深蓝渐变近似）
d.rounded_rectangle([8, 8, S - 8, S - 8], radius=52, fill=(37, 99, 235, 255))
# 内圈/装饰
d.rounded_rectangle([40, 40, S - 40, S - 40], radius=34, outline=(255, 255, 255, 60), width=8)

# 三个堆叠纸页（代表备份存档层级），白色主体
def page(x0, y0, w, h, cy):
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=12, fill=(255, 255, 255, 230))
    d.rounded_rectangle([x0 + 14, y0 + h - 8, x0 + w - 14, y0 + h - 8 + 5], radius=3, fill=(37, 99, 235, 255))
    # 文本线
    for k in range(3):
        yy = y0 + 18 + k * 16
        d.rounded_rectangle([x0 + 16, yy, x0 + w - 16, yy + 6], radius=3, fill=(160, 180, 230, 255))

# 三层堆叠，斜向
page(64, 74, 128, 150, 235)
page(84, 92, 128, 150, 235)
page(104, 110, 128, 150, 235)

dir = os.path.dirname(os.path.abspath(__file__))
os.makedirs(dir, exist_ok=True)
out = os.path.join(dir, "app.ico")
img.save(out, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.resize((256, 256)).save(os.path.join(dir, "app.png"))
print("icon written:", out, os.path.getsize(out))
