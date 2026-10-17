# Tier 3 换到标定内参参考（gb3）计划（2026-10-17，第 1 版）

## 目标

kfix1017 的榜单 A/B 按判据 6 记“完整内参修正在榜上得到支持”，登记的下一步是把 Tier 3 换到标定内参的参考，以另一位用户的 gb3 交付为准
（`agent-doc/plan-t3-kfix-2026-10-16.md` 末节）。本计划做其中跟得住的主机位集：在 gb3 参考上重训 5 集，连同已训好的 k-fix 重训 2 集，
按事先登记的规则逐集决定换不换，目标是 10/18 上午有一份可交的 Tier 3 候选。交不交由 rxzhou 定。全程不读真值、不读 Tier 1、不读 Tier 2 轨迹。

## 事实（核过的）

1. gb3 交付 `tier3_cari4d_gb_best_dr2s_dyn7`（另一位用户 10/16 23:23 MDT 跑完，10/17 交付；目录与交付说明见 `results/ops/t3_gb3_chain_ml40_1017_1515.txt`，
   逐集来源与指纹见 `results/t3gb3/inventory_ml40.txt`）：
   - 30 集，ep28 在 `_suspect`。世界系用标定内参 GB（主机位 f 866.3、cx 701.8、cy 531.1；二机位与侧机位 ep21 同用 GB，交付说明写明侧机位是
     证据不足下的决定），地面校正 1.222°/0.984 保留，二机位尺度 0.949。
   - 每集选的 convert 与 f830_best（我们 hm 参考的来源）逐集相同（30/30）：ep6、7、22 是 convert_v2，ep0、8、18、20、21、24、26、29 是 convert
     （与 k-fix、v2 同一份 CARI4D 输出）。
   - 版本目录带支撑面：有桌面的 12 集与 best_hm 的 12 集相同（ep2、3、6、7、9、11、13、16、17、20、25、27），其余是空的 Xform（sha256 4f9e5e6f2014…）。
   - 交付说明的已知问题：GB 转换里物体按点映射移动，人体只有骨盆按映射、其余部位随骨盆刚体移动，手持物体的集手离物体远了 1–6.5 cm
     （手到物体表面距离中位 ep01 1.9→7.1 cm、ep16 5.1→10.9、ep02 1.4→3.2、ep10 0.8→2.3、ep19 0.7→1.6、ep07 0.4→1.5、ep04 0.4→1.2、ep09 0.2→0.9、
     ep25 0.2→0.6；大件不变）；ep16 第 106–128 帧拿起时位姿跳变；ep03、ep04 朝向翻转；ep28 重建失败；ep29 脚与行李箱有缺口。
     另一位用户写明修正后以原名重生成，时间未定。
   - 主机位在 convert 一级的世界系结果与 k-fix 的物体位置、人体参数逐位相同，朝向最多差 0.33°（`results/t3kfix/kfix_vs_gb3_world_ml40_1016.txt`）；
     gb3 在此之上还有 dr2s（深度后处理）与 dyn7（动力学后处理，只改物体位姿一列）。
2. 现在榜上的 kfix1017（`stages/evaluate/exports/t3_select_probe1015.tsv`，其中 4 集按 `t3_select_kfix1017.tsv` 换掉）：
   - 已在标定内参参考上：ep18（k-fix 重训），ep24、ep26（v2 策略对 k-fix 参考重新导出）。ep20 是 v2 参考加方块桌面的重训（v2s），参考仍是 f830。
   - 4096 世界、对照各自参考，SP-SR ≥ 0.5 的集 11 个：ep0、6、7、8、18、20、21、22、24、26、29（MPPE 2.1–9.0 cm）；其余 19 集 SP-SR ≤ 0.121、
     MPPE 21–121 cm（`results/t3probe/eval_table_probe1015.txt`；ep18、20 取 `results/t3kfix/retrain_switch_t3{pk,ps}_mf4090.txt`）。
