# 计划：Tier 1 跟丢集的接触标记提前（c10），ml40 今夜试 4 集（2026-10-16 14:3x MDT，第 2 版：按独立复核修改）

## 事实（核过的）

- r3o 两档都判“没用”（`results/r3o/verdict_P1_mf4090.txt`、`results/ml40/r3o/verdict_P2_ml40.txt`），按 r3o 计划停，另写计划。
- 跟丢集是接触后很快丢：按 MP-SR 门槛（0.03 m、0.52 rad），物体越线的中位步与首次接触帧之差 ep11 +9、ep28 +18、ep25 +19、ep1 +25、ep9 +25、ep2 +32；
  ep4 是 −58，参考里球棒在接触前就自己转（`results/r3o/onset_terms_t1_thr_{mf4090,ml40}.txt`，逐帧回放下步号就是帧号；
  首次接触帧取 `results/t1diag/contact_window_mf4090.txt`）。
- 首次接触后 30 帧里，物体在世界里自转的中位：跟丢 7 集 16.4°，其余 22 集 1.0°；掌心自转 9.4° 对 11.6°（同一份记录）。
  跟得好的集，刚接触那一段物体基本不动；跟丢的集，一接触物体就要动。30 帧在逐帧回放下只有 0.6 秒。
- FlashCHORD 的 ReconBody 目标函数有 force_closure（权重 5.0），只在参考标记为接触的帧计分（`contact_active[frame * num_hands + hand] > 0.5`），
  奖励是手对物体的摩擦锥覆盖率（`v040_p185_nfg/src/flash_chord/objectives/recon_body.py` 第 158–186 行）；标记来自参考 parquet 的 `hand_contact_active`
  （`data/motion_v1.py` 第 248 行，必须是 0/1）。评测只看物体，不看这个标记。

## 假设与改法

- 假设：抓握奖励只从参考的接触帧才开始，物体又在接触后 0.2–0.6 秒就要动，策略来不及建立抓握。
- 改法（只改训练用的接触标记，参考轨迹一字不动）：每只手的接触标记，每段的起点往前提 10 帧（不早于第 0 帧），
  并把两段之间不超过 15 帧的空档补成接触。新参考放 `runs/motion/tier1_c10/`（只换 parquet 的这一列；物体网格、支撑面、元数据照抄）。
- 配方：变体 A（与现在这几集的候选同一族），只换参考目录；run 名 `t1-ep<N>-w2048-cap10m-r3a-c10-ml40`。

## 范围

- ml40 今夜 4 集：ep25、ep28、ep11、ep1（按现在 Tier 1 提交的 MPPE 贡献 118、66、59、38 cm 排）。ep4 失败机理不同，不做；ep9、ep2 放后面。
- 不做对照集（省 GPU）：改法只用在跟丢集上，“有用”要求至少修好一集。

## 判据（训练前登记）

- 每集同 r3o 的判法（`stages/policy/r3o_gate.py` 的 judge）：4096 世界 MP-SR ≥ 0.3 记“修好”；MP-SR ≥ 0.1，或基线 SP-SR < 0.3 而新 SP-SR ≥ 0.3，
  或失败_物体比基线低 0.2 以上，记“有起色”；其余“没用”。基线取 r3o P1 登记的那几条（`stages/policy/r3o_verdict.json` 的 P1）。
- 总判：修好 ≥ 1 集记“有用”（之后给修好的集补 seed 43，并把同样的改法用到 Tier 2 的跟丢集）；修好 0 集但有起色 ≥ 2 集记“看不清”；其余“没用”。
- 只报：新 run 的 4096 世界 MPPE 与现在提交那条的 4096 世界 MPPE 并列（换不换候选另走逐条选）。

## 执行

1. 工具（各带测试）：`stages/retarget/contact_relabel.py`（改一列、其余列逐值相同、只许 0/1）；`make_var_queue.py` 让 Tier 1 段也能换参考目录，新段 t1c；
   `arm_var_chain.sh` 认 t1c*（同 t1y*：ml40、Tier 1）；判读用 `r3o_verdict.py` 加一节 C1（无对照，总判按上面）。
2. ml40 同步（没有链在跑时），容器里生成 tier1_c10（4 集），配置核对、预演、起链；评测链结束后 `run_after_log.sh` 自动跑判读，命令（仓库根）：
   `V2D_MAX_POLLS=1440 setsid nohup stages/policy/run_after_log.sh runs/logs/t1c_eval_ml40.log "DAY2_EVAL_(DONE|FAILED)" t1diag/verdict_C1_ml40 python3 stages/policy/r3o_verdict.py C1 > runs/logs/after_verdict_C1_ml40.log 2>&1 < /dev/null &`。
   人工兜底：有一条评测失败时 `r3o_verdict.py C1` 退出码 2（缺评测文件），导出链也不导（要求失败 0）；那就按日志补评那一条再判，或只判评完的几条并写明。
3. 约 4 × 2 小时加评测导出，明早 02:00 前后出判读。

## 风险

- 提前的 10 帧里，参考的手还离物体几厘米，抓握奖励与掌心跟踪会有一点冲突；10 帧按接触前掌心速度约 2–3 cm，量级不大。
- 单种子；4 集都是 0 起步，修好一集也可能是种子运气（“有用”之后先补 seed 43）。

## 执行记录

- 14:5x 生成 tier1_c10（ml40，容器里，`results/t1diag/c10_relabel_ml40.txt`）：4 集只换 hand_contact_active，首段起点都提前 10 帧，
  段数 ep25 右手 8 → 4、ep28 12/11 → 6/4、ep11 左手 5 → 1、ep1 左手 12 → 2（原来的接触标记碎成很多段，补空档后抓握奖励不再断断续续）。
  方向核对：每只手的首段起点与 `results/t1diag/contact_window_mf4090.txt` 的首次接触帧逐一相同（如 ep25 左 218、右 100），表是手 × 帧，没有读反。
- 配置核对 8 份意外差异都是 0（`results/t1diag/cfgcheck_t1c_ml40.txt`）。预演先停在 precheck_expect.sh：“带后缀的参考目录只许 Tier 3”。
  放开到 Tier 1、2，保留“目录档位数字等于 run 名档位”和“run 名含 -<后缀>-”两条（precheck_expect.sh、fc_export.sh 与各自测试，cf38fcd），预演 DRYRUN_OK。
- 独立复核（Fable，15:3x）：GO WITH FIXES，4 MINOR、3 NIT，没有 MAJOR。处理：
  - 诊断记录拉回仓库（MINOR 1）；`contact_relabel.py` 按 hand_sides 与帧数断言形状、打印抄过去的支撑面（MINOR 2、3）；
  - 4 集的支撑面在 tier1 都有、已原样抄到 tier1_c10（cmp 相同），队列里没有关支撑面的覆盖；`check_inputs.py` 对 4 份新参考退出码 0
    （`results/t1diag/check_inputs_c10_ml40.txt`，MINOR 3）；
  - “评测只看物体”改为实测（MINOR 4）：`eval_parquet_pair.sh` 用现有 ep25 策略、同一评测器对 tier1 与 tier1_c10 各评 4096 世界，
    在 k-fix 的容差内一致才起链（`results/t1diag/eval_pair_c10_ep25_ml40.txt`）；
  - NIT 5（判法里骨盆先倒的情形）只报不改判法；NIT 6 段数变化记在上面；NIT 7 起链前核了 ml40 的来历与链标记，C1 的命令与兜底写进第 2 步。
