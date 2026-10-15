# 逐帧终止分析：Tier 3 与 Tier 1 丙（2026-10-14 晚）

第 2 版。第 1 版经独立审查（Fable 5.1）为 GO WITH FIXES，15 条意见全部采纳，逐条处理见第 8 节。主要改动：长链标记写内容（空标记挡不住同步）；
证据表的布尔列核取值；富集读法加机会水平、排除起点太早的 run、B 上限改 0.5；F_flip 改名“短翻转”，另加单帧跳变，写明成段翻转这张表测不了；
帧号对齐改由评测 JSON 的 start_frame 与 reference_end_fraction 把门；接触取法先与评测器的参考对象对一次。

目的：查清失败的世界在第几帧、因为哪一项越线。Tier 3 用来回答另一位用户等着的问题（失败是不是集中在翻转帧与遮挡段），Tier 1 用来做
`plan-first-place-2026-10-14.md` 的选项丙（跟丢的集骨盆在哪一刻失守、和接触的先后）。只报，不据此起训练；训练计划另写、另审。
用户 10/14 23:4x 要求写这份计划，审过后在两台卡上跑。

## 1. 事实

- **两台 GPU 空着**：23:33 两台都是 0 MiB、0%，我们没有链在跑；mf4090 上另一个用户的视觉容器不占 GPU（`results/ops/gpu_procs_mf4090_1014_2333.txt`、
  `results/ops/gpu_procs_ml40_1014_2333.txt`）。另一位用户在 ml40 上用 CPU 复查 best_dyn7（`results/ops/t3_queue_ml40_1014_2333.txt`）。
- **另一位用户在等这份分析**：交接 197a02f 写“是否往重建侧投入，等逐帧终止分析：先确认失败是否集中在翻转帧与遮挡段”，并给出 best_hm 的逐帧证据表
  `$T/dev/perframe/hm/epNN.csv`（`results/t3dyn/handoff_tier3_197a02f.txt`）。快照 `results/ops/t3_perframe_hm_ml40_1014_2355.txt`：30 集的行数、
  表头、state 与 evidence 两列的取值、31 个文件的 sha256；18 条 best_hm 的行数都等于评测的 step_count。表头：episode, frame, state, label_left,
  label_right, limb_d_m, viol_object_any, viol_lin_held, viol_lin_airborne, viol_lin_supported, viol_rot_torque, viol_rot_jump, viol_rot_jump_symmetric,
  viol_rest_drift, viol_rot_drift, viol_root_acc, turn_prev_deg, dev_local_deg, orient_outlier, mask_px, iou, evidence。布尔列的取值快照里没记，拷贝时补记。
- **证据表测得到和测不到的**：`orient_outlier` 是“与前后 15 帧多数朝向差 > 45°”，按构造只抓 15 帧以内的短翻转；另一位用户四次探针都分不开的是
  成段翻转（整段朝向错），这张表测不了。已对照视频确认的只有 ep04 第 313、509、669 帧球棒头尾颠倒（交接 197a02f）。交接还写 best_hm 29 集都在开头
  30 帧内就有物体违规，所以起点若也在开头，会和旗标“同在开头”。
- **帧号 = 步号**的依据：评测 JSON 顶层 `start_frame 0`、`reset_mode explicit`，`reference_tracking.reference_end_fraction 1.0`
  （`results/day2/eval_t3-ep15-w2048-cap4m-r3a-dyn4-mf4090_s349999104.txt`）；评测器的 `reference_frame = step`，起始帧 0
  （`agent-doc/plan-box6-and-eval-runtime-2026-10-01.md` 第 7 条）；diag2 的手掌坐标帧闸与评测器差 8.14e-07 m（错一帧约 0.05 m，
  `results/diag2/phase_t1-ep16-w2048-cap4m-mf4090.txt`）。本计划逐条再核 start_frame、reference_end_fraction 与参考帧数。