3. 现有策略只跟得住训练用的那份参考：k-fix 重新导出时，物体相对机器人根的位置差中位 ep24 0.78 cm，跟住；ep0 6.2 cm，MP-SR 0.965 → 0.000
   （`results/t3kfix/ref_pair_diff_ep{0,24}_mf4090.txt`、`results/t3kfix/reexport_mf4090.txt`）。
4. k-fix 参考上的重训（t3pk，`results/t3kfix/retrain_switch_t3pk_mf4090.txt`），4096 世界对照各自参考：ep18 MPPE 4.25 → 4.63 cm（判换）；
   ep0 2.60 → 5.63 cm（MP-SR 0.965 → 0.845、SP-SR 0.992 → 0.882），ep29 8.00 → 11.13 cm（SP-SR 0.713 → 0.531），按判据 5 都判不换。
5. 跟丢的 19 集的问题在人体：同一配方在 Tier 2 参考上 ep3、12、15、16 的 MP-SR 0.81–0.99，在 Tier 3 参考上都是 0；Tier 3 人体根加速度 p99 的
   中位 47.6 m/s²（Tier 2 4.3）；人体时间平滑（best_dyn4s）的试点换种子没有复现（`agent-doc/plan-t3dyn-pilot-2026-10-14.md`）。gb3 的人体只比
   f830 多了按内参的搬动与缩放，跟丢的原因不变（推断）。
6. 榜：kfix1017 MPPE 55.76705、AUC 0.04885、SP-SR 0.13333、MP-SR 0；G 版 56.87427、0.00690、0.03333、0；FF 的 AUC 0.156。
   上传器 10/17 14:47 报每个 Tier 3 榜“5 left today”（`results/submission/submit_t3_kfix1017.txt`）。
7. 两张卡 21:00 MDT 前后空出（ml40 的 t1c_s43、mf4090 的 t2m2，各 3 集）。重训一集连评测与导出约 2.4 小时（t3pk 三集 13:32 起、20:50 评完）。
   今晚 Tier 1、Tier 2 没有复核过的 GPU 计划。链在跑时 `scripts/dev/remote` 拒绝同步，新文件用 push-new-files。
8. 现有工具：`tier3_stage_hf.sh`（ml40 打包 → HF → mf4090 拼档目录，只支持 `V2D_T3_SUPPORT_DIR`，不支持 `V2D_T3_SUPPORT=delivery`）、
   `tier3_relay.sh`（mf4090 的档目录、转换与重定向结果经 HF 转到 ml40）、`ref_pair_diff.py`、`arm_after.sh`（上一段有一条失败就不起下一段）。

## 范围

- 重训 5 集：ep6、7、8、20、22（主机位、现有策略跟得住、参考还是 f830）。ep6、7、8 在 ml40（原来就在 ml40 训，buffer 1000 万），ep20、22 在 mf4090
  （buffer 400 万）。
- ep0、ep29：已有 k-fix 重训（事实 4），按下面的规则 S 直接判，不再训。k-fix 与 gb3 同一世界系（事实 1 最后一条）。
- ep21（侧机位）：排在 mf4090 最后，用夜里空出的卡时训；下一次提交不含它（A/B 只支持主机位，GB 内参对侧机位是证据不足下的选择），另行决定。
- 不在这一轮：ep18、24、26（已在 k-fix 参考上；与 gb3 的差只量、只报）；跟丢的 19 集（事实 5）。

## 做法

### 1. 工具（Mac 上改，各带测试；服务器上只放新文件）

a. `stages/recovery/tier3_pack_remote.sh` 与 `tools/t3_episode_remote.sh` 的白名单加 `tier3_cari4d_gb_best_dr2s_dyn7` 与 `_suspect`（两处一起改）。
   两个脚本都经 stdin 送到 ml40 执行，服务器上不用同步。
b. `stages/recovery/tier3_stage_hf.sh` 加 `V2D_T3_SUPPORT=delivery`：打包带上元数据 support_surface 指向的文件，`tier3_root.py` 加
   `--support-from-incoming`；与 `V2D_T3_SUPPORT_DIR` 只能设一个（同 `tier3_stage.sh`）。`test_tier3_stage_hf.py` 加一例正例、一例两者都设的拒绝。
