"""上传 generate_lightx2v.py 并 nohup 后台启动全量生成（conn 直连，避开 launch_remote 上传怪癖）"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conn

c = conn.connect()
sftp = c.open_sftp()
local = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate_lightx2v.py"))
remote = "/root/autodl-tmp/generate_lightx2v.py"
sftp.put(local, remote)
print("上传完成:", remote)
sftp.close()

log = "/root/autodl-tmp/generate_lightx2v.log"
cmd = f"/root/miniconda3/bin/python -u {remote}"
_, out, err = c.exec_command(f'nohup {cmd} > {log} 2>&1 & echo started pid=$!', timeout=30)
print(out.read().decode().strip())
et = err.read().decode()
if et:
    print("STDERR:", et[:300])
c.close()
print("已后台启动，日志:", log)
