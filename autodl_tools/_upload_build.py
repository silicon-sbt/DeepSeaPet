"""上传组装脚本 + 基准图到 AutoDL，nohup 后台启动组装"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conn import connect, upload_and_nohup

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

# 创建 generate_video.py 预期的基准图目录
c = connect()
sftp = c.open_sftp()
for d in ('/root/autodl-tmp/sprites_output', '/root/autodl-tmp/sprites_output/idle'):
    try:
        sftp.mkdir(d)
    except Exception:
        pass
sftp.close()
c.close()
print('目录就绪', flush=True)

files = {
    os.path.join(ROOT, 'autodl_tools', '_build_pipeline.py'): '/root/autodl-tmp/_build_pipeline.py',
    os.path.join(ROOT, 'module_5_assets', 'base_idle.png'): '/root/autodl-tmp/sprites_output/idle/idle_00.png',
}
upload_and_nohup(files, '/root/autodl-tmp/build.log',
                 '/root/miniconda3/bin/python -u /root/autodl-tmp/_build_pipeline.py')
print('组装已在后台启动，日志 /root/autodl-tmp/build.log', flush=True)
