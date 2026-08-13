"""吃屎收尾：从 AutoDL 生成帧切最佳格 + 色度键抠图 → 透明精灵帧。
输出到 sprites_new/ 临时目录，确认效果后再覆盖 module_5_assets/sprites/。
"""
import glob, os, sys
import numpy as np
from PIL import Image

STATES = ["idle", "hide", "peek", "walk", "sleep", "happy", "lying"]
# 每状态选定的最佳格位（人工复核 _split_sprites.py 输出）
BEST_CELL = {"idle": 3, "hide": 3, "peek": 3, "walk": 1, "sleep": 3, "happy": 3, "lying": 3}
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites_video_dl")
DST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites_new")
SIZE = 512

def chroma_key(a):
    """绿幕/白底色度键 → RGBA。绿：g 明显高于 r/b；白：三通道全亮。"""
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    green = (g > r + 40) & (g > b + 40)
    white = (r > 225) & (g > 225) & (b > 225)
    bg = green | white
    alpha = bg.astype(np.uint8) * 255
    rgba = np.dstack([a.astype(np.uint8), alpha])
    return rgba

def center_crop_transparent(rgba, size=SIZE):
    """把透明图内容裁剪到内容 bbox 再居中到 size×size"""
    ys, xs = np.where(rgba[:, :, 3] > 0)
    if len(ys) == 0:
        return Image.fromarray(rgba).resize((size, size), Image.LANCZOS)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    crop = rgba[y0:y1 + 1, x0:x1 + 1]
    im = Image.fromarray(crop)
    im.thumbnail((size - 40, size - 40), Image.LANCZOS)  # 留白边
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
    return canvas

os.makedirs(DST, exist_ok=True)
for st in STATES:
    c = BEST_CELL[st]
    fs = sorted(glob.glob(f"{SRC}/{st}/{st}_*.png"))
    if len(fs) < 8:
        print(f"{st}: 缺帧"); continue
    for i, f in enumerate(fs):
        a = np.asarray(Image.open(f).convert("RGB")).astype(int)
        h, w, _ = a.shape
        pos = [(0, 0), (0, w // 2), (h // 2, 0), (h // 2, w // 2)]
        y0, x0 = pos[c]
        cell = a[y0:y0 + h // 2, x0:x0 + w // 2]
        rgba = chroma_key(cell)
        out = center_crop_transparent(rgba)
        out.save(os.path.join(DST, f"{st}_{i:02d}.png"))
    print(f"{st}: 格{c} → 8 帧透明图已输出")
print(f"全部完成 → {DST}")
