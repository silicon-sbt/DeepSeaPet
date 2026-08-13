"""持续 tail 远端生成日志，输出进度关键行；检测到"全部完成"或致命错误即退出"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conn

LOG = "/root/autodl-tmp/generate_lightx2v.log"
KEY = re.compile(
    r'\[(idle|hide|peek|walk|sleep|happy|lying)\]'
    r'|生成失败|视频生成完成|提取 \d+ 帧完成'
    r'|全部完成|文件总数|Traceback|CUDA out of memory|OutOfMemory|Error|error'
)

c = conn.connect()
ch = c.get_transport().open_session()
ch.exec_command(f"tail -f {LOG}")
ch.settimeout(None)  # 无限阻塞等待新行；模型加载/推理间隙可能几十秒无日志
buf = b""
done = False
while not done:
    try:
        data = ch.recv(4096)
    except Exception:
        print("WATCH_RECV_ERR", flush=True)
        break
    if not data:
        print("WATCH_EOF", flush=True)
        break
    buf += data
    while b"\n" in buf:
        line, buf = buf.split(b"\n", 1)
        s = line.decode(errors="replace").strip()
        if KEY.search(s):
            print(s, flush=True)
            if "全部完成" in s or "Traceback" in s or "CUDA out of memory" in s:
                done = True
c.close()
