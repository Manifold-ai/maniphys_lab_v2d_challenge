"""逐帧诊断：物体朝向误差在哪一段累积、物体有没有被转动、手有没有沿参考走（只用 numpy，容器内外都能跑）。

读 diag_rollout.py 存下的 npz 与两份评测报告，按 agent-doc/plan-day1b-2026-09-27.md 事先登记的 Q1–Q4 输出数字，另画一张 SVG。
先做有效性检查：本次诊断的汇总指标必须与参照评测一致（同一个 checkpoint，|ΔADD-AUC| < 0.01 且 |Δchord_sr| < 0.05），
再核对按判据逐个世界重算的成功率与评测报告一致；任何一条不过，只打印数字、不给解读，退出码 3。

转动的度量：取参考在关注段内逐帧转动增量（世界系旋转向量 log(R_t R_{t-1}^T)）之和的方向作为主轴 a，把参考与实际的逐帧增量
都投影到 a 上再带符号累加，得到“转动进度”。零均值的逐帧抖动在带符号累加里相互抵消，不会像“增量绝对值之和”那样随帧数攒起来；
全程用旋转矩阵，不受四元数正负号翻转影响；主轴不必竖直（另报它与竖直方向的夹角）。

用法：python diag_rotation.py <rollout.npz> <本次评测 JSON> <参照评测 JSON> [--segment 209 420] [--svg out.svg] [--title 名字]
"""
import argparse
import json
import sys

import numpy as np

KEY_FRAMES = (0, 100, 209, 269, 300, 360, 420)


def quat_xyzw_to_matrix(q: np.ndarray) -> np.ndarray:
    q = q / np.linalg.norm(q, axis=-1, keepdims=True)
    x, y, z, w = np.moveaxis(q, -1, 0)
    return np.stack([
        np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], -1),
        np.stack([2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], -1),
        np.stack([2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)], -1),
    ], -2)


def rotvec(R: np.ndarray) -> np.ndarray:
    """(…,3,3) → (…,3)。对数映射；这里的逐帧增量远小于 π。"""
    ang = np.arccos(np.clip((np.trace(R, axis1=-2, axis2=-1) - 1) / 2, -1, 1))
    v = np.stack([R[..., 2, 1] - R[..., 1, 2], R[..., 0, 2] - R[..., 2, 0], R[..., 1, 0] - R[..., 0, 1]], -1)
    s = np.sin(ang)
    return v * np.where(s > 1e-9, ang / (2 * np.where(s > 1e-9, s, 1)), 0.5)[..., None]


def angle_deg(R: np.ndarray) -> np.ndarray:
    return np.degrees(np.arccos(np.clip((np.trace(R, axis1=-2, axis2=-1) - 1) / 2, -1, 1)))


def world_increments(R: np.ndarray) -> np.ndarray:
    """逐帧世界系增量 log(R_t R_{t-1}^T)，R 形状 (T,…,3,3) → (T-1,…,3)。"""
    return rotvec(np.einsum("t...ij,t...kj->t...ik", R[1:], R[:-1]))


def classify(net_ach: float, net_ref: float) -> str:
    """事先登记的 Q2 解读规则（带符号净转动）。"""
    if net_ref != 0 and net_ach / net_ref >= 0.5:
        return "跟着转了"
    if np.sign(net_ach) == np.sign(net_ref) and abs(net_ach) >= 30:
        return "尝试了但没跟上"
    if abs(net_ach) < 10:
        return "基本没转"
    return "其他（如实描述）"


def q(x: np.ndarray, axis=None):
    return np.percentile(x, [25, 50, 75], axis=axis)


