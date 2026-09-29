# 交接：ml40（L40S）上开 FlashCHORD 训练

- 最近更新：2026-09-28 17:05 MDT；分支 `track2/p1-training`（已 push）
- 时区：服务器日志是北京时间，比 Mac（MDT）早 14 小时；对用户一律报丹佛时间

## 当前状态（本节取代下文“未完成 / 阻塞”“下一步”“兜底”三节，那几节只作 9/26 的历史）

已完成：
- ml40 上 flash_chord 镜像在系统盘重建：前 11 层 diff_id 与 104 个依赖和 mf4090 一致，ID `sha256:96c808f9…`。
- Day 1：两条 ep20 全程与 snack_box（100 万 buffer）都一次跑完。评测、判定与 jev 见 `agent-doc/experiments/2026-09-28-day1.md`，
  其中每个数都由 `scripts/experiments/2026-09-28-day1.sh` 重新生成。结论：ep20 两条都没过（ADD-AUC 低于物体完全不动）。
- docker / containerd 存储迁到 `/lab_data`：2026-09-27 15:48 MDT，`deploy/ml40/migrate_docker_storage.sh --apply --reuse-copy`，
  停机约 15 s。第一次尝试在拷完、docker 已在新位置起来后自动回滚，原因是验收检查只认双引号，而 containerd v2.3.5 的
  `config dump` 写的是 `root = '…'`；已修，重跑复用第一次的副本。
- 仓库副本搬到 `/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge`（`deploy/ml40/move_repo.sh`，校验和零差异），Mac 的 `.env.ml40`
  已改到新路径。复核、搬迁与测试由 `deploy/ml40/post_migration.sh` 在 ml40 上后台完成，日志
  `/lab_data/rxzhou/ops/post-migration-20260928-054829.log`，最后一行 `POST_MIGRATION_DONE`。
- 系统盘清理（用户确认后，18:21 MDT）：`migrate_docker_storage.sh --cleanup` 删了 `/var/lib/{containerd,docker}.pre-migration`（72 GB），
  `move_repo.sh --cleanup` 删了仓库旧副本（14 GB）；两者先跑 `cleanup-check`，删前把检查再跑一遍（没有进程或挂载在用、镜像清单与验收时一致、
  旧副本的每个文件新副本都有）。系统盘 85% → 25%；`~/v2d` 下其他文件、8 个镜像（含 4 个 `v2d_*`）、Warp 缓存都在。
- snack_box（100 万 buffer）评测不通过：chord_sr 0、ADD-AUC 0.540 低于它的不动基线 0.566（`results/day1/verdict_snackbox.txt`）。
- Day 1b 逐帧诊断（mf4090）：三个 policy 的有效性闸全过；T1、T2、T4 触发，T3 没触发。数字、解读与限定见
  `agent-doc/experiments/2026-09-28-day1b.md`，触发判定 `results/day1/diag_triggers.txt`。
- 满配 snack_box 对照第 1 次（`ctrl-snackbox-w2048-cap10m-ml40`）：冒烟通过（SMOKE_OK），正式训练 19:56 MDT 开始，20:02 在第一个
  checkpoint 上传 W&B artifact 时因 token 核验连不上服务器退出。目录与 W&B run 原样保留，不续训。

| 东西 | 位置 |
|---|---|
| ml40 仓库副本 | `/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge`（系统盘上的旧副本已删） |
| docker / containerd | `/lab_data/docker`、`/lab_data/containerd`（系统盘上的旧数据已删） |
| 运维日志 | `/lab_data/rxzhou/ops/`（rxzhou 不用 sudo 可读） |
| sudo 密码 | Mac 会话 scratchpad 里的 `.sudo_ml40`（0600），只经 stdin 交给 `sudo -S`；用户说用完不必删 |

