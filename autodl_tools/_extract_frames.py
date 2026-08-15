"""从即梦生成的行走视频抽帧，供步态周期自审和 8 关键帧挑选

用法:
    python autodl_tools/_extract_frames.py                    # 默认抽 _walk_gen/walk_raw.mp4 -> _walk_gen/frames/ (10fps)
    python autodl_tools/_extract_frames.py --video xxx.mp4 --fps 5 --outdir out/
    python autodl_tools/_extract_frames.py --times 0.5,1.0,1.5   # 按秒精确抽帧（选好 8 帧后精抽）

抽帧用 imageio-ffmpeg 自带的 ffmpeg 二进制（零额外依赖）。
"""
import argparse
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

REPO = Path(__file__).resolve().parents[1]
DEFAULT_VIDEO = REPO / "_walk_gen" / "walk_raw.mp4"
DEFAULT_OUT = REPO / "_walk_gen" / "frames"


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def extract_fps(video: Path, outdir: Path, fps: float):
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_exe(), "-y", "-i", str(video),
        "-vf", f"fps={fps}",
        "-q:v", "2",
        str(outdir / "frame_%03d.png"),
    ]
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
    files = sorted(outdir.glob("frame_*.png"))
    print(f"已抽 {len(files)} 帧 -> {outdir}", flush=True)


def extract_times(video: Path, outdir: Path, times: list[float]):
    outdir.mkdir(parents=True, exist_ok=True)
    for i, t in enumerate(times):
        out = outdir / f"key_{i:02d}_t{t:.2f}s.png"
        cmd = [
            ffmpeg_exe(), "-y", "-ss", f"{t:.3f}", "-i", str(video),
            "-frames:v", "1", "-q:v", "2", str(out),
        ]
        subprocess.run(cmd, check=True)
        print(f"t={t:.2f}s -> {out.name}", flush=True)
    print(f"精抽 {len(times)} 帧 -> {outdir}", flush=True)


def main():
    ap = argparse.ArgumentParser(description="从行走视频抽帧")
    ap.add_argument("--video", default=str(DEFAULT_VIDEO))
    ap.add_argument("--outdir", default=str(DEFAULT_OUT))
    ap.add_argument("--fps", type=float, default=10.0, help="按帧率抽帧")
    ap.add_argument("--times", default=None, help="按秒精确抽帧，逗号分隔，如 0.5,1.0,1.5")
    args = ap.parse_args()

    video = Path(args.video)
    if not video.exists():
        sys.exit(f"视频不存在: {video}")
    outdir = Path(args.outdir)

    if args.times:
        times = [float(x) for x in args.times.split(",")]
        extract_times(video, outdir, times)
    else:
        extract_fps(video, outdir, args.fps)


if __name__ == "__main__":
    sys.exit(main())
