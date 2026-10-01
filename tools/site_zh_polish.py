"""SOP 单页站点中文表述润色的辅助工具（Mac 上跑，只用标准库）。改的只是 l-zh 正文块，其他一律不动。

润色范围：每个 <section class="pg" id="pg-x"> 里的 <div class="pb l-zh"> 正文块（下称“中文块”）。侧栏、英文块、
不带语言类的共用块（任务一览的卡片由 tools/site_task_gallery.py 生成）都在范围外。计划 agent-doc/plan-sop-zh-polish-2026-09-30.md。

子命令：
  extract <html> --out <目录>     每页中文块原样写成 <目录>/<页>.html，另打印逐页统计（汉字数、可疑句式命中数）。
  apply <html> --edits <json> [--select <json>] [--report <json>] [--write]
                                  改动 [{"id", "page", "old", "new", "why"}] 一律对同一份源码定位（不串行叠加）。硬性拒绝：
                                  old 在全文不是恰好一次、不在中文块内、与别的改动重叠、半截标签、碰到锁定元素（标题、th、
                                  .kicker、.pill、.t、.v、站内链接）却没把它原样带进 new、碰到带 jev 分数的句子、所在句子在别页
                                  逐字重复，或受保护记号的序列变了（按顺序比：标签、实体、数字、拉丁字母词、运算符号、汉字数词
                                  加量词、否定与限定词）。软提示：都、全、均、还、也、才的个数变了。
                                  --select 只套用列出的 id；--report 写出逐条结论与整句前后对照（给复核和 jev 用）。
  jevspec --report <json> --ids <json> --out <前缀>
                                  给选中的改动生成两份 tools/jev_claims.py 规格：<前缀>_fwd.json（原句支持新句？查新增与强化）、
                                  <前缀>_rev.json（新句支持原句？查丢失与弱化），各带真假对照。
  check <html> [--base <git 版本>] 与 git 版本（默认 HEAD）比：中文块以外逐字节相同；每块受保护记号序列不变；锁定元素与
                                  带 jev 分数的句子逐字不变。全过打印 ZH_POLISH_OK。

用法：python3 tools/site_zh_polish.py check docs/site/v2d-track2.html
"""
import argparse
import collections
import html
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
LOCK_TAGS = {"h1", "h2", "h3", "h4", "th"}
LOCK_CLASSES = {"kicker", "pill", "t", "v"}
# 否定、确定程度与归因：按出现顺序整体保护（多字的排在前面，先匹配长的）
HEDGES = ["按我们的理解", "未核实", "未验证", "没验证", "没核实", "待确认", "事后描述", "事后", "推测", "推断", "估计", "估算",
          "可能", "或许", "也许", "大约", "左右", "至少", "最多", "超过", "不到", "以上", "以下", "还没", "尚未",
          "不", "没", "未", "无", "非", "已", "尚", "仍", "只", "仅", "约"]
SOFT = ["都", "全", "均", "还", "也", "才"]
CN_NUM = r"(?:第)?[一二三四五六七八九十两百千万亿半]+(?=[条个份次台张页块倍种轮批段帧步天小时分钟秒周组项点处位名维层类遍成])"
SYMBOLS = r"[≥≤±−+%×=<>~≈→/′″·]"
PATTERNS = {
    "进行": r"进行",
    "对…进行": r"对[^，。；：]{1,20}进行",
    "被字句": r"被",
    "三连的": r"的[^，。；：、（）]{0,8}的[^，。；：、（）]{0,8}的",
    "不是…而是/不仅…更": r"不是[^。；]{1,30}而是|不仅[^。；]{1,30}(更|还|也)",
    "铺垫/预告": r"接下来|让我们|下面(我们)?(来)?(看|说)|值得注意|需要注意的是|值得一提|需要指出",
    "套话收尾": r"综上|总之|总而言之|总的来说|由此可见",
    "高频词": r"赋能|至关重要|深入探讨|无缝|彰显|闭环|抓手",
    "破折号": r"——",
}
TERMINATORS = "。；！？"
OPEN_BLOCKS = ("<p", "<li", "<td", "<br", "<div", "<blockquote", "<ul", "<ol", "<tr")
CLOSE_BLOCKS = ("</p>", "</li>", "</td>", "<br", "</div>", "</blockquote>", "<ul", "<ol", "</ul>", "</ol>")


