# Tier 3 换到标定内参参考（gb3）计划（2026-10-17，第 2 版：按独立复核修改）

第 1 版（d3b03d3）经独立复核判 GO WITH FIXES（MAJOR 3、MINOR 6、NIT 3），本版逐条改写，各条改在哪见文末“对第一版复核的处理”。

## 目标

kfix1017 的榜单 A/B 按判据 6 记“完整内参修正在榜上得到支持”，登记的下一步是把 Tier 3 换到标定内参的参考，以另一位用户的 gb3 交付为准
（`agent-doc/plan-t3-kfix-2026-10-16.md` 末节）。本计划做其中跟得住的主机位集：在 gb3 参考上重训 7 集（ep22 进选集另要 rxzhou 点头），
按事先登记的规则逐集决定换不换，目标是 10/18 上午有一份可交的 Tier 3 候选。交不交由 rxzhou 定。全程不读真值、不读 Tier 1、不读 Tier 2 轨迹。

## 事实（核过的）

1. gb3 交付 `tier3_cari4d_gb_best_dr2s_dyn7`（另一位用户 10/16 23:23 MDT 跑完，10/17 交付；交付说明 `results/t3gb3/delivery_md_ml40.txt`，
   逐集来源与指纹 `results/t3gb3/inventory_ml40.txt`）：
   - 30 集，ep28 在 `_suspect`。世界系用标定内参 GB（主机位 f 866.3、cx 701.8、cy 531.1；二机位与侧机位 ep21 同用 GB，交付说明写明侧机位是
     证据不足下的决定），地面校正 1.222°/0.984 保留，二机位尺度 0.949。
   - 每集选的 convert 与 f830_best（我们 hm 参考的来源）逐集相同（30/30）：ep6、7、22 是 convert_v2，ep0、8、18、20、21、24、26、29 是 convert。
   - 版本目录带支撑面：有桌面的 12 集与 best_hm 的 12 集相同（ep2、3、6、7、9、11、13、16、17、20、25、27），其余是空的 Xform（sha256 4f9e5e6f2014…）。
   - 交付说明的已知问题：GB 转换里物体按点映射移动，人体只有骨盆按映射、其余部位随骨盆刚体移动，手持物体的集手离物体远了 1–6.5 cm
     （手到物体表面距离中位 ep01 1.9→7.1 cm、ep16 5.1→10.9、ep02 1.4→3.2、ep10 0.8→2.3、ep19 0.7→1.6、ep07 0.4→1.5、ep04 0.4→1.2、ep09 0.2→0.9、
     ep25 0.2→0.6；大件不变）；ep16 第 106–128 帧拿起时位姿跳变；ep03、ep04 朝向翻转；ep28 重建失败；ep29 脚与行李箱有缺口。
     另一位用户写明修正后以原名重生成，时间未定。
   - 与 k-fix 的关系只核过 convert 一族：10/16 10:57 MDT（gb3 的链跑完之前）比的 7 集（ep0、18、20、22、24、26、29 的 convert 世界步结果），
     物体位置、人体参数逐位相同，朝向最多差 0.33°（`results/t3kfix/kfix_vs_gb3_world_ml40_1016.txt`）。gb3 交付版的 ep22 取的是 convert_v2，
     不在这次比对的范围里；ep6、7 同样。gb3 在世界步之上还有 dr2s（深度后处理）与 dyn7（动力学后处理，只改物体位姿一列）。
   - 人体：gb3 的人体就是所选 convert 的世界步结果（dr2s、dyn7 只改物体位姿一列）。10/16 判据 4 量过的人脚高度只覆盖 convert 一族。
2. 现在榜上的 kfix1017（`stages/evaluate/exports/t3_select_probe1015.tsv`，其中 4 集按 `t3_select_kfix1017.tsv` 换掉）：
   - 已在标定内参参考上：ep18（k-fix 重训），ep24、ep26（v2 策略对 k-fix 参考重新导出：4096 世界 MPPE 3.10、2.85 cm，SP-SR 0.998、0.992，
     `results/t3kfix/reexport_mf4090.txt`）。ep20 是 v2 参考加方块桌面的重训（v2s），参考仍是 f830。
   - 4096 世界、对照各自参考，SP-SR ≥ 0.5 的集 11 个：ep0、6、7、8、18、20、21、22、24、26、29（MPPE 2.1–9.0 cm）；其余 19 集 SP-SR ≤ 0.121、
     MPPE 21–121 cm（`results/t3probe/eval_table_probe1015.txt`；ep18、20 现选的是 t3pk、t3ps 的重训，`results/t3kfix/retrain_switch_t3{pk,ps}_mf4090.txt`）。
