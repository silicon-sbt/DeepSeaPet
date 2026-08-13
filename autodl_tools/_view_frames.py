"""ASCII 渲染 f4-f7 及水印填充效果"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from PIL import Image

OUT = r'E:\code\deepseek的桌宠\_frames_local'
bg = np.array([119.0, 205.0, 142.0])

def ascii_render(f, cols=88, title=''):
    arr = f
    h, w = arr.shape[:2]
    d = np.abs(arr - bg).max(axis=2)
    mask = d > 40
    rows = max(1, int(h * cols / w / 2))
    out = []
    for ry in range(rows):
        sy0 = int(ry*h/rows); sy1 = int((ry+1)*h/rows)
        line = []
        for cx in range(cols):
            sx0 = int(cx*w/cols); sx1 = int((cx+1)*w/cols)
            blk = mask[sy0:sy1, sx0:sx1]
            if blk.sum() > blk.size*0.5:
                line.append('#')
            elif blk.sum() > blk.size*0.15:
                line.append('+')
            elif blk.sum() > 0:
                line.append('.')
            else:
                line.append(' ')
        out.append(''.join(line))
    print(f'=== {title} ===')
    print('\n'.join(out))
    print()

frames = [np.array(Image.open(os.path.join(OUT, f'f{i}.png')).convert('RGB')).astype(float) for i in range(8)]
# f4-f7 下半部（含角色脚部）
for i in [4, 5, 6, 7]:
    ascii_render(frames[i][::2], cols=80, title=f'f{i}')

# 水印填充效果：检查 f7 右下角水印区是否与背景一致
sub = frames[7][580:719, 540:719]
d = np.abs(sub - bg).max(axis=2)
print(f'f7 水印填充区: 残留异常像素 {(d>15).sum()}/{d.size} (应为0)')