def line_offsets(s: str) -> list:
    offs, pos = [0], 0
    for line in s.splitlines(keepends=True):
        pos += len(line)
        offs.append(pos)
    return offs


class Regions(HTMLParser):
    """每页中文块（div.pb.l-zh）的 [起, 止)，以及块里锁定元素与 jev 分数 span 的区间。"""

    def __init__(self, src: str) -> None:
        super().__init__(convert_charrefs=False)
        self.src, self.offs = src, line_offsets(src)
        self.stack = []
        self.page = None
        self.page_depth = 0
        self.regions = []        # (页, 起, 止)
        self.locked = []         # (起, 止)
        self.jv = []             # (起, 止)
        self._open = None
        self._pending = []       # (种类, 起, 深度)

    def _pos(self) -> int:
        line, col = self.getpos()
        return self.offs[line - 1] + col

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = set((a.get("class") or "").split())
        start = self._pos()
        if tag == "section" and "pg" in classes and (a.get("id") or "").startswith("pg-"):
            self.page, self.page_depth = a["id"][3:], len(self.stack) + 1
        if tag in VOID:
            return
        self.stack.append(tag)
        depth = len(self.stack)
        if tag == "div" and {"pb", "l-zh"} <= classes and self.page and self._open is None:
            self._open = (self.page, start, depth)
        if self._open:
            if tag in LOCK_TAGS or classes & LOCK_CLASSES or (tag == "a" and (a.get("href") or "").startswith("#")):
                self._pending.append(("lock", start, depth))
            if tag == "span" and "jv" in classes:
                self._pending.append(("jv", start, depth))

    def handle_endtag(self, tag):
        if tag in VOID or not self.stack:
            return
        depth = len(self.stack)
        start = self._pos()
        end = self.src.index(">", start) + 1
        while self._pending and self._pending[-1][2] == depth:
            kind, s, _ = self._pending.pop()
            (self.locked if kind == "lock" else self.jv).append((s, end))
        if self._open and self._open[2] == depth:
            self.regions.append((self._open[0], self._open[1], end))
            self._open = None
        if tag == "section" and depth == self.page_depth:
            self.page = None
        self.stack.pop()


def parse(src: str) -> Regions:
    p = Regions(src)
    p.feed(src)
    p.close()
    return p


def visible(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s))


def protected_seq(s: str) -> list:
    """按出现顺序的受保护记号：标签、实体、<code> 内容，以及标签外文字里的数字、拉丁字母词、运算符号、汉字数词加量词、否定与限定词。"""
    out = []
    pos = 0
    hedge_rx = "|".join(map(re.escape, HEDGES))
    text_rx = re.compile(rf"(\d+(?:[.,:/]\d+)*|[０-９]+|&[a-zA-Z#0-9]+;|[A-Za-z_][A-Za-z0-9_\-']*|{CN_NUM}|{hedge_rx}|{SYMBOLS})")
    for m in re.finditer(r"<[^>]+>", s):
        out.extend("t:" + x for x in text_rx.findall(s[pos:m.start()]))
        out.append("tag:" + m.group(0))
        pos = m.end()
    out.extend("t:" + x for x in text_rx.findall(s[pos:]))
    return out


def soft_counts(s: str) -> collections.Counter:
    t = visible(s)
    return collections.Counter({w: t.count(w) for w in SOFT if t.count(w)})


def seq_diff(a: list, b: list) -> str:
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    return f"第 {i} 个记号起不同：原 {a[i:i + 3]} → 新 {b[i:i + 3]}"


def region_of(regions: list, s: int, e: int):
    for page, rs, re_ in regions:
        if rs <= s and e <= re_:
            return page, rs, re_
    return None


