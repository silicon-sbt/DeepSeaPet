"""通用：轮询远端日志，出现完成词或失败标记即退出（静默，复用同一 SSH 连接）
用法: python _poll_remote.py <远端日志> <完成词>
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conn import connect

LOG = sys.argv[1] if len(sys.argv) > 1 else '/root/autodl-tmp/build.log'
DONE = sys.argv[2] if len(sys.argv) > 2 else '组装完成'
FAIL = ['Traceback (most recent', 'AssertionError', 'IndexError', 'RuntimeError', 'KeyError', '下载失败']

c = connect()
try:
    while True:
        try:
            _, out, _ = c.exec_command(f'tail -c 4000 {LOG}')
            data = out.read().decode(errors='replace')
        except Exception as e:
            print(f'SSH执行失败: {e}', flush=True)
            time.sleep(60)
            continue
        if DONE in data:
            print('DONE', flush=True)
            print(data[-1200:], flush=True)
            break
        if any(m in data for m in FAIL):
            print('FAIL', flush=True)
            print(data[-1500:], flush=True)
            break
        time.sleep(45)
finally:
    c.close()
