"""ep7_ckpt_eval.sh（连同 scripts/dev/record、stages/policy/ckpt_nonfinite.py）的行为测试（暂无契约 ID：运行规范待成文）。只用标准库。

临时目录里搭最小仓库：真的 ep7_ckpt_eval.sh、scripts/dev/record、ckpt_nonfinite.py；假的 stages/policy/fc_eval.sh（按环境变量写出
带 non_finite_worlds 的评测 JSON 或失败）、假的 scripts/dev/in-flash-chord（模拟取证 rollout）、PATH 前面放假的 nvidia-smi。
计划 agent-doc/plan-ep7-eval-and-guards-2026-10-02.md 的 A 部分。
  1. 评测成功、没有非有限世界：不跑取证；最后一行 EP7_EVAL_DONE（评测 成功；非有限世界 0；取证 没跑）；评测挂的是 8c778f9 副本
  2. 评测成功、有 2 个非有限世界：跑取证，挂的是 v0.4.0 + #185 副本、走 GPU；hydra 目录删掉、npz 留着
  3. 评测失败：非有限世界记未知，照样跑取证；取证也失败时记“取证 失败”
  4. 拒绝（退出码 2、不写日志）：日志已存在、policy 不在、policy 含 NaN、源码副本缺 SOURCE_V2D.txt、设了要等的日志却没给正则
  5. 等别的链的日志结束才开始，本日志里没有那条链结束标记的原文；GPU 一直被占则 EP7_EVAL_FAILED
  6. 试跑（V2D_EP7_EVAL_DRYRUN=1）：打印 EP7_EVAL_DRYRUN_OK，不写日志、不调评测
用法：python3 stages/evaluate/test_ep7_ckpt_eval.py
"""
import json
import os
import shutil
import struct
import subprocess
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUN, STEP, NAME = "t1-ep7-w2048-cap4m-p185-mf4090", "130004992", "ep7_eval_mf"
FAKE_EVAL = r'''#!/usr/bin/env bash
echo "eval|${V2D_FC_SRC-unset}|$*" >> runs/fake_calls.txt
[ "${FAKE_EVAL_RC:-0}" = 0 ] || { echo "fc_eval: 评测失败（假）" >&2; exit "${FAKE_EVAL_RC}"; }
printf '{"world_count": 4096, "non_finite_worlds": %s}\n' "${FAKE_NF:-[]}" > "runs/flash_chord/$1/eval_$2_w4096.json"
echo "fc_eval: 假评测 $1 policy_$2"
'''
FAKE_FC = r'''#!/usr/bin/env bash
cmd="$*"
echo "roll|${V2D_GPU:-}|${V2D_FC_SRC-unset}|$cmd" >> runs/fake_calls.txt
out=$(sed -E 's|.* /repo/(runs/ep7/[^ ]+) --worlds.*|\1|' <<< "$cmd"); mkdir -p "${out}_hydra"
[ "${FAKE_ROLL_RC:-0}" = 0 ] && touch "$out.npz"
echo "fake rollout rc ${FAKE_ROLL_RC:-0}"; exit "${FAKE_ROLL_RC:-0}"
'''
FAKE_GPU = r'''#!/usr/bin/env bash
[ "${FAKE_GPU:-}" = busy ] && echo 4242
exit 0
'''


def write_policy(path: Path, values) -> None:
    """最小的 safetensors：一个 F32 张量。mtime 往前拨，ckpt_nonfinite.py 才认它写完了。"""
    data = struct.pack(f"<{len(values)}f", *values)
    header = json.dumps({"w": {"dtype": "F32", "shape": [len(values)], "data_offsets": [0, len(data)]}}).encode()
    path.write_bytes(struct.pack("<Q", len(header)) + header + data)
    old = time.time() - 60
    os.utime(path, (old, old))


def setup(root: Path, policy=(1.0, 2.0, 3.0)) -> None:
    for d in ("stages/evaluate", "stages/policy", "scripts/dev", "bin", "runs/logs", f"runs/flash_chord/{RUN}"):
        (root / d).mkdir(parents=True, exist_ok=True)
    for f in ("stages/evaluate/ep7_ckpt_eval.sh", "scripts/dev/record", "stages/policy/ckpt_nonfinite.py"):
        shutil.copy(REPO / f, root / f); (root / f).chmod(0o755)
    for f, body in (("stages/policy/fc_eval.sh", FAKE_EVAL), ("scripts/dev/in-flash-chord", FAKE_FC), ("bin/nvidia-smi", FAKE_GPU)):
        (root / f).write_text(body); (root / f).chmod(0o755)
    (root / ".v2d-source-commit").write_text("deadbeef\n")
    for s in ("src8c", "srcp185"):
        (root / s / "src/flash_chord").mkdir(parents=True)
        (root / s / "SOURCE_V2D.txt").write_text(f"假副本 {s}\n")
    if policy is not None:
        write_policy(root / f"runs/flash_chord/{RUN}/policy_{STEP}.safetensors", policy)


def chain(root: Path, **kw) -> subprocess.CompletedProcess:
    e = dict(os.environ, PATH=f"{root / 'bin'}:{os.environ['PATH']}", V2D_POLL_S="1",
             V2D_EVAL_SRC=str(root / "src8c"), V2D_ROLLOUT_SRC=str(root / "srcp185"))
    e.update(kw)
    e = {k: v for k, v in e.items() if v is not None}
    return subprocess.run(["bash", "stages/evaluate/ep7_ckpt_eval.sh", RUN, STEP, NAME], cwd=root, env=e,
                          capture_output=True, text=True, errors="replace", timeout=120)


