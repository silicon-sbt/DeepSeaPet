"""本地 rembg 抠图：旧版迈步 walk_00/walk_01 → 512×512 透明 → 覆盖 sprites/"""
from PIL import Image
from rembg import remove
import sys

SRC = "autodl_tools/_walk_dl_v1"
DST = "module_5_assets/sprites"

for name in ("walk_00", "walk_01"):
    img = Image.open(f"{SRC}/{name}.png").convert("RGBA")
    out = remove(img)
    out = out.resize((512, 512), Image.LANCZOS)
    out.save(f"{DST}/{name}.png")
    print(f"{name} -> {DST}/{name}.png ({out.size}, {out.mode})", flush=True)

print("DONE")
