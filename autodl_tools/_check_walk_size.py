"""临时：对比 walk/idle sprite 角色 alpha 包围盒（检查动画切换角色大小一致性）"""
from PIL import Image
import numpy as np

for f in ("walk_00", "walk_01", "idle_00"):
    a = np.array(Image.open(f"module_5_assets/sprites/{f}.png").convert("RGBA"))
    ys, xs = np.where(a[:, :, 3] > 0)
    if len(xs) == 0:
        print(f, "EMPTY")
        continue
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    print(f"{f}: bbox x[{x0},{x1}] y[{y0},{y1}] W={x1-x0} H={y1-y0} center_x={(x0+x1)/2:.0f}")
