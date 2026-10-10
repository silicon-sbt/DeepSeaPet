"""下载官方 Wan2.1-VAE（diffusers 0.39 兼容格式）到 ms_cache/wan_vae_ms"""
import os, urllib.request, concurrent.futures

BASE = 'https://modelscope.cn/models/Wan-AI/Wan2.1-T2V-14B-Diffusers/resolve/master/vae/'
DEST = '/root/autodl-tmp/ms_cache/wan_vae_ms'
os.makedirs(DEST, exist_ok=True)
FILES = ['config.json', 'diffusion_pytorch_model.safetensors']


def head_size(url):
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
                    data = r.read(2 * 1024 * 1024)
                    if not data:
                        break
                    while data:
                        n = os.pwrite(fd, data, pos)
                        data = data[n:]
                        pos += n
            finally:
                os.close(fd)
        return True
    except Exception as e:
        print(f'  分块失败 {start}: {str(e)[:60]}', flush=True)
        return False


for name in FILES:
    url = BASE + name
    path = os.path.join(DEST, name)
    done = path + '.done'
    total = head_size(url)
    if os.path.exists(done) and os.path.getsize(path) >= total:
        print(f'{name}: 已完整', flush=True)
        continue
    if total < 1024 * 1024:  # 小文件单请求直下
        with urllib.request.urlopen(url, timeout=60) as r, open(path, 'wb') as f:
            while True:
                d = r.read(1024 * 1024)
                if not d:
                    break
                f.write(d)
        open(done, 'w').close()
        print(f'{name}: 完成 ({total/1e6:.2f}MB)', flush=True)
        continue
    NCHUNK = 16
    chunk = total // NCHUNK
    with open(path, 'wb') as f:
        f.truncate(total)
    ranges = [(i * chunk, (i + 1) * chunk - 1 if i < NCHUNK - 1 else total - 1) for i in range(NCHUNK)]
    with concurrent.futures.ThreadPoolExecutor(NCHUNK) as ex:
        ok = list(ex.map(lambda r: dl_chunk(url, path, r[0], r[1]), ranges))
    if all(ok):
        open(done, 'w').close()
        print(f'{name}: 完成 ({total/1e6:.2f}MB)', flush=True)
    else:
        print(f'{name}: 失败 {ok.count(False)}/{NCHUNK}', flush=True)

print('VAE_DL_DONE', flush=True)
