# 计划：Tier 3 对齐之后，跟丢的集换成“机器人原地站、物体不动”的保底（t3static，10/21，第 2 版）

2026-10-21 15:1x MDT 写定第 1 版，15:4x 按独立复核改成第 2 版（改动见文末），分支 track2/p1-training。判据在结果出来之前登记在这里。
只用 Tier 3 的数据与对自己重建参考的读数；Tier 1 只经已对齐的帧参考用到第 0 帧（`agent-doc/plan-t3align-2026-10-21.md`）。
这一轮只打包、预演，不上传；交不交由 rxzhou 定（`agent-doc/strategy-2026-10-19.md` 第 1 节）。

## 0. 事实（都有出处）

1. **榜上“物体不动”的分数**：Kelly To the H 三档 AUC 0.26633 / 0.26600 / 0.26600，MPPE 49.12 / 49.14 / 49.14 cm，SP-SR、MP-SR 全是 0（`results/board/lb_1021_1455.txt`）。
   Tier 2 上“物体停在第 0 帧”对 Tier 2 自己轨迹的 30 集 MPPE 平均 49.4 cm（`results/t2diag/t2_static_floor.txt`，逐集相加 1483.3 / 30）。读法（推测）：Kelly 交的就是“物体不动”。
2. **maniphys.ai 的 Tier 3 比“不动”差**：AUC 0.10649、MPPE 54.98984（gb1018e22，10/18）。不计 solidSF.com，Tier 3 AUC 第 1 是 Kelly 0.266、MPPE 第 1 是 FF 45.99；
   SP-SR 是 maniphys.ai 唯一的第一（0.26666 对 Team OPS 0.16666）（`results/board/diff_1021_1401_ex_solidSF.txt`）。
3. **对齐把第 0 帧对上了**：对齐后 CSV 第 0 帧物体位置差 0.01–0.77 cm（原来 2.9–50.1 cm，中位约 11 cm），按物体对齐的 15 集朝向差 ≤ 0.7°；10 集朝向仍差 > 30°（ep3、4、9、11、12、13、14、17、25、27）（`agent-doc/plan-t3align-2026-10-21.md` 执行记录）。
4. **策略 = SONIC 解码器照参考 + 训出的残差**：残差头为 0 时，动作只取决于参考与机器人自己的状态（`agent-doc/plan-t12replay-2026-10-20.md` 事实 2、`plan-t12arm-2026-10-20.md` 事实 4）。
   冒烟 run 存第 409600 步时残差头量过是严格的 0（`results/t12replay/residual_head_mf4090.txt`，`stages/evaluate/residual_head_norm.py`）。
5. **评测时物体不会被推向参考**：Tier 2 ep4 零残差回放（机器人没碰到球棒）导出 MPPE 111.48 cm，“不动”111.51 cm（`results/t2diag/t2_static_floor.txt`）。
6. **改参考的工具现成**：`stages/retarget/hands_off.py` 把两条手臂与手指固定为一帧、接触标记清零、手掌按正向运动学重算，其余列与 object 目录照抄（只改关节、`ee_pose_w`、接触三列，第 206–209 行）。
   打包器只核对物体的参考（`third_party/v2d_submission_kit/update_0f2f9f4b/v2d_submission_kit/tools/pack_submission.py` 第 361–367 行；`pack_tier.sh` 用的是这份 kit），机器人怎么动不核。
7. **10/20 的保底不保底**：手臂不去够物体、腿照参考走的策略照样摔、照样把瓶子弄下桌（Tier 2 ep25 117.09 → 93.54 cm；摔在第 195 帧）。所以这次让机器人**连走都不走**。
8. **只评冒烟那一步的现成做法**：t2rp 用 `day2_eval_chain.sh` 的附加表（`eval smoke-<run> 409600 frame <源帧数>`，`stages/evaluate/t2rp_mf4090.tsv`）与手写的导出清单
   （`stages/evaluate/exports/cand_t2_t2rp_mf4090.tsv`），冒烟开始后建 `runs/.chain-stop-<训练链名>` 不开正式训练（`stages/policy/arm_t2sd.sh` 第 4、28 行）。
9. **t3m1022a 混用了几种参考**：gb4、hm、hm-ph、gb3、v2、hm28-ph（`stages/evaluate/exports/t3_select_t3m1022a.tsv`）；有桌面的集 hm、gb3、gb4 都是同 12 集（`make_var_queue.py` 第 77 行 `TABLES_HM`）。
10. **算力**：mf4090 约 19:30 MDT 空（t2mtr 训评完）；ml40 约 23:30 空（t3g5 B 段）。一集冒烟约 4–5 分钟、4096 世界评测约 5 分钟、导出约 3 分钟（这一条没有逐项核过）。Tier 3 额度 10/22 16:14 MDT 起。

