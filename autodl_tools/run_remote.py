"""向 AutoDL 发送单条命令（连接信息走 conn.py，只改 ssh 文件）"""
import sys
from conn import connect

cmd = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else 'nvidia-smi'
print(f'>>> {cmd}', flush=True)

c = connect()
_, out, err = c.exec_command(cmd, timeout=300)
print(out.read().decode(), flush=True)
err_text = err.read().decode()
if err_text:
    print('STDERR:', err_text[:500], flush=True)
c.close()
