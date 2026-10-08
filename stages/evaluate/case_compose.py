"""把 case_clip.py render 渲出的左右两栏拼成成片并取封面（容器里执行，用 imageio_ffmpeg 自带的 ffmpeg）。计划 agent-doc/plan-site-cases-video-2026-10-08.md 第 3 节。

成片：左右拼接（1280×480）、实时速度（30 fps）、H.264 CRF 28、yuv420p、faststart、去元数据、无音轨。
封面：摔倒取骨盆超阈值那一帧，其余取中间帧（帧号来自 record.npz 里这一类的 stats）。
用法：python case_compose.py <record.npz> <类别> <left.mp4> <right.mp4> <输出前缀>（右栏可能比左栏长：截到左栏的帧数）
"""

import json
import subprocess
import sys

import imageio_ffmpeg
import numpy as np


def main():
    npz, kind, left, right, out = sys.argv[1:6]
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    z = np.load(npz, allow_pickle=False)
    stats = z[f"{kind}_stats"]
    frames = int(z[f"{kind}_frames"].shape[0])  # 左栏帧数（骨盆跳变时已截断）
    key = min(int(stats[4]), frames - 1) if kind == "fall" and stats[4] >= 0 else frames // 2
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", left, "-i", right,
                    "-filter_complex", "hstack=inputs=2:shortest=1", "-frames:v", str(frames), "-c:v", "libx264", "-crf", "28", "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-map_metadata", "-1", "-an", f"{out}.mp4"], check=True)
    subprocess.run([ff, "-y", "-loglevel", "error", "-ss", f"{key / 30.0:.3f}", "-i", f"{out}.mp4",
                    "-frames:v", "1", "-q:v", "4", f"{out}.jpg"], check=True)
    print(json.dumps({"out": f"{out}.mp4", "poster_frame": key, "frames": frames}))


if __name__ == "__main__":
    main()
