# Tier 1 批量第 1 批：剩下 21 条逐帧满配（2026-09-29 08:50 MDT，09:25 按审查修改）

- 分支 `track2/p1-training`；时间一律丹佛时间（服务器日志是北京时间，早 14 小时）。
- 用户 08:45 选“并行”：两张卡用原配方跑剩下的 21 条，T1 / T4 诊断同时做（另写计划，不占训练 GPU）。
- 顺序：本计划 → 独立审查（GO WITH FIXES，无 BLOCKER）→ 按审查修改（见文末）→ 登记提交 → 执行。

## 为什么跑、为什么分两段

每次提交要全部 30 条 episode（`results/submission/kit_facts.txt`）；目前有逐帧 policy 的是 9 条（ep20、26、13、10、4、2、21、27、3）。
剩下 21 条用原配方逐帧跑完，就能交第一次，也是以后改进的基线。

分 A、B 两段、每段训完就评：A 段的分数能提前约半天出来，有系统性问题可以在 B 之前停。B 段的队列现在就生成、和 A 一起同步，
服务器上的等待包装在 A 评完后自动开 B，不依赖 Mac，也不留同步窗口。两段期间两台都不同步；评测环境升级到 aee95f2 与 T1 / T4 诊断
按各自计划另做：需要服务器 GPU 的放到 B 段之后，T1 / T4 的 CPU 分析在 Mac 上用只读拉回的数据做。

## 事实

1. 剩下 21 条（序列、源帧数、支撑面取自 `results/batch_summary_v040.tsv`、`results/day2/sequence_stats_tier1.txt`、
   `results/day2/empty_support_tier1.txt`），12 条只有地面。
2. 两条特殊的：ep1 vacuum_left_lean_02 有支撑面，重定向对齐检查 ALIGN：物体最低点低于地面 22.5 mm（surface=floor），静置帧可能带约 2 cm 的系统误差；
   ep29 rolling_luggage_left_foot_push_06 只有地面，左右手接触帧都是 0（左脚推），抓握奖励恒为 0，预期训不好。两条都建场景成功
   （`results/day2/palm_frame_probe_all.txt`），不做特殊处理，提交要它们的轨迹，照训。
3. ep11 源帧 901，官方样例 CSV 里 e000011 只有 900 帧（一帧物体不可见被丢掉）；打包器只查缺行，多一帧不影响，src_frames 保持 901
   （改成 900 会让链的帧数核对把它 SKIP）。
4. 产能与显存：ml40 1000 万一条 2 h 09 m – 2 h 16 m，整卡 40.2–40.3 GB；mf4090 400 万一条 2 h 03 m – 2 h 13 m，整卡 23.8 GB；
   冒烟加 256 世界 rollout 每条约 5 分钟。4096 世界评测每次：ml40 约 5.5–6.6 分钟（`results/ml40/day2/eval_*` 的 run_at 间隔），mf4090 约 5 分钟。
5. 质量参考（逐帧、最终 checkpoint）：新序列 8 条里 2 条过 Day 1 判据（ep26 ml40、ep27 mf4090）；mf4090 400 万与 ml40 1000 万在 ep20 上相近
   （`results/day2/batch_verdict_*.txt`）。
6. 磁盘：mf4090 09:06 剩 15 GB；一条正式约 0.5 GB（只留 2 份 state），一条冒烟约 0.33 GB，A、B 两段合计约 8.8 GB。ml40 在 `/lab_data`，空间充足。
7. 镜像（09:06 查）：ml40 `flash_chord:latest` 为 `96c808f9…`、mf4090 为 `6f423d57…`，各自等于最近一条同机 run 的 run_record，
   指纹 `e2934912858820b8 / df0cf35711a68fb3` 与链里写死的一致。两台都没有 `runs/.chain-active-*`，GPU 空。

## 设计

- 分机器：21 条按 episode 序号排序，交替分配（ml40 先）；A 段取每台前 5 条；B 段其余，为两台时长平衡，ml40 的最后一条 ep29 改到 mf4090：
  - A：ml40 ep0、5、7、9、12；mf4090 ep1、6、8、11、14
  - B：ml40 ep15、17、19、23、25；mf4090 ep16、18、22、24、28、29
- 配方：官方 G1 FlashSAC，逐帧回放（不加回放或容差覆盖），2048 世界、349,999,104 步、种子 42；ml40 默认 1000 万 buffer（不写覆盖），
  mf4090 `training.replay.capacity=4000000`；只有地面的加 `scene.support=false`。