验证（命令 → 结果）：
- `ssh ml40 'docker info --format "{{.DockerRootDir}}"'` → `/lab_data/docker`
- `results/ml40/ops/eval_compare_w64_vs_w256_after_migration.txt` → `CONSISTENT`（新存储上 64 世界与迁移前 256 世界 ADD-AUC 差 0.00015）
- `results/ml40/ops/test_fc_wrappers_after_move.txt` → 62 通过、0 失败
- `V2D_ENV=ml40 V2D_DRYRUN=1 scripts/dev/remote` → 只列本地改动；`.v2d-source-commit` 已加保护规则，不再被 `--delete` 删掉

- 满配 snack_box 对照第 2 次：不通过（边缘），见 `agent-doc/experiments/2026-09-28-day1b.md`。
- 回放速度对照（T2）：预算内没有差别，见 `agent-doc/experiments/2026-09-28-playback.md`。官方评测按什么速度回放没有公开，
  `eval_robotic_grounding.py` 在 HF 与 GitHub 都没有发布（`results/playback/find_eval_script*.txt`）。

未完成（09-28 22:45 MDT）：
1. Day 2（计划 `agent-doc/plan-day2-2026-09-28.md` 第 2 版，登记于 67f1d86；执行记录 `agent-doc/experiments/2026-09-28-day2.md`）：
   - ml40：tmux `v2d-day2` 预检已完成，接着跑训练链（日志 `runs/logs/day2_train_ml40.log`：6 条冒烟，再 6 条满配）；
     tmux `v2d-day2-eval` 等训练链结束再评测（`runs/logs/day2_eval_ml40.log`）。
   - mf4090：第一次开链因显存上限参数与计划不一致，三条冒烟全被跳过（见执行记录的“执行偏差”）；16:58 MDT 用整卡总量作上限重开：
     tmux `v2d-day2-r2`（`runs/logs/day2_train_mf4090_r2.log`）与 `v2d-day2-r2-eval`（`runs/logs/day2_eval_mf4090_r2.log`）。
   - 链在跑时服务器上有 `runs/.chain-active-*`，`scripts/dev/remote` 拒绝同步；只读检查用普通 ssh。
   - 9/28 23:05 用户选 B（按“固定逐帧”处理，见执行记录）：23:08 强制同步 ml40（来历 f540d48），原训练链在 ep13 逐帧完成后按来历核对停下，
     ep13、ep10 的真实时长不再开跑；原评测链评 ep26 两条与 ep13 逐帧。之后 tmux `v2d-day2b` 的等待包装在原评测链结束后开
     `day2b_train_ml40`（ep10、ep4、ep2 逐帧满配），tmux `v2d-day2b-eval` 随后评测（`runs/logs/day2b_eval_ml40.log`）。
     **这些链结束前不要再同步 ml40**：评测链在等待结束后才记来历，中途同步会让它们停下。
   - mf4090：B 的三条已评完（真实时长两颗种子都没训起来；逐帧与 ml40 满配相近，只作描述）。9/29 00:24 按
     `agent-doc/plan-mf4090-night-2026-09-29.md` 开今晚 3 条逐帧满配（ep21、ep27、ep3，400 万 buffer）：tmux `v2d-night1`
     （`runs/logs/night1_train_mf4090.log`）与 `v2d-night1-eval`（`runs/logs/night1_eval_mf4090.log`），执行记录
     `agent-doc/experiments/2026-09-29-mf4090-night1.md`。预计 07:10 训完、07:55 评完。
   - 9/29 08:30 Day 2、Day 2b、night1 都已评完，结果与登记的判定见两份执行记录（逐帧新序列 8 条里 ep26、ep27 过 Day 1 判据）。
   - 9/29 09:29 起 Tier 1 批量第 1 批（剩下 21 条逐帧满配，计划 `agent-doc/plan-batch1-tier1-2026-09-29.md`，执行记录
     `agent-doc/experiments/2026-09-29-batch1.md`）：每台 tmux `v2d-b1a`、`v2d-b1a-eval`、`v2d-b1b`、`v2d-b1b-eval`，A 段评完后 B 段自动开跑。
     预计 A 段 mf4090 21:45、ml40 22:35 评完；B 段 ml40 约 9/30 12:05、mf4090 约 13:10 评完。**两段结束前不要同步两台。**
   - 四条链最后一行分别是 DAY2_TRAIN_DONE / DAY2_EVAL_DONE（或 …_FAILED）。都结束后：`scripts/dev/pull-results` 与
     `V2D_ENV=ml40 scripts/dev/pull-results`，再 `scripts/dev/record day2/compare python3 stages/evaluate/day2_compare.py stages/evaluate/day2_spec.json`，
     jev 核对承重结论，填执行记录。
