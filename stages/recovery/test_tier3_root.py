"""tier3_root.py 的测试（守计划 agent-doc/plan-t3-pilot-2026-10-09.md 第 3 节：拼 Tier 3 档目录，哈希逐个比对（审查 M1）、来源写进 provenance.json；
运行规范未成文，暂无契约 ID）。只用标准库。
临时目录里放假的转来产物（两集）、假的官方 Tier 2 目录，以及按真实文件算出的哈希表，跑脚本后核：
  1. 档目录的 parquet 与元数据行（按 episode_index 排）、网格 / 地面 / 支撑面按相对路径从 Tier 2 目录复制，内容相同；
     provenance.json 每集有部署版本与 parquet sha256；同样的输入再跑一次：跳过，不报错，元数据行不重复
  2. 哈希表里一项对不上（转来的 parquet 或 Tier 2 的网格）、或有没用上的行：拒绝，什么也不写
  3. 同一集换了 parquet 内容（哈希表也跟着换）再跑：拒绝，已有的文件不变
  4. 元数据里的相对路径带 ..：拒绝，什么也不写
  5. Tier 2 目录参数指到含 tier_1_multiview_caption 的目录：读文件就抛 Tier1AccessError（tier_guard 在进程里生效），什么也不写
用法：python3 stages/recovery/test_tier3_root.py
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMIT = "6820f709248c0bbd8147eb070f5d3933423bf965"


def row(ep, seq, obj, rel_mesh=None):
    return {"episode_index": ep, "frames": 700 + ep, "sequence_id": seq, "object": obj,
            "mesh": rel_mesh or f"mesh/{obj}/{obj}.glb", "ground_plane": f"ground_plane/{seq}.json",
            "support_surface": f"support_surface/{seq}_support.usda", "support_surface_frame": "g1_retarget_world"}


def h(path: Path, algo: str) -> str:
    return hashlib.new(algo, path.read_bytes()).hexdigest()


def setup(t: Path, bad_rel=False):
    inc, t2 = t / "incoming", t / "tier_2_synthetic_noise"
    lines = []
    for ep, seq, obj in ((8, "s8_chair", "chair"), (24, "s24_can", "can")):
        r = row(ep, seq, obj, "mesh/../../etc/passwd" if bad_rel and ep == 24 else None)
        (inc / "meta").mkdir(parents=True, exist_ok=True)
        (inc / "data" / "chunk-000").mkdir(parents=True, exist_ok=True)
        mf = inc / "meta" / f"episode_{ep:06d}.metadata.json"
        pf = inc / "data" / "chunk-000" / f"episode_{ep:06d}.parquet"
        mf.write_text(json.dumps(r))
        pf.write_bytes(f"pq{ep}".encode())
        lines += [f"meta/{mf.name}\tsha256\t{h(mf, 'sha256')}", f"data/chunk-000/{pf.name}\tsha256\t{h(pf, 'sha256')}"]
        for k, body in (("mesh", f"mesh-{obj}"), ("ground_plane", f"plane-{seq}"), ("support_surface", "empty")):
            if k == "mesh" and bad_rel and ep == 24:
                continue
            p = t2 / r[k]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body)
            lines.append(f"{r[k]}\tmd5\t{h(p, 'md5')}")
    (inc / "DEPLOYED").write_text(f"{COMMIT} dirty=0\n")
    exp = t / "expect.tsv"
    exp.write_text("\n".join(sorted(set(lines))) + "\n")
    return inc, t2, exp


def run(inc, root, t2, exp):
    return subprocess.run([sys.executable, str(HERE / "tier3_root.py"), str(inc), "--expect", str(exp), "--root", str(root), "--tier2", str(t2)],
                          capture_output=True, text=True)


def test_build_and_rerun():
    with tempfile.TemporaryDirectory() as d:
        t = Path(d)
        inc, t2, exp = setup(t)
        root = t / "root"
        r = run(inc, root, t2, exp)
        assert r.returncode == 0 and r.stdout.strip().endswith("TIER3_ROOT_OK"), r.stdout + r.stderr
        rows = [json.loads(x) for x in (root / "meta" / "episodes_metadata.jsonl").read_text().splitlines()]
        assert [x["episode_index"] for x in rows] == [8, 24], rows
        for x in rows:
            ep = x["episode_index"]
            assert (root / "data" / "chunk-000" / f"episode_{ep:06d}.parquet").read_bytes() == f"pq{ep}".encode()
            for k in ("mesh", "ground_plane", "support_surface"):
                assert (root / x[k]).read_text() == (t2 / x[k]).read_text(), (ep, k)
        assert r.stdout.count(" md5 ") == 6, r.stdout   # 两集各一份网格、地面、支撑面
        prov = json.loads((root / "meta" / "provenance.json").read_text())["episodes"]
        assert sorted(prov) == ["24", "8"] and prov["8"]["deployed_commit"] == COMMIT and prov["8"]["deployed_clean"] is True, prov
        assert prov["24"]["parquet_sha256"] == hashlib.sha256(b"pq24").hexdigest() and set(prov["8"]["tier2_md5"]) == {"mesh", "ground_plane", "support_surface"}
        r2 = run(inc, root, t2, exp)
        assert r2.returncode == 0 and "写 data" not in r2.stdout, r2.stdout + r2.stderr
        assert len((root / "meta" / "episodes_metadata.jsonl").read_text().splitlines()) == 2


def test_expect_mismatch_or_unused_refuses():
    for kind in ("parquet", "mesh", "unused"):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            inc, t2, exp = setup(t)
            text = exp.read_text()
            if kind == "parquet":
                text = text.replace(hashlib.sha256(b"pq8").hexdigest(), "0" * 64)
            elif kind == "mesh":
                (t2 / "mesh" / "can" / "can.glb").write_text("newer mesh")
            else:
                text += "mesh/other/other.glb\tmd5\t" + "1" * 32 + "\n"
            exp.write_text(text)
            r = run(inc, t / "root", t2, exp)
            msg = r.stdout + r.stderr
            assert r.returncode != 0 and ("哈希表里是" in msg or "没用上的行" in msg), (kind, msg)
            assert not (t / "root").exists(), kind


def test_changed_parquet_refuses():
    with tempfile.TemporaryDirectory() as d:
        t = Path(d)
        inc, t2, exp = setup(t)
        root = t / "root"
        assert run(inc, root, t2, exp).returncode == 0
        (inc / "data" / "chunk-000" / "episode_000008.parquet").write_bytes(b"changed")
        exp.write_text(exp.read_text().replace(hashlib.sha256(b"pq8").hexdigest(), hashlib.sha256(b"changed").hexdigest()))
        r = run(inc, root, t2, exp)
        assert r.returncode != 0 and "不覆盖" in r.stdout + r.stderr, r.stdout + r.stderr
        assert (root / "data" / "chunk-000" / "episode_000008.parquet").read_bytes() == b"pq8"


def test_unsafe_relative_path_refuses():
    with tempfile.TemporaryDirectory() as d:
        t = Path(d)
        inc, t2, exp = setup(t, bad_rel=True)
        root = t / "root"
        r = run(inc, root, t2, exp)
        assert r.returncode != 0 and "不安全" in r.stdout + r.stderr, r.stdout + r.stderr
        assert not root.exists()


def test_tier1_read_blocked():
    with tempfile.TemporaryDirectory() as d:
        t = Path(d)
        inc, t2, exp = setup(t)
        t1 = t / "tier_1_multiview_caption"
        t2.rename(t1)
        r = run(inc, t / "root", t1, exp)
        assert r.returncode != 0 and "Tier1AccessError" in r.stderr, r.stdout + r.stderr
        assert not (t / "root").exists()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
    print("ALL_OK")
