"""多线程 Range 分块下载 distill_fp8 到 ms_cache（带分块完成位 + .done 完整性标记）
先杀掉慢速 modelscope 进程，16 线程/文件并发；每分块全部成功才写 .done，否则视为失败可重下"""
import os, sys, urllib.request, concurrent.futures

sys.stdout.reconfigure(encoding='utf-8')
os.system("pkill -f 'modelscope download' 2>/dev/null")
print('已停止 modelscope 进程', flush=True)

BASE = 'https://modelscope.cn/models/lightx2v/Wan2.1-I2V-14B-480P-StepDistill-CfgDistill-Lightx2v/resolve/master/distill_fp8/'
DEST = '/root/autodl-tmp/ms_cache/distill_fp8'
os.makedirs(DEST, exist_ok=True)

FILES = [
    'models_t5_umt5-xxl-enc-fp8.pth',
    'non_block.safetensors',
    'clip-fp8.pth',
    'Wan2.1_VAE.pth',
    'taew2_1.pth',
    'config.json',
    'diffusion_pytorch_model.safetensors.index.json',
]

def head_size(url):
    # 用 GET Range: bytes=0-0，从 Content-Range 头取总大小
    req = urllib.request.Request(url, headers={'Range': 'bytes=0-0'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return int(r.headers.get('Content-Range', '').split('/')[-1])

def dl_chunk(url, path, start, end):
    """下载 [start,end] 区间；os.pwrite 写不重叠偏移，线程安全免锁，返回是否成功"""
    req = urllib.request.Request(url, headers={'Range': f'bytes={start}-{end}'})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            fd = os.open(path, os.O_RDWR)
            try:
                pos = start
                while True:
                    data = r.read(2 * 1024 * 1024)  # 每次 2MB 流式读，避免 OOM
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

def download_file(name):
    url = BASE + name
    path = os.path.join(DEST, name)
    done_flag = path + '.done'
    try:
        total = head_size(url)
    except Exception as e:
        print(f'{name}: HEAD 失败 {str(e)[:60]}', flush=True)
        return
    if os.path.exists(done_flag) and os.path.getsize(path) >= total:
        print(f'{name}: 已完整下载跳过', flush=True)
        return
    # 小文件（<1MB）单请求直下：modelscope CDN 对并发 Range 小请求会返回 404
    if total < 1024 * 1024:
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(path, 'wb') as f:
                while True:
                    data = r.read(1024 * 1024)
                    if not data:
                        break
                    f.write(data)
            open(done_flag, 'w').close()
            print(f'{name}: 完成 ({total/1e9:.2f}GB)', flush=True)
        except Exception as e:
            print(f'{name}: 下载失败 {str(e)[:80]}', flush=True)
        return
    NCHUNK = 16
    chunk = total // NCHUNK
    with open(path, 'wb') as f:
        f.truncate(total)
    ranges = [(i * chunk, (i + 1) * chunk - 1 if i < NCHUNK - 1 else total - 1) for i in range(NCHUNK)]
    with concurrent.futures.ThreadPoolExecutor(NCHUNK) as ex:
        ok = list(ex.map(lambda r: dl_chunk(url, path, r[0], r[1]), ranges))
    if all(ok):
        open(done_flag, 'w').close()
        print(f'{name}: 完成 ({total/1e9:.2f}GB)', flush=True)
    else:
        print(f'{name}: 下载失败（{ok.count(False)}/16 分块未完成）', flush=True)

for name in FILES:
    try:
        download_file(name)
    except Exception as e:
        print(f'{name}: 失败 {str(e)[:80]}', flush=True)

print('ALL_DONE', flush=True)
