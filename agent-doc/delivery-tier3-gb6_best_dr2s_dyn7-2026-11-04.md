# Tier 3 交付：`tier3_cari4d_gb6_best_dr2s_dyn7`

由 `stages/recovery/tier3/gate/t3_delivery_report.py` 从各项检查的结果文件生成，数字不经手抄。上一个交付版：`tier3_cari4d_gb5_best_dr2s_dyn7`。

## 这是什么

- 用途：dyn7 dynamics post-process on gb6_best_dr2s; the second Tier 3 final (user 11-04), gb5_best_dr2s_dyn7 stays delivered as the first; checked by gate/chain_check.sh set gb6dyn7 and gate/dyn/gb6_selfcheck_now.sh against gb5_best_dr2s_dyn7: dynamics, hand-object and the pose audit differ from gb5 only on ep11 and ep17; the other 28 episodes' tables equal gb5's (metadata differs only by the version name), their support usda byte-identical except ep01, whose two lean boxes moved about 1.4 mm (inferred: t3_lean_support.py samples the mesh unseeded under trimesh 4.5.1); ep17 delivered-layer dynamics violations 26 -> 46, not attributed; the chain was not run end to end (resumed after the alignment KeyError, step 4 run separately, no ROT_FULL_DONE); delivery-layer texture sheets not seen by the user; DELIVERED 11-04 by user decision (report runs/<version>/DELIVERY.md)
- 由 `t3_dynamics_post.py` from `tier3_cari4d_gb6_best_dr2s` 生成；代码 af1f37f49421fdc5aaadf3ca4111b41094271789 dirty=0 (deploy_l40
- 支撑面：`runs/support/tier3_cari4d_gb6_best`，写成 usda 放在本版本的 `support_surface/` 下（路径见每集元数据的 `support_surface`）。
- 集数：30（其中 1 集在 `tier3_cari4d_gb6_best_dr2s_dyn7_suspect`）。

## 与上一个交付版对比

| 项目 | `tier3_cari4d_gb5_best_dr2s_dyn7` | `tier3_cari4d_gb6_best_dr2s_dyn7` |
|---|---|---|
| 物体动力学违规帧（占比） | 1779 (7.7%) | 1797 (7.8%) |
| 零违规的集 | 7 | 7 |
| 前 30 帧内就违规的集 | 2 | 2 |
| `lin_supported` | 415 | 414 |
| `lin_airborne` | 257 | 255 |
| `lin_held` | 8 | 8 |
| `rest_drift` | 1016 | 1016 |
| `rot_drift` | 934 | 933 |
| `rot_jump` | 411 | 431 |
| `rot_torque` | 417 | 427 |
| 轮廓 IoU（各集中位数的均值，29 集，不含 ep28） | 0.809 | 0.809 |
| IoU < 0.5 的抽样帧 | 502 | 502 |
| 训练前门槛，用我们的支撑面 | 30/30 | 30/30 |
| 标了接触但手离物体 > 3 cm | 0.94% | 0.89% |
| 标了接触的帧（左右手合计） | 18321 | 18354 |

门槛只列用我们支撑面判的结果：Tier 3 不能用官方支撑面；只按地面判时，放在桌上的物体必然算悬空。逐集表里的「地面」一列只作参考，hm 那套门槛数据是 10-13 建的、集目录里带着官方支撑面，口径不同。

## 自检（清单见 10-15 定的 13 项）

| # | 项目 | 结果 |
|---|---|---|
| 11 | 数据契约（对照 `tier3_cari4d_gb6_best_dr2s`） | 通过；改动的列 ['observation.object.pose'] |
| 2 | 改动审计 | 锁定段外可见改动 > 5 cm 的帧 103；最多的集：ep17_traffic_cone 58, ep11_light_blue_book 45, ep00_tall_bar_stool 0 |
| 3 | 逐帧画面对齐 | IoU < 0.5 的抽样帧 502（上一交付版 502） |
| 5 | 动力学检查 | 违规帧 1797，见上表 |
| 9 | 手和物体 | 标了接触但手离物体 > 3 cm 的占 0.89%；接触帧比上一交付版少 10% 以上的集：无 |
| 12 | 来源 | `tier3_cari4d_gb6_best_dr2s_dyn7.provenance.json`：有；`tier_guard` 拒绝读取低档位数据 |
| 13 | 每帧可信度 | 30 集 22990 帧：ok 94.1%、unverified 1.2%、bad 4.7%，连成跟丢段的帧 5.5%。逐帧结果在版本目录的 `confidence/episode_*.parquet`（`t3_frame_confidence.py`）。ok 只说明剪影与掩码吻合，朝向翻转在剪影上看不出来 |
| 4 | 看图：user（11-03/11-04，ROT_DEG 5 对 10 贴图目测） | 两轮共 42 帧（FP 层，按两版朝向差最大抽帧）：用户给出明确方向的 8 帧里 5 更好 4 帧（ep01 f129、f145，ep17 f125、f187）、10 更好 4 帧（ep13 f769、ep28 f645、ep01 f338、f322）；规则所用裁判（轮廓 IoU）在这 8 帧上同向 7、线内同号 1、相反 0。规则选中的两集里 ep17 有 2 帧目测改对作旁证，ep11 没有目测（图：`/lab_data/yqchen/v2d/seedance_t3/rotdeg/review/`） |
| - | 看图：agent（11-04，规则稳定性扫描） | ROT_DEG 3–8 扫描（seedance_t3/rotsweep/）：ep17 在每个值下都被选中（双侧平台）；ep11 在 3–5 上同一批 48 帧一致变好、6 起不再改这批帧（单侧平台，5 是上端）；ep13 裁判判变差而 3、4 把答案帧 226 判对（裁判与答案相反的一例）。按事前写定的判据 C 不换值（图：`/lab_data/yqchen/v2d/seedance_t3/rotsweep/`） |
| 4 | 看图：agent（11-04，交付层贴图） | ep11 9 帧（0、146、326、350、365、380、586、811、900）、ep17 10 帧（0、124、156、171、188、203、222、245、278、439）的交付层 gb5 对 gb6 贴图叠图（t3_pose_overlay.py 默认抽帧，tex=1）；交付时用户未看（图：`dev/sel_diag/review_gb6/`） |
| - | 未做 | 复现：命令是 t3_rot_full.sh gb6 gb5，但本次没有端到端跑通，由三段拼出：驱动（af1f37f4）跑到链路第 7 步对齐 KeyError 停下；dev/gb6_resume.sh 用 e6e2f19e 只补跑对齐、补写结束标记；第 4 步比对用 8a9cc9ce 另跑。ROT_FULL_DONE 没有写出：第 4 步在 ep01 依靠方块上判不同（见已知问题）。按现在的代码重跑，预期在第 4 步 ep01 停下 |
| - | 未做 | gb5 交付时的登记闸门（ATTRIBUTE M5 M6）对本版本没有跑 |
| - | 未做 | 交付层贴图（dev/sel_diag/review_gb6/）用户未看 |
| - | 未做 | 6 合成轨迹空跑与幂等性（工具未写） |

## 逐集

| 集 | 帧数 | 违规帧（上一版） | 首次违规帧（上一版） | IoU 中位（上一版） | 门槛 地面 / 我们的支撑面 | 手 > 3 cm 帧 | 接触帧（上一版） | 可信 ok / unverified / bad |
|---|---|---|---|---|---|---|---|---|
| ep00_tall_bar_stool | 778 | 7 (7) | 704 (704) | 0.837 (0.837) | 过 / 过 | 3 | 749 (749) | 100% / 0% / 0% |
| ep01_vacuum | 747 | 108 (108) | 128 (128) | 0.587 (0.587) | 过 / 过 | 14 | 235 (235) | 85% / 0% / 15% |
| ep02_blue_easter_basket | 980 | 206 (206) | 87 (87) | 0.726 (0.726) | 过 / 过 | 0 | 425 (425) | 69% / 18% / 13% |
| ep03_contigo_coffee_mug | 781 | 19 (19) | 99 (99) | 0.860 (0.860) | 不过 / 过 | 0 | 515 (515) | 100% / 0% / 0% |
| ep04_baseball_bat | 803 | 24 (24) | 102 (102) | 0.777 (0.777) | 过 / 过 | 2 | 852 (852) | 96% / 0% / 4% |
| ep05_big_black_box | 1003 | 7 (7) | 589 (589) | 0.923 (0.923) | 过 / 过 | 5 | 1058 (1058) | 100% / 0% / 0% |
| ep06_monitor | 546 | 0 (0) | None (None) | 0.739 (0.739) | 不过 / 过 | 3 | 511 (511) | 100% / 0% / 0% |
| ep07_iron | 896 | 0 (0) | None (None) | 0.893 (0.893) | 不过 / 过 | 0 | 694 (694) | 100% / 0% / 0% |
| ep08_skinny_wood_chair | 708 | 56 (56) | 144 (144) | 0.813 (0.813) | 过 / 过 | 0 | 483 (483) | 100% / 0% / 0% |
| ep09_big_red_bowl | 870 | 22 (22) | 509 (509) | 0.816 (0.816) | 过 / 过 | 0 | 1056 (1056) | 96% / 0% / 4% |
| ep10_white_desk | 794 | 13 (13) | 90 (90) | 0.725 (0.725) | 过 / 过 | 6 | 514 (514) | 100% / 0% / 0% |
| ep11_light_blue_book | 901 | 37 (39) | 124 (51) | 0.812 (0.811) | 过 / 过 | 43 | 1609 (1624) | 95% / 2% / 3% |
| ep12_black_platform | 700 | 1 (1) | 158 (158) | 0.900 (0.900) | 过 / 过 | 0 | 710 (710) | 100% / 0% / 0% |
| ep13_snack_box | 922 | 314 (314) | 182 (182) | 0.854 (0.854) | 过 / 过 | 28 | 586 (586) | 96% / 0% / 4% |
| ep14_round_table | 993 | 4 (4) | 300 (300) | 0.792 (0.792) | 过 / 过 | 47 | 1135 (1135) | 100% / 0% / 0% |
| ep15_wet_floor_sign | 715 | 3 (3) | 497 (497) | 0.832 (0.832) | 过 / 过 | 1 | 389 (389) | 99% / 1% / 0% |
| ep16_spray_bottle | 477 | 78 (78) | 341 (341) | 0.869 (0.869) | 过 / 过 | 0 | 197 (197) | 95% / 4% / 1% |
| ep17_traffic_cone | 440 | 46 (26) | 123 (126) | 0.827 (0.827) | 过 / 过 | 0 | 365 (317) | 91% / 9% / 0% |
| ep18_blue_trash_can | 858 | 0 (0) | None (None) | 0.921 (0.921) | 过 / 过 | 2 | 702 (702) | 100% / 0% / 0% |
| ep19_cane | 886 | 140 (140) | 88 (88) | 0.447 (0.447) | 过 / 过 | 2 | 395 (395) | 82% / 0% / 18% |
| ep20_rice_cooker | 553 | 0 (0) | None (None) | 0.908 (0.908) | 不过 / 过 | 0 | 326 (326) | 100% / 0% / 0% |
| ep21_tall_bar_stool | 678 | 0 (0) | None (None) | 0.828 (0.828) | 过 / 过 | 2 | 888 (888) | 100% / 0% / 0% |
| ep22_step_ladder | 719 | 4 (4) | 602 (602) | 0.835 (0.835) | 过 / 过 | 0 | 412 (412) | 100% / 0% / 0% |
| ep23_toy_stroller | 946 | 0 (0) | None (None) | 0.810 (0.810) | 过 / 过 | 0 | 689 (689) | 100% / 0% / 0% |
| ep24_watering_can | 748 | 13 (13) | 0 (0) | 0.797 (0.797) | 过 / 过 | 0 | 473 (473) | 99% / 0% / 1% |
| ep25_cyan_water_bottle | 859 | 25 (25) | 0 (0) | 0.824 (0.824) | 不过 / 过 | 5 | 803 (803) | 100% / 0% / 0% |
| ep26_skateboard | 669 | 0 (0) | None (None) | 0.899 (0.899) | 过 / 过 | 0 | 485 (485) | 100% / 0% / 0% |
| ep27_woven_basket | 565 | 13 (13) | 181 (181) | 0.829 (0.829) | 过 / 过 | 0 | 596 (596) | 98% / 1% / 1% |
| ep28_squeegee | 988 | 283 (283) | 146 (146) | 0.446 (0.446) | 过 / 过 | 0 | 502 (502) | 46% / 1% / 53% |
| ep29_rolling_luggage | 467 | 374 (374) | 93 (93) | 0.787 (0.787) | 过 / 过 | 0 | 0 (0) | 97% / 0% / 3% |

## 已知问题

- ep17 交付层物体动力学违规帧 26 → 46（rot_torque 15 → 28、rot_jump 23 → 40），与方案 §2 的预期方向相反：预期依据的是 05 层（FP 选择）> 24° 跳变，那一层确实按预期减少（rot_eval.json：ep17 7 → 5、ep11 15 → 7），但经 CARI4D 06–08、dr2s、dyn7 之后交付层跳变变多。原因没有归因：gb5 交付时已知闸门的跳变计数含绕锥桶近似对称轴的自旋，本版本增量是否同属此类没有逐帧核对；gb5 交付时用的登记闸门（ATTRIBUTE M5 M6）本次没有跑。因此 ep17「改好」的证据只有 05 层改动帧的轮廓 IoU（28 帧 +0.029）与用户目测 2 帧（f125、f187）
- ep11 交付层违规帧 39 → 37；我们的支撑面门槛 ep11 间隙 0.0 → −1.9 mm，仍判过
- 规则（改动帧 IoU 增益 > 0.02 才用 5）与 0.02 都是看过这 13 集的审计结果之后定的；裁判在人眼能分的 8 帧上同向，在 ep13 一个答案帧上相反；规则固定 ROT_DEG 5，在新集上落在平台哪一侧没有证据
- ep01 支撑面的两个依靠方块与 gb5 交付版差约 1.4 mm（平移）、0.1 mm（尺寸），数据表相同、两版物体位姿输入相同（retarget 输出物体列差 0）、地面拟合与相机配准文件相同。依靠方块本身不可逐位复现（已验证：同一输入、同一代码上 t3_lean_support.py 跑三次——链路一次、--dry 两次，dev/lean_dry/——ep01 第一个方块的 lo.y 依次为 −0.7947、−0.7958、−0.7960）。原因（推断）：它想用 seed=0 采样网格表面，L40S 的 trimesh 4.5.1 的 sample 没有 seed 参数，代码静默退回无种子采样。gb5 交付版 ep01 的依靠方块同样不能逐位复现。gb6 的这一份过了我们的支撑面门槛
- ep11、ep17 在 rxzhou 的训练记录里都属于跟丢的集：ep11 在 hm 与 gb5 参考上正式训练都跟丢（ADD-AUC 0.069 / 0.065），提交包里用的是 4096000 步占位；ep17 在 hm 参考上跟丢（MPPE 92 cm），gb5 上没训过
- gb5 交付版的已知问题照旧：ep28 重建失败（手离刮水器 20–40 cm）、ep29 脚与行李箱有缺口、ep02 815–979 帧遮挡段位置不对、ep13 189/209/769 帧跟丢等

## 说明

- 与 gb5 交付版的唯一设计差别：FP 时间线选择器的 ROT_DEG 按集自动定（t3_rot_rule.py），选中 ep11、ep17 用 5，重跑这两集的 CARI4D 06–08、convert 与整条链；其余 28 集的数据表与 gb5 相同（parquet 元数据只差 depth_post / dynamics_post 记的来历版本名）。复现命令见未完成项
- 产出过程：链路第 7 步对齐因 t3_align_check.py 不认 convert_fp_gb6 停下（KeyError），修复 e6e2f19e 后由 dev/gb6_resume.sh 只补跑对齐、补写结束标记（日志行标 resumed）；其余检查是原次运行的结果。驱动第 4 步原先按整份文件比字节，因元数据含版本名在构造上不可能通过，8a9cc9ce 改为表内容 + 只允许来历版本名不同
- 提交：第二个 final 只替换 ep11、ep17 两行（用本版本参考按提交版同一训练配置重训），其余 28 集沿用第一个 final 的 checkpoint 与帧参考；第一个 final 里这两集的参考是 hm，不是 gb5，所以两份提交在这两集上的差别是 hm → gb6，不只是 ROT_DEG
- 方案 §4 停止条件的本次处理（用户 11-04「先按老流程交付」）：链路检查中断后续跑（不是整条重跑）；28 集「逐字节相同」改为表内容相同、元数据只差版本名，ep01 依靠方块不同；自检各项跑完，ep17 违规帧增加未归因、仍交付；交付层贴图用户未看
- 自检 13（每帧可信度）在本版本上全 30 集重跑（e6e2f19e）；28 个未改动集的摘要行与 gb5 交付版相同，逐帧表除 NaN 位置外逐值相同（遮挡帧无轮廓记 NaN）
