"""tools/hf_archive.py 里不连网的部分的行为测试：挑文件规则与删除（暂无契约 ID：运维工具）。只用标准库，Mac 与训练机都能跑。

在临时目录里造假的 runs/flash_chord：
  - smoke-a：有 DONE、两份 state → 两份都挑；删光后写 STATE_PRUNED（取最大的 policy 步数）
  - t1-b：有 DONE、三份 state，最大的一份 state 写坏了 → 留第二大的完整一份，其余两份挑（含写坏的那份）
  - t1-c：没有 DONE → 不挑
  - t2-ep0-x：有 DONE → 名字含 t2-，不挑
  - smoke-t2-ep0-x：有 DONE → 不挑
删除：核对或抽查没通过一个都不删；演习不删；--yes 先写 ARCHIVED.json 再删；本地文件被改过的跳过；
中途断了（文件已删、STATE_PRUNED 没写）重跑能补上 STATE_PRUNED；暂存目录的硬链接一起清掉。

policy 中间份（plan --kind policy，K=9），另造一套 runs/flash_chord 与 runs/exports/a.tsv：
  - t1-p：14 份 policy、步 14 有 state，导出表里有步 2 → 挑 1、3、4、5
  - t2-ep1-p：12 份 → 名字带 t2- 也算，挑 1、2、3
  - t1-q：12 份，最新一份写坏了 → 整个 run 不动
  - t1-r：没有 DONE → 不动；t1-s：正好 9 份 → 没得挑
  - t1-u：12 份，步 2 与步 12 有 state → 步 2 的 policy 留着，挑 1、3
  - smoke-v：11 份，STATE_PRUNED 记步 1 → 挑 2
删除：有训练链在跑一个都不删；按删除时的文件重算保护（计划之后新导出的步数跳过）；ARCHIVED.json 追加不覆盖；
最新一份 policy 在删除前坏了，整个 run 跳过；导出输入清单 stages/evaluate/exports/*.tsv 里的步数也受保护；
抽查 --per-run 每条 run 挑 1 个。
hf_archive_run.sh（只在 Linux 上测，用 GNU find）：runs/tools/ 下放桩工具（upload、verify、spotcheck 是假的，其余转给真工具），
PATH 前面放假 nvidia-smi。verify 步骤停在删除前、什么都不删；delete 步骤缺核对结果、有训练链、GPU 上有进程都停，
正常时先重新核对再删；删除时多删一个清单外的文件，全量比对要报 HF_ARCHIVE_FILES_CHECK_FAILED。
用法：python3 tools/test_hf_archive.py
"""
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parent / "hf_archive.py"
RUNNER = Path(__file__).resolve().parent / "hf_archive_run.sh"


def ckpt(p: Path, n: int = 4, broken: bool = False) -> None:
    data = b"\0" * (4 * n)
    head = json.dumps({"w": {"dtype": "F32", "shape": [n], "data_offsets": [0, len(data)]}}).encode()
    blob = struct.pack("<Q", len(head)) + head + data
    p.write_bytes(blob[:-3] if broken else blob)


def run(root: Path, *args: str, rc: int = 0) -> str:
    r = subprocess.run([sys.executable, str(TOOL), *args], cwd=root, capture_output=True, text=True, timeout=60)
    assert r.returncode == rc, (args, r.returncode, r.stdout, r.stderr)
    return r.stdout + r.stderr


def build(root: Path) -> None:
    R = root / "runs/flash_chord"
    for name, done, steps, broken_last in (("smoke-a", True, (10, 20), False), ("t1-b", True, (10, 20, 30), True),
                                           ("t1-c", False, (10, 20), False), ("t2-ep0-x", True, (10, 20), False),
                                           ("smoke-t2-ep0-x", True, (10,), False)):
        d = R / name
        d.mkdir(parents=True)
        if done:
            (d / "DONE").write_text("x\n")
        for i, s in enumerate(steps):
            last = i == len(steps) - 1
            ckpt(d / f"state_{s}.safetensors", n=8 + s, broken=broken_last and last)
            ckpt(d / f"policy_{s}.safetensors", n=2)


