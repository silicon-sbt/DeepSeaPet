"""对比两图 + 精细扫描 (1).png 左上角"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from PIL import Image

f1 = '二次元Q版精灵待机呼吸动画.png'
f2 = '二次元Q版精灵待机呼吸动画 (1).png'
a = np.array(Image.open(f1).convert('RGB')).astype(float)
b = np.array(Image.open(f2).convert('RGB')).astype(float)
diff = np.abs(a-b)
print(f'两图逐像素最大差: {diff.max():.0f} 平均差: {diff.mean():.3f}')
if diff.max() > 1:
    m = diff.max(axis=2) > 5
    ys, xs = np.where(m)
    print(f'差异像素: {len(ys)} bbox x[{xs.min()}-{xs.max()}] y[{ys.min()}-{ys.max()}]')
else:
    print('两图完全相同')

# 精细扫描 (1).png 左上角 x0-400 y0-120
bg = np.array([118.0, 203.0, 144.0])
arr = b
h, w = arr.shape[:2]
dist = np.abs(arr - bg).max(axis=2)

for (x0,x1,y0,y1) in [(0,200,0,80), (0,300,0,60), (0,400,0,120), (0,500,0,200)]:
    sub = dist[y0:y1, x0:x1]
    mask = sub > 15
    cnt = mask.sum()
    if cnt:
        ys, xs = np.where(mask)
        px = arr[y0:y1, x0:x1][ys, xs]
        blue = (px[:,2]-px[:,0]) > 15
        print(f'x[{x0}-{x1}] y[{y0}-{y1}]: {cnt}px bbox x[{x0+xs.min()}-{x0+xs.max()}] y[{y0+ys.min()}-{y0+ys.max()}] 蓝{blue.sum()} 白{(~blue).sum()}')
    else:
        print(f'x[{x0}-{x1}] y[{y0}-{y1}]: 干净')
