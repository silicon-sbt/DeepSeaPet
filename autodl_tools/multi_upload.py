"""多线程断点续传 — 4 路并行上传剩余数据块，最后合并"""
import paramiko, os, sys, time, threading

host = 'connect.westd.seetacloud.com'
port = 11721
pwd = 'REDACTED'

LOCAL = r"E:\code\deepseek的桌宠\animagine_model\models\ModelE--Animagine-XL\snapshots\master\animagineXL40_v40.safetensors"
REMOTE = "/root/autodl-tmp/models/animagineXL40_v40.safetensors"
THREADS = 4
CHUNK = 4 * 1024 * 1024  # 4MB per read

total = os.path.getsize(LOCAL)

# === 检查远程已有大小 ===
c0 = paramiko.SSHClient()
c0.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c0.connect(host, port=port, username='root', password=pwd, timeout=30)
s0 = c0.open_sftp()
try:
    remote_size = s0.stat(REMOTE).st_size
except FileNotFoundError:
    remote_size = 0
s0.close(); c0.close()

print(f"远程已有: {remote_size:,} ({remote_size/total*100:.1f}%)", flush=True)
if remote_size >= total:
    print("已完成!", flush=True)
    sys.exit(0)

remaining = total - remote_size
chunk_size = remaining // THREADS
# 让每个线程均匀分配（最后一个线程收尾）
ranges = []
for i in range(THREADS):
    start = remote_size + i * chunk_size
    end = remote_size + (i + 1) * chunk_size if i < THREADS - 1 else total
    ranges.append((i, start, end))
    print(f"  线程 {i}: {start:,} → {end:,} ({end-start:,} 字节)", flush=True)

print(f"\n{THREADS} 路并行上传中...", flush=True)

# === 线程状态 ===
progress = [0] * THREADS
lock = threading.Lock()
t0 = time.time()
errors = []

def upload_chunk(tid: int, start: int, end: int):
    global errors
    tmp = f"{REMOTE}.part{tid}"
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(host, port=port, username='root', password=pwd, timeout=30)
        sftp = c.open_sftp()

        # 上传分块到临时文件
        with open(LOCAL, 'rb') as lf:
            lf.seek(start)
            rf = sftp.open(tmp, 'wb')
            to_send = end - start
            sent = 0
            while sent < to_send:
                data = lf.read(min(CHUNK, to_send - sent))
                if not data:
                    break
                rf.write(data)
                sent += len(data)
                with lock:
                    progress[tid] = sent
            rf.close()
        sftp.close(); c.close()
        with lock:
            progress[tid] = to_send  # 标记完成
    except Exception as e:
        with lock:
            errors.append(f"线程 {tid}: {e}")

# === 启动线程 ===
threads = []
for tid, start, end in ranges:
    t = threading.Thread(target=upload_chunk, args=(tid, start, end), daemon=True)
    threads.append(t)
    t.start()

# === 监控进度 ===
last_report = 0
while any(t.is_alive() for t in threads):
    time.sleep(5)
    now = time.time()
    if now - last_report < 30:
        continue
    last_report = now
    with lock:
        done = sum(progress)
    pct = (remote_size + done) / total * 100
    elapsed = now - t0
    speed = done / elapsed / 1024**2 if elapsed > 0 else 0
    eta = (remaining - done) / (speed * 1024**2) if speed > 0 else 0
    print(f"  {pct:.1f}%  ({speed:.1f} MB/s)  ETA {eta/60:.0f}min", flush=True)

for t in threads:
    t.join()

elapsed = time.time() - t0
with lock:
    done = sum(progress)
speed = done / elapsed / 1024**2 if elapsed > 0 else 0
print(f"上传完成! {done:,} 字节  {speed:.1f} MB/s", flush=True)

if errors:
    print(f"错误: {errors}", flush=True)
    sys.exit(1)

# === 合并分块到主文件 ===
print("\n合并分块...", flush=True)
c2 = paramiko.SSHClient()
c2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c2.connect(host, port=port, username='root', password=pwd, timeout=30)
# 逐个追加分块
for i in range(THREADS):
    tmp = f"{REMOTE}.part{i}"
    cmd = f"cat {tmp} >> {REMOTE} && rm {tmp}"
    print(f"  合并 part{i}...", flush=True)
    _, out, err = c2.exec_command(cmd, timeout=120)
    err_text = err.read().decode().strip()
    if err_text:
        print(f"  错误: {err_text}", flush=True)

# 验证
_, out, _ = c2.exec_command(f"stat --format=%s {REMOTE}")
final_size = int(out.read().decode().strip())
c2.close()

print(f"\n最终文件: {final_size:,} / {total:,} ({final_size/total*100:.1f}%)", flush=True)
if final_size == total:
    print("DONE=1 完整性验证通过!", flush=True)
else:
    print(f"警告: 大小不匹配! 差 {total - final_size} 字节", flush=True)
    sys.exit(1)
