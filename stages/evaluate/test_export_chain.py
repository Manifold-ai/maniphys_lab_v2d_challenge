"""export_chain.sh（连同 check_export.sh、scripts/dev/record）的行为测试（暂无契约 ID：运行规范待成文）。只用标准库。

临时目录里搭最小仓库：真的 export_chain.sh、check_export.sh（经 V2D_COMPAT_PY_IMPORT 走宿主机）、scripts/dev/record；假的 fc_export.sh
（按 run 与步数的环境变量决定退出码，预检模式另有一套）、check_export.py、fc_src_check.py，PATH 前面放假的 nvidia-smi。计划第 3.2、3.6 节。
  1. 正常：两条导出、核对都过记 ok；没有 DONE 记 no_done；有 NONFINITE 记 nonfinite、不调 fc_export；结果表的 sha256 与文件一致；
  2. 规矩二：最终一步报 13，往前退时跳过 12、用第一份导出与核对都过的，补评 4096 世界 → fallback；补评失败 → fallback_noeval；
     一路 13 到上限 → fallback_failed，只试上限那么多份；往前退时遇到别的失败 → 停在这一条；
  3. 导出其他失败 → export_failed；核对不过 → check_failed，接着做下一行；
  4. 门槛不是“完成 1”、GPU 被占、没设 V2D_FC_SRC、副本核不过：EXPORT_CHAIN_FAILED，一行都不做；
  5. 旧日志或旧结果表已存在、清单没有行：退出码 2，不写日志；
  6. 设了 V2D_WAIT_FOR_EVAL_LOG：等那份日志结束才开始；本日志里不出现评测链结束标记的原文；
  7. 预检：不写日志、结果表与标记；没训完的行只提示；某行 fc_export 预检退出码非 0 时 EXPORT_DRYRUN_FAIL。
用法：python3 stages/evaluate/test_export_chain.py
"""
import hashlib
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STEP = "349999104"
A, B, C, D = (f"t1-ep{n}-w2048-cap4m-mf4090" for n in (3, 6, 8, 11))
FAKE_EXPORT = r'''#!/usr/bin/env bash
RUN=$1; STEP=$2; W=${V2D_EXPORT_WORLDS:-1}; TRAJ=${V2D_EXPORT_TRAJ:-1}; K="${RUN//-/_}"
if [ "${V2D_EXPORT_DRYRUN:-0}" = 1 ]; then key="FAKE_DRY_RC_$K"; rc="${!key:-0}"; echo "fc_export: DRYRUN $RUN policy_$STEP"; exit "$rc"; fi
echo "$RUN $STEP $W" >> runs/fake_calls.txt
key="FAKE_RC_${K}_${STEP}_w${W}"; rc="${!key:-}"
[ -n "$rc" ] || { key="FAKE_RC_${K}_${STEP}"; rc="${!key:-0}"; }
d="runs/flash_chord/$RUN/export_8c778f9/s${STEP}_w${W}"
if [ "$rc" = 0 ]; then
  mkdir -p "$d"; echo "{\"world_count\": $W, \"step\": $STEP}" > "$d/episode_000007.json"
  [ "$TRAJ" = 1 ] && echo "parquet $RUN $STEP" > "$d/episode_000007.parquet"
  echo "fake ok $RUN $STEP"
fi
[ "$rc" = 0 ] || echo "fake fail rc $rc" >&2
exit "$rc"
'''
FAKE_CHECK = r'''import os, sys
mode = os.environ.get("FAKE_CHECK_" + sys.argv[1].replace("-", "_") + "_" + sys.argv[2], "ok")
print("EXPORT_OK" if mode == "ok" else "EXPORT_FAIL 1"); sys.exit(0 if mode == "ok" else 1)
'''
FAKE_SRC = 'import os, sys\nrc = int(os.environ.get("FAKE_SRC_RC", "0")); print("FC_SRC_OK" if rc == 0 else "FC_SRC_FAIL 1"); sys.exit(rc)\n'
FAKE_GPU = '#!/usr/bin/env bash\n[ "${FAKE_GPU:-idle}" = busy ] && printf "4242\\n4343\\n"\nexit 0\n'
GATE_OK = "=== x DAY2_TRAIN_DONE（完成 1、失败 0、跳过 0、发散 0）\n"
TSV = f"# 注释行\n1\t3\t{A}\t{STEP}\n1\t6\t{B}\t{STEP}\n1\t8\t{C}\t{STEP}\n1\t11\t{D}\t{STEP}\n"