def verified_from_plan(root: Path, manifest: str, out: str) -> list:
    rows = json.loads((root / manifest).read_text())
    v = [{**r, "repo": "u/r", "path_in_repo": f"m/runs/flash_chord/{r['run']}/{r['file']}", "hub_size": r["size"],
          "hub_sha256": r["sha256"], "match": True} for r in rows]
    (root / out).write_text(json.dumps(v))
    return v


def test_plan_rules() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        build(root)
        run(root, "plan", "--out", "m.json")
        rows = json.loads((root / "m.json").read_text())
        got = sorted((r["run"], r["file"]) for r in rows)
        assert got == [("smoke-a", "state_10.safetensors"), ("smoke-a", "state_20.safetensors"),
                       ("t1-b", "state_10.safetensors"), ("t1-b", "state_30.safetensors")], got


def test_delete_gates_and_effects() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        build(root)
        run(root, "plan", "--out", "m.json")
        v = verified_from_plan(root, "m.json", "v.json")
        (root / "spot_bad.json").write_text(json.dumps({"ok": False, "checked": [{"path_in_repo": v[0]["path_in_repo"]}]}))
        (root / "spot.json").write_text(json.dumps({"ok": True, "checked": [{"path_in_repo": v[0]["path_in_repo"], "match": True}]}))
        assert "一个都不删" in run(root, "delete", "--verified", "v.json", "--spotcheck", "spot_bad.json", rc=1)
        bad = [dict(r, match=False) if i == 0 else r for i, r in enumerate(v)]
        (root / "v_bad.json").write_text(json.dumps(bad))
        assert "一个都不删" in run(root, "delete", "--verified", "v_bad.json", "--spotcheck", "spot.json", rc=1)
        out = run(root, "delete", "--verified", "v.json", "--spotcheck", "spot.json")  # 演习
        assert "演习" in out and (root / "runs/flash_chord/smoke-a/state_10.safetensors").exists(), out
        stage = root / "runs/hf_stage/m/runs/flash_chord/smoke-a"  # 假装上传时留下的硬链接
        stage.mkdir(parents=True)
        os.link(root / "runs/flash_chord/smoke-a/state_10.safetensors", stage / "state_10.safetensors")
        ckpt(root / "runs/flash_chord/t1-b/state_10.safetensors", n=99)  # 本地被改过：应跳过
        out = run(root, "delete", "--verified", "v.json", "--spotcheck", "spot.json", "--yes")
        R = root / "runs/flash_chord"
        assert not (R / "smoke-a/state_10.safetensors").exists() and not (R / "smoke-a/state_20.safetensors").exists(), out
        assert (R / "smoke-a/STATE_PRUNED").read_text().strip() == "20", out
        assert (R / "t1-b/state_10.safetensors").exists() and "不一样了" in out, out
        assert not (R / "t1-b/state_30.safetensors").exists() and (R / "t1-b/state_20.safetensors").exists(), out
        arch = json.loads((R / "smoke-a/ARCHIVED.json").read_text())
        assert {f["file"] for f in arch[0]["files"]} == {"state_10.safetensors", "state_20.safetensors"}, arch
        for name in ("t1-c", "t2-ep0-x", "smoke-t2-ep0-x"):
            assert len(list((R / name).glob("state_*"))) >= 1 and not (R / name / "ARCHIVED.json").exists(), name
        assert not (root / "runs/hf_stage").exists(), "暂存目录没清掉"


def test_rerun_after_interrupted_delete_writes_state_pruned() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        build(root)
        run(root, "plan", "--out", "m.json")
        verified_from_plan(root, "m.json", "v.json")
        v = json.loads((root / "v.json").read_text())
        (root / "spot.json").write_text(json.dumps({"ok": True, "checked": [{"path_in_repo": v[0]["path_in_repo"], "match": True}]}))
        R = root / "runs/flash_chord/smoke-a"
        for p in R.glob("state_*"):  # 模拟上一轮删完文件、还没写 STATE_PRUNED 就断了
            p.unlink()
        out = run(root, "delete", "--verified", "v.json", "--spotcheck", "spot.json", "--yes")
        assert (R / "STATE_PRUNED").read_text().strip() == "20", out


