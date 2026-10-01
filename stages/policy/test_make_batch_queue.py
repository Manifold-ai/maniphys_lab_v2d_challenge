"""make_batch_queue.py 的行为测试（暂无契约 ID：运行规范待成文）。只用标准库，Mac 上跑，读仓库里已落盘的 results/ 与队列，不改它们。

  1. Tier 1：用第 1 批的参数重新生成 A、B 两段四份队列，与仓库里已提交、已跑过的队列逐字节相同（加 --tier 之后 Tier 1 行为不变）；
  2. Tier 2：run 名 t2-…、parquet 在 runs/motion/tier2 下、只有地面的序列加 scene.support=false、圆柱支撑面的不加、
     正式行带 V2D_KEEP_STATES=1 与 tag t2batch、帧数取 Tier 2 的重定向汇总；带 scale 方盒的 ep1 / ep7 / ep28 拒绝排队；
  3. 已存在的输出拒绝覆盖。
用法：python3 stages/policy/test_make_batch_queue.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "stages/policy/make_batch_queue.py"
PLAN1 = "agent-doc/plan-batch1-tier1-2026-09-29.md"
BATCH1 = {("ml40", "batch1a"): "0 5 7 9 12", ("mf4090", "batch1a"): "1 6 8 11 14",
          ("ml40", "batch1b"): "15 17 19 23 25", ("mf4090", "batch1b"): "16 18 22 24 28 29"}


def gen(out: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, V2D_QUEUE_DIR=str(out))
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=30)


def test_tier1_regenerates_batch1_byte_for_byte() -> None:
    with tempfile.TemporaryDirectory() as t:
        for (m, label), eps in BATCH1.items():
            r = gen(Path(t), m, label, PLAN1, *eps.split())
            assert r.returncode == 0, r.stderr
            for suffix in (".expect.tsv", "_smoke.txt", ".txt"):
                new = (Path(t) / f"{m}_{label}{suffix}").read_bytes()
                old = (ROOT / "stages/policy/queues" / f"{m}_{label}{suffix}").read_bytes()
                assert new == old, f"{m}_{label}{suffix} 与已提交的队列不同"


def test_tier2_rows() -> None:
    with tempfile.TemporaryDirectory() as t:
        r = gen(Path(t), "--tier", "2", "mf4090", "t2x", "plan.md", "0", "2", "29")
        assert r.returncode == 0, r.stderr
        exp = (Path(t) / "mf4090_t2x.expect.tsv").read_text().splitlines()
        assert exp[1].split("\t")[:6] == ["t2-ep0-w2048-cap4m-mf4090", "smoke-t2-ep0-w2048-cap4m-mf4090",
                                          "2026-06-04_14-16-23_tall_bar_stool_tip_up_04", "frame", "778", "false"], exp[1]
        assert exp[2].split("\t")[5] == "true", exp[2]            # ep2：圆柱支撑面
        assert exp[3].split("\t")[4] == "467", exp[3]             # ep29 的帧数（两档帧数本来相同，这一条只作回归，分不出来源）
        full = (Path(t) / "mf4090_t2x.txt").read_text().splitlines()
        assert full[0].startswith("# Tier 2 批量 t2x（计划 plan.md）：v5.4 净室参考"), full[0]
        assert full[1] == ("V2D_WANDB_TAG=t2batch V2D_MAX_RETRY=0 V2D_GPU_APPS=1 V2D_WANDB_UPLOAD_CKPT=0 V2D_KEEP_STATES=1 "
                           "t2-ep0-w2048-cap4m-mf4090 /repo/runs/motion/tier2/whole_body/soma/"
                           "sequence_id=2026-06-04_14-16-23_tall_bar_stool_tip_up_04/robot_name=g1/data.parquet "
                           "2048 349999104 training.replay.capacity=4000000 scene.support=false"), full[1]
        assert full[2].endswith("2048 349999104 training.replay.capacity=4000000"), full[2]
        smoke = (Path(t) / "mf4090_t2x_smoke.txt").read_text().splitlines()
        assert smoke[1].startswith("V2D_WANDB_PROJECT=v2d-selftest V2D_WANDB_TAG=smoke ") and " smoke-t2-ep0-" in smoke[1], smoke[1]
        assert "V2D_KEEP_STATES" not in smoke[1], smoke[1]
        ml = gen(Path(t), "--tier", "2", "ml40", "t2y", "plan.md", "2")
        assert ml.returncode == 0, ml.stderr
        assert "training.replay.capacity" not in (Path(t) / "ml40_t2y.txt").read_text()


def test_tier2_refuses_box_supports() -> None:
    for ep in ("1", "7", "28"):
        with tempfile.TemporaryDirectory() as t:
            r = gen(Path(t), "--tier", "2", "ml40", "t2z", "plan.md", "0", ep)
            assert r.returncode != 0 and "方盒" in r.stderr, (ep, r.stdout, r.stderr)
            assert not list(Path(t).iterdir()), f"ep{ep} 被拒时不该写出任何文件"


def test_refuses_overwrite() -> None:
    with tempfile.TemporaryDirectory() as t:
        assert gen(Path(t), "--tier", "2", "ml40", "t2w", "plan.md", "0").returncode == 0
        r = gen(Path(t), "--tier", "2", "ml40", "t2w", "plan.md", "0")
        assert r.returncode != 0 and "拒绝覆盖" in r.stderr, r.stderr


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
    print("ALL_OK")