3. 现有策略只跟得住训练用的那份参考：k-fix 重新导出时，物体相对机器人根的位置差中位 ep24 0.78 cm，跟住；ep0 6.2 cm，MP-SR 0.965 → 0.000
   （`results/t3kfix/ref_pair_diff_ep{0,24}_mf4090.txt`、`results/t3kfix/reexport_mf4090.txt`）。
4. k-fix 参考上的重训（t3pk，`results/t3kfix/retrain_switch_t3pk_mf4090.txt`），4096 世界对照各自参考：ep18 MPPE 4.25 → 4.63 cm（判换）；
   ep0 2.60 → 5.63 cm（MP-SR 0.965 → 0.845、SP-SR 0.992 → 0.882），ep29 8.00 → 11.13 cm（SP-SR 0.713 → 0.531），按判据 5 都判不换。
5. 跟丢的 19 集的问题在人体：同一配方在 Tier 2 参考上 ep3、12、15、16 的 MP-SR 0.81–0.99，在 Tier 3 参考上都是 0；Tier 3 人体根加速度 p99 的
   中位 47.6 m/s²（Tier 2 4.3）；人体时间平滑的试点里，best_dyn4 上 ep12 的 0.562 换种子没有复现，best_dyn4s 两个种子都是 0
   （`agent-doc/plan-t3dyn-pilot-2026-10-14.md`）。gb3 的人体只比 f830 多了按内参的搬动与缩放，跟丢的原因不变（推断）。
6. 榜：kfix1017 MPPE 55.76705、AUC 0.04885、SP-SR 0.13333、MP-SR 0；G 版 56.87427、0.00690、0.03333、0；FF 的 AUC 0.156。
   kfix1017 上传前，上传器报每个 Tier 3 榜“5 left today”（`results/submission/submit_t3_kfix1017.txt`）。
7. 两张卡 21:00 MDT 前后空出：ml40 的 t1c_s43、mf4090 的 t2m2 各 3 条，16:30 时都在训第 2 条（第 1 条约 2 小时 15 分）。评测链等整段训练写完
   `DAY2_TRAIN_DONE` 才开始（`day2_eval_chain.sh`）。t3pk 三集 13:32 起、20:29 出判据 5 的读数。链在跑时 `scripts/dev/remote` 拒绝同步，新文件用
   push-new-files；`arm_var_chain.sh` 在卡上有别的进程时先停，预演也过不了。
8. 磁盘：mf4090 可用 75 GB，一条 run 约 360 MB；ml40 /lab_data 可用 1.3 TB（`arm_var_chain.sh` 的 t3q 分支要 200000 MB）。
9. 现有工具：`tier3_pack_remote.sh` 与 `tier3_root.py` 已支持交付目录里的支撑面（`V2D_T3_SUPPORT=delivery`、`--support-from-incoming`），
   只有 `tier3_stage_hf.sh` 不支持；`tier3_relay.sh`（mf4090 的档目录、转换与重定向结果经 HF 转到 ml40）；`ref_pair_diff.py`；
   `arm_after.sh`（上一段有一条失败就不起下一段）。

## 范围

- 在 gb3 上训 8 条：
  - mf4090（buffer 400 万，段 t3pg）：ep20、ep0、ep22、ep21；
  - ml40（buffer 1000 万，段 t3qg）：ep6、ep8、ep7、ep29。
  ep0、ep29 已有 k-fix 重训，但判据 5 判了不换，这一轮不拿它们套新规则（复核 MAJOR 1），改在 gb3 上新训，结果出来之前登记规则。
- ep22：10/16 rxzhou 按判据 4 的严读法定了 ep22 留旧参考（人脚 −3.71 cm）。这一版照训，因为卡时没有别的用处；但进不进选集要 rxzhou 推翻 10/16 的决定，
  并先看 gb3 ep22 的人脚检验（判据 G0b）。gb3 的 ep22 来自 convert_v2，与 10/16 量的不是同一份人体，重建版本、内参、后处理三样都换了。