- **工具已有**：`stages/evaluate/fc_eval_dump.sh <run> <步数>` 用 8c778f9 评测器评 4096 世界，并把逐步、逐世界的跟踪误差（float16）存成
  `runs/flash_chord/<run>/eval_dump/eval_<步数>_w4096.{json,npz}`；结果已在就直接返回；GPU 上有别的进程就拒绝（退出码 6）。npz 每条约 42 MB
  （`agent-doc/plan-t1-fall-order-2026-10-07.md`）。`stages/evaluate/fall_order.py` 定义失败世界、t_obj、t_pel、t_palm 与“物体先 / 骨盆先 / 同时”（k = 25 步），
  门有 MP-SR 复现 `REPRO_MP = 0.01`；`fall_order_one.py` 是单条 run 的驱动（选项丙第 0 步，已审）。
- **复现门的旧记录**：10/7 那次 8 条 run 的新评与原评 MP-SR 差最大 0.0142，当时登记偏离，把门放到 0.025（`results/r3/fall_order_t1.txt`）。
  10/14 查明同一 checkpoint 每次导出的那 1 局都不一样（`results/first/zero_ep19_ml40.txt`），所以 4096 世界的复评与原评之间有抽样差。
- **用时**：mf4090 每条约 4.2 分钟（`t3pdyn` 3 条 12 分 42 秒，`results/t3dyn/health_t3pdyn_mf4090.txt`）；ml40 每条约 5.7 分钟（`t3qdyn` 2 条
  11 分 24 秒，`results/t3dyn/health_t3qdyn_ml40.txt`）。
- **Tier 3 的 run**（4096 世界 MP-SR，对照各自参考）：
  - best_hm，mf4090，`t3-ep<N>-w2048-cap4m-r3a-hm-mf4090`：ep15、17、1、2、3（`results/t3p4/eval_table_t3p4a.txt`），ep12、13、14、16、19、21、25、27
    （`results/t3p4/eval_table_t3p4b.txt`）；ep21 是 0.501，其余 0.000。
  - best_hm，ml40，`t3-ep<N>-w2048-cap10m-r3a-hm-ml40`：ep4 0.000、ep5 0.000、ep6 0.198、ep7 0.996、ep8 0.998（`results/t3q/eval_table_t3qa.txt`）。
  - 试点：`t3-ep15-w2048-cap4m-r3a-dyn4-mf4090`（0.000）、`t3-ep12-w2048-cap4m-r3a-dyn4-ml40`（0.562）、`t3-ep12-w2048-cap4m-r3a-dyn4s-ml40`（0.000）。
  - 不分析：ep3、ep16 的 dyn4 run（参考朝向错，`results/t3dyn/handoff_tier3_dynamics_3e38561.txt`）；`-v2-` 的旧版 run。
- **Tier 1 丙的 run**（t1c1014b 交上去的，`stages/evaluate/exports/t1_select_t1c1014b.tsv`）：mf4090 的 `t1-ep1-w2048-cap4m-p185-mf4090`、
  `t1-ep11-w2048-cap4m-mf4090`、`t1-ep28-w2048-cap4m-p185-mf4090`；ml40 的 `t1-ep2-w2048-cap10m-r3a-ml40`、`t1-ep4-w2048-cap10m-ml40`、
  `t1-ep9-w2048-cap10m-ml40`、`t1-ep25-w2048-cap10m-ml40`。这 7 集占 t1c1014b 的 MPPE 合计 87.8%。与登记的丙相比的偏离见第 8 节第 9 条。
- **接触**：参考 parquet 是单行表，`hand_sides` 与 `hand_contact_active`（2 × T）两列（mf4090 上 ep15 best_hm 实查：左手 0 帧、右手 399 帧，
  与重定向记录一致）。`diag_rollout.py` 用的是评测器参考对象的 `contact_active(side)`；两种取法先对一次（第 3 节第 4 步）。
- **长链的约定**：`stages/evaluate/export_chain.sh` 的骨架——起链写 `runs/.chain-active-<日志名>`、退出时删；GPU 上有进程就每分钟看一次，
  最多等 `V2D_GPU_WAIT_S`（默认 7200 秒）；预检模式；日志里不抄链结束标记的原文。`scripts/dev/remote` 是 `cat runs/.chain-active-*` 后判非空，
  所以标记必须写内容（`export_chain.sh` 的 `touch` 有同样的隐患，另记，不在本计划改）。

## 2. 做什么、不做什么