2. 官方 submission kit（9/28 邮件，19:46 MDT 发布）：已下载到 `third_party/v2d_submission_kit/`（不进 git），事实见
   `results/submission/kit_facts.txt`（jev 8 条核实）。要点：评测按 checkpoint 自己的配置、1 个世界、确定性动作；导出轨迹帧号 = 步数，
   按 30 fps 参考逐帧计分；每次提交要全部 30 条 episode；评测要用上游 main aee95f2 的 FlashCHORD 运行时（v0.4.0 没有轨迹导出）。
   推断（未核实）：真实时长训练的 policy 会被错位计分，只有逐帧对齐。Day 2 照跑（用户未答复前的默认），是否取消剩下的真实时长臂待用户定。
   待办：评测环境升级到 aee95f2 并实测对齐（先写计划、review）；Kaggle 接受规则与凭据（用户）；每次提交要用户点头。
3. 问组委会：邮件草稿 `agent-doc/organizer-email-draft-2026-09-28.md`（9/28 22:40 按 kit 改写）与 Discord 草稿
   `agent-doc/organizer-discord-draft-2026-09-28.md`，都等实测对齐后由用户发出。
4. 其余：T4 查重定向、T1 查接近与抓取（都先写计划、review 再跑）；snack 满配的逐帧诊断；按 Day 2 判定写 Tier 1 批量训练计划
   （16 条只有地面的序列要 `scene.support=false`）。
5. Mac 会话 scratchpad 里约 390 个旧文件分拣：可复现的脚本与证据进仓库，涉及队友的内容不进 git。
6. 轮换 sudo 密码：在对话里出现过多次，而且同一密码在 mf4090 上也能用。

工作方式（用户要求）：长时间运行或需要等待的活放服务器后台（tmux / `setsid nohup … < /dev/null &`），自己写日志、最后一行写结论；
Mac 只发短命令，用户会断网。分析与诊断脚本一律进仓库，经 `scripts/dev/record` 落到 `results/`。

---

以下为 2026-09-26（MDT）的原始交接，保留作历史。

## 目标

周二 9/29 在 ml40 的 L40S 上用 FlashCHORD 跑 G1 满配 recipe（2048 worlds、replay 10M、349,999,104 步），
Tier 1 ep20（rice_cooker）。之后按实测吞吐排 Tier 1 / Tier 2 批量。

## 已核实的事实（2026-09-27 03:38 北京时间，只读；jev 对照题 真 0.87 / 假 0.05）

