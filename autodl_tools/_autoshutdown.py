"""布置自动关机 watchdog：下载脚本结束（成功或失败）后自动 shutdown。
用 kill -0 <pid> 检测下载进程存活，避开 pgrep/pkill -f 匹配自身命令行的自杀陷阱。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conn import connect

c = connect()

# 1. 动态查下载脚本的 bash 进程 pid（不硬编码）
_, out, _ = c.exec_command("ps aux | grep _dl_ipadapter_final.sh | grep -v grep")
ps_out = out.read().decode().strip()
lines = [l for l in ps_out.split("\n") if "_dl_ipadapter_final.sh" in l]
if not lines:
    print("警告：找不到下载进程，不布置关机（下载可能已结束）")
    c.close()
    sys.exit(1)
pid = lines[0].split()[1]
print(f"下载脚本 pid={pid}", flush=True)

# 2. watchdog：pid 退出后 sleep 5 缓冲，再关机
watchdog = (
    f"nohup bash -c 'while kill -0 {pid} 2>/dev/null; do sleep 30; done; "
    f"sleep 5; shutdown -h now' > /tmp/autoshutdown.log 2>&1 & echo watchdog_ready"
)
_, out, err = c.exec_command(watchdog)
print(out.read().decode().strip(), flush=True)
et = err.read().decode()
if et:
    print("STDERR:", et[:200], flush=True)
c.close()
print("已布置：下载结束后自动关机（日志 /tmp/autoshutdown.log）")
