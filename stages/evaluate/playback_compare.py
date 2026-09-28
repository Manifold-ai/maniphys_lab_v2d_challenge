"""回放速度对照的判定（只读诊断报告里的 summary_json 行，只用标准库，任何机器都能跑）。

判据（agent-doc/plan-playback-2026-09-28.md，跑之前定下）。Δr = 同一 buffer 下，真实时长减逐帧回放（1.67 倍速）的中位净转动比：
  支持（速度是瓶颈）：Δr(满配) ≥ +0.10，且真实时长满配的中位净转比 ≥ 它自己的所需比值，且 Δr(100 万) > 0
  否定（速度不是瓶颈）：Δr(满配) < +0.03
  部分：其余情况
只有一对时：阈值用在这一对上，结论注明只有哪一对（T2 是在满配上触发的，只有 100 万一对时只作参考）。
任一报告的 VALIDITY 不是 PASS：只列数字、不判定，退出码 3。
次要数字照报、不改变判定：ADD-AUC 相对各自不动基线的差、三段贡献差、成功世界数、palm 误差中位。

用法：python3 stages/evaluate/playback_compare.py --pair 10m <逐帧回放的报告> <真实时长的报告> [--pair 1m <…> <…>]
"""
import argparse
import json
import sys
from pathlib import Path

SUPPORT_DR, REJECT_DR = 0.10, 0.03


def summary(path: str) -> dict:
    for line in Path(path).read_text().splitlines():
        s = line.strip()
        if s.startswith("summary_json "):
            return json.loads(s[len("summary_json "):])
    raise SystemExit(f"{path}: 没有 summary_json 行")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", nargs=3, action="append", required=True, metavar=("BUFFER", "FRAME_PLAYBACK_REPORT", "REAL_TIME_REPORT"))
    a = ap.parse_args()
    pairs = {}
    for name, ctrl, rt in a.pair:
        if name not in ("10m", "1m") or name in pairs:
            raise SystemExit(f"--pair 的 buffer 只能是 10m 或 1m，且各给一次（收到 {name}）")
        pairs[name] = (summary(ctrl), summary(rt))
    valid = all(c["valid"] and r["valid"] for c, r in pairs.values())
    dr = {}
    for name, (c, r) in pairs.items():
        dr[name] = r["median_net_ratio"] - c["median_net_ratio"]
        gc, gr = c["add_auc"] - c["static_add_auc"], r["add_auc"] - r["static_add_auc"]
        print(f"== {name}（逐帧回放 → 真实时长）")
        print(f"  VALIDITY {'PASS' if c['valid'] else 'FAIL'} → {'PASS' if r['valid'] else 'FAIL'}；世界数 {c['worlds']} / {r['worlds']}")
        print(f"  中位净转动比 {c['median_net_ratio']:.3f}（需 {c['required_ratio']:.3f}）→ {r['median_net_ratio']:.3f}（需 {r['required_ratio']:.3f}）；Δr {dr[name]:+.3f}")
        print(f"  ADD-AUC − 不动基线 {gc:+.4f}（{c['add_auc']:.4f} − {c['static_add_auc']:.4f}）→ {gr:+.4f}（{r['add_auc']:.4f} − {r['static_add_auc']:.4f}）；变化 {gr - gc:+.4f}")
        print("  三段贡献差 " + " / ".join(f"{x:+.4f}" for x in c["segment_gap"]) + " → " + " / ".join(f"{x:+.4f}" for x in r["segment_gap"]))
        print(f"  成功世界 {c['success']} → {r['success']}；palm 误差中位（分段，cm）"
              f"{[round(x, 1) for x in c['palm_error_median_cm']]} → {[round(x, 1) for x in r['palm_error_median_cm']]}")
    if not valid:
        print("有报告的闸没过：只列数字，不判定")
        return 3
    main_pair = "10m" if "10m" in pairs else "1m"
    other = "1m" if main_pair == "10m" else "10m"
    r_main = pairs[main_pair][1]
    reach = r_main["median_net_ratio"] >= r_main["required_ratio"]
    other_ok = dr[other] > 0 if other in pairs else True
    if dr[main_pair] < REJECT_DR:
        verdict = "否定（速度不是瓶颈）"
    elif dr[main_pair] >= SUPPORT_DR and reach and other_ok:
        verdict = "支持（速度是瓶颈）"
    else:
        verdict = "部分"
    why = (f"Δr({main_pair}) {dr[main_pair]:+.3f}；真实时长{'达到' if reach else '没达到'}所需比值"
           + (f"；Δr({other}) {dr[other]:+.3f}" if other in pairs else ""))
    note = ""
    if len(pairs) == 1:
        note = "（仅 100 万一对：T2 是在满配上触发的，只作参考）" if main_pair == "1m" else "（仅满配一对，缺 100 万的方向核对）"
    print(f"判定：{verdict}{note}  |  {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
