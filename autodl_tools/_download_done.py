"""下载已完成(>=8帧)状态的精灵帧到本地 sprites_video_dl/，进行中/未完成自动跳过"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conn

LOCAL_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites_video_dl")
STATES = ["idle", "hide", "peek", "walk", "sleep", "happy", "lying"]
REMOTE_BASE = "/root/autodl-tmp/sprites_video"

c = conn.connect()
sftp = c.open_sftp()
total = 0
for st in STATES:
    rdir = f"{REMOTE_BASE}/{st}"
    try:
        files = sorted(f for f in sftp.listdir(rdir) if f.endswith(".png"))
    except IOError:
        continue
    if len(files) < 8:
        print(f"{st}: 进行中 ({len(files)}/8)，跳过", flush=True)
        continue
    ldir = os.path.join(LOCAL_BASE, st)
    os.makedirs(ldir, exist_ok=True)
    for fn in files:
        sftp.get(f"{rdir}/{fn}", os.path.join(ldir, fn))
    print(f"{st}: 下载 {len(files)} 帧", flush=True)
    total += len(files)
sftp.close()
c.close()
print(f"合计下载 {total} 帧 → {LOCAL_BASE}", flush=True)