def setup(root: Path, tsv: str = TSV, done=(A, B), nonfinite=(), policies: dict = None) -> None:
    for d in ("stages/evaluate/exports", "stages/policy", "scripts/dev", "bin", "runs/logs", "third_party/patches"):
        (root / d).mkdir(parents=True, exist_ok=True)
    for f in ("stages/evaluate/export_chain.sh", "stages/evaluate/check_export.sh", "scripts/dev/record"):
        shutil.copy(REPO / f, root / f)
    files = {"stages/evaluate/fc_export.sh": FAKE_EXPORT, "stages/evaluate/check_export.py": FAKE_CHECK,
             "stages/policy/fc_src_check.py": FAKE_SRC, "bin/nvidia-smi": FAKE_GPU}
    for f, text in files.items():
        (root / f).write_text(text)
    for f in ("stages/evaluate/fc_export.sh", "bin/nvidia-smi", "stages/evaluate/export_chain.sh", "stages/evaluate/check_export.sh", "scripts/dev/record"):
        (root / f).chmod(0o755)
    (root / "stages/evaluate/exports/mf.tsv").write_text(tsv)
    (root / ".v2d-source-commit").write_text("deadbeef\n")
    (root / "third_party/patches/flash_chord-8c778f9.sha256").write_text("x  y\n")
    (root / "runs/logs/compat_mf.gate").write_text(GATE_OK)
    for run in done:
        (root / f"runs/flash_chord/{run}").mkdir(parents=True, exist_ok=True)
        (root / f"runs/flash_chord/{run}/DONE").write_text("")
    for run in nonfinite:
        (root / f"runs/flash_chord/{run}/NONFINITE").write_text("")
    for run, steps in (policies or {}).items():
        for s in steps:
            (root / f"runs/flash_chord/{run}/policy_{s}.safetensors").write_text("")


def env(root: Path, **kw) -> dict:
    e = dict(os.environ, PATH=f"{root / 'bin'}:{os.environ['PATH']}", V2D_FC_SRC="/x/fcsrc", V2D_POLL_S="1", V2D_COMPAT_PY_IMPORT="import json",
             V2D_REQUIRE_GATE="runs/logs/compat_mf.gate")
    e.update(kw)
    return {k: v for k, v in e.items() if v is not None}


def k(run: str, step: str = STEP, w: str = "") -> str:
    return f"FAKE_RC_{run.replace('-', '_')}_{step}" + (f"_w{w}" if w else "")


def chain(root: Path, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "stages/evaluate/export_chain.sh", "stages/evaluate/exports/mf.tsv", "export_mf"], cwd=root, env=env(root, **kw),
                          capture_output=True, text=True, errors="replace", timeout=120)


def table(root: Path) -> dict:
    lines = (root / "runs/exports/export_mf.tsv").read_text().splitlines()
    assert lines[0].split("\t")[:5] == ["tier", "episode", "run", "step", "status"], lines[0]
    return {f[2]: f for f in (line.split("\t") for line in lines[1:])}


