"""生成变体 A 清单的期望表、冒烟队列、正式队列与导出清单，一次一段。只用标准库。
  t2x  Tier 2 铺开：其余 24 条 episode 的变体 A seed 42，ml40，buffer 1000 万（计划 agent-doc/plan-t2-scaleout-2026-10-09.md）。
       分两段（Fable 5.1 审查 m5）：t2xa 是基线失败:骨盆低于 0.65 的 15 条（与试验同一种情形），t2xb 是几乎每个世界都摔的 9 条（外推）
  t3p  Tier 3 试跑：ep8、ep24 的变体 A seed 42，mf4090，buffer 400 万，参考换成 runs/motion/tier3 下从视频重建的那份
       （计划 agent-doc/plan-t3-pilot-2026-10-09.md）；一段 t3p
  t3p2 Tier 3 试跑第二轮：同两集，参考换成 runs/motion/tier3_v2 下同组成员校正版重建的那份，run 名带 -v2；其余同 t3p
       （计划 agent-doc/plan-t3-pilot-v2-2026-10-10.md）；一段 t3p2
  t3p3 Tier 3 校正版其余 10 集（P2′ 过门槛的 ep0、15、17、18、20、21、22、23、26、29）：参考同 t3p2，run 名同 t3p2 的写法；
       基线取 Tier 2 导出清单里这条 episode 现在交的 run（同 t2x；ep15、17、21、23 的基线在 mf4090 上）。
       分两段（计划 agent-doc/plan-t3-v2-train10-2026-10-10.md）：t3p3a 是现有磁盘放得下的 4 集（有支撑面的 ep20 与没有手接触的 ep29 在前），
       t3p3b 是归档腾出空间后的 6 集（ep17 放最后：Tier 2 变体 A 在 ep17 上每个世界都失败）
段名以清单名开头，有几个清单名都匹配时取最长的（t3p2 不落到 t3p）。续跑或补跑另起一段（审查 M2）：段名不在上面、用 --episodes 指定这一段的 episode（必须属于这份清单，顺序照清单），
例如 t2xa2；run 名不变，文件名带段名，所以日志、导出结果都是新的，每个 checkpoint 仍只导出一次。

每条都从一条 Tier 2 基线 run（seed 42）派生。基线行用 make_trial_queue.py 的 baseline() 在基线所在机器的队列文件里找、核对
（期望表与队列各恰好一种、冒烟与正式一致、步数、没有种子与变体的键、种子 42）。基线覆盖里只允许 scene.support=false 与
training.replay.capacity=4000000：出现别的键就报错，因为不知道它在新 run 里该不该留。
  t2x 的基线是 stages/evaluate/exports/{ml40,mf4090}.tsv 里这条 episode 现在交的 run，机器取 run 名的最后一段（如 -p185-ml40 → ml40）。
      buffer 用 ml40 默认的 1000 万：基线的 training.replay.capacity=4000000 去掉，期望表的 buffer 列写 10000000。
  t3p、t3p2 的基线是 ml40 上的 t2-ep<N>-w2048-cap10m-ml40；t3p3 的基线同 t2x。Tier 3 都把 parquet 的 /runs/motion/tier2/ 换成清单 motion 键给的目录
      （t3p 是 /runs/motion/tier3/，t3p2、t3p3 是 /runs/motion/tier3_v2/；序列名相同），加 400 万 buffer。
命名：t2x → t2-ep<N>-w2048-cap10m-r3a-ml40；t3p → t3-ep<N>-w2048-cap4m-r3a-mf4090；t3p2、t3p3 → t3-ep<N>-w2048-cap4m-r3a-v2-mf4090。顺序照计划（t2x 按基线 4096 世界失败:骨盆从低到高）。
输出：stages/policy/queues/<机器>_<段名>{.expect.tsv,_smoke.txt,.txt} 与 stages/evaluate/exports/cand_t<档>_<段名>_<机器>.tsv（export_chain.sh 的清单）。
W&B 标签用清单名（t2x、t3p、t3p2、t3p3）。任何一条核对不过就退出，什么文件都不写。
用法（仓库根）：python3 stages/policy/make_var_queue.py t2xa|t2xb|t3p|t3p2|t3p3a|t3p3b [--root <仓库根>]
           python3 stages/policy/make_var_queue.py <段名> --episodes 7,16 [--root <仓库根>]   （续跑、补跑）
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
            "parts": {"t2xa": [29, 23, 6, 18, 7, 16, 0, 21, 15, 10, 27, 3, 5, 11, 17], "t2xb": [9, 1, 13, 19, 2, 4, 14, 25, 28]},
            "run": "t2-ep{ep}-w2048-cap10m-r3a-ml40",
            "desc": "Tier 2 铺开：其余 24 条的变体 A seed 42（ml40，buffer 1000 万，按基线 4096 世界失败:骨盆从低到高）"},
    "t3p": {"plan": "agent-doc/plan-t3-pilot-2026-10-09.md", "tier": 3, "machine": "mf4090", "cap": "4000000",
            "episodes": [8, 24], "parts": {"t3p": [8, 24]}, "base": "t2-ep{ep}-w2048-cap10m-ml40", "motion": "tier3",
            "run": "t3-ep{ep}-w2048-cap4m-r3a-mf4090",
            "desc": "Tier 3 试跑：ep8、ep24 的变体 A seed 42（mf4090，buffer 400 万，参考是 runs/motion/tier3 下从视频重建的那份）"},
    "t3p2": {"plan": "agent-doc/plan-t3-pilot-v2-2026-10-10.md", "tier": 3, "machine": "mf4090", "cap": "4000000",
             "episodes": [8, 24], "parts": {"t3p2": [8, 24]}, "base": "t2-ep{ep}-w2048-cap10m-ml40", "motion": "tier3_v2",
             "run": "t3-ep{ep}-w2048-cap4m-r3a-v2-mf4090",
             "desc": "Tier 3 试跑第二轮：ep8、ep24 的变体 A seed 42（mf4090，buffer 400 万，参考是 runs/motion/tier3_v2 下同组成员校正版重建的那份）"},
    "t3p3": {"plan": "agent-doc/plan-t3-v2-train10-2026-10-10.md", "tier": 3, "machine": "mf4090", "cap": "4000000",
             "episodes": [20, 29, 0, 15, 18, 21, 22, 23, 26, 17],
             "parts": {"t3p3a": [20, 29, 0, 15], "t3p3b": [18, 21, 22, 23, 26, 17]}, "base": None, "motion": "tier3_v2",
             "run": "t3-ep{ep}-w2048-cap4m-r3a-v2-mf4090",
             "desc": "Tier 3 校正版其余 10 集：变体 A seed 42（mf4090，buffer 400 万，参考是 runs/motion/tier3_v2 下校正版重建的那份，基线取 Tier 2 导出清单）"},
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


def resolve(part: str, episodes=None) -> tuple:
    """段名 → (清单名, 这一段的 episode)。预设的段不许再给 --episodes；别的段名必须给，且只能取这份清单里的 episode。"""
    name = max((k for k in SETS if part.startswith(k)), key=len, default=None)   # 取最长的：t3p2 不落到 t3p
    if name is None or not part.replace("_", "").isalnum() or part != part.lower():
        raise SystemExit(f"make_var_queue: 段名 {part} 不以 {'、'.join(SETS)} 开头，或含小写字母、数字、下划线以外的字符")
    s = SETS[name]
    if part in s["parts"]:
        if episodes is not None:
            raise SystemExit(f"make_var_queue: {part} 是预设的段，不能再给 --episodes")
        return name, s["parts"][part]
    if not episodes:
        raise SystemExit(f"make_var_queue: {part} 不是预设的段（{'、'.join(s['parts'])}），要用 --episodes 指定")
    bad = sorted(set(episodes) - set(s["episodes"]))
    if bad or len(set(episodes)) != len(episodes):
        raise SystemExit(f"make_var_queue: --episodes 里有不属于 {name} 的 {bad}，或有重复")
    return name, [ep for ep in s["episodes"] if ep in episodes]


def make(part: str, root: Path, episodes=None) -> dict:
    name, eps = resolve(part, episodes)
    s = SETS[name]
    qdir = root / "stages" / "policy" / "queues"
    if s["tier"] == 2 or s["base"] is None:   # t2x 与 t3p3：基线取导出清单里这条 episode 现在交的 run
        cur = current_baselines(root)
        missing = [ep for ep in eps if ep not in cur]
        if missing:
            raise SystemExit(f"make_var_queue: 导出清单里没有 Tier 2 的 {missing}")
        bases = {ep: cur[ep] for ep in eps}
    else:
        bases = {ep: s["base"].format(ep=ep) for ep in eps}
    exp, smoke, formal_lines, cand = [HEADER], [], [], []
    for ep in eps:
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
            parquet = parquet.replace("/runs/motion/tier2/", f"/runs/motion/{s['motion']}/")
        run = s["run"].format(ep=ep)
        exp.append("\t".join([run, f"smoke-{run}", *row[2:8], s["cap"] or "10000000", "42", "no"]))
        tail = f"{parquet} {formal['worlds']}"
        formal_lines.append(f"{env_formal(name)} {run} {tail} {STEPS} {' '.join(over)}")
        smoke.append(f"{ENV_SMOKE} smoke-{run} {tail} {SMOKE_STEPS} {' '.join(over)}")
        cand.append(f"{s['tier']}\t{ep}\t{run}\t{STEPS}")
    head = (f"# {s['desc']}；这一段 {part}：{'、'.join(f'ep{e}' for e in eps)}；计划 {s['plan']}；变体 A = {' '.join(VARIANT)}；"
            f"训练挂 v040_p185_nfg（链的环境给 V2D_ALLOW_FC_SRC=1 V2D_FC_SRC=<副本>，不写进队列行）。make_var_queue.py 生成，不要手改。")
    stem = f"{s['machine']}_{part}"
    return {
        qdir / f"{stem}.expect.tsv": "\n".join(exp) + "\n",
        qdir / f"{stem}_smoke.txt": "\n".join([head, *smoke]) + "\n",
        qdir / f"{stem}.txt": "\n".join([head, *formal_lines]) + "\n",
        root / "stages" / "evaluate" / "exports" / f"cand_t{s['tier']}_{part}_{s['machine']}.tsv":
            "\n".join([f"# {s['desc']}，段 {part} 的候选导出（计划 {s['plan']}）：档位 episode run 步数。make_var_queue.py 生成，不要手改。", *cand]) + "\n",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("part")
    ap.add_argument("--episodes", type=lambda x: [int(v) for v in x.split(",") if v.strip()], default=None)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    a = ap.parse_args(argv)
    for path, text in make(a.part, Path(a.root), a.episodes).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        print(f"写 {path.relative_to(a.root)}（{text.count(chr(10))} 行）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
