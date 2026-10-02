# 执行记录：8c778f9 兼容性验证 + 方盒三条两档重训（10/1 晚部署，10/2 自动执行）

计划 `agent-doc/plan-box6-and-eval-runtime-2026-10-01.md` 第 2 版（3b55a0e），按 Fable 5.1 的计划与代码两份审查修改（两份都是 GO WITH FIXES，没有 BLOCKER）。
时间一律 UTC-6；服务器日志是北京时间（UTC+8）。

## 部署与预检（10/1 20:49–21:02，不占 GPU，Tier 2 链没动）

| 项 | 结果 | 落盘 |
|---|---|---|
| 放新文件 | 两台各 27 个新文件，md5 全对，`.v2d-source-commit` 仍是 90a73fa8e852；之后按需覆盖了 4 个我们自己放上去的文件（`V2D_PUSH_REPLACE_FROM`，只许覆盖先前那一版） | `results/box/deploy{,2,3,4,5}_{mf4090,ml40}.txt` |
| 源码副本 | mf4090：p185、8c778f9 两份都 FC_SRC_OK；ml40：新建 8c778f9 副本 FC_SRC_OK，已有的 p185 副本复核 FC_SRC_OK | `results/box/fc_src_{mf4090,ml40}.txt` |
| 副本核对的一处修正 | ml40 的 p185 副本第一次核对不过，差异全在 `assets/.cache/convex/*.npz`：FlashCHORD 建场景时写的凸包缓存，npz 带时间戳，同名文件字节也不同；`support.py` 本身一致。核对改为跳过 `.cache/`（f779ffc） | `results/box/fc_src_ml40.txt.failed` |
| 宿主机测试 | mf4090 宿主机 6 套全过（python 3.10.12、numpy 2.2.6、pyarrow 25.0.1）；ml40 宿主机没有 numpy：4 套只用标准库的在宿主机过，2 套要 numpy 的在容器里过。check_export 因此改由 `check_export.sh` 在缺库时进容器跑（781accd） | `results/box/tests_{mf4090,ml40}.txt`、`tests2_mf4090.txt`、`tests3_mf4090.txt` |
| compat 预检 | 两台 COMPAT_DRYRUN_OK：每行 fc_export 的预检退出码对（守卫行 12），要等的日志在，副本核得过；ml40 的 check_export 走容器 | `results/box/compat_dryrun{,2}_{mf4090,ml40}.txt` |
| 配置核对与正向预检 | mf4090 8 份、ml40 4 份配置与官方配方的意外差异都是 0；PRECHECK_OK（4 条、2 条 run） | `results/box/cfgcheck_{mf4090,ml40}.txt` |
| P5′ 打包换算 | Tier 1 30 条对发布输入、Tier 2 30 条对 v5.4，全部 FRAME_REF_OK，残差约 0.0001 mm、0.0001 mrad；计分帧合计 22,989，与样例提交的行数相同 | `results/box/frame_ref_t{1,2}_mf4090.txt` |
| Tier 2 方盒参考的穿透（#185 几何） | ep1 对椅背 121 帧嵌入超过 5 mm、52 帧穿板；ep7 熨斗 123 帧有顶点穿到 1 cm 桌板另一侧；ep28 两块板 244、211 帧穿过，160 帧低于地面超过 5 mm。已补进计划的事先登记 | `results/box/support_penetration_t2_mf4090.txt` |

P5′ 的结论：只要评测器记下的参考就是 motion parquet 的物体位姿（导出后由 check_export 复核），两档打包时的刚体换算都不会挡住；Tier 2 给 `--frame-references` 传 v5.4。

## 起链（10/1 20:58 失败、21:01 重起）

- **20:58 第一次起链，失败**（安全地失败：没有任何 GPU 任务开跑，Tier 2 链没动）。compat 往自己日志里写了等待提示
  “等 … 的最后一行变成 DAY2_EVAL_DONE / DAY2_EVAL_FAILED”。chain_after.sh 盯着 compat 日志的最后一行找 `DAY2_EVAL_(DONE|FAILED)`，
  当场把这句等待提示当成 compat 已经结束，去读门槛文件，门槛还没写，就在方盒训练日志里写了 DAY2_TRAIN_FAILED；
  方盒评测链随即开始，GPU 检查发现 Tier 2 的进程，停下（`results/box/arm_{mf4090,ml40}.txt`）。
  两边的测试与审查原型都是先跑完 compat 再跑 chain_after，没测到两者同时在跑的情形。
