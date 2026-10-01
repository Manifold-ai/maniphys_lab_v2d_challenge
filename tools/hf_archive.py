"""把训练机上已经用不上的 state 文件归档到 Hugging Face 私有仓库，核对无误后再删本地（训练机上、仓库根执行）。
计划 agent-doc/plan-hf-archive-2026-10-01.md（第 2 版，按 Fable 5.1 审查修改）。

五个子命令，各自独立、各自落盘，任何一步没过就停在那一步：
  plan      --out <清单.json>     按规则挑文件，记下每个文件的大小与 sha256（只读）。
  upload    --manifest <清单> --repo <用户/仓库> --prefix <机器名>
                                  建私有仓库（已有就复用，必须是私有），把清单里的文件硬链接进暂存目录 runs/hf_stage/<机器名>/，
                                  再用 upload_large_folder 上传（可断点续传，2 个并发）。
  verify    --manifest <清单> --repo <用户/仓库> --prefix <机器名> --out <核对.json>
                                  列出仓库里的文件，逐个比大小与 LFS sha256；全部对上才退出码 0。这个 sha256 是上传时客户端算的，
                                  只能证明“仓库里有个标着这个哈希的对象”，所以删除前还要 spotcheck。
  spotcheck --verified <核对.json> --n 3 --out <抽查.json>
                                  随机挑 n 个文件从仓库下载回来，本地重算 sha256 与清单比，比完删掉下载的副本；全部一致才退出码 0。
  delete    --verified <核对.json> --spotcheck <抽查.json> [--yes]
                                  核对与抽查都通过才删；删之前逐个重新核对：run 目录还有 DONE、本地大小与 sha256 没变、
                                  不是正式 run 步数最大的那份完整 state。每个 run 先写 ARCHIVED.json（归档了什么、在仓库哪里）再删；
                                  冒烟目录的 state 空了就写 STATE_PRUNED（同训练链的约定），不依赖这一轮有没有删到东西，中途断了重跑能补上。
                                  最后清掉暂存目录的硬链接，空间才真正释放。不加 --yes 只打印将删什么。

挑文件的规则（plan）：只看 runs/flash_chord 下有 DONE 的 run，跳过名字里有 t2- 的（Tier 2 第 1 批正在用）。
  - 冒烟（smoke- 或 smoke_ 开头）：全部 state_*.safetensors；
  - 其他：除“步数最大、state 与同步数 policy 都完整”的那份以外的 state_*.safetensors；找不到完整的一份，整个 run 不动。
  policy_*.safetensors、日志、评测结果一律不动。
凭据只经环境变量传进来（HF_TOKEN、https_proxy），不落命令行、不写日志；HF_ENDPOINT 必须没设或等于 https://huggingface.co
（服务器 .env 把它指向下载镜像，带 token 的请求不能经第三方转发）。只用标准库加 huggingface_hub。
"""
import argparse
import hashlib
import json
import os
import random
import re
import struct
import sys
import time
from pathlib import Path

RUNS = Path("runs/flash_chord")
STAGE = Path("runs/hf_stage")
STATE = re.compile(r"state_(\d+)\.safetensors")
POLICY = re.compile(r"policy_(\d+)\.safetensors")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def complete(p: Path) -> bool:
    """safetensors 文件头能解析、大小等于头里声明的数据末尾（同 stages/policy/ckpt_latest.py）。"""
    try:
        size = p.stat().st_size
        with p.open("rb") as f:
            raw = f.read(8)
            if len(raw) != 8:
                return False
            (n,) = struct.unpack("<Q", raw)
            if n <= 0 or 8 + n > size:
                return False
            header = json.loads(f.read(n))
        end = max((v["data_offsets"][1] for k, v in header.items() if k != "__metadata__"), default=0)
        return size == 8 + n + end
    except (OSError, ValueError, KeyError, TypeError):
        return False


def states(d: Path) -> list:
    out = []
    for p in d.glob("state_*.safetensors"):
        m = STATE.fullmatch(p.name)
        if m:
            out.append((int(m.group(1)), p))
    return sorted(out)


def is_smoke(run: str) -> bool:
    return run.startswith("smoke-") or run.startswith("smoke_")


def keep_state(d: Path, run: str):
    """正式 run 留下的那份：步数最大、且 state 与同步数的 policy 都完整；冒烟不留（None）。找不到完整的返回 "__none__"。"""
    if is_smoke(run):
        return None
    for step, p in reversed(states(d)):
        if complete(p) and complete(d / f"policy_{step}.safetensors"):
            return p.name
    return "__none__"


def candidates() -> list:
    rows = []
    for d in sorted(p for p in RUNS.iterdir() if p.is_dir()):
        run = d.name
        if "t2-" in run or not (d / "DONE").exists():
            continue
        st = states(d)
        if not st:
            continue
        keep = keep_state(d, run)
        if keep == "__none__":
            print(f"跳过 {run}：找不到完整的最终 state，整个 run 不动")
            continue
        for step, p in st:
            if p.name == keep:
                continue
            rows.append({"run": run, "kind": "smoke" if is_smoke(run) else "formal", "file": p.name, "step": step,
                         "size": p.stat().st_size, "sha256": sha256(p)})
    return rows