def calls(root: Path) -> list:
    f = root / "runs/fake_calls.txt"
    return f.read_text().splitlines() if f.exists() else []


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_normal() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t); setup(root, done=(A, B, D), nonfinite=(D,))
        r = chain(root)
        log = (root / "runs/logs/export_mf.log").read_text()
        assert r.returncode == 0 and log.rstrip().endswith("EXPORT_CHAIN_DONE（成功 2、失败 2）"), log
        tb = table(root)
        assert [tb[x][4] for x in (A, B, C, D)] == ["ok", "ok", "no_done", "nonfinite"], tb
        j = root / tb[A][5]; q = root / tb[A][6]
        assert tb[A][5].endswith(f"s{STEP}_w1/episode_000007.json") and tb[A][7] == sha(j) and tb[A][8] == sha(q), tb[A]
        assert tb[C][5:] == ["", "", "", ""], tb[C]
        assert not any(D in c for c in calls(root)), calls(root)
        assert (root / f"results/submission/exports/export_mf_{A}_s{STEP}.txt").exists()
        assert (root / f"results/submission/exports/export_mf_{A}_s{STEP}_check.txt").exists()
        assert not (root / "runs/.chain-active-export_mf").exists()
        assert sum("EXPORT_CHAIN_" in line for line in log.splitlines()) == 1, log


def test_rule2_fallback() -> None:
    pol = {A: ("100", "200", "300", STEP)}
    with tempfile.TemporaryDirectory() as t:   # 13 → 300 非有限跳过 → 200 能用 → 补评成功
        root = Path(t); setup(root, policies=pol)
        r = chain(root, **{k(A): "13", k(A, "300"): "12"})
        tb = table(root)
        assert r.returncode == 0 and tb[A][3:5] == ["200", "fallback"] and tb[B][4] == "ok", tb
        assert calls(root)[:4] == [f"{A} {STEP} 1", f"{A} 300 1", f"{A} 200 1", f"{A} 200 4096"], calls(root)
        assert tb[A][5].endswith("s200_w1/episode_000007.json") and tb[A][8], tb[A]
        assert (root / f"results/submission/exports/export_mf_{A}_s200_w4096.txt").exists()
    with tempfile.TemporaryDirectory() as t:   # 补评失败 → fallback_noeval，仍算成功
        root = Path(t); setup(root, policies=pol)
        chain(root, **{k(A): "13", k(A, "300", "4096"): "3"})
        tb = table(root); log = (root / "runs/logs/export_mf.log").read_text()
        assert tb[A][3:5] == ["300", "fallback_noeval"] and "成功 2、失败 2" in log, (tb, log)
    with tempfile.TemporaryDirectory() as t:   # 一路 13，上限 2 份
        root = Path(t); setup(root, policies=pol)
        chain(root, V2D_FALLBACK_MAX="2", **{k(A): "13", k(A, "300"): "13", k(A, "200"): "13", k(A, "100"): "0"})
        tb = table(root)
        assert tb[A][3:5] == ["200", "fallback_failed"], tb
        assert [c for c in calls(root) if c.startswith(A)] == [f"{A} {STEP} 1", f"{A} 300 1", f"{A} 200 1"], calls(root)
    with tempfile.TemporaryDirectory() as t:   # 往前退时别的失败 → 停在这一条
        root = Path(t); setup(root, policies=pol)
        chain(root, **{k(A): "13", k(A, "300"): "3"})
        tb = table(root)
        assert tb[A][3:5] == ["300", "fallback_failed"] and tb[B][4] == "ok", tb
        assert [c for c in calls(root) if c.startswith(A)] == [f"{A} {STEP} 1", f"{A} 300 1"], calls(root)
    with tempfile.TemporaryDirectory() as t:   # 往前退时核对不过 → 停在这一条
        root = Path(t); setup(root, policies=pol)
        chain(root, **{k(A): "13", f"FAKE_CHECK_{A.replace('-', '_')}_300": "fail"})
        tb = table(root)
        assert tb[A][3:5] == ["300", "fallback_failed"], tb


def test_row_failures() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t); setup(root)
        r = chain(root, **{k(A): "3", f"FAKE_CHECK_{B.replace('-', '_')}_{STEP}": "fail"})
        tb = table(root); log = (root / "runs/logs/export_mf.log").read_text()
        assert r.returncode == 0 and tb[A][4] == "export_failed" and tb[B][4] == "check_failed", tb
        assert tb[B][7] and tb[B][8], tb[B]   # 核对不过的那份文件照样记 sha256，方便事后对照
        assert log.rstrip().endswith("EXPORT_CHAIN_DONE（成功 0、失败 4）"), log
    with tempfile.TemporaryDirectory() as t:   # 最终一步 12（非有限、读不了，但没有 NONFINITE）：不回退
        root = Path(t); setup(root, policies={A: ("300", STEP)})
        chain(root, **{k(A): "12"})
        assert table(root)[A][4] == "export_failed" and [c for c in calls(root) if c.startswith(A)] == [f"{A} {STEP} 1"]


