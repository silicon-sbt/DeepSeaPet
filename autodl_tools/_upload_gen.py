"""上传基准图 + 生成脚本到 AutoDL。用 sftp.putfo 传 file object，绕开本地中文路径编码问题。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conn import connect

HERE = os.path.dirname(os.path.abspath(__file__))
REF = r"E:\code\deepseek的桌宠\module_5_assets\base_idle.png"

c = connect()
sftp = c.open_sftp()

# 基准图（本地中文路径，用 putfo 传 file object）
c.exec_command("mkdir -p /root/autodl-tmp/sprites_output/idle")[1].read()
with open(REF, "rb") as f:
    sftp.putfo(f, "/root/autodl-tmp/sprites_output/idle/idle_00.png")

# 生成脚本
with open(os.path.join(HERE, "generate_sdxl.py"), "rb") as f:
    sftp.putfo(f, "/root/autodl-tmp/generate_sdxl.py")

sftp.close()
_, out, err = c.exec_command("ls -la /root/autodl-tmp/sprites_output/idle/ /root/autodl-tmp/generate_sdxl.py")
print(out.read().decode())
print(err.read().decode())
c.close()
print("上传完成")
