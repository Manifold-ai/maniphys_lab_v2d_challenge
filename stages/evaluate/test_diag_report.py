"""diag_report.py 的合成数据测试（只用 numpy；暂无契约 ID：诊断工具不在交付链上）。

参考绕某轴在第 209–420 帧匀速转 300°（默认竖直轴；另测倾斜 20° 的轴）。10 个世界：
0–3 跟到 90%（全程不越物体门槛，palm 正常 → 成功）；4–5 只转 40°；6–7 不转但每帧 ±0.5° 来回抖动，世界 6 另有一对 ±40° 跳变；
8–9 先转 60°（第 300 帧）再转回 0°（第 420 帧）。随机翻转四元数正负号。环境自带的朝向误差按位姿算，与脚本应当对得上。
检查：七道闸各自通过与被拦（逐项改坏一处）、四类分类计数、主轴夹角、跳变计数、Q0 各段贡献相加等于全程、SVG 标签配对。
用法：python stages/evaluate/test_diag_report.py
"""
import json
import re
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
T, W, S0, S1 = 553, 10, 209, 420
THR = np.arange(0.01, 0.10, 0.01)


def auc(x):
    x = np.asarray(x, np.float64).ravel()
    return float(np.trapezoid([np.mean(x < t) for t in THR], x=np.linspace(0, 1, THR.size)))


def axis_angle_quat(axis, deg):
    h = np.radians(deg) / 2
    s = np.sin(h)[..., None] * np.asarray(axis)[None, :]
    return np.concatenate([s, np.cos(h)[..., None]], -1)  # xyzw


def ramp(total, a=S0, b=S1):
    t = np.arange(T)
    return np.clip((t - a) / (b - a), 0, 1) * total


def geodesic_deg(qa, qb):
    return np.degrees(2 * np.arccos(np.clip(np.abs(np.sum(qa * qb, -1)), 0, 1)))


def build(tmp: Path, tilt_deg=0.0, **broken):
    rng = np.random.default_rng(0)
    axis = np.array([0.0, np.sin(np.radians(tilt_deg)), np.cos(np.radians(tilt_deg))])
    ref_deg = ramp(300.0)
    qr = axis_angle_quat(axis, ref_deg)
    ach = np.zeros((T, W, 1, 7))
    ach[:, :, 0, :3] = 0.02
    for w in range(W):
        if w < 4:
            deg = 0.9 * ref_deg
        elif w < 6:
            deg = ramp(40.0)
        elif w < 8:
            deg = np.cumsum(np.where(np.arange(T) % 2 == 0, 0.5, -0.5))
            if w == 6:
                deg = deg + np.where((np.arange(T) == 100), 40.0, 0.0)  # 第 100 帧单独偏 40°：前后两个增量都 > 30°
        else:
            deg = np.where(np.arange(T) <= 300, ramp(60.0, S0, 300), 60.0 - ramp(60.0, 300, S1))
        q = axis_angle_quat(axis, deg)
        q *= np.where(rng.random(T) < 0.5, -1.0, 1.0)[:, None]
        ach[:, w, 0, 3:7] = q
    ref = np.zeros((T, 1, 7))
    ref[:, 0, 3:7] = qr
    names = ["pelvis_position_m", "pelvis_orientation_rad", "palm_position_m", "palm_orientation_rad",
             "object_position_m", "object_orientation_rad"]
    err = np.full((T, W, 6), 0.01)
    ori = geodesic_deg(ach[:, :, 0, 3:7], qr[:, None])
    err[..., 5] = np.radians(ori) + (np.radians(1.0) if broken.get("env_ori") else 0.0)
    err[300:, 6:8, 2] = 0.2  # 抖动世界 palm 越线
    criteria = {"error_names": names, "thresholds": [0.25, 0.8, 0.15, 1.5, 0.1, 1.5],
                "active_after_step": [-1, -1, 10, 10, 10, 10],
                "causes": [["pelvis", [0, 1]], ["palm", [2, 3]], ["object", [4, 5]]]}
    thr = np.array(criteria["thresholds"])
    act = np.array(criteria["active_after_step"])
    exceeded = ((np.arange(T)[:, None, None] > act[None, None, :]) & (err > thr[None, None, :])).any((0, 2))
    success_rate = float((~exceeded).mean())
    add = rng.uniform(0, 0.12, size=(T, W))
    add_static = rng.uniform(0, 0.12, size=T)
    np.savez(tmp / "r.npz", achieved_pose_w=ach, reference_pose_w=ref, tracking_error=err, add=add, add_static=add_static,
             tracking_error_names=np.array(names), ref_palm_names=np.array(["left_hand_palm_link", "right_hand_palm_link"]),
             ref_palm_mesh_dist=np.full((T, 2), 0.05), contact_sides=np.array(["left", "right"]),
             contact_active=np.zeros((T, 2), bool), completion_truncated=np.ones(W, bool), completion_progress=np.ones(W),
             non_finite_worlds=np.array([], np.int64), criteria_json=np.array(json.dumps(criteria)),
             reported_success_rate=np.float64(success_rate), policy=np.array("synthetic"),
             upstream_md5=np.array("{}"), wrapper_calls=np.array('{"record": 1, "score": 1}'))
    metrics = {"add_auc": auc(add) + (0.01 if broken.get("add_auc") else 0.0), "chord_sr": success_rate,
               "maniptrans_sr": 0.0, "mppe_cm": 3.0}
    diag = {"metrics": metrics, "checkpoint_sha256": "x", "world_count": W, "step_count": T}
    same = json.loads(json.dumps(diag))
    if broken.get("same_card"):  # 只有 10 个世界时 chord_sr 的 z 检验很弱，另把 ADD-AUC 改掉 0.01（> 0.005 的容差）
        same["metrics"]["chord_sr"] = 0.0 if success_rate > 0.5 else 1.0
        same["metrics"]["add_auc"] += 0.01
    (tmp / "diag.json").write_text(json.dumps(diag))
    (tmp / "same.json").write_text(json.dumps(same))
    return success_rate