- ep21（侧机位）：排在 mf4090 最后，读数只报，不进下一次提交（A/B 只支持主机位，GB 内参对侧机位是证据不足下的选择）。
- 不在这一轮：ep18、24、26（已在 k-fix 参考上；与 gb3 的差只量、只报）；跟丢的 19 集（事实 5）。

## 做法

### 1. 工具（Mac 上改，各带测试；服务器上只放新文件）

a. `tier3_pack_remote.sh` 与 `tools/t3_episode_remote.sh` 的白名单加 `tier3_cari4d_gb_best_dr2s_dyn7` 与 `_suspect`（两处一起改；两个脚本都经 stdin
   送到 ml40 执行，服务器上不用同步）。已改，d3b03d3。
b. `tier3_stage_hf.sh` 加 `V2D_T3_SUPPORT=delivery`：转给打包脚本，`tier3_root.py` 加 `--support-from-incoming`；与 `V2D_T3_SUPPORT_DIR` 只能设一个
   （同 `tier3_stage.sh`）。打包脚本与 `tier3_root.py` 本来就支持，服务器上不用改。测试 8 例 ALL_OK（`results/t3gb3/test_tier3_stage_hf.txt`）。
c. `make_var_queue.py` 加两个段 t3pg、t3qg（参考 /runs/motion/tier3_gb3/，支撑面按 gb3 自己的，tables 键同 best_hm 的 12 集；run 名
   `t3-ep<N>-w2048-cap4m-r3a-gb3-mf4090`、`t3-ep<N>-w2048-cap10m-r3a-gb3-ml40`）。段名以 t3p、t3q 开头，套用 `arm_var_chain.sh` 现有的两个分支，
   `arm_var_chain.sh` 不改。测试核：正式行、冒烟行、期望表行遮掉 run 名、参考目录、W&B 标签后，与 t3p4、t3q 同集的行逐字相同（ALL_OK）。
   要从队列里拿掉某一集时，用非预设的段名加 `--episodes`（如 `t3qg2 --episodes 6,8,29`；预设段不收 `--episodes`）。
d. `arm_after.sh` 加 `V2D_AFTER_INDEPENDENT=1`：第 5 步（上一段全部做完才起）只记录、不拦；等链结束、卡空、来历与队列不变、预演与起链各步照旧。
   测试 9 组 ALL_OK（`results/t3gb3/test_arm_after.txt`）。用法见做法 3.2。
e. `stages/evaluate/gb3_switch.py`：按规则 S（判据 G2）逐集判，现选 run 的值写死在 `stages/evaluate/gb3_switch_t3pg.json`、`gb3_switch_t3qg.json`
   （来源逐项注明），新值读评测链写的 `eval_<步数>_w4096.json` 并核参考在 tier3_gb3 下。测试 ALL_OK。
f. `stages/evaluate/t3_refdiff_batch.sh`：按清单 `stages/evaluate/exports/t3_gb3_refdiff_pairs.tsv`（旧参考目录逐集写明：ep6、7、8、21 是 tier3_hm，
   ep0、22、24、26、29 是 tier3_v2，ep20 是 tier3_v2s，ep18 是 tier3_kfix；另加 ep0、18、24、26、29 的 k-fix → gb3）逐行跑 `ref_pair_diff.py`
   （mf4090，CPU 容器）。只报。
g. `stages/recovery/t3_gb3_feet.sh`（第 2 版新加）：在 ml40 上用另一位用户的 `t3_feet_diag.py` 量 gb3 人体的支撑脚高度，convert_gb3 与 convert_v2_gb3
   各建一个只读挂载的影子根，地面拟合取 `floor_fit_gb3.json`（判据 G0b）。

### 2. 搬运与重定向（CPU，21:00 前做完）

1. 记录（已做，`results/ops/t3_episodes_ml40_1017_gb3.txt`、`results/ops/t2_inputs_mf4090_1017_gb3.txt`，11 集：ep0、6、7、8、18、20、21、22、24、26、29）。
2. 哈希表 `stages/recovery/expect/t3gb3_11_1017.tsv`（54 行：11 集的 parquet、元数据、支撑面各 11 行，网格 10 行（ep0、ep21 共用一份），地面 11 行），
   已提交并放到 mf4090。
