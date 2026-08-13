"""rembg 抠图：_frames_local/f*.png → module_5_assets/sprites/idle_*.png (720x720 RGBA)"""
import sys, os, time
sys.stdout.reconfigure(encoding='utf-8')

# 让 rembg 从项目目录加载模型，避免下到 C 盘
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["U2NET_HOME"] = os.path.join(PROJ, "models")
os.makedirs(os.path.join(PROJ, "models"), exist_ok=True)

import numpy as np
from PIL import Image
from rembg import remove, new_session

SRC = os.path.join(PROJ, '_frames_local')
DST = os.path.join(PROJ, 'module_5_assets', 'sprites')
os.makedirs(DST, exist_ok=True)

print(f'模型目录(U2NET_HOME): {os.environ["U2NET_HOME"]}')
t0 = time.time()
print('加载 u2net session (首次略慢)...')
session = new_session('u2net')
print(f'session 就绪 {time.time()-t0:.1f}s')

for i in range(8):
    fp = os.path.join(SRC, f'f{i}.png')
    img = Image.open(fp).convert('RGB')
    t1 = time.time()
    out = remove(img, session=session)
    out = out.resize((720, 720), Image.LANCZOS)
    dp = os.path.join(DST, f'idle_{i:02d}.png')
    out.save(dp)
    a = np.array(out)[:,:,3]
    print(f'  idle_{i:02d}.png 透明{(a==0).mean()*100:.1f}% {time.time()-t1:.1f}s → {dp}')

print(f'\n完成! 8帧 → {DST} 总耗时 {time.time()-t0:.0f}s')
