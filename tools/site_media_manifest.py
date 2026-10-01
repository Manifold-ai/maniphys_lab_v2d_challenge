"""SOP 页面视频素材的清单（Mac 上跑，只用标准库）：每个文件的字节数与 md5，参考动画附渲染时的逐帧检查结果，最后按判据给出结论。

素材本身不进 git（数据集派生，见 CLAUDE.md“数据与产物”），清单进 results/ 作溯源。判据出自计划 agent-doc/plan-site-media-2026-09-30.md 第 2 版：
30 条都有 exo 片段、参考动画与两张封面；exo 单个 ≤ 3 MB、参考动画单个 ≤ 1.5 MB、总量 ≤ 60 MB；参考动画全部帧有限且渲染帧数 = 参考帧数。
用法：python3 tools/site_media_manifest.py runs/site_media
  落盘：scripts/dev/record site/media_manifest python3 tools/site_media_manifest.py runs/site_media
"""
import hashlib
import json
import sys
from pathlib import Path


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def main() -> int:
    d = Path(sys.argv[1])
    files = sorted(p for p in d.iterdir() if p.suffix in (".mp4", ".jpg") and not p.name.startswith("."))
    total = 0
    print("文件 | 字节 | md5 | 渲染检查")
    for p in files:
        size = p.stat().st_size
        total += size
        j = p.with_suffix(".json")
        info = json.loads(j.read_text()) if p.suffix == ".mp4" and j.exists() else ""
        print(f"{p.name} | {size} | {md5(p)} | {json.dumps(info, ensure_ascii=False) if info else ''}")
    problems = []
    for n in range(30):
        for kind in ("exo", "ref"):
            for ext in (".mp4", ".jpg"):
                if not (d / f"{kind}_ep{n:02d}{ext}").is_file():
                    problems.append(f"缺 {kind}_ep{n:02d}{ext}")
        exo, ref = d / f"exo_ep{n:02d}.mp4", d / f"ref_ep{n:02d}.mp4"
        if exo.is_file() and exo.stat().st_size > 3_000_000:
            problems.append(f"{exo.name} 超过 3 MB")
        if ref.is_file() and ref.stat().st_size > 1_500_000:
            problems.append(f"{ref.name} 超过 1.5 MB")
    for j in sorted(d.glob("ref_ep*.json")):
        info = json.loads(j.read_text())
        if info.get("first_nonfinite_frame") is not None or info.get("frames_rendered") != info.get("reference_frames"):
            problems.append(f"{j.stem}：渲染检查不过 {info}")
    if total > 60_000_000:
        problems.append(f"总量 {total} B 超过 60 MB")
    print(f"共 {len(files)} 个文件，{total / 1e6:.2f} MB")
    for p in problems:
        print("问题：" + p)
    print("MEDIA_OK" if not problems else f"MEDIA_PROBLEMS {len(problems)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
