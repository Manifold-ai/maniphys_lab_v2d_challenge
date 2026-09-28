"""diag_rotation.py 的合成数据测试（只用 numpy；暂无契约 ID：诊断工具不在交付链上）。

参考绕竖直轴在第 209–420 帧匀速转 300°；8 个世界：0–3 跟到参考的 60%，4–5 只转 40°，6–7 不转但每帧 ±0.5° 来回抖动
（增量绝对值之和约 105°，带符号净转动为 0）。随机翻转四元数正负号。6、7 两个世界在第 300 帧后 palm 误差越线。
检查：净转动、主轴方向、三类解读、逐世界成功率、有效性通过与拦截、SVG 可解析。
用法：python stages/evaluate/test_diag_rotation.py
"""
import json
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
T, W, S0, S1 = 553, 8, 209, 420


def yaw_quat(theta_deg: np.ndarray) -> np.ndarray:
    h = np.radians(theta_deg) / 2
    return np.stack([np.zeros_like(h), np.zeros_like(h), np.sin(h), np.cos(h)], -1)  # xyzw


def ramp(total: float) -> np.ndarray:
    t = np.arange(T)
    return np.clip((t - S0) / (S1 - S0), 0, 1) * total


def build(tmp: Path, ref_chord: float) -> tuple[Path, Path, Path]:
    rng = np.random.default_rng(0)
    ref = np.zeros((T, 1, 7))
    ref[:, 0, 3:7] = yaw_quat(ramp(300.0))
    ach = np.zeros((T, W, 1, 7))
    ach[:, :, 0, :3] = 0.02
    for w in range(W):
        if w < 4:
            yaw = ramp(180.0)
        elif w < 6:
            yaw = ramp(40.0)
        else:
            yaw = np.cumsum(np.where(np.arange(T) % 2 == 0, 0.5, -0.5))  # 来回抖动，净 0
        qw = yaw_quat(yaw)
        qw *= np.where(rng.random(T) < 0.5, -1.0, 1.0)[:, None]  # 正负号翻转不应影响结果
        ach[:, w, 0, 3:7] = qw
    names = ["pelvis_position_m", "pelvis_orientation_rad", "palm_position_m", "palm_orientation_rad",
             "object_position_m", "object_orientation_rad"]
    err = np.full((T, W, 6), 0.01)
    err[300:, 6:, 2] = 0.2  # palm 越线
    criteria = {"error_names": names, "thresholds": [0.25, 0.8, 0.1, 1.0, 0.1, 1.5],
                "active_after_step": [-1, -1, 10, 10, 10, 10],
                "causes": [["pelvis", [0, 1]], ["palm", [2, 3]], ["object", [4, 5]]]}
    npz = tmp / "r.npz"
    np.savez(npz, achieved_pose_w=ach, reference_pose_w=ref, tracking_error=err, tracking_error_names=np.array(names),
             control_fps=np.float64(50), start_frame=np.int64(0), non_finite_worlds=np.array([], dtype=np.int64),
             completion_truncated=np.ones(W, dtype=bool), completion_progress=np.ones(W),
             criteria_json=np.array(json.dumps(criteria)), reported_success_rate=np.float64(0.75),
             policy=np.array("synthetic"), world_count=np.int64(W))
    run, refp = tmp / "run.json", tmp / "ref.json"
    run.write_text(json.dumps({"metrics": {"add_auc": 0.430, "chord_sr": 0.75}, "checkpoint_sha256": "x", "world_count": W}))
    refp.write_text(json.dumps({"metrics": {"add_auc": 0.431, "chord_sr": ref_chord}, "checkpoint_sha256": "x", "world_count": 4096}))
    return npz, run, refp


def svg_balanced(text: str) -> bool:
    """只检查标签配对（自己生成的文件，不需要完整 XML 解析器）。"""
    stack, bad = [], []

    class P(HTMLParser):
        def handle_starttag(self, tag, attrs):
            stack.append(tag)

        def handle_startendtag(self, tag, attrs):
            pass

        def handle_endtag(self, tag):
            if stack and stack[-1] == tag:
                stack.pop()
            else:
                bad.append(tag)

    P().feed(text)
    return text.lstrip().startswith("<svg") and not stack and not bad


def run_diag(npz, run, refp, svg=None):
    cmd = [sys.executable, str(HERE / "diag_rotation.py"), str(npz), str(run), str(refp), "--segment", str(S0), str(S1)]
    if svg:
        cmd += ["--svg", str(svg)]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def main() -> int:
    fails = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal fails
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  | {detail}"))
        fails += not ok

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        npz, run, refp = build(tmp, ref_chord=0.79)
        p = run_diag(npz, run, refp, svg=tmp / "c.svg")
        out = p.stdout
        check("有效性通过时退出码 0", p.returncode == 0, p.stderr[-500:])
        check("VALIDITY PASS", "VALIDITY PASS" in out, out[:300])
        check("参考净转 300°", "绕主轴净转 300.0°" in out, out[:600])
        check("主轴竖直（夹角 0.0°）", "竖直方向夹角 0.0°" in out)
        check("逐世界成功率重算为 0.75", "逐世界重算的成功率 0.7500 vs 评测报告 0.7500" in out)
        line = next((ln for ln in out.splitlines() if ln.strip().startswith("解读（逐世界）")), "")
        check("三类解读计数 4/2/2", all(s in line for s in ("跟着转了 4", "尝试了但没跟上 2", "基本没转 2")), line)
        jitter = next((ln for ln in out.split("== 失败的世界")[1].splitlines() if "增量绝对值之和中位" in ln), "")
        check("抖动世界：带符号净转 0°、绝对值之和约 105°", "实际 中位 0.0°" in jitter and "绝对值之和中位 10" in jitter, jitter)
        check("SVG 标签配对完整", svg_balanced((tmp / "c.svg").read_text()))
        npz, run, refp = build(tmp, ref_chord=0.90)
        p = run_diag(npz, run, refp)
        check("chord_sr 相差 0.15 时拦截：退出码 3 且 VALIDITY FAIL", p.returncode == 3 and "VALIDITY FAIL" in p.stdout, p.stdout[:300])
    print(f"结果：{'全部通过' if fails == 0 else f'{fails} 项失败'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
