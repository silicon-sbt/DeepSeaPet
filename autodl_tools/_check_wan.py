"""探测 ModelScope 上 Wan2.1 I2V 仓库文件结构 — 判断能否直接用 diffusers WanPipeline 加载"""
import sys, json, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

def list_files(repo):
    url = f"https://modelscope.cn/api/v1/models/{repo}/repo/files?Revision=master&Recursive=true"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read().decode())
        files = data.get('Data', {}).get('Files', [])
        total = sum(f.get('Size', 0) or 0 for f in files)
        nbig = sum(1 for f in files if (f.get('Size', 0) or 0) > 10**8)
        print(f"\n=== {repo} ===")
        print(f"  文件数: {len(files)}  总大小: {total/1024**3:.1f} GB  大文件(>100MB): {nbig} 个")
        # 打印目录结构(前若干层) + 大文件
        seen_dirs = set()
        for f in sorted(files, key=lambda x: -(x.get('Size', 0) or 0)):
            p = f['Path']; sz = f.get('Size', 0) or 0
            if sz > 10**7:
                print(f"  [大] {p}  {sz/1024**3:.2f} GB")
            else:
                top = '/'.join(p.split('/')[:2])
                if top not in seen_dirs:
                    seen_dirs.add(top)
                    print(f"       {top}/ ...")
    except Exception as e:
        print(f"\n=== {repo} 失败: {type(e).__name__}: {str(e)[:150]} ===")

for repo in [
    'Wan-AI/Wan2.1-VAE',                                                     # 官方独立 VAE
    'Wan-AI/Wan2.1-T2V-14B-Diffusers',                                        # 官方 90GB BF16
]:
    list_files(repo)
