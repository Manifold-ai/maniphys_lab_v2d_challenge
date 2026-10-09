"""仓内路径解析。脚本不再写死绝对路径。

动机：数据集与上游 toolkit 从 ~/v2d/* 搬进仓库后，写死路径的脚本会静默地
找不到文件。路径从仓库根推导，换机器、换布局都不用改脚本。

档位隔离（见 CLAUDE.md）将来落在这一层：tier() 应当只返回调用方声明的那一档，
让 Tier 2/3 的管线拿不到 Tier 1 的干净轨迹。当前仅做路径解析，未加强制。
"""
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data" / "challenge"
TRACK2 = DATA / "track_2"
TIER1 = TRACK2 / "tier_1_multiview_caption"
TIER2 = TRACK2 / "tier_2_synthetic_noise"
RESULTS = REPO / "results"
RUNS = REPO / "runs"          # 训练与缓存产物，gitignored，rsync 受 P 规则保护
# Tier 3 只发 exo 视频，没有官方的轨迹目录。这里不是官方数据：是从视频重建后拼成的档目录（与 Tier 2 同 schema），
# 由 stages/recovery/tier3_root.py 写（计划 agent-doc/plan-t3-pilot-2026-10-09.md）。
TIER3 = RUNS / "tier3" / "root"
UPSTREAM = REPO / "third_party" / "video_to_data"
SOMA_ASSETS = (UPSTREAM / "robotic_grounding/source/robotic_grounding"
               / "robotic_grounding/assets/body_models/soma")

def tier(n: int) -> Path:
    """按档位号取数据根。不要跨档合并——三档的 episode 与帧号刻意对齐，
    用途是逐帧比较，不是互相补数据。"""
    return {1: TIER1, 2: TIER2, 3: TIER3}[n]
