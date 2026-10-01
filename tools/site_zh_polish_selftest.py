"""tools/site_zh_polish.py apply 的自检：会改变意思的改动必须被拒，正常的句法改动必须能过（Mac 上跑，只用标准库）。

坏改动取自计划审阅时在副本里试出的 16 条漏网改动（agent-doc/plan-sop-zh-polish-2026-09-30.md“审阅与处理”），每条单独送进 apply，
保证拒绝来自它自己的问题，而不是和别条重叠。好改动是两条真实的句法修改。对象是当前的 docs/site/v2d-track2.html（只读）。
全部符合预期打印 SELFTEST_OK。

用法：python3 tools/site_zh_polish_selftest.py
  落盘：scripts/dev/record site/zh_polish_selftest python3 tools/site_zh_polish_selftest.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HTML = "docs/site/v2d-track2.html"
BAD = [
    ("数字对调", "v0.4.0 的导入器 5 / 8 发散，换上 #185 0 / 8", "v0.4.0 的导入器 0 / 8 发散，换上 #185 5 / 8"),
    ("比较符翻转", "MP-SR ≥ 0.95 的 5 条、0.5–0.95 的 2 条", "MP-SR ≤ 0.95 的 5 条、0.5–0.95 的 2 条"),
    ("汉字数词", "无效的三条都用方盒支撑面", "无效的两条都用方盒支撑面"),
    ("万", "支持：ep7 冒烟（400 万步", "支持：ep7 冒烟（400 步"),
    ("否定辖域", "而 ep7 在这种几何上的 13 条冒烟没有一条学起来", "而 ep7 在这种几何上的 13 条冒烟有一条没学起来"),
    ("限定词挪位", "所以至少 ep7 交不出有意义的轨迹", "所以 ep7 交不出至少有意义的轨迹"),
    ("jev 分数换句", "，是写错了文件）<span class=\"jv\">jev 0.81</span>。", "<span class=\"jv\">jev 0.81</span>，是写错了文件）。"),
    ("改标题", "<h2>现在要做的三件事</h2>", "<h2>现在要做的事</h2>"),
    ("标签错嵌", "<b><a href=\"#diverge\">给组委会发方盒三条的问题</a></b>", "<b>给组委会发<a href=\"#diverge\">方盒三条的问题</b></a>"),
    ("&gt; 改 &gt;=", "的判据（chord_sr &gt; 0、MP-SR &gt; 0", "的判据（chord_sr &gt;= 0、MP-SR &gt; 0"),
    ("删负号", "秩相关 −0.69、−0.65", "秩相关 0.69、0.65"),
    ("链接包错字", "见<a href=\"#diverge\">发散排查</a>。</li>", "<a href=\"#diverge\">见</a>发散排查。</li>"),
    ("删未核实", "参考物体在第 0 帧就已嵌进立方体（未核实）", "参考物体在第 0 帧就已嵌进立方体"),
    ("改链接文字", "<li><a href=\"#batch1\">第 1 批批量</a></li><li><a href=\"#diverge\">发散排查</a></li></ul></section>",
     "<li><a href=\"#batch1\">第 1 批批量训练</a></li><li><a href=\"#diverge\">发散排查</a></li></ul></section>"),
    ("属性引号", "<p class=\"lead\">截至 9/30 14:40", "<p class=lead>截至 9/30 14:40"),
    ("已改未", "上游 #185 已修。", "上游 #185 未修。"),
    ("半截标签", "lead\">截至 9/30 14:40", "lead>截至 9/30 14:40"),
]
GOOD = [
    ("“是”连用", "能下的结论是 v0.4.0 把方盒建成 1 m 立方体是 ep7 冒烟发散的触发",
     "能下的结论是：v0.4.0 把方盒建成 1 m 立方体，触发了 ep7 冒烟的发散"),
    ("并列不对称", "还差组委会的答复、按 9/30 重新下载的新 kit 接上评测与打包、每条选 checkpoint，以及 Kaggle 的规则与凭据",
     "还差四件事：组委会的答复、按 9/30 重新下载的新 kit 接上评测与打包、为每条选定 checkpoint，以及 Kaggle 的规则与凭据"),
]


def run(edits: list) -> tuple:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(edits, f, ensure_ascii=False)
    r = subprocess.run([sys.executable, "tools/site_zh_polish.py", "apply", HTML, "--edits", f.name],
                       capture_output=True, text=True)
    Path(f.name).unlink()
    return r.returncode, r.stdout.strip().splitlines()[0] if r.stdout.strip() else r.stderr.strip()


def main() -> int:
    bad = 0
    for name, old, new in BAD:
        code, line = run([{"id": name, "old": old, "new": new}])
        ok = code != 0 and line.startswith("[拒]")
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} 坏改动应拒 | {name} | {line}")
    for name, old, new in GOOD:
        code, line = run([{"id": name, "old": old, "new": new}])
        ok = code == 0 and line.startswith("[收]")
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} 好改动应收 | {name} | {line}")
    print("SELFTEST_OK" if not bad else f"SELFTEST_FAILED {bad}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