- 队列：`stages/policy/queues/{ml40,mf4090}_batch1{a,b}{.expect.tsv,_smoke.txt,.txt}`，由 `stages/policy/make_batch_queue.py` 生成（格式同今晚）：
  冒烟 `V2D_WANDB_PROJECT=v2d-selftest V2D_WANDB_TAG=smoke`，正式 `V2D_WANDB_TAG=batch`，都带 `V2D_MAX_RETRY=0 V2D_GPU_APPS=1 V2D_WANDB_UPLOAD_CKPT=0`。
- 执行链：原样复用 `stages/policy/day2_train_chain.sh` 与 `stages/evaluate/day2_eval_chain.sh`（Day 2 与今晚已跑通 12 条，脚本自 f540d48 / 224dcce 未改）。
  冒烟显存上限：**ml40 44000**（Day 1 起登记的值，实测峰值 40.3 GB），**mf4090 24564**（只按 OOM 字样判）。评测每条最后 3 个 checkpoint、
  匹配回放、4096 世界，不做换回放评测。
- 评测环境升级（另有计划）不得改动训练用的 `third_party/video_to_data` 与 `flash_chord:latest`：放在仓外或另一目录、另打标签；
  开下一批训练前核对 upstream、镜像 ID、指纹都等于本批的 run_record；在 mf4090 上建镜像前先看磁盘。

## 判据（事先登记，同今晚）

- **能进批量**：冒烟全过（`smoke_check.sh` 各项、rollout 帧数 = 源帧数）；正式训练一段跑完、日志无 RESOURCE_EXHAUSTED / exceeds the base limit；
  3 个 checkpoint 的评测都成功，step_count = 源帧数，`non_finite_worlds` 都为空。满足的，最终 checkpoint `policy_349999104` 作为这条 episode
  当前的候选提交 policy（aee95f2 评测器实测后确认）；不从三个 checkpoint 里挑。
- **质量（只报数，看最终 checkpoint）**：Day 1 判据（chord_sr > 0、maniptrans_sr > 0、ADD-AUC > 这条序列逐帧的不动基线），边缘同 Day 1；
  另报 SP-SR、MPPE 与走势。判定用 `stages/evaluate/batch_verdict.py`。
- **失败处理**：冒烟不过 → 该条 SKIPPED，其余照跑；XLA 显存错误（`fc_run` 退出码 4）→ 该机器这段剩下的 run 全部停（形状相同），记“无结果”；
  其他失败 → 记录，继续下一条。都不人工续训。要重排的失败条目，先把旧的 `runs/flash_chord/<run>` 目录移走或换 run 名
  （留着 state 没有 DONE 的目录会被链直接 SKIP），放进下一批。

## 时间（按实测速度估计）

- A 段约 09:35 开跑：mf4090 约 20:30 训完、21:45 评完；ml40 约 21:00 训完、22:35 评完。
- B 段各自在 A 评完后自动开跑：mf4090 6 条约 11:40（9/30）训完、13:10 评完；ml40 5 条约 10:30 训完、12:05 评完。

## 执行步骤

1. 生成 A、B 两段队列；按审查改计划；提交（工作树干净）。
2. 确认两台都没有 `runs/.chain-active-*`；同步两台（先 `V2D_DRYRUN=1` 看清单；ml40 用 `V2D_ENV=ml40`；不需要强制）。
3. 两台各对 A、B 的冒烟与正式队列跑 `fc_config_check.sh`（`scripts/dev/record day2/cfgcheck_<队列名> stages/policy/fc_config_check.sh stages/policy/queues/<队列名>.txt`），
   意外差异必须为 0。
