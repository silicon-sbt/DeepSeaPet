"""连接 AutoDL 服务器，检查环境（连接信息走 conn.py）"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conn import connect

print('连接中...', flush=True)
try:
    c = connect(timeout=25)
    print('已连接!', flush=True)
    for cmd_name, cmd in [
        ('GPU', 'nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>&1'),
        ('Python', 'python3 -V 2>&1; python -V 2>&1'),
        ('pip包', 'pip list 2>/dev/null | grep -iE "torch|comfy|diffusers|xformers" || echo "(无)"'),
        ('目录', 'ls /root/ 2>/dev/null | head -15 || echo "(空)"'),
        ('磁盘', 'df -h / | tail -1'),
    ]:
        _, out, err = c.exec_command(cmd)
        result = out.read().decode().strip() or err.read().decode().strip()
        print(f'[{cmd_name}] {result}', flush=True)
    c.close()
except Exception as e:
    print(f'连接失败: {e}', flush=True)
    sys.exit(1)