## 1. 做什么

1. **站立参考**（CPU）：`hands_off.py` 加 `--stand`：先列出 parquet schema 里所有随帧变的机器人列（关节角、`robot_root_position`、`robot_root_wxyz`、`ee_pose_w`，以及有的话的速度类列），
   位置、朝向类在全部帧都换成第 0 帧的值，速度类全部置 0；`ee_pose_w` 按正向运动学重算（沿用现有自检：原关节角下算出的手掌与原 `ee_pose_w` 差 ≤ 2 mm）；`hand_contact_active` 全部置 0；
   object 目录、物体轨迹列、支撑面、`v2d_meta.json` 照抄。报告：第 0 帧机器人各连杆（含骨盆、腿、脚）点到物体表面的最近距离（物体停在第 0 帧位姿）。
   测试 `stages/retarget/test_hands_off.py` 加一条：机器人列全帧相同、速度列为 0、物体列逐字节相同。
   **每种参考一个目录**：t3m1022a 里这一集用哪一版参考，就从那一版生成，放到 `runs/motion/tier3_<版本>st/`（例如 `tier3_hmst`、`tier3_gb4st`）。
2. **自参考的“不动”分**（CPU）：新写 `stages/evaluate/t3_static_floor.py`（照 `t2_static_floor.py`，同一套官方公式 `v2dlb/object_pose.py`，挂 `tier_guard.forbid_tier1`）：
   读评测器用的那份参考（motion parquet 的 `object_body_position` / `object_body_wxyz`，wxyz），按逐帧回放的帧数对齐，物体一直停在第 0 帧时对这份参考的 MPPE、ADD-AUC、SP-SR、MP-SR。
   脚本与第 2 节的规则**先提交**，再出表：与 t3m1022a 里各集 run 的 4096 世界对自己参考的读数（同一评测器版本、同一指标键）并排（`results/t3static/select_table.txt`）。
3. **选集**：只看这张表，按第 2 节 S3 定哪些集换成站立保底。
4. **冒烟、评测、导出**（GPU）：每种参考一段（`make_var_queue.py` 加 `t3pst<版本>`（mf4090）与 `t3qst<版本>`（ml40）），run 名 `t3-ep{ep}-w2048-cap{4m,10m}-r3a-<版本>st-<机器>`；
   **覆盖逐项照抄这一集原 run**（支撑面开关、ph 等），配置核对只许 parquet 路径与存档间隔两处不同。只跑冒烟：步数截到 819200（只要第 409600 步），`training.checkpoint.save_interval_environment_steps=409600`；
   冒烟开始后建停链标记，不开正式训练（照 `arm_t2sd.sh`）。每集量第 409600 步的残差头（S1，先核张量布局与 t12replay 一致），
   再用附加表 `eval smoke-<run> 409600 frame <源帧数>` 评 4096 世界，按手写的导出清单导出 1 个世界。先在 mf4090 上做试点 3 集（S2），过了再铺开；ml40 空了分一半。
5. **拼清单**：t3m1022a 换上站立保底的集，名为 **t3m1022s**。物体轨迹不变，帧参考直接用 t3m1022aa 里这一集已对齐的 npz：先核新参考的 `poses.npy` 与 `source_parquet` 的物体部分
   和原参考 sha256 相同（或物体列逐字节相同），再只改清单里的 run、step、tier_dir 三列；每集在清单里只有一行，旧行删掉。打包、预演、`csv_frame0_check.py`、逐集比 CSV。
   t3g5 已过 R1 的 ep12（gb5 参考）另做一版 **t3m1022s12**：ep12 换成 gb5 的 run，帧参考按 gb5 参考生成后用同一对齐规则对齐。两版都不上传。
6. 结果写进本计划执行记录，交 rxzhou 定交不交、交哪一版。

## 2. 判据（登记，第 2 版）

