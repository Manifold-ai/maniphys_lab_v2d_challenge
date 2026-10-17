"""Delivery report of a Tier 3 version: self-check results and basic numbers, next to the previous delivery (10-16).

Every delivered version carries one (user, 10-16), so whoever trains on it knows what it is and how it was checked.
Reads the checks' own result files, never retyped numbers, and a small spec json for what only a person states (who
reviewed which images, known issues, notes). Writes Markdown to stdout.

Spec json:
  {"version": "<dir name under runs/>", "set": "<gate set>", "base": "<previous delivery>", "base_set": "<its gate set>",
   "align": "<align json of version>", "base_align": "<align json holding base>", "contract": "<contract json>",
   "audit": "<pose audit json, base -> version or the previous candidate -> version>", "supports": "<support dir name>",
   "reviews": [{"item": "...", "by": "user|agent", "result": "...", "images": "<dir>"}], "known_issues": ["..."],
   "not_done": ["..."], "notes": ["..."]}

    python t3_delivery_report.py <tier3 root> <gate dir> <spec json> > DELIVERY.md
"""
import json
import re
import sys
from pathlib import Path

LABEL_DROP = 0.10  # an episode whose labelled contact frames fall by more than this against the previous delivery is listed
KEYS = ["lin_supported", "lin_airborne", "lin_held", "rest_drift", "rot_drift", "rot_jump", "rot_torque"]


def dyn(g: Path, s: str):
    return json.loads((g / "dyn" / f"tier3_{s}.json").read_text())["episodes"]


def labelled(e: dict) -> int:
    return sum(e[h]["labelled"] for h in ("left", "right"))


def ho(g: Path, s: str):
    rows = json.loads((g / "dyn" / f"ho_{s}.json").read_text())
    lab = sum(e[h]["labelled"] for e in rows for h in ("left", "right"))
    away = sum(e[h]["label_on_hand_away"] for e in rows for h in ("left", "right"))
    return {e["episode"][:4]: e for e in rows}, away / max(lab, 1)


def gate(g: Path, s: str, ours: bool):
    """Per episode index -> pass, from the floor-only P2 table or our-supports RESULT lines."""
    if ours:
        out = {}
        for line in (g / "logs" / f"oursup_{s}.txt").read_text().splitlines():
            m = re.match(r"^(\d+) RESULT .*ok=(\d)", line)
            if m:
                out[int(m.group(1))] = m.group(2) == "1"
        return out
    txt = (g / "logs" / f"p2_{s}.txt").read_text()
    fail = re.search(r"P2_FAIL \d+/\d+：(.*)", txt)
    failed = {int(x[2:]) for x in fail.group(1).split()} if fail and fail.group(1).strip() not in ("无", "") else set()
    return {i: i not in failed for i in range(30)}


def align(path: Path, version: str):
    rows = {e["episode"]: e[version] for e in json.loads(path.read_text()) if version in e}
    return rows


