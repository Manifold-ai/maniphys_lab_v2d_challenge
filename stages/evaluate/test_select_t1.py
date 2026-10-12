"""select_t1.py 的选择规则测试：守 agent-doc/plan-t1-per-episode-select-2026-10-08.md 第 4 节第 2 版（MP-SR → SP-SR → AUC / 0.3780 − MPPE / 25.1706，平手保留现在交的那条）；
--gate 参数（agent-doc/plan-next-training-2026-10-12.md 第 0 步第 4 条）：四个数按 METRICS 顺序解析，个数不对报错，默认仍是 10/3 的值。"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from select_t1 import GATE, choose, parse_gate  # noqa: E402


def c(run, mp, sp, auc, mppe):
    return {"run": run, "maniptrans_sr": mp, "spider_sr": sp, "add_auc": auc, "mppe_cm": mppe}


def test_mp_first():
    assert choose([c("a", 0.0, 1.0, 0.9, 1.0), c("b", 1.0, 0.0, 0.1, 50.0)], "a")["run"] == "b"


def test_then_sp_then_combined():
    assert choose([c("a", 0.0, 0.0, 0.9, 1.0), c("b", 0.0, 1.0, 0.1, 50.0)], "a")["run"] == "b"
    # 失败的 episode：AUC 略高但 MPPE 大得多的输给 MPPE 小的（0.05/0.378 − 90/25.17 < 0.03/0.378 − 20/25.17）
    assert choose([c("a", 0.0, 0.0, 0.05, 90.0), c("b", 0.0, 0.0, 0.03, 20.0)], "a")["run"] == "b"
    assert choose([c("a", 1.0, 1.0, 0.6, 9.0), c("b", 1.0, 1.0, 0.6, 2.0)], "a")["run"] == "b"


def test_tie_keeps_current():
    assert choose([c("a", 1.0, 1.0, 0.6, 2.0), c("b", 1.0, 1.0, 0.6, 2.0)], "b")["run"] == "b"
    assert choose([c("b", 1.0, 1.0, 0.6, 2.0), c("a", 1.0, 1.0, 0.6, 2.0)], "z")["run"] == "a"


def test_gate_arg():
    assert parse_gate("0.459651,0.600000,0.500000,24.623127") == {"add_auc": 0.459651, "spider_sr": 0.6, "maniptrans_sr": 0.5, "mppe_cm": 24.623127}
    assert GATE == {"add_auc": 0.3780, "spider_sr": 0.5333, "maniptrans_sr": 0.2667, "mppe_cm": 25.1706}
    try:
        parse_gate("0.1,0.2,0.3")
    except argparse.ArgumentTypeError:
        pass
    else:
        raise AssertionError("三个数应该报错")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
    print("ALL_OK")