3. 拼档目录：`V2D_T3_SUBDIR=tier3_cari4d_gb_best_dr2s_dyn7 V2D_T3_SET=gb3 V2D_T3_SUPPORT=delivery scripts/dev/record t3gb3/stage_hf_mf4090
   stages/recovery/tier3_stage_hf.sh t3gb3_11_1017 0 6 7 8 18 20 21 22 24 26 29`，要 `TIER3_ROOT_OK`。
4. 重定向（mf4090 的 tmux，CPU，eps.sh 逐集顺序跑，11 集约 40 分钟）：`V2D_T3_SET=gb3 scripts/dev/record t3gb3/retarget_mf4090
   stages/retarget/eps.sh 3 20 0 22 21 6 8 7 29 18 24 26`；随后 `check_inputs.py` 核 11 份 motion parquet；有桌面的 ep6、7、20 用 `support_kinds.py`
   与 `support_import_check.py` 核训练场景里的支撑面建得出来（同 best_hm 计划第 9 步）。
5. 转到 ml40：`scripts/dev/record t3gb3/relay_ml40_hf stages/recovery/tier3_relay.sh gb3 11 <文件数> t3gb3_1017a`，要 `RELAY_OK`。
6. 参考差（只报）：`scripts/dev/record t3gb3/refdiff_mf4090 stages/evaluate/t3_refdiff_batch.sh stages/evaluate/exports/t3_gb3_refdiff_pairs.tsv`。
7. 人脚（ml40，与第 4–6 步同时）：`scripts/dev/record t3gb3/feet_gb3_ml40 bash stages/recovery/t3_gb3_feet.sh`（setsid 后台）。
8. HF 中转仓的 README（`docs/hf/v2d-track2-transfer/README.md`）补 t3kfix_5_1016、t3gb3_11_1017、t3gb3_1017a 三个标签，上传 README。

### 3. 训练（GPU，21:00 起，服务器自己接上）

1. 队列：t3pg、t3qg 的队列与导出清单提交、推送，push-new-files 放到对应机器；两台各跑 `fc_config_check.sh`（冒烟与正式，意外差异 0）与
   `precheck_expect.sh`（都不占 GPU）。`arm_var_chain.sh` 的预演在卡上有进程时过不了，留给 `arm_after.sh` 第 8 步在卡空之后做（复核 MAJOR 3）。
2. 挂接：`stages/policy/arm_after.sh` 复制成两台的 `runs/tools/arm_after.sh`（复制前看没有在等的 arm_after 进程，复制后记 md5），各 setsid 起一个：
   - mf4090：`V2D_AFTER_INDEPENDENT=1 V2D_POLL_S=60 V2D_AFTER_MAX_POLLS=720 setsid nohup bash runs/tools/arm_after.sh t3pg runs/logs/t2m2_train_mf4090.log
     runs/logs/t2m2_eval_mf4090.log runs/logs/cand_t2_t2m2_mf4090.log 3 > runs/logs/arm_after_t3pg_mf4090.log 2>&1 < /dev/null &`
   - ml40：`V2D_AFTER_INDEPENDENT=1 V2D_POLL_S=60 V2D_AFTER_MAX_POLLS=720 setsid nohup bash runs/tools/arm_after.sh t3qg runs/logs/t1c_s43_train_ml40.log
     runs/logs/t1c_s43_eval_ml40.log runs/logs/cand_t1_t1c_s43_ml40.log 3 > runs/logs/arm_after_t3qg_ml40.log 2>&1 < /dev/null &`
   起完核两份日志的第一行。日志最后一行是 `ARM_AFTER_STOPPED <原因>` 时（例如空档里卡被别人占了，`arm_var_chain.sh` 不重试）：21:10 的检查若 Mac 在线就
   手动处理；否则早上手动起。
