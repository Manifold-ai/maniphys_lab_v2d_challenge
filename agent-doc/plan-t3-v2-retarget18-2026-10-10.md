# 计划：Tier 3 校正版其余 18 集的重定向（mf4090，2026-10-10，第 2 版）

用户 10/10：“先把 v2 里另外 18 集重定向一遍，就是通过剪影检查的 20 集减去这两集。”
这一步只数过 P2′ 的集，不训练、不出提交，不读 Tier 1 的轨迹。时间一律 UTC−6。
第 1 版经 Fable 5.1 独立审查（GO WITH FIXES：1 条 MAJOR、5 条 MINOR、2 条 NIT），按意见改成本版，逐条处理见文末“审查与处理”。

## 1. 事实

- **第二轮**（`agent-doc/plan-t3-pilot-v2-2026-10-10.md`）：选的是 f830 版（同组成员 ml40 上的 `runs/tier3_cari4d_f830_floor`）。
  ep24 过 P2′，训练后 4096 世界评测 MP-SR 0.933（对照的是 v2 参考，`results/t3p2/eval_table_t3p2.txt`）；ep8 重定向后穿地 33.9 mm，没过 P2′，没训。
- **其余 18 集**：这一版通过剪影检查的 20 集减去 ep8、ep24，即 ep 0 3 5 7 9 12 14 15 16 17 18 20 21 22 23 25 26 29。
  A 段（第 0–4 帧）的间隙在 −33.7 至 +7.3 mm 之间（`results/t3float/gate_f830_ok20_mf4090.txt`），ep7（−33.2 mm）与 ep14（−33.7 mm）在 A 段就超过 30 mm。
  12 集静置在地面上，6 集在支撑面上（ep3、7、9、16、20、25，面高 0.47–0.88 m）。
- **ep29 不用手**：元数据里的任务是“using your left foot push the rolling luggage”；Tier 2 同集重定向左右手接触都是 0，状态 `OK+NOCONTACT`
  （`results/batch_summary_v040_t2v54.tsv`）。另外 17 集在 Tier 2 里都有手部接触。Tier 2 的 ep29（`t2-ep29-w2048-cap10m-ml40`）4096 世界 MP-SR 0.140
  （`results/ml40/day2/eval_t2-ep29-w2048-cap10m-ml40_s349999104.txt`），只作以后决定训不训时的参考。
- **A 段间隙预测不了重定向后的间隙**：对齐检查取物体网格最低点最低的 5% 帧的中位（`stages/retarget/check_support_alignment.py:57`），
  重定向器还从人体脚步重建地面，并在第 0 帧补抬。第二轮 ep8 从 −16.9 mm 变成 −33.9 mm，ep24 从 +23.5 mm 变成 −16.6 mm
  （`stages/retarget/p2_table.py` 对 `results/t3p2/retarget_mf4090.txt` 的输出）。所以 18 集都要重定向，按 P2′ 逐集数。
- **对齐检查的支撑面**：用 `UsdGeom.BBoxCache` 取支撑面几何体的世界包围盒，带缩放的方盒按缩放后的尺寸算。
  物体中心的水平投影不在任何支撑面的范围内时，候选只剩地面，放在桌上的物体会判成悬空。任务把物体放到地上时（如 ep9、ep16），最低的帧本来就在地面上。
- **拼档目录**：`stages/recovery/tier3_root.py` 往已有的 `runs/tier3/root_v2` 里加集时，已有集的元数据与 parquet 相同就跳过，不同就拒绝；
  哈希表里每一行都要用上，所以哈希表只能含这次拼的集。10/9 那份官方 Tier 2 输入的 md5 记录（`results/ops/t3p_mf4090_inputs_1009.txt`）
  只有 ep8、ep24，而且是临时命令打的。第一轮的 `runs/tier3/root` 里也正好是 ep8、ep24，漏设 `V2D_T3_SET=v2` 时同样会拼成 20 行。
- **机器**（17:05 前后）：mf4090 没有长链标记，GPU 占用 0 MiB，负载 0，根分区可用 4119 MB，部署版本 e7c6a69。第二轮两集在 `runs/tier3/root_v2`、
  `runs/motion_src/tier3_v2`、`runs/motion/tier3_v2` 共占 14、46、40 MB，约每集 50 MB。ml40 上 t2xa 在训，不同步。
  第二轮重定向 ep8 用了 80 秒、ep24 用了 151 秒（`results/t3p2/retarget_mf4090.txt`）。
