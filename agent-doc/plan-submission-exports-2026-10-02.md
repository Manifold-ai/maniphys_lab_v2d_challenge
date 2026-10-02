# 计划：提交流程与两档各 30 条导出（只导出、打包、预检，不上传）

第 1 版，10/2 00:40（UTC-6），分支 `track2/p1-training`，基于 23daeae。时间一律 UTC-6；服务器日志是北京时间（UTC+8）。

用户 10/1 23:50 的决定（原文）：

- “暂时先别提交任何内容”。
- 队伍名 “maniphys.ai”。
- 工作顺序：“1. 先把提交流程和 30 条导出做完；2. 再挑 2–3 条 MP-SR 为 0 的序列做诊断，弄清楚失败出在接近、抓取还是跟踪；3. 最后用一个改动后的配方在约 5 条序列上试，过了判据再铺开。”

本计划只管第 1 步。“提交流程做完”在这里指：两档各有一份由官方打包器生成、能通过官方上传器本地校验的 CSV，从导出到打包的每一步都有落盘记录；不往 Kaggle 上传。

## 1. 事实

1. **官方打包器**（kit `update_0f2f9f4b`，zip sha256 0f2f9f4b…，`tools/pack_submission.py`）：
   - 缺一条计分 episode 就整份拒绝（271 行）；每条 episode 只交 1 个世界（`config/tracks.json` 的 `worlds_per_episode: 1`）；
   - 拒收 `environment_valid=false` 的世界（311 行）；各条 episode 的 `eval_script_sha256`、`eval_code_sha256` 必须相同（422 行，“One submission is one evaluator build”）；
   - `--code-commit` 必须是 GitHub 的 `/commit/<sha>` 链接（454 行）；
   - 干净参考找 `<数据根>/track_2/baseline` 或 `<数据根>/track_2/tier_1_multiview_caption`，哪个有 `meta/` 用哪个（`v2dlb/dataset.py:20–26`）；
   - Track 2 的坐标换算（82–130 行）：用第一个计分帧求一个刚体变换，把评测器记下的参考对到“这一档的输入参考”上，逐帧残差超过 1 mm 或 1e-3 rad 就报错。
     输入参考默认是这一档发布的数据，给了 `--frame-references` 就用它（`dataset.py:29–42`，`pack_submission.py:132–160` 读 npz）；
   - 本地分数：三档都按干净参考算，最后打印一行 `locally computed: …`（506 行）。Tier 2、Tier 3 的交叉核对只打印一句说明、不打印数（566 行）；
     网格目录存在时才算 AUC（531 行）。
2. **官方上传器**（`submit/v2d_submit.py`）：`--dry-run` 也要 `-m`（448 行）；它在本地按官方样例核 CSV 的行，调 `preflight`（249 行起，
   只读：列已有提交、查配额、核各比赛的用户与队伍名是否一致），然后在 517 行返回，上传与回执都在这之后（526 行起）。
3. **Kaggle 状态**（10/1 23:52，`results/submission/kaggle_join_status_1001_2125.txt`）：Tier 1 四个比赛已加入；Tier 2 加入了 mp-sr、mppe、sp-sr，
   tier2-auc 显示规则未接受；Tier 3 没加入。队伍名还要用户在每个比赛的 Team 页改成 maniphys.ai。
4. **checkpoint**：每条 run 约每 1000 万步存一份 policy，共 35 份（mf4090 上 `t1-ep3-w2048-cap4m-mf4090` 实列：`policy_10000384` … `policy_349999104`）。
5. **数据**：mf4090 上 Tier 1 干净参考 `meta` 2.0 MB、`data` 30 MB、`mesh` 345 MB（29 个物体，每个一个 glb，打包器只读 glb）；视频 655 MB 用不到。
   v5.4 在 `runs/recovery/tier2_v54/episode_XXXXXX.npz`：`object_pose` [T,7]（x,y,z,qw,qx,qy,qz，OpenCV 世界系）、`visible`、`meta`；
   发布的 Tier 2 parquet 的 `frame_index` 是 0..T−1（ep16 实查：477 帧，0…476）。