3. 读数：两台各起 `run_after_log.sh`，等评测日志的 `DAY2_EVAL_(DONE|FAILED)`，跑 `python3 stages/evaluate/gb3_switch.py stages/evaluate/gb3_switch_<段>.json`，
   记录 `results/t3gb3/switch_t3pg_mf4090.txt`、`results/ml40/t3gb3/switch_t3qg_ml40.txt`（拉回后的路径；V2D_MAX_POLLS 1080，约 18 小时）。
4. 预计（估计，每条约 2.2 小时）：两台各 4 条，训练约 05:50 写完；评测链随后开始，评测与导出约 06:40 做完，两份读数 07:00 前后出来。

### 4. 选集与打包（10/18 上午）

1. 选择清单 `stages/evaluate/exports/t3_select_gb1018.tsv`：kfix1017 的 30 行，判换的集换成新 run（ep22 要 rxzhou 点头，ep21 不进）。
2. 换的集：导出拉回（`pull_submission.sh` 按 sha256 核），frame refs 用 `make_frame_refs_t3.py`（默认模式，新 run 训练用的就是 gb3，从 run 记录取；
   ml40 的 run 在 ml40 的容器里生成）；合并时 `merge_frefs_t3.py --take-plain`（gb3 的世界系已含偏航）；没换的集沿用 kfix1017 的 frame refs。
3. 逐集并列报：候选与现选 run 的 4096 世界 MPPE、SP-SR、MP-SR，导出那一个世界的 SP、MP 是否成功（让 rxzhou 看到 SP-SR 榜的风险）。
4. `pack_tier.sh` 打包、官方打包器 PACK_OK、上传预演；与 kfix1017 的 CSV 逐行比，只有换的集不同。交不交由 rxzhou 定。

## 判据（跑之前登记）

- G0 搬运与重定向：`TIER3_ROOT_OK`、`RELAY_OK`；重定向 `EPS_DONE`、没有 `FAIL:*` 的集才留在队列里；`ALIGN`、`NOCONTACT` 照训、在报告里标出（同以往 Tier 3）；
  ep6、7、20 的桌面在训练场景里建不出来，这一集拿出队列（做法 1c 的非预设段）。
- G0b 人脚（只报，供 rxzhou 定 ep22）：gb3 人体世界步之后支撑脚高度中位，逐集报；ep22 另与 10/16 的 −3.71 cm（convert）并列。
- G1 参考差：只报，不判。登记一个预期：7 集的物体相对机器人根位置差中位都超过 2 cm（推断：深度乘 1.04–1.09，另有 dr2s、dyn7 与 hm 后处理的差）。
- G2 换集规则 S，只用于这一轮新训的 gb3 run（结果出来之前登记）：4096 世界、对照各自参考、同一评测器，
  **候选 MPPE ≤ 现选 run 的 MPPE + 4.0 cm，且候选 SP-SR ≥ 0.5** 才换。现选 run 的值（MPPE cm / SP-SR）：ep0 2.60/0.992、ep6 3.79/0.978、
  ep7 2.11/0.997、ep8 2.32/0.999、ep20 5.77/0.891、ep22 3.70/0.980、ep29 8.00/0.713（ep21 8.96/0.876，只报）。
  两个条件是连着的：4096 世界的 MPPE 含跟丢的世界，SP-SR 掉下去时 MPPE 也会涨。
- G3 提交的读法（只在 G2 判换的集不少于 3 集时提议交；ep22 只在 rxzhou 点头后计入；ep21 不计；交不交由 rxzhou 定）：
  记新版为 MK2，kfix1017 的 MK1 = 55.76705，τ = 1.0 cm：
  - MK2 ≤ MK1 − τ：记“放宽跟踪要求、换到标定内参在榜上得到支持”，新版作为现选；下一轮考虑 ep21、ep18/24/26 换 gb3；
  - MK2 ≥ MK1 + τ：记“不支持”，现选退回 kfix1017，停下来另写计划，不再用第二次提交拆分；
  - 之间：记“看不清”。新版的 AUC 与 SP-SR 都不低于 kfix1017 时新版作为现选，否则退回 kfix1017。
  - AUC、SP-SR、MP-SR 照报；AUC 比 kfix1017 高 0.005 以上单独记。
- G4：任何一步不读真值、不读 Tier 1、不读 Tier 2 轨迹；不按榜上分数挑参数。

## 规则 S 的来由

