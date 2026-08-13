"""下载 7 状态基准图到本地 base_refs/，用于与生成帧对比"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conn

LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "base_refs")
os.makedirs(LOCAL, exist_ok=True)
STATES = ["idle", "hide", "peek", "walk", "sleep", "happy", "lying"]

c = conn.connect()
sftp = c.open_sftp()
for st in STATES:
    r = f"/root/autodl-tmp/sprites_output/{st}/{st}_00.png"
    l = os.path.join(LOCAL, f"{st}_00.png")
    sftp.get(r, l)
    print("下载:", st)
sftp.close()
c.close()