def log(root: Path) -> str:
    return (root / f"runs/logs/{NAME}.log").read_text(errors="replace")


def calls(root: Path) -> list:
    f = root / "runs/fake_calls.txt"
    return f.read_text().splitlines() if f.exists() else []


def test_clean() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d); setup(root)
        r = chain(root)
        assert r.returncode == 0, r.stderr
        last = log(root).strip().splitlines()[-1]
        assert "EP7_EVAL_DONE（评测 成功；非有限世界 0；取证 没跑）" in last, last
        c = calls(root)
        assert len(c) == 1 and c[0].startswith(f"eval|{root / 'src8c'}|{RUN} {STEP}"), c
        assert (root / f"results/day2/eval_{RUN}_s{STEP}.txt").exists()
        assert not (root / f"runs/.chain-active-{NAME}").exists()


def test_nonfinite() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d); setup(root)
        r = chain(root, FAKE_NF="[3, 7]")
        assert r.returncode == 0, r.stderr
        assert "EP7_EVAL_DONE（评测 成功；非有限世界 2；取证 完成）" in log(root).strip().splitlines()[-1], log(root)
        c = calls(root)
        assert len(c) == 2 and c[1].startswith(f"roll|1|{root / 'srcp185'}|"), c
        assert f"/repo/runs/flash_chord/{RUN}/policy_{STEP}.safetensors /repo/runs/ep7/{RUN}/blowup_s{STEP}_w4096 --worlds 4096" in c[1], c[1]
        assert (root / f"runs/ep7/{RUN}/blowup_s{STEP}_w4096.npz").exists()
        assert not (root / f"runs/ep7/{RUN}/blowup_s{STEP}_w4096_hydra").exists()


def test_eval_fails() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d); setup(root)
        r = chain(root, FAKE_EVAL_RC="1")
        assert r.returncode == 0, r.stderr
        assert "EP7_EVAL_DONE（评测 失败；非有限世界 未知；取证 完成）" in log(root).strip().splitlines()[-1], log(root)
        assert (root / f"results/day2/eval_{RUN}_s{STEP}.txt.failed").exists()
    with tempfile.TemporaryDirectory() as d:
        root = Path(d); setup(root)
        r = chain(root, FAKE_EVAL_RC="1", FAKE_ROLL_RC="5")
        assert r.returncode == 0, r.stderr
        assert "EP7_EVAL_DONE（评测 失败；非有限世界 未知；取证 失败）" in log(root).strip().splitlines()[-1], log(root)


def test_refuse() -> None:
    def refused(prepare, **kw) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); setup(root, **kw.pop("setup_kw", {}))
            before = prepare(root) if prepare else None
            r = chain(root, **kw)
            assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
            assert not calls(root)
            if before is None:
                assert not (root / f"runs/logs/{NAME}.log").exists()
            else:
                assert log(root) == before

    def existing_log(root):
        (root / f"runs/logs/{NAME}.log").write_text("旧日志\n"); return "旧日志\n"

    def no_source(root):
        (root / "srcp185/SOURCE_V2D.txt").unlink()

    refused(existing_log)
    refused(None, setup_kw={"policy": None})
    refused(None, setup_kw={"policy": (1.0, float("nan"), 3.0)})
    refused(no_source)
    with tempfile.TemporaryDirectory() as d:  # 设了要等的日志却没给正则
        root = Path(d); setup(root); (root / "runs/logs/other.log").write_text("x\n")
        r = chain(root, V2D_WAIT_FOR_LOG="runs/logs/other.log")
        assert r.returncode == 2 and not calls(root), (r.returncode, r.stderr)


def test_wait() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d); setup(root)
        other = root / "runs/logs/diag2_mf.log"; other.write_text("=== 还在跑\n")

        def finish():
            time.sleep(2.5)
            with other.open("a") as f:
                f.write("=== 2026-10-03 05:10:00 CST DIAG2_DONE（完成 3、闸不过 0、对照不过 0、出错 0）\n")

        t = threading.Thread(target=finish); t.start()
        t0 = time.time()
        r = chain(root, V2D_WAIT_FOR_LOG="runs/logs/diag2_mf.log", V2D_WAIT_FOR_RE="DIAG2_(DONE|FAILED)")
        t.join()
        assert r.returncode == 0 and time.time() - t0 >= 2, (r.returncode, r.stderr)
        text = log(root)
        assert "DIAG2_" not in text and "诊断链结束" in text, text
        assert text.strip().splitlines()[-1].count("EP7_EVAL_DONE") == 1 and text.count("EP7_EVAL_DONE") == 1
    with tempfile.TemporaryDirectory() as d:
        root = Path(d); setup(root)
        r = chain(root, FAKE_GPU="busy", V2D_GPU_WAIT_S="2")
        assert r.returncode == 1 and not calls(root), (r.returncode, r.stderr)
        assert log(root).strip().splitlines()[-1].endswith("EP7_EVAL_FAILED"), log(root)


def test_dryrun() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d); setup(root)
        r = chain(root, V2D_EP7_EVAL_DRYRUN="1")
        assert r.returncode == 0 and "EP7_EVAL_DRYRUN_OK" in r.stdout, (r.returncode, r.stdout, r.stderr)
        assert not calls(root) and not (root / f"runs/logs/{NAME}.log").exists()


if __name__ == "__main__":
    for t in (test_clean, test_nonfinite, test_eval_fails, test_refuse, test_wait, test_dryrun):
        t(); print(f"ok {t.__name__}")
    print("ALL_OK")
