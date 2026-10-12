"""make_var_queue.py 的测试（守计划 agent-doc/plan-t2-scaleout-2026-10-09.md 第 2、3 节与 agent-doc/plan-t3-pilot-2026-10-09.md 第 2、3 节的
run 设计；运行规范未成文，暂无契约 ID）。只用标准库。
临时目录里放假的 Tier 2 基线（30 条 episode：偶数在 ml40、1000 万 buffer，奇数在 mf4090、带 training.replay.capacity=4000000；
ep1 用 -p185-ml40 的名字；support 为 true 的不带 scene.support=false）与两份导出清单，跑生成脚本后核：
  1. t2xa、t2xb 两段：15 条与 9 条 run 的名字与计划顺序；每行没有 buffer 覆盖、有变体 A 两项、基线有的 scene.support=false 照留；
     冒烟与正式行除步数、前缀外一致；W&B 标签 t2x；期望表的 buffer 列 10000000、种子 42，其余列照抄基线；导出清单与 run 一一对应、档位 2
  2. t3p：2 条 run；parquet 换到 /runs/motion/tier3/、序列名不变；覆盖以 400 万 buffer 开头；期望表 buffer 列 4000000；导出清单档位 3；
     t3p2（agent-doc/plan-t3-pilot-v2-2026-10-10.md）：段名也以 t3p 开头，要落到 t3p2 这份清单（取最长的）；run 名带 -v2，
     parquet 在 /runs/motion/tier3_v2/ 下，W&B 标签 t3p2，其余同 t3p；
     t3p3a、t3p3b（agent-doc/plan-t3-v2-train10-2026-10-10.md）：4 条与 6 条，顺序照计划；基线取导出清单（奇数号在 mf4090、
     带 400 万 buffer 覆盖，去掉后照样以 400 万开头）；run 名、parquet 目录同 t3p2，W&B 标签 t3p3
  3. 基线覆盖里有计划没说的键、或一条 episode 在导出清单里出现两次：报错退出，不写文件
  4. 续跑段 t2xa2 --episodes 16,7：只有这两条，顺序照清单（ep7 在前），文件名带段名
  5. 段名不对：预设段又给 --episodes、非预设段不给 --episodes、--episodes 里有清单外的 episode、段名不以清单名开头，都报错不写文件
  6. t1xa、t1ya（agent-doc/plan-next-training-2026-10-12.md 第 3 节 A、C）：基线取 t1_select_r3x.tsv 里的 Tier 1 run（偶数号在 ml40、
     1000 万 buffer，奇数号在 mf4090、带 400 万覆盖）；t1xa 7 条在 mf4090、一律 400 万、W&B 标签 t1x；t1ya 6 条在 ml40、没有 buffer 覆盖、标签 t1y；
     parquet 在 /runs/motion/tier1/；导出清单档位 1。ml40 的 ep10 在第二张期望表里多一行、只差 xeval（真实情形同 t1-ep10-w2048-cap10m-ml40），
     照常生成；那一行若还差别的列（帧数），报“找到 2 种”、不写文件（make_trial_queue.baseline 的改动，同计划审查 M2）
  7. t3p4a、t3p4b、t3qa、t3qb（agent-doc/plan-d-t3hm-train-2026-10-12.md）：四段合起来恰好 29 集、不重复；run 名带 -hm-，parquet 在
     /runs/motion/tier3_hm/；mf4090 两段带 400 万覆盖、期望表 4000000，ml40 两段没有 buffer 覆盖、期望表 10000000；支撑面按 best_hm 的 12 集桌面定，
     与基线不同的几种都核：ep1（基线是 p185 run）、ep15（基线开着支撑面、best_hm 只有地面：要加覆盖、列改 false）、ep17（基线关着、best_hm 有桌面：
     去掉覆盖、列改 true）；ml40 的续跑段 t3qc --episodes 12,13 照总顺序生成（段之间挪集只要 --episodes）
用法：python3 stages/policy/test_make_var_queue.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV = "V2D_WANDB_TAG=batch V2D_MAX_RETRY=0 V2D_GPU_APPS=1 V2D_WANDB_UPLOAD_CKPT=0"
SENV = "V2D_WANDB_PROJECT=v2d-selftest V2D_WANDB_TAG=smoke V2D_MAX_RETRY=0 V2D_GPU_APPS=1 V2D_WANDB_UPLOAD_CKPT=0"
HEADER = "run\tsmoke\tsequence_id\tplayback\tsrc_frames\tsupport\tpos_tol\tori_tol\tcapacity\tseed\txeval"
VAR = ["objective.object_position_std=0.05", "termination.object_orientation_threshold=0.6"]
T2XA = [29, 23, 6, 18, 7, 16, 0, 21, 15, 10, 27, 3, 5, 11, 17]
T2XB = [9, 1, 13, 19, 2, 4, 14, 25, 28]
T1XA = [17, 21, 10, 13, 19, 3, 14]
T1YA = [2, 11, 16, 4, 9, 25]


def seq(ep):
    return f"2026-01-{ep:02d}_obj_{ep}"


def frames(ep):
    return str(500 + ep)


def support(ep):
    return "true" if ep % 3 == 0 else "false"


def base_run(ep):
    if ep == 1:
        return "t2-ep1-w2048-cap10m-p185-ml40"
    return f"t2-ep{ep}-w2048-cap10m-ml40" if ep % 2 == 0 else f"t2-ep{ep}-w2048-cap4m-mf4090"


def pq(ep, tier=2, motion=None):
    return f"/repo/runs/motion/{motion or f'tier{tier}'}/whole_body/soma/sequence_id={seq(ep)}/robot_name=g1/data.parquet"


def t1_base_run(ep):
    return f"t1-ep{ep}-w2048-cap10m-ml40" if ep % 2 == 0 else f"t1-ep{ep}-w2048-cap4m-mf4090"


def setup_t1(q: Path, ex: Path, dup_conflict=False):
    rows = {"ml40": [], "mf4090": []}
    for ep in range(30):
        run = t1_base_run(ep)
        m = run.rsplit("-", 1)[1]
        over = ([] if support(ep) == "true" else ["scene.support=false"]) + (["training.replay.capacity=4000000"] if m == "mf4090" else [])
        rows[m].append((ep, run, "10000000" if m == "ml40" else "4000000", over))
    sel = []
    for m, items in rows.items():
        exp, fl, sl = [HEADER], ["# Tier 1 基线"], ["# Tier 1 基线冒烟"]
        for ep, run, cap, over in items:
            exp.append("\t".join([run, f"smoke-{run}", seq(ep), "frame", frames(ep), support(ep), "0.015", "0.086", cap, "42", "no"]))
            o = (" " + " ".join(over)) if over else ""
            fl.append(f"{ENV} {run} {pq(ep, 1)} 2048 349999104{o}")
            sl.append(f"{SENV} smoke-{run} {pq(ep, 1)} 2048 4096000{o}")
            sel.append(f"1\t{ep}\t{run}\t349999104\t{m}")
        (q / f"{m}_t1base.expect.tsv").write_text("\n".join(exp) + "\n")
        (q / f"{m}_t1base.txt").write_text("\n".join(fl) + "\n")
        (q / f"{m}_t1base_smoke.txt").write_text("\n".join(sl) + "\n")
    run = t1_base_run(10)   # 第二张表里的同一条 run：只差 xeval；dup_conflict 时帧数也不同
    (q / "ml40_t1dup.expect.tsv").write_text("\n".join([HEADER, "\t".join(
        [run, f"smoke-{run}", seq(10), "frame", frames(10) + ("1" if dup_conflict else ""), support(10), "0.015", "0.086", "10000000", "42", "yes"])]) + "\n")
    (ex / "t1_select_r3x.tsv").write_text("\n".join(sel) + "\n")


def setup(root: Path, bad_key_ep=None, dup_ep=None, t1_dup_conflict=False):
    q = root / "stages" / "policy" / "queues"
    ex = root / "stages" / "evaluate" / "exports"
    q.mkdir(parents=True)
    ex.mkdir(parents=True)
    setup_t1(q, ex, t1_dup_conflict)
    rows = {"ml40": [], "mf4090": []}
    for ep in range(30):
        run = base_run(ep)
        m = run.rsplit("-", 1)[1]
        cap = "10000000" if m == "ml40" else "4000000"
        over = ([] if support(ep) == "true" else ["scene.support=false"]) + (["training.replay.capacity=4000000"] if m == "mf4090" else [])
        if ep == bad_key_ep:
            over.append("training.batch_size=512")
        rows[m].append((ep, run, cap, over))
    for m, items in rows.items():
        exp, fl, sl = [HEADER], ["# 基线"], ["# 基线冒烟"]
        for ep, run, cap, over in items:
            exp.append("\t".join([run, f"smoke-{run}", seq(ep), "frame", frames(ep), support(ep), "0.015", "0.086", cap, "42", "no"]))
            o = (" " + " ".join(over)) if over else ""
            fl.append(f"{ENV} {run} {pq(ep)} 2048 349999104{o}")
            sl.append(f"{SENV} smoke-{run} {pq(ep)} 2048 4096000{o}")
        (q / f"{m}_t2a.expect.tsv").write_text("\n".join(exp) + "\n")
        (q / f"{m}_t2a.txt").write_text("\n".join(fl) + "\n")
        (q / f"{m}_t2a_smoke.txt").write_text("\n".join(sl) + "\n")
        lines = ["# 导出清单"] + [f"2\t{ep}\t{run}\t349999104" for ep, run, _, _ in items]
        if m == "ml40" and dup_ep is not None:
            lines.append(f"2\t{dup_ep}\tt2-ep{dup_ep}-w2048-cap10m-other-ml40\t349999104")
        (ex / f"{m}.tsv").write_text("\n".join(lines) + "\n")
    # t3p 的基线是 ml40 上 cap10m 的 ep8、ep24：两者都是偶数号，上面已经放在 ml40


def gen(root: Path, name: str, *extra):
    return subprocess.run([sys.executable, str(HERE / "make_var_queue.py"), name, "--root", str(root), *extra], capture_output=True, text=True)


def lines(p: Path):
    return [x for x in p.read_text().splitlines() if x and not x.startswith("#")]


def check_set(root, name, eps, run_fmt, tier, cap_col, cap_over, env_tag, machine, motion=None):
    q = root / "stages" / "policy" / "queues"
    want = [run_fmt.format(ep=e) for e in eps]
    f, s = lines(q / f"{machine}_{name}.txt"), lines(q / f"{machine}_{name}_smoke.txt")
    assert [x.split()[5] for x in f] == want, f
    for fx, sx, ep in zip(f, s, eps):
        ft, st = fx.split(), sx.split()
        over = ft[9:]
        assert ft[:5] == f"V2D_WANDB_TAG={env_tag} V2D_MAX_RETRY=0 V2D_GPU_APPS=1 V2D_WANDB_UPLOAD_CKPT=0 V2D_KEEP_STATES=1".split(), fx
        assert st[:5] == SENV.split(), sx
        assert ft[6] == pq(ep, tier, motion) and ft[7] == "2048" and ft[8] == "349999104", fx
        caps = [o for o in over if o.startswith("training.replay.capacity=")]
        assert caps == ([cap_over] if cap_over else []) and (not cap_over or over[0] == cap_over), fx
        assert ("scene.support=false" in over) == (support(ep) == "false") and over[-2:] == VAR, fx
        assert st[5] == "smoke-" + ft[5] and st[8] == "4096000" and st[6:8] == ft[6:8] and st[9:] == over, (fx, sx)
    exp = lines(q / f"{machine}_{name}.expect.tsv")
    assert exp[0] == HEADER
    for row, run, ep in zip(exp[1:], want, eps):
        c = row.split("\t")
        assert c[:2] == [run, "smoke-" + run] and c[2:8] == [seq(ep), "frame", frames(ep), support(ep), "0.015", "0.086"], row
        assert c[8:] == [cap_col, "42", "no"], row
    assert len(exp) == len(eps) + 1
    cand = lines(root / "stages" / "evaluate" / "exports" / f"cand_t{tier}_{name}_{machine}.tsv")
    assert cand == [f"{tier}\t{ep}\t{run}\t349999104" for ep, run in zip(eps, want)], cand


def test_t2x_parts():
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        setup(root)
        for part, eps in (("t2xa", T2XA), ("t2xb", T2XB)):
            r = gen(root, part)
            assert r.returncode == 0, r.stdout + r.stderr
            check_set(root, part, eps, "t2-ep{ep}-w2048-cap10m-r3a-ml40", 2, "10000000", None, "t2x", "ml40")


def test_resume_part():
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        setup(root)
        r = gen(root, "t2xa2", "--episodes", "16,7")
        assert r.returncode == 0, r.stdout + r.stderr
        check_set(root, "t2xa2", [7, 16], "t2-ep{ep}-w2048-cap10m-r3a-ml40", 2, "10000000", None, "t2x", "ml40")


def test_bad_parts_refuse():
    for args in (["t2xa", "--episodes", "7"], ["t2xz"], ["t2xr", "--episodes", "8"], ["t2xr", "--episodes", "7,7"], ["foo"]):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            setup(root)
            r = gen(root, *args)
            assert r.returncode != 0, (args, r.stdout + r.stderr)
            assert not list((root / "stages" / "policy" / "queues").glob("ml40_t2x*")), args


def test_t3p():
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        setup(root)
        r = gen(root, "t3p")
        assert r.returncode == 0, r.stdout + r.stderr
        check_set(root, "t3p", [8, 24], "t3-ep{ep}-w2048-cap4m-r3a-mf4090", 3, "4000000", "training.replay.capacity=4000000", "t3p", "mf4090")


def test_t3p2():
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        setup(root)
        r = gen(root, "t3p2")
        assert r.returncode == 0, r.stdout + r.stderr
        check_set(root, "t3p2", [8, 24], "t3-ep{ep}-w2048-cap4m-r3a-v2-mf4090", 3, "4000000", "training.replay.capacity=4000000", "t3p2",
                  "mf4090", motion="tier3_v2")
        assert not (root / "stages" / "policy" / "queues" / "mf4090_t3p.txt").exists()


def test_t3p3_parts():
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        setup(root)
        for part, eps in (("t3p3a", [20, 29, 0, 15]), ("t3p3b", [18, 21, 22, 23, 26, 17])):
            r = gen(root, part)
            assert r.returncode == 0, r.stdout + r.stderr
            check_set(root, part, eps, "t3-ep{ep}-w2048-cap4m-r3a-v2-mf4090", 3, "4000000", "training.replay.capacity=4000000", "t3p3",
                      "mf4090", motion="tier3_v2")
        r = gen(root, "t3p3a", "--episodes", "20")
        assert r.returncode != 0, r.stdout + r.stderr


TABLES_HM = [2, 3, 6, 7, 9, 11, 13, 16, 17, 20, 25, 27]


def test_t3p4_t3q_parts():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        setup(root)
        q = root / "stages" / "policy" / "queues"
        parts = {"t3p4a": ("mf4090", [15, 17, 1, 2, 3]), "t3p4b": ("mf4090", [12, 13, 14, 16, 19, 21, 25, 27]),
                 "t3qa": ("ml40", [4, 5, 6, 7, 8, 9, 10, 11]), "t3qb": ("ml40", [0, 18, 22, 24, 26, 20, 23, 29])}
        allep = [e for _, eps in parts.values() for e in eps]
        assert sorted(allep) == [e for e in range(30) if e != 28] and len(allep) == 29, allep
        for part, (m, eps) in parts.items():
            r = gen(root, part)
            assert r.returncode == 0, r.stdout + r.stderr
            tag = "t3p4" if m == "mf4090" else "t3q"
            fmt = "t3-ep{ep}-w2048-cap4m-r3a-hm-mf4090" if m == "mf4090" else "t3-ep{ep}-w2048-cap10m-r3a-hm-ml40"
            f, sm = lines(q / f"{m}_{part}.txt"), lines(q / f"{m}_{part}_smoke.txt")
            assert [x.split()[5] for x in f] == [fmt.format(ep=e) for e in eps], f
            exp = lines(q / f"{m}_{part}.expect.tsv")[1:]
            for fx, sx, row, ep in zip(f, sm, exp, eps):
                ft, over, c = fx.split(), fx.split()[9:], row.split("\t")
                assert ft[0] == f"V2D_WANDB_TAG={tag}" and ft[6] == pq(ep, 3, "tier3_hm"), fx
                caps = [o for o in over if o.startswith("training.replay.capacity=")]
                assert caps == (["training.replay.capacity=4000000"] if m == "mf4090" else []), fx
                on = ep in TABLES_HM
                assert ("scene.support=false" in over) == (not on) and over.count("scene.support=false") <= 1 and over[-2:] == VAR, (ep, fx)
                assert c[5] == ("true" if on else "false") and c[2:5] == [seq(ep), "frame", frames(ep)], (ep, row)
                assert c[8] == ("4000000" if m == "mf4090" else "10000000"), row
                assert sx.split()[9:] == over, (fx, sx)
        # 与基线不同的几种：ep15 基线开着（15 % 3 == 0）、best_hm 只有地面；ep17 基线关着、best_hm 有桌面；ep1 的基线是 p185 run、关着
        assert support(15) == "true" and support(17) == "false" and support(1) == "false" and base_run(1).endswith("-p185-ml40")
        r = gen(root, "t3qc", "--episodes", "13,12")
        assert r.returncode == 0, r.stdout + r.stderr
        assert [x.split()[5] for x in lines(q / "ml40_t3qc.txt")] == ["t3-ep12-w2048-cap10m-r3a-hm-ml40", "t3-ep13-w2048-cap10m-r3a-hm-ml40"]


def test_t1_parts():
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        setup(root)
        r = gen(root, "t1xa")
        assert r.returncode == 0, r.stdout + r.stderr
        check_set(root, "t1xa", T1XA, "t1-ep{ep}-w2048-cap4m-r3a-mf4090", 1, "4000000", "training.replay.capacity=4000000", "t1x", "mf4090")
        r = gen(root, "t1ya")
        assert r.returncode == 0, r.stdout + r.stderr
        check_set(root, "t1ya", T1YA, "t1-ep{ep}-w2048-cap10m-r3a-ml40", 1, "10000000", None, "t1y", "ml40")
        r = gen(root, "t1xa", "--episodes", "10")
        assert r.returncode != 0, r.stdout + r.stderr


def test_t1_xeval_conflict_refuses():
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        setup(root, t1_dup_conflict=True)
        r = gen(root, "t1xa")
        out = r.stdout + r.stderr
        assert r.returncode != 0 and "找到 2 种" in out, out
        assert not (root / "stages" / "policy" / "queues" / "mf4090_t1xa.txt").exists()


def test_unknown_override_refuses():
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        setup(root, bad_key_ep=6)
        r = gen(root, "t2xa")
        out = r.stdout + r.stderr
        assert r.returncode != 0 and "计划没说怎么处理的键" in out, out
        assert not (root / "stages" / "policy" / "queues" / "ml40_t2xa.txt").exists()


def test_duplicate_export_row_refuses():
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        setup(root, dup_ep=10)
        r = gen(root, "t2xa")
        assert r.returncode != 0 and "不止一行" in r.stdout + r.stderr, r.stdout + r.stderr
        assert not (root / "stages" / "evaluate" / "exports" / "cand_t2_t2xa_ml40.tsv").exists()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
    print("ALL_OK")