def sentence_bounds(src: str, s: int, e: int, rs: int, re_: int) -> tuple:
    """把 [s, e) 扩到所在整句：向前到上一个句末标点或块级标签，向后到下一个句末标点或块级标签。"""
    left = rs
    for t in TERMINATORS:
        k = src.rfind(t, rs, s)
        if k >= 0:
            left = max(left, k + 1)
    for t in OPEN_BLOCKS:
        k = src.rfind(t, rs, s)
        if k >= 0:
            left = max(left, src.index(">", k) + 1)
    right = re_
    for t in TERMINATORS:
        k = src.find(t, e, re_)
        if k >= 0:
            right = min(right, k + 1)
    for t in CLOSE_BLOCKS:
        k = src.find(t, e, re_)
        if k >= 0:
            right = min(right, k)
    return min(left, s), max(right, e)


def frozen_sentences(src: str, p: Regions) -> list:
    out = []
    for s, e in p.jv:
        r = region_of(p.regions, s, e)
        if r:
            out.append(sentence_bounds(src, s, e, r[1], r[2]))
    return out


def overlaps(a: tuple, b: tuple) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def cmd_extract(a) -> int:
    src = Path(a.html).read_text(encoding="utf-8")
    p = parse(src)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    per = collections.OrderedDict()
    for page, s, e in p.regions:
        per.setdefault(page, []).append(src[s:e])
    total = collections.Counter()
    print("页 | 汉字 | 超过 120 字的句子 | " + " | ".join(PATTERNS))
    for page, blocks in per.items():
        body = "\n".join(blocks)
        (out / f"{page}.html").write_text(body, encoding="utf-8")
        text = re.sub(r"<[^>]+>", "", body)
        han = len(re.findall(r"[一-鿿]", text))
        long_ = sum(1 for x in re.split(r"[。；！？\n]", text) if len(re.findall(r"[一-鿿]", x)) > 120)
        hits = [len(re.findall(rx, text)) for rx in PATTERNS.values()]
        total.update({"汉字": han, "长句": long_, **{k: h for k, h in zip(PATTERNS, hits)}})
        print(f"{page} | {han} | {long_} | " + " | ".join(map(str, hits)))
    print(f"合计 {len(per)} 页 | " + "，".join(f"{k} {v}" for k, v in total.items()))
    return 0


def judge(src: str, p: Regions, frozen: list, sentences_by_page: dict, ed: dict, taken: list):
    """返回 (拒绝理由或 None, 区间, 提示, 整句前后)。"""
    old, new = ed["old"], ed["new"]
    if old == new:
        return "old 与 new 相同", None, "", None
    n = src.count(old)
    if n != 1:
        return f"old 在全文出现 {n} 次（要恰好 1 次）", None, "", None
    s = src.index(old)
    span = (s, s + len(old))
    r = region_of(p.regions, *span)
    if r is None:
        return "不在中文块内（或跨块）", span, "", None
    page, rs, re_ = r
    if ed.get("page") and ed["page"] != page:
        return f"页不符：标的是 {ed['page']}，实际在 {page}", span, "", None
    for x in (old, new):
        if "<" in re.sub(r"<[^>]*>", "", x) or ">" in re.sub(r"<[^>]*>", "", x):
            return "含半截标签", span, "", None
    for t in taken:
        if overlaps(span, t):
            return "与别的改动重叠", span, "", None
    for ls, le in p.locked:
        if overlaps(span, (ls, le)):
            if not (span[0] <= ls and le <= span[1]):
                return f"部分碰到锁定元素 {src[ls:le][:40]!r}", span, "", None
            if new.count(src[ls:le]) != old.count(src[ls:le]):
                return f"锁定元素没有原样保留 {src[ls:le][:40]!r}", span, "", None
    for fs, fe in frozen:
        if overlaps(span, (fs, fe)):
            return f"碰到带 jev 分数的句子 {visible(src[fs:fe])[:30]!r}", span, "", None
    ss, se = sentence_bounds(src, span[0], span[1], rs, re_)
    sent_old = src[ss:se]
    sent_new = src[ss:span[0]] + new + src[span[1]:se]
    key = visible(sent_old).strip()
    if len(key) >= 12 and any(key in t for pg, t in sentences_by_page.items() if pg != page):
        return "所在句子在别页逐字重复（跨页统一处理，不单改）", span, "", None
    a_, b_ = protected_seq(sent_old), protected_seq(sent_new)
    if a_ != b_:
        return "受保护记号序列变了：" + seq_diff(a_, b_), span, "", None
    lost, gained = soft_counts(old) - soft_counts(new), soft_counts(new) - soft_counts(old)
    note = ""
    if lost or gained:
        note = "范围词个数变了：" + "，".join([f"少{k}×{v}" for k, v in lost.items()] + [f"多{k}×{v}" for k, v in gained.items()])
    return None, span, note, {"old_sentence": sent_old, "new_sentence": sent_new,
                              "old_text": visible(sent_old).strip(), "new_text": visible(sent_new).strip()}


