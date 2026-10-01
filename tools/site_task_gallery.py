"""生成 SOP 页面“任务一览”页（pg-tasks）的 HTML 片段（Mac 上跑，只用标准库，只读已落盘的结果）。

输入：results/site/task_table.txt（stages/evaluate/site_task_table.py：ep、序列名、帧数、支撑面、官方英文任务原文）；
results/batch1/error_table_with_mf4090_b.txt（27 条逐帧满配最终 checkpoint 的判定与 MP-SR）；results/day2/batch_verdict_*.txt
（summary_json，用来标出每条判定来自哪一批）；--media-dir 下的素材（exo_epNN / ref_epNN 的 .mp4 .jpg .json）。
每条一张卡：ep 与英文序列名、帧数、支撑面、判定与 MP-SR（标明 Tier 1、逐帧满配、最终 checkpoint、本地 4096 世界与来源文件）、
官方任务原文（照抄、HTML 转义）、两段视频（人类示范 exo、G1 运动学参考）。视频用 data-src，页面脚本进入视口时再取回播放。
计划 agent-doc/plan-site-media-2026-09-30.md（第 2 版）。
用法：python3 tools/site_task_gallery.py --media-dir runs/site_media --out <片段.html>
"""
import argparse
import glob
import html
import json
import re
from pathlib import Path

SOURCE = {"ml40_batch1a": ("第 1 批 A 段", "batch 1 segment A"), "mf4090_batch1a": ("第 1 批 A 段", "batch 1 segment A"),
          "ml40_batch1b": ("第 1 批 B 段", "batch 1 segment B"), "mf4090_batch1b": ("第 1 批 B 段", "batch 1 segment B"),
          "ml40_day2": ("Day 2", "Day 2"), "ml40_day2b": ("Day 2b", "Day 2b"), "mf4090_day2": ("Day 2", "Day 2"),
          "mf4090_night1": ("night1", "night1")}


def task_table(path: Path) -> list:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        f = line.split("\t")
        if len(f) == 7 and f[0].isdigit():
            rows.append({"ep": int(f[0]), "seq": f[1], "short": f[2], "object": f[3], "frames": int(f[4]), "support": f[5], "task": f[6]})
    return rows


def error_table(path: Path) -> dict:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        f = [x.strip() for x in line.split(" | ")]
        m = re.fullmatch(r"ep(\d+)", f[0]) if f else None
        if m and len(f) > 4:
            out[int(m.group(1))] = {"verdict": f[2], "mp": f[4], "sp": f[5]}
    return out


def verdict_sources() -> dict:
    """ep → [(来源键, maniptrans_sr)]，只取逐帧、有判定的 summary_json。"""
    out = {}
    for p in sorted(glob.glob("results/day2/batch_verdict_*.txt")):
        key = Path(p).stem.replace("batch_verdict_", "")
        for line in open(p, encoding="utf-8"):
            if "summary_json " not in line:
                continue
            j = json.loads(line.split("summary_json ", 1)[1])
            m = re.search(r"-ep(\d+)-", j.get("run", ""))
            if m and j.get("playback") == "frame" and j.get("verdict") in ("PASS", "FAIL"):
                out.setdefault(int(m.group(1)), []).append((key, j.get("maniptrans_sr")))
    return out


def support_label(s: str) -> tuple:
    if s == "none":
        return "无支撑面（只有地面，训练加 scene.support=false）", "no support surface (floor only; trained with scene.support=false)"
    if s.startswith("Cube"):
        return f"{s}（v0.4.0 与 aee95f2 会建成 1 m 立方体，动画用 #185 几何）", f"{s} (v0.4.0 and aee95f2 build a 1 m cube; the animation uses the #185 geometry)"
    return s, s


def media(md: Path, name: str):
    mp4, jpg = md / f"{name}.mp4", md / f"{name}.jpg"
    return (mp4.exists() and jpg.exists()), (json.loads((md / f"{name}.json").read_text()) if (md / f"{name}.json").exists() else None)


