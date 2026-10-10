# 计划：Tier 3 试跑第二轮（校正版参考，mf4090，2026-10-10，第 2 版）

第 1 版经 Fable 5.1 独立审查（GO WITH FIXES：1 条 MAJOR、5 条 MINOR、2 条 NIT），按意见改成本版，逐条处理见文末“审查与处理”。

用户 10/10：“开始规划执行”。此前的建议是走甲：先用同组成员的两版校正只读复查悬空，过了再重跑 ep8、ep24。
这一轮只看换成校正版参考后跟不跟得上，不出提交，不读 Tier 1 的轨迹。时间一律 UTC−6。

## 1. 事实

- **第一轮结果**（`results/t3p/eval_table_t3p.txt`，计划 `agent-doc/plan-t3-pilot-2026-10-09.md`）：t3-ep8、t3-ep24（mf4090，buffer 400 万，
  变体 A，seed 42）在 4096 世界评测里 MP-SR 都是 0.000，骨盆、物体、手掌三项失败比例都是 1.000；同两集的 Tier 2 变体 A（ml40，buffer 1000 万）是 0.999。
- **配置不像是原因**（`results/t3p/jev_claims_t3_next_step.txt`）：t1-ep8-w2048-cap4m-r3a-mf4090 相对官方配方的改动与 t3-ep8 相同
  （`results/r3/g1_cfgcheck_mf4090.txt`、`results/t3p/cfgcheck_mf4090.txt`），4096 世界 MP-SR 是 0.955
  （`results/day2/eval_t1-ep8-w2048-cap4m-r3a-mf4090_s349999104.txt`）。这个对比只用来排除配置，不进入 Tier 3 的任何选择，
  也不写进本轮的评测汇总与 SOP 的表。两条 run 的代码版本不同（bbaa151、9c31ba8），没有逐项核对。
- **悬空**：第一轮重定向后，物体静置时离地 +114.9 mm（ep8）、+146.2 mm（ep24）；Tier 2 同两集是 −3.4、−2.2 mm
  （`results/t3p/retarget_mf4090.txt`、`results/batch_summary_v040_t2v54.tsv`）。悬空分析（`agent-doc/experiments/2026-10-09-t3-float-structure.md`）
  的对照没过；事后跑法（`--all-rest`，20 集）里地面上 14 集的常数模型 o = +135.5 ± 10.6 mm，残差平方和 20492 mm²，每集标准差约 40 mm；
  ep8、ep24 在这一跑法里的间隙是 +123.1、+180.0 mm（`results/t3float/posthoc_t3_ok20_mf4090.txt`）。同一跑法处理官方 Tier 2 目录，
  地面上 20 集 o = −4.5 ± 3.1 mm，|间隙| 中位 6.3 mm（`results/t3float/posthoc_control_tier2_mf4090.txt`）。
- **校正版**（`results/ops/t3_queue_ml40_1010_0735.txt`）：同组成员在 ml40 上另写了两版，`runs/tier3_cari4d_floor`（10/9 20:31–20:54 写出）
  与 `runs/tier3_cari4d_f830_floor`（10/9 21:59–22:21 写出），各 20 集，另各 9 集在对应的 `_suspect` 目录；集的划分与原版
  `tier3_cari4d`、`tier3_cari4d_suspect` 相同。校正了什么没有核实。从目录名推断（未核实）：前者校正了地面，后者另把焦距定为 830。
  同组成员的等卡脚本（参数 ep28、ep27、ep19、ep3）还挂在 ml40 上，ep3 在这 20 集里，所以校正版的文件之后可能被重写。
- **机器**（`results/ops/machines_1010_1330.txt`）：13:28 时 mf4090 的 GPU 进程 0、长链标记 0，根分区可用 4682 MB；ml40 上 t2xa 在训
  （t2-ep27 到 99%），训练约 22:00 前后结束（估计）。第一轮从起链到导出门结束用了 4 小时 54 分钟（14:59–19:53），两条 run 各约 360 MB
  （`results/t3p/health_mf4090.txt`）。
- **规则解读（未确认）**：同第一轮，Tier 3 用 Tier 2 目录里的官方网格、地面平面与支撑面。这一轮不提交；正式做 Tier 3 前要问组委会。

## 2. 做法

分两段。A 段的结论决定 B 段做不做、用哪一版。

**A 段：悬空复查（只读，不用 GPU，约 30 分钟）**

