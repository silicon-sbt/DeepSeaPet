"""下载 9 状态 72 帧 + rembg 抠图 → module_5_assets/sprites/{state}_00~07.png（透明背景）
用法: python _download_rembg.py [state ...]   # 不传则全部 9 状态
流式：sftp.getfo 到内存 → 抠图 → 保存，不落临时磁盘。
"""
import sys, os, io, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import conn

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("U2NET_HOME", os.path.join(PROJ, "models"))

import numpy as np
from PIL import Image
from rembg import remove, new_session

STATES = ["idle", "happy", "walk", "hide", "peek", "sleep", "lying", "held", "flying"]
REMOTE_BASE = "/root/autodl-tmp/sprites_output"
DST = os.path.join(PROJ, "module_5_assets", "sprites")
SIZE = 512


def main():
    states = sys.argv[1:] or STATES
    os.makedirs(DST, exist_ok=True)
    print("加载 u2net session ...", flush=True)
    session = new_session("u2net")
    print("session 就绪", flush=True)

    c = conn.connect()
    sftp = c.open_sftp()
    total = 0
    t0 = time.time()
    for st in states:
        alpha_means = []
        for i in range(8):
            r = f"{REMOTE_BASE}/{st}/{st}_{i:02d}.png"
            buf = io.BytesIO()
            sftp.getfo(r, buf)
            buf.seek(0)
            img = Image.open(buf).convert("RGB")
            out = remove(img, session=session)
            out = out.resize((SIZE, SIZE), Image.LANCZOS)
            a = np.array(out)[:, :, 3]
            out.save(os.path.join(DST, f"{st}_{i:02d}.png"))
            alpha_means.append(a.mean())
            total += 1
        print(f"{st}: 8 帧完成，不透明均值 {np.mean(alpha_means):.0f}/255", flush=True)
    sftp.close()
    c.close()
    print(f"合计 {total} 帧 → {DST}，耗时 {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
