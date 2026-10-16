"""SOP 单页站点发布前的禁用词检查（Mac 上跑，只用标准库）：页面可见文字里这些词出现几次，与上一版（git 某个提交里的同一文件）比。
页面规则（定时更新的任务里写明）：不写 jev、claim、Fable、Opus、review、审查、用户、user、coding agent、原文；人称规则：不写 我们、同组成员、
teammate、we、our。有的词在旧内容里本来就有（如引用的英文原句、文件名），所以这里只管“比上一版多出来的”：逐词打印两版的次数，
次数变多的词打印新版里每一处的上下文，由人判断是不是规则管的、要不要改。
可见文字：去掉 <script>、<style> 的内容与所有标签，解开 HTML 实体；<code> 里的路径也算（页面上看得到）。
英文词按整词、不分大小写匹配（we、our、user、claim、review 带常见词尾）；中文词按子串匹配。
用法：python3 tools/site_banned_words.py docs/site/v2d-track2.html [--base HEAD]
最后一行 BANNED_SAME（没有词变多）或 BANNED_MORE <词…>（退出码 1）。
"""
import argparse
import html
import re
import subprocess
import sys
from pathlib import Path

ZH = ["jev", "Fable", "Opus", "审查", "用户", "原文", "我们", "同组成员", "coding agent"]
EN = {"claim": r"claims?", "review": r"review(?:s|ed|er|ers|ing)?", "user": r"users?", "teammate": r"teammates?",
      "we": r"we", "our": r"our"}


def visible(src: str) -> str:
    src = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", src)
    src = re.sub(r"(?s)<[^>]+>", " ", src)
    return html.unescape(src)


def pattern(word: str) -> re.Pattern:
    if word in EN:
        return re.compile(rf"(?i)(?<![A-Za-z]){EN[word]}(?![A-Za-z])")
    return re.compile(re.escape(word), re.I if word.isascii() else 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("html", type=Path)
    ap.add_argument("--base", default="HEAD")
    a = ap.parse_args()
    cur = visible(a.html.read_text(encoding="utf-8"))
    old_src = subprocess.run(["git", "show", f"{a.base}:{a.html.as_posix()}"], capture_output=True, text=True, check=True).stdout
    old = visible(old_src)
    more = []
    print(f"{'词':<14}{a.base:>10}{'现在':>8}")
    for w in ZH + list(EN):
        pat = pattern(w)
        n_old, hits = len(pat.findall(old)), list(pat.finditer(cur))
        print(f"{w:<14}{n_old:>10}{len(hits):>8}")
        if len(hits) > n_old:
            more.append(w)
            for m in hits:
                ctx = re.sub(r"\s+", " ", cur[max(0, m.start() - 40):m.end() + 40])
                print(f"    {w}：…{ctx}…")
    print("BANNED_MORE " + " ".join(more) if more else "BANNED_SAME")
    return 1 if more else 0


if __name__ == "__main__":
    sys.exit(main())