- 两台各起一条 dump 链，Tier 3 在前：mf4090 17 条（`stages/evaluate/frames/dump_mf4090_1014.txt`：Tier 3 best_hm 13 条、dyn4 ep15、Tier 1 3 条），
  ml40 11 条（`stages/evaluate/frames/dump_ml40_1014.txt`：Tier 3 best_hm 失败的 ep4、5、6，ep12 两版，Tier 1 4 条，最后是跟上的 ep7、ep8）。
- 链结束后在各自机器的容器里跑分析，结果落 `results/frames/`，拉回 Mac；Tier 3 best_hm 的结果再与证据表快照对照（Mac 上）。
- 不做：任何训练；Tier 2 的 8 集；diag2；ep3、ep16 的 dyn4 run。分析只用 4096 世界的复评（与 10/14 用户定的“以 4096 世界为主”一致）。

## 3. 做法

0. **代码**（不用 GPU；已写、测试已过，提交后才用）：
   - `stages/evaluate/dump_chain.sh <清单> <日志名>`：照 `export_chain.sh` 的骨架，清单每行 `run 步数`。起链写非空标记（日志名、来历、时间）；
     先核 `V2D_FC_SRC` 再等 GPU；逐行：已有 dump 记 `exists`，NONFINITE 记 `nonfinite`，没有 policy 记 `no_policy`，`fc_eval_dump.sh` 退出码 6 就等
     GPU 空了重跑这一行（最多等 `V2D_GPU_WAIT_S`，等不到停整条链），其他失败记 `failed`、接着下一行；结果表 `runs/frames/<日志名>.tsv`；
     结尾 `DUMP_CHAIN_DONE（成功 x、失败 y）` 或 `DUMP_CHAIN_FAILED`。预检 `V2D_DUMP_CHAIN_DRYRUN=1`：副本核对、别的长链标记、残留的 `fc-evaldump-*`
     容器、磁盘余量（行数 × 60 MB + 1 GB）、每行的 policy、NONFINITE 与原评测（4096 世界、无非有限世界），全过打 `DUMP_DRYRUN_OK`。
     测试 `test_dump_chain.py`（假 `fc_eval_dump.sh`、`nvidia-smi`、`df`、`docker`；bash 4，在 mf4090 上跑）。
   - `stages/evaluate/fail_onset.py`（容器里）：每条 run 调 `fall_order.run_one` 得每个世界的 t_obj、t_pel、t_palm，读参考接触；按第 4 节的门；
     输出 `results/frames/<段名>/onset_<run>.json`（每帧越线计数、接触、阈值、门与汇总）与同名 `.txt`。一次只收同一档，t2、t3 先装 Tier 1 禁读。
     测试 `test_fail_onset.py`（9 个）。
   - `stages/evaluate/t3_onset_evidence.py`（Mac）：按第 4 节的旗标、窗口、门与读法对照；先装 Tier 1 禁读。测试 `test_t3_onset_evidence.py`（6 个）。
   - `stages/evaluate/contact_check.py`（容器里）：parquet 的接触与 diag2 npz 里评测器参考对象的接触逐帧比，打 `CONTACT_SAME` 或 `CONTACT_DIFF`。
   - `tools/t3_evidence_fetch.sh`（Mac）：只读拷证据表，31 个文件逐个比快照登记的 sha256，补记布尔列取值，全对才落盘，打 `T3_EVIDENCE_FETCH_OK`。
1. **提交、拷证据表**：提交第 0 步的文件与清单；`scripts/dev/record t3frame/evidence_fetch_hm tools/t3_evidence_fetch.sh
   results/t3frame/evidence_hm_1015_1235cst results/ops/t3_perframe_hm_ml40_1014_2355.txt`（目录名用文件时间 10/15 12:35–12:50 CST）。
2. **同步与测试**：两台都没有链在跑；`scripts/dev/remote` 各同步一次（`results/ops/sync_<机器>_<时间>.txt`）；mf4090 跑三套测试（bash 4 与容器），
   ml40 在容器里跑两套 Python 测试，都要全过。起链之后两台都不再同步；真要补已提交的新文件只用 `scripts/dev/push-new-files`。