- 判据 5（新的 MP-SR、SP-SR 都不低于旧值减 0.05）是在“新参考是不是更好”还没有答案时定的，只防跟踪变差。判据 6 的 A/B 已给出方向：标定内参的参考
  在榜上更好。现在要比的是“跟踪变差多少”与“参考变好多少”。
- 4.0 cm 是一个假设：新参考离真值近的量，不少于参考位移的五分之一（偏航之后中位约 21 cm，`agent-doc/plan-t3-kfix-2026-10-16.md` 目标一节；
  k-fix 对 v2 含偏航 24–29 cm，`results/t3world/kfix_ref_diff.txt`）。五分之一这个比例没有别的依据，由 G3 的榜单读数来检验；
  榜单的幅度（kfix1017 换的 4 集合计 MPPE −33 cm，ep20 的作用分不出来）与之同向，但没有拿来定数。
- 单独标注：4.0 cm 是在看过 t3pk 的 ep0（+3.03 cm）、ep29（+3.13 cm）之后写下的，取 3.0 cm 就会把这两集挡掉。为此这一轮规则 S 只用于新训的
  gb3 run，已有的 k-fix 重训照判据 5 不换。
- 两个 MPPE 都是对照各自参考的跟踪误差，与参考对真值的误差相加只是近似（三角不等式给的是上界）。SP-SR ≥ 0.5 保证多数世界跟得住。

## 不在这一步

- 提交（要 rxzhou 点头）；ep22 进不进选集（要 rxzhou 点头）；Tier 1、Tier 2 的 GPU 安排（明早按 21:10 的读数另写）。
- 跟丢集与二机位集（ep12、14、16、25、28 都跟丢）；k-fix 三集换 gb3；手物偏差修好之后的重生成版本。

## 风险

- 单种子：重训可能达不到旧 run 的跟踪（ep0 的 k-fix 重训从 0.965 降到 0.845）。规则 S 挡掉 MPPE 变差超过 4 cm 或 SP-SR 低于 0.5 的。
- 4.0 cm 的假设不对（新参考并没有近这么多）：会在 G3 的读数上露出来，退回 kfix1017。
- gb3 以原名重生成：我们的副本按哈希表的 sha256 钉住，训练与提交都用钉住的那份；重生成之后要不要换另议。
- ep7 是手持的熨斗，手物偏差 0.4 → 1.5 cm（事实 1）；ep29 脚与行李箱有缺口（交付说明）。照训，读数里标出。
- 夜里空档有别人占卡，`arm_var_chain.sh` 不重试，那一台就空到早上（做法 3.2）。
- t2m2、t1c_s43 若有失败，`V2D_AFTER_INDEPENDENT=1` 让 Tier 3 照起；那两段的失败按它们自己的计划处理。

## 代价

- 编码与测试：工具 a–g，约 2 小时（已做完 a–f）。CPU：搬运约 30 分钟，重定向 11 集约 40 分钟，转到 ml40 约 15 分钟，人脚约 20 分钟。
- GPU：8 条重训，两台各约 9 小时，到 10/18 07:00 前后。

## 对第一版复核的处理

| 条目 | 处理 |
|---|---|
| MAJOR 1 规则 S 事后定 | 规则 S 只用于新训的 gb3 run；ep0、29 改在 gb3 上新训，已有的 k-fix 重训照判据 5 不换；五分之一写明是 G3 检验的假设；“分开查”删掉 |
| MAJOR 2 ep22 | 写明推翻 10/16 的决定要 rxzhou 点头；gb3 的 ep22 来自 convert_v2，加人脚检验（工具 g、判据 G0b）；照训，进选集另批 |
| MAJOR 3 预演过不了 | 开链前只跑 `fc_config_check.sh` 与 `precheck_expect.sh`，预演留给 `arm_after.sh` 第 8 步 |
| MINOR 4 | 1b 改为只改 `tier3_stage_hf.sh`；1a、2.1 写明已做 |
| MINOR 5 | 时间表改为整段训练写完才评测 |
| MINOR 6 | 参考差的旧参考目录逐集写明 |
| MINOR 7 | 挂接命令写全；`ARM_AFTER_STOPPED` 的处理写明 |
| MINOR 8 | G3 写明“看不清”与“不支持”时选哪一版；选集时并列报导出世界的成功与否 |
| MINOR 9 | 拿掉某集用非预设段加 `--episodes` |
| NIT 10 | 事实 1、2、5、6、7 按复核改 |
| NIT 11 | HF 中转仓 README 补三个标签（做法 2.8） |
| NIT 12 | 重定向改为逐集顺序跑 |