- **文件可能被重写**：10/10 07:35 同组成员的等卡脚本（参数含 ep3）还挂在 ml40 上（`results/ops/t3_queue_ml40_1010_0735.txt`）。
  审查期间（17:31）的只读核对显示 18 集的 sha256 都与 A 段相同（提交后重跑，见执行记录）。

## 2. 做法

1. 代码（第 3 节）提交后同步到 mf4090，在那边跑测试（`results/t3p2/tests18_mf4090.txt`）。
2. B.1 只读核对：`V2D_T3_SUBDIR=tier3_cari4d_f830_floor` 经 stdin 在 ml40 上跑 `tools/t3_episode_remote.sh`，18 集
   （`results/ops/t3_episodes_ml40_1010_v2_18.txt`；审查期间跑过一次，提交后重跑，让记录指向干净的提交）。
3. mf4090 上跑 `stages/recovery/tier2_inputs_md5.py`，取这些集的官方 Tier 2 网格、地面平面、支撑面的 md5（`results/ops/t2_inputs_mf4090_1010_18.txt`）。
4. `stages/recovery/t3_sha_match.py <B.1 记录> <A 段记录> --inputs <第 3 步的记录>` 比对 B.1 与 A 段（`results/t3p2/sha_match_18.txt`）。
5. `stages/recovery/tier3_expect.py` 从第 2、3 步的记录生成 `stages/recovery/expect/t3p2_18_1010.tsv`，提交并同步到 mf4090。
6. `V2D_T3_SUBDIR=tier3_cari4d_f830_floor V2D_T3_SET=v2 stages/recovery/tier3_stage.sh t3p2_18_1010 <集>`，拼进 `runs/tier3/root_v2`
   （`results/t3p2/stage18_mf4090.txt`）。随后只读核对两个档目录（`results/t3p2/stage18_check_mf4090.txt`）：`root_v2` 与 `root` 的
   `meta/episodes_metadata.jsonl` 的修改时间与行数。
7. mf4090 的 tmux `v2d-t3p2-retarget18` 里跑
   `V2D_T3_SET=v2 V2D_RECORD_TRACEBACK_OK=1 scripts/dev/record t3p2/retarget18_mf4090 stages/retarget/eps.sh 3 <集>`。
   转换写到 `runs/motion_src/tier3_v2/<序列>`，重定向写到 `runs/motion/tier3_v2`，日志是 `runs/logs/batch/t3_v2_ep<EE>.*`；ep8、ep24 的目录与日志不动。
   `FAIL:*` 的结果行与日志尾里的 Traceback 是数据，不让整份记录变成 `.failed`。
8. 拉回结果，跑 `stages/retarget/p2_table.py results/t3p2/retarget18_mf4090.txt --no-contact 29 --a-phase results/t3float/gate_f830_ok20_mf4090.txt`
   （`results/t3p2/p2_18.txt`），过 jev（带对照题），更新执行记录，提交，回报。

## 3. 代码改动

- `stages/recovery/tier2_inputs_md5.py`（新）：按 Tier 2 的 `meta/episodes_metadata.jsonl` 列出给定几集的网格、地面平面、支撑面的 md5，
  格式与 10/9 那份记录的 md5 行相同，取代当时的临时命令。开头调 `tier_guard.forbid_tier1()`。
- `stages/recovery/t3_sha_match.py`（新）：把第二轮手工做的 sha256 前 12 位核对写成脚本。对第二轮的两份记录跑出 `SHA_MATCH 2/2`，与当时的手工核对相同。
  审查之后另加 `--inputs`（只报，不影响退出码）：B.1 里同组成员重建用的网格、地面与官方 Tier 2 同名文件的 md5 是否相同，第二轮对 ep8、ep24 是手工比的；
  对第二轮的记录跑出 `INPUTS_SAME 4/4`。
- `stages/retarget/p2_table.py`（新）：按 P2′ 逐集判一份 `eps.sh` 记录。集的清单取自记录头，没有结果行的集记“失败”；
  `--no-contact` 登记接触一条不适用的集；`--a-phase` 加 A 段面高、间隙与差，A 段在支撑面上而重定向后最近的是地面的集在原因里注明。
  对第二轮的记录跑出 ep8 不过、ep24 过，与 10/10 的人工判读相同。
- `stages/retarget/eps.sh`：每集日志段先单独打出 “Saved robot sole Z range” 那一行，再打最后 15 行（段标题改为“脚底高度与最后 15 行”）。
  只改打印，不改执行。