1. 两版各取通过剪影检查的 20 集（ep 0 3 5 7 8 9 12 14 15 16 17 18 20 21 22 23 24 25 26 29），用 `stages/recovery/t3_float_pack.sh`
   转到 mf4090 的 `runs/tier3/incoming/float_1010_floor/ok` 与 `runs/tier3/incoming/float_1010_f830/ok`
   （记录 `results/t3float/pack_1010_floor.txt`、`results/t3float/pack_1010_f830.txt`）。不转 `_suspect` 的 9 集，因为登记的判读只用 20 集。
2. 在 mf4090 上经 `scripts/dev/incontainer` 跑 `stages/recovery/t3_float_facts.py`：
   - 脚本回归：官方 Tier 2 目录，`--all-rest`，与 10/9 的命令相同（记录 `results/t3float/regress_control_tier2_mf4090.txt`）；
   - 两版各跑一次 `--all-rest --offset-gate 30`（记录 `results/t3float/gate_floor_ok20_mf4090.txt`、`results/t3float/gate_f830_ok20_mf4090.txt`）。
3. `python3 stages/recovery/t3_pick_version.py floor=<记录> f830=<记录>` 按第 4 节选版（记录 `results/t3float/pick_1010.txt`）。
4. 结果过 jev（带对照题）。

**B 段：重跑 ep8、ep24（mf4090 GPU，约 5 小时）**

选出的那一版记作 v2。新目录都带 `_v2` 后缀，第一轮的文件一个也不覆盖：以后要看第一轮 policy 的回放，仍要用第一轮的参考。

1. 只读核对 v2 的 ep8、ep24（`V2D_T3_SUBDIR=<v2 目录>` 跑 `tools/t3_episode_remote.sh`，记录 `results/ops/t3_episodes_ml40_1010_v2.txt`）。
   两集的 sha256 要与 A 段记录里的前 12 位相同（见第 5 节）。用 `stages/recovery/tier3_expect.py` 从这份记录与
   `results/ops/t3p_mf4090_inputs_1009.txt`（mf4090 上官方 Tier 2 网格、地面、支撑面的 md5）生成哈希表 `stages/recovery/expect/t3p2_1010.tsv`，提交并同步。
2. `V2D_T3_SUBDIR=<v2 目录> V2D_T3_SET=v2 stages/recovery/tier3_stage.sh t3p2_1010 8 24`，拼成 `runs/tier3/root_v2`（记录 `results/t3p2/stage_mf4090.txt`）。
3. 在 mf4090 的 tmux 里跑 `V2D_T3_SET=v2 stages/retarget/eps.sh 3 8 24`：转换写到 `runs/motion_src/tier3_v2`，重定向写到 `runs/motion/tier3_v2`，
   日志 `runs/logs/batch/t3_v2_ep08.*`、`t3_v2_ep24.*`（记录 `results/t3p2/retarget_mf4090.txt`）。按 P2′ 判。
4. `python3 stages/policy/make_var_queue.py t3p2` 生成队列：run 名 `t3-ep8-w2048-cap4m-r3a-v2-mf4090`、`t3-ep24-w2048-cap4m-r3a-v2-mf4090`，
   参考在 `/repo/runs/motion/tier3_v2/` 下，其余与 t3p 相同。提交并同步。
5. 配置展开（`results/t3p2/cfgcheck_mf4090.txt`）、预演（`results/t3p2/arm_dryrun_t3p2_mf4090.txt`）、起链（`results/t3p2/arm_t3p2_mf4090.txt`），
   做法同第一轮：`stages/policy/arm_var_chain.sh t3p2`。段名以 t3p 开头，走 mf4090、Tier 3 那一支（冒烟判过后删 state、可用不到 1200 MB 就停）。
6. 链结束后写健康记录 `results/t3p2/health_mf4090.txt` 与评测汇总 `results/t3p2/eval_table_t3p2.txt`（与第一轮、Tier 2 同集并列），过 jev，回报。

ml40 只经 stdin 读同组成员的文件，不同步、不起进程：t2xa 的链在跑，`scripts/dev/remote` 见到长链标记会拒绝同步，也不设 `V2D_FORCE_SYNC`。

## 3. 代码改动（66f6afa）

