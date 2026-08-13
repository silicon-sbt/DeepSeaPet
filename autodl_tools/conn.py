"""AutoDL 连接统一入口：解析 autodl_tools/ssh，克隆实例后只改这一个文件"""
import os, re, sys
import paramiko

_SSH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ssh')

def load_conn():
    """从 ssh 文件解析 (host, port, user, password)"""
    with open(_SSH_FILE, encoding='utf-8') as f:
        text = f.read()
    m = re.search(r'-p\s+(\d+)\s+(\w+)@([\w.\-]+)', text)
    pw = re.search(r'密码[:：]\s*(\S+)', text)
    if not m or not pw:
        raise ValueError(f'无法从 {_SSH_FILE} 解析连接信息')
    return m.group(3), int(m.group(1)), m.group(2), pw.group(1)

def connect(timeout=20):
    host, port, user, pw = load_conn()
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, port=port, username=user, password=pw, timeout=timeout)
    return c

def upload_and_nohup(local_files, remote_log, remote_cmd):
    """上传本地文件，nohup 后台执行 remote_cmd（stdout/stderr 重定向到 remote_log）"""
    sys.stdout.reconfigure(encoding='utf-8')
    c = connect()
    sftp = c.open_sftp()
    for local, remote in local_files.items():
        sftp.put(local, remote)
    sftp.close()
    _, out, err = c.exec_command(f'nohup {remote_cmd} > {remote_log} 2>&1 & echo started pid=$!', timeout=30)
    print(out.read().decode(), flush=True)
    et = err.read().decode()
    if et:
        print('STDERR:', et[:300], flush=True)
    c.close()
