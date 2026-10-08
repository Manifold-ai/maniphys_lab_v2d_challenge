# stages/recovery

Tier 2 的轨迹恢复：从带噪的物体轨迹估出更好的物体轨迹，落盘后交给 `retarget`。Tier 1 不经过这一段；Tier 3 从 exo 视频重建，在 [`tier3/`](tier3/)。

**这一段不得读取 Tier 1 的任何数据**，包括作为监督信号、校准参考或验证集（`docs/adr/00002-tier-isolation.md`）。
提交管线与 Tier 2 的评价脚本在入口调 `libs/v2d_infra/tier_guard.py` 的 `forbid_tier1()`。

## 提交管线（v5.4）

| 文件 | 作用 |
|---|---|
| `export_tier2.py` | 入口：`python3 stages/recovery/export_tier2.py v5.4`（必须写明版本，没有默认值），写 `runs/recovery/tier2_v54/episode_XXXXXX.npz` |
| `v51.py` | 降噪：静止判据、静止段积分、支撑面 3 自由度锚定、布朗桥 |
| `t2core.py` | 不读数据的纯函数（积分、修正、桥） |
| `nopen.py` | 不穿地约束 |
| `cleanroom_params.py` | 只用 Tier 2 推出 v5.4 的参数，写 `runs/recovery/cleanroom_params.json` |

交接：`stages/retarget/one.sh` 用 `T2_POSES` 选位姿目录，默认 `tier2_v54`。提交侧 `stages/evaluate/make_frame_references.py` 要求降噪版本是 v5.4。

## 只用 Tier 2 的评价

`t2eval.py` 实现计划 `agent-doc/plan-tier2-denoise-2026-10-04.md` 的 E1–E5 与第 5 节的判据。候选 A1、A1′、B1、C1 都在开关后面，
开关关闭时 v5.4 的输出逐位不变（`t2eval.py` 对每条 episode 与 `runs/recovery/tier2_v54` 比较）。测试：`test_t2eval.py`、`test_tier2_defaults.py`。

## 研发脚本

其余脚本（`denoise_v1.py`–`denoise_v4.py`、`support_bridge*.py`、`overfit_audit.py`、`st_tune.py`、`residual_v51.py`、`fusion_ceiling.py`、
`nopen_eval.py` 等）是 9 月的研发与分析脚本，多数用 Tier 1 打分；`denoise_v1.py` 在 import 时就读 Tier 1 的元数据。它们的结论只作背景，
提交管线与 Tier 2 的评价都不 import 它们。

契约见 [`docs/contracts/recovery.md`](../../docs/contracts/recovery.md)（尚空）。
