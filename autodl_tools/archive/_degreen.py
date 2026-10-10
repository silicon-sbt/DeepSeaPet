"""色度键去绿：把基准图里残留的绿幕像素替换成白底。
处理 base_refs/ 下 7 个状态基准图，输出 _clean 后缀，不覆盖原图。
"""
from PIL import Image
import numpy as np, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "base_refs")

for name in ["idle", "happy", "hide", "lying", "peek", "sleep", "walk"]:
    src = os.path.join(SRC, f"{name}_00.png")
    if not os.path.exists(src):
        print(f"{name}: 跳过（无文件）")
        continue
    a = np.array(Image.open(src).convert("RGB"))
    r = a[:, :, 0].astype(int)
    g = a[:, :, 1].astype(int)
    b = a[:, :, 2].astype(int)
    green = (g > r + 40) & (g > b + 40)
    n = int(green.sum())
    a[green] = [255, 255, 255]
    dst = os.path.join(SRC, f"{name}_00_clean.png")
    Image.fromarray(a).save(dst)
    total = a.shape[0] * a.shape[1]
    print(f"{name}: 去绿 {n} 像素 ({n/total*100:.2f}%) -> {name}_00_clean.png")
