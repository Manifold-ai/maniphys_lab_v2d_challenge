"""读 Kaggle 比赛规则页里与分享有关的条款原文（只读；Mac 上执行，训练机连不上 kaggle.com）。

规则页是脚本渲染的，WebFetch 只拿到标题。这里走网页自己用的内部接口（未公开、可能改）：先 GET 规则页拿
XSRF-TOKEN cookie，再 POST competitions.CompetitionService/GetCompetition 取比赛 id，
POST competitions.PageService/ListPages 取各页内容。只打印 rules（比赛方可编辑的部分）与 foundational-rules
（Kaggle 附加、不可编辑的部分）两页：每页的长度与 sha256（以后核对规则有没有改），以及提到分享、
Competition Code、公开、开源、外部数据与预训练模型的段落原文（按空行分段，段内换行并成空格）。不需要登录，不用 Kaggle token。
用户 10/11 回复 HF 归档“不需要private”，改公开之前先核规则（计划 agent-doc/plan-hf-archive-batch3-2026-10-10.md）。

用法：python3 tools/kaggle_rules.py <比赛 slug> [<比赛 slug> ...]
"""
import hashlib
import http.cookiejar
import json
import re
import sys
import urllib.request

PAT = re.compile(r"[Ss]har(?:e|ed|ing)|Competition Code|[Pp]ublicly|[Pp]rivately|[Oo]pen [Ss]ource|External Data|[Pp]re-trained models")


def fetch(slug: str) -> list:
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.open(f"https://www.kaggle.com/competitions/{slug}/rules", timeout=30).read()
    xsrf = next((c.value for c in jar if c.name == "XSRF-TOKEN"), None)
    if not xsrf:
        sys.exit(f"{slug}：规则页没给 XSRF-TOKEN cookie，接口可能改了")

    def post(path: str, body: dict) -> dict:
        req = urllib.request.Request(f"https://www.kaggle.com/api/i/{path}", data=json.dumps(body).encode(),
                                     headers={"content-type": "application/json", "x-xsrf-token": xsrf}, method="POST")
        return json.loads(op.open(req, timeout=30).read())

    comp = post("competitions.CompetitionService/GetCompetition", {"competitionName": slug})
    print(f"## {slug}：id {comp.get('id')}，标题 {comp.get('title')}，截止 {comp.get('deadline')}")
    return post("competitions.PageService/ListPages", {"competitionId": comp["id"]}).get("pages") or []


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit("用法：python3 tools/kaggle_rules.py <比赛 slug> [...]")
    for slug in sys.argv[1:]:
        pages = {p.get("name"): p.get("content") or "" for p in fetch(slug)}
        print(f"各页：{', '.join(f'{k}（{len(v)} 字符）' for k, v in pages.items())}")
        for name in ("rules", "foundational-rules"):
            text = pages.get(name)
            if text is None:
                print(f"### {name}：没有这一页")
                continue
            print(f"### {name}：{len(text)} 字符，sha256 {hashlib.sha256(text.encode()).hexdigest()}")
            for para in re.split(r"\n\s*\n", text):
                para = " ".join(re.sub(r"<[^>]+>", "", para).split())
                if para and PAT.search(para):
                    print(f"- {para}")
    print("KAGGLE_RULES_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