- 三个新脚本各带测试（`test_tier2_inputs_md5.py`、`test_t3_sha_match.py`、`test_p2_table.py`）。

## 4. 判据（执行前登记）

- **SHA**：B.1 里每集 parquet 的 sha256 都以 A 段记录里同一集的前 12 位开头。不同的集不拼、不重定向，回报这些集；
  去掉它们重跑 B.1 再生成哈希表，其余照做。
- **拼目录**：拼目录的记录里有 `V2D_T3_SET=v2` 与 `TIER3_ROOT_OK`；核对记录里 `runs/tier3/root_v2/meta/episodes_metadata.jsonl` 有 20 行、
  修改时间在拼目录之后，`runs/tier3/root/meta/episodes_metadata.jsonl` 仍是 2 行、修改时间仍是 10/9。ep8、ep24 的行与 parquet 不变
  （`tier3_root.py` 相同就跳过）。不满足就停。
- **重定向的目录**：`retarget18_mf4090.txt` 的第一行正文是 `目录 runs/motion_src/tier3_v2、runs/motion/tier3_v2`。不是就停，结果不判读。
- **P2′**（同第二轮第 4 节，10/10 偏离后按集判）：重定向后 |间隙| ≤ 30 mm（正负都算，状态是 ALIGN 也照算）且至少一只手有接触，记“过”；
  否则记“不过”；结果行是 `FAIL:*` 或没有结果行，记“失败”，这一步不重试。阈值不因结果调整。
- **ep29**：任务用脚推、不用手（第 1 节），接触一条不适用，只按间隙判，结论单独打一行（`CONTACT_NA`）。这一条在看到 18 集的重定向结果之前登记。
- **只报**：重建用的网格、地面与官方 Tier 2 是否相同（`INPUTS_SAME` / `INPUTS_DIFF`）；过 P2′ 的集数与集号；每集的帧数、左右手接触帧数、IK 残差中位、间隙、支撑面、状态、机器人脚底高度范围、A 段面高与间隙、两者之差；
  A 段在支撑面上而重定向后最近的是地面的集（`SURFACE_TO_FLOOR`），这类集要么是任务把物体放到了地上，要么是物体不在支撑面的范围内（后者是几百 mm 的悬空），
  不改 P2′ 的结论。
- 这一步不训练。过 P2′ 的集要不要训、训哪些，由用户定。

## 5. 停手条件与已知限制

- 哈希表核对不符（文件在 B.1 与拼目录之间变了）：`tier3_root.py` 什么也不写，停下重新核对。`tier3_stage.sh` 在跑 `tier3_root.py` 之前已把
  `incoming/<标签>.partial` 改名为 `incoming/<标签>`，重试要换新标签与新哈希表，或先删掉那个目录（只有这次转来的文件）。
- 拼目录或重定向的目录不对（第 4 节）：停，不判读。
- 重定向前 mf4090 可用不到 2500 MB：不起（预计用约 0.9–1.0 GB，估计）。
- mf4090 上出现别的用户的进程：不停别人的进程，回报用户。
- ml40 上只经 stdin 跑两个只读脚本（`tools/t3_episode_remote.sh`、`stages/recovery/tier3_pack_remote.sh`），不同步、不起长进程。
- 已知限制：P2′ 只说明重定向后物体静置时贴着支撑面、手有接触，不预言训练能不能跟上，有训练证据的只有 ep24 一集。
  Tier 3 用 Tier 2 目录里的官方网格、地面平面与支撑面，规则解读未确认。`submission_check.py` 不认 `tier3_v2`（第二轮第 5 节）。

## 6. 时间

测试与审查约 30 分钟；B.1 到拼目录约 15 分钟；重定向按每集 80–151 秒算约 25–45 分钟；汇总、jev 与记录约 15 分钟。19:00 前后结束（估计）。

## 审查与处理

