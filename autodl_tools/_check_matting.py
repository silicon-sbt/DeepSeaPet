"""ASCII 渲染强绿像素位置，判断是角色本身还是绿边"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from PIL import Image

DST = r'E:\code\deepseek的桌宠\module_5_assets\sprites'
img = Image.open(os.path.join(DST, 'idle_00.png')).convert('RGBA')
arr = np.array(img).astype(float)
r, g, b, a = arr[:,:,0], arr[:,:,1], arr[:,:,2], arr[:,:,3]

# 三通道图
opaque = a > 128
greenish = (g > 140) & (g - r > 30) & opaque
bluish = (b - r > 20) & opaque
other = opaque & ~greenish & ~bluish

h, w = 720, 720
cols = 96
rows = int(h * cols / w / 2)
print('G=强绿  B=蓝  .=其他不透明  .=透明')
for ry in range(rows):
    sy0 = int(ry*h/rows); sy1 = int((ry+1)*h/rows)
    line = []
    for cx in range(cols):
        sx0 = int(cx*w/cols); sx1 = int((cx+1)*w/cols)
        seg = (slice(sy0,sy1), slice(sx0,sx1))
        gcnt = greenish[seg].sum()
        bcnt = bluish[seg].sum()
        ocnt = other[seg].sum()
        tot = (sy1-sy0)*(sx1-sx0)
        if gcnt > bcnt and gcnt > ocnt and gcnt > tot*0.2:
            line.append('G')
        elif bcnt > ocnt and bcnt > tot*0.25:
            line.append('B')
        elif ocnt > tot*0.25:
            line.append('.')
        elif ocnt > 0:
            line.append('+')
        else:
            line.append(' ')
    print(''.join(line))
