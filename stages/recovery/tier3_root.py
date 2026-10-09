"""从转来的 Tier 3 重建产物拼出档目录（计划 agent-doc/plan-t3-pilot-2026-10-09.md 第 3 节）。只用标准库。

输入 <incoming>：stages/recovery/tier3_pack_remote.sh 打的 tar 解开后的目录，有 data/chunk-000/episode_<N>.parquet、
meta/episode_<N>.metadata.json（同组成员的转换脚本每集写一份，字段与 Tier 2 的 episodes_metadata.jsonl 一行相同）与 DEPLOYED。
输出 <root>（默认 libs/v2d_infra/paths.py 的 TIER3，即 runs/tier3/root）：
  data/chunk-000/episode_<N>.parquet、meta/episodes_metadata.jsonl（每集一行，按 episode_index 排），
  以及每行 mesh、ground_plane、support_surface 指向的文件：从官方 Tier 2 目录（--tier2）按同一相对路径复制。
  规则解读未确认：Tier 3 用 Tier 2 目录里的官方网格、地面平面与支撑面（同组成员的重建也用了前两者），正式做 Tier 3 前要问组委会。
每个写入的文件打一行 sha256（网格、地面与支撑面另打 md5，便于和 results/ops/t3p_mf4090_inputs_1009.txt 比）。
同一集已在 root 里：parquet 与元数据都相同就跳过；任何一项不同就拒绝（退出码 1，先核完再写，不同时什么也不写）。
相对路径必须留在各自目录里（不许绝对路径与 ..）。开头调 tier_guard.forbid_tier1()：本进程读不到 Tier 1 的任何文件。
用法（仓库根）：python3 stages/recovery/tier3_root.py <incoming> [--root <输出>] [--tier2 <官方 Tier 2 目录>]
测试：stages/recovery/test_tier3_root.py。
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "libs" / "v2d_infra"))
from paths import TIER2, TIER3  # noqa: E402
from tier_guard import forbid_tier1  # noqa: E402

LINKED = ("mesh", "ground_plane", "support_surface")


def digest(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def safe_rel(rel: str) -> PurePosixPath:
    p = PurePosixPath(rel)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise SystemExit(f"tier3_root: 元数据里的相对路径不安全：{rel}")
    return p


def plan(incoming: Path, root: Path, tier2: Path) -> tuple:
    """核对并列出要写的文件（源 → 目标）与 metadata 行；不写任何东西。"""
    metas = sorted((incoming / "meta").glob("episode_*.metadata.json"))
    if not metas:
        raise SystemExit(f"tier3_root: {incoming}/meta 下没有 episode_*.metadata.json")
    old_rows = {}
    jl = root / "meta" / "episodes_metadata.jsonl"
    if jl.exists():
        for line in jl.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                old_rows[int(r["episode_index"])] = r
    copies, rows = [], dict(old_rows)
    for m in metas:
        row = json.loads(m.read_text())
        ep = int(row["episode_index"])
        if m.name != f"episode_{ep:06d}.metadata.json":
            raise SystemExit(f"tier3_root: {m.name} 里的 episode_index 是 {ep}")
        src_pq = incoming / "data" / "chunk-000" / f"episode_{ep:06d}.parquet"
        if not src_pq.is_file():
            raise SystemExit(f"tier3_root: 缺 {src_pq}")
        dst_pq = root / "data" / "chunk-000" / src_pq.name
        if ep in old_rows:
            if old_rows[ep] != row or not dst_pq.is_file() or digest(dst_pq, "sha256") != digest(src_pq, "sha256"):
                raise SystemExit(f"tier3_root: ep{ep} 已在 {root} 里，且元数据或 parquet 与这次的不同；不覆盖")
            continue
        copies.append((src_pq, dst_pq))
        for k in LINKED:
            rel = safe_rel(row[k])
            src = tier2 / rel
            if not src.is_file():
                raise SystemExit(f"tier3_root: ep{ep} 的 {k} 在官方 Tier 2 目录里没有：{src}")
            dst = root / rel
            if dst.exists() and digest(dst, "sha256") != digest(src, "sha256"):
                raise SystemExit(f"tier3_root: {dst} 已存在且与官方文件不同")
            copies.append((src, dst))
        rows[ep] = row
    return copies, rows


def main(argv=None) -> int:
    forbid_tier1()
    ap = argparse.ArgumentParser()
    ap.add_argument("incoming", type=Path)
    ap.add_argument("--root", type=Path, default=TIER3)
    ap.add_argument("--tier2", type=Path, default=TIER2)
    a = ap.parse_args(argv)
    copies, rows = plan(a.incoming, a.root, a.tier2)
    for src, dst in copies:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copyfile(src, dst)
        rel = dst.relative_to(a.root)
        md5 = f" md5 {digest(dst, 'md5')}" if rel.parts[0] in LINKED else ""
        print(f"写 {rel} sha256 {digest(dst, 'sha256')}{md5}")
    jl = a.root / "meta" / "episodes_metadata.jsonl"
    jl.parent.mkdir(parents=True, exist_ok=True)
    jl.write_text("".join(json.dumps(rows[ep], ensure_ascii=False) + "\n" for ep in sorted(rows)))
    print(f"写 meta/episodes_metadata.jsonl（{len(rows)} 行：{', '.join(f'ep{e}' for e in sorted(rows))}）")
    print("TIER3_ROOT_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
