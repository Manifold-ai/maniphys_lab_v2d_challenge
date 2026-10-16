"""r3o_verdict.py 的测试（暂无契约 ID；计划 agent-doc/plan-r3o-2026-10-15.md 2.2、2.3）。只用标准库，在 Mac 上跑。
临时目录里造 P1 的对照与 7 集跟丢集的 eval_<步数>_w4096.json（规格用临时的小规格，判法与段间门相同）：
  1. 修好 2 集、对照过 → 有用；2. 修好 2 集、对照不过 → 没用（修好不止 1 集，看不清的条件也不满足）；3. 修好 1 集 → 看不清；
  4. 修好 0 集、有起色 2 集（一集 MP-SR 0.15，一集失败_物体降 0.25）→ 看不清；5. 全没用 → 没用；6. 少一个评测文件 → 退出码 2。
用法：python3 stages/policy/test_r3o_verdict.py；最后一行 ALL_OK。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parent / "r3o_verdict.py"
STEP = 349999104


def ev(root: Path, run: str, mp: float, sp: float = 0.0, obj: float = 1.0) -> None:
    d = root / "runs/flash_chord" / run
    d.mkdir(parents=True, exist_ok=True)
    (d / f"eval_{STEP}_w4096.json").write_text(json.dumps({"world_count": 4096, "non_finite_worlds": [],
                                                           "metrics": {"maniptrans_sr": mp, "spider_sr_uncentered": sp},
                                                           "reference_tracking": {"failure_cause_fraction": {"object": obj}}}))


def case(ctl_mp: float, lost: list, drop: bool = False) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        spec = {"P1": {"tier": 1, "control": {"run": "ctl", "floor": 0.45}, "lost": {}}}
        ev(root, "ctl", ctl_mp)
        for i, (mp, sp, obj) in enumerate(lost):
            run = f"lost{i}"
            spec["P1"]["lost"][run] = {"baseline_run": f"b{i}", "baseline_obj_fail": 1.0, "baseline_sp": 0.0}
            if not (drop and i == 0):
                ev(root, run, mp, sp, obj)
        (root / "spec.json").write_text(json.dumps(spec))
        return subprocess.run([sys.executable, str(TOOL), "P1", "--root", str(root), "--spec", str(root / "spec.json")],
                              capture_output=True, text=True, check=False)


def last(r: subprocess.CompletedProcess) -> str:
    return r.stdout.strip().splitlines()[-1]


if __name__ == "__main__":
    none = (0.0, 0.0, 1.0)
    r = case(0.84, [(0.5, 0.5, 0.2), (0.31, 0.4, 0.5)] + [none] * 5)
    assert last(r) == "R3O_VERDICT 有用", r.stdout
    print("  1. 修好 2 集、对照过 → 有用")
    r = case(0.40, [(0.5, 0.5, 0.2), (0.31, 0.4, 0.5)] + [none] * 5)
    assert last(r) == "R3O_VERDICT 没用", r.stdout
    print("  2. 修好 2 集、对照不过 → 没用")
    r = case(0.84, [(0.5, 0.5, 0.2)] + [none] * 6)
    assert last(r) == "R3O_VERDICT 看不清", r.stdout
    print("  3. 修好 1 集 → 看不清")
    r = case(0.84, [(0.15, 0.0, 1.0), (0.0, 0.0, 0.75)] + [none] * 5)
    assert last(r) == "R3O_VERDICT 看不清", r.stdout
    print("  4. 修好 0 集、有起色 2 集 → 看不清")
    r = case(0.84, [none] * 7)
    assert last(r) == "R3O_VERDICT 没用", r.stdout
    print("  5. 全没用 → 没用")
    r = case(0.84, [none] * 7, drop=True)
    assert r.returncode == 2 and last(r) == "R3O_VERDICT_ERROR", r.stdout
    print("  6. 少一个评测文件 → 退出码 2")
    print("ALL_OK")
