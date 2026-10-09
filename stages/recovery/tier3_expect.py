"""从两份只读核对记录生成拼 Tier 3 档目录时要比对的哈希表（Mac 上跑，只用标准库）。计划 agent-doc/plan-t3-pilot-2026-10-09.md 第 3 节（Fable 5.1 审查 M1）。

输入：
  <远端记录>    tools/t3_episode_remote.sh 的输出（results/ops/t3_episodes_ml40_*.txt）：取“可读 … sha256 <hex> <相对路径>”行，
                即同组成员产物里各集 parquet 与元数据的 sha256；
  <Tier 2 记录> results/ops/t3p_mf4090_inputs_*.txt：取“<md5> <相对路径>”行，即 mf4090 上官方 Tier 2 目录里网格、地面平面与支撑面的 md5。
输出（stdout，TSV，无表头）：相对路径、算法、哈希。data/、meta/ 下的是转来的产物（sha256），mesh/、ground_plane/、support_surface/ 下的是
Tier 2 目录里的文件（md5）。同一路径出现两次且哈希不同、或一行也没取到，就报错退出。
用法：python3 stages/recovery/tier3_expect.py <远端记录> <Tier 2 记录> > stages/recovery/expect/<标签>.tsv
测试：stages/recovery/test_tier3_expect.py。
"""
import re
import sys
from pathlib import Path

REMOTE = re.compile(r"^可读 .* sha256 ([0-9a-f]{64}) ((?:data|meta)/\S+)$")
TIER2 = re.compile(r"^([0-9a-f]{32}) ((?:mesh|ground_plane|support_surface)/\S+)$")


def collect(remote: Path, tier2: Path) -> dict:
    out = {}
    for path, pat, algo in ((remote, REMOTE, "sha256"), (tier2, TIER2, "md5")):
        n = 0
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():   # record 的 command 行里非 ASCII 参数被转义坏了，不是合法 UTF-8
            m = pat.match(line.strip())
            if not m:
                continue
            rel, h = m.group(2), m.group(1)
            if rel in out and out[rel] != (algo, h):
                raise SystemExit(f"tier3_expect: {rel} 出现两次且哈希不同")
            out[rel] = (algo, h)
            n += 1
        if n == 0:
            raise SystemExit(f"tier3_expect: {path} 里一行 {algo} 也没取到")
    return out


def main(argv=None) -> int:
    a = sys.argv[1:] if argv is None else argv
    if len(a) != 2:
        raise SystemExit("用法：tier3_expect.py <远端记录> <Tier 2 记录>")
    for rel, (algo, h) in sorted(collect(Path(a[0]), Path(a[1])).items()):
        print(f"{rel}\t{algo}\t{h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