| 事实 | 依据 | 核对 |
|---|---|---|
| ml40 系统盘剩 18,955,116,544 B；flash_chord 在 4090 上占 21.98 GB → 现在装不下 | `df -B1`、`docker system df -v` | 代码比较 |
| ml40 docker 用 containerd 镜像存储，镜像在 `/var/lib/containerd`；只改 data-root 搬不走 | `docker info` driver-type `io.containerd.snapshotter.v1`；Docker 文档 containerd 页 | jev 0.89 |
| 管理员迁移只建了 `/lab_data/docker-migration`，还没开始 | daemon.json 9/25 未变、docker 9/25 起未重启、`/lab_data` 已用四次读数均为 9,104,125,952 | jev 0.75 |
| 迁移后可在 ml40 重建：镜像站的 `nvidia/cuda:13.0.2-devel-ubuntu24.04` 11 个 diff_id 与 4090 镜像前 11 层逐一相同 | 经 ml40 的 registry-mirrors 查 config | 代码比较；jev 0.82 |
| 重建的镜像 ID 与 4090 不同 | apt 层、构建时间不同 | "字节相同" jev 0.19 |
| 经 Mac 中转太慢：4090→Mac 0.23 MB/s、Mac→ml40 1.20 MB/s（16 MiB 实测） | 本次实测 | 代码 |
| JAX 显存上限 = 0.75 ×（Total − Reserved）向上取整到 2 MiB；4090 报错 `base limit (18939379712)` 与之吻合（nvidia-smi 取整误差内）；L40S ≈ 34,094 MiB | XLA `gpu_helpers.cc`；4090 日志 | jev 0.92 |
| 10M 按账算能放下，但**未证明**；整卡余量未知 | 4090 采样 5–6 s 一次，有 6,671 MiB 瞬时点 | 估计 0.89 / 已证明 0.09 |
| 4090 稳态约 50.5k env steps/s（后半段回归），1M buffer 跑满长度约 1.9–2.2 h | `fc_smoke_w2048.log` | jev 0.97 |
| L40S 吞吐未测；"2.5 h/策略、Tier 1 三十条约 3 天"无依据 | — | jev 0.13 |
| ml40：28 核、111 GiB 内存、单卡 L40S | `nproc`、`free -g`（2026-09-27 04:23 北京时间） | 只读 |
| 训练输入两台机器逐字节一致（motion 360、motion_src 480、recovery 91、stages/libs/scripts 0 差异） | 两侧 sha256 清单 | 代码 |

## 本次已完成

- `docs/adr/00003-stage-handoff-and-runtime.md`：加多主机与 ml40 就地重建镜像的决定。
- `scripts/dev/_load-env`（新）：`.env` + `.env.<V2D_ENV>` 叠加；名字非法或文件缺失直接退出，不回落；目标打印到 stderr。
- `scripts/dev/remote`：改用 `_load-env`；`V2D_DRYRUN=1` 只列清单、不执行远端命令；显式放行 `.env.example`
  （rsync 不认 .gitignore 的 `!` 取反，干跑实测会删它）。
- `scripts/dev/init-remote`、`pull-results`：改用 `_load-env`；非默认主机回流到 `results/<主机>/`。
- `scripts/dev/pull-runs`（新）：只拉 `policy_*.safetensors`、小元数据与 `runs/logs` 文本，落到 `runs/<主机>/`。
- `scripts/dev/build-flash-chord`：`V2D_BUILD_DIRECT=1` 直连构建，不读 `.env`、不传代理。
- `.gitignore` 加 `.env.*` / `!.env.example`；`.env.example` 加 `V2D_ENV` 说明；Mac 上建 `.env.ml40`（600，不进 git、不上传）。
- 两台服务器已同步，Mac 侧哈希核对 `CODE_OK`（mf4090、ml40 各一次）。

验证（均已跑过）：

```bash
V2D_DRYRUN=1 scripts/dev/remote echo X          # 与改动前清单一致，不执行 echo
V2D_ENV=bogus scripts/dev/remote                # rc=1，报缺 .env.bogus
V2D_ENV='ml40;rm' scripts/dev/remote            # rc=1，报非法
V2D_ENV=ml40 V2D_DRYRUN=1 scripts/dev/remote    # 0 删除，不传 .env*
V2D_ENV=ml40 scripts/dev/pull-runs '../etc'     # rc=1
# build-flash-chord 用假 docker 截参数：直连模式无 --build-arg、无代理变量；默认模式 argv 不含凭据
```

## 未完成 / 阻塞

1. **管理员迁移 docker 存储（含 containerd root）**，并建 `/lab_data/v2d`（mfshared，2775）。需用户联系，消息草稿见对话。
2. **L40S 使用时段**与 ml40 其他用户约定。
3. **首次 commit**（建议分支 `track2/p1-training`）。周二的运行记录要能指回 commit。
4. **4090 基线**：Tier 1 ep20、1M buffer 全长（GPU 当前空闲，盘剩 20 GB）。占共享 GPU，需用户先知会队友。
5. 未核实：BuildKit 构建时 `FROM` 是否走 daemon 的 registry-mirrors；`TF_CPP_MIN_LOG_LEVEL=0` 能否打出 `XLA backend will use up to` 一行。

## 下一步（迁移完成后，按顺序）

