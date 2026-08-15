"""即梦 (Seedance 2.0) I2V 生成桌宠行走循环视频

AutoDL art 端点, 火山方舟格式 (异步任务)。
依据官方文档: POST 创建任务 -> 轮询 GET tasks/{id} -> succeeded 拿 video_url。

用法:
    python imeng_walk.py                    # 默认锚点 idle_00.png, 下载视频到 _walk_gen/walk_raw.mp4
    python imeng_walk.py --anchor xxx.png --prompt "..."
    python imeng_walk.py --dry-run          # 只打印请求体, 不创建任务
"""
import argparse
import base64
import io
import json
import os
import sys
import time
from pathlib import Path

import requests
from PIL import Image

API_KEY = os.environ.get("IMENG_KEY")
if not API_KEY:
    raise SystemExit("未设置 IMENG_KEY 环境变量(在 C:\\Users\\A\\.claude\\CLAUDE.md 全局指令里, 勿写进本仓库)")
BASE = "https://www.autodl.art/api/v1/ark/v3/contents/generations/tasks"
MODEL = "doubao-seedance-2-0-260128"
DEFAULT_ANCHOR = Path(__file__).resolve().parents[1] / "module_5_assets" / "sprites" / "idle_00.png"
OUT_DIR = Path(__file__).resolve().parents[1] / "_walk_gen"

PROMPT = (
    "2D 横版卷轴游戏风格, 手绘动漫插画, 扁平 2D 画面, 非 3D, 非渲染模型。"
    "一名 Q 版少女角色, 蓝紫色渐变长发, 头戴鲸鱼尾巴发饰, 身着深蓝女仆装。"
    "角色侧身面向右方, 正在原地自然散步: 小步幅左右脚交替迈步, 脚步放低贴地, "
    "膝盖微弯, 双臂随步伐小幅自然摆动, 身体保持直立, 动作幅度小, 节奏平缓均匀, "
    "像日常走路一样轻松自然。"
    "注意: 这是走路不是跳舞, 不要抬腿过高, 不要甩动四肢, 不要夸张动作, "
    "不要跳跃, 不要旋转, 不要扭动身体。"
    "整个行走过程中角色必须始终完整地保持在画面正中央, 不可以移动出画面, "
    "不可以上下跳动, 不可以改变大小和位置, 缩放比例保持恒定。"
    "画面简单, 纯色白底背景, 无场景, 无文字。"
)


def prep_anchor(path: Path, size: int = 1024, bg=(255, 255, 255), target_h: int = 700) -> Image.Image:
    """透明锚点 -> 白底 + 角色缩放到固定高度居中, 留出边距 (视频方法: 角色保持画面内)"""
    img = Image.open(path).convert("RGBA")
    w, h = img.size
    px = img.load()
    xs, ys = [], []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            if px[x, y][3] > 128:
                xs.append(x)
                ys.append(y)
    if not xs:
        raise SystemExit(f"{path} 里没找到不透明像素")
    crop = img.crop((min(xs), min(ys), max(xs) + 1, max(ys) + 1))
    # 按目标高度等比缩放
    ch, cw = crop.size
    scale = target_h / ch
    crop = crop.resize((max(1, round(cw * scale)), target_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (size, size), (*bg, 255))
    cx = (size - crop.width) // 2
    cy = (size - crop.height) // 2
    canvas.alpha_composite(crop, (cx, cy))
    return canvas.convert("RGB")


def b64_data_uri(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def http_json(url: str, data: dict | None = None, timeout: int = 90):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    try:
        if data is not None:
            r = requests.post(url, headers=headers, json=data, timeout=timeout)
        else:
            r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:600]}")
        return r.json()
    except requests.RequestException as e:
        raise RuntimeError(f"请求失败: {e}") from e


def create_task(img_uri: str, prompt: str) -> dict:
    # 官方文档格式: content 数组 = [{"type":"text",...}, {"type":"image_url",...,"role":"first_frame"}]
    payload = {
        "model": MODEL,
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": img_uri}, "role": "first_frame"},
        ],
        "resolution": "720p",
        "ratio": "1:1",
        "duration": 5,
        "watermark": False,
        "generate_audio": False,
        "return_last_frame": False,
    }
    return http_json(BASE, payload)


def poll_task(task_id: str, interval: int = 15, timeout: int = 360) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = http_json(f"{BASE}/{task_id}", timeout=30)
        st = resp.get("status")
        print(f"  [{st}] {resp.get('id')}", flush=True)
        if st == "succeeded":
            url = resp.get("content", {}).get("video_url")
            if not url:
                raise SystemExit(f"succeeded 但无 video_url: {json.dumps(resp, ensure_ascii=False)[:400]}")
            return url
        if st in ("failed", "cancelled", "expired"):
            raise SystemExit(f"任务 {st}: {json.dumps(resp, ensure_ascii=False)[:400]}")
        time.sleep(interval)
    raise SystemExit("轮询超时")


def download(url: str, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    # 防覆盖：目标已存在时先备份（带时间戳），绝不直接覆盖旧素材
    if out.exists():
        bak = out.with_name(f"{out.stem}_prev_{time.strftime('%Y%m%d_%H%M%S')}{out.suffix}")
        out.rename(bak)
        print(f"旧文件已备份 -> {bak}", flush=True)
    with requests.get(url, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=120) as r:
        r.raise_for_status()
        out.write_bytes(r.content)
    print(f"已下载: {out} ({out.stat().st_size/1e6:.1f} MB)", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", default=str(DEFAULT_ANCHOR))
    ap.add_argument("--prompt", default=PROMPT)
    ap.add_argument("--out", default=str(OUT_DIR / "walk_raw.mp4"))
    ap.add_argument("--dry-run", action="store_true", help="只打印请求体")
    args = ap.parse_args()

    img = prep_anchor(Path(args.anchor))
    uri = b64_data_uri(img)
    print(f"[1/4] 锚点已预处理: {Path(args.anchor).name} -> {img.size} ({len(uri)//1024} KB b64)", flush=True)

    if args.dry_run:
        payload = {
            "model": MODEL,
            "content": [
                {"type": "text", "text": args.prompt},
                {"type": "image_url", "image_url": {"url": f"<data uri {len(uri)//1024}KB>"}, "role": "first_frame"},
            ],
            "resolution": "720p", "ratio": "1:1", "duration": 5,
            "watermark": False, "generate_audio": False,
        }
        print("[dry-run] 请求体:", json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"[2/4] 创建任务 model={MODEL} duration=5s", flush=True)
    resp = create_task(uri, args.prompt)
    task_id = resp.get("id")
    if not task_id:
        raise SystemExit(f"创建失败: {json.dumps(resp, ensure_ascii=False)[:400]}")
    print(f"  task_id={task_id}", flush=True)

    print("[3/4] 轮询 (约 2-3 分钟)...", flush=True)
    video_url = poll_task(task_id)

    print("[4/4] 下载视频", flush=True)
    download(video_url, Path(args.out))


if __name__ == "__main__":
    sys.exit(main())
