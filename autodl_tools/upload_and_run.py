"""上传本地文件到 AutoDL 并前台执行（实时打印输出）

连接信息统一走 conn.py 解析 autodl_tools/ssh——克隆实例后端口/密码必变，
只改 ssh 文件一处。历史遗留的 host/port/password 字面量已清除。
用法: python upload_and_run.py <本地文件>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conn import connect

local_file = sys.argv[1] if len(sys.argv) > 1 else 'generate_sprites.py'
remote_path = f'/root/autodl-tmp/{os.path.basename(local_file)}'

c = connect()
try:
    print(f'上传 {local_file}...', flush=True)
    sftp = c.open_sftp()
    sftp.put(local_file, remote_path)
    sftp.close()
    print('上传完成!', flush=True)

    print(f'执行 {remote_path}...', flush=True)
    _, out, _ = c.exec_command(f'/root/miniconda3/bin/python {remote_path} 2>&1', timeout=1800)

    # 实时打印（用 channel 而非 out.read()，否则要等命令跑完才出字）
    channel = out.channel
    while not channel.closed or channel.recv_ready() or channel.recv_stderr_ready():
        if channel.recv_ready():
            data = channel.recv(4096)
            if data:
                print(data.decode(errors='replace'), end='', flush=True)
        if channel.recv_stderr_ready():
            data = channel.recv_stderr(4096)
            if data:
                print(data.decode(errors='replace'), end='', flush=True)
        if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
            break

    print(f'\n退出码: {channel.exit_status}', flush=True)
finally:
    c.close()