def test_stops() -> None:
    for kw, word in (({"V2D_REQUIRE_GATE": "runs/logs/compat_bad.gate"}, "不是“完成 1”"), ({"FAKE_GPU": "busy"}, "4242,4343"),
                     ({"V2D_FC_SRC": None}, "没设 V2D_FC_SRC"), ({"FAKE_SRC_RC": "1"}, "不是核对过的 8c778f9 副本")):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); setup(root)
            (root / "runs/logs/compat_bad.gate").write_text("=== x DAY2_TRAIN_DONE（完成 0、失败 1、跳过 0、发散 0）\n")
            r = chain(root, **kw)
            log = (root / "runs/logs/export_mf.log").read_text()
            assert r.returncode == 1 and word in log and log.rstrip().endswith("EXPORT_CHAIN_FAILED"), (kw, log)
            assert calls(root) == [] and table(root) == {}, kw
            assert not (root / "runs/.chain-active-export_mf").exists()


def test_refusals() -> None:
    for pre in ("runs/logs/export_mf.log", "runs/exports/export_mf.tsv"):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); setup(root)
            (root / pre).parent.mkdir(parents=True, exist_ok=True); (root / pre).write_text("old\n")
            r = chain(root)
            assert r.returncode == 2 and (root / pre).read_text() == "old\n" and calls(root) == [], (pre, r.stderr)
    with tempfile.TemporaryDirectory() as t:
        root = Path(t); setup(root, tsv="# 只有注释\n\n")
        r = chain(root)
        assert r.returncode == 2 and not (root / "runs/logs/export_mf.log").exists(), r.stderr


def test_waits_for_previous_eval() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t); setup(root)
        prev = root / "runs/logs/box_eval_mf.log"
        prev.write_text("=== x 等 runs/logs/box_train_mf.log 的最后一行变成 DAY2_TRAIN_DONE / DAY2_TRAIN_FAILED\n")
        threading.Timer(3, lambda: prev.write_text("=== x DAY2_EVAL_DONE（成功 4、失败 0）\n")).start()
        t0 = time.time()
        r = chain(root, V2D_WAIT_FOR_EVAL_LOG="runs/logs/box_eval_mf.log")
        log = (root / "runs/logs/export_mf.log").read_text()
        assert r.returncode == 0 and time.time() - t0 >= 3 and "上一段评测链已结束：=== x 评测链完成（成功 4、失败 0）" in log, log
        assert "DAY2_EVAL_" not in log and "DAY2_TRAIN_" not in log, log


def test_dryrun() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t); setup(root, done=(A, B, D), nonfinite=(D,))
        (root / "runs/logs/compat_mf.gate").unlink()
        r = chain(root, V2D_EXPORT_CHAIN_DRYRUN="1")
        assert r.returncode == 0 and r.stdout.rstrip().endswith("EXPORT_DRYRUN_OK"), r.stdout
        assert "还没写，开跑时再看" in r.stdout and f"{C}：还没有 DONE" in r.stdout and f"{D}：有 NONFINITE" in r.stdout, r.stdout
        assert not (root / "runs/logs/export_mf.log").exists() and not (root / "runs/exports").exists() and calls(root) == []
        assert not (root / "runs/.chain-active-export_mf").exists()
        r = chain(root, V2D_EXPORT_CHAIN_DRYRUN="1", V2D_WAIT_FOR_EVAL_LOG="runs/logs/missing.log", **{f"FAKE_DRY_RC_{A.replace('-', '_')}": "12"})
        assert r.returncode == 1 and r.stdout.rstrip().endswith("EXPORT_DRYRUN_FAIL 2"), r.stdout


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"ok  {name}")
    print("ALL_OK")
