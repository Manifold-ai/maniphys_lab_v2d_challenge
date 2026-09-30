"""ckpt_nonfinite.py 的行为测试（暂无契约 ID：运行规范待成文）。只用标准库，Mac 与训练机都能跑。

在临时目录里造假的 runs/flash_chord/<run>/policy_<步数>.safetensors（F32），与一个只记录调用的假 stages/policy/fc_stop.sh：
  1. 有限、含 NaN、含 inf、写到一半（大小不对）四种文件的扫描结果；
  2. 看守：按步数连续 2 份非有限才调用 fc_stop；不连续（坏、好、坏）不调用，run 出现 DONE 后退出；
     已有 DONE 时即使连续 2 份非有限也不调用（DONE 优先）；
  3. --stop-at-step：写出到那一步就 fc_stop（截断），非有限止损在前时按非有限记。
用法：python3 stages/policy/test_ckpt_nonfinite.py
"""
import json
import os
import struct
import subprocess
import sys
import tempfile
import time
from array import array
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "ckpt_nonfinite.py"
OLD = time.time() - 60  # 早于脚本的 10 秒写入余量


def write_ckpt(path: Path, values: list[float], truncate: bool = False) -> None:
    data = array("f", values).tobytes()
    head = json.dumps({"w": {"dtype": "F32", "shape": [len(values)], "data_offsets": [0, len(data)]}}).encode()
    blob = struct.pack("<Q", len(head)) + head + data
    path.write_bytes(blob[:-4] if truncate else blob)
    os.utime(path, (OLD, OLD))


def setup(root: Path, run: str) -> Path:
    d = root / "runs/flash_chord" / run
    d.mkdir(parents=True)
    stop = root / "stages/policy/fc_stop.sh"
    stop.parent.mkdir(parents=True, exist_ok=True)
    stop.write_text('#!/usr/bin/env bash\necho "$1" >> fc_stop_calls.txt\ntouch "runs/flash_chord/$1/STOP"\n')
    stop.chmod(0o755)
    return d


def run(root: Path, *args: str) -> str:
    r = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=root, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_scan() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        d = setup(root, "r")
        write_ckpt(d / "policy_10.safetensors", [0.0, 1.5, -2.0])
        write_ckpt(d / "policy_20.safetensors", [0.0, float("nan"), float("nan")])
        write_ckpt(d / "policy_30.safetensors", [float("inf"), 1.0, 2.0])
        write_ckpt(d / "policy_40.safetensors", [1.0, 2.0, 3.0], truncate=True)
        out = run(root, "r")
        assert "10 步：非有限 0 / 3" in out, out
        assert "20 步：非有限 2 / 3（NaN 2，inf 0）" in out, out
        assert "30 步：非有限 1 / 3（NaN 0，inf 1）" in out, out
        assert "40 步：不完整或还在写，跳过" in out, out
        assert "第一份含非有限参数：20 步" in out, out
        last = run(root, "--last", "r")
        assert "30 步" in last and "40 步" not in last, last  # 最后一份不完整，退回 30


def test_watch_stops_on_two_consecutive() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        d = setup(root, "r")
        write_ckpt(d / "policy_10.safetensors", [1.0])
        write_ckpt(d / "policy_20.safetensors", [float("nan")])
        write_ckpt(d / "policy_30.safetensors", [float("nan")])
        out = run(root, "--watch", "r", "--interval", "1", "--timeout", "20")
        assert "NAN_WATCH_STOPPED" in out, out
        assert (root / "fc_stop_calls.txt").read_text().split() == ["r"]


def test_watch_ignores_non_consecutive() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        d = setup(root, "r")
        write_ckpt(d / "policy_10.safetensors", [float("nan")])
        write_ckpt(d / "policy_20.safetensors", [1.0])
        write_ckpt(d / "policy_30.safetensors", [float("nan")])
        (d / "DONE").touch()
        out = run(root, "--watch", "r", "--interval", "1", "--timeout", "20")
        assert "NAN_WATCH_DONE" in out, out
        assert not (root / "fc_stop_calls.txt").exists()


def test_watch_done_beats_stop() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        d = setup(root, "r")
        write_ckpt(d / "policy_10.safetensors", [float("nan")])
        write_ckpt(d / "policy_20.safetensors", [float("nan")])
        (d / "DONE").touch()
        out = run(root, "--watch", "r", "--interval", "1", "--timeout", "20", "--tag", "commit abc123")
        assert "NAN_WATCH_DONE" in out and "commit abc123" in out, out
        assert not (root / "fc_stop_calls.txt").exists()


def test_watch_stop_at_step() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        d = setup(root, "r")
        write_ckpt(d / "policy_10.safetensors", [1.0])
        write_ckpt(d / "policy_20.safetensors", [2.0])
        out = run(root, "--watch", "r", "--interval", "1", "--timeout", "20", "--stop-at-step", "20")
        assert "NAN_WATCH_TRUNCATED" in out, out
        assert (root / "fc_stop_calls.txt").read_text().split() == ["r"]


def test_watch_nan_beats_stop_at_step() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        d = setup(root, "r")
        write_ckpt(d / "policy_10.safetensors", [float("nan")])
        write_ckpt(d / "policy_20.safetensors", [float("nan")])
        out = run(root, "--watch", "r", "--interval", "1", "--timeout", "20", "--stop-at-step", "20")
        assert "NAN_WATCH_STOPPED" in out and "NAN_WATCH_TRUNCATED" not in out, out


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
    print("ALL_OK")