def cmd_apply(a) -> int:
    path = Path(a.html)
    src = path.read_text(encoding="utf-8")
    edits = json.loads(Path(a.edits).read_text(encoding="utf-8"))
    ids = [e["id"] for e in edits]
    if len(ids) != len(set(ids)):
        print("id 重复：" + ", ".join(k for k, v in collections.Counter(ids).items() if v > 1))
        return 2
    if a.select:
        keep = set(json.loads(Path(a.select).read_text(encoding="utf-8")))
        edits = [e for e in edits if e["id"] in keep]
    p = parse(src)
    frozen = frozen_sentences(src, p)
    sentences_by_page = {}
    for page, s, e in p.regions:
        sentences_by_page[page] = sentences_by_page.get(page, "") + visible(src[s:e])
    taken, accepted, report = [], [], []
    for ed in edits:
        why, span, note, ctx = judge(src, p, frozen, sentences_by_page, ed, taken)
        row = {"id": ed["id"], "page": ed.get("page"), "why": ed.get("why"), "old": ed["old"], "new": ed["new"],
               "status": "accepted" if why is None else "rejected", "reason": why, "note": note}
        if ctx:
            row.update(ctx)
        report.append(row)
        if why is None:
            taken.append(span)
            accepted.append((span, ed["new"]))
            print(f"[收] {ed['id']} {ed.get('page', '?')}" + (f"（{note}）" if note else ""))
        else:
            print(f"[拒] {ed['id']} {ed.get('page', '?')}：{why}")
    print(f"收 {len(accepted)} 条，拒 {len(report) - len(accepted)} 条")
    if a.report:
        Path(a.report).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.write:
        for (s, e), new in sorted(accepted, reverse=True):
            src = src[:s] + new + src[e:]
        path.write_text(src, encoding="utf-8")
        print(f"已写回 {path}")
    return 0 if len(accepted) == len(report) else 1


CONTROLS = [
    # (原句, 改句, 正向期望, 反向期望)。正向 = 原句支持改句（查新增与强化），反向 = 改句支持原句（查丢失与弱化）；None 表示这个方向不用。
    # 矛盾类在两个方向都是假；“丢信息”只在反向是假，“加信息”只在正向是假。
    ("截至 9/30 14:40，第 1 批 21 条全部结束。", "第 1 批的 21 条在 9/30 14:40 之前全部结束。", "true", "true"),
    ("下一批先写计划、review 再开跑。", "下一批开跑前，先写计划并经过 review。", "true", "true"),
    ("参考物体在第 0 帧就已嵌进立方体（未核实）。", "参考物体在第 0 帧就已嵌进立方体，这一点已经核实。", "false", "false"),
    ("对策会偏离配方，要另写计划登记，还没做。", "对策不偏离配方，已经做完。", "false", "false"),
    ("ml40 跑完诊断队列后空闲，mf4090 还在跑第 1 批。", "mf4090 跑完诊断队列后空闲，ml40 还在跑第 1 批。", "false", "false"),
    ("v0.4.0 的导入器把方盒建成立方体，参考物体埋在立方体里。", "参考物体把立方体埋在方盒里，导入器没有出错。", "false", "false"),
    ("第 1 批里有三条序列的支撑面是方盒。", "第 1 批里只有一条序列的支撑面是方盒。", "false", "false"),
    ("ep1 变慢的起点与出 NaN 重合，原来的推测撤回。", "ep1 变慢导致了 NaN，原来的推测成立。", "false", "false"),
    ("ml40 和 mf4090 都空闲，都没有排任务。", "ml40 空闲。", None, "false"),
    ("ep7 冒烟发散了。", "ep7 冒烟因为导入器的错误在第 5000 万步发散了。", "false", None),
]


