"""卸载错配的 torchaudio 2.11（需 CUDA13），并重测 lightx2v import"""
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
with sftp.open("/tmp/_probe3.py", "w") as f:
    f.write(PROBE)
sftp.close()

script = "/root/miniconda3/bin/pip uninstall -y torchaudio 2>&1 | tail -1 && /root/miniconda3/bin/python /tmp/_probe3.py"
_, out, err = c.exec_command(script, timeout=120)
print(out.read().decode(errors="replace"))
e = err.read().decode(errors="replace")
if e:
    print("STDERR:", e[-200:])
c.close()