def run(tmp: Path, expect=(210, 420, 270), predict=(359, 94), svg=False):
    cmd = [sys.executable, str(HERE / "diag_report.py"), str(tmp / "r.npz"), "--diag-json", str(tmp / "diag.json"),
           "--same-card-json", str(tmp / "same.json"), "--segments", str(S0), str(S1),
           "--expect-ref", *map(str, expect), "--predict", *map(str, predict)]
    if svg:
        cmd += ["--svg", str(tmp / "c.svg")]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def svg_balanced(text: str) -> bool:
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


def main() -> int:
    fails = 0

    def check(name, ok, detail=""):
        nonlocal fails
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  | {detail[:400]}"))
        fails += not ok

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        sr = build(tmp)
        p = run(tmp, svg=True)
        out = p.stdout
        check("成功率 0.4（世界 0–3）", abs(sr - 0.4) < 1e-12, str(sr))
        check("全部闸通过、退出码 0", p.returncode == 0 and "VALIDITY PASS" in out and out.count("  FAIL  ") == 0, out[:900] + p.stderr[-400:])
        check("G1 判为逐位相同", "包装前后逐位相同" in out, out[:600])
        cls = next((ln for ln in out.splitlines() if "分类（事先登记）" in ln), "")
        check("四类计数 4/4/2/0", all(s in cls for s in ("净转过半 4", "转过但没保持或没跟上 4", "基本没转 2", "其他 0")), cls)
        check("主轴竖直", "竖直方向夹角 0.0°" in out)
        check("跳变 2 次", "跳变 2 次" in out, next((ln for ln in out.splitlines() if "跳变" in ln), ""))
        contrib = [float(x) for x in re.findall(r"贡献 ([0-9.]+) / ", out)]
        full = float(re.search(r"全程：policy ([0-9.]+)", out).group(1))
        check("Q0 三段贡献相加等于全程", len(contrib) == 3 and abs(sum(contrib) - full) < 3e-4, f"{contrib} vs {full}")
        check("SVG 标签配对完整", svg_balanced((tmp / "c.svg").read_text()))
        for key, label in (("add_auc", "G2"), ("env_ori", "G3"), ("same_card", "G1")):
            build(tmp, **{key: True})
            p = run(tmp)
            check(f"{label} 改坏后被拦（退出码 3、分类不给）", p.returncode == 3 and "VALIDITY FAIL" in p.stdout and "分类：闸没过" in p.stdout,
                  p.stdout[:700])
        build(tmp)
        p = run(tmp, expect=(209, 420, 269))
        check("G4 已知答案不符时被拦", p.returncode == 3 and "FAIL  G4" in p.stdout, p.stdout[:600])
        p = run(tmp, predict=(359, 170))
        check("G6 事先预测不成立时被拦", p.returncode == 3 and "FAIL  G6" in p.stdout, p.stdout[:600])
        build(tmp, tilt_deg=20.0)
        p = run(tmp)
        cls = next((ln for ln in p.stdout.splitlines() if "分类（事先登记）" in ln), "")
        check("主轴倾斜 20°：夹角算对、分类不变", "竖直方向夹角 20.0°" in p.stdout and "净转过半 4" in cls and p.returncode == 0,
              p.stdout[:700])
    print(f"结果：{'全部通过' if fails == 0 else f'{fails} 项失败'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
