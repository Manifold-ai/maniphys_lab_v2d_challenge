"""stages/recovery/t3r_compare.py 的测试：守计划 agent-doc/plan-t3takeover-v3-2026-10-21.md 判据 K1 的两个比较器与门槛自检。"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t3r_compare import IGNORE_KEY, compare, self_test


def _args(**kw):
    a = argparse.Namespace(tol=1e-6, tol_rad=1e-6, subset=False, ignore_key=IGNORE_KEY, quat_col=["observation.object.pose"])
    for k, v in kw.items():
        setattr(a, k, v)
    return a


def _pose_table(pose: np.ndarray) -> pa.Table:
    return pa.table({"frame_index": list(range(len(pose))), "observation.object.pose": pose.tolist()})


def test_bytes_numbers_different_npz():
    """K1：npz 逐字节相同、数值在门槛内、超门槛三种结论。"""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        x = np.linspace(0, 1, 10)
        np.savez(p / "a.npz", x=x)
        np.savez(p / "b.npz", x=x)
        assert compare(p / "a.npz", p / "b.npz", _args())[0] == "BYTES_EQUAL"
        np.savez(p / "c.npz", x=x + 5e-7)
        assert compare(p / "a.npz", p / "c.npz", _args())[0] == "NUMBERS_EQUAL"
        np.savez(p / "e.npz", x=x + 3e-6)
        v, msg = compare(p / "a.npz", p / "e.npz", _args())
        assert v == "DIFFERENT" and "x" in msg, msg


def test_parquet_quaternion_sign_and_position():
    """K1：parquet 的物体位姿——四元数取反算相同，位置挪 2e-6 m 算不同；门槛自检三项都过。"""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        rng = np.random.default_rng(0)
        q = rng.normal(size=(20, 4))
        q /= np.linalg.norm(q, axis=1, keepdims=True)
        pose = np.concatenate([rng.normal(size=(20, 3)), q], axis=1)
        pq.write_table(_pose_table(pose), p / "a.parquet")
        flip = pose.copy()
        flip[:, 3:] *= -1
        pq.write_table(_pose_table(flip), p / "b.parquet")
        assert compare(p / "b.parquet", p / "a.parquet", _args())[0] == "NUMBERS_EQUAL"
        shift = pose.copy()
        shift[5, 1] += 2e-6
        pq.write_table(_pose_table(shift), p / "c.parquet")
        assert compare(p / "c.parquet", p / "a.parquet", _args())[0] == "DIFFERENT"
        assert self_test(p / "a.parquet", _args()) == []


def test_json_subset_and_ignored_keys():
    """K1：JSON 去掉路径、时间字段后按字段比；--subset 时参照多出来的集不算不同，我们这份里的值不同就算不同。"""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        ours = {"time": "now", "episodes": {"ep14": {"k": 1.0, "path": "/a"}}}
        ref = {"time": "then", "episodes": {"ep14": {"k": 1.0 + 1e-9, "path": "/b"}, "ep15": {"k": 2.0}}}
        (p / "o.json").write_text(json.dumps(ours))
        (p / "r.json").write_text(json.dumps(ref))
        assert compare(p / "o.json", p / "r.json", _args(subset=True))[0] == "NUMBERS_EQUAL"
        assert compare(p / "o.json", p / "r.json", _args(subset=False))[0] == "DIFFERENT"
        ours["episodes"]["ep14"]["k"] = 1.1
        (p / "o.json").write_text(json.dumps(ours))
        assert compare(p / "o.json", p / "r.json", _args(subset=True))[0] == "DIFFERENT"


def test_other_suffix_bytes_only():
    """K1：其余后缀（如 usda）只比字节。"""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "a.usda").write_text("x 1.0\n")
        (p / "b.usda").write_text("x 1.0\n")
        (p / "c.usda").write_text("x 1.00\n")
        assert compare(p / "a.usda", p / "b.usda", _args())[0] == "BYTES_EQUAL"
        assert compare(p / "a.usda", p / "c.usda", _args())[0] == "DIFFERENT"