- `stages/recovery/tier3_pack_remote.sh`、`tools/t3_episode_remote.sh`：`V2D_T3_SUBDIR` 的白名单加上 `tier3_cari4d_floor`、`tier3_cari4d_f830_floor`
  及各自的 `_suspect`。`t3_episode_remote.sh` 原来写死 `tier3_cari4d`，改为同样按 `V2D_T3_SUBDIR` 取，并打印读的是哪个目录。
- `stages/recovery/t3_float_pack.sh`（新）：A 段的转发，先解到 `.partial`，成功才改名；打印个数、部署版本、每个 parquet 的修改时间与 sha256 前 12 位。
- `stages/recovery/t3_float_facts.py`：加 `--offset-gate <mm>`，按第 4 节打 `OFFSET_GATE_PASS`、`OFFSET_GATE_FAIL` 或 `OFFSET_GATE_NONE`，
  同一行给 o、标准误与地面上各集间隙的标准差。只有给了 `--offset-gate`，`--all-rest` 的输出才不标“事后（未登记）”；不给时与 10/9 相同。
- `stages/recovery/t3_pick_version.py`（新）：按第 4 节的选版规则读两份记录，打 `PICK <名>`、`PICK_BLOCKED <名>` 或 `PICK_NONE`。
- `libs/v2d_infra/paths.py`：环境变量 `V2D_T3_SET`（只许小写字母与数字）。设了时，Tier 3 的档目录是 `runs/tier3/root_<名>`，
  `runs/motion_src`、`runs/motion` 下的目录名是 `tier3_<名>`（`tier_dirname()`）。不设时与现在相同，Tier 1、2 不受影响。
- `stages/retarget/challenge_to_soma.py`、`stages/retarget/one.sh`、`stages/retarget/eps.sh`：目录名与日志名改用 `tier_dirname()`，日志名是 `t3_<名>_ep<EE>`。
- `stages/recovery/tier3_stage.sh`：把 `V2D_T3_SUBDIR` 传给 ml40 上的打包，把 `V2D_T3_SET` 传给 mf4090 上的 `tier3_root.py`（默认输出跟着 `paths.TIER3`）。
  两个值先在本地按字符集核对。
- `stages/policy/precheck_expect.sh`（训练链与起链都调它）：档位目录取自队列行的 parquet，必须是 `tier<档>`，或 Tier 3 的 `tier3_<名>`
  且 run 名含 `-<名>-`；序列须与期望表相同；断言就用这个目录。`day2_train_chain.sh` 只改注释。
- `stages/policy/arm_var_chain.sh`：导出要读的 `v2d_meta.json` 到 `runs/motion_src/<队列行 parquet 的目录>/<序列>/` 下核对。
- `stages/evaluate/fc_export.sh`：从 run 记录里 parquet 路径取目录名（`tier1`、`tier2`、`tier3` 或 `tier3_<名>`），到 `runs/motion_src/<同名目录>`
  下找 `v2d_meta.json`。档位仍须与 run 名一致。
- `stages/policy/make_var_queue.py`：清单加 `t3p2`（`motion` 键为 `tier3_v2`，t3p 补上 `tier3`）。段名取最长匹配的清单名，否则 `t3p2` 会落到 `t3p`。
- 测试：新增 `libs/v2d_infra/test_paths.py`、`stages/policy/test_precheck_expect.py`、`stages/recovery/test_t3_pick_version.py`；
  `test_make_var_queue.py`、`test_fc_export.py`、`test_t3_float_facts.py` 各补一种情形。Mac 上能跑的已全过；要 bash 4 或容器的
  （`test_precheck_expect.py`、`test_day2_chain_waits.py`、`test_t3_float_facts.py`、`test_challenge_to_soma.py`）同步后在 mf4090 上跑，
  记录 `results/t3p2/tests_mf4090.txt`。

## 4. 判据（执行前登记）

A 段：

- **脚本回归**：`--all-rest` 处理官方 Tier 2 目录，输出正文（记录头之后）须与 10/9 的 `results/t3float/posthoc_control_tier2_mf4090.txt`
  逐行相同（地面上 20 集，o = −4.5 ± 3.1 mm，|间隙| 中位 6.3 mm）。这一步只查代码改动有没有改变计算；作为几何计算对照的是 10/9 那份记录。
  不相同就停下，查代码或数据，A 段不判读。
- **每一版**：只用 20 集，`--all-rest --offset-gate 30`。地面上的集至少 8 集、常数模型 |o| ≤ 30 mm 记“过”，否则记“不过”；地面上不到 8 集记“不判读”。
  第一轮每集标准差约 40 mm，地面上 8–14 集时 o 的标准误约 11–14 mm，30 mm 约是 2–3 倍标准误。
