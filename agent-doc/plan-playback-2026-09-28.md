# 回放速度对照计划（第 1 版）：Day 1b 诊断触发条件 T2

- 日期：2026-09-28（MDT；服务器日志是北京时间，早 14 小时）；分支 `track2/p1-training`
- 命名：T2 是 Day 1b 逐帧诊断的第 2 个触发条件（“滞后”），**与 Tier 2 无关**。本计划的 run 名带 `rt`（real time），
  结果放 `results/playback/`；数据是 Tier 1 ep20（rice_cooker）。
- 顺序：计划 → 独立审查 → 修订 → 登记并提交 → 执行
- 占卡：mf4090 约 3 小时（开跑前由用户知会队友）；ml40 约 2.5 小时，排在 snack_box 对照第 2 次之后（开跑前由用户与 yqchen 约时段）

## 出发点（事实）

证据文件：`results/playback/upstream_playback_facts.txt`（上游 33129dd 的源码与配置摘录，`stages/policy/playback_facts.sh` 生成）、
`results/day1/diag_t1-ep20-*.txt`、`results/day1/static_baseline_ep20.txt`、`results/ml40/day1/wb_summary.txt`。
事实 2–10 的 jev 核对：`results/playback/jev_claims_plan.txt`（`agent-doc/plan-playback-2026-09-28.claims.json`，12 条全部 ≥ 0.77，真假对照 0.98 / 0.02）。

1. **触发**：ep20 满配（1000 万 buffer，ml40）第 209–420 帧的中位净转动比 0.704，低于第 420 帧不越物体门槛所需的 0.720
   （参考在这一段净转 307.1°）。操作结束后物体停在比参考少转约 75° 处，第 3 段贡献差 −0.045。
   100 万 buffer（mf4090）中位 0.756，没触发；但它 3315 个世界先在手上越线，成功 62 个（满配 3285 个）。
2. **G1 配方逐帧回放**：`task.source_frame_playback: true`、`motion_speed: 1.0`（`g1_recon_body_flash_sac.yaml` 第 16–17 行，PPO 版相同）。
   每个 50 Hz 控制步走一帧源数据。ep20 parquet 是 30 fps，于是按 1.67 倍速播放：553 帧 = 11.06 s，真实时长 18.4 s。
3. **关掉逐帧回放**（`motion_speed` 仍为 1.0）时，加载器按时间重采样到 50 Hz：`resample_times` 给出 round(552 / 30 × 50) + 1 = 921 帧；
   关节与位置线性插值，四元数 slerp，接触取最近帧（`data/motion_v1.py` 第 271–291 行、`data/resampling.py` 第 11–18 行）。
   参考 fps 取控制频率（第 312 行），环境断言两者相等（`envs/base.py` 第 118 行）。
4. **上游其他配方不逐帧回放**：`task/default.yaml` 与三个 Sharpa 手部配方都是 `source_frame_playback: false`、`motion_speed: 0.5`（半速），
   只有 G1 ReconBody 的两个配方逐帧回放。官方评测按哪种速度播放不知道：上游 HEAD 今天仍是 v0.4.0（33129dd），比赛评测脚本没有发布。
5. **评测器按 checkpoint 自带的配置重建参考**：配置取自 checkpoint 元数据（`evaluation/harness.py` 第 332–348 行）；评测组合那一步只改
   scene / env / termination（第 173–208 行），`motion_speed` 与 `source_frame_playback` 原样传给 `setup_scene`（第 361、372 行）；
   评测步数 = 参考帧数（第 378 行）。所以每个 policy 都按它训练时的速度评测；真实时长的 policy 评 921 步。
6. `stages/evaluate/static_baseline.py` 同样按 policy 的配置加载参考，能直接算出真实时长参考的不动基线与转动剖面。
7. **curriculum 阈值是绝对步数**（35,000,320 … 349,999,104；VOC 在 209,999,872 步即 60% 处降到 0；82.5%、87.5% 处引入首帧起步）。
   总步数不变，两臂的 curriculum 就完全相同；改总步数得连阈值一起改。