def main():
    root, g, spec = Path(sys.argv[1]), Path(sys.argv[2]), json.loads(Path(sys.argv[3]).read_text())
    v, s, b, bs = spec["version"], spec["set"], spec["base"], spec["base_set"]
    runs = root / "runs"
    D, DB = dyn(g, s), dyn(g, bs)
    H, hshare = ho(g, s)
    HB, hbshare = ho(g, bs)
    # the hand-away share only counts frames the retarget labelled; a hand pulled off the object loses its labels, and
    # those frames leave the count (10-17: GB lost 60 of ep01's 216, the share stayed 0.45 -> 0.48%), so the labelled
    # frames themselves are compared to the previous delivery
    drops = sorted(((k, labelled(HB[k]), labelled(H[k])) for k in H if k in HB and labelled(HB[k]) > 0
                    and labelled(H[k]) < (1 - LABEL_DROP) * labelled(HB[k])), key=lambda x: x[2] / x[1])
    gf, go = gate(g, s, False), gate(g, s, True)
    gfb, gob = gate(g, bs, False), gate(g, bs, True)
    A, AB = align(Path(spec["align"]), v), align(Path(spec["base_align"]), b)
    eps29 = [e for e in A if e in AB and not e.startswith("ep28")]
    mean = lambda R, E: sum(R[e]["iou_p50"] for e in E) / len(E)
    low = lambda R: sum(sum(1 for x in r["per_frame"]["iou"] if x < 0.5) for r in R.values())
    total = lambda d: sum(e["frames"] for e in d.values())
    viol = lambda d: sum(e["object_any"] for e in d.values())
    early = lambda d: sum(1 for e in d.values() if e["first"]["object_any"] is not None and e["first"]["object_any"] < 30)
    prov = json.loads((runs / f"{v}.provenance.json").read_text()) if (runs / f"{v}.provenance.json").exists() else {}
    reg = json.loads((Path(__file__).resolve().parents[1] / "versions.json").read_text())["versions"]
    key = v.replace("tier3_cari4d_f830_", "")
    contract = json.loads(Path(spec["contract"]).read_text()) if spec.get("contract") else None
    audit = json.loads(Path(spec["audit"]).read_text()) if spec.get("audit") else None

    o = [f"# Tier 3 交付：`{v}`", ""]
    o += [f"由 `stages/recovery/tier3/gate/t3_delivery_report.py` 从各项检查的结果文件生成，数字不经手抄。上一个交付版：`{b}`。", ""]
    o += ["## 这是什么", "", f"- 用途：{reg.get(key, {}).get('purpose', '（未登记）')}",
          f"- 由 `{prov.get('made_by', '?')}` from `{prov.get('from_version', '?')}` 生成；代码 {prov.get('deployed', '?')[:60]}",
          f"- 支撑面：`runs/support/{spec['supports']}`，写成 usda 放在本版本的 `support_surface/` 下（路径见每集元数据的 `support_surface`）。",
          f"- 集数：{len(D)}（其中 {sum(1 for p in (runs / (v + '_suspect') / 'data' / 'chunk-000').glob('*.parquet'))} 集在 `{v}_suspect`）。", ""]
    o += ["## 与上一个交付版对比", "", f"| 项目 | `{b}` | `{v}` |", "|---|---|---|",
          f"| 物体动力学违规帧（占比） | {viol(DB)} ({100 * viol(DB) / total(DB):.1f}%) | {viol(D)} ({100 * viol(D) / total(D):.1f}%) |",
          f"| 零违规的集 | {sum(1 for e in DB.values() if e['object_any'] == 0)} | {sum(1 for e in D.values() if e['object_any'] == 0)} |",
          f"| 前 30 帧内就违规的集 | {early(DB)} | {early(D)} |"]
    for k in KEYS:
        o.append(f"| `{k}` | {sum(e['count'][k] for e in DB.values())} | {sum(e['count'][k] for e in D.values())} |")
    o += [f"| 轮廓 IoU（各集中位数的均值，29 集，不含 ep28） | {mean(AB, eps29):.3f} | {mean(A, eps29):.3f} |",
          f"| IoU < 0.5 的抽样帧 | {low(AB)} | {low(A)} |",
          f"| 训练前门槛，用我们的支撑面 | {sum(gob.values())}/{len(gob)} | {sum(go.values())}/{len(go)} |",
          f"| 标了接触但手离物体 > 3 cm | {100 * hbshare:.2f}% | {100 * hshare:.2f}% |",
          f"| 标了接触的帧（左右手合计） | {sum(labelled(e) for e in HB.values())} | {sum(labelled(e) for e in H.values())} |", ""]
    o += ["门槛只列用我们支撑面判的结果：Tier 3 不能用官方支撑面；只按地面判时，放在桌上的物体必然算悬空。逐集表里的「地面」一列只作参考，"
          "hm 那套门槛数据是 10-13 建的、集目录里带着官方支撑面，口径不同。", ""]
    o += ["## 自检（清单见 10-15 定的 13 项）", "", "| # | 项目 | 结果 |", "|---|---|---|"]
    if contract:
        o.append(f"| 11 | 数据契约（对照 `{contract['base']}`） | {'通过' if not contract['problems'] else '不通过：' + '; '.join(contract['problems'])}；改动的列 {contract['changed_columns']} |")
    if audit:
        n5 = sum(e["visible_frames_over_5cm_outside_locked"] for e in audit)
        top = sorted(audit, key=lambda e: -e["visible_frames_over_5cm_outside_locked"])[:3]
        o.append(f"| 2 | 改动审计 | 锁定段外可见改动 > 5 cm 的帧 {n5}；最多的集：" + ", ".join(f"{e['episode']} {e['visible_frames_over_5cm_outside_locked']}" for e in top) + " |")
    o.append(f"| 3 | 逐帧画面对齐 | IoU < 0.5 的抽样帧 {low(A)}（上一交付版 {low(AB)}） |")
    o.append(f"| 5 | 动力学检查 | 违规帧 {viol(D)}，见上表 |")
    o.append(f"| 9 | 手和物体 | 标了接触但手离物体 > 3 cm 的占 {100 * hshare:.2f}%；接触帧比上一交付版少 {100 * LABEL_DROP:.0f}% 以上的集："
             + ("、".join(f"{k} {a} → {n}" for k, a, n in drops) if drops else "无") + " |")
    o.append(f"| 12 | 来源 | `{v}.provenance.json`：{'有' if prov else '缺'}；`tier_guard` 拒绝读取低档位数据 |")
    for r in spec.get("reviews", []):
        o.append(f"| {r['item']} | 看图：{r['by']} | {r['result']}" + (f"（图：`{r['images']}`）" if r.get("images") else "") + " |")
    for t in spec.get("not_done", []):
        o.append(f"| - | 未做 | {t} |")
    o += ["", "## 逐集", "", "| 集 | 帧数 | 违规帧（上一版） | 首次违规帧（上一版） | IoU 中位（上一版） | 门槛 地面 / 我们的支撑面 | 手 > 3 cm 帧 | 接触帧（上一版） |",
          "|---|---|---|---|---|---|---|---|"]
    for k in sorted(D):
        e, eb = D[k], DB.get(k, {})
        name = next((n for n in A if n.startswith(k)), k)
        iou = f"{A[name]['iou_p50']:.3f} ({AB[name]['iou_p50']:.3f})" if name in A and name in AB else "-"
        hh = H.get(k)
        away = sum(hh[x]["label_on_hand_away"] for x in ("left", "right")) if hh else "-"
        lab = f"{labelled(hh)} ({labelled(HB[k]) if k in HB else '-'})" if hh else "-"
        i = int(k[2:])
        o.append(f"| {name} | {e['frames']} | {e['object_any']} ({eb.get('object_any', '-')}) | {e['first']['object_any']} ({eb.get('first', {}).get('object_any', '-')}) | {iou} | "
                 f"{'过' if gf.get(i) else '不过'} / {'过' if go.get(i) else '不过'} | {away} | {lab} |")
    if spec.get("known_issues"):
        o += ["", "## 已知问题", ""] + [f"- {t}" for t in spec["known_issues"]]
    if spec.get("notes"):
        o += ["", "## 说明", ""] + [f"- {t}" for t in spec["notes"]]
    print("\n".join(o))


if __name__ == "__main__":
    main()
