"""多线程 Range 分块下载 IP-Adapter image_encoder/model.safetensors（ModelScope 源）。

无卡模式可跑：流式写盘，内存占用 ~几十 MB。先删污染旧文件，
16 线程分块下载，完成验证 safetensors 文件头（前 8 字节 = header 长度）。
"""
import os, urllib.request, concurrent.futures

URL = "https://modelscope.cn/models/AI-ModelScope/IP-Adapter/resolve/master/models/image_encoder/model.safetensors"
DEST = "/root/autodl-tmp/ip_adapter/sdxl_models/image_encoder/model.safetensors"
NCHUNK = 16

def head_size(url):
    # GET Range: bytes=0-0，从 Content-Range 头取总大小
    req = urllib.request.Request(url, headers={'Range': 'bytes=0-0'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return int(r.headers.get('Content-Range', '').split('/')[-1])

def dl_chunk(url, path, start, end):
    req = urllib.request.Request(url, headers={'Range': f'bytes={start}-{end}'})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            fd = os.open(path, os.O_RDWR)
            try:
                pos = start
                while True:
                    data = r.read(2 * 1024 * 1024)  # 每块 2MB 流式，避免 OOM
                    if not data:
                        break
                    while data:  # pwrite 可能只写部分，循环补全
                        n = os.pwrite(fd, data, pos)
                        data = data[n:]
                        pos += n
            finally:
                os.close(fd)
        return True
    except Exception as e:
        print(f'  分块失败 {start}: {str(e)[:60]}', flush=True)
        return False

# 删污染旧文件（curl -C 续传残留 "Entry not found" 头，见 memory 经验 6）
if os.path.exists(DEST):
    os.remove(DEST)
    print('已删污染旧文件', flush=True)

total = head_size(URL)
print(f'目标大小 {total} 字节 ({total/1e9:.2f}GB)', flush=True)

with open(DEST, 'wb') as f:
    f.truncate(total)

chunk = total // NCHUNK
ranges = [(i * chunk, (i + 1) * chunk - 1 if i < NCHUNK - 1 else total - 1) for i in range(NCHUNK)]
with concurrent.futures.ThreadPoolExecutor(NCHUNK) as ex:
    ok = list(ex.map(lambda r: dl_chunk(URL, DEST, r[0], r[1]), ranges))

if all(ok):
    with open(DEST, 'rb') as f:
        head = f.read(8)
    hlen = int.from_bytes(head, 'little')
    assert 0 < hlen < 10_000_000, f'文件头异常 {head.hex()}'
    print(f'下载完成，文件头验证通过（safetensors header 长度 {hlen}）', flush=True)
else:
    print(f'下载失败（{ok.count(False)}/{NCHUNK} 分块未完成）', flush=True)