8. 观测里的参考预览是未来第 0、5、10 个控制步（`envs/recon_body.py` 第 23、192 行）：两种回放下都是 0.2 s 仿真时间，
   但真实时长下只覆盖 0.2 s 的源动作（逐帧回放覆盖 0.33 s）。`reset_freeze_steps` 50、VOC 衰减 10 步，也按控制步计。
9. 训练种子 = `reset.seed`，`fc_train.sh` 固定为 42，两臂同种子。GPU 上训练不逐位可复现；**训练随机性有多大没有测过**（没有重复种子的 run）。
10. 队列行末尾可以带 Hydra 覆盖，`fc_config_check.sh` 只放行队列行里写出的键。训练路径脚本（fc_run / fc_train / fc_queue）与 Day 1 训练所用
    7e30e3d 逐字节相同（`git diff` 为空）。
11. 吞吐：Day 1 的 100 万 buffer（mf4090）中位 47,803 步/秒；满配（ml40）47,310 步/秒，训练用时 2 h 10 min。回放方式不改每步开销。
    mf4090 盘剩 21 GB，一条 100 万 buffer 的 run 约 0.5 GB。
12. Day 1b A 第 1 次尝试在上传 checkpoint artifact 时，因 W&B token 核验连不上服务器而崩溃，所以正式 run 一律 `V2D_WANDB_UPLOAD_CKPT=0`。
    冒烟判据要求日志里有 W&B 同步成功的行，冒烟保留上传。
13. 训练期曲线（W&B 分段汇总）：满配最后三段物体旋转误差 0.674 → 0.661 → 0.654 rad，基本走平；100 万 buffer 最后一段 palm 终止占 0.75。
14. 帧换算：真实时长第 k 帧 ↔ 时刻 k/50 s ↔ 源第 0.6k 帧。源第 209、269、359、420、552 帧 ↔ 348.3、448.3、598.3、700、920。

## 问题与假设

问题：满配 ep20 转动跟不上（中位净转比 0.70 < 0.72），是不是因为 1.67 倍速回放让转动快过了机器人跟得上的速度？
- H（速度是瓶颈）：按真实时长训练与评测，净转动比明显上升并超过所需比值，第 3 段的残差缩小。
- 对立：跟不上与速度无关，原因在参考的手-物几何（T4）、奖励或策略本身。

## 设计

2 × 2：buffer {1000 万（ml40），100 万（mf4090）} × 回放 {1.67 倍速（Day 1 已有），真实时长（新训）}。每格一个种子（42），
总步数 349,999,104，curriculum 不变。两臂只差 `task.source_frame_playback=false`。

- 满配这一对直接回答 T2（触发来自它）。100 万这一对是同一效应在另一个 buffer 下的第二次测量，看方向是否一致；
  没有重复种子，这是现在最便宜的稳健性检查。
- 总步数相同，而不是每帧访问次数相同：这样 curriculum 与算力都一致。代价是真实时长的参考长 1.67 倍，每个参考帧被访问的次数约为 0.6 倍，
  这个混杂对真实时长一臂不利。所以“支持”的结论偏保守；“否定”要看训练是否走平（见判据）。
- 两臂各按自己的速度评测（事实 5），各自对照自己的不动基线；关注段按时间对齐（1.67 倍速 209–420，真实时长 348–700）。
- 不做交叉评测（真实时长训练、1.67 倍速评测）：官方口径未知，这个数现在没有决策用途。

## 执行链

### mf4090（`stages/policy/queues/mf4090_playback.sh`，tmux，任何一步不符即停）

0. 守卫：GPU 上没有别的进程；正式 run 目录不处于“有 checkpoint、没有 DONE”；parquet sha256 前 16 位 `9e3503b5396b42a4`（与 Day 1 同一份）。
1. 冒烟 `smoke-t1-ep20-w2048-cap1m-rt-mf4090`：409.6 万步，W&B 记到 `v2d-selftest`，`V2D_MAX_RETRY=0`，保留 checkpoint 上传；
   覆盖 `training.replay.capacity=1000000 task.source_frame_playback=false`。
   `smoke_check.sh`：显存峰值 ≤ 14,000 MiB（Day 1 同配置实测 11,555），镜像指纹 `e2934912858820b8` / `df0cf35711a68fb3`（Day 1 mf4090 的值）。