6. **Mac 环境**：uv 0.12.16。kit 的 `requirements.txt` 只写下限，uv 默认解析出 pandas 3.0.6；限 `pandas<3` 后是 2.3.3，numpy 2.5.3、pyarrow 25.0.1、trimesh 5.1.0，
   Python 3.12.14，`pack_submission` 能导入。
7. **ep20**：Tier 1 有两条逐帧回放的 policy：ml40 的先导 run `t1_ep20_w2048_cap10m_ml40` 和 mf4090 的批量 run `t1-ep20-w2048-cap4m-mf4090`。
   `results/day2/batch_verdict_*.txt` 里逐帧判定的只有批量那条（另两条带 `-rt-` 的是实时回放）。SOP 记为“还要定用哪条”。
8. **已有的导出**：兼容性验证（`agent-doc/plan-box6-and-eval-runtime-2026-10-01.md`）会先导出 mf4090 的 t1-ep6、t1-ep8、t2-ep2 与 ml40 的 t1-ep12、t2-ep0
   （都是 1 个世界、最终 checkpoint、8c778f9 副本）。`fc_export.sh` 遇到已有完整结果就直接用，不重复导出。

## 2. 每条 episode 用哪条 run（`stages/evaluate/export_map.py`）

登记的选择规则，不按分数挑：

- Tier 1：`results/day2/batch_verdict_*.txt` 里有逐帧判定的批量 run（27 条），加上方盒重训的 `t1-ep{1,7,28}-…-p185-mf4090`；
- Tier 2：第 1 批的期望表 `stages/policy/queues/{ml40,mf4090}_t2{a,b,c}.expect.tsv`（27 条，ep10 以 C 段为准），加上方盒的 t2 行；
- 每条 episode 必须恰好一条 run，否则报错；步数一律用最终 checkpoint 349999104。规矩二的回退在导出时按需发生，不写进清单。

生成结果已提交：`stages/evaluate/exports/mf4090.tsv`（Tier 1 16 条、Tier 2 14 条）、`ml40.tsv`（Tier 1 14 条、Tier 2 16 条）。
ep20 按这条规则用批量那条（`t1-ep20-w2048-cap4m-mf4090`），与误差表、SOP 的批量表同一口径；用户要换成先导那条，改清单即可。

## 3. 设计

### 3.1 顺序

两台各自按这个顺序跑，前一段的日志最后一行变成结束行，后一段才开始：

```mermaid
flowchart LR
  T2[Tier 2 第 1 批评测] --> C[compat 兼容性验证] --> BT[方盒训练] --> BE[方盒评测] --> X[提交导出]
  C -. 门槛“完成 1” .-> BT
  C -. 门槛“完成 1” .-> X
```

按 `agent-doc/experiments/2026-10-02-box6-eval-runtime.md` 的估计，方盒评测 10/2 15:00–16:00 结束，导出随后开始。

### 3.2 导出链（`stages/evaluate/export_chain.sh`）

- **开始前**：等 `runs/logs/box_eval_<机器>.log` 的最后一行变成评测链结束行；`runs/logs/compat_<机器>.gate` 必须是“完成 1”；GPU 上没有别的进程；
  `V2D_FC_SRC` 是核对过的 8c778f9 副本。任何一条不满足就停，日志最后一行 `EXPORT_CHAIN_FAILED`。
