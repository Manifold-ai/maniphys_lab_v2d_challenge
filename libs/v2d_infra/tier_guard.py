"""档位隔离的机制守卫：调用 forbid_tier1() 之后，本进程任何读取 Tier 1 目录的动作都会抛错。

CLAUDE.md 要求档位隔离"要有机制守，不能只靠自觉"。规则原文：Tier 2/3 的方法要用
"anything other than the clean trajectory captions provided in Tier 1"。
提交用的 Tier 2/3 管线在入口处调用 forbid_tier1()。

覆盖两条读取路径：
  1. Python 层（open / os.listdir / os.scandir / glob.glob，覆盖 np.load、json、trimesh、glob）：audit hook；
  2. pyarrow 的 C++ 文件系统（pq.read_table / ParquetFile），audit hook 拦不到：包装这两个入口。
audit hook 一旦加上就无法移除（Python 的设计），所以只在提交管线的进程里调用。
"""
import os
import sys

TIER1_DIRNAME = "tier_1_multiview_caption"
TIER2_DIRNAME = "tier_2_synthetic_noise"


class TierAccessError(RuntimeError):
    """故意不继承 OSError：glob 等代码会 except OSError 把错误吞掉、静默返回空结果（Python 3.10 实测）。"""


class Tier1AccessError(TierAccessError):
    pass


def _check(path):
    try:
        p = os.fsdecode(path)
    except TypeError:
        return
    if TIER1_DIRNAME in p:
        raise Tier1AccessError(f"档位隔离：Tier 2/3 管线试图读取 Tier 1 文件 {p}")


def _check_lower(path):
    """Tier 3：Tier 1、Tier 2 都不许读。按字面路径与真实路径各查一次：软链接换个名字也拦得住
    （10-15：一份复制出来的 Tier 1 轨迹换了目录名就绕过了只看字面的检查）。"""
    try:
        p = os.fsdecode(path)
    except TypeError:
        return
    for q in (p, os.path.realpath(p)):
        for name in (TIER1_DIRNAME, TIER2_DIRNAME):
            if name in q:
                raise TierAccessError(f"档位隔离：Tier 3 管线试图读取低档位文件 {p}（{q}）")


def forbid_lower_tiers():
    """Tier 3 管线入口调用：此后本进程读 Tier 1 或 Tier 2 的任何文件都会抛 TierAccessError。
    复制出来、换了名字的数据拦不住，那要靠 t3_provenance 记录的输入清单。"""
    _install(_check_lower)


def forbid_tier1():
    _install(_check)


def _install(check):
    def hook(event, args):
        if event in ("open", "os.listdir", "os.scandir", "glob.glob", "glob.glob/2") and args:
            check(args[0])
    sys.addaudithook(hook)
    try:
        import pyarrow.parquet as pq
    except ImportError:   # 没装 pyarrow 的解释器（例如 ml40 宿主）读不了 parquet，只需 audit hook
        return
    for name in ("read_table", "ParquetFile"):
        orig = getattr(pq, name)
        if check in getattr(orig, "_tier_checks", ()):  # 同一种检查只包一层；不同检查叠加（先 tier1 再 lower 两个都生效）
            continue
        def guarded(source, *a, _orig=orig, _check=check, **k):
            if isinstance(source, (str, bytes, os.PathLike)):
                _check(source)
            return _orig(source, *a, **k)
        guarded._tier_guarded = True
        guarded._tier_checks = (*getattr(orig, "_tier_checks", ()), check)
        setattr(pq, name, guarded)
