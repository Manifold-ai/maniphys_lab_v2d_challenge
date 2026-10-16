# Tier 3 交付：`tier3_cari4d_f830_best_dr2s_dyn7`

由 `stages/recovery/tier3/gate/t3_delivery_report.py` 从各项检查的结果文件生成，数字不经手抄。上一个交付版：`tier3_cari4d_f830_best_hm`。

## 这是什么

- 用途：dyn7's dynamics post-process (ebad90b) on the ray-corrected best_dr2s; IoU 0.810 (best 0.810, hm 0.738), 2189 violation frames, 7 clean, airborne 274; gate 30/30 with supports runs/support/tier3_cari4d_f830_best_v3 (centre-of-mass sweep, 1723b15), 29/30 with v2 (ep07). Orientation flips untouched; ep07 iron sinks ~1 cm at the table edge (dr2s made with v2 supports)
- 由 `t3_dynamics_post.py` from `tier3_cari4d_f830_best_dr2s` 生成；代码 3e46ecd6b62b3b3ebc6e6f901c1b20a77119ceb4 dirty=0 (deploy_l40
- 支撑面：`runs/support/tier3_cari4d_f830_best_v3`，写成 usda 放在本版本的 `support_surface/` 下（路径见每集元数据的 `support_surface`）。
- 集数：30（其中 1 集在 `tier3_cari4d_f830_best_dr2s_dyn7_suspect`）。

## 与上一个交付版对比

| 项目 | `tier3_cari4d_f830_best_hm` | `tier3_cari4d_f830_best_dr2s_dyn7` |
|---|---|---|
| 物体动力学违规帧（占比） | 6207 (27.0%) | 2189 (9.5%) |
| 零违规的集 | 0 | 7 |
| 前 30 帧内就违规的集 | 30 | 3 |
| `lin_supported` | 4357 | 398 |
| `lin_airborne` | 496 | 274 |
| `lin_held` | 29 | 12 |
| `rest_drift` | 2853 | 1308 |
| `rot_drift` | 1503 | 1201 |
| `rot_jump` | 696 | 545 |
| `rot_torque` | 924 | 552 |
| 轮廓 IoU（各集中位数的均值，29 集，不含 ep28） | 0.738 | 0.810 |
| IoU < 0.5 的抽样帧 | 810 | 528 |
| 训练前门槛，用我们的支撑面 | 30/30 | 30/30 |
| 标了接触但手离物体 > 3 cm | 0.44% | 0.45% |

门槛只列用我们支撑面判的结果：Tier 3 不能用官方支撑面；只按地面判时，放在桌上的物体必然算悬空。逐集表里的「地面」一列只作参考，hm 那套门槛数据是 10-13 建的、集目录里带着官方支撑面，口径不同。

## 自检（清单见 10-15 定的 13 项）

| # | 项目 | 结果 |
|---|---|---|
| 11 | 数据契约（对照 `tier3_cari4d_f830_best_dr2s`） | 通过；改动的列 ['observation.object.pose'] |
| 2 | 改动审计 | 锁定段外可见改动 > 5 cm 的帧 537；最多的集：ep28_squeegee 263, ep19_cane 117, ep04_baseball_bat 29 |
| 3 | 逐帧画面对齐 | IoU < 0.5 的抽样帧 528（上一交付版 810） |
| 5 | 动力学检查 | 违规帧 2189，见上表 |
| 9 | 手和物体 | 标了接触但手离物体 > 3 cm 的占 0.45% |
| 12 | 来源 | `tier3_cari4d_f830_best_dr2s_dyn7.provenance.json`：有；`tier_guard` 拒绝读取低档位数据 |
| 4 | 看图：用户（10-16） | 16 个对照帧：纸箱、刮水器明显变好，其余差不多，原来错的仍错（如球棒头尾），没有变差（图：`dev/checked_frames/dr2sd7/`） |
| 2 | 看图：用户（10-16） | 改动最大的帧（ep28/19/01/04/14/13/02）整体是变好；ep02 第 395 帧篮子三版都倒置（重建朝向）（图：`dev/checked_frames/audit_dr2sd7/`） |
| - | 未做 | 6 合成轨迹空跑与幂等性（工具未写） |
| - | 未做 | 13 每帧可信度（工具未写） |
| - | 未做 | dr2s 本身由 10-13 的代码 5752307 生成，10-16 用当前代码逐表复现一致 |

## 逐集

| 集 | 帧数 | 违规帧（上一版） | 首次违规帧（上一版） | IoU 中位（上一版） | 门槛 地面 / 我们的支撑面 | 手 > 3 cm 帧 |
|---|---|---|---|---|---|---|
| ep00_tall_bar_stool | 778 | 6 (126) | 704 (0) | 0.845 (0.776) | 过 / 过 | 2 |
| ep01_vacuum | 747 | 82 (261) | 128 (0) | 0.518 (0.506) | 过 / 过 | 8 |
| ep02_blue_easter_basket | 980 | 272 (320) | 171 (7) | 0.790 (0.471) | 过 / 过 | 0 |
| ep03_contigo_coffee_mug | 781 | 30 (165) | 89 (0) | 0.853 (0.802) | 不过 / 过 | 0 |
| ep04_baseball_bat | 803 | 51 (228) | 102 (0) | 0.762 (0.550) | 过 / 过 | 3 |
| ep05_big_black_box | 1003 | 4 (102) | 591 (0) | 0.929 (0.914) | 过 / 过 | 4 |
| ep06_monitor | 546 | 0 (157) | None (4) | 0.770 (0.747) | 不过 / 过 | 1 |
| ep07_iron | 896 | 0 (146) | None (0) | 0.886 (0.871) | 不过 / 过 | 0 |
| ep08_skinny_wood_chair | 708 | 62 (204) | 133 (0) | 0.832 (0.804) | 过 / 过 | 0 |
| ep09_big_red_bowl | 870 | 36 (320) | 233 (0) | 0.810 (0.607) | 过 / 过 | 0 |
| ep10_white_desk | 794 | 14 (114) | 82 (0) | 0.743 (0.695) | 过 / 过 | 1 |
| ep11_light_blue_book | 901 | 52 (87) | 134 (0) | 0.763 (0.641) | 过 / 过 | 3 |
| ep12_black_platform | 700 | 0 (172) | None (2) | 0.916 (0.874) | 过 / 过 | 0 |
| ep13_snack_box | 922 | 321 (479) | 80 (0) | 0.850 (0.789) | 过 / 过 | 29 |
| ep14_round_table | 993 | 4 (105) | 300 (5) | 0.803 (0.758) | 过 / 过 | 29 |
| ep15_wet_floor_sign | 715 | 6 (175) | 489 (0) | 0.836 (0.844) | 过 / 过 | 0 |
| ep16_spray_bottle | 477 | 84 (192) | 264 (0) | 0.866 (0.799) | 过 / 过 | 0 |
| ep17_traffic_cone | 440 | 40 (158) | 108 (6) | 0.801 (0.758) | 过 / 过 | 0 |
| ep18_blue_trash_can | 858 | 0 (167) | None (0) | 0.929 (0.929) | 过 / 过 | 1 |
| ep19_cane | 886 | 133 (259) | 192 (3) | 0.445 (0.456) | 过 / 过 | 1 |
| ep20_rice_cooker | 553 | 1 (165) | 465 (0) | 0.912 (0.912) | 不过 / 过 | 0 |
| ep21_tall_bar_stool | 678 | 0 (65) | None (0) | 0.825 (0.808) | 过 / 过 | 0 |
| ep22_step_ladder | 719 | 4 (212) | 602 (0) | 0.841 (0.783) | 过 / 过 | 0 |
| ep23_toy_stroller | 946 | 0 (76) | None (0) | 0.808 (0.736) | 过 / 过 | 0 |
| ep24_watering_can | 748 | 11 (102) | 0 (0) | 0.798 (0.786) | 过 / 过 | 0 |
| ep25_cyan_water_bottle | 859 | 96 (134) | 0 (0) | 0.823 (0.710) | 不过 / 过 | 0 |
| ep26_skateboard | 669 | 0 (273) | None (0) | 0.909 (0.790) | 过 / 过 | 0 |
| ep27_woven_basket | 565 | 129 (240) | 23 (0) | 0.824 (0.529) | 过 / 过 | 1 |
| ep28_squeegee | 988 | 375 (553) | 144 (0) | 0.404 (0.172) | 过 / 过 | 0 |
| ep29_rolling_luggage | 467 | 376 (450) | 91 (0) | 0.793 (0.765) | 过 / 过 | 0 |

## 已知问题

- 朝向翻转没有修：ep03 第 451 帧杯子上下颠倒、ep04 球棒头尾颠倒、ep02 篮子倒置等，来自 CARI4D 的 CoCoNet，等初值试点
- ep28 重建失败（手离刮水器 20–40 cm），ep29 重建出的脚与行李箱有 6–10 cm 缺口，ep13 重定向后脚够不到箱子
- ep07 熨斗在桌沿处陷入桌面约 1 cm（dr2s 用 v2 支撑面生成）
- rxzhou 的打包脚本有白名单，新版本名需要他自己加入才能读到

## 说明

- 位置：沿相机视线修正深度（dr2s），不再竖直抬升，画面吻合与未修正的 best 持平；动力学：dyn7 的静置锁定与衔接
- 对照答案见比赛仓 stages/recovery/tier3/checked_frames.json（用户看图确认）
- 交付规则（用户 10-16 下班前授权）：dr2s3_dyn7（用 v3 支撑面重做深度修正）若 6 条事先登记的条件全过就交付它，否则交付本版本。dr2s3_dyn7 未过第 1 条：相对本版本，ep06、07、11 的人体平移也变了（深度修正 --move-human=3d 让人跟随物体，属设计行为，但规则写的是只许物体位姿变），按规则交付本版本；dr2s3_dyn7 的检查结果留给用户复看
- 本版本的门槛用 v3 支撑面（`runs/support/tier3_cari4d_f830_best_v3`，滑动时质心经过处扩大，用户看过投影图）；v2 时 ep07 不过
- rxzhou 的打包脚本（tier3_pack_remote.sh / t3_episode_remote.sh）按白名单读目录名，需要把 tier3_cari4d_f830_best_dr2s_dyn7 与 _suspect 加进去才能读到；best_hm 原样保留