- **选版**（`t3_pick_version.py`）：两版都不过，B 段不做，把数据整理好交给同组成员。只有一版过，选它。两版都过：
  | |o_a| − |o_b| | > 2·√(SE_a² + SE_b²) 时选 |o| 小的；否则看 ep8、ep24 两集间隙绝对值的较大者，选它更小的那版。
- **B 段预检**：选出的那一版里，ep8、ep24 在 A 段的间隙绝对值都 ≤ 50 mm，B 段才做（`PICK`）；否则不做（`PICK_BLOCKED`）。
  第一轮 A 段的间隙与重定向后的间隙差 8–34 mm（123.1 对 114.9，180.0 对 146.2），所以预检放宽到 50 mm，最终仍以 P2′ 为准。
- **只报**：每集间隙、倾角与尺度模型、两版 ep8 与 ep24 的间隙、parquet 的 sha256。

B 段：

- **P2′**：ep8、ep24 重定向后 |间隙| 都 ≤ 30 mm（正负都算），且至少一只手有接触。状态是 ALIGN、但间隙在 ±30 mm 内的照样训。
  有一条不过就不训，查原因并回报。第一轮只拦穿地、悬空只报；这一轮要看的正是去掉悬空之后的情形，所以悬空也拦。
- **队列**：与 t3p 的队列相比，只有首行说明、run 名、W&B 标签和参考目录（tier3 → tier3_v2）不同；配置展开的意外差异为 0；`precheck_expect.sh` 全过。
- **R1–R3**：同第一轮（冒烟非有限 0；4096 世界评测 `world_count` 4096、`non_finite_worlds` 为空、`step_count` 与导出相同；导出结果 ok）。
- **只报**：重定向的 IK 残差中位、左右手接触帧数、机器人脚底高度范围（`one.sh` 日志里的 “Saved robot sole Z range”），与第一轮并列。
  第一轮骨盆一项也是 1.000，地面校正动的是物体，不一定动人体；“仍跟不上”时，这几项用来分开物体悬空与人体轨迹两种原因。
- **读数**（只报，不出提交）：4096 世界评测对照的是训练用的 v2 参考，不是干净真值。
  - 两集 MP-SR 都 ≥ 0.5：记“校正版跟得上”。
  - 两集都 ≤ 0.05：记“校正版仍跟不上”，下一步建议用 viewer 看三项里哪项先超限。
  - 其余记“说不清”。
  - v2 与第一轮差的是整版校正（地面，可能还有焦距），读数只说这一版能不能跟，不单独归因于悬空。下一步由用户定。

## 5. 停手条件与已知限制

- 脚本回归不相同、两版都不过，或 `PICK_BLOCKED`：不做 B 段。
- A、B 两段读的不是同一份文件：B.1 记录里 ep8、ep24 的 sha256 与 A 段记录（`gate_<版>_ok20_mf4090.txt` 的 parquet 列）前 12 位不同，
  说明同组成员在两段之间重写了文件，停下，A 段重做。
- 哈希表核对不符（文件在 B.1 与 B.2 之间变了）：`tier3_root.py` 什么也不写，停下来重新核对。
- P2′ 不过：不训。
- 起链检查不过（来历不干净、可用不到 2500 MB、已有标记）：不起。
- mf4090 上出现别的用户的 GPU 进程：链按现有逻辑等卡；不停别人的进程，回报用户。
- 训练中可用空间不到 1200 MB：链按现有逻辑自己停。
- 已知限制，本轮不改：`stages/evaluate/submission_check.py` 的“训练参考在本档目录”只认 `/runs/motion/tier<档>/`，v2 的 run 过不了。
  这一轮不提交；它拦的方向是安全的。要用 v2 出 Tier 3 提交前，连同测试一起改。`tools/motion_inputs_remote.sh` 写死 `tier<档>`，本轮不用它。

## 6. 时间

A 段约 30 分钟。B 段的核对、转发与重定向约 20 分钟，链约 5 小时。15:30 前后起链的话，约 20:30 结束（估计）。

## 审查与处理