def build_policy(root: Path) -> None:
    R = root / "runs/flash_chord"

    def mk(name, done, pol_steps, state_steps=(), broken_last=False, state_pruned=None):
        d = R / name
        d.mkdir(parents=True)
        if done:
            (d / "DONE").write_text("x\n")
        pol_steps = list(pol_steps)
        for i, s in enumerate(pol_steps):
            ckpt(d / f"policy_{s}.safetensors", n=2 + s, broken=broken_last and i == len(pol_steps) - 1)
        for s in state_steps:
            ckpt(d / f"state_{s}.safetensors", n=8 + s)
        if state_pruned is not None:
            (d / "STATE_PRUNED").write_text(f"{state_pruned}\n")

    mk("t1-p", True, range(1, 15), state_steps=(14,))
    mk("t2-ep1-p", True, range(1, 13))
    mk("t1-q", True, range(1, 13), broken_last=True)
    mk("t1-r", False, range(1, 16))
    mk("t1-s", True, range(1, 10))
    mk("t1-u", True, range(1, 13), state_steps=(2, 12))
    mk("smoke-v", True, range(1, 12), state_pruned=1)
    E = root / "runs/exports"
    E.mkdir(parents=True)
    (E / "a.tsv").write_text("tier\tepisode\trun\tstep\tstatus\n1\t0\tt1-p\t2\tok\n1\t0\tt1-p\tnot-a-step\tok\n")


POLICY_PICK = {("t1-p", 1), ("t1-p", 3), ("t1-p", 4), ("t1-p", 5), ("t2-ep1-p", 1), ("t2-ep1-p", 2), ("t2-ep1-p", 3),
               ("t1-u", 1), ("t1-u", 3), ("smoke-v", 2)}


def spot_ok(root: Path, v: list, name: str = "spot.json") -> None:
    (root / name).write_text(json.dumps({"ok": True, "checked": [{"path_in_repo": v[0]["path_in_repo"], "match": True}]}))


def test_policy_plan_rules() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        build_policy(root)
        out = run(root, "plan", "--kind", "policy", "--out", "pm.json")
        rows = json.loads((root / "pm.json").read_text())
        assert {(r["run"], r["step"]) for r in rows} == POLICY_PICK, (rows, out)
        assert all(r["kind"] == "policy" and r["keep"] == 9 and r["file"] == f"policy_{r['step']}.safetensors" for r in rows), rows
        assert "t1-q" in out and "不完整" in out, out
        (root / "runs/.chain-active-x").write_text("")
        assert "训练链" in run(root, "plan", "--kind", "policy", "--out", "pm2.json", rc=1)


def test_policy_delete() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        build_policy(root)
        R = root / "runs/flash_chord"
        (R / "t1-p/ARCHIVED.json").write_text(json.dumps([{"time": "old", "files": [{"file": "state_0.safetensors"}]}]))
        run(root, "plan", "--kind", "policy", "--out", "pm.json")
        v = verified_from_plan(root, "pm.json", "v.json")
        spot_ok(root, v)
        (root / "runs/.chain-active-x").write_text("")
        assert "一个都不删" in run(root, "delete", "--verified", "v.json", "--spotcheck", "spot.json", "--yes", rc=1)
        assert (R / "t1-p/policy_1.safetensors").exists()
        (root / "runs/.chain-active-x").unlink()
        with (root / "runs/exports/a.tsv").open("a") as f:  # 计划之后又导出了步 3：删除时要跳过
            f.write("1\t0\tt1-p\t3\tok\n")
        ckpt(R / "t2-ep1-p/policy_1.safetensors", n=99)  # 本地被改过：跳过
        stage = root / "runs/hf_stage/m/runs/flash_chord/t1-u"
        stage.mkdir(parents=True)
        os.link(R / "t1-u/policy_1.safetensors", stage / "policy_1.safetensors")
        out = run(root, "delete", "--verified", "v.json", "--spotcheck", "spot.json", "--yes")
        left = {(d.name, int(p.stem.split("_")[1])) for d in R.iterdir() for p in d.glob("policy_*.safetensors")}
        deleted = {("t1-p", 1), ("t1-p", 4), ("t1-p", 5), ("t2-ep1-p", 2), ("t2-ep1-p", 3), ("t1-u", 1), ("t1-u", 3), ("smoke-v", 2)}
        assert not (deleted & left), (deleted & left, out)
        assert {("t1-p", 3), ("t1-p", 2), ("t2-ep1-p", 1), ("t1-u", 2), ("smoke-v", 1)} <= left, out
        assert "受保护" in out and "不一样了" in out, out
        for name, n in (("t1-p", 9), ("t2-ep1-p", 9), ("t1-u", 9), ("smoke-v", 9)):  # 最新 9 份都在
            steps = sorted(s for r, s in left if r == name)
            assert steps[-n:] == list(range(max(steps) - n + 1, max(steps) + 1)), (name, steps)
        arch = json.loads((R / "t1-p/ARCHIVED.json").read_text())
        assert len(arch) == 2 and arch[0]["time"] == "old", arch
        assert {f["file"] for f in arch[1]["files"]} == {"policy_1.safetensors", "policy_4.safetensors", "policy_5.safetensors"}, arch
        assert (R / "smoke-v/STATE_PRUNED").read_text().strip() == "1"
        assert not (R / "t1-p/STATE_PRUNED").exists()
        assert not (root / "runs/hf_stage").exists(), "暂存目录没清掉"


