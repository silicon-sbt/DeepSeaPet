"""本地即梦 Seedream img2img 生成 walk 迈步左右腿两帧。
参考图 = base_refs/walk_00.png（豆包生成的迈步基准图），零 torch，仅 urllib。

用法：python autodl_tools/_gen_walk_jimeng.py
key：从环境变量 VOLCENGINE_API_KEY 或 api火山 文件读取（取 ark- 开头的行）。
"""
import base64, json, os, sys, time, urllib.request, urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# ── key ──
key = os.environ.get("VOLCENGINE_API_KEY", "").strip()
if not key:
    for f in (ROOT / "api火山", HERE / "api火山"):
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("ark-"):
                    key = line.strip()
                    break
if not key.startswith("ark-"):
    sys.exit("找不到 VOLCENGINE_API_KEY（ark- 开头）")

URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"

REF = ROOT / "autodl_tools" / "base_refs" / "walk_00.png"
OUT = ROOT / "autodl_tools" / "sprites_walk_jimeng"
OUT.mkdir(parents=True, exist_ok=True)

BASE = ("蓝发、头顶双触角、女仆装、鲸鱼尾巴的 Q 版鲸鱼娘，全身，纯白背景，单角色，"
        "3D 渲染风格，与参考图完全相同的角色、服装、配色、角度")
# 左右腿两帧
PROMPTS = {
    "walk_00": BASE + "，正在走路，左腿在前迈步，右腿在后蹬地，手臂自然摆动，侧视图，全身",
    "walk_01": BASE + "，正在走路，右腿在前迈步，左腿在后蹬地，手臂自然摆动，侧视图，全身",
}

with open(REF, "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

for name, prompt in PROMPTS.items():
    body = {
        "model": "doubao-seedream-4-0-250828",
        "prompt": prompt,
        "image": f"data:image/png;base64,{b64}",
        "size": "1k",
        "response_format": "url",   # 默认 url；seedream 支持 url/b64
    }
    req = urllib.request.Request(URL, json.dumps(body).encode(), {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    })
    print(f"[{name}] 提交 ...", flush=True)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.loads(r.read())
        print(f"[{name}] HTTP ok, {time.time()-t0:.1f}s", flush=True)
        # 保存图片
        data = resp.get("data") or resp.get("images") or []
        img = data[0] if data else None
        if img:
            b64str = img.get("b64_json") or ""
            if b64str:
                raw = base64.b64decode(b64str)
            else:
                raw = None
                print(f"[{name}] 响应字段: {list(img.keys())}", flush=True)
            if raw:
                p = OUT / f"{name}.png"
                p.write_bytes(raw)
                print(f"[{name}] 已保存 {p} ({len(raw)//1024}KB)", flush=True)
        else:
            print(f"[{name}] 响应无图片: {json.dumps(resp)[:800]}", flush=True)
    except urllib.error.HTTPError as e:
        print(f"[{name}] HTTP {e.code}: {e.read().decode()[:800]}", flush=True)
    except Exception as e:
        print(f"[{name}] 异常: {e}", flush=True)
