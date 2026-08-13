"""打印 lightx2v 完整导入 traceback，定位下一个缺失"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conn

c = conn.connect()
sftp = c.open_sftp()
PROBE = r'''
import traceback
try:
    import lightx2v
    from lightx2v import LightX2VPipeline
    print("IMPORT_FULL_OK")
except Exception:
    traceback.print_exc()
'''
with sftp.open("/tmp/_probe2.py", "w") as f:
    f.write(PROBE)
sftp.close()
_, out, err = c.exec_command("/root/miniconda3/bin/python /tmp/_probe2.py", timeout=120)
print(out.read().decode(errors="replace"))
e = err.read().decode(errors="replace")
if e:
    print("STDERR:", e[-300:])
c.close()
