"""fc_export.sh 的行为测试（暂无契约 ID：运行规范待成文）。只用标准库，Mac 与训练机都能跑。

临时目录里搭最小仓库：真的 fc_export.sh；假的 ckpt_nonfinite.py（按 FAKE_NF 打印“非有限 0 / 10”“非有限 3 / 10”或不完整那一行）、
eval_summary.py、scripts/dev/in-flash-chord（记下收到的命令，按 FAKE_EVAL 写出 JSON 与 parquet、报终止错误、报别的错误或退出码 0 却不写文件）；
PATH 前面放假的 flock 与 nvidia-smi（按 FAKE_GPU 报有没有进程）。
  1. 守卫开着、policy 有限：导出到 export_8c778f9/s<步数>_w1/episode_000006.{json,parquet}，命令与 kit 的 run_policy_evaluation.py 逐项同序；
  2. 规矩一：有 NONFINITE、policy 含非有限参数、扫描结果里没有这一步（不完整）都拒绝，退出码 12，不起容器；关掉守卫时照样导出；
  3. 规矩二的识别：评测器报 must disable task failure termination → 13；别的失败 → 3；退出码 0 却缺文件 → 3；
  4. V2D_FC_SRC 不是 8c778f9 副本 → 2；run 名档位与 run 记录里 parquet 的档位不一致 → 2；GPU 有别的进程 → 6；
  5. 已有完整结果不重复导出；V2D_EXPORT_TRAJ=0 时命令里没有 object_trajectories_output，只要 JSON；
  6. 同一个日志先有一次终止报错、再有一次别的失败：第二次判 3，不判 13（报错分类只看这一次追加的日志）；
  7. V2D_EXPORT_DRYRUN=1：守卫照常（含 NaN 的仍是 12），通过时只打印命令、退出码 0，不起容器、不写文件；
  8. 摘要脚本出错不改变导出的退出码；
  9. Tier 3 校正版（agent-doc/plan-t3-pilot-v2-2026-10-10.md）：parquet 在 runs/motion/tier3_v2/ 下时，v2d_meta.json 到 runs/motion_src/tier3_v2/
     找（tier3/ 下第一轮那份不读）；目录名大写、空后缀或 Tier 1、2 带后缀都拒绝，退出码 2。
用法：python3 stages/evaluate/test_fc_export.py
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN, STEP, SEQ = "t1-ep6-w2048-cap4m-mf4090", "349999104", "2026-06-01_11-26-44_monitor_rotate_05"
FAKE_NF = r'''import os, sys
mode = os.environ.get("FAKE_NF", "ok")
print(f"== {sys.argv[1]}（policy 35 份）")
if mode == "ok":
    print("  349,999,104 步：非有限 0 / 10（NaN 0，inf 0）"); print("  全部有限"); sys.exit(0)
if mode == "nan":
    print("  349,999,104 步：非有限 3 / 10（NaN 3，inf 0）"); sys.exit(1)
print("  349,999,104 步：不完整或还在写，跳过"); sys.exit(0)
'''
FAKE_IFC = r'''#!/usr/bin/env bash
echo "$*" >> "$FAKE_CALLS"
echo "in-flash-chord: /workspace ← ${V2D_FC_SRC}（flash_chord 8c778f905c（fake））" >&2
case "${FAKE_EVAL:-ok}" in
  term) echo "RuntimeError: evaluation must disable task failure termination before scoring the full reference" >&2; exit 1 ;;
  boom) echo "RuntimeError: something else" >&2; exit 1 ;;
  empty) exit 0 ;;
esac
for tok in $*; do
  case "$tok" in
    evaluation.metrics_output=*) f="${tok#evaluation.metrics_output=}"; f="$FAKE_ROOT/${f#/repo/}"; mkdir -p "$(dirname "$f")"; echo '{"world_count": 1}' > "$f" ;;
    evaluation.object_trajectories_output=*) f="${tok#evaluation.object_trajectories_output=}"; f="$FAKE_ROOT/${f#/repo/}"; mkdir -p "$(dirname "$f")"; echo PAR1 > "$f" ;;
  esac
done
'''
FAKE_GPU = '#!/usr/bin/env bash\n[ "${FAKE_GPU:-idle}" = busy ] && echo 4242\nexit 0\n'


def setup(root: Path) -> None:
    for d in ("stages/evaluate", "stages/policy", "scripts/dev", "bin", f"runs/flash_chord/{RUN}", f"runs/motion_src/tier1/{SEQ}", "fcsrc", "badsrc"):
        (root / d).mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "fc_export.sh", root / "stages/evaluate")
    (root / "stages/policy/ckpt_nonfinite.py").write_text(FAKE_NF)
    (root / "stages/policy/eval_summary.py").write_text("import os, sys\nprint('SUMMARY')\nsys.exit(int(os.environ.get('FAKE_SUMMARY_RC', '0')))\n")
    for name, text in (("scripts/dev/in-flash-chord", FAKE_IFC), ("bin/nvidia-smi", FAKE_GPU), ("bin/flock", "#!/usr/bin/env bash\nexit 0\n")):
        (root / name).write_text(text)
        (root / name).chmod(0o755)
    (root / "fcsrc/SOURCE_V2D.txt").write_text("flash_chord 8c778f905c（v0.4.0 33129dd + patch）\n")
    (root / "badsrc/SOURCE_V2D.txt").write_text("flash_chord v0.4.0（33129dd）+ #185\n")
    d = root / "runs/flash_chord" / RUN
    (d / f"policy_{STEP}.safetensors").write_bytes(b"x")
    parquet = f"/repo/runs/motion/tier1/whole_body/soma/sequence_id={SEQ}/robot_name=g1/data.parquet"
    (d / "run_record.jsonl").write_text(json.dumps({"event": "start", "parquet": parquet}) + "\n" + json.dumps({"event": "start", "parquet": "x"}) + "\n")
    (root / f"runs/motion_src/tier1/{SEQ}/v2d_meta.json").write_text(json.dumps({"tier": 1, "episode": 6, "sequence_id": SEQ}))


def run(root: Path, run_name: str = RUN, **env) -> tuple:
    calls = root / "calls.txt"
    if calls.exists():
        calls.unlink()
    e = dict(os.environ, PATH=f"{root / 'bin'}:{os.environ['PATH']}", FAKE_CALLS=str(calls), FAKE_ROOT=str(root),
             V2D_FC_SRC=str(root / "fcsrc"))
    e.update(env)
    r = subprocess.run(["bash", str(root / "stages/evaluate/fc_export.sh"), run_name, STEP], cwd=root, env=e,
                       capture_output=True, text=True, errors="replace", timeout=60)
    return r.returncode, r.stdout + r.stderr, calls.read_text() if calls.exists() else ""


def out(root: Path, w: str = "1") -> Path:
    return root / f"runs/flash_chord/{RUN}/export_8c778f9/s{STEP}_w{w}/episode_000006"


def test_export_matches_kit_runner() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t); setup(root)
        rc, text, calls = run(root)
        assert rc == 0 and out(root).with_suffix(".json").is_file() and out(root).with_suffix(".parquet").is_file(), (rc, text)
        toks = calls.split("python scripts/evaluate_policy.py ", 1)[1].split()
        keys = [x.split("=", 1)[0] for x in toks]
        assert keys == ["evaluation.checkpoint", "evaluation.world_count", "evaluation.reset_mode", "evaluation.metrics_output",
                        "evaluation.object_trajectories_output", "hydra.run.dir", "logging.mode"], keys
        assert f"evaluation.checkpoint=/repo/runs/flash_chord/{RUN}/policy_{STEP}.safetensors" in toks and "evaluation.world_count=1" in toks
        assert "evaluation.reset_mode=explicit" in toks and "logging.mode=disabled" in toks and calls.startswith("cd /workspace && "), calls
        assert "SUMMARY" in text and "in-flash-chord: /workspace ← " in text, text
        rc2, text2, calls2 = run(root)
        assert rc2 == 0 and not calls2 and "已有结果" in text2, (rc2, text2)


def test_rule1_guard() -> None:
    for how in ("NONFINITE", "nan", "partial"):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); setup(root)
            env = {}
            if how == "NONFINITE":
                (root / f"runs/flash_chord/{RUN}/NONFINITE").write_text("x")
            else:
                env["FAKE_NF"] = how
            rc, text, calls = run(root, **env)
            assert rc == 12 and not calls and "不导出" in text, (how, rc, text, calls)
            rc, text, calls = run(root, V2D_EXPORT_UNGUARDED="1", **env)
            assert rc == 0 and calls, (how, rc, text)


def test_rule2_and_failures() -> None:
    for mode, want in (("term", 13), ("boom", 3), ("empty", 3)):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); setup(root)
            rc, text, _ = run(root, FAKE_EVAL=mode)
            assert rc == want, (mode, rc, text)
            if mode == "term":
                assert "规矩二" in text, text


def test_refusals() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t); setup(root)
        rc, text, calls = run(root, V2D_FC_SRC=str(root / "badsrc"))
        assert rc == 2 and not calls and "8c778f9" in text, (rc, text)
        rc, text, calls = run(root, FAKE_GPU="busy")
        assert rc == 6 and not calls, (rc, text)
        t2 = "t2-ep6-w2048-cap4m-mf4090"
        shutil.copytree(root / f"runs/flash_chord/{RUN}", root / f"runs/flash_chord/{t2}")
        rc, text, calls = run(root, run_name=t2)
        assert rc == 2 and not calls and "档位" in text, (rc, text)
        rc, text, calls = run(root, run_name="smoke-t1-ep6-w2048-cap4m-mf4090")
        assert rc == 2 and not calls, (rc, text)


def test_traj_off() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t); setup(root)
        rc, text, calls = run(root, V2D_EXPORT_WORLDS="4096", V2D_EXPORT_TRAJ="0")
        assert rc == 0 and "object_trajectories_output" not in calls and "evaluation.world_count=4096" in calls, (rc, calls)
        assert out(root, "4096").with_suffix(".json").is_file() and not out(root, "4096").with_suffix(".parquet").exists()


def test_rerun_classification() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t); setup(root)
        rc1, _, _ = run(root, FAKE_EVAL="term")
        rc2, text2, _ = run(root, FAKE_EVAL="boom")
        assert (rc1, rc2) == (13, 3), (rc1, rc2, text2)


def test_dryrun() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t); setup(root)
        rc, text, calls = run(root, V2D_EXPORT_DRYRUN="1", FAKE_GPU="busy")
        assert rc == 0 and not calls and "DRYRUN" in text and "evaluation.world_count=1" in text, (rc, text, calls)
        assert not (root / f"runs/flash_chord/{RUN}/export_8c778f9").exists() and not (root / "runs/logs").exists()
        rc, text, calls = run(root, V2D_EXPORT_DRYRUN="1", FAKE_NF="nan")
        assert rc == 12 and not calls, (rc, text)


def test_summary_failure_keeps_exit_code() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t); setup(root)
        rc, text, _ = run(root, FAKE_SUMMARY_RC="1")
        assert rc == 0 and "摘要打印失败" in text, (rc, text)



def test_t3_set_dir() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t); setup(root)
        r3 = "t3-ep24-w2048-cap4m-r3a-v2-mf4090"
        d = root / "runs/flash_chord" / r3
        shutil.copytree(root / f"runs/flash_chord/{RUN}", d)
        pq3 = f"/repo/runs/motion/tier3_v2/whole_body/soma/sequence_id={SEQ}/robot_name=g1/data.parquet"
        (d / "run_record.jsonl").write_text(json.dumps({"event": "start", "parquet": pq3}) + "\n")
        for sub, ep in (("tier3_v2", 24), ("tier3", 99)):
            (root / f"runs/motion_src/{sub}/{SEQ}").mkdir(parents=True)
            (root / f"runs/motion_src/{sub}/{SEQ}/v2d_meta.json").write_text(json.dumps({"tier": 3, "episode": ep, "sequence_id": SEQ}))
        rc, text, calls = run(root, run_name=r3)
        assert rc == 0 and (d / f"export_8c778f9/s{STEP}_w1/episode_000024.json").is_file(), (rc, text)
        assert not (d / f"export_8c778f9/s{STEP}_w1/episode_000099.json").exists(), text
        for bad in ("tier3_V2", "tier3_", "tier2_v2"):
            (d / "run_record.jsonl").write_text(json.dumps({"event": "start", "parquet": pq3.replace("tier3_v2", bad)}) + "\n")
            rc, text, calls = run(root, run_name=r3)
            assert rc == 2 and not calls, (bad, rc, text)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
    print("ALL_OK")
