# 契约：轨迹恢复（recovery）

边界：`stages/recovery`：Tier 2 从带噪轨迹、Tier 3 从 exo 视频，估出人体与物体轨迹，按 `data.md` 的 schema 落盘。Tier 1 不经过这一面。

**契约 ID**：`RECOVERY-<层><序号>`，层用 U / C / D / I。Caller 已有 RECOVERY-C001–C003；其余表空白，上游 ADR 未定，条目待填。

## User-facing

| ID | 主题 | 交付 | 验证 | 审阅 | 状态 |
|---|---|---|---|---|---|

## Caller

| ID | 主题 | 交付 | 验证 | 审阅 | 状态 |
|---|---|---|---|---|---|
| RECOVERY-C001 | silhouette pose choice | choose_pose accepts only when the best median is at least 0.5, the gain over current is at least 0.05, and the gap over the second best is at least 0.05 (min_gain may be raised by the caller), using the plan check order; right_multiply right-multiplies and does not change translation. | `stages/recovery/tier3/test_t3_sil_choose.py` | 待审 | 已实现 |
| RECOVERY-C002 | silhouette decision units | units: every unheld run is one unit and a held run splits only at single-frame turns above 24 deg; units cover every frame once; candidate turns are about the centre of mass and exclude shape symmetries; the null control holds only turns the silhouette cannot see; units with fewer than 10 evidence frames are refused. | `stages/recovery/tier3/test_t3_fix_units.py` | 待审 | 已实现 |
| RECOVERY-C003 | motion before contact | an unheld run is drift only when the reference moves more than 3 cm, the object mask keeps its centroid within 15 px, IoU 0.8 and area within 5 %, and one frozen pose fits the video no worse on every evidence frame; a moving mask is hand_late and the object is left alone. | `stages/recovery/tier3/test_t3_fix_onset.py` | 待审 | 已实现 |
| RECOVERY-C004 | texture orientation choice | the point-splat render puts each surface sample's texture colour on its projected pixel (pixel centres as rasterise) and keeps the nearest sample, and a glb round trip keeps the texture orientation; scores are the per-channel YCrCb NCC over the channels with enough contrast; a segment between two rotation jumps (not cut inside an untouched run) switches only if, in each variant, the best pose is a candidate with at least 3 full blocks, median at least 0.3, a lead of at least 0.05 over current and the non-neighbour candidates, a block-bootstrap lower bound above 0 and the top place in at least 2/3 of the blocks, and both variants pick the same candidate. | `stages/recovery/tier3/test_t3_tex.py` | 待审 | 已实现 |

## Data

| ID | 主题 | 交付 | 验证 | 审阅 | 状态 |
|---|---|---|---|---|---|

## Internal

| ID | 主题 | 交付 | 验证 | 审阅 | 状态 |
|---|---|---|---|---|---|

## 非目标

待填。