def cmd_plan(a) -> int:
    rows = candidates()
    Path(a.out).write_text(json.dumps(rows, indent=1) + "\n")
    total = sum(r["size"] for r in rows)
    runs = sorted({r["run"] for r in rows})
    print(f"候选 {len(rows)} 个文件，{len(runs)} 个 run，共 {total / 1e9:.2f} GB（冒烟 "
          f"{sum(r['size'] for r in rows if r['kind'] == 'smoke') / 1e9:.2f} GB，正式 run 的旧 state "
          f"{sum(r['size'] for r in rows if r['kind'] == 'formal') / 1e9:.2f} GB）")
    for r in rows:
        print(f"  {r['kind']:<6} {r['run']}/{r['file']}  {r['size']}  {r['sha256'][:16]}…")
    print(f"清单写到 {a.out}")
    return 0


def repo_path(prefix: str, r: dict) -> str:
    return f"{prefix}/runs/flash_chord/{r['run']}/{r['file']}"


def need_env() -> None:
    for k in ("HF_TOKEN", "https_proxy"):
        if not os.environ.get(k):
            sys.exit(f"缺环境变量 {k}（经 stdin 注入，不要写在命令行上）")
    ep = os.environ.get("HF_ENDPOINT", "")
    if ep and ep.rstrip("/") != "https://huggingface.co":
        sys.exit("HF_ENDPOINT 不是 https://huggingface.co（服务器 .env 把它指向下载镜像），带 token 的请求不能经它转发，停下")


def cmd_upload(a) -> int:
    need_env()
    from huggingface_hub import HfApi
    rows = json.loads(Path(a.manifest).read_text())
    stage = STAGE / a.prefix
    for r in rows:
        src = RUNS / r["run"] / r["file"]
        dst = stage / repo_path(a.prefix, r).split("/", 1)[1]
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            os.link(src, dst)  # 硬链接，不多占盘
    api = HfApi()
    api.create_repo(a.repo, repo_type="model", private=True, exist_ok=True)
    if not api.repo_info(a.repo, repo_type="model").private:
        sys.exit(f"{a.repo} 不是私有仓库，停下")
    t0 = time.time()
    print(f"{time.strftime('%F %T')} 开始上传 {len(rows)} 个文件到私有仓库 {a.repo}（{sum(r['size'] for r in rows) / 1e9:.2f} GB）", flush=True)
    api.upload_large_folder(repo_id=a.repo, folder_path=str(STAGE), repo_type="model",
                            allow_patterns=[f"{a.prefix}/**"], private=True, num_workers=2)  # 训练机上只占 2 个并发
    print(f"{time.strftime('%F %T')} 上传结束，用时 {(time.time() - t0) / 60:.1f} 分钟；HF_UPLOAD_DONE", flush=True)
    return 0


def cmd_verify(a) -> int:
    need_env()
    from huggingface_hub import HfApi
    rows = json.loads(Path(a.manifest).read_text())
    hub = {}
    for f in HfApi().list_repo_tree(a.repo, repo_type="model", path_in_repo=a.prefix, recursive=True, expand=True):
        lfs = getattr(f, "lfs", None)
        if lfs is not None:
            hub[f.path] = (f.size, getattr(lfs, "sha256", None))
    out, bad = [], 0
    for r in rows:
        path = repo_path(a.prefix, r)
        size, sha = hub.get(path, (None, None))
        ok = size == r["size"] and sha == r["sha256"]
        bad += not ok
        out.append({**r, "repo": a.repo, "path_in_repo": path, "hub_size": size, "hub_sha256": sha, "match": ok})
        print(f"  {'ok ' if ok else 'BAD'} {path}  本地 {r['size']} / {r['sha256'][:12]}…  仓库 {size} / {(sha or '无')[:12]}…")
    Path(a.out).write_text(json.dumps(out, indent=1) + "\n")
    print(f"{len(rows) - bad} / {len(rows)} 个文件核对一致；" + ("HF_VERIFY_OK" if not bad else f"HF_VERIFY_FAIL {bad}"))
    return 0 if not bad else 1


def rmtree(root: Path) -> None:
    for p in sorted(root.rglob("*"), reverse=True):
        if p.is_file() or p.is_symlink():
            p.unlink()
        elif p.is_dir():
            p.rmdir()
    root.rmdir()


