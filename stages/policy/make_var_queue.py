"""生成变体 A 清单的期望表、冒烟队列、正式队列与导出清单。只用标准库。
  t2x  Tier 2 铺开：其余 24 条 episode 的变体 A seed 42，ml40，buffer 1000 万（计划 agent-doc/plan-t2-scaleout-2026-10-09.md）
  t3p  Tier 3 试跑：ep8、ep24 的变体 A seed 42，mf4090，buffer 400 万，参考换成 runs/motion/tier3 下从视频重建的那份
       （计划 agent-doc/plan-t3-pilot-2026-10-09.md）

每条都从一条 Tier 2 基线 run（seed 42）派生。基线行用 make_trial_queue.py 的 baseline() 在基线所在机器的队列文件里找、核对
（期望表与队列各恰好一种、冒烟与正式一致、步数、没有种子与变体的键、种子 42）。基线覆盖里只允许 scene.support=false 与
training.replay.capacity=4000000：出现别的键就报错，因为不知道它在新 run 里该不该留。
  t2x 的基线是 stages/evaluate/exports/{ml40,mf4090}.tsv 里这条 episode 现在交的 run，机器取 run 名的最后一段（如 -p185-ml40 → ml40）。
      buffer 用 ml40 默认的 1000 万：基线的 training.replay.capacity=4000000 去掉，期望表的 buffer 列写 10000000。
  t3p 的基线是 ml40 上的 t2-ep<N>-w2048-cap10m-ml40：parquet 的 /runs/motion/tier2/ 换成 /runs/motion/tier3/（序列名相同），加 400 万 buffer。
命名：t2x → t2-ep<N>-w2048-cap10m-r3a-ml40；t3p → t3-ep<N>-w2048-cap4m-r3a-mf4090。顺序照计划（t2x 按基线 4096 世界失败:骨盆从低到高）。
输出：stages/policy/queues/<机器>_<名字>{.expect.tsv,_smoke.txt,.txt} 与 stages/evaluate/exports/cand_t<档>_<名字>_<机器>.tsv（export_chain.sh 的清单）。
任何一条核对不过就退出，什么文件都不写。
用法（仓库根）：python3 stages/policy/make_var_queue.py t2x|t3p [--root <仓库根>]
测试：stages/policy/test_make_var_queue.py。
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_trial_queue import HEADER, SMOKE_STEPS, STEPS, VARIANT, baseline  # noqa: E402

ALLOWED = {"scene.support=false", "training.replay.capacity=4000000"}
SETS = {
    "t2x": {"plan": "agent-doc/plan-t2-scaleout-2026-10-09.md", "tier": 2, "machine": "ml40", "cap": None,
            "episodes": [29, 23, 6, 18, 7, 16, 0, 21, 15, 10, 27, 3, 5, 11, 17, 9, 1, 13, 19, 2, 4, 14, 25, 28],
            "run": "t2-ep{ep}-w2048-cap10m-r3a-ml40",
            "desc": "Tier 2 铺开：其余 24 条的变体 A seed 42（ml40，buffer 1000 万，按基线 4096 世界失败:骨盆从低到高）"},
    "t3p": {"plan": "agent-doc/plan-t3-pilot-2026-10-09.md", "tier": 3, "machine": "mf4090", "cap": "4000000",
            "episodes": [8, 24], "base": "t2-ep{ep}-w2048-cap10m-ml40",
            "run": "t3-ep{ep}-w2048-cap4m-r3a-mf4090",
            "desc": "Tier 3 试跑：ep8、ep24 的变体 A seed 42（mf4090，buffer 400 万，参考是 runs/motion/tier3 下从视频重建的那份）"},
}
ENV_SMOKE = "V2D_WANDB_PROJECT=v2d-selftest V2D_WANDB_TAG=smoke V2D_MAX_RETRY=0 V2D_GPU_APPS=1 V2D_WANDB_UPLOAD_CKPT=0"


def env_formal(name: str) -> str:
    return f"V2D_WANDB_TAG={name} V2D_MAX_RETRY=0 V2D_GPU_APPS=1 V2D_WANDB_UPLOAD_CKPT=0 V2D_KEEP_STATES=1"


def current_baselines(root: Path) -> dict:
    """Tier 2 的 episode → 现在交的 run（两份导出清单合起来，每条 episode 恰好一行）。"""
    out = {}
    for m in ("ml40", "mf4090"):
        for line in (root / "stages" / "evaluate" / "exports" / f"{m}.tsv").read_text().splitlines():
            c = line.split("\t")
            if len(c) >= 4 and c[0] == "2":
                ep = int(c[1])
                if ep in out:
                    raise SystemExit(f"make_var_queue: Tier 2 ep{ep} 在导出清单里不止一行（{out[ep]}、{c[2]}）")
                out[ep] = c[2]
    return out


def make(name: str, root: Path) -> dict:
    s = SETS[name]
    qdir = root / "stages" / "policy" / "queues"
    if s["tier"] == 2:
        cur = current_baselines(root)
        missing = [ep for ep in s["episodes"] if ep not in cur]
        if missing:
            raise SystemExit(f"make_var_queue: 导出清单里没有 Tier 2 的 {missing}")
        bases = {ep: cur[ep] for ep in s["episodes"]}
    else:
        bases = {ep: s["base"].format(ep=ep) for ep in s["episodes"]}
    exp, smoke, formal_lines, cand = [HEADER], [], [], []
    for ep in s["episodes"]:
        base = bases[ep]
        row, formal = baseline(qdir, base.rsplit("-", 1)[1], base)
        extra = sorted(set(formal["overrides"]) - ALLOWED)
        if extra:
            raise SystemExit(f"make_var_queue: {base} 的覆盖里有计划没说怎么处理的键：{extra}")
        if formal["worlds"] != "2048":
            raise SystemExit(f"make_var_queue: {base} 的世界数是 {formal['worlds']}，不是 2048")
        keep = [o for o in formal["overrides"] if not o.startswith("training.replay.capacity=")]
        over = ([f"training.replay.capacity={s['cap']}"] if s["cap"] else []) + keep + VARIANT
        parquet = formal["parquet"]
        if s["tier"] == 3:
            if parquet.count("/runs/motion/tier2/") != 1:
                raise SystemExit(f"make_var_queue: {base} 的 parquet 不在 /runs/motion/tier2/ 下：{parquet}")
            parquet = parquet.replace("/runs/motion/tier2/", "/runs/motion/tier3/")
        run = s["run"].format(ep=ep)
        exp.append("\t".join([run, f"smoke-{run}", *row[2:8], s["cap"] or "10000000", "42", "no"]))
        tail = f"{parquet} {formal['worlds']}"
        formal_lines.append(f"{env_formal(name)} {run} {tail} {STEPS} {' '.join(over)}")
        smoke.append(f"{ENV_SMOKE} smoke-{run} {tail} {SMOKE_STEPS} {' '.join(over)}")
        cand.append(f"{s['tier']}\t{ep}\t{run}\t{STEPS}")
    head = (f"# {s['desc']}；计划 {s['plan']}；变体 A = {' '.join(VARIANT)}；训练挂 v040_p185_nfg"
            f"（链的环境给 V2D_ALLOW_FC_SRC=1 V2D_FC_SRC=<副本>，不写进队列行）。make_var_queue.py 生成，不要手改。")
    stem = f"{s['machine']}_{name}"
    return {
        qdir / f"{stem}.expect.tsv": "\n".join(exp) + "\n",
        qdir / f"{stem}_smoke.txt": "\n".join([head, *smoke]) + "\n",
        qdir / f"{stem}.txt": "\n".join([head, *formal_lines]) + "\n",
        root / "stages" / "evaluate" / "exports" / f"cand_t{s['tier']}_{name}_{s['machine']}.tsv":
            "\n".join([f"# {s['desc']} 的候选导出（计划 {s['plan']}）：档位 episode run 步数。make_var_queue.py 生成，不要手改。", *cand]) + "\n",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name", choices=sorted(SETS))
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    a = ap.parse_args(argv)
    for path, text in make(a.name, Path(a.root)).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        print(f"写 {path.relative_to(a.root)}（{text.count(chr(10))} 行）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
