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
    """绿幕/白底色度键 → RGBA（flood-fill 连通域版）。

    只把「与图像边缘 4-连通的」绿色/白色当背景抠掉；角色内部的白色
    （围裙/袜边/高光）不与边缘连通，全部保留。
    （教训: 旧版用全局阈值 (r>225)&(g>225)&(b>225)，把角色白色部分抠成透明洞。）
    """
    from collections import deque
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    green = (g > r + 40) & (g > b + 40)
    white = (r > 242) & (g > 242) & (b > 242)
    bgmask = green | white
    h, w = a.shape[:2]
    bg = np.zeros((h, w), bool)
    q = deque()
    for x in range(w):
        if bgmask[0, x]:
            bg[0, x] = True; q.append((0, x))
        if bgmask[h - 1, x]:
            bg[h - 1, x] = True; q.append((h - 1, x))
    for y in range(h):
        if bgmask[y, 0]:
            bg[y, 0] = True; q.append((y, 0))
        if bgmask[y, w - 1]:
            bg[y, w - 1] = True; q.append((y, w - 1))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not bg[ny, nx] and bgmask[ny, nx]:
                bg[ny, nx] = True
                q.append((ny, nx))
    alpha = np.where(bg, 0, 255).astype(np.uint8)
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
