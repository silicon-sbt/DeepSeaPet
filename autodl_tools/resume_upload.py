"""断点续传上传 — 检测远程文件大小，从断点继续（连接信息走 conn.py）

注意：单线程 + 大文件很慢，能不用就别用；多线程版本见 multi_upload.py。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conn import connect

LOCAL = r"E:\code\deepseek的桌宠\animagine_model\models\ModelE--Animagine-XL\snapshots\master\animagineXL40_v40.safetensors"
REMOTE = "/root/autodl-tmp/models/animagineXL40_v40.safetensors"
CHUNK = 8 * 1024 * 1024  # 8MB

total = os.path.getsize(LOCAL)
print(f"本地文件: {total:,} 字节 ({total/1024**3:.2f} GB)", flush=True)

c = connect(timeout=30)
try:
    sftp = c.open_sftp()

    # 检查远程已有大小
    try:
        remote_size = sftp.stat(REMOTE).st_size
        print(f"远程已有: {remote_size:,} 字节 ({remote_size/total*100:.1f}%)", flush=True)
    except FileNotFoundError:
        remote_size = 0
        print("远程无文件，从头开始", flush=True)

    if remote_size >= total:
        print("已完成！", flush=True)
        sftp.close()
        sys.exit(0)

    # 追加模式打开远程文件
    print(f"从 {remote_size:,} 处继续上传...", flush=True)
    rf = sftp.open(REMOTE, 'ab')

    t0 = time.time()
    written = remote_size
    last_print = written
    last_time = t0

    with open(LOCAL, 'rb') as lf:
        lf.seek(remote_size)
        while True:
            data = lf.read(CHUNK)
            if not data:
                break
            rf.write(data)
            written += len(data)

            # 每 30 秒或每 5% 打印进度
            now = time.time()
            if now - last_time >= 30 or written - last_print >= total * 0.05:
                elapsed = now - t0
                speed = (written - remote_size) / elapsed / 1024**2 if elapsed > 0 else 0
                remaining = total - written
                eta = remaining / (speed * 1024**2) if speed > 0 else 0
                print(f"  {written/total*100:.1f}%  "
                      f"({written/1024**3:.2f}/{total/1024**3:.2f} GB)  "
                      f"{speed:.1f} MB/s  ETA {eta/60:.0f}min", flush=True)
                last_print = written
                last_time = now

    rf.close()
    sftp.close()

    elapsed = time.time() - t0
    speed = (total - remote_size) / elapsed / 1024**2 if elapsed > 0 else 0
    print(f"DONE={written} 总耗时 {elapsed/60:.1f}min 平均 {speed:.1f} MB/s", flush=True)
finally:
    c.close()