2. 参考核对（都经 `scripts/dev/record` 落到 `results/playback/`）：
   - `static_baseline.py` 用冒烟 policy，再用 `playback_refcheck.py` 与 Day 1 的 `static_baseline_ep20.txt` 对照：帧数 921、`source_frame_playback False`；
     不动 ADD-AUC 与 0.4708 相差 ≤ 0.010；首次越 1.5 rad 的帧与 448.3 相差 ≤ 2；源第 60、120 … 540 帧与真实时长第 100、200 … 900 帧
     离初始朝向的角度相差 ≤ 2°。
   - 冒烟 policy 的 256 世界 `fc_eval.sh`：正常返回，评测 JSON 的 `step_count` = 921。
   - 由核对输出填 `stages/evaluate/diag_playback.runs` 的 G4 已知答案（增量 > 0.5° 的首末帧、首次越 1.5 rad 的帧）。这一步在正式评测之前完成并提交。
3. 正式 `t1-ep20-w2048-cap1m-rt-mf4090`：349,999,104 步，`V2D_MAX_RETRY=0`，`V2D_WANDB_UPLOAD_CKPT=0`，W&B 标签 `playback`，覆盖同冒烟。
4. 4096 世界 `fc_eval.sh`、`verdict.py`（Day 1 判据，门槛用真实时长的不动基线）、`policy_inputs.py`，都经 record。
5. 逐帧诊断：`V2D_DIAG_RECORD_DIR=playback stages/evaluate/diag_day1b.sh stages/evaluate/diag_playback.runs`
   （本 run 一行：关注段 348–700，G6 帧 598，帧换算 5/3）。
6. 日志最后一行 `PLAYBACK_DONE` 或 `PLAYBACK_FAILED`。

### ml40（`stages/policy/queues/ml40_playback.sh`）

snack_box 对照链结束（日志最后一行 DAY1B_DONE 或 DAY1B_FAILED、tmux 会话已退出），且用户与 yqchen 约好时段，再同步代码、核对配置、启动。
snack 链结束之前不往 ml40 同步代码：同步会改写 `.v2d-source-commit`，snack 评测结果头部的来历就不对了。

0. 守卫同上。`fc_config_check.sh` 在启动前跑：与配方的差只有命名类与队列行写出的 `task.source_frame_playback`。
1. 正式 `t1-ep20-w2048-cap10m-rt-ml40`：满配 + `task.source_frame_playback=false`，349,999,104 步，`V2D_MAX_RETRY=0`，`V2D_WANDB_UPLOAD_CKPT=0`。
   不另做冒烟：真实时长这条代码路径在 mf4090 上冒烟过（同上游、同镜像指纹），ml40 的满配路径 snack 正在跑；第一个 checkpoint（约 5 分钟）前失败就停。
2. 4096 世界评测、`policy_inputs.py`，经 record。
3. 诊断在 mf4090 上做（同 Day 1b）：policy 与 ml40 评测 JSON 经 Mac 中转（`scripts/dev/relay-run`，三端 sha256 一致，写 `COPIED_FROM.json`），
   `diag_playback.runs` 加一行，带 ml40 评测 JSON 的 sha256。

## 判据（事先登记）

**有效性**：两条正式 run 各一段跑完（DONE，`run_record.jsonl` 只有一次 start）；冒烟与参考核对全过；
四份诊断报告（Day 1b 的两份对照 + 新的两份）VALIDITY 全 PASS。任何一条不满足：只列数字、不判定。

**主指标**：同一 buffer 的一对里，真实时长减 1.67 倍速的中位净转动比之差 Δr（诊断 Q2，关注段按时间对齐）。

| 判定 | 条件 |
|---|---|
| 支持（速度是瓶颈） | Δr(满配) ≥ +0.10，且真实时长满配的中位净转比 ≥ 它自己的所需比值，且 Δr(100 万) > 0 |
| 否定（速度不是瓶颈） | Δr(满配) < +0.03 |
| 部分 | 其余情况 |