- **处理**：停掉在等的 compat 会话，三份日志改名为 `*.aborted-10021059` 留档；compat 日志里只有最后一行带结束标记的原文
  （等待提示改写，上一段评测链的结束行抄进来时把标记换成中文）；补测试“compat 在等时 chain_after 同时盯着，不许提前决定”，
  它在旧脚本上失败、新脚本上通过，另断言 compat 日志里只有一行带结束标记（c354d7a）。服务器上重跑测试与两台预检，都过。
- **21:01 重起**，两台各三个会话都在等（`results/box/arm2_{mf4090,ml40}.txt`）：
  compat 等上一段评测链结束；chain_after 有进程（mf4090 899044、ml40 37234），挺过了第一次检查；方盒评测链在等方盒训练日志。

## 接下来（自动）

| 时间（估计） | 机器 | 事件 |
|---|---|---|
| 10/2 06:15 前后 | mf4090 | Tier 2 B 段评完 → compat 开始（约 15 分钟）：4 行导出、1 行 4096 世界比对、守卫与反向对照 → 门槛 → 方盒 4 条（t1-ep1、t1-ep7、t1-ep28、t2-ep28） |
| 10/2 08:15 前后 | ml40 | Tier 2 B 段评完 → C 段（ep10）约 2.5 小时 |
| 10/2 10:45 前后 | ml40 | C 段评完 → compat（约 10 分钟）→ 门槛 → 方盒 2 条（t2-ep1、t2-ep7） |
| 10/2 15:00–16:00 | 两台 | 方盒 6 条评完（8c778f9 副本，4096 世界，只评最终 checkpoint） |

Mac 回来后要做的：拉回 compat 结果与导出，按计划第 3.5 节的判据与决策表下结论，写进本记录、过 jev；方盒评完后跑
`batch_verdict.py --steps 349999104` 与 `mount_check.py`；链跑完后整体同步一次（来历会从 90a73fa 更新）。

## mf4090 兼容性验证结果（10/2 06:33–06:43，按计划第 3.5 节下结论）

Tier 2 B 段 06:32:56 评完（成功 8、失败 0），compat 06:33:32 开始，06:42:50 结束：`COMPAT_PASS（7 行全部符合）`，门槛 `完成 1`
（`runs/logs/compat_mf4090.log`；逐行结果 `results/submission/compat/mf4090_*.txt`）。

| 判据 | 结果 |
|---|---|
| P1 加载 | 4 个 export 行（t1-ep8、t1-ep6、t2-ep2 各 1 个世界，t1-ep8 2 个世界）`fc_export.sh` 都退出码 0 |
| P2 结构 | 4 份导出逐项通过：schema、米、xyzw、世界数、刚体数、起始帧 0、步数等于 motion 帧数（708、546、980）、行数、`reference_frame = step`、`environment_valid` 全真、位姿全有限、`non_finite_worlds` 为空 |
| P3 来历 | `checkpoint_sha256` 等于 policy 文件；`eval_code_sha256` b1b3ebe3…、`eval_script_sha256` 160d24f5… 等于 8c778f9 的值 |
| P4 一致 | t1-ep6 4096 世界：8c778f9 ADD-AUC 0.6335、v0.4.0 0.6321，差 +0.0014（< 0.005）；chord_sr 0.9585 对 0.9531，\|z\| 1.18（< 3）；CONSISTENT |
| N1 守卫 | t1-ep1（含 NaN）`fc_export.sh` 退出码 12，不起容器 |
| N2 反向对照 | 关掉守卫导出 t1-ep1：评测器出错，`fc_export.sh` 退出码 3（不是终止报错），没有产出能通过核对的导出，符合期望 |

只报：
- 1 个世界与 4096 世界：t1-ep6 只导 1 个世界时 MP-SR 是 0、ADD-AUC 0.6327，同一 checkpoint 4096 世界的 MP-SR 是 0.5696、ADD-AUC 0.6335。
  单世界提交是这个分布里的一个样本，本地 4096 世界的 MP-SR 不能直接读成排行榜上这条 episode 会不会成功。
