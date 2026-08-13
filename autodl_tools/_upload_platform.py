"""上传 lightx2v_platform 并验证 lightx2v import"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conn

c = conn.connect()
sftp = c.open_sftp()
sftp.put(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_platform.tgz"),
         "/root/autodl-tmp/_platform.tgz")
sftp.close()

script = '''cd /root/autodl-tmp && tar xzf _platform.tgz -C lightx2v && ls lightx2v/ && /root/miniconda3/bin/python -c "import lightx2v; print('lightx2v import OK'); from lightx2v import LightX2VPipeline; print('LightX2VPipeline OK')"'''
_, out, err = c.exec_command(script, timeout=120)
print(out.read().decode(errors="replace"))
e = err.read().decode(errors="replace")
if e:
    print("STDERR:", e[-800:])
c.close()
