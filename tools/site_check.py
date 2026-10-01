"""检查 SOP 单页站点（docs/site/*.html）的结构，发布前跑一遍。只用标准库。

查四件事（给了 --media-dir 时查第五件）：
  1. 非空元素的开闭标签配对（按嵌套顺序；void 元素与自闭合写法跳过）；
  2. 站内链接 href="#x" 都指向存在的页（页面 id 是 pg-x，路由 token 不带前缀；或页内另有 id="x" 的元素）；
  3. 每个 <section class="pg" id="pg-x"> 在侧栏里都有 #x 链接（翻页顺序取自侧栏，漏了就翻不到）；
  4. 每页都有中文（l-zh）和英文（l-en）两块；
  5. 页面里 src / poster / data-src 引用的 media/... 素材都在 --media-dir 里（素材不进 git，发布时经 Artifact files 上传）。
有问题逐条打印并以退出码 1 结束；全过打印 SITE_OK。

用法：python3 tools/site_check.py docs/site/v2d-track2.html [--media-dir runs/site_media]
"""
import re
from pathlib import Path
import sys
from html.parser import HTMLParser

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class Checker(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, int]] = []
        self.problems: list[str] = []
        self.ids: set[str] = set()
        self.hrefs: list[tuple[str, int]] = []
        self.pages: list[str] = []
        self.side_links: list[str] = []
        self.in_side = 0
        self.page_langs: dict[str, set[str]] = {}
        self.current_page: str | None = None
        self.page_depth = 0
        self.media: list[tuple[str, int]] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        line = self.getpos()[0]
        if a.get("id"):
            self.ids.add(a["id"])
        for k in ("src", "poster", "data-src"):
            if (a.get(k) or "").startswith("media/"):
                self.media.append((a[k], line))
        if tag == "a" and (a.get("href") or "").startswith("#"):
            self.hrefs.append((a["href"][1:], line))
            if self.in_side:
                self.side_links.append(a["href"][1:])
        if tag == "section" and "pg" in (a.get("class") or "").split() and (a.get("id") or "").startswith("pg-"):
            self.current_page = a["id"][3:]
            self.pages.append(self.current_page)
            self.page_langs[self.current_page] = set()
            self.page_depth = len(self.stack) + 1
        if self.current_page and tag == "div":
            classes = (a.get("class") or "").split()
            for lang in ("l-zh", "l-en"):
                if lang in classes:
                    self.page_langs[self.current_page].add(lang)
        if tag == "nav" and a.get("id") == "side":
            self.in_side = len(self.stack) + 1
        if tag not in VOID:
            self.stack.append((tag, line))

    def handle_startendtag(self, tag, attrs):
        # 自闭合写法（如 <line .../>）不入栈，但 id 与链接照样收集
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])

    def handle_endtag(self, tag):
        line = self.getpos()[0]
        if tag in VOID:
            return
        if not self.stack:
            self.problems.append(f"第 {line} 行：多余的 </{tag}>")
            return
        open_tag, open_line = self.stack[-1]
        if open_tag != tag:
            self.problems.append(f"第 {line} 行：</{tag}> 与第 {open_line} 行的 <{open_tag}> 不配对")
            # 尽量恢复：向下找同名开标签
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]
                    break
        else:
            self.stack.pop()
        if self.in_side and len(self.stack) < self.in_side:
            self.in_side = 0
        if self.current_page and len(self.stack) < self.page_depth:
            self.current_page = None


def main(path: str, media_dir=None) -> int:
    text = open(path, encoding="utf-8").read()
    c = Checker()
    c.feed(text)
    c.close()
    problems = list(c.problems)
    for tag, line in c.stack:
        problems.append(f"第 {line} 行：<{tag}> 没有闭合")
    pages = set(c.pages)
    for token, line in c.hrefs:
        if token and token not in pages and token not in c.ids and token != "home":
            problems.append(f"第 {line} 行：链接 #{token} 没有对应的页（pg-{token}）或元素")
    side = set(c.side_links)
    for pg in c.pages:
        if pg != "home" and pg not in side:
            problems.append(f"页 pg-{pg} 不在侧栏里，翻页到不了")
        missing = {"l-zh", "l-en"} - c.page_langs.get(pg, set())
        if missing:
            problems.append(f"页 pg-{pg} 缺 {', '.join(sorted(missing))} 块")
    dup = sorted({x for x in c.pages if c.pages.count(x) > 1})
    if dup:
        problems.append(f"重复的页 id：{dup}")
    if media_dir:
        for ref, line in c.media:
            if not (Path(media_dir) / ref[len("media/"):]).is_file():
                problems.append(f"第 {line} 行：素材 {ref} 不在 {media_dir}")
    elif c.media:
        print(f"（页面引用了 {len(c.media)} 个 media/ 素材，没给 --media-dir，未核对）")
    title = re.search(r"<title>([^<]*)</title>", text[:8192])
    print(f"{path}：{len(c.pages)} 页，站内链接 {len(c.hrefs)} 个，侧栏链接 {len(c.side_links)} 个，素材引用 {len(c.media)} 个，标题 {title.group(1) if title else '（无）'}")
    for p in problems:
        print(p)
    if problems:
        return 1
    print("SITE_OK")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    media = None
    if "--media-dir" in args:
        i = args.index("--media-dir")
        media = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        sys.exit("用法：site_check.py <html> [--media-dir <目录>]")
    sys.exit(main(args[0], media))