4. 开链前按链里的断言预跑两台全部 42 个展开配置（21 条 × 冒烟与正式）；镜像已在事实 7 核过。
5. 开链（逐字；每台四个 tmux）。ml40（`/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge`）：
   `tmux new-session -d -s v2d-b1a -c "$PWD" 'stages/policy/day2_train_chain.sh stages/policy/queues/ml40_batch1a.expect.tsv stages/policy/queues/ml40_batch1a_smoke.txt stages/policy/queues/ml40_batch1a.txt 44000 batch1a_train_ml40'`
   `tmux new-session -d -s v2d-b1a-eval -c "$PWD" 'V2D_WAIT_FOR_LOG=runs/logs/batch1a_train_ml40.log stages/evaluate/day2_eval_chain.sh stages/policy/queues/ml40_batch1a.expect.tsv - batch1a_eval_ml40'`
   `tmux new-session -d -s v2d-b1b -c "$PWD" 'until tail -1 runs/logs/batch1a_eval_ml40.log 2>/dev/null | grep -qE "DAY2_EVAL_(DONE|FAILED)"; do sleep 60; done; stages/policy/day2_train_chain.sh stages/policy/queues/ml40_batch1b.expect.tsv stages/policy/queues/ml40_batch1b_smoke.txt stages/policy/queues/ml40_batch1b.txt 44000 batch1b_train_ml40'`
   `tmux new-session -d -s v2d-b1b-eval -c "$PWD" 'V2D_WAIT_FOR_LOG=runs/logs/batch1b_train_ml40.log stages/evaluate/day2_eval_chain.sh stages/policy/queues/ml40_batch1b.expect.tsv - batch1b_eval_ml40'`
   mf4090（`~/v2d/maniphys_lab_v2d_challenge`）：同上四条，把 `ml40` 换成 `mf4090`、上限 `44000` 换成 **`24564`**：
   `tmux new-session -d -s v2d-b1a -c "$PWD" 'stages/policy/day2_train_chain.sh stages/policy/queues/mf4090_batch1a.expect.tsv stages/policy/queues/mf4090_batch1a_smoke.txt stages/policy/queues/mf4090_batch1a.txt 24564 batch1a_train_mf4090'`
   `tmux new-session -d -s v2d-b1a-eval -c "$PWD" 'V2D_WAIT_FOR_LOG=runs/logs/batch1a_train_mf4090.log stages/evaluate/day2_eval_chain.sh stages/policy/queues/mf4090_batch1a.expect.tsv - batch1a_eval_mf4090'`
   `tmux new-session -d -s v2d-b1b -c "$PWD" 'until tail -1 runs/logs/batch1a_eval_mf4090.log 2>/dev/null | grep -qE "DAY2_EVAL_(DONE|FAILED)"; do sleep 60; done; stages/policy/day2_train_chain.sh stages/policy/queues/mf4090_batch1b.expect.tsv stages/policy/queues/mf4090_batch1b_smoke.txt stages/policy/queues/mf4090_batch1b.txt 24564 batch1b_train_mf4090'`
   `tmux new-session -d -s v2d-b1b-eval -c "$PWD" 'V2D_WAIT_FOR_LOG=runs/logs/batch1b_train_mf4090.log stages/evaluate/day2_eval_chain.sh stages/policy/queues/mf4090_batch1b.expect.tsv - batch1b_eval_mf4090'`
6. 确认两台 A 段训练链开头的正向核对通过、**第一条冒烟 SMOKE_OK**、A 评测链与 B 包装都在等；之后只做短查询。
7. A 段评完（约 22:35）：`scripts/dev/pull-results` 与 `V2D_ENV=ml40 scripts/dev/pull-results`；两台各
   `scripts/dev/record day2/batch_verdict_<机器>_batch1a python3 stages/evaluate/batch_verdict.py stages/policy/queues/<机器>_batch1a.expect.tsv <结果目录>`；
   确认 B 段已自动开跑、第一条冒烟 SMOKE_OK；写执行记录；jev 核对承重结论。B 段评完同样收尾。

## 不做的事

- 不改配方、不调超参、不换种子；不人工续训或降档。
- A、B 两段期间不同步两台（评测升级、T1 / T4 的代码只提交，不上服务器）。
- 不用这批结果去改 Day 2 的判定。

## 审查与处理（09-29 09:20，独立审查：GO WITH FIXES，无 BLOCKER）

- 评测升级会碰训练运行时（构建与训练共用 `third_party/video_to_data` 和 `flash_chord:latest`）→ 设计里写明升级另放目录、另打标签，
  下一批开跑前核对 upstream、镜像 ID、指纹；mf4090 建镜像前看磁盘；磁盘数改为 09:06 的 15 GB。
- B 段依赖 Mac 在窗口里同步 → B 段队列现在生成、随 A 一起同步，服务器上的等待包装在 A 评完后自动开 B，不再留同步窗口。
- 开链命令是模板、ml40 误填 24564 会让冒烟全 SKIP → 第 5 步 8 条命令逐字写出；第 6 步加“第一条冒烟 SMOKE_OK”。
- ml40 评测每次约 5.5–6.6 分钟（不是 2.5）→ 时间重算；B 段为两台平衡时长，ml40 的 ep29 改到 mf4090。
- ep11 源帧 901 而样例 CSV 900 帧 → 记入事实 3，不改 src_frames。
- 失败条目重排要先移走旧目录 → 写入失败处理。
- 收尾步骤 → 写入第 7 步。
- ep1 的 −22.5 mm 是物体穿进地面的深度，与椅背无关 → 事实 2 改正。
- 审查核对无误的：A 段 10 行的序列、源帧、支撑面、buffer、步数、环境变量、命名（与生成器重跑逐字节相同）；21 条恰为 30 条减已做 9 条、
  两台两段不重不漏；链脚本未改。