| 编号 | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | MAJOR | ep29 的任务是用左脚推，Tier 2 同集两手接触都是 0；按“至少一只手有接触”会被机械判掉，且“阈值不因结果调整”使事后无法纠正 | 看到结果之前登记：ep29 接触一条不适用、只按间隙判、单独一行；`p2_table.py` 加 `--no-contact` 与测试。核对过 Tier 2 那批，其余 17 集都有手部接触 |
| 2 | MINOR | 第一轮 `root` 也是 ep8、ep24，“20 行”分不出拼进了哪个目录 | 判据加：记录里有 `V2D_T3_SET=v2`，拼完只读核对两个档目录的行数与修改时间；重定向记录的目录行必须是 `tier3_v2` |
| 3 | MINOR | 支撑面范围外的物体判成地面上的悬空，没有标注 | `p2_table.py` 加 A 段面高列，A 段在支撑面上而重定向后最近的是地面的集在原因里注明并另打 `SURFACE_TO_FLOOR`；只报，不改结论（任务把物体放到地上时也会这样） |
| 4 | MINOR | 日志尾里出现 Traceback 会让整份 18 集的记录变成 `.failed` | 第 7 步设 `V2D_RECORD_TRACEBACK_OK=1`，`FAIL:*` 行是数据 |
| 5 | MINOR | `p2_table.py` 发现不了没有结果行的集，分母会悄悄变小 | 集的清单改从记录头取，没有结果行的集记“失败”；有记录头没要求的集就报错 |
| 6 | MINOR | 支撑面几何体多时，脚底高度那一行会被挤出最后 15 行 | `eps.sh` 每集先单独打出那一行，再打最后 15 行 |
| 7 | NIT | B.1 与 sha 核对在审查与提交之前跑过，记录的来历带 dirty | 提交后重跑这两步（现在的第 2、4 步） |
| 8 | NIT | `tier3_root.py` 拒绝之后，同一标签不能重试 | 第 5 节写明：换新标签与新哈希表，或先删掉那个 incoming 目录 |

审查另核了：没有一步读 Tier 1；所有写入都按序列分目录，日志名不会是 ep08、ep24；设了 `V2D_T3_SET=v2` 时第一轮的目录不动；
在临时目录里实测往已有 ep8 的档目录加集，`TIER3_ROOT_OK`，ep8 的行、parquet 与来源都保留，哈希表里带旧集的行会被拒绝且什么也不写；
三个新脚本的解析与真记录一致，`tier2_inputs_md5.py` 的输出能被 `tier3_expect.py` 取到；ml40 上只有只读命令；18 集平均 745 帧，与第二轮的 728 帧相近，
时间与磁盘的估计与所引记录相符。

## 执行记录

服务器日志记的是 CST，这里已换成 UTC−6。

- 17:31 审查期间先跑了一次 B.1 与 sha 核对（只读，18/18 相同）；按审查第 7 条，提交后重跑的记录覆盖了这两份。
- 17:45 代码 c13b610 同步到 mf4090，测试全过（`results/t3p2/tests18_mf4090.txt`；`t3_sha_match.py` 加 `--inputs` 之后在 Mac 上另跑，
  `results/t3p2/tests18_sha_match_mac.txt`）。
- 17:45 B.1 重跑（`results/ops/t3_episodes_ml40_1010_v2_18.txt`）：18 集的 parquet 与元数据都可读。官方 Tier 2 输入（`results/ops/t2_inputs_mf4090_1010_18.txt`）：
  18 集 53 个文件（ep0、ep21 共用 tall_bar_stool 的网格）。哈希表 `stages/recovery/expect/t3p2_18_1010.tsv` 89 行（5966a00）。
- 17:47 sha 核对（`results/t3p2/sha_match_18.txt`，5966a00）：`SHA_MATCH 18/18`；重建用的网格与地面与官方 Tier 2 相同，`INPUTS_SAME 36/36`。
- 17:48 拼目录（`results/t3p2/stage18_mf4090.txt`）：`V2D_T3_SET=v2`，`TIER3_ROOT_OK`，写入 18 个 parquet 与网格、地面、支撑面文件；
  转发时对方的部署版本是 ae06e75（第二轮是 85154fe），文件以 sha256 为准，与 A 段相同。核对（`results/t3p2/stage18_check_mf4090.txt`）：
  `root_v2` 的 `meta/episodes_metadata.jsonl` 20 行、修改时间 10/10 17:48；第一轮 `root` 仍是 2 行、修改时间仍是 10/9 14:49；
  `root_v2` 里 ep8、ep24 的 parquet 的 sha256 与 `t3p2_1010.tsv` 相同。拼目录的判据全过。
- **磁盘估计偏低**：`root_v2` 从 14 MB 涨到 252 MB，主要是网格（18 集的网格每集 8–25 MB，第二轮两集是 3 MB 与 9 MB）。
  第二轮两集的重定向产物（`motion_src` 加 `motion`）是网格的 6.8–8.7 倍，按此估这一步约用 1.7–2.1 GB，计划第 5 节写的 0.9–1.0 GB 偏低一倍。
  起之前可用 3859 MB，满足登记的“≥ 2500 MB”，照计划起；跑完预计剩 1.8–2.2 GB，低于起训练链要求的 2500 MB（估计）。