def video(name: str, zh: str, en: str) -> str:
    return (f'<figure class="vid"><video data-src="media/{name}.mp4" poster="media/{name}.jpg" muted loop playsinline controls preload="none" '
            f'width="480" height="360"></video><figcaption><span class="l-zh">{zh}</span><span class="l-en">{en}</span></figcaption></figure>')


def card(r: dict, et: dict, vs: dict, md: Path) -> str:
    ep = r["ep"]
    sup_zh, sup_en = support_label(r["support"])
    if ep in et:
        e = et[ep]
        src = [k for k, mp in vs.get(ep, []) if mp is not None and abs(float(mp) - float(e["mp"])) < 6e-4] or [k for k, _ in vs.get(ep, [])]
        szh, sen = SOURCE.get(src[0], (src[0], src[0])) if src else ("?", "?")
        vzh = "通过" if e["verdict"] == "通过" else "不通过"
        ven = "pass" if e["verdict"] == "通过" else "fail"
        sep = " " if szh[-1:].isascii() else ""
        res = (f'<span class="l-zh">{szh}{sep}判定：<b>{vzh}</b>，MP-SR {e["mp"]}，SP-SR {e["sp"]}</span>'
               f'<span class="l-en">{sen} verdict: <b>{ven}</b>, MP-SR {e["mp"]}, SP-SR {e["sp"]}</span>')
    else:
        res = '<span class="l-zh">无效，未评（方盒支撑面，见发散排查）</span><span class="l-en">Invalid, not evaluated (box support; see the divergence page)</span>'
    ok_exo, _ = media(md, f"exo_ep{ep:02d}")
    ok_ref, rj = media(md, f"ref_ep{ep:02d}")
    vids = []
    vids.append(video(f"exo_ep{ep:02d}", "人类示范（exo 相机，2 倍速）", "Human demo (exo camera, 2× speed)") if ok_exo
                else '<p class="muted"><span class="l-zh">exo 片段缺失</span><span class="l-en">exo clip missing</span></p>')
    note_zh = note_en = ""
    if rj and (rj.get("first_nonfinite_frame") is not None or rj.get("frames_rendered") != rj.get("reference_frames")):
        note_zh = f"（渲染异常：{html.escape(json.dumps(rj))}）"
        note_en = f" (render issue: {html.escape(json.dumps(rj))})"
    vids.append(video(f"ref_ep{ep:02d}", f"G1 参考（运动学回放，2 倍速）{note_zh}", f"G1 reference (kinematic playback, 2× speed){note_en}") if ok_ref
                else '<p class="muted"><span class="l-zh">参考动画缺失</span><span class="l-en">reference animation missing</span></p>')
    return (f'<article class="task" id="task-ep{ep}"><h3><span class="mono">ep{ep}</span> · <code>{html.escape(r["short"])}</code></h3>'
            f'<p class="meta"><span class="l-zh">{r["frames"]} 帧（30 fps）· {sup_zh}</span><span class="l-en">{r["frames"]} frames (30 fps) · {sup_en}</span><br>{res}</p>'
            f'<blockquote class="taskq" lang="en">{html.escape(r["task"])}</blockquote>'
            f'<div class="vids">{"".join(vids)}</div></article>')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--media-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    rows = task_table(Path("results/site/task_table.txt"))
    et = error_table(Path("results/batch1/error_table_with_mf4090_b.txt"))
    vs = verdict_sources()
    cards = "\n".join(card(r, et, vs, a.media_dir) for r in rows)
    a.out.write_text(f'<div class="taskgrid">\n{cards}\n</div>\n', encoding="utf-8")
    print(f"{len(rows)} 张卡，写到 {a.out}；有判定的 {sum(1 for r in rows if r['ep'] in et)} 条")


if __name__ == "__main__":
    main()