def cmd_jevspec(a) -> int:
    report = {r["id"]: r for r in json.loads(Path(a.report).read_text(encoding="utf-8"))}
    ids = json.loads(Path(a.ids).read_text(encoding="utf-8"))
    for direction in ("fwd", "rev"):
        ev, claims = {}, []
        for i, (o, n, cf, cr) in enumerate(CONTROLS):
            c = cf if direction == "fwd" else cr
            if c is None:
                continue
            src_, claim = (o, n) if direction == "fwd" else (n, o)
            ev[f"ctl{i}"] = {"text": src_}
            claims.append({"id": f"ctl{i}", "evidence": [f"ctl{i}"], "claim": claim, "control": c})
        for k in ids:
            r = report[k]
            src_, claim = (r["old_text"], r["new_text"]) if direction == "fwd" else (r["new_text"], r["old_text"])
            ev[k] = {"text": src_}
            claims.append({"id": k, "evidence": [k], "claim": claim})
        out = Path(f"{a.out}_{direction}.json")
        out.write_text(json.dumps({"model": "jev-1.13.0", "evidence": ev, "claims": claims}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"写出 {out}：{len(ids)} 条改动 + {len(claims) - len(ids)} 条对照")
    return 0


def skeleton(src: str, regions: list) -> str:
    out, pos = [], 0
    for page, s, e in regions:
        out.append(src[pos:s])
        out.append(f"<<ZH:{page}>>")
        pos = e
    out.append(src[pos:])
    return "".join(out)


def cmd_check(a) -> int:
    new = Path(a.html).read_text(encoding="utf-8")
    old = subprocess.run(["git", "show", f"{a.base}:{a.html}"], capture_output=True, text=True, check=True).stdout
    po, pn = parse(old), parse(new)
    problems = []
    if [r[0] for r in po.regions] != [r[0] for r in pn.regions]:
        problems.append("中文块的页序列变了")
    if skeleton(old, po.regions) != skeleton(new, pn.regions):
        problems.append("中文块以外的内容变了")
    changed = 0
    for (page, s0, e0), (_, s1, e1) in zip(po.regions, pn.regions):
        b0, b1 = old[s0:e0], new[s1:e1]
        if b0 != b1:
            changed += 1
            a_, b_ = protected_seq(b0), protected_seq(b1)
            if a_ != b_:
                problems.append(f"{page}：受保护记号序列变了：{seq_diff(a_, b_)}")
    if [old[s:e] for s, e in po.locked] != [new[s:e] for s, e in pn.locked]:
        problems.append("锁定元素（标题、th、.kicker、.pill、.t、.v、站内链接）变了")
    if [old[s:e] for s, e in frozen_sentences(old, po)] != [new[s:e] for s, e in frozen_sentences(new, pn)]:
        problems.append("带 jev 分数的句子变了")
    print(f"中文块 {len(pn.regions)} 个，改动 {changed} 个；锁定元素 {len(pn.locked)} 个，jev 分数 {len(pn.jv)} 个")
    for p in problems:
        print("问题：" + p)
    print("ZH_POLISH_OK" if not problems else f"ZH_POLISH_PROBLEMS {len(problems)}")
    return 0 if not problems else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("html")
    e.add_argument("--out", required=True)
    p = sub.add_parser("apply")
    p.add_argument("html")
    p.add_argument("--edits", required=True)
    p.add_argument("--select")
    p.add_argument("--report")
    p.add_argument("--write", action="store_true")
    j = sub.add_parser("jevspec")
    j.add_argument("--report", required=True)
    j.add_argument("--ids", required=True)
    j.add_argument("--out", required=True)
    c = sub.add_parser("check")
    c.add_argument("html")
    c.add_argument("--base", default="HEAD")
    a = ap.parse_args()
    return {"extract": cmd_extract, "apply": cmd_apply, "jevspec": cmd_jevspec, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