3. **起链**：两台各先预检（`DUMP_DRYRUN_OK`），再在 tmux 里起：
   `V2D_FC_SRC=<8c778f9 副本> stages/evaluate/dump_chain.sh stages/evaluate/frames/dump_<机器>_1014.txt frames_<机器>_1014`
   （副本：mf4090 `/home/rxzhou/v2d/fc_src/fc_8c778f9`，ml40 `/lab_data/rxzhou/v2d/fc_src/fc_8c778f9`）。起之前记一次 GPU 进程快照。
4. **接触核对**（mf4090、CPU、可与链同时）：`scripts/dev/record frames/contact_check_t1ep16 scripts/dev/in-flash-chord "cd /repo && python
   stages/evaluate/contact_check.py runs/diag2/t1-ep16-w2048-cap4m-mf4090/rollout_w4096.npz t1-ep16-w2048-cap4m-mf4090"`。`CONTACT_SAME` 才报接触三段。
5. **分析**（各台链结束后，每台分两档各调一次）：
   `scripts/dev/record frames/onset_t3_<机器> scripts/dev/in-flash-chord "cd /repo && python stages/evaluate/fail_onset.py /repo/results/frames/t3_<机器> <该机 t3 run…> --repro noise"`；
   `scripts/dev/record frames/onset_t1_<机器> scripts/dev/in-flash-chord "cd /repo && python stages/evaluate/fail_onset.py /repo/results/frames/t1_<机器> <该机 t1 run…> --repro fixed"`；
   Tier 1 的 7 条另跑登记的 `fall_order_one.py`（`frames/fall_order_one_t1_<机器>`，门与判法不改）。拉回后在 Mac 上：
   `scripts/dev/record frames/t3_onset_evidence <带 numpy 的 python> stages/evaluate/t3_onset_evidence.py results/t3frame/evidence_hm_1015_1235cst
   results/frames/t3_mf4090/onset_t3-*-hm-*.json results/ml40/frames/t3_ml40/onset_t3-*-hm-*.json`（ml40 的结果拉回到 `results/ml40/`；脚本要求恰好是
   登记的 18 集）。链跑着时两台不能同步：分析脚本按约定复制到 `runs/tools/frames/` 再跑，记 md5，与提交里的逐字相同。
6. **记录**：执行记录、jev（数字与判读，带对照）、提交；给另一位用户的摘要经用户转。

## 4. 判据（执行前登记，不改）

**门**（每条 run 单独判；不过的那条记“门不过”、不进分类与对照，其余照常）：

- G1：npz 与新评 JSON 的 MP-SR 差 < 1e-9，误差数组形状等于 (step_count, world_count, 6)（`fall_order.run_one`）。
- G2：新评与原评测 JSON 的 checkpoint sha256 相同。
- G3：MP-SR 复现。Tier 1 丙的 7 条按登记的 0.01（`--repro fixed`）。Tier 3 的 21 条用 |新 − 原| ≤ max(0.01, 3·√(2p(1−p)/N))（`--repro noise`），
  p 取原评测的 MP-SR，N 取新评的世界数（p = 0.5 时约 0.033）。两种都另打 z = 差 / √(2p(1−p)/N)。MPPE 差只报。
- G4：同一次调用的 run 之间骨盆、手掌、物体位置阈值与 active_after_step 相同，同一变体的物体朝向阈值相同（与多数不同的那条门不过）；
  Tier 3 对照时 18 条 best_hm 之间再比一次，物体朝向阈值必须是 0.6。
- G5：证据表行数等于 step_count、frame 列是 0 到 step_count − 1 的连续整数；用到的布尔列取值只有 0、1、True、False。
- G6（档位隔离）：一次只处理同一档的 run；Tier 2、Tier 3 的进程先调 `tier_guard.forbid_tier1()`；Tier 3 的对照只读 Tier 3 的 onset 与证据表。
- G7（帧号对齐）：新评 JSON 的 `start_frame` 是 0、`reference_tracking.reference_end_fraction` 是 1.0，参考 parquet 的帧数等于 step_count。

**定义**（与 `fall_order.py` 相同的不改）：