c. `stages/policy/make_var_queue.py` 加两个段：
   - `t3pg`：mf4090，buffer 400 万，参考 /runs/motion/tier3_gb3/，支撑面按 gb3 自己的（tables 键，同 best_hm 的 12 集，事实 1），
     run 名 `t3-ep<N>-w2048-cap4m-r3a-gb3-mf4090`，顺序 ep20、22、21；
   - `t3qg`：ml40，buffer 1000 万，同上，run 名 `t3-ep<N>-w2048-cap10m-r3a-gb3-ml40`，顺序 ep6、8、7。
   段名以 t3p、t3q 开头，套用 `arm_var_chain.sh` 现有的两个分支（机器、显存、磁盘要求），`arm_var_chain.sh` 不改。测试核：生成的正式行、冒烟行、
   期望表行遮掉 run 名、参考目录、W&B 标签后，与 t3p4（mf4090）、t3q（ml40）同集的行逐字相同。
d. `stages/policy/arm_after.sh` 加 `V2D_AFTER_INDEPENDENT=1`：下一段与上一段无关时，第 5 步（上一段全部做完才起）只记录、不拦；其余各步不变。
   用途：今晚 t2m2、t1c_s43 有一条失败也不耽误 Tier 3 起链。`test_arm_after.py` 加两例（设了照起、不设照旧拦）。复制到 runs/tools/ 时记 md5。
e. 新脚本 `stages/evaluate/gb3_switch.py`：按规则 S（下面判据 G2）逐集判，旧值与门槛写死在 `stages/evaluate/gb3_switch.json`
   （来源记录逐项注明），新值读评测链写的 `eval_<步数>_w4096.json`，并核其中记的参考 parquet 在 tier3_gb3（ep0、29 是 tier3_kfix）下。
   最后一行 `GB3_SWITCH_DONE <换> <不判>`。测试：假 JSON 的换、不换、参考目录不对、缺文件四例。
f. 新脚本 `stages/evaluate/t3_refdiff_batch.sh`：按一份清单（集、旧参考目录、新参考目录）逐行跑 `ref_pair_diff.py`（mf4090，CPU 容器，
   `V2D_GPU` 不设），每集一行汇总“物体相对机器人根的位置差中位、机器人根位置差中位”。只报。

### 2. 搬运与重定向（CPU，21:00 前做完）

1. 记录：`V2D_T3_SUBDIR=tier3_cari4d_gb_best_dr2s_dyn7 V2D_T3_SUPPORT=delivery` 经 stdin 在 ml40 上跑 `tools/t3_episode_remote.sh`，11 集
   （ep0、6、7、8、18、20、21、22、24、26、29），记录 `results/ops/t3_episodes_ml40_1017_gb3.txt`；mf4090 上 `tier2_inputs_md5.py` 取这 11 集的
   官方网格与地面（`results/ops/t2_inputs_mf4090_1017_gb3.txt`）。两份记录过 `tools/name_leak_check.sh`。
2. 哈希表：`tier3_expect.py <第 1 步 ml40 记录> <mf4090 记录> --support-from-remote > stages/recovery/expect/t3gb3_11_1017.tsv`；提交、推送、
   push-new-files 到 mf4090。
3. 拼档目录：`V2D_T3_SUBDIR=tier3_cari4d_gb_best_dr2s_dyn7 V2D_T3_SET=gb3 V2D_T3_SUPPORT=delivery scripts/dev/record t3gb3/stage_hf_mf4090
   stages/recovery/tier3_stage_hf.sh t3gb3_11_1017 <11 集>`，要 `TIER3_ROOT_OK`。
4. 重定向（mf4090 的 tmux，CPU）：`V2D_T3_SET=gb3 scripts/dev/record t3gb3/retarget_mf4090 stages/retarget/eps.sh 3 6 8 7 20 22 21 0 29 18 24 26`
   （要训练的 6 集在前）；随后 `check_inputs.py` 核 11 份 motion parquet；有桌面的 ep6、7、20 用 `support_kinds.py` 与 `support_import_check.py`
   核训练场景里的支撑面建得出来（同 best_hm 计划第 9 步）。