def svg_chart(title, T, s0, s1, panels) -> str:
    """panels: [(标题, y 单位, [(名字, y(T,), 颜色, 虚线?)], 带(lo,hi)或 None, 水平线或 None)] → SVG 字符串。"""
    Wd, left, right, ph, gap, top = 900, 70, 20, 150, 46, 40
    H = top + len(panels) * (ph + gap) + 10
    def x(f):
        return left + (Wd - left - right) * f / max(T - 1, 1)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {Wd} {H}" font-family="sans-serif" font-size="12">',
           f'<rect x="0" y="0" width="{Wd}" height="{H}" fill="#ffffff"/>',
           f'<text x="{left}" y="22" font-size="14" font-weight="700" fill="#111111">{title}</text>']
    for k, (ptitle, unit, series, band, hline) in enumerate(panels):
        y0 = top + k * (ph + gap) + 18
        vals = [s[1] for s in series] + ([band[0], band[1]] if band else []) + ([np.full(T, hline)] if hline is not None else [])
        lo, hi = float(np.nanmin(vals)), float(np.nanmax(vals))
        if hi - lo < 1e-9:
            hi = lo + 1
        pad = 0.05 * (hi - lo)
        lo, hi = lo - pad, hi + pad
        def y(v, y0=y0, lo=lo, hi=hi):  # 绑定本轮的面板参数
            return y0 + ph - ph * (v - lo) / (hi - lo)
        out.append(f'<text x="{left}" y="{y0 - 6}" font-weight="700" fill="#111111">{ptitle}</text>')
        out.append(f'<rect x="{x(s0):.1f}" y="{y0}" width="{x(s1) - x(s0):.1f}" height="{ph}" fill="#000000" fill-opacity="0.06"/>')
        out.append(f'<rect x="{left}" y="{y0}" width="{Wd - left - right}" height="{ph}" fill="none" stroke="#bbbbbb"/>')
        for t in np.linspace(lo + pad, hi - pad, 4):
            out.append(f'<text x="{left - 6}" y="{y(t) + 4:.1f}" text-anchor="end" fill="#555555">{t:.0f}{unit}</text>')
        if band is not None:
            pts = [f"{x(f):.1f},{y(v):.1f}" for f, v in enumerate(band[1])] + [f"{x(f):.1f},{y(v):.1f}" for f, v in reversed(list(enumerate(band[0])))]
            out.append(f'<polygon points="{" ".join(pts)}" fill="#2e7d32" fill-opacity="0.18" stroke="none"/>')
        if hline is not None:
            out.append(f'<line x1="{left}" x2="{Wd - right}" y1="{y(hline):.1f}" y2="{y(hline):.1f}" stroke="#b3261e" stroke-dasharray="5 4"/>')
        for i, (name, ys, color, dashed) in enumerate(series):
            pts = " ".join(f"{x(f):.1f},{y(v):.1f}" for f, v in enumerate(ys))
            dash = ' stroke-dasharray="4 3"' if dashed else ""  # 容器是 Python 3.11：f-string 表达式里不能有反斜杠
            out.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.6"{dash}/>')
            out.append(f'<text x="{Wd - right - 6}" y="{y0 + 14 + 14 * i}" text-anchor="end" fill="{color}">{name}</text>')
        if k == len(panels) - 1:
            for f in range(0, T, 100):
                out.append(f'<text x="{x(f):.1f}" y="{y0 + ph + 16}" text-anchor="middle" fill="#555555">{f}</text>')
            out.append(f'<text x="{(x(s0) + x(s1)) / 2:.1f}" y="{y0 + ph + 32}" text-anchor="middle" fill="#555555">帧（灰底为第 {s0}–{s1} 帧）</text>')
    out.append("</svg>")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("npz")
    ap.add_argument("run_json")
    ap.add_argument("ref_json")
    ap.add_argument("--segment", type=int, nargs=2, default=(209, 420))
    ap.add_argument("--svg")
    ap.add_argument("--title", default="")
    a = ap.parse_args()
    s0, s1 = a.segment

    d = np.load(a.npz, allow_pickle=False)
    ach = d["achieved_pose_w"][:, :, 0].astype(np.float64)   # (T,W,7) 位置 + xyzw
    ref = d["reference_pose_w"][:, 0].astype(np.float64)      # (T,7)
    err = d["tracking_error"].astype(np.float64)              # (T,W,E)
    names = [str(n) for n in d["tracking_error_names"]]
    T, W = ach.shape[:2]
    crit = json.loads(str(d["criteria_json"]))
    with open(a.run_json) as f:
        run = json.load(f)
    with open(a.ref_json) as f:
        refj = json.load(f)
    print(f"policy {d['policy']}  worlds {W}  frames {T}  segment {s0}-{s1}  error terms {names}")

    # ── 有效性 ─────────────────────────────────────────────────────────
    ra, rc, fa, fc = run["metrics"]["add_auc"], run["metrics"]["chord_sr"], refj["metrics"]["add_auc"], refj["metrics"]["chord_sr"]
    same_ckpt = run["checkpoint_sha256"] == refj["checkpoint_sha256"]
    thr, act = crit["thresholds"], crit["active_after_step"]
    step = np.arange(T)[:, None]
    cause_fail, first_fail, first_cause = {}, np.full(W, T), np.array([""] * W, dtype=object)
    for cname, idx in crit["causes"]:
        f = np.zeros(W, dtype=bool)
        for i in idx:
            if thr[i] is None:
                continue
            ex = (step > act[i]) & (err[..., i] > thr[i])
            f |= ex.any(0)
            fe = np.where(ex.any(0), ex.argmax(0), T)
            first_cause = np.where(fe < first_fail, cname, first_cause)
            first_fail = np.minimum(first_fail, fe)
        cause_fail[cname] = f
    invalid = np.zeros(W, dtype=bool)
    invalid[d["non_finite_worlds"]] = True
    reached = d["completion_truncated"].astype(bool) & np.isclose(d["completion_progress"], 1.0, atol=1e-6)
    success = reached & ~invalid & ~np.logical_or.reduce(list(cause_fail.values()))
    rec, rep = float(success.mean()), float(d["reported_success_rate"])
    valid = same_ckpt and abs(ra - fa) < 0.01 and abs(rc - fc) < 0.05 and abs(rec - rep) < 1e-9
    print("== 有效性")
    print(f"  checkpoint 相同 {same_ckpt}；ADD-AUC 本次 {ra:.4f} vs 参照 {fa:.4f}（|Δ| {abs(ra - fa):.4f} < 0.01）；"
          f"chord_sr 本次 {rc:.4f} vs 参照 {fc:.4f}（|Δ| {abs(rc - fc):.4f} < 0.05）；参照 {refj.get('world_count')} 世界")
    print(f"  逐世界重算的成功率 {rec:.4f} vs 评测报告 {rep:.4f}；门槛 {dict(zip(crit['error_names'], thr))}，生效步 {act}")
    print(f"  VALIDITY {'PASS' if valid else 'FAIL'}")

    # ── 基本量 ─────────────────────────────────────────────────────────
    Ra, Rr = quat_xyzw_to_matrix(ach[..., 3:7]), quat_xyzw_to_matrix(ref[:, 3:7])
    ori = angle_deg(np.einsum("twij,tkj->twik", Ra, Rr))                  # (T,W) 物体朝向误差（°）
    pos = np.linalg.norm(ach[..., :3] - ref[:, None, :3], axis=-1) * 100   # (T,W) 物体位置误差（cm）
    col = {n: i for i, n in enumerate(names)}
    palm = err[..., col["palm_position_m"]] * 100 if "palm_position_m" in col else np.full((T, W), np.nan)
    pelvis = err[..., col["pelvis_position_m"]] * 100 if "pelvis_position_m" in col else np.full((T, W), np.nan)
    env_ori = np.degrees(err[..., col["object_orientation_rad"]]) if "object_orientation_rad" in col else None
    inc_r, inc_a = world_increments(Rr), world_increments(Ra)             # (T-1,3), (T-1,W,3)
    axis = inc_r[s0:s1].sum(0)
    axis /= np.linalg.norm(axis)
    phi_r = np.degrees(np.concatenate([[0.0], np.cumsum(inc_r @ axis)]))              # (T,)
    phi_a = np.degrees(np.concatenate([np.zeros((1, W)), np.cumsum(inc_a @ axis, 0)]))  # (T,W)
    net_r, net_a = phi_r[s1] - phi_r[s0], phi_a[s1] - phi_a[s0]
    unsigned_a = np.degrees(np.linalg.norm(inc_a[s0:s1], axis=-1).sum(0))
    unsigned_r = float(np.degrees(np.linalg.norm(inc_r[s0:s1], axis=-1).sum()))
    kf = [k for k in KEY_FRAMES if k < T] + [T - 1]

    def report(label, m):
        if not m.any():
            print(f"== {label}：0 个世界")
            return
        o, p, pl, pv = ori[:, m], pos[:, m], palm[:, m], pelvis[:, m]
        med = np.median(o, 1)
        first30 = int(np.argmax(med > 30)) if (med > 30).any() else None
        first86 = int(np.argmax(med > 86)) if (med > 86).any() else None
        print(f"== {label}：{int(m.sum())} 个世界")
        print("  Q1 物体朝向误差（°，世界中位）：" + "  ".join(f"{k}:{med[k]:.1f}" for k in kf))
        print(f"     分段平均：0–{s0 - 1} {o[:s0].mean():.1f}；{s0}–{s1} {o[s0:s1 + 1].mean():.1f}；{s1 + 1}–{T - 1} {o[s1 + 1:].mean():.1f}；"
              f"中位首次超过 30° 在第 {first30} 帧、超过 86° 在第 {first86} 帧")
        print("     物体位置误差（cm，世界中位）：" + "  ".join(f"{k}:{np.median(p[k]):.1f}" for k in kf))
        na = net_a[m]
        lo, mid, hi = q(na)
        print(f"  Q2 绕主轴的净转动 第 {s0}–{s1} 帧：参考 {net_r:.1f}°；实际 中位 {mid:.1f}°（四分位 {lo:.1f}–{hi:.1f}），"
              f"占参考 {mid / net_r:.0%}；实际增量绝对值之和中位 {np.median(unsigned_a[m]):.1f}°（仅供参考，含抖动）")
        cls = [classify(v, net_r) for v in na]
        print("     解读（逐世界）：" + "；".join(f"{c} {cls.count(c)}" for c in dict.fromkeys(cls)) +
              f"；世界中位值落在：{classify(mid, net_r)}")
        print("     转动进度（°，世界中位）：" + "  ".join(f"{k}:{np.median(phi_a[k, m]):.0f}/{phi_r[k]:.0f}" for k in kf) + "（实际/参考）")
        print(f"  Q3 第 {s0}–{s1} 帧 palm 位置误差中位 {np.median(pl[s0:s1 + 1]):.1f} cm（对照物体朝向误差中位 {np.median(o[s0:s1 + 1]):.1f}°）；"
              f"0–{s0 - 1} 帧 {np.median(pl[:s0]):.1f} cm；{s1 + 1} 帧以后 {np.median(pl[s1 + 1:]):.1f} cm")
        print("     palm 位置误差（cm，世界中位）：" + "  ".join(f"{k}:{np.median(pl[k]):.1f}" for k in kf) +
              f"；pelvis 位置误差中位 {np.nanmedian(pv):.1f} cm")

    print("== 参考与主轴")
    print(f"  参考第 {s0}–{s1} 帧绕主轴净转 {net_r:.1f}°，增量绝对值之和 {unsigned_r:.1f}°；主轴与竖直方向夹角 {np.degrees(np.arccos(abs(axis[2]))):.1f}°")
    if env_ori is not None:
        print(f"  （核对）环境自带的物体朝向误差与按位姿算的差：中位 {np.median(np.abs(env_ori - ori)):.3f}°，最大 {np.max(np.abs(env_ori - ori)):.3f}°")
    report("全部世界", np.ones(W, dtype=bool))
    report("任务原生判据下成功的世界", success)
    fail = ~success
    report("失败的世界", fail)
    if fail.any():
        ff = first_fail[fail]
        causes = first_cause[fail]
        print(f"  Q4 失败世界首次越线：第 {int(np.percentile(ff, 25))}/{int(np.median(ff))}/{int(np.percentile(ff, 75))} 帧（四分位）；"
              "首个越线的原因：" + "；".join(f"{c} {int((causes == c).sum())}" for c in dict.fromkeys(causes.tolist())))

    if a.svg:
        lo_o, med_o, hi_o = q(ori, axis=1)
        lo_p, med_p, hi_p = q(phi_a, axis=1)
        lo_h, med_h, hi_h = q(palm, axis=1)
        svg = svg_chart(a.title or str(d["policy"]), T, s0, s1, [
            ("绕主轴的转动进度（参考 vs 实际，世界中位与四分位）", "°",
             [("参考", phi_r, "#222222", True), ("实际（中位）", med_p, "#2e7d32", False)], (lo_p, hi_p), None),
            ("物体朝向误差（红虚线：1.5 rad 门槛）", "°", [("中位", med_o, "#2e7d32", False)], (lo_o, hi_o), 85.94),
            ("palm 位置误差", "cm", [("中位", med_h, "#2e7d32", False)], (lo_h, hi_h), None),
        ])
        with open(a.svg, "w") as f:
            f.write(svg)
        print(f"svg: {a.svg}")
    return 0 if valid else 3


if __name__ == "__main__":
    sys.exit(main())