## 执行记录（10/17 晚）

- 16:3x 记录与哈希表（做法 2.1、2.2）：`results/ops/t3_episodes_ml40_1017_gb3.txt`、`results/ops/t2_inputs_mf4090_1017_gb3.txt`、
  `stages/recovery/expect/t3gb3_11_1017.tsv`（54 行）；jev 核了 9 条事实，0.92–0.98，3 道对照题都判不支持（`results/t3gb3/jev_plan_facts.txt`；
  第一次把 ep0、ep29 合成一条，0.58，拆开重跑，`jev_plan_facts_try1.txt`）。
- 16:41 拼档目录（`results/t3gb3/stage_hf_mf4090.txt`）：34 个文件经 HF 转到 mf4090，`TIER3_ROOT_OK`。记录里“parquet 在对方的修改时间 22:41 UTC”
  是 HF 拉取落盘的时间：另一位用户的 gb3 链 10/16 23:23 MDT 跑完后数据目录没再动过，交付说明与支撑面目录的修改时间是 10/17 08:49 MDT；
  11 个 parquet 的 sha256 与 16:28 的记录相同。
- 16:42–17:07 重定向（`results/t3gb3/retarget_mf4090.txt`）：11 集 `EPS_DONE`，没有 `FAIL:*`；ep29 `OK+NOCONTACT`（脚推行李箱，两手接触都是 0，
  v2 参考上也是 NOCONTACT），其余 `OK`；间隙 −0.5 到 0.0 mm（v2、k-fix 参考上 ep26 是 −28.1、−35.6 mm）。
  `check_inputs.py` 11 份都过（`results/t3gb3/check_inputs_mf4090.txt`；第一次也过了，我判断记录的写法有误把它当成失败重跑了一次，
  `check_inputs_mf4090_try1.txt`）。支撑面（`support_kinds_{root,stage}_mf4090.txt`）：档目录与训练场景里的 11 份 md5 相同；ep6、7、20 是
  一块缩放过的 Cube，用训练挂的 p185 导入器建出来是 BOX（`support_import_p185_mf4090.txt`），其余 8 集是空的 Xform。G0 过。
- G0b 人脚（`results/ml40/t3gb3/feet_gb3_ml40.txt`，世界步之后支撑脚高度中位）：ep22（gb3 用的 convert_v2）−3.77 cm，convert 一族的 ep22 −3.71 cm，
  10/16 旧链 −3.76 cm，三份基本相同；ep6（convert_v2）−4.35 cm，旧链 −4.25 cm（旧策略在它上面 SP-SR 0.978）。即 ep22 人脚低的问题与参考版本无关。
- G1 参考差（`results/t3gb3/refdiff_mf4090.txt`，物体相对机器人根的位置差中位）：训练参考 → gb3，ep6 3.61 cm、ep8 1.59 cm、ep7 4.15 cm、ep20 2.52 cm、
  ep22 3.62 cm、ep21 6.26 cm、ep0 5.21 cm、ep29 5.50 cm；k-fix → gb3，ep0 1.05 cm、ep18 0.97 cm、ep24 0.86 cm、ep26 1.80 cm、ep29 5.82 cm。
  登记的预期（7 集都超过 2 cm）在 ep8 上不成立：ep8 只差 1.59 cm，原策略对 gb3 重新导出也许够；按登记这一轮仍重训。
- 17:11 mf4090：`fc_config_check.sh` 8 份配置意外差异 0（`results/t3gb3/cfgcheck_t3pg_mf4090.txt`），`precheck_expect.sh` 4 条全过
  （`precheck_t3pg_mf4090.txt`；第一次少给了期望表，用法错，`precheck_t3pg_mf4090_badargs.txt.failed`）。
  17:12 `runs/tools/arm_after.sh`（md5 07173c9b…，新加 `V2D_AFTER_INDEPENDENT`）挂上 t3pg，等 t2m2 的链结束、卡空（`results/t3gb3/arm_after_t3pg_launch_mf4090.txt`，
  日志 `runs/logs/arm_after_t3pg_mf4090.log`）；读数等待进程挂上（`results/t3gb3/after_switch_t3pg_launch_mf4090.txt`，日志
  `runs/logs/after_switch_t3pg_mf4090.log`，最多 1080 次）。
