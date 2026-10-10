"""看 v2 角色本体质量：ASCII 渲染 f0 判断角色是否画好"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from PIL import Image

f = '二次元Q版精灵待机呼吸动画 (2).png'
arr = np.array(Image.open(f).convert('RGB')).astype(float)
bg = np.array([175.0, 255.0, 127.0])
dist = np.abs(arr - bg).max(axis=2)

def ascii_render(x0, x1, y0, y1, cols=96, title=''):
    sub = arr[y0:y1, x0:x1]
    d = dist[y0:y1, x0:x1]
    mask = d > 40
    rows = max(1, int((y1-y0) * cols / (x1-x0) / 2))
    out = []
    for ry in range(rows):
        sy0 = int(ry*(y1-y0)/rows); sy1 = int((ry+1)*(y1-y0)/rows)
        line = []
        for cx in range(cols):
            sx0 = int(cx*(x1-x0)/cols); sx1 = int((cx+1)*(x1-x0)/cols)
            blk = mask[sy0:sy1, sx0:sx1]
            subblk = sub[sy0:sy1, sx0:sx1]
            bm = subblk[:,:,2]-subblk[:,:,0]
            gm = subblk[:,:,1]-subblk[:,:,0]
            if blk.sum() > blk.size*0.3:
                if bm[blk].mean() > 15: line.append('B')
                elif gm[blk].mean() > 20: line.append('G')
                else: line.append('#')
            elif blk.sum() > 0: line.append('.')
            else: line.append(' ')
        out.append(''.join(line))
    print(f'=== {title} ===')
    print('\n'.join(out)); print()

# f0 完整
ascii_render(0, 720, 0, 720, cols=96, title='f0 全貌 (B=蓝 G=绿 #=白/其他)')
