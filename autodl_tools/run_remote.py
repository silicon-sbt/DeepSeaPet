"""向 AutoDL 发送单条命令"""
import paramiko, sys

host = 'connect.westb.seetacloud.com'
port = 40700

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, port=port, username='root', password='REDACTED', timeout=20)

cmd = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else 'nvidia-smi'
print(f'>>> {cmd}', flush=True)

_, out, err = c.exec_command(cmd, timeout=300)
print(out.read().decode(), flush=True)
err_text = err.read().decode()
if err_text:
    print('STDERR:', err_text[:500], flush=True)
c.close()