- t1-ep8 2 个世界的导出：ADD-AUC 0.6732，MP-SR、chord_sr、SP-SR 都是 1.0。
- 评测器记下的参考位姿与 motion parquet 的物体位姿：位置最大差 0.0000 mm，朝向最大差 0.040–0.043°。这一项 `check_export.py` 没有先把 motion 那一侧的四元数归一化
  （评测器那一侧归一化了），float32 存储时归一化误差 1e-7 量级就会在 arccos 里放大成这个量级。打包器两侧都归一化，E6、E7 预演实测的换算残差是 1.7e-7 rad、1.1e-7 rad
  （`agent-doc/experiments/2026-10-02-submission-exports.md`），所以这 0.04° 是比较方式造成的，不是评测器参考真有这么大的偏差。
- `fc_export.sh` 第一次给某个 run、步数、世界数写日志时，`wc -l < 日志` 会往 stderr 打一句“No such file or directory”，不影响结果（只是显示）。

结论（决策表第一行，mf4090 部分）：v0.4.0 训出的 checkpoint 能在 8c778f9 里加载、导出，提交用 8c778f9 副本导出；ml40 那台的 compat 排在 C 段之后（约 10:40），两台都过才算这一行成立。
门槛过后 06:43:34 方盒训练链开始：4 条冒烟（t1-ep1、t1-ep7、t1-ep28、t2-ep28）都 `SMOKE_OK`，前三条的 256 世界 rollout 非有限世界都是 0（`runs/logs/box_train_mf4090.log`）；
正式训练按 t1-ep1、t1-ep7、t1-ep28、t2-ep28 的顺序跑，每条约 2.2 小时，估计 16:00 前后训完。

## ml40 兼容性验证结果（10/2 10:09–10:17，按计划第 3.5 节下结论）

C 段 ep10 10:09:16 评完（`DAY2_EVAL_DONE（成功 1、失败 0）`），compat 10:09:40 开始，10:17:21 结束：`COMPAT_PASS（3 行全部符合）`，门槛 `完成 1`
（`results/ml40/submission/compat/ml40_*.txt`）。

| 判据 | 结果 |
|---|---|
| P1 加载 | 2 个 export 行（t1-ep12、t2-ep0 各 1 个世界）`fc_export.sh` 都退出码 0 |
| P2 结构 | 两份导出逐项通过：步数等于 motion 帧数（700、778）、`environment_valid` 全真、`non_finite_worlds` 为空等 |
| P3 来历 | `eval_code_sha256` b1b3ebe3…、`eval_script_sha256` 160d24f5… 等于 8c778f9 的值，checkpoint sha256 对得上 |
| P4 一致 | t1-ep12 4096 世界：8c778f9 ADD-AUC 0.6972、v0.4.0 0.6968，差 +0.0004；chord_sr 0.9917 对 0.9907，\|z\| 0.47；CONSISTENT |

ml40 的清单没有守卫与反向对照行（这两行只在 mf4090 上跑，都已符合期望）。

只报：t1-ep12 只导 1 个世界时 MP-SR 是 1.0（4096 世界 0.9919）；t2-ep0 只导 1 个世界时 MP-SR 是 0（对照 Tier 2 v5.4 参考），ADD-AUC 0.3127；
评测器参考与 motion parquet 的朝向最大差 0.043°、0.044°，同 mf4090，是核对脚本没归一化造成的（打包器实测残差 1e-7 量级，见提交流程的执行记录）。

**两台的结论（决策表第一行）**：P1–P3 两台都过，“v0.4.0 训出的 checkpoint 能在 8c778f9 里加载、导出”成立。第 1 批的 54 份 policy 继续当候选，提交一律用 8c778f9 副本导出；
P4 两台都过（t1-ep6 差 0.0014、t1-ep12 差 0.0004），已有的 v0.4.0 下 4096 世界评测与判定可以沿用。

门槛过后方盒链开始：ml40 两条冒烟都通过，10:27:26 起正式训练 t2-ep1（`runs/logs/box_train_ml40.log`），之后是 t2-ep7。

## 方盒 t1-ep7 正式训练发散，看守止损（10/2 09:52）

- `t1-ep7-w2048-cap4m-p185-mf4090` 08:54:33 起正式训练（#185 补丁副本）。看守逐份扫 checkpoint：1 亿到 130,004,992 步都是非有限 0 / 1,207,577；
  140,005,376 步与 150,005,760 步各有 5892 个 NaN，连续 2 份非有限，09:52:37 调 fc_stop，链记“发散：看守止损”，接着训 t1-ep28
  （`runs/logs/box_train_mf4090.log`、`runs/logs/t1-ep7-w2048-cap4m-p185-mf4090.nanwatch.log`）。本地 .wandb 里的 NaN 字样 09:40 起出现。