- 失败世界、t_obj、t_pel、t_palm、摔倒、三类（k = 25，另报 10、50）照 `fall_order.py`。
- 起点 t_on = min(t_pel, t_obj)（两者中存在的那个；都不存在的失败世界单独计数）。帧号 = 步号（G7）。
- 接触：参考两侧任一侧 `hand_contact_active` 为真的帧算“接触中”。

**只报**（两档都报）：每条 run 的失败世界数、摔倒数、三类占比；t_on、t_pel、t_obj 的分位（10/25/50/75/90）；起点最集中的 15 帧窗口及其占比；
摔倒世界里 t_pel 落在“第一次接触之前 / 接触中 / 第一次接触之后的不接触段”的占比（第 3 节第 4 步 `CONTACT_SAME` 之后才报）。Tier 1 的这些就是丙的结果，按登记只报。

**Tier 3 的对照与读法**（只对 best_hm 的 18 条；结论给另一位用户做决定，我们不据此起训练）：

- 旗标（取自证据表，逐帧）：短翻转 F_flip = orient_outlier（只抓 15 帧以内的翻转）；单帧跳变 F_jump = viol_rot_jump；看不清 F_vis = evidence 含
  off_image 或 no_mask；物体违规 F_obj = viol_object_any；转动违规 F_rot = viol_rot_torque、viol_rot_jump、viol_rot_jump_symmetric、viol_rot_drift 任一；
  根加速度 F_root = viol_root_acc；接触切换 F_sw = label_left 或 label_right 与上一帧不同。
- 窗口：起点前 15 帧到起点，[t_on − 15, t_on]。
- 每条 run、每种旗标：A = 有起点的失败世界里，窗口内至少一帧带旗标的比例；B = 从 b0 到最后一帧的每一帧当作起点时，窗口内至少一帧带旗标的比例，
  b0 = 骨盆两项与物体两项 active_after_step 的最小值 + 1；富集比 E = A / B。
- 进入汇总：有起点的失败世界 ≥ 50；起点中位 ≥ 100 帧（太早的起点和开头的旗标同在一处，比不出先后）；0.02 ≤ B ≤ 0.5（B > 0.5 时 E 到不了 2）。
  不满足的记“不可比”，数照报。
- 读法（每种旗标单独读）：进入汇总的 run ≥ 4 条；E ≥ 2 算一次命中。命中 ≥ 2/3 且机会水平 p ≤ 0.05 记“集中”，p 是各 run 以自己的 B 为命中概率时
  “至少这么多命中”的概率（泊松二项；同一条 run 的世界共用一份参考，起点挤在一个窗口时 A 只能是 0 或 1，命中的机会约等于 B）；
  E ≤ 1.25 的 ≥ 2/3 记“不集中”；其余“看不清”。
- 另报：窗口取 5、30 帧时的同样读法（不改结论）；每条 run 起点的四分位距、最集中窗口的占比（≥ 50% 标“单窗口”）与窗口里各旗标的帧数；
  ep04 已确认的头尾颠倒帧（313、509、669）之后 30 帧内的起点数与同样宽度的机会占比；ep7、ep8 的 B（失败世界不到 50 个，不进汇总）。
- 写给另一位用户的摘要里写明：F_flip 只抓短翻转，成段翻转用这张表测不了；F_flip 读“不集中”不等于“翻转不是原因”。

**停**：任何一步不满足就停在那一步，查原因，不改判据、不改配置重跑。

## 5. 风险

- 复评与原评不是同一次抽样：G3 按抽样误差给余量，另打 z；分析全用复评自身，内部一致。
- 同一集的 4096 个世界高度相关，读法按 run 计数、加机会水平，不把世界当独立样本。run 只有 18 条，读法本身力量有限，看不清是可能的结果。
- 证据表是另一位用户的中间产物，还在迭代：以 sha256 核过的快照为准；197a02f 是交接的提交号，不是生成这批表的代码版本。
- 15 帧窗口是人定的：另报 5、30 帧。成段翻转测不了，见第 4 节。
- 误差数组存 float16，阈值附近分辨率约 6e-5 m、5e-4 rad，个别越线可能挪一步，对 15 帧窗口没有影响。
- Tier 3 的失败几乎都是骨盆先越线（骨盆失败比例 0.98–1.0），t_on 基本就是 t_pel；骨盆越线不一定是摔倒，误差里没有高度分量。
- 另一位用户若开始用 GPU，我们的链按约定等，不停别人的进程；等满 2 小时就停，报告。
- 磁盘：28 条 × 约 45 MB ≈ 1.3 GB；mf4090 可用约 85 GB。