- G0b 补充（同一份记录，gb3 实际用的 convert）：convert 一族 ep0 −0.61、ep8 −3.29、ep18 −0.15、ep20 +1.62、ep21 +0.89、ep24 −0.49、ep26 −2.88、
  ep29 −2.55 cm；convert_v2 一族 ep6 −4.35、ep7 −0.37、ep22 −3.77 cm。convert 一族的 7 集与 10/16 k-fix 的判据 4 读数相差 0.07 cm 以内。
- 17:20 转到 ml40（`results/t3gb3/relay_ml40_hf.txt`）：HF 上传 43 秒、下载 496 秒，199 个文件 850.5 MB，两端 sha256 清单逐行相同，`RELAY_OK`。
  HF 中转仓 README 补了 t3kfix_5_1016、t3v2s_20_1016、t3gb3_11_1017、t3gb3_1017a 四个标签并上传（`results/ops/hf_readme_v2d_track2_transfer_gb3.txt`，
  `HF_README_OK`，仓库私有）。
- 17:22 ml40：`fc_config_check.sh` 8 份意外差异 0、`precheck_expect.sh` 4 条全过（`results/ml40/t3gb3/cfgcheck_t3qg_ml40.txt`、`precheck_t3qg_ml40.txt`）。
  17:23 `runs/tools/arm_after.sh`（md5 07173c9b…）挂上 t3qg，等 t1c_s43 的链结束、卡空（`results/t3gb3/arm_after_t3qg_launch_ml40.txt`，
  日志 `runs/logs/arm_after_t3qg_ml40.log`）；读数等待进程同时挂上（日志 `runs/logs/after_switch_t3qg_ml40.log`）。
- 10/18 上午（第 4 节）：规则 S 判换 ep0、6、7、8、20（ep22 达标，要 rxzhou 点头），不换 ep21、29。选择清单 `stages/evaluate/exports/t3_select_gb1018.tsv`
  （kfix1017 的 30 行换 5 集）与 `t3_select_gb1018e22.tsv`（另换 ep22）；6 集的导出按 sha256 拉回（`results/t3gb3/pull_select_gb1018.txt`），帧参考在各自机器的
  容器里按 run 记录的 gb3 参考生成（`results/t3gb3/frame_refs_gb1018_{mf4090,ml40}.txt`，FRAME_REFS_T3_OK 3 + 3），与 kfix1017 其余各集的帧参考合并
  （新的一侧 --take-plain，`results/t3gb3/merge_frefs_gb1018{,e22}.txt`）；轨迹目录只换这几集（`results/t3gb3/t3dir_gb1018{,e22}.txt`）。
  打包与预演都过：`runs/submission/csv/track2_tier3_gb1018.csv`（sha256 2e7ac77d…）、`track2_tier3_gb1018e22.csv`（dc376a2b…），提交链接 1178467；
  与 kfix1017 的 CSV 逐行比，内容不同的恰好是换的集（`results/t3gb3/csvdiff_gb1018{,e22}_vs_kfix1017.txt`）。
- 逐集并列（`results/t3gb3/switch_table_gb1018.txt`，对照各自的重建参考）：ep0 的 gb3 run 导出那 1 局 SP 0、MP 0、MPPE 25.73 cm（现选那条 1 / 1 / 2.25 cm），
  而它的 4096 世界 SP-SR 0.936、MP-SR 0.916，是导出抽样的坏运气；其余几集导出的成败与现选相同（ep7、8、22 都是 1 / 1，ep6、20 都是 1 / 0）。
  ep0 这一局若在真值上也偏这么多，单这一集会让 Tier 3 MPPE 高约 0.8 cm（23.5 / 30），与 G3 的 τ = 1.0 cm 同量级，会让读数偏向“看不清”。不提交；交不交、交哪份由 rxzhou 定。
