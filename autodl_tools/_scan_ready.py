"""扫盘：等克隆完毕 + 内容级核验全部文件，ALL_READY 后退出。

每 30 秒：SSH 连接（克隆中连不上则重试）→ 上传 _verify_ready.py → 执行内容级核验
（文件头/JSON/PNG，非仅大小）→ 全过打印 ALL_READY 退出。
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conn import connect

HERE = os.path.dirname(os.path.abspath(__file__))
VERIFY = "/root/autodl-tmp/_verify_ready.py"
LOCAL_VERIFY = os.path.join(HERE, "_verify_ready.py")

def setup():
    c = connect(timeout=15)
    sftp = c.open_sftp()
    sftp.put(LOCAL_VERIFY, VERIFY)
    sftp.close()
    return c

c = None
while True:
    stamp = time.strftime("%H:%M:%S")
    try:
        if c is None:
            c = setup()
            print(f"[{stamp}] 已连接，核验脚本已上传", flush=True)
        _, out, _ = c.exec_command(f"/root/miniconda3/bin/python {VERIFY}", timeout=40)
        text = out.read().decode()
        for line in text.strip().splitlines():
            print(f"  {line}", flush=True)
        if "ALL_READY" in text:
            print(f"[{stamp}] 克隆完毕，全部文件内容级完整", flush=True)
            break
        print(f"[{stamp}] 文件未就绪（克隆中），30s 后再查", flush=True)
    except Exception as e:
        print(f"[{stamp}] 连接失败（克隆/开机中）: {str(e)[:60]}", flush=True)
        c = None
    time.sleep(30)