阈值没有训练随机性的估计可依（事实 9），所以故意放宽：+0.10 相当于关注段末多转约 31°，比 Day 1 两种 buffer 之间的差（0.05）还大。
只拿到 100 万一对时（ml40 没排上），同样的阈值用在 100 万这一对上，结论标“仅 100 万，T2 是在满配上触发的，只作参考”。

**次要（照报，不改变判定）**：ADD-AUC 相对各自不动基线的差及其变化、三段贡献差、成功世界数、操作段 palm 误差中位、
Day 1 判据（`verdict.py`）、训练期曲线。判为否定或部分时，若真实时长 run 的 W&B 分段汇总里最后一段物体旋转误差比第 6 段
（VOC 刚降到 0 的那段）低 ≥ 10%，标注“可能没训够（每帧访问约 0.6 倍）”，下一步候选里加一条等访问量的 run
（总步数与 curriculum 阈值都乘 5/3），做不做由用户定。

判定由 `stages/evaluate/playback_compare.py` 按上表机械给出，脚本在执行前写好并测过。

## 结果 → 下一步

- 支持：1.67 倍速确实卡住了转动。数字写进给组委会的邮件（官方评测按哪种速度播放）；得到答复之前，上榜用的训练不改回放方式；
  候选实验：速度 curriculum（先真实时长，再逐步加速到 1.67 倍）。
- 否定：转动跟不上与速度无关，下一步转 T4（参考右手离物体 5.9 cm，查重定向管线）与 T1（操作开始前预转约 20°，查接近、reset 与 VOC）。
- 部分：如实报告；是否加重复种子由用户定。

不管结果如何，官方评测的回放速度都要问组委会（已在待发邮件里）。

## 工具改动（执行前完成并测试）

1. `diag_report.py` 加 `--frame-scale`（默认 1）：Q1 另列的 ep20 关键帧（100、269、300、359、360）按倍数换算，只影响打印。
   `diag_day1b.sh` 的运行表加可选第 10 列（帧换算，缺省 1），旧表不受影响。合成测试补两项：不给参数时输出不变；给 5/3 时 Q1 列出换算后的帧。
2. `stages/evaluate/playback_refcheck.py`：读两份 `static_baseline` 输出，做上面第 2 步的参考核对，打印 G4 已知答案；合成测试（通过一例、四种改坏各一例）。
3. `stages/evaluate/playback_compare.py`：读四份诊断报告的 `summary_json`，按判据表给出支持 / 否定 / 部分，附次要数字；
   合成测试（三种判定各一例、闸没过、只有 100 万一对）。
4. 队列与链：`queues/mf4090_playback_smoke.txt`、`mf4090_playback.txt`、`mf4090_playback.sh`、`ml40_playback.txt`、`ml40_playback.sh`；
   两台机器的队列都先过 `fc_config_check.sh`。
5. `scripts/dev/relay-run`：经 Mac 把一个 run 的 policy 与评测 JSON 从一台机器转到另一台，三端 sha256 核对，写 `COPIED_FROM.json`。
6. `stages/policy/playback_facts.sh`（已写，输出已落盘）：上游事实摘录，也是 jev 核对的证据。

## 时间（丹佛）

- mf4090：冒烟与核对约 15 分钟，正式训练约 2 小时，评测与诊断约 40 分钟，共约 3 小时。
- ml40：snack 对照预计 09:45 前后结束。约好时段后训练 2 h 10 min、评测约 15 分钟；它的诊断在 mf4090 上再要约 30 分钟。
- 两边都顺利时，结论在 13:30 前后。

## 风险与限定

- 单种子：两对方向一致只能降低、不能排除偶然。
- 官方评测的回放速度未知：真实时长 policy 的分数只和它自己的不动基线比，不能当榜上分数的预测。
- 真实时长的 episode 更长，除了每帧访问变少，reset 次数、首帧起步的相对频率也跟着变；这些都算在“回放方式”这个处理里，不单独拆。
- mf4090 与 ml40 都是共享卡。
