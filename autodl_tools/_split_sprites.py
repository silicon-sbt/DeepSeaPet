"""量化筛选每状态 AutoDL 生成帧四格中最健康的一格。
指标：角色占比、绿幕占比、角色居中度、帧间稳定性。输出每状态最佳格。
"""
import glob, os, sys
import numpy as np
from PIL import Image

STATES = ["idle", "hide", "peek", "walk", "sleep", "happy", "lying"]
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites_video_dl")

def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(int)

def cell_metrics(a):
    """a: 单格 RGB 数组，返回各健康度指标 dict"""
    h, w, _ = a.shape
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    # 背景掩码比 _eat_shit.py 的 (40/225) 宽松：筛选只估占比，太保守会漏算贴边角色
    green = (g > r + 30) & (g > b + 30)
    white = (r > 220) & (g > 220) & (b > 220)
    role = ~(green | white)
    role_ratio = role.mean()
    green_ratio = green.mean()
    # 角色 bbox 居中度：bbox 离中心越近越好（0~1，1 为正中且贴边合理）
    ys, xs = np.where(role)
    if len(ys) == 0:
        return {"role": 0, "green": 1, "center": 0}
    cy, cx = (ys.min() + ys.max()) / 2 / h, (xs.min() + xs.max()) / 2 / w
    center = 1 - (abs(cy - 0.5) + abs(cx - 0.5))  # 越居中越高
    return {"role": role_ratio, "green": green_ratio, "center": center}

for st in STATES:
    fs = sorted(glob.glob(f"{SRC}/{st}/*.png"))
    if len(fs) < 8:
        print(f"{st}: 缺帧"); continue
    frames = [load(f) for f in fs]
    h, w, _ = frames[0].shape
    pos = [(0, 0), (0, w // 2), (h // 2, 0), (h // 2, w // 2)]
    best = None
    for c, (y0, x0) in enumerate(pos):
        cells = [fr[y0:y0 + h // 2, x0:x0 + w // 2] for fr in frames]
        m = cell_metrics(cells[0])
        # 帧间稳定性：该格 8 帧相对首帧平均色差
        stab = sum(np.abs(cells[i] - cells[0]).mean() for i in range(1, 8)) / 7
        score = (
            m["role"] * 1.0          # 有内容
            - abs(m["role"] - 0.4) * 2  # 角色占比接近 40% 最佳
            - (1 - m["center"]) * 1.5   # 角色居中
            - m["green"] * 0.5          # 绿幕少
            - stab * 0.02               # 稳定加分(色差小的稳定格)
        )
        print(f"  {st} 格{c}: 角色{m['role'] * 100:.0f}% 绿{m['green'] * 100:.0f}% "
              f"居中{m['center']:.2f} 帧间色差{stab:.0f}")
        if best is None or score > best[0]:
            best = (score, c, stab)
    print(f"  >>> {st} 最佳格: {best[1]} (帧间色差 {best[2]:.0f})")