5. 转到 ml40：`scripts/dev/record t3gb3/relay_ml40_hf stages/recovery/tier3_relay.sh gb3 11 <文件数> t3gb3_1017a`，要 `RELAY_OK`。
6. 参考差（只报）：`t3_refdiff_batch.sh` 在 mf4090 上比 11 集“现有 run 训练用的参考 → gb3”（旧参考从各 run 的 run_record.jsonl 第一条 start 取），
   ep0、18、24、26、29 另比“k-fix → gb3”（`results/t3gb3/refdiff_mf4090.txt`）。

### 3. 训练（GPU，21:00 起，服务器自己接上）

1. 队列：`make_var_queue.py t3pg`、`t3qg` 生成的文件提交、推送，push-new-files 到对应机器；两台各跑 `fc_config_check.sh`（冒烟与正式，
   意外差异 0）与 `V2D_ARM_DRYRUN=1 arm_var_chain.sh <段>`，要 `DRYRUN_OK`。
2. 挂接：`arm_after.sh` 复制到 runs/tools/（记 md5），两台各 setsid 起一个，`V2D_AFTER_INDEPENDENT=1`，等现在的链结束、卡空后起：
   mf4090 `t3pg`（上一段 t2m2，3 条），ml40 `t3qg`（上一段 t1c_s43，3 条）。起完核日志第一行。
3. 读数：两台各起 `run_after_log.sh`，等评测日志的结束行，跑 `gb3_switch.py`，记录 `results/t3gb3/switch_t3pg_mf4090.txt`、`switch_t3qg_ml40.txt`。
4. 预计（估计）：mf4090 ep20 约 23:30、ep22 约 02:00、ep21 约 04:30；ml40 ep6 约 23:30、ep8 约 02:00、ep7 约 04:30（都含评测与导出）。

### 4. 选集与打包（10/18 上午）

1. ep0、ep29 的 t3pk 现在就按规则 S 判（`results/t3gb3/switch_t3pk_now.txt`，旧值、新值都已在记录里）。
2. 选择清单 `stages/evaluate/exports/t3_select_gb1018.tsv`：kfix1017 的 30 行，判换的集换成新 run。
3. 换的集：导出拉回（`pull_submission.sh` 按 sha256 核），frame refs 用 `make_frame_refs_t3.py`（新 run 训练用的就是新参考，从 run 记录取）在训练机上生成，
   合并时 `merge_frefs_t3.py --take-plain`（gb3、k-fix 的世界系已含偏航，事实 1 最后一条）；没换的集沿用 kfix1017 的 frame refs。
4. `pack_tier.sh` 打包、官方打包器 PACK_OK、上传预演；与 kfix1017 的 CSV 逐行比，只有换的集不同。交不交由 rxzhou 定。

## 判据（跑之前登记）

- G0 搬运与重定向：哈希表核过（`TIER3_ROOT_OK`、`RELAY_OK`）；重定向 `EPS_DONE`、没有 `FAIL:*` 的集才进队列；`ALIGN`、`NOCONTACT` 照训、在报告里标出
  （同以往 Tier 3）；ep6、7、20 的桌面在训练场景里建不出来，这一集拿出队列。
- G1 参考差：只报，不判。登记一个预期：5 集的物体相对机器人根位置差中位都超过 2 cm（推断：深度乘 1.04–1.09，另有 dr2s、dyn7 与 hm 后处理的差）。
  某集 ≤ 2 cm 时，在报告里写明“这一集原策略对 gb3 重新导出也许够”，这一轮仍按重训做（卡时够，不另起一条链）。
- G2 换集规则 S（对 ep0、6、7、8、20、22、29，各自的候选是 gb3 重训或 k-fix 重训）：4096 世界、对照各自参考、同一评测器，
  **候选 MPPE ≤ 现选 run 的 MPPE + 4.0 cm，且候选 SP-SR ≥ 0.5** 才换；MP-SR、ADD-AUC、导出那一个世界的值并列照报。现选 run 的值
  （MPPE cm / SP-SR）：ep0 2.60/0.992、ep6 3.79/0.978、ep7 2.11/0.997、ep8 2.32/0.999、ep20 5.77/0.891、ep22 3.70/0.980、ep29 8.00/0.713。
  ep21 的读数照算，不进下一次提交。