def test_policy_delete_skips_run_whose_newest_policy_broke() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        build_policy(root)
        R = root / "runs/flash_chord"
        run(root, "plan", "--kind", "policy", "--out", "pm.json")
        v = verified_from_plan(root, "pm.json", "v.json")
        spot_ok(root, v)
        ckpt(R / "t1-u/policy_12.safetensors", n=14, broken=True)
        out = run(root, "delete", "--verified", "v.json", "--spotcheck", "spot.json", "--yes")
        assert (R / "t1-u/policy_1.safetensors").exists() and (R / "t1-u/policy_3.safetensors").exists(), out
        assert "跳过 t1-u" in out and not (R / "t1-u/ARCHIVED.json").exists(), out


def test_export_input_lists_protect() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        build_policy(root)
        L = root / "stages/evaluate/exports"
        L.mkdir(parents=True)
        (L / "l.tsv").write_text("# 档位 episode run 步数\n1\t1\tt2-ep1-p\t3\n1\t1\tt2-ep1-p\tbad\n")
        run(root, "plan", "--kind", "policy", "--out", "pm.json")
        got = {(r["run"], r["step"]) for r in json.loads((root / "pm.json").read_text())}
        assert got == POLICY_PICK - {("t2-ep1-p", 3)}, got


def test_spot_pick() -> None:
    spec = importlib.util.spec_from_file_location("hf_archive_under_test", TOOL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    rows = [{"run": f"r{i % 3}", "file": f"f{i}"} for i in range(30)]
    per_run = m.spot_pick(rows, 5, True, 7)
    assert sorted(r["run"] for r in per_run) == ["r0", "r1", "r2"], per_run
    assert len(m.spot_pick(rows, 5, False, 7)) == 5 and len(m.spot_pick(rows, 99, False, 7)) == 30


STUB = """import os, shutil, subprocess, sys
REAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hf_archive_real.py")
cmd = sys.argv[1]
if cmd == "upload":
    sys.exit(0)
if cmd in ("verify", "spotcheck"):
    shutil.copy(os.environ["STUB_VERIFIED" if cmd == "verify" else "STUB_SPOT"], sys.argv[sys.argv.index("--out") + 1])
    sys.exit(0)
r = subprocess.run([sys.executable, REAL] + sys.argv[1:])
if cmd == "delete" and os.environ.get("STUB_EXTRA_DELETE"):
    os.unlink(os.environ["STUB_EXTRA_DELETE"])
sys.exit(r.returncode)
"""
RUNNER_ARGS = ["bash", str(RUNNER), "runs/pm.json", "u/r", "m", "runs/x"]


def runner_setup(root: Path) -> dict:
    build_policy(root)
    tools = root / "runs/tools"
    tools.mkdir(parents=True)
    shutil.copy(TOOL, tools / "hf_archive_real.py")
    (tools / "hf_archive.py").write_text(STUB)
    run(root, "plan", "--kind", "policy", "--out", "runs/pm.json")
    v = verified_from_plan(root, "runs/pm.json", "runs/stub_verified.json")
    spot_ok(root, v, "runs/stub_spot.json")
    b = root / "bin"
    b.mkdir()
    (b / "nvidia-smi").write_text('#!/bin/sh\nprintf "%s" "${STUB_GPU:-}"\n')
    (b / "nvidia-smi").chmod(0o755)
    return {**os.environ, "PATH": f"{b}:{os.environ['PATH']}", "STUB_VERIFIED": str(root / "runs/stub_verified.json"),
            "STUB_SPOT": str(root / "runs/stub_spot.json")}


def run_runner(root: Path, env: dict, steps: str, **extra) -> subprocess.CompletedProcess:
    return subprocess.run(RUNNER_ARGS, cwd=root, env={**env, "V2D_HF_ARCHIVE_STEPS": steps, **extra},
                          capture_output=True, text=True, timeout=120)


def n_policies(root: Path) -> int:
    return len(list((root / "runs/flash_chord").glob("*/policy_*.safetensors")))


def linux_only(name: str) -> bool:
    if sys.platform.startswith("linux"):
        return True
    print(f"跳过 {name}：要 GNU find（-printf），只在训练机上跑")
    return False


def test_runner_verify_step() -> None:
    if not linux_only("test_runner_verify_step"):
        return
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        env = runner_setup(root)
        before = n_policies(root)
        r = run_runner(root, env, "verify", V2D_HF_SPOTCHECK_PER_RUN="1")
        assert r.returncode == 0 and r.stdout.rstrip().endswith("HF_ARCHIVE_VERIFIED"), r.stdout + r.stderr
        assert "抽查 每条 run 1 个" in r.stdout and n_policies(root) == before, r.stdout
        assert (root / "runs/x.verified.json").exists() and (root / "runs/x.spotcheck.json").exists()
        assert run_runner(root, env, "nope").returncode == 2
        assert run_runner(root, env, "verify", V2D_HF_SPOTCHECK_PER_RUN="2").returncode == 2


def test_runner_delete_step() -> None:
    if not linux_only("test_runner_delete_step"):
        return
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        env = runner_setup(root)
        before = n_policies(root)
        r = run_runner(root, env, "delete")
        assert r.returncode == 1 and "HF_ARCHIVE_STOPPED delete（缺核对或抽查结果）" in r.stdout, r.stdout + r.stderr
        shutil.copy(root / "runs/stub_verified.json", root / "runs/x.verified.json")
        shutil.copy(root / "runs/stub_spot.json", root / "runs/x.spotcheck.json")
        (root / "runs/.chain-active-x").write_text("")
        r = run_runner(root, env, "delete")
        assert r.returncode == 1 and "HF_ARCHIVE_STOPPED delete（有训练链在跑）" in r.stdout, r.stdout + r.stderr
        (root / "runs/.chain-active-x").unlink()
        r = run_runner(root, env, "delete", STUB_GPU="4242")
        assert r.returncode == 1 and "GPU 上有进程：4242" in r.stdout and n_policies(root) == before, r.stdout + r.stderr
        r = run_runner(root, env, "delete")
        assert r.returncode == 0 and r.stdout.rstrip().endswith("HF_ARCHIVE_DONE"), r.stdout + r.stderr
        assert "清单外消失的文件：无" in r.stdout and "其中没删的 0 个" in r.stdout, r.stdout
        assert (root / "runs/x.reverified.json").exists() and n_policies(root) == before - len(POLICY_PICK), r.stdout


def test_runner_files_check_catches_extra_deletion() -> None:
    if not linux_only("test_runner_files_check_catches_extra_deletion"):
        return
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        env = runner_setup(root)
        shutil.copy(root / "runs/stub_verified.json", root / "runs/x.verified.json")
        shutil.copy(root / "runs/stub_spot.json", root / "runs/x.spotcheck.json")
        extra = root / "runs/flash_chord/t1-s/policy_1.safetensors"
        r = run_runner(root, env, "delete", STUB_EXTRA_DELETE=str(extra))
        assert r.returncode == 1 and r.stdout.rstrip().endswith("HF_ARCHIVE_FILES_CHECK_FAILED"), r.stdout + r.stderr
        assert "t1-s/policy_1.safetensors" in r.stdout, r.stdout


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
    print("ALL_OK")