- 冒烟（400 万步，256 世界 rollout 非有限世界 0）是通过的；计划第 4.5 节事先登记过“#185 几何下满 3.5 亿步没跑过，靠看守兜底”。看守按设计起了作用。
  发散排查的结论（v0.4.0 把方盒建成 1 m 立方体是 ep7 冒烟发散的触发）只覆盖 400 万步的冒烟；这条正式 run 说明 #185 几何下 ep7 在约 1.4 亿步仍会发散，原因没查。
- 按第 4.5 节的结局：发散，不人工续训。run 目录没有 DONE，导出链会把 Tier 1 ep7 记成 `no_done`，Tier 1 凑不齐 30 条、打不出 CSV。
  接下来怎么办等用户定（提交流程计划第 4 节的决策表）：用最后一份有限的 checkpoint（130,004,992 步，约训练的 37%，要先在 8c778f9 下评 4096 世界才能进候选，
  这超出了规矩二的范围）、换种子或带改动重训，还是先不交 Tier 1。
- 同一序列的 Tier 2 方盒 `t2-ep7-…-p185-ml40` 排在 ml40 的 t2-ep1 之后，同样有看守。

## 方盒 t2-ep7 正式训练也发散，看守止损（10/2 13:21）；方盒训练与导出收尾

- `t2-ep7-w2048-cap10m-p185-ml40` 12:19:40 起正式训练。看守扫到 140,005,376 步都是非有限 0 / 1,207,577，150,005,760 与 160,006,144 步各 5892 个 NaN，
  13:21:45 调 fc_stop；冒烟是通过的（`results/box/t2ep7_divergence_ml40.txt`）。ml40 的方盒训练链以 `DAY2_TRAIN_DONE（完成 1、失败 0、跳过 0、发散 1）` 结束。
- mf4090 的 t2-ep28 13:46:15 训完，方盒训练链以 `DAY2_TRAIN_DONE（完成 3、失败 0、跳过 0、发散 1）` 结束。6 条方盒的结局：t1-ep1、t1-ep28、t2-ep1、t2-ep28 完成，t1-ep7、t2-ep7 发散。
  方盒评测链 mf4090 14:01:33 结束（成功 3）、ml40 13:28:36 结束（成功 1），两条 ep7 没有 DONE、不评（`results/t2/status_{mf4090,ml40}_1430.txt`）。
- 两台的方盒评测链与导出链都已结束：ml40 13:56:53、mf4090 14:26:24，各是 `EXPORT_CHAIN_DONE（成功 29、失败 1）`，没导出的就是两档的 ep7（`no_done`）
  （`results/box/export_end_mf4090.txt`）。两档都只缺 ep7，都打不出 CSV。
- 两条 ep7 都坏在 1.33–1.43 亿步，不是偶然。事实分析（先坏的是环境侧的量、奖励归一化器与 BatchNorm 统计量不设防、只有 ep7 的桌面是 1 cm 薄板）与选项见
  `agent-doc/experiments/2026-10-02-ep7-divergence-analysis.md`，jev 19 条全部核实。怎么补等用户定。

## 方盒 4 条跑完的 run 的判定与挂载核对（10/2 15:17）

- 按批量判据（最终 checkpoint、8c778f9 副本、4096 世界）4 条都不通过：t1-ep1、t1-ep28、t2-ep28（mf4090）与 t2-ep1（ml40）的 chord_sr、MP-SR、SP-SR 都是 0，
  MPPE 45.6–60.4 cm；t1-ep28、t2-ep1 的 ADD-AUC 高于不动基线（0.1311 对 0.1163、0.204 对 0.170），t1-ep1、t2-ep28 低于基线。两条 ep7 没有最终 checkpoint，记无效
  （`results/box/batch_verdict_{mf4090,ml40}_box.txt`）。Tier 2 的分数对照 Tier 2 v5.4 参考，不和 Tier 1 比。
- 挂载核对两台都是 `MOUNT_OK`：4 条 run 的训练日志指向 #185 补丁副本，评测日志指向 8c778f9 副本（`results/box/mount_check_mf4090.txt`、`results/ml40/box/mount_check_ml40.txt`）。
- 两条 ep7 发散前最后一份有限 checkpoint 的评测 15:15、15:17 在两台起链，见 `agent-doc/plan-ep7-eval-and-guards-2026-10-02.md` 的 A 部分与 `agent-doc/handoff-ep7-2026-10-02.md`。
