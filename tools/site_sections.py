"""SOP 页面按分区拆开与拼回（Mac 上跑，只用标准库）。分批精简整理页面时，每个分区单独成一个片段文件，改完再按原顺序拼回。
split：docs/site/v2d-track2.html → <目录>/00_head.html、<序号>_<分区 id>.html …（每个片段从 `<section class="pg" id=…>` 开始，到下一个分区之前）；拼回逐字节等于原文件（自检）。
join：按文件名顺序拼回，写到给定的输出路径。
check：比较两份页面的元素 id 集合、href="#…" 锚点集合与几种标签的开闭数，打印差异；页面规则的禁用词（jev、Fable、Opus、用户、我们 等）在正文里的出现次数。
用法：python3 tools/site_sections.py split <页面> <目录> | join <目录> <输出> | check <旧页面> <新页面>   最后一行 SITE_SECTIONS_OK 或 SITE_SECTIONS_FAIL
"""
import re
import sys
from pathlib import Path

SEC = re.compile(r'<section class="pg" id="(pg-[a-z0-9-]+)"')
BANNED = ["jev", "claim", "Fable", "Opus", "GO WITH FIXES", "MAJOR", "用户", "coding agent", "我们", "同组成员", "同事", "teammate", " we ", " our ", "We ", "Our "]
TAGS = ["section", "div", "table", "ul", "ol", "li", "p", "tr", "td", "th", "h1", "h2", "h3", "details", "summary"]


def split(page: Path, out: Path) -> int:
    s = page.read_text(encoding="utf-8")
    starts = [(m.start(), m.group(1)) for m in SEC.finditer(s)]
    out.mkdir(parents=True, exist_ok=False)
    parts = [("00_head", s[: starts[0][0]])]
    for i, (a, name) in enumerate(starts):
        b = starts[i + 1][0] if i + 1 < len(starts) else len(s)
        parts.append((f"{i + 1:02d}_{name}", s[a:b]))
    for name, text in parts:
        (out / f"{name}.html").write_text(text, encoding="utf-8")
    back = "".join((out / f"{n}.html").read_text(encoding="utf-8") for n, _ in parts)
    ok = back == s
    print(f"拆成 {len(parts)} 个片段到 {out}；拼回逐字节相同：{ok}")
    return 0 if ok else 1


def join(src: Path, out: Path) -> int:
    files = sorted(src.glob("*.html"))
    out.write_text("".join(f.read_text(encoding="utf-8") for f in files), encoding="utf-8")
    print(f"按顺序拼了 {len(files)} 个片段 → {out}")
    return 0


def text_of(s: str) -> str:
    s = re.sub(r"<style.*?</style>|<script.*?</script>", "", s, flags=re.S)
    return re.sub(r"<[^>]+>", " ", s)


def check(old: Path, new: Path) -> int:
    a, b = old.read_text(encoding="utf-8"), new.read_text(encoding="utf-8")
    bad = 0
    ida, idb = set(re.findall(r'\bid="([^"]+)"', a)), set(re.findall(r'\bid="([^"]+)"', b))
    hra, hrb = set(re.findall(r'href="#([A-Za-z0-9_-]+)"', a)), set(re.findall(r'href="#([A-Za-z0-9_-]+)"', b))
    print(f"元素 id：旧 {len(ida)}、新 {len(idb)}；新里少了 {sorted(ida - idb)}；多了 {sorted(idb - ida)}")
    dangling = sorted(h for h in hrb if h not in idb and f"pg-{h}" not in idb)
    print(f"锚点：旧 {len(hra)}、新 {len(hrb)}；新页面里指向不存在的 id：{dangling}")
    bad += bool(ida - idb) + bool(dangling)
    for t in TAGS:
        o, c = len(re.findall(rf"<{t}[\s>]", b)), len(re.findall(rf"</{t}>", b))
        if o != c and t not in ("li", "p", "td", "th", "tr"):
            print(f"标签 <{t}> 开 {o}、闭 {c}，不平衡")
            bad += 1
    tb = text_of(b)
    hits = {w: tb.count(w) for w in BANNED if tb.count(w)}
    print(f"正文禁用词（新页面）：{hits or '无'}；旧页面：{ {w: text_of(a).count(w) for w in BANNED if text_of(a).count(w)} or '无'}")
    print(f"正文字符：旧 {len(text_of(a))}、新 {len(tb)}")
    print("SITE_SECTIONS_OK" if bad == 0 else f"SITE_SECTIONS_FAIL {bad}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "split":
        sys.exit(split(Path(sys.argv[2]), Path(sys.argv[3])))
    if cmd == "join":
        sys.exit(join(Path(sys.argv[2]), Path(sys.argv[3])))
    if cmd == "check":
        sys.exit(check(Path(sys.argv[2]), Path(sys.argv[3])))
    sys.exit("用法见文件开头")