- **逐行**（某行不过不停）：
  - run 没有 `DONE` → `no_done`；有 `NONFINITE` → `nonfinite`（规矩一：不导出，也不回退，记缺，等用户定）；
  - 否则 `fc_export.sh` 导出 1 个世界的轨迹，再跑 `check_export.sh`（P2 结构、P3 来历，同兼容性验证）。都过 → `ok`；导出失败 → `export_failed`；核对不过 → `check_failed`；
  - `fc_export.sh` 退出码 13（评测器报 must disable task failure termination）→ 规矩二：按步数从大到小试同一 run 里更早的 policy，最多 8 份
    （`V2D_FALLBACK_MAX`，新定的上限，约退回 8000 万步）。退出码 12（非有限、读不了）跳过，13 继续往前，导出与核对都过的那一步就用；
    别的失败停在这一条（`fallback_failed`）。用上的那一步再在 8c778f9 下补评 4096 世界（只写 JSON）：补评成功 → `fallback`，
    补评失败 → `fallback_noeval`（轨迹能交，但按 box6 计划第 4.5 节，退回的 checkpoint 要有 4096 世界评测才进候选，所以不进打包目录，人来看）。
- **落盘**：每次导出、核对、补评经 `scripts/dev/record` 写 `results/submission/exports/export_<机器>_<run>_s<步数>[_check|_w4096].txt`；
  结果表 `runs/exports/export_<机器>.tsv` 每行：档位、episode、run、用的步数、状态、JSON 与 parquet 的路径和 sha256。
  日志 `runs/logs/export_<机器>.log`，最后一行 `EXPORT_CHAIN_DONE（成功 x、失败 y）`；本日志里不出现评测链结束标记的原文（10/1 起链事故的教训）。
- **预检**（`V2D_EXPORT_CHAIN_DRYRUN=1`）：不等、不查 GPU、不写任何文件；核清单、副本、check_export 能跑、要等的日志存在；
  已训完的行跑 `fc_export.sh` 的预检（要退出码 0），还没训完或有 `NONFINITE` 的行只提示。
- **起链**：`stages/evaluate/arm_export_chain.sh <机器>`，预检要 `EXPORT_DRYRUN_OK`，tmux 会话名 `v2d-export`。
- **用时**：每条 1 个世界的导出约 1–2 分钟（估计，兼容性验证跑完后用实测更新），30 条约 1 小时；回退时每多试一份加一次导出，补评 4096 世界的时长未实测。

### 3.3 Tier 2 的帧参考（`stages/evaluate/make_frame_references.py`，mf4090 宿主机，只用 CPU）

- 每条 episode 一个 `episode_XXXXXX.npz`：`episode_index`、`coordinate_frame=released_track2_world`、`frame_index`（取发布的 Tier 2 parquet 的列）、
  `pose_xyzw` [T,1,7]（v5.4 由 wxyz 换成 xyzw）。来源取 `runs/motion_src/tier2/<序列>/v2d_meta.json` 的 `object_pose_source`，即训练用的那份 v5.4。
- 粗核世界系：v5.4 与发布的 Tier 2 带噪输入逐帧位置差的中位数要小于 0.1 m（换错世界系会差到米级）；逐条打出位置、角度差的中位数与第 0 帧的差。
- 进程开头 `forbid_tier1()`，只读 Tier 2 的文件。输出 `runs/submission/frame_refs_t2/` 与 `manifest.tsv`（含来源与输出的 sha256）。

### 3.4 拉回 Mac（`stages/evaluate/pull_submission.sh`）

只走 ssh 流（ml40 上 scp 会卡住），每个文件落地后与远端 sha256 逐个核对；目标已存在且内容不同就拒绝。

- `data`：Tier 1 干净参考（meta、data、mesh）与 Tier 2 发布输入（meta、data），约 410 MB；
- `refs`：Tier 2 帧参考；
- `exports <机器> export_<机器>`：结果表里 `ok`、`fallback` 的文件进 `runs/submission/final/t<档位>/`，`fallback_noeval` 的进 `held/`；
- `compat <机器>`：兼容性验证的 1 个世界导出，进 `runs/submission/compat/t<档位>/`，供第 3.6 节预演。

### 3.5 打包与预检（`stages/evaluate/pack_tier.sh`，Mac）

