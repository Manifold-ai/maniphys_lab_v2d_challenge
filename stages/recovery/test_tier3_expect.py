"""tier3_expect.py 的测试（守计划 agent-doc/plan-t3-pilot-2026-10-09.md 第 3 节、审查 M1；暂无契约 ID）。只用标准库。
  1. 从两份假记录取出 parquet / 元数据的 sha256 与网格 / 地面 / 支撑面的 md5，别的行（标题、元数据 JSON、“输入”行）不取
  2. 同一路径两个不同的哈希：报错
  3. 一份记录一行也取不到：报错
  （两份假记录的 Tier 2 那份头一行带坏的 UTF-8 字节，同 scripts/dev/record 记下的含中文参数的 command 行）
用法：python3 stages/recovery/test_tier3_expect.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
A64, B64 = "a" * 64, "b" * 64
REMOTE = f"""# command  : ssh ml40 bash -s -- 8
== host 2026-10-10 04:20:39 CST
## episode 8
可读 962684 字节 2026-10-09 14:36:25.401319 sha256 {A64} data/chunk-000/episode_000008.parquet
可读 629 字节 2026-10-09 14:36:25.401319313 sha256 {B64} meta/episode_000008.metadata.json
{{"episode_index": 8, "mesh": "mesh/chair/chair.glb"}}
输入 mesh 666b6366a803130fc20050249ad67fa2 mesh/chair/chair.glb
"""
TIER2 = """== VM 2026-10-10 04:20:25 CST 来历 d8b309e9d52c
666b6366a803130fc20050249ad67fa2 mesh/chair/chair.glb
9626590db5bd1dc3a8188ee4d0d03f11 ground_plane/s8.json
e7b1026ef52ee91c15c1fcd6d216c653 support_surface/s8_support.usda
## 支撑面形状
s8	empty	no	e7b1026ef52ee91c15c1fcd6d216c653
"""


def run(remote: str, tier2: str):
    with tempfile.TemporaryDirectory() as t:
        r, s = Path(t) / "r.txt", Path(t) / "s.txt"
        r.write_text(remote, encoding="utf-8")
        s.write_bytes(b"# command  : bash -c \xe6\x94\\225\n" + tier2.encode("utf-8"))   # 同真记录：头一行有坏的 UTF-8
        return subprocess.run([sys.executable, str(HERE / "tier3_expect.py"), str(r), str(s)], capture_output=True, text=True)


def test_collects_both():
    p = run(REMOTE, TIER2)
    assert p.returncode == 0, p.stderr
    assert p.stdout.splitlines() == [
        f"data/chunk-000/episode_000008.parquet\tsha256\t{A64}",
        "ground_plane/s8.json\tmd5\t9626590db5bd1dc3a8188ee4d0d03f11",
        "mesh/chair/chair.glb\tmd5\t666b6366a803130fc20050249ad67fa2",
        f"meta/episode_000008.metadata.json\tsha256\t{B64}",
        "support_surface/s8_support.usda\tmd5\te7b1026ef52ee91c15c1fcd6d216c653",
    ], p.stdout


def test_conflict_refuses():
    p = run(REMOTE, TIER2 + "00000000000000000000000000000000 mesh/chair/chair.glb\n")
    assert p.returncode != 0 and "哈希不同" in p.stderr + p.stdout, p.stdout + p.stderr


def test_empty_record_refuses():
    p = run(REMOTE, "== 空\n")
    assert p.returncode != 0 and "一行 md5 也没取到" in p.stderr + p.stdout, p.stdout + p.stderr


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
    print("ALL_OK")
