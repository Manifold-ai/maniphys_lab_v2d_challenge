"""核对 B.1 只读记录里的 parquet 与 A 段悬空复查读的是不是同一份文件（Mac 上跑，只用标准库）。
计划 agent-doc/plan-t3-v2-retarget18-2026-10-10.md（沿用 agent-doc/plan-t3-pilot-v2-2026-10-10.md 第 5 节：两段之间同组成员重写了文件就停）。
输入：
  <B.1 记录> tools/t3_episode_remote.sh 的输出：取“可读 … sha256 <64 位> data/chunk-000/episode_<N>.parquet”行；
  <A 段记录> stages/recovery/t3_float_facts.py 的输出：取 15 列的数据行，第 1 列是集号，第 15 列是 parquet sha256 前 12 位。
B.1 记录里的每一集都要在 A 段记录里，且 sha256 以 A 段的前 12 位开头。每集打一行，最后打 SHA_MATCH <n>/<n>，
否则打 SHA_MISMATCH 并退出码 1。A 段有、B.1 没有的集不管（A 段是 20 集，B.1 只核要拼的那几集）。
--inputs <Tier 2 记录>（只报，不影响退出码）：stages/recovery/tier2_inputs_md5.py 的输出。B.1 每集的“输入 mesh / ground_plane <md5> <相对路径>”行
（同组成员重建时用的网格与地面）逐个与官方 Tier 2 同一相对路径的 md5 比，打 INPUTS_SAME 或 INPUTS_DIFF（第二轮对 ep8、ep24 是手工比的）。
用法：python3 stages/recovery/t3_sha_match.py <B.1 记录> <A 段记录> [--inputs <Tier 2 记录>]
测试：stages/recovery/test_t3_sha_match.py。
"""
import argparse
import re
import sys
from pathlib import Path

B1 = re.compile(r"^可读 \d+ 字节 (\S+ \S+) sha256 ([0-9a-f]{64}) data/chunk-000/episode_(\d{6})\.parquet$")
EPISODE = re.compile(r"^## episode (\d+)$")
INPUT = re.compile(r"^输入 (mesh|ground_plane) (\S+) ((?:mesh|ground_plane)/\S+)$")
TIER2 = re.compile(r"^([0-9a-f]{32}) ((?:mesh|ground_plane|support_surface)/\S+)$")   # 同 tier3_expect.py


def b1_rows(path: Path) -> dict:
    out = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():   # record 的 command 行可能有坏的 UTF-8
        m = B1.match(line.strip())
        if m:
            ep = int(m.group(3))
            if ep in out:
                raise SystemExit(f"t3_sha_match: {path} 里 ep{ep} 出现两次")
            out[ep] = (m.group(2), m.group(1))
    if not out:
        raise SystemExit(f"t3_sha_match: {path} 里一行 parquet 的 sha256 也没取到")
    return out


def a_rows(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not any(x.startswith("T3_FLOAT_FACTS_DONE") for x in lines):
        raise SystemExit(f"t3_sha_match: {path} 没有结束标记 T3_FLOAT_FACTS_DONE")
    out = {}
    for x in lines:
        c = x.split("\t")
        if len(c) == 15 and c[0].isdigit() and re.fullmatch(r"[0-9a-f]{12}", c[14]):
            out[int(c[0])] = c[14]
    if not out:
        raise SystemExit(f"t3_sha_match: {path} 里一行数据也没取到")
    return out


def inputs(b1_path: Path, t2_path: Path) -> list:
    """[(集, 键, 相对路径, 重建输入的 md5, 官方 Tier 2 的 md5 或 None)]。"""
    t2 = {}
    for x in t2_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = TIER2.match(x.strip())
        if m:
            t2[m.group(2)] = m.group(1)
    if not t2:
        raise SystemExit(f"t3_sha_match: {t2_path} 里一行 md5 也没取到")
    out, ep = [], None
    for x in b1_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = EPISODE.match(x.strip())
        if m:
            ep = int(m.group(1))
            continue
        m = INPUT.match(x.strip())
        if m and ep is not None:
            out.append((ep, m.group(1), m.group(3), m.group(2), t2.get(m.group(3))))
    if not out:
        raise SystemExit(f"t3_sha_match: {b1_path} 里一行“输入”也没取到")
    return out


def main(argv=None) -> int:
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("b1", type=Path)
    ap_.add_argument("a_phase", type=Path)
    ap_.add_argument("--inputs", type=Path)
    a = ap_.parse_args(argv)
    b1, ap = b1_rows(a.b1), a_rows(a.a_phase)
    print(f"B.1 记录 {a.b1}；A 段记录 {a.a_phase}{f'；Tier 2 记录 {a.inputs}' if a.inputs else ''}")
    print("ep\tA段前12位\tB.1前12位\tB.1修改时间\t相同")
    bad = []
    for ep in sorted(b1):
        sha, mtime = b1[ep]
        want = ap.get(ep, "-")
        same = want != "-" and sha.startswith(want)
        if not same:
            bad.append(ep)
        print(f"{ep}\t{want}\t{sha[:12]}\t{mtime}\t{'yes' if same else 'NO'}")
    if a.inputs:
        rows = inputs(a.b1, a.inputs)
        print("## 重建用的输入与官方 Tier 2 文件（只报）")
        print("ep\t键\t相对路径\t重建输入md5\tTier2_md5\t相同")
        diff = []
        for ep, k, rel, got, want in rows:
            same = want is not None and got == want
            if not same:
                diff.append(f"ep{ep} {k}")
            print(f"{ep}\t{k}\t{rel}\t{got}\t{want or '-'}\t{'yes' if same else 'NO'}")
        print(f"INPUTS_SAME {len(rows)}/{len(rows)}" if not diff else f"INPUTS_DIFF {len(rows) - len(diff)}/{len(rows)}：{'，'.join(diff)}")
    if bad:
        print(f"SHA_MISMATCH {len(b1) - len(bad)}/{len(b1)}：ep{bad} 与 A 段记录不同或不在 A 段记录里")
        return 1
    print(f"SHA_MATCH {len(b1)}/{len(b1)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