## 6. 时间（估计）

- 提交、拷证据表、同步、测试、预检：约 30 分钟。
- 链：mf4090 17 条约 70–80 分钟，ml40 11 条约 60–65 分钟。
- 分析与对照：链结束后约 30 分钟。

## 7. 要用户定的

无卡点。Tier 2 的 8 集要不要补、分析之后两台卡怎么分（Tier 3 dyn7 的小试点、Tier 1 的训练），等结果出来再定。

## 8. 审查

第 1 版：Fable 5.1，GO WITH FIXES。核过没问题的：28 条 run 的名字、机器与 MP-SR，两份清单，18 条 best_hm 证据表行数，用时估计，G3 的设定。

| # | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | MAJOR | 长链标记是空文件，`scripts/dev/remote` 判非空，挡不住同步；测试用 `-e` 判，抓不到 | 采纳：标记写日志名、来历与时间；测试改 `-s`。`export_chain.sh` 的同样隐患另记 |
| 2 | MAJOR | 证据表布尔列的编码没核过，`nan`/`None` 会被当成真 | 采纳：用到的布尔列只许 0、1、True、False，否则 G5 不过；拷贝时补记取值集 |
| 3 | MAJOR | 富集读法没有机会水平，也没防起点都在开头 | 采纳：报四分位距与最集中窗口占比；“集中”另要机会水平 p ≤ 0.05；起点中位 < 100 帧的 run 不进汇总 |
| 4 | MAJOR | F_flip 只抓 ≤15 帧的翻转，答不了成段翻转 | 采纳：改名短翻转，加 F_jump，第 1、4 节与摘要写明成段翻转测不了；另报 ep04 已确认的颠倒帧 |
| 5 | MINOR | B 在 (0.5, 0.8] 时“集中”不可达 | 采纳：B 上限改 0.5，B 照打 |
| 6 | MINOR | G4 没实现 | 采纳：JSON 与摘要写阈值；同一次调用内比、Tier 3 对照时再比 |
| 7 | MINOR | 帧号对齐写成 G5 保证，依据不对 | 采纳：第 1 节引三条事实；新增 G7 核 start_frame、reference_end_fraction 与参考帧数 |
| 8 | MINOR | 接触取法与 diag_rollout.py 不同，没核过 | 采纳：`contact_check.py` 先对 ep16 的 diag2 npz，`CONTACT_SAME` 才报接触三段 |
| 9 | MINOR | 与登记的丙有四处偏离，要写明 | 采纳：(a) 加 ep2（跟丢名单里、交上去的 run）；(b) Tier 2 的 8 集推迟；(c) 不跑 diag2，所以丙承诺的接近、抓取、跟踪三类占比这次没有；(d) 接触三段是新代码、只报。Tier 1 保持 0.01 不算偏离 |
| 10 | MINOR | “链跑时写分析脚本”隐含链中同步 | 采纳：先提交、同步、测试再起链；链跑期间不同步，补文件只用 `push-new-files` |
| 11 | MINOR | 预检漏查别的长链标记与残留容器；等卡在核副本之前 | 采纳：预检加两项；先核副本再等卡 |
| 12 | MINOR | 证据表快照要核 sha256；目录名不该用交接提交号 | 采纳：`t3_evidence_fetch.sh` 逐个比 31 个 sha256；目录名用文件时间 |
| 13 | NIT | ep7、ep8 收益最低却排在 ml40 前面 | 采纳：挪到清单最后 |
| 14 | NIT | 第 3 节分析命令是省略号 | 采纳：写成完整命令，每台分两档各调一次 |
| 15 | NIT | 误差数组是 float16 | 采纳：写进第 5 节 |

代码审查（第 2 版代码，提交 6e263ea；独立 agent，PASS WITH FIXES，15 条）：

| # | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | MAJOR | 第 5 步的通配漏掉拉回到 `results/ml40/` 的 5 条 ml40 结果，脚本也不核收了哪些集 | 采纳：`t3_onset_evidence.py` 要求 best_hm 的集恰好是登记的 18 集、不重复，否则退出码 2；第 5 步命令改成两个目录 |
| 2 | MINOR | G4 的多数在平票时取决于参数顺序 | 采纳：没有严格多数时整组记门不过（两个脚本） |
| 3 | MINOR | GPU 检查在 nvidia-smi 出错时当成卡空 | 采纳：`dump_chain.sh` 与 `fc_eval_dump.sh` 都按被占处理；预检加“nvidia-smi 能跑” |
| 4 | MINOR | 退出码 6 的重跑没有停顿、没有总时限 | 采纳：重跑前停 `V2D_POLL_S` 秒，一行累计等满 `V2D_GPU_WAIT_S` 就停 |
| 5 | MINOR | 接触只核了 Tier 1 的一集，Tier 3 的接触值没核 | 采纳：`hand_contact_active` 有 0、1 以外的值记门不过 |
| 6 | MINOR | 冻结期越线的测试放在成功世界上，测不到 | 采纳：另放一个在失败世界上，并断言它仍记 no_cross |
| 7 | MINOR | 新调用处没有测试证明档位守卫会拦 | 采纳：两个脚本各加一个读到 Tier 1 目录名时调用失败的测试；守卫的错误不再被宽的 except 吞掉 |
| 8 | MINOR | 证据表测试只测了两种旗标 | 采纳：每个用到的列单独置位，断言只有对应旗标命中 |
| 9 | NIT | 清单最后一行没有换行会丢 | 采纳：读到最后一行 |
| 10 | NIT | G4 不过的 JSON 里仍有计数 | 采纳：删去计数 |
| 11 | NIT | 两处中位数的算法不同 | 采纳：都用 np.percentile |
| 12 | NIT | 没有固定世界数，环境里残留的 `V2D_EVAL_WORLDS` 会让每行失败 | 采纳：调用时固定 4096 |
| 13 | NIT | 两处档位守卫的边角 | 采纳：按文件名先筛再读；`contact_check.py` 对非 t1 的 run 装守卫 |
| 14 | NIT | 一个坏 npz 会让整次调用失败 | 采纳：只算那一条门不过（守卫的错误除外） |
| 15 | NIT | 拷贝脚本的远端报错可能带出别人的目录名 | 采纳：远端 stderr 丢掉 |

## 9. 执行记录

- 00:13 第 2 版代码与计划提交（6e263ea）。00:2x 证据表快照：31 个文件的 sha256 与 23:55 的登记全部相同，用到的布尔列只有 0、1
  （`results/t3frame/evidence_fetch_hm.txt`；第一次在 Mac 的 bash 3.2 上因全角标点紧跟变量失败，修后重跑，a4e9c59）。
- 00:2x 两台同步到 a4e9c59；两台 `test_dump_chain.py` 都 `ALL_OK`，容器里 21 个 pytest 都过（`results/frames/tests_mf4090.txt`、`tests_ml40.txt`）；
  两台预检 `DUMP_DRYRUN_OK`（`results/frames/dryrun_frames_*_1014.txt`）。甲的队列生成后两台再同步到 6bfb784。
- 00:30 两台起 dump 链（`results/frames/arm_frames_*_1014.txt`），标记写了内容，副本核对通过；00:31 两台挂上甲的 arm_after（`agent-doc/plan-overnight-2026-10-15.md`）。
- 00:34 代码审查回来（上表）。在跑的两条 dump 链用的是 6bfb784 的 `dump_chain.sh`：第 3、4、9、12 条这次碰不到（两台 nvidia-smi 正常、清单都以换行结尾、
  tmux 全局环境里没有 `V2D_EVAL_WORLDS`），不停链；改动供以后用。分析脚本改后在 Mac 上 23 个测试全过、`test_dump_chain.py` 在 mf4090 的临时目录里 10 组全过；
  链跑着不能同步，跑分析时把这一版的 `fail_onset.py`、`fall_order.py` 复制到 `runs/tools/frames/` 再跑，记 md5。
