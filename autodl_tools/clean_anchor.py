"""清理基准图残留(绿幕 + 孤立蓝斑 + 边缘羽化) -> 白底 1024 锚点 (即梦 I2V 首帧用)

用法:
    python clean_anchor.py                      # idle_00.png -> _walk_gen/anchor_clean.png
    python clean_anchor.py --src xxx.png --out yyy.png
    python clean_anchor.py --preview            # 额外存处理前后对比预览
    python clean_anchor.py --blob x0,y0,x1,y1   # 额外清除指定区域的孤立色斑 (原图 512 坐标)
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = ROOT / "module_5_assets" / "sprites" / "idle_00.png"
DEFAULT_OUT = ROOT / "_walk_gen" / "anchor_clean.png"

# 上次确认的 #14 蓝斑: anchor_clean(1024) x455-474 y766-779 -> 原图(512)换算 x238-252 y425-435
BLOB14_512 = (238, 425, 252, 435)


def remove_green(img: Image.Image, tol: int = 40) -> Image.Image:
    """色度键抠绿幕: 亮绿 (g>r+tol & g>b+tol & g>120) 的像素变透明"""
    a = np.array(img.convert("RGBA")).astype(np.float32)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    green = (g > r + tol) & (g > b + tol) & (al > 0) & (g > 120)
    al[green] = 0
    return Image.fromarray(np.stack([r, g, b, al], axis=-1).astype(np.uint8), "RGBA")


def remove_blob(img: Image.Image, bbox) -> Image.Image:
    """清除指定 bbox 内种子连通的孤立色斑: 填周边环均色 (色差大才动)"""
    x0, y0, x1, y1 = bbox
    a = np.array(img).astype(np.int32)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    H, W = a.shape[:2]

    # 种子 = bbox 内 alpha>0 的像素 (取该区域非透明像素为候选)
    seed_px = []
    for y in range(max(0, y0), min(H, y1 + 1)):
        for x in range(max(0, x0), min(W, x1 + 1)):
            if al[y, x] > 128:
                seed_px.append((y, x))
    if not seed_px:
        print(f"  bbox {bbox} 内无像素, 跳过")
        return img

    # BFS 连通域: 与种子色相近 (色距 <60) 的相邻像素
    seed_rgb = np.median([a[y, x, :3] for y, x in seed_px], axis=0)
    seen = np.zeros((H, W), dtype=bool)
    stack = list(seed_px)
    blob = []
    while stack:
        y, x = stack.pop()
        if seen[y, x]:
            continue
        seen[y, x] = True
        if al[y, x] <= 128:
            continue
        if abs(int(a[y, x, 0]) - seed_rgb[0]) > 60 or abs(int(a[y, x, 1]) - seed_rgb[1]) > 60 or abs(int(a[y, x, 2]) - seed_rgb[2]) > 60:
            continue
        blob.append((y, x))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ny, nx = y + dy, x + dx
                if 0 <= ny < H and 0 <= nx < W and not seen[ny, nx]:
                    stack.append((ny, nx))
    if len(blob) < 5 or len(blob) > 3000:
        print(f"  bbox {bbox} 连通域 {len(blob)}px, 越界或太小, 跳过")
        return img

    # 周边环 (外扩 6px) 的颜色均值, 排除透明像素
    ring = set()
    for y, x in blob:
        for dy in range(-6, 7):
            for dx in range(-6, 7):
                if max(abs(dy), abs(dx)) < 2:
                    continue
                ny, nx = y + dy, x + dx
                if 0 <= ny < H and 0 <= nx < W and al[ny, nx] > 128 and (ny, nx) not in blob:
                    ring.add((ny, nx))
    if ring:
        ring_rgb = np.median([a[y, x, :3] for y, x in ring], axis=0)
    else:
        ring_rgb = np.array([255, 255, 255])

    for y, x in blob:
        a[y, x, 0], a[y, x, 1], a[y, x, 2] = ring_rgb
    print(f"  清除蓝斑 {len(blob)}px, 填充色 RGB={ring_rgb.round(0)}")
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def feather_edge(img: Image.Image, radius: int = 2) -> Image.Image:
    """边缘羽化: alpha 从 0 到 255 在 radius px 内渐变 (消除硬边)"""
    a = np.array(img).astype(np.float32)
    al = a[..., 3]
    from scipy.ndimage import maximum_filter, distance_transform_edt
    # 内部距离场 -> 距边缘越近越透明
    interior = al > 0
    dist = distance_transform_edt(interior)
    edge_w = dist < radius
    al[edge_w] = al[edge_w] * (dist[edge_w] / radius)
    a[..., 3] = al
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def to_white_anchor(cleaned: Image.Image, size: int = 1024, target_h: int = 700) -> Image.Image:
    """透明角色 -> 白底 size 居中"""
    a = np.array(cleaned).astype(int)
    ys, xs = np.nonzero(a[..., 3] > 128)
    if len(xs) == 0:
        raise SystemExit("全透明了, 抠过头")
    crop = cleaned.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    scale = target_h / crop.height
    crop = crop.resize((max(1, round(crop.width * scale)), target_h), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    canvas.alpha_composite(crop, ((size - crop.width) // 2, (size - crop.height) // 2))
    return canvas.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--blob", default=None, help="清除指定 bbox 蓝斑 x0,y0,x1,y1 (原图坐标)")
    args = ap.parse_args()

    src = Image.open(args.src).convert("RGBA")
    n0 = (np.array(src)[..., 3] == 0).sum()

    cleaned = remove_green(src)
    n1 = (np.array(cleaned)[..., 3] == 0).sum()
    print(f"抠绿: 透明 {n0} -> {n1} (+{n1 - n0}px)")

    blob_boxes = []
    if args.blob:
        blob_boxes.append(tuple(map(int, args.blob.split(","))))
    else:
        blob_boxes.append(BLOB14_512)  # 默认清 #14
    for bx in blob_boxes:
        cleaned = remove_blob(cleaned, bx)

    cleaned = feather_edge(cleaned)
    anchor = to_white_anchor(cleaned)
    anchor.save(args.out)
    print(f"已保存: {args.out}")

    if args.preview:
        prev = Image.new("RGB", (512 * 2 + 10, 512), (200, 200, 200))
        prev.paste(src.convert("RGB"), (0, 0))
        bg = Image.new("RGBA", (512, 512), (255, 255, 255, 255))
        bg.alpha_composite(cleaned.resize((512, 512), Image.LANCZOS))
        prev.paste(bg.convert("RGB"), (512 + 10, 0))
        prev.save(ROOT / "_walk_gen" / "anchor_preview.png")
        print(f"对比预览: {ROOT / '_walk_gen' / 'anchor_preview.png'}")


if __name__ == "__main__":
    main()
