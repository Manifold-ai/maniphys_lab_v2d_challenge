"""核对 B.1 只读记录里的 parquet 与 A 段悬空复查读的是不是同一份文件（Mac 上跑，只用标准库）。
计划 agent-doc/plan-t3-v2-retarget18-2026-10-10.md（沿用 agent-doc/plan-t3-pilot-v2-2026-10-10.md 第 5 节：两段之间同组成员重写了文件就停）。
输入：
  <B.1 记录> tools/t3_episode_remote.sh 的输出：取“可读 … sha256 <64 位> data/chunk-000/episode_<N>.parquet”行；
  <A 段记录> stages/recovery/t3_float_facts.py 的输出：取 15 列的数据行，第 1 列是集号，第 15 列是 parquet sha256 前 12 位。
B.1 记录里的每一集都要在 A 段记录里，且 sha256 以 A 段的前 12 位开头。每集打一行，最后打 SHA_MATCH <n>/<n>，
否则打 SHA_MISMATCH 并退出码 1。A 段有、B.1 没有的集不管（A 段是 20 集，B.1 只核要拼的那几集）。
用法：python3 stages/recovery/t3_sha_match.py <B.1 记录> <A 段记录>
测试：stages/recovery/test_t3_sha_match.py。
"""
import re
import sys
from pathlib import Path

B1 = re.compile(r"^可读 \d+ 字节 (\S+ \S+) sha256 ([0-9a-f]{64}) data/chunk-000/episode_(\d{6})\.parquet$")


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


def main(argv=None) -> int:
    a = sys.argv[1:] if argv is None else argv
    if len(a) != 2:
        raise SystemExit("用法：t3_sha_match.py <B.1 记录> <A 段记录>")
    b1, ap = b1_rows(Path(a[0])), a_rows(Path(a[1]))
    print(f"B.1 记录 {a[0]}；A 段记录 {a[1]}")
    print("ep\tA段前12位\tB.1前12位\tB.1修改时间\t相同")
    bad = []
    for ep in sorted(b1):
        sha, mtime = b1[ep]
        want = ap.get(ep, "-")
        same = want != "-" and sha.startswith(want)
        if not same:
            bad.append(ep)
        print(f"{ep}\t{want}\t{sha[:12]}\t{mtime}\t{'yes' if same else 'NO'}")
    if bad:
        print(f"SHA_MISMATCH {len(b1) - len(bad)}/{len(b1)}：ep{bad} 与 A 段记录不同或不在 A 段记录里")
        return 1
    print(f"SHA_MATCH {len(b1)}/{len(b1)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