- **S0（站立参考）**：每份新 parquet 机器人位置、朝向类列全帧与第 0 帧逐位相同，速度类列为 0；物体位姿列与原 parquet 逐字节相同；手掌自检 ≤ 2 mm。不过的集不用。
- **S1（零残差）**：第 409600 步的残差均值头（与 t12replay 同三个张量，布局先核）最大绝对值 = 0。不为 0 的集不换。
- **S2（物体真的不动；每一集要换的都要过）**：4096 世界对自己参考的 MPPE 与第 2 步算出的“不动”分差 ≤ 1.0 cm，且导出的 1 个世界里物体离第 0 帧位姿全程 ≤ 2 cm、≤ 5°。不过的集不换。
  试点 3 集 = ep16（瓶子在约 1 m 高的台面上）、ep15（只有地面）、第 1 步报告里机器人离物体最近的一集（与前两集重复就取第二近）；试点 ≥ 2 集不过 → 停，记“站立保底不成立”，另写计划。
- **S3（选集，只用 Tier 3 的读数，规则先于出表提交）**：一集换成站立保底，当且仅当
  （a）t3m1022a 里这一集 run 的 4096 世界对自己参考的 MPPE > 这一集参考的“不动”MPPE，且
  （b）原 run 的 4096 世界对自己参考的 SP-SR 不高于“不动”的 SP-SR（守住 Tier 3 SP-SR 这块第一）。
  ADD-AUC 并列报，不进规则。对齐后朝向仍差 > 30° 的 10 集照同一规则判。
- **S4（清单）**：t3m1022s 打包 `PACK_OK`、预演通过；`csv_frame0_check.py` 对 t3m1022a 的旧 CSV `CSV_FRAME0_OK`；与 t3m1022aa 逐集比，内容不同的恰好是 S3 选中且过了 S1、S2 的集。t3m1022s12 另外只多 ep12 不同。
- **不做预测**：对齐与保底都只能交上去才看得到对真值的分；第 0 帧偏差与自参考读数都不当作榜上分数的预测。交不交照策略第 1 节由 rxzhou 定，这一轮不上传。

## 3. 风险

- 站立的机器人可能慢慢倒；倒在原地、离物体远就不碰物体。S2 每集都查；离物体近的集（第 1 步报告）倒下可能碰到，S2 不过就不换。
- 物体自己掉：参考第 0 帧若悬空或穿进支撑面，仿真开局就会动（10/15 的“从台面掉落”）。覆盖照抄原 run（支撑面开关不能错），S2 第二条查导出世界里的物体位移。
- 自参考是重建结果，不是真值；“不动”对自己参考的分与对真值的分不同。规则只拿它在同一份参考上比策略与“不动”，不推到真值。
- t3m1022a 各集的自参考读数之前已经见过；规则与脚本先提交再出表，规则按事实 2 的榜面（SP-SR 要守、AUC 与 MPPE 输给“不动”）定，不按逐集读数挑。
- 规则读法：站立保底是一份真的 checkpoint、在官方仿真里跑出的轨迹；规则里没有禁止“机器人不去做任务”的条文。这是解读，封榜后组委会怎么看未知。
- mf4090、ml40 各占约 2–3 小时；不占正在训的 run（等 t2mtr、t3g5 B 段结束）。

## 4. 之后（不在本计划里）

- Tier 1 ep25（导出 117.99 对“不动”49.71 cm）、Tier 2 ep25（115.88 对 49.51）、ep28（56.14 对 48.49）同法保底，只涨名次、不拿第一，交不交要 rxzhou 先定“只为名次和的提交”算不算数。
- 对齐后朝向仍差 > 30° 的 10 集（物体系里右乘固定旋转）另写计划。

## 复核与改动（第 2 版，10/21 15:4x MDT，Opus；Fable 本周额度到 10/23 13:00 纽约时间）

结论 GO WITH FIXES（5 MAJOR、3 MINOR、1 NIT，无 BLOCKER）；合规没查出问题：对齐只经 `tier1_frame0.py`，选集不用人的判断，S3 只用 Tier 3 读数。改动：
MAJOR 1 只跑冒烟时评测链不评、导出记 no_done、冒烟后会接着开正式训练 → 照 t2rp 用附加表与手写导出清单，建停链标记（事实 8、第 1 节第 4 步）；
MAJOR 2 `make_frame_refs_t3.py` 读 `poses.npy` 与 `root_<后缀>`、不读 motion parquet，按 parquet 重生成会报错 → 物体轨迹不变，直接用已对齐的 npz，核 sha256 后只改清单三列、每集一行（第 5 步）；
MAJOR 3 t3m1022a 混用几种参考、每段只认一个 motion 目录 → 每种参考一个目录一段，覆盖照抄原 run，配置核对只许两处不同（事实 9、第 1、4 步）；
MAJOR 4 S3 只看 MPPE 会丢 Tier 3 SP-SR 的第一 → 加（b）；MAJOR 5 物体位移只在试点查 → S2 改为每一集要换的都要过，ep27 有桌面，试点换成只有地面的 ep15；
MINOR 6 `--stand` 要写根位置、根朝向，列出全部随帧变的机器人列、速度置 0，距离报告加骨盆与腿；MINOR 7 仓里只有 `forbid_tier1`，读评测器用的那份参考、按回放帧数对齐；
MINOR 8 事实 5（现事实 6）kit 副本改成 update_0f2f9f4b、事实 4 改成“参考与机器人状态”、S1 先核张量布局；NIT 9 冒烟步数截到 819200。另加事实 5（评测时物体不会被推向参考）。

