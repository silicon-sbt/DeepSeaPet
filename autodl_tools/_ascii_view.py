"""ASCII 渲染图片，让我"看"到画面轮廓（基准图 vs 生成帧对比）"""
from PIL import Image
import numpy as np

CHARS = "@%#*+=-:. "  # 从左到右：暗→亮

def render(path, w=60):
    im = Image.open(path).convert("L")
    h = int(w * im.height / im.width * 0.5)
    a = np.asarray(im.resize((w, h)))
    lines = []
    for row in a:
        lines.append("".join(CHARS[int(v) * len(CHARS) // 256] for v in row))
    return "\n".join(lines)

if __name__ == "__main__":
    import glob, os, sys
    here = os.path.dirname(os.path.abspath(__file__))
    states = sys.argv[1:] or ["idle", "hide", "walk"]
    for st in states:
        base = os.path.join(here, f"base_refs/{st}_00.png")
        gen = glob.glob(os.path.join(here, f"sprites_video_dl/{st}/*_00.png"))
        if not os.path.exists(base) or not gen:
            print(f"=== {st}: 缺文件 ===")
            continue
        print(f"===== {st}  基准图 =====")
        print(render(base))
        print(f"===== {st}  生成首帧 =====")
        print(render(gen[0]))
        print()