| 编号 | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | MAJOR | `precheck_expect.sh` 断言 parquet 含 `/runs/motion/tier<档>/`，v2 的 run 起链前就会被拦 | 改为取队列行 parquet 的目录，`tier3_<名>` 要求 run 名含 `-<名>-`；新增 `test_precheck_expect.py`（含 t3 的 run 指到 tier1 被拒）；改 `day2_train_chain.sh` 注释 |
| 2 | MINOR | `arm_var_chain.sh` 核对的是第一轮的 `v2d_meta.json` | 改为按队列行 parquet 的目录核对，第 3 节列出 |
| 3 | MINOR | 30 mm 门槛约 2 倍标准误，选版可能选在噪声上；ep8、ep24 各自能否过 P2′ 没有预判 | 门槛行加打标准误与每集标准差；登记选版规则（2·√(SE²+SE²) 以内看 ep8、ep24）与 B 段预检（50 mm）；`t3_pick_version.py` 机械执行 |
| 4 | MINOR | 对照是同一脚本处理同一目录，15 mm 是看过结果后定的，只算回归 | 改称“脚本回归”，判据改为与 10/9 记录逐行相同；不给 `--offset-gate` 时照旧标“事后（未登记）” |
| 5 | MINOR | `submission_check.py` 不认 `tier3_<名>` | 本轮不提交，记为已知限制；出 Tier 3 提交前连同测试一起改 |
| 6 | MINOR | A、B 两段可能读到不同版本的文件 | 第 5 节加 sha256 前 12 位核对，不同就重做 A 段 |
| 7 | NIT | `one.sh` 的日志名会截断第一轮的日志；`motion_inputs_remote.sh` 写死目录 | 日志名已改用 `t3_<名>_ep<EE>`；`motion_inputs_remote.sh` 本轮不用，记为已知限制 |
| 8 | NIT | 骨盆也是 1.000，读数分不开物体与人体 | 只报加脚底高度范围、IK 残差与接触帧数，与第一轮并列 |

审查另核了：没有 Tier 3 步骤读 Tier 1；按第 3 节实现后不写第一轮的任何目录；ml40 上只有 `tar`、`sha256sum`、`find`；磁盘与时间的估计与所引记录相符；
MP-SR 的 0.5、0.05 在看到新数据前定下。

## 执行记录

服务器日志记的是 CST，这里已换成 UTC−6。

- 13:5x 代码 66f6afa、计划第 2 版 656d54c，同步到 mf4090（mf4090 没有长链；ml40 不同步）。mf4090 上 10 组测试全过（`results/t3p2/tests_mf4090.txt`，来历 44ba8a6）。
  第一次跑时新加的测试发现 `offset_gate` 返回 numpy 的布尔值（`is True` 判不出），改成 Python 布尔后重跑。
- 14:00 A 段转发（`results/t3float/pack_1010_floor.txt`、`results/t3float/pack_1010_f830.txt`）：两版各 20 个 parquet、20 份元数据，转发时对方的部署版本 85154fe；
  parquet 修改时间与 07:35 的快照相同。
- 14:01 脚本回归：输出正文与 10/9 的记录逐行相同（`results/t3float/regress_diff_1010.txt`，`REGRESS_SAME`）。
- 14:01–14:02 两版都过门槛（`results/t3float/gate_floor_ok20_mf4090.txt`、`results/t3float/gate_f830_ok20_mf4090.txt`，地面上各 14 集）：

  | 版 | o | 每集标准差 | ep8 间隙 | ep24 间隙 | 尺度模型 s（只报） |
  |---|---|---|---|---|---|
  | 第一轮 `tier3_cari4d`（10/9 事后跑法） | +135.5 ± 10.6 mm | 约 40 mm | +123.1 mm | +180.0 mm | −0.011 ± 0.031 |
  | `tier3_cari4d_floor` | −7.4 ± 3.9 mm | 14.4 mm | −24.0 mm | +20.0 mm | +0.021 ± 0.011 |
  | `tier3_cari4d_f830_floor` | −5.1 ± 4.0 mm | 15.0 mm | −16.9 mm | +23.5 mm | +0.015 ± 0.011 |

- 14:02 选版 `PICK f830`（`results/t3float/pick_1010.txt`）：|o| 之差 2.3 mm 不超过 2·√(SE²+SE²) = 11.2 mm，改比 ep8、ep24 间隙绝对值的较大者，
  f830 是 23.5 mm，floor 是 24.0 mm，只差 0.5 mm，两版在这一条上实际打平。jev 5 条全部核实（0.76–0.97），3 道对照题正常
  （`results/t3float/jev_claims_float_recheck.txt`，规格 `agent-doc/experiments/2026-10-10-t3-float-recheck.claims.json`）。
