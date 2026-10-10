"""t3_sha_match.py 的测试（守计划 agent-doc/plan-t3-v2-retarget18-2026-10-10.md 第 4 节的 SHA 判据；暂无契约 ID）。只用标准库。
  1. B.1 的两集都与 A 段前 12 位相同：SHA_MATCH 2/2，退出码 0；元数据行、“输入”行与 A 段的其他集不影响
  2. 一集不同、一集不在 A 段记录里：SHA_MISMATCH，退出码 1
  3. A 段记录没有结束标记、B.1 记录一行也取不到：报错
用法：python3 stages/recovery/test_t3_sha_match.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
S0, S3 = "d317b3547639" + "0" * 52, "2bf3cc985770" + "1" * 52


def b1(*items) -> str:
    out = ["# command  : ssh ml40 bash -s -- 0 3", "== host 2026-10-11 04:02:01 CST", "## 目录 runs/tier3_cari4d_f830_floor"]
    for ep, sha in items:
        e = f"{ep:06d}"
        out += [f"## episode {ep}",
                f"可读 963451 字节 2026-10-10 12:05:36.075896 sha256 {sha} data/chunk-000/episode_{e}.parquet",
                f"可读 629 字节 2026-10-10 12:05:36.075896301 sha256 {'c' * 64} meta/episode_{e}.metadata.json",
                "输入 mesh 666b6366a803130fc20050249ad67fa2 mesh/x/x.glb"]
    return "\n".join(out) + "\n"


def a_phase(done: bool = True) -> str:
    head = "ep\t物体\t帧\t位移mm\tH_m\th_mm\t面高_m\t间隙mm\t间隙30mm\tZ_m\tX_m\tD_m\tL_m\tk\tparquet_sha256"
    rows = ["0\ttall_bar_stool\t5\t34.1\t1.386\t-9.3\t0.000\t-9.3\t-20.2\t2.54\t-0.32\t2.79\t1.103\t1.008\td317b3547639",
            "3\tcontigo_coffee_mug\t5\t26.0\t1.390\t+777.7\t0.777\t+0.4\t-5.8\t2.56\t+0.27\t2.62\t0.500\t0.999\t2bf3cc985770",
            "5\tbig_black_box\t5\t14.2\t1.383\t+4.2\t0.000\t+4.2\t-6.8\t2.53\t-0.34\t2.71\t0.905\t0.995\t5c508937b139"]
    return "\n".join([head, *rows, "OFFSET_GATE_PASS（地面上 14 集）", *(["T3_FLOAT_FACTS_DONE"] if done else [])]) + "\n"


def run(b1_text: str, a_text: str):
    with tempfile.TemporaryDirectory() as t:
        b, a = Path(t) / "b1.txt", Path(t) / "a.txt"
        b.write_bytes(b"# command  : bash -c \xe6\x94\\225\n" + b1_text.encode("utf-8"))   # 同真记录：头一行有坏的 UTF-8
        a.write_text(a_text, encoding="utf-8")
        return subprocess.run([sys.executable, str(HERE / "t3_sha_match.py"), str(b), str(a)], capture_output=True, text=True)


def test_match():
    p = run(b1((0, S0), (3, S3)), a_phase())
    assert p.returncode == 0, p.stdout + p.stderr
    assert p.stdout.splitlines()[-1] == "SHA_MATCH 2/2", p.stdout
    assert "0\td317b3547639\td317b3547639\t2026-10-10 12:05:36.075896\tyes" in p.stdout, p.stdout


def test_mismatch():
    p = run(b1((0, "f" * 64), (3, S3), (7, S0)), a_phase())
    assert p.returncode == 1, p.stdout + p.stderr
    assert p.stdout.splitlines()[-1].startswith("SHA_MISMATCH 1/3：ep[0, 7]"), p.stdout


def test_bad_inputs_refuse():
    p = run(b1((0, S0)), a_phase(done=False))
    assert p.returncode != 0 and "没有结束标记" in p.stderr, p.stdout + p.stderr
    p = run("== 空\n", a_phase())
    assert p.returncode != 0 and "一行 parquet 的 sha256 也没取到" in p.stderr, p.stdout + p.stderr


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
    print("ALL_OK")