- 17:49 起重定向：tmux `v2d-t3p2-retarget18`，GPU 进程 0，负载 0。
- 18:35 重定向结束（`results/t3p2/retarget18_mf4090.txt`，以 `EPS_DONE` 结束，18 集都有退出码行）。目录行是 `runs/motion_src/tier3_v2、runs/motion/tier3_v2`，
  判据过。Mac 18:27 前后断网到 20:30 之后，等待脚本退出，重定向在 mf4090 的 tmux 里不受影响。结束后可用 2658 MB，这一步实际用了约 1.2 GB。
- P2′（`results/t3p2/p2_18.txt`）：**18 集过 10 集**（ep0、15、17、18、20、21、22、23、26、29），不过 8 集，重定向失败 0 集。ep29 按登记只看间隙（−28.2 mm）。

  | 集 | 间隙 | 支撑面 | 左 / 右手接触 | IK 残差中位 | A 段间隙 | P2′ |
  |---|---|---|---|---|---|---|
  | ep0 | −23.4 mm | 地面 | 280 / 455 | 0.648 | −9.3 mm | 过 |
  | ep3 | +90.0 mm | 地面（A 段在 0.777 m 的支撑面上） | 0 / 244 | 0.455 | +0.4 mm | 不过（悬空） |
  | ep5 | −34.9 mm | 地面 | 488 / 614 | 0.956 | +4.2 mm | 不过（穿地） |
  | ep7 | +710.9 mm | 地面（A 段在 0.782 m 的支撑面上） | 0 / 562 | 0.702 | −33.2 mm | 不过（悬空） |
  | ep9 | −31.6 mm | 支撑面 | 382 / 417 | 0.760 | +2.3 mm | 不过（穿地） |
  | ep12 | −63.5 mm | 地面 | 320 / 423 | 0.612 | −5.4 mm | 不过（穿地） |
  | ep14 | −79.3 mm | 地面 | 471 / 646 | 0.596 | −33.7 mm | 不过（穿地） |
  | ep15 | +1.4 mm | 地面 | 0 / 420 | 0.864 | +6.5 mm | 过 |
  | ep16 | +238.3 mm | 地面（A 段在 0.878 m 的支撑面上） | 183 / 0 | 0.551 | −19.1 mm | 不过（悬空） |
  | ep17 | −0.5 mm | 地面 | 145 / 175 | 0.909 | +7.3 mm | 过 |
  | ep18 | −9.3 mm | 地面 | 298 / 422 | 0.881 | +2.1 mm | 过 |
  | ep20 | −21.8 mm | 支撑面 | 0 / 325 | 0.895 | −5.8 mm | 过 |
  | ep21 | −26.1 mm | 地面 | 449 / 462 | 0.858 | −0.7 mm | 过 |
  | ep22 | −21.3 mm | 地面 | 0 / 390 | 0.526 | +3.7 mm | 过 |
  | ep23 | −23.0 mm | 地面 | 324 / 293 | 0.908 | −16.9 mm | 过 |
  | ep25 | +728.6 mm | 地面（A 段在 0.783 m 的支撑面上） | 59 / 137 | 1.089 | +0.8 mm | 不过（悬空） |
  | ep26 | −28.1 mm | 地面 | 259 / 237 | 0.766 | −9.1 mm | 过 |
  | ep29 | −28.2 mm | 地面 | 0 / 0 | 0.544 | −26.2 mm | 过（接触不适用） |

- 只报：A 段在支撑面上的 6 集里，ep3、7、16、25 重定向后最近的面是地面，都判成悬空；ep7、ep25 是 700 mm 以上，是物体不在支撑面范围内的那种。
  A 段面高为 0 的 12 集，重定向后的间隙都比 A 段低（差 −2.0 至 −58.1 mm），第二轮的 ep8、ep24 也是（−17.0、−40.1 mm）；穿地的 4 集都在这一组里。
  原因没有查，只记现象。
- jev 7 条全部核实（0.81–0.98），4 道对照题正常（`results/t3p2/jev_claims_retarget18.txt`，规格 `agent-doc/experiments/2026-10-10-t3v2-retarget18.claims.json`）。
- 加上第二轮的 ep24，这一版 20 集里过 P2′ 的是 11 集。训不训、训哪些由用户定；起链要求可用 ≥ 2500 MB，mf4090 现在是 2658 MB，训练每条约 360 MB（第二轮），要先腾空间。
