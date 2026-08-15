"""即梦行走帧 -> 桌宠 walk 精灵帧（flood-fill 连通域抠图 + 统一缩放 + 脚底对齐 + 居中）

用法:
    python autodl_tools/_clean_frames.py                          # keys/ -> cleaned/（512x512 RGBA，贴底 y=499）
    python autodl_tools/_clean_frames.py --rekey DIR              # 对已有 RGBA 帧只重抠 alpha（几何不变），修复坏抠图
    python autodl_tools/_clean_frames.py --src xxx --foot-y 499 --target 512

抠图算法: flood-fill 从图像四边扩散，只把「与边缘连通的近白像素」当背景抠掉；
角色内部的白色（围裙/袜边/高光）不与边缘连通，全部保留。
（教训: 之前用全局阈值 (r,g,b)>225 直接抠，女仆装白色部分被误杀成透明洞。）

对齐基准: 现有 module_5_assets/sprites/walk_00.png（脚底 y=499, 角色高约 494）。
所有帧统一 scale（基于中位高度），逐帧按自身 bbox 裁剪缩放，脚底对齐同一 y，水平居中，
保证 8 帧循环播放时无上下/左右抖动。
"""
import argparse
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
DEFAULT_SRC = REPO / "_walk_gen" / "keys"
DEFAULT_DST = REPO / "_walk_gen" / "cleaned"
BG_THRESHOLD = 242  # 背景 = 与边缘连通的近白像素（>242）


def load_rgb(p: Path) -> np.ndarray:
    return np.array(Image.open(p).convert("RGB")).astype(int)


def flood_fill_background(rgb: np.ndarray, thr: int = BG_THRESHOLD) -> np.ndarray:
    """返回背景掩码：与图像边缘 4-连通的近白像素（真背景）"""
    h, w = rgb.shape[:2]
    white = (rgb[:, :, 0] > thr) & (rgb[:, :, 1] > thr) & (rgb[:, :, 2] > thr)
    bg = np.zeros((h, w), bool)
    q = deque()
    for x in range(w):
        if white[0, x]:
            bg[0, x] = True
            q.append((0, x))
        if white[h - 1, x]:
            bg[h - 1, x] = True
            q.append((h - 1, x))
    for y in range(h):
        if white[y, 0]:
            bg[y, 0] = True
            q.append((y, 0))
        if white[y, w - 1]:
            bg[y, w - 1] = True
            q.append((y, w - 1))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not bg[ny, nx] and white[ny, nx]:
                bg[ny, nx] = True
                q.append((ny, nx))
    return bg


def clean_and_align(src: Path, dst: Path, target: int, foot_y: int, thr: int = BG_THRESHOLD, flip: bool = False):
    dst.mkdir(parents=True, exist_ok=True)
    files = sorted(src.glob("key_*.png"))
    if not files:
        sys.exit(f"{src} 下没有 key_*.png")

    # 1) 统一 scale：目标高度 = 现有 walk_00 高度（取 494），基于中位高度
    heights = []
    for f in files:
        a = load_rgb(f)
        ys = np.where(~flood_fill_background(a, thr))[0]
        heights.append(int(ys.max() - ys.min()))
    med_h = float(np.median(heights))
    target_h = 494.0  # 与现有 walk_00.png 角色高度一致
    scale = target_h / med_h
    print(f"{len(files)} 帧, 中位高度 {med_h:.0f}px, scale={scale:.4f} (目标高 {target_h:.0f})", flush=True)

    # 2) 逐帧: flood-fill 抠图 -> bbox 裁剪 -> 缩放 -> 脚底对齐 + 居中
    for f in files:
        a = load_rgb(f)
        bg = flood_fill_background(a, thr)
        alpha = np.where(bg, 0, 255).astype(np.uint8)
        rgba = np.dstack([a.astype(np.uint8), alpha])
        im = Image.fromarray(rgba)
        bbox = im.getbbox()
        if bbox is None:
            print(f"  WARN {f.name}: 全白无角色, 跳过", flush=True)
            continue
        im = im.crop(bbox)
        w, h = im.size
        nh = max(1, round(h * scale))
        nw = max(1, round(w * scale))
        im = im.resize((nw, nh), Image.LANCZOS)

        canvas = Image.new("RGBA", (target, target), (0, 0, 0, 0))
        x = (target - nw) // 2
        y = foot_y - nh
        if flip:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        canvas.paste(im, (x, y), im)
        out = dst / f.name
        canvas.save(out)
        print(f"  {f.name}: {w}x{h} -> {nw}x{nh} @({x},{y})" + (" [flipped]" if flip else ""), flush=True)
    print(f"完成 -> {dst}", flush=True)


def rekey_dir(d: Path, thr: int = BG_THRESHOLD):
    """修复坏抠图：对已有 RGBA 帧重抠 alpha（flood-fill），几何布局不动"""
    files = sorted(d.glob("*.png"))
    if not files:
        sys.exit(f"{d} 下没有 PNG")
    for f in files:
        im = Image.open(f).convert("RGBA")
        rgb = np.array(im.convert("RGB")).astype(int)
        bg = flood_fill_background(rgb, thr)
        arr = np.array(im)
        arr[:, :, 3] = np.where(bg, 0, 255).astype(np.uint8)
        Image.fromarray(arr).save(f)
        print(f"  rekeyed {f.name}", flush=True)
    print(f"重抠完成 -> {d}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--dst", default=str(DEFAULT_DST))
    ap.add_argument("--target", type=int, default=512)
    ap.add_argument("--foot-y", type=int, default=499, help="脚底对齐到的 y 坐标（现有 walk_00 为 499）")
    ap.add_argument("--rekey", default=None, help="只重抠指定目录 RGBA 帧的 alpha（修复坏抠图，几何不变）")
    ap.add_argument("--thr", type=int, default=BG_THRESHOLD, help="背景白阈值（默认 242）")
    ap.add_argument("--flip", action="store_true", help="输出前水平翻转（素材面朝左时统一为面朝右）")
    args = ap.parse_args()

    if args.rekey:
        rekey_dir(Path(args.rekey), args.thr)
    else:
        clean_and_align(Path(args.src), Path(args.dst), args.target, args.foot_y, args.thr, args.flip)


if __name__ == "__main__":
    sys.exit(main())