def cmd_spotcheck(a) -> int:
    need_env()
    from huggingface_hub import hf_hub_download
    rows = json.loads(Path(a.verified).read_text())
    if not all(r["match"] for r in rows):
        sys.exit("核对结果里有没对上的文件，不抽查")
    seed = int(time.time())
    pick = random.Random(seed).sample(rows, min(a.n, len(rows)))
    tmp = Path("runs/hf_spotcheck")
    tmp.mkdir(parents=True, exist_ok=True)
    out, bad = [], 0
    for r in pick:
        local = Path(hf_hub_download(r["repo"], r["path_in_repo"], repo_type="model", local_dir=str(tmp)))
        got = sha256(local)
        size = local.stat().st_size
        ok = got == r["sha256"] and size == r["size"]
        bad += not ok
        out.append({"path_in_repo": r["path_in_repo"], "size": size, "sha256": got, "expected": r["sha256"], "match": ok})
        print(f"  {'ok ' if ok else 'BAD'} {r['path_in_repo']}  下载后 sha256 {got[:16]}…，清单 {r['sha256'][:16]}…", flush=True)
        local.unlink()
    rmtree(tmp)  # 下载的副本与 local_dir 里的缓存都删掉
    Path(a.out).write_text(json.dumps({"seed": seed, "checked": out, "ok": not bad}, indent=1) + "\n")
    print(f"抽查 {len(out)} 个，{len(out) - bad} 个一致（随机种子 {seed}）；" + ("HF_SPOTCHECK_OK" if not bad else f"HF_SPOTCHECK_FAIL {bad}"))
    return 0 if not bad else 1


def cmd_delete(a) -> int:
    rows = json.loads(Path(a.verified).read_text())
    if not all(r["match"] for r in rows):
        sys.exit("核对结果里有没对上的文件，一个都不删")
    spot = json.loads(Path(a.spotcheck).read_text())
    verified_paths = {r["path_in_repo"] for r in rows}
    if not spot.get("ok") or not spot.get("checked") or not all(c["path_in_repo"] in verified_paths for c in spot["checked"]):
        sys.exit("抽查没通过（或抽查的文件不在核对清单里），一个都不删")
    by_run = {}
    for r in rows:
        by_run.setdefault(r["run"], []).append(r)
    freed = 0
    for run, rs in sorted(by_run.items()):
        d = RUNS / run
        if not (d / "DONE").exists():
            print(f"跳过 {run}：没有 DONE")
            continue
        keep = keep_state(d, run)
        if keep == "__none__":
            print(f"跳过 {run}：找不到完整的最终 state，整个 run 不动")
            continue
        todo = []
        for r in rs:
            p = d / r["file"]
            if r["file"] == keep:
                print(f"跳过 {run}/{r['file']}：是这个正式 run 步数最大的完整 state")
                continue
            if not p.exists():
                print(f"跳过 {run}/{r['file']}：已不在（之前删过）")
                continue
            if p.stat().st_size != r["size"] or sha256(p) != r["sha256"]:
                print(f"跳过 {run}/{r['file']}：和清单里的不一样了")
                continue
            todo.append(r)
        if a.yes and todo:  # 先写记录再删：中途断了，记录里也有这些文件在仓库里的位置
            arch = d / "ARCHIVED.json"
            old = json.loads(arch.read_text()) if arch.exists() else []
            files = [{k: r[k] for k in ("file", "step", "size", "sha256", "repo", "path_in_repo")} for r in todo]
            arch.write_text(json.dumps(old + [{"time": time.strftime("%FT%T%z"), "files": files}], indent=1) + "\n")
        for r in todo:
            print(f"{'删' if a.yes else '将删'} {run}/{r['file']}（{r['size'] / 1e6:.0f} MB，在 {r['repo']}:{r['path_in_repo']}）")
            if a.yes:
                (d / r["file"]).unlink()
                freed += r["size"]
        if a.yes and is_smoke(run) and not states(d) and not (d / "STATE_PRUNED").exists():
            pol = sorted(int(m.group(1)) for p in d.glob("policy_*.safetensors") if (m := POLICY.fullmatch(p.name)))
            if pol:
                (d / "STATE_PRUNED").write_text(f"{pol[-1]}\n")
                print(f"写 {run}/STATE_PRUNED（{pol[-1]} 步）")
    if a.yes and STAGE.exists():
        rmtree(STAGE)  # 硬链接也要删掉，空间才真正释放
    est = sum(r["size"] for r in rows) / 1e9
    print(f"释放 {freed / 1e9:.2f} GB；HF_DELETE_DONE" if a.yes else f"预计释放约 {est:.2f} GB（演习，没删）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--out", required=True)
    for name in ("upload", "verify"):
        q = sub.add_parser(name)
        q.add_argument("--manifest", required=True)
        q.add_argument("--repo", required=True)
        q.add_argument("--prefix", required=True)
        if name == "verify":
            q.add_argument("--out", required=True)
    c = sub.add_parser("spotcheck")
    c.add_argument("--verified", required=True)
    c.add_argument("--n", type=int, default=3)
    c.add_argument("--out", required=True)
    d = sub.add_parser("delete")
    d.add_argument("--verified", required=True)
    d.add_argument("--spotcheck", required=True)
    d.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    return {"plan": cmd_plan, "upload": cmd_upload, "verify": cmd_verify, "spotcheck": cmd_spotcheck, "delete": cmd_delete}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