- G3 提交的读法（只在 G2 判换的集不少于 3 集时提议交；交不交由 rxzhou 定）：记新版为 MK2，kfix1017 的 MK1 = 55.76705，τ = 1.0 cm：
  - MK2 ≤ MK1 − τ：记“放宽跟踪要求、换到标定内参在榜上得到支持”，下一轮考虑 ep21、ep18/24/26 换 gb3；
  - MK2 ≥ MK1 + τ：记“不支持”，退回 kfix1017，分开看 k-fix 重训（ep0、29）与 gb3 重训两类；
  - 之间：记“看不清”。AUC、SP-SR、MP-SR 照报；AUC 比 kfix1017 高 0.005 以上单独记。
- G4：任何一步不读真值、不读 Tier 1、不读 Tier 2 轨迹；不按榜上分数挑参数。

## 规则 S 的来由（单独标注：在看过 t3pk 的 ep0、ep29 读数之后定）

- 判据 5（新的 MP-SR、SP-SR 都不低于旧值减 0.05）是在“新参考是不是更好”还没有答案时定的，只防跟踪变差。判据 6 的 A/B 已给出方向：标定内参的参考
  在榜上更好。现在要比的是“跟踪变差多少”与“参考变好多少”。
- 4.0 cm 取的是参考位移的约五分之一：标定内参把物体搬动的量，偏航之后中位约 21 cm（`agent-doc/plan-t3-kfix-2026-10-16.md` 目标一节），k-fix 对 v2
  含偏航 24–29 cm（`results/t3world/kfix_ref_diff.txt`）。只要新参考离真值近的量不少于这一位移的五分之一，跟踪变差 4 cm 以内就不亏。这是按量级的
  假设，没有用榜单的幅度定；榜单的幅度（kfix1017 换的 4 集合计 MPPE −33 cm，ep20 的作用分不出来）与之同向。
- 两个 MPPE 都是对照各自参考的跟踪误差，与参考对真值的误差相加只是近似（三角不等式给的是上界）。SP-SR ≥ 0.5 保证多数世界跟得住。
- 规则定在看过 ep0、ep29 的读数之后：按 S，ep0（+3.03 cm、SP-SR 0.882）与 ep29（+3.13 cm、0.531）都换。为此 G3 的读法把 k-fix 重训与 gb3 重训分开查，
  ep0、29 不单独作为规则 S 的证据。

## 不在这一步

- 提交（要 rxzhou 点头）；Tier 1、Tier 2 的 GPU 安排（明早按 21:10 的读数另写）。
- 跟丢集与二机位集（ep12、14、16、25、28 都跟丢）；k-fix 三集换 gb3；手物偏差修好之后的重生成版本。

## 风险

- 单种子：重训可能达不到旧 run 的跟踪（ep0 的 k-fix 重训从 0.965 降到 0.845）。规则 S 挡掉 MPPE 变差超过 4 cm 或 SP-SR 低于 0.5 的。
- 4.0 cm 的假设不对（新参考并没有近这么多）：会在 G3 的读数上露出来，退回 kfix1017。
- gb3 以原名重生成：我们的副本按哈希表的 sha256 钉住，训练与提交都用钉住的那份；重生成之后要不要换另议。
- ep7 是手持的熨斗，手物偏差 0.4 → 1.5 cm（事实 1），在 ±2 cm 的接触判定内，照训。
- t2m2、t1c_s43 若有失败，`V2D_AFTER_INDEPENDENT=1` 让 Tier 3 照起；那两段的失败按它们自己的计划处理。

## 代价

- 编码与测试：工具 a–f，约 1.5 小时。CPU：记录、搬运约 30 分钟，重定向 11 集约 40 分钟（3 路并行），转到 ml40 约 15 分钟。
- GPU：6 集重训约 14.5 小时卡时，两台并行到 10/18 04:30 前后。
