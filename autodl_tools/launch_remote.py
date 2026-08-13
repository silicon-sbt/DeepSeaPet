"""通用：上传本地文件到 AutoDL 并 nohup 后台执行命令（日志 /root/autodl-tmp/{basename}.log）
用法:
  python launch_remote.py <远端命令> -- <本地路径> <远端路径> [<本地> <远端> ...]
示例:
  python launch_remote.py "/root/miniconda3/bin/python /root/autodl-tmp/_fast_download.py" -- autodl_tools/_fast_download.py /root/autodl-tmp/_fast_download.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conn import upload_and_nohup

sys.stdout.reconfigure(encoding='utf-8')

argv = sys.argv[1:]
if '--' in argv:
    i = argv.index('--')
    cmd = ' '.join(argv[:i])
    pairs = argv[i + 1:]
    files = {pairs[j]: pairs[j + 1] for j in range(0, len(pairs), 2)}
else:
    cmd = ' '.join(argv)
    files = {}

remote_script = cmd.split()[-1]
log = '/root/autodl-tmp/' + os.path.splitext(os.path.basename(remote_script))[0] + '.log'
upload_and_nohup(files, log, cmd)
print(f'已在后台启动，日志: {log}')