- 14:02 B.1 只读核对（`results/ops/t3_episodes_ml40_1010_v2.txt`）：f830 版 ep8、ep24 的 sha256 与 A 段记录的前 12 位相同，帧数 708、748；
  网格与地面文件的 md5 与 `results/ops/t3p_mf4090_inputs_1009.txt` 相同。哈希表 `stages/recovery/expect/t3p2_1010.tsv`。
- 14:03 第一次拼档目录在 Mac 上停在 `tier3_stage.sh` 最后一步：macOS 自带的 bash 3.2 把 `$SUB；` 里全角分号的首字节读进变量名，`set -u` 报未定义。
  转发已完成、改名之前停下，mf4090 上的 `runs/tier3/incoming/t3p2_1010.partial` 只有转来的 5 个文件，已删。改过的脚本里变量后紧跟全角字符的都加了大括号
  （d6a8e11），重跑 `TIER3_ROOT_OK`（`results/t3p2/stage_mf4090.txt`）。`runs/tier3/root` 没动（meta 的修改时间仍是 10/9 14:49）。
- 14:04–14:08 重定向（`results/t3p2/retarget_mf4090.txt`，tmux `v2d-t3p2-retarget`）：

  | 集 | 帧数 | 左手 / 右手接触帧 | IK 残差中位 | 间隙 | 状态 | 脚底高度范围 |
  |---|---|---|---|---|---|---|
  | ep8 第一轮 | 708 | 229 / 250 | 1.235 | +114.9 mm | ALIGN | +0.006 至 +0.115 m |
  | ep8 v2 | 708 | 216 / 251 | 0.531 | **−33.9 mm** | ALIGN | +0.001 至 +0.111 m |
  | ep24 第一轮 | 748 | 0 / 481 | 0.712 | +146.2 mm | ALIGN | +0.007 至 +0.189 m |
  | ep24 v2 | 748 | 0 / 494 | 0.457 | −16.6 mm | OK | +0.000 至 +0.176 m |

  **P2′ 不过**：ep8 的 |间隙| 33.9 mm 超过 30 mm（穿地）。按第 4 节，两集都不训，查原因、回报。ep24 过。
  原因（只读日志，未另做验证）：对齐检查取物体最低的 5% 帧的中位（`stages/retarget/check_support_alignment.py:57`），A 段取第 0–4 帧。
  重定向器在第 0 帧量到网格最低点 −3.8 mm、补抬 4.3 mm（上限 10 mm），所以 ep8 开头不穿地，穿地 3.4 cm 出在序列中物体最低的那些帧。
  重定向器的地面是从人体脚步重建的（第一轮 ep8：法向偏 2.275°、偏移 1.003 m；v2：2.432°、0.873 m），v2 的人体轨迹也变了。
- 队列已按 B.4 生成（`stages/policy/queues/mf4090_t3p2*`、`stages/evaluate/exports/cand_t3_t3p2_mf4090.tsv`），与 t3p 相比只有 run 名、W&B 标签与参考目录不同
  （`results/t3p2/queue_diff.txt`）。没有做配置展开，没有起链。
- **偏离（14:16）**：P2′ 不过后回报了三个选项：只训 ep24（推荐）、两集都训（ep8 改为只报）、停。用户回复“继续，过了就直接起链”，按推荐项执行：
  只训 ep24，门槛不动，把第 4 节“有一条不过就不训”改为按集判。ep8 这一轮不训。读数照第 4 节的阈值，但只有 ep24 一集：
  MP-SR ≥ 0.5 记“校正版在 ep24 上跟得上”，≤ 0.05 记“仍跟不上”，其余“说不清”；一集的结论不外推到 ep8。
  队列另起一段 `t3p2b`（`make_var_queue.py t3p2b --episodes 24`），run 名、参考与 t3p2 的 ep24 行逐字相同；起链用 `arm_var_chain.sh t3p2b`。
  配置展开与预演都过就直接起链（用户同一句话）。
- 14:16 配置展开（`results/t3p2/cfgcheck_mf4090.txt`）：冒烟、正式各 284 个键，与官方配方不同 17、16 个，意外 0 个（与第一轮相同）。
  预演 `DRYRUN_OK`（`results/t3p2/arm_dryrun_t3p2b_mf4090.txt`）：precheck 按 `tier3_v2` 目录断言、配方断言全过，来历 e7c6a69，可用 4533 MB。