1. 只读验收，重点看根分区，不能只看 `docker info`：
   `ssh ml40 'df -B1 / /lab_data; docker info --format "{{.DockerRootDir}} {{.Driver}} {{json .Runtimes}}"; docker image ls; test -w /lab_data/v2d && echo WRITABLE'`
   通过：`/` 可用从约 19 GB 涨到约 90 GB；Runtimes 含 nvidia；4 个 `v2d_*` 都在。
2. 重建：`ssh ml40 'cd ~/v2d/maniphys_lab_v2d_challenge && V2D_BUILD_DIRECT=1 scripts/dev/build-flash-chord > runs/logs/build_flash_chord_ml40.log 2>&1'`；
   核对前 11 层 diff_id 与 4090 相同，记录 Image ID。
3. 卡空闲确认：`nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader` 为空、`docker ps` 为空。
4. 10M smoke（不覆盖 capacity）：

   ```bash
   cd ~/v2d/maniphys_lab_v2d_challenge
   P='/repo/runs/motion/tier1/whole_body/soma/sequence_id=2026-06-08_16-57-34_rice_cooker_clockwise_04/robot_name=g1/data.parquet'
   timeout 1800 nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv,noheader -lms 200 > runs/logs/fc_smoke_ml40_cap10m.gpu &
   timeout 1800 nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader -lms 200 > runs/logs/fc_smoke_ml40_cap10m.apps &
   timeout 1700 env V2D_GPU=1 scripts/dev/in-flash-chord \
     "TF_CPP_MIN_LOG_LEVEL=0 bash /repo/stages/policy/fc_train.sh '$P' 2048 4096000 /repo/runs/flash_chord/smoke_ml40_t1_ep20_w2048_cap10m" \
     > runs/logs/fc_smoke_ml40_cap10m.log 2>&1; echo exit=$?
   pgrep -af '[n]vidia-smi --query'   # 应为空
   ```

   **事先定好的判据**：exit 0；日志有 `compiled FlashSAC JAX executables`，progress 超过 409,600；
   `grep -E 'exceeds the base limit|RESOURCE_EXHAUSTED|out of memory'` 无命中 → 通过。
   整卡峰值 > 44,000 MiB 或 OOM → 正式跑改 `training.replay.capacity=8000000`，记录里注明偏离 recipe；再不行 6M。
   同时记下：稳态 steps/s（后半段回归，不用累计均值）、`XLA backend will use up to` 行、onnxruntime 用的 provider。
5. 写运行记录 `agent-doc/experiments/2026-09-29-ml40-t1-ep20.md`：档位 Tier 1、parquet、commit、上游 v0.4.0 `33129dd`、
   镜像 ID 与 base diff_id、覆盖参数、seed 42、smoke 峰值与稳态吞吐。
6. 正式跑：同上命令，步数 `349999104`，输出 `/repo/runs/flash_chord/t1_ep20_w2048_cap10m_ml40`，tmux 里跑，
   nvidia-smi 采样用 `timeout 28800 ... -l 2`。结束后 `V2D_ENV=ml40 scripts/dev/pull-runs t1_ep20_w2048_cap10m_ml40`。

## 迁移没按时完成的兜底（待用户选）

- 4090 先顶上：1M buffer 继续跑 Tier 1。
- `/lab_data/v2d` 可写时，ml40 宿主机安装 FlashCHORD（venv、uv cache、runs 全放 `/lab_data/v2d`），ADR-00003 写临时例外。
  **不在 ml40 系统盘装 venv**：装完根分区约 97.5%，剩 3.9 GB，四个用户共用。
- 整体推迟。

## 不要做

- ~~迁移完成前，在 ml40 上 docker load / pull / build / run~~（2026-09-28 按 ADR-00003 修订：系统盘回升到 45 GB，改为先在系统盘构建；
  迁移要在两次训练之间的空窗做，批量训练前必须完成）。
- `ssh -A` 转发 agent 进 mf4090（多人共用，有 sudo 的人能借用）。
- 让 `.env`（含代理凭据）进 ml40 的构建环境。
