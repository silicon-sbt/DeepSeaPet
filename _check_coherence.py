"""检查img2img生成的帧间连贯性"""
from PIL import Image
import os

d = r'E:\code\deepseek的桌宠\module_5_assets\sprites'

def pixel_diff(img1, img2):
    p1 = list(img1.getdata())
    p2 = list(img2.getdata())
    total = 0
    count = 0
    for a, b in zip(p1, p2):
        for i in range(3):
            total += abs(a[i] - b[i])
            count += 1
    return total / count

for state in ['idle', 'walk', 'hide', 'peek', 'sleep', 'happy', 'lying']:
    frames = sorted([f for f in os.listdir(d) if f.startswith(f'{state}_') and f.endswith('.png')])
    if len(frames) < 2:
        continue

    imgs = [Image.open(os.path.join(d, f)) for f in frames]

    # 每帧与帧0的差异（是否保持一致性）
    diffs_from_base = []
    for i in range(1, len(imgs)):
        d = pixel_diff(imgs[0], imgs[i])
        diffs_from_base.append(d)

    # 相邻帧间差异
    adj_diffs = [pixel_diff(imgs[i], imgs[i+1]) for i in range(len(imgs)-1)]

    avg_base = sum(diffs_from_base) / len(diffs_from_base)
    avg_adj = sum(adj_diffs) / len(adj_diffs)

    print(f'{state}: 与帧0平均差异={avg_base:.1f}, 邻帧平均差异={avg_adj:.1f}, 帧间范围=({min(adj_diffs):.1f}-{max(adj_diffs):.1f})')

    for img in imgs:
        img.close()
