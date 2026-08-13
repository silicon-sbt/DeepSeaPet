"""分析帧角色位置漂移 + 角色区相似度"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from PIL import Image

OUT = r'E:\code\deepseek的桌宠\_frames_local'
bg = np.array([119.0, 205.0, 142.0])

frames = [np.array(Image.open(os.path.join(OUT, f'f{i}.png')).convert('RGB')).astype(float) for i in range(8)]

print('每帧角色 bbox + 中心:')
for i, f in enumerate(frames):
    d = np.abs(f - bg).max(axis=2)
    m = d > 40
    ys, xs = np.where(m)
    if len(ys):
        cx, cy = (xs.min()+xs.max())/2, (ys.min()+ys.max())/2
        print(f'  f{i}: bbox x[{xs.min()}-{xs.max()}] y[{ys.min()}-{ys.max()}] 中心({cx:.0f},{cy:.0f})')

# 角色区相似度：把每帧非背景像素块对齐后比较
def content(f, bg):
    d = np.abs(f - bg).max(axis=2)
    m = d > 40
    ys, xs = np.where(m)
    if not len(ys): return None
    return f[ys.min():ys.max()+1, xs.min():xs.max()+1]

print('\n内容块尺寸 + 与帧0的内容差异:')
base = content(frames[0], bg)
for i in range(1, 8):
    c = content(frames[i], bg)
    if c is None or base is None: continue
    # resize 到相同大小后比较（用 PIL 简单缩放）
    from PIL import Image as PI
    b0 = PI.fromarray(base.astype(np.uint8)).resize((256, 256))
    ci = PI.fromarray(c.astype(np.uint8)).resize((256, 256))
    d = np.abs(np.array(b0).astype(float) - np.array(ci).astype(float))
    m = d.mean(axis=2) > 40
    diff = d[m].mean() if m.sum() else 0
    frac = m.mean()
    print(f'  f{i}: 内容尺寸{base.shape[1]}x{base.shape[0]} vs {c.shape[1]}x{c.shape[0]} 显著差异{frac*100:.1f}% 均差{diff:.1f}')
