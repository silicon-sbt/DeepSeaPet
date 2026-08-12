import paramiko, sys, os

host = 'connect.westb.seetacloud.com'
port = 40700

local_file = sys.argv[1] if len(sys.argv) > 1 else 'generate_sprites.py'
remote_path = f'/root/autodl-tmp/{os.path.basename(local_file)}'

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, port=port, username='root', password='REDACTED', timeout=20)

# 上传
print(f'上传 {local_file}...', flush=True)
sftp = c.open_sftp()
sftp.put(local_file, remote_path)
sftp.close()
print('上传完成!', flush=True)

# 运行
print(f'执行 {remote_path}...', flush=True)
_, out, err = c.exec_command(f'/root/miniconda3/bin/python {remote_path} 2>&1', timeout=1800)

# 实时打印输出
import select
channel = out.channel
while not channel.closed or channel.recv_ready() or channel.recv_stderr_ready():
    if channel.recv_ready():
        data = channel.recv(4096)
        if data:
            print(data.decode(), end='', flush=True)
    if channel.recv_stderr_ready():
        data = channel.recv_stderr(4096)
        if data:
            print(data.decode(), end='', flush=True)
    if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
        break

print(f'\n退出码: {channel.exit_status}', flush=True)
c.close()
