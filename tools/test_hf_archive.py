"""tools/hf_archive.py 里不连网的部分的行为测试：挑文件规则与删除（暂无契约 ID：运维工具）。只用标准库，Mac 与训练机都能跑。

在临时目录里造假的 runs/flash_chord：
  - smoke-a：有 DONE、两份 state → 两份都挑；删光后写 STATE_PRUNED（取最大的 policy 步数）
  - t1-b：有 DONE、三份 state，最大的一份 state 写坏了 → 留第二大的完整一份，其余两份挑（含写坏的那份）
  - t1-c：没有 DONE → 不挑
  - t2-ep0-x：有 DONE → 名字含 t2-，不挑
  - smoke-t2-ep0-x：有 DONE → 不挑
删除：核对或抽查没通过一个都不删；演习不删；--yes 先写 ARCHIVED.json 再删；本地文件被改过的跳过；
中途断了（文件已删、STATE_PRUNED 没写）重跑能补上 STATE_PRUNED；暂存目录的硬链接一起清掉。
用法：python3 tools/test_hf_archive.py
"""
import json
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parent / "hf_archive.py"


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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
    print("ALL_OK")
