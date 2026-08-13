"""诊断 SFTP 上传失败：对比相对/绝对路径 + listdir/stat 定位问题层"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conn

c = conn.connect()
sftp = c.open_sftp()

# 1. 本地文件是否存在
abs_local = os.path.join(os.getcwd(), "generate_lightx2v.py")
print("cwd:", os.getcwd())
print("本地存在:", os.path.exists("generate_lightx2v.py"), "abs:", os.path.exists(abs_local))

# 2. 远端 listdir / stat
try:
    print("listdir:", sftp.listdir("/root/autodl-tmp")[:6])
except Exception as e:
    print("listdir FAIL:", repr(e))
try:
    print("stat:", sftp.stat("/root/autodl-tmp"))
except Exception as e:
    print("stat FAIL:", repr(e))

# 3. 逐层 put 尝试
for label, remote in [("abs", "/root/autodl-tmp/generate_lightx2v.py"),
                      ("rel", "generate_lightx2v.py")]:
    try:
        sftp.put(abs_local if label == "abs" else "generate_lightx2v.py", remote)
        print(f"PUT OK ({label}): {remote}")
        break
    except Exception as e:
        print(f"PUT FAIL ({label}): {type(e).__name__}: {str(e)[:150]}")

sftp.close()
c.close()