- uv 起 Python 3.12，装 kit 的 requirements，另限 `pandas<3`（kit 写时用的是 pandas 2，第 1 节事实 6）；跑前核 kit zip 的 sha256。
- `--code-commit` 用当前 HEAD 的链接，要求 HEAD 已推到 origin、除 `results/` 外工作树干净。仓库保持私有（用户 10/1 的决定）。
- Tier 2 加 `--frame-references runs/submission/frame_refs_t2`，并在落盘与显示之前滤掉 `locally computed` 那一行（第 5 节）。
- 预检只调 `v2d_submit.py … --dry-run`；脚本里没有不带 `--dry-run` 的调用。CSV 写到 `runs/submission/csv/track2_tier<档位>_<名字>.csv`，不进 git。

### 3.6 预演（兼容性验证的导出一到就做）

- **E6（Tier 1）**：`pack_tier.sh 1 runs/submission/compat/t1 rehearsal 6 8`（ml40 的 ep12 到了再加）。要求退出码 0、换算残差在容差内；交叉核对那一行照录、只报。
- **E7（Tier 2）**：`pack_tier.sh 2 runs/submission/compat/t2 rehearsal 2`（ml40 的 ep0 到了再加），要求退出码 0；
  反向对照 `V2D_PACK_NEGCTL=1` 同样的命令：不给帧参考，打包器改用发布的带噪输入，要求报“do not differ by one rigid transform”。
- 预演用 `--config` 只计这几条 episode，不跑上传器预检。

## 4. 判据（执行前登记）

| 编号 | 判据 | 不过时 |
|---|---|---|
| X1 | 每行 `fc_export.sh` 退出码 0 且 `check_export.sh` 最后一行 `EXPORT_OK` | 按第 3.2 节的状态记，不自动重跑 |
| X2 | 两台导出链最后一行 `EXPORT_CHAIN_DONE`，结果表 30 行 | 停在开头的检查：人看原因，修好后改名旧日志再起 |
| X3 | 拉回 `PULL_OK`，每个文件的 sha256 与结果表或远端一致 | 重拉；仍不一致就停 |
| X4 | 每档 30 条打包退出码 0，换算残差在打包器容差内；Tier 2 的落盘与屏幕输出里没有 `locally computed` | 按打包器的报错定位到 episode |
| X5 | 上传器预检打印 “looks valid” 与 “--dry-run: nothing submitted.” | Tier 2 若因 tier2-auc 规则未接受或队伍名不一致而不过，记为用户待办，不算流程失败 |
| R1 | E6、E7 退出码 0，E7 反向对照 `NEGCTL_OK`，帧参考 `FRAME_REFS_OK 30` | 先修帧参考或打包参数，再起导出链 |

只报、不作判据：Tier 1 的交叉核对行（“the trajectory reproduces the evaluator's own metrics”或不一致的明细）；每条 episode 1 个世界的指标与同一 checkpoint 4096 世界评测的差别
（kit 的说法是 explicit 重置下各世界从同一帧出发、policy 确定，所以只交 1 个世界；这一点我们没有单独验证过）。

**第 1 步完成**：两档 X1–X5 都过，结果写进执行记录并过 jev。某一档凑不齐 30 条时，这一档的 CSV 打不出来（打包器要全部 30 条），按下表交用户定：

| 情形 | 默认处理 |
|---|---|
| `nonfinite` | 不导出（规矩一）。是否也退到更早的有限 checkpoint，规矩二没有覆盖，等用户定 |
| `no_done`（方盒没训完或失败） | 按 box6 计划第 4.5 节的结局记；是否重训等用户定 |
| `fallback_noeval` | 不进打包目录；补评或直接采用，等用户定 |
| `export_failed`、`check_failed`、`fallback_failed` | 先查原因写进记录，不自动重跑 |

## 5. 净室