- 14:17 起链 `ARMED`（`results/t3p2/arm_t3p2b_mf4090.txt`）：会话 `v2d-t3p2b-train`、`v2d-t3p2b-eval`、`v2d-t3p2b-export`，开始冒烟 smoke-t3-ep24-w2048-cap4m-r3a-v2-mf4090。
  按第一轮每条约 2 小时 20 分钟估，16:50 前后导出门结束（估计）。
- 14:22 冒烟通过：748 帧，256 世界 rollout 里非有限世界 0 个，冒烟的 state 已删（`runs/logs/t3p2b_train_mf4090.log`）；14:22:11 开始正式训练。
  15:38 时 55%（已用 1:13:46，预计还要 1:00），GPU 上只有本链的进程，可用 4155 MB。Mac 这边一次长时间 ssh 等待在中途断开（退出码 255），链在 mf4090 的 tmux 里不受影响。
- 16:39 正式训练结束（用时 2 小时 17 分），16:45 评测链结束，16:47 导出门与导出链结束。之后 mf4090 上没有本链的 tmux 会话，GPU 占用 0 MiB，可用 4125 MB。
- R1–R3 都过（`results/t3p2/health_mf4090.txt`）：训练链 `DAY2_TRAIN_DONE`（完成 1、失败 0、跳过 0、发散 0），run 的 DONE=1、NONFINITE=0、GUARD_STOP=0，
  看守日志里含非有限的扫描行 0 条；冒烟的 256 世界 rollout 里非有限世界 0 个；评测链 `DAY2_EVAL_DONE`（成功 1、失败 0），4096 世界评测 `world_count` 4096、
  `non_finite_worlds` 为空、`step_count` 748，与导出相同；导出结果 ok。`DIVERGE_IN_CHAIN` 为 1，数到的是结束行里的“发散 0”，与第一轮相同。
- 评测汇总（`results/t3p2/eval_table_t3p2.txt`，4096 世界，第 349999104 步）：

  | run | 参考目录 | MP-SR | SP-SR | ADD-AUC | MPPE | CHORD SR | 失败：骨盆 / 物体 / 手掌 |
  |---|---|---|---|---|---|---|---|
  | t3-ep24-w2048-cap4m-r3a-v2-mf4090 | `tier3_v2` | **0.933** | 0.995 | 0.696 | 3.02 cm | 0.861 | 0.104 / 0.113 / 0.136 |
  | t3-ep24-w2048-cap4m-r3a-mf4090（第一轮） | `tier3` | 0.000 | 0.000 | 0.004 | 38.70 cm | 0.000 | 1.000 / 1.000 / 1.000 |
  | t2-ep24-w2048-cap10m-r3a-ml40 | `tier2` | 0.999 | 0.999 | 0.814 | 1.66 cm | 0.999 | 0.001 / 0.001 / 0.001 |
  | t2-ep24-w2048-cap10m-r3a-s43-ml40 | `tier2` | 0.999 | 0.999 | 0.797 | 1.65 cm | 0.995 | 0.001 / 0.002 / 0.004 |

  每一行对照的都是各自训练用的参考，不是干净真值。三档分开计分，Tier 2 两行只作同集参照；它们在 ml40 上训练，buffer 1000 万条，Tier 3 两行在 mf4090 上训练，buffer 400 万条。
- **读数**：ep24 的 MP-SR 0.933 ≥ 0.5，按第 4 节的阈值（偏离后按集判）记“校正版在 ep24 上跟得上”。只有一集，不外推到 ep8；
  v2 与第一轮差的是整版校正，不单独归因于悬空。只报的几项（第一轮 → v2）：IK 残差中位 0.712 → 0.457，右手接触 481 → 494 帧（左手两轮都是 0），
  间隙 +146.2 → −16.6 mm，机器人脚底高度范围 +0.0073 至 +0.1892 m → +0.0004 至 +0.1760 m。
- jev 6 条全部核实（0.96–0.99），4 道对照题正常（`results/t3p2/jev_claims_t3p2_result.txt`，规格 `agent-doc/experiments/2026-10-10-t3p2-result.claims.json`）。
- 这一轮不出提交。v2 的 run 过不了 `submission_check.py` 的档位目录检查（第 5 节已知限制），用 v2 出 Tier 3 提交前要先改它和测试。下一步由用户定。
