"""把若干份评测文本并成一张表（Mac 上跑，只用标准库，只读已落盘的结果）。

每份文件要有 summary_json 行（fc_eval 打的，见 results/day2/eval_<run>_s<步数>.txt）；run 名取自其中 checkpoint 的路径。
列：run、步数、世界数、帧数、MP-SR（maniptrans_sr）、SP-SR（spider_sr_uncentered）、ADD-AUC、MPPE（cm）、平均位置误差（cm）、
平均朝向误差（°）、CHORD SR、失败原因里骨盆 / 物体 / 手掌的比例、checkpoint sha256 前 12 位。成功率与误差都是对全部世界取平均。
用法：python3 stages/evaluate/eval_table.py <评测文本> ...
"""
import json
import re
import sys
from pathlib import Path


def row(path: Path) -> list[str]:
    m = re.search(r"summary_json (\{.*\})", path.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(f"eval_table: {path} 里没有 summary_json 行")
    j = json.loads(m.group(1))
    run = Path(j["checkpoint"]).parent.name
    fail = j["reference_tracking"]["failure_cause_fraction"]
    return [
        run, str(j["environment_steps"]), str(j["world_count"]), str(j["step_count"]),
        f"{j['maniptrans_sr']:.3f}", f"{j['spider_sr_uncentered']:.3f}", f"{j['add_auc']:.3f}", f"{j['mppe_cm']:.2f}",
        f"{100 * j['object_position_error_m']:.2f}", f"{j['object_orientation_error_deg']:.1f}", f"{j['chord_sr']:.3f}",
        f"{fail.get('pelvis', 0.0):.3f}", f"{fail.get('object', 0.0):.3f}", f"{fail.get('palm', 0.0):.3f}",
        j["checkpoint_sha256"][:12],
    ]


def main(argv: list[str]) -> int:
    if not argv:
        raise SystemExit(__doc__)
    head = ["run", "步数", "世界", "帧", "MP-SR", "SP-SR", "ADD-AUC", "MPPE_cm", "位置_cm", "朝向_deg", "CHORD_SR",
            "失败_骨盆", "失败_物体", "失败_手掌", "sha256"]
    print("\t".join(head))
    for p in argv:
        print("\t".join(row(Path(p))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