## 执行记录

- 15:2x–16:0x MDT（CPU；两台的训练链在跑、不能同步，按已提交的版本只拷新脚本过去跑，记录里有 md5）：
  - 机器人随帧变的列只有 `robot_root_position`、`robot_root_wxyz`、`robot_joint_positions`、`ee_pose_w`，没有速度列（`results/t3static/parquet_columns_hm_ep16.txt`）；`--stand` 写成单独的 `stages/retarget/stand_still.py`（21f6bfe）。
  - 规则与脚本先提交（21f6bfe、之后 eval_json_record.py），再出表。“不动”分：mf4090 25 集、ml40 5 集（`results/t3static/floor_mf4090.txt`、`results/ml40/t3static/floor_ml40.txt`；工具包只有 Mac 上有，
    把 `update_0f2f9f4b/v2dlb/object_pose.py` 拷到两台的同一路径，md5 32481d0c… 与 Mac 相同）。ep9、10、11、28 的原 run 是第 4096000 步的占位策略，评测只在 JSON 里，用 `eval_json_record.py` 记下。
  - **S3 选集**（`results/t3static/select_table.txt`）：换成站立保底的 15 集 = ep1、2、3、4、9、11、12、13、16、17、19、23、25、27、28；缺读数 0 集。
    ep10（a）成立、（b）不成立（原 run 4096 世界里 1 个成功，SP-SR 0.000244 > 0），按规则留原 run；ep5、ep20 同样因（b）留原 run。
  - ep4、9、11 的 hm 参考在两台上逐字节相同（sha256 前 16 位 ee185f3c…、0d4500f2…、411b706a…），15 集全放 mf4090 做（cap4m；原 run 是 cap10m 的 3 集只有 buffer 不同，零残差的第 409600 步与 buffer 无关）。
  - 第 0 帧机器人离物体最近（`results/t3static/stand_dryrun_mf4090.txt`、`results/ml40/t3static/stand_dryrun_ml40.txt`）：ep1 0.295 m、ep12 0.363、ep23 0.408、ep13 0.533、ep28 0.535、ep19 0.538，其余 0.62–1.19 m。
  - **试点改动**：第 2 版定的 ep15 不在换集名单里（原 run 22.19 cm 好于“不动”63.54），改用换集里只有地面的 ep23；最近的一集是 ep1。试点 = ep16、ep23、ep1。
  - 站立参考 15 份写到 mf4090 的 `runs/motion/tier3_st`（`results/t3static/stand_batch_mf4090.txt`，STAND_BATCH_DONE，每份写后自检过）。**偏离第 2 版的地方**：15 集放在一个目录里，每集从它原 run 的参考版本（hm 13 集、v2 ep23、hm28 ep28）生成，
    而不是每种版本一个目录；配置照抄原 run 的支撑面开关（`TABLES_ST`，原 run 没有 `scene.support=false` 的 10 集），队列生成的覆盖与原 run 只差 parquet 路径、存档间隔、冒烟步数（与第 2 版的意图相同）。
  - 队列：`make_var_queue.py` 加 `t3pst`（`t3psta` = 试点 ep16、23、1；`t3pstb` = 其余 12 集），测试 ALL_OK；附加表 `stages/evaluate/t3st{a,b}_mf4090.tsv`、手写导出清单 `stages/evaluate/exports/cand_t3_t3st{a,b}_mf4090.tsv`；
    `arm_smoke_dense.sh` 推广到 `t3p` 段（Tier 2 的行为不变）。冒烟步数没截短（NIT 9 没做，一集多约 1.5 分钟）。等 mf4090 的 t2mtr 链结束、整仓同步后起 `arm_smoke_dense.sh t3psta t3sta`。