- Tier 2 的帧参考只读 Tier 2 的文件与 v5.4，进程开头 `forbid_tier1()`；测试里有“来源指向 Tier 1 目录时被拦下”一项。
- Tier 2 打包用官方打包器，它会读干净参考来核帧、算本地分数（kit 原文：“Local scores use the clean reference”）。打包是官方的提交步骤，照做；
  但 Tier 2 的本地分数是按 Tier 1 干净参考算的数，我们的解读是不拿来做任何 Tier 2 的选择，所以在落盘与显示之前滤掉那一行
  （属解读，不是官方原文；box6 计划第 5 节已登记，用户还没确认）。
- Tier 2 导出的 metrics JSON 是对 policy 输入（v5.4）算的，与已有的 Tier 2 评测同一口径，不和 Tier 1 比。
- Kaggle 的 Tier 2 排行榜给出的也是对干净参考的分数，而且滤不掉。排行榜反馈怎么用，要在第一次交 Tier 2 之前定下（用户决定）。

## 6. 执行步骤

1. Mac：新脚本的测试全过；提交、推送（本版）。
2. Fable 5.1 审计划与代码；按审查意见修改，再提交。
3. `scripts/dev/push-new-files` 把新文件放到两台（只加新文件，不动在跑的链）；服务器上跑 `test_export_chain.py`（两台）与
   `test_make_frame_references.py`（mf4090 宿主机，没有 pandas，kit 那部分跳过）。
4. mf4090（只用 CPU）：`scripts/dev/record submission/frame_refs_t2_mf4090 python3 stages/evaluate/make_frame_references.py`，要 `FRAME_REFS_OK 30`。
5. 两台：`scripts/dev/record submission/exports/arm_<机器> stages/evaluate/arm_export_chain.sh <机器>`，要 `ARMED`。
6. Mac：`pull_submission.sh data`、`pull_submission.sh refs`（对服务器只读）。
7. 兼容性验证跑完（mf4090 约 06:30，ml40 约 10:45）：`pull_submission.sh compat <机器>`，做第 3.6 节的预演。
8. 导出跑完（约 16:30–17:00）：拉回两台的结果，打两档，跑上传器预检；结果写进执行记录，过 jev，向用户回报。不上传。

## 7. 留给用户的决定

- 什么时候开始上传（现在不传）；tier2-auc 的规则、各比赛的队伍改名（用户在浏览器里操作）。
- Tier 2、Tier 3 的本地分数是否照现在的解读滤掉；Tier 2 排行榜反馈怎么用。
- ep20 用哪条（默认批量那条）。
- 第 4 节下表里出现的情形。

## 8. 代码清单

| 文件 | 作用 | 测试 |
|---|---|---|
| `stages/evaluate/export_map.py` | 生成导出清单 | `test_export_map.py`：已提交的清单与重新生成的逐字节相同、两档各 30 条；重复、缺条、已存在时报错 |
| `stages/evaluate/exports/{mf4090,ml40}.tsv` | 导出清单 | 同上 |
| `stages/evaluate/export_chain.sh` | 导出链 | `test_export_chain.py`：7 组（正常、规矩二的四种走向、行内失败、开头停、拒绝、等待、预检） |
| `stages/evaluate/arm_export_chain.sh` | 起链 | 部署时跑预检 |
| `stages/evaluate/make_frame_references.py` | Tier 2 帧参考 | `test_make_frame_references.py`：格式、xyzw、sha256，用 kit 的函数读回；世界系不对、帧数不对、来源不是 v5.4、读 Tier 1 被拦 |
| `stages/evaluate/pull_submission.sh` | 拉回 Mac | 第一次拉 `data` 时实测 |
| `stages/evaluate/pack_tier.sh` | 打包与预检 | `test_pack_tier.py`：Tier 2 滤掉本地分数、Tier 1 保留、只调 `--dry-run`、预演配置、反向对照、拒绝条件 |

## 9. 审查记录

（待填）
