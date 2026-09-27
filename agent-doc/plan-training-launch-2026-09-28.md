# 方案：ml40 构建镜像 + 两台机器接 W&B 开训（支持断点续训）

- 日期：2026-09-27（MDT）＝ 9/28 凌晨（北京时间）
- 分支：`track2/p1-training`，HEAD `246a876`
- 状态：**待审** → 审后执行

## 已核实的事实

| 事实 | 依据 |
|---|---|
| FlashCHORD 支持续训：`training.resume=true training.checkpoint_path=<state_N.safetensors>`，恢复 learner 的环境步数、优化器、奖励归一化，课程阶段按步数接上；replay 不恢复（`save_replay=false`），续训后重新攒到 409,600 条才更新 | `training/flash_sac/runner.py:465-485`，`configs/training/reference_flash_sac.yaml` |
| 续训要求 `(总步数 − 已完成步数) % world_count == 0`；G1 配方每 10,000,384 步（= 2048×4883）存一对 `policy_N` / `state_N` | runner.py:488-490，`experiment/g1_recon_body_flash_sac.yaml` |
| W&B：`logging.mode` ∈ online/offline/disabled，`logging.entity/project/experiment(=group)/run_name`，`upload_checkpoints=true` 只传 policy（4.9 MB），`upload_training_state=false`；wandb 目录写在 `output_dir` 下 | `configs/logging/wandb.yaml`，`scripts/train_flash_sac.py:89-98`，runner.py:170-225 |
| `wandb.init` 没传 id/resume，可用环境变量 `WANDB_RUN_ID` + `WANDB_RESUME=allow` 让续训写同一条曲线 | runner.py:187 |
| 镜像里 wandb 0.22.2；你的 key 验证通过，账号 `zhou-rongx`，默认 entity `zhou-rongx-northeastern-university` | 在 mf4090 镜像里实测 |
| 两台机器直连 `api.wandb.ai`、`storage.googleapis.com`（W&B 文件上传）都通 | curl 实测 |
| `fc_train.sh` 写死了 `logging.mode=disabled`；`in-flash-chord` 不转发任何宿主机环境变量 | 源码 |
| ml40 构建所需：apt（Ubuntu、NVIDIA）、GitHub、PyPI 都通；**ghcr 镜像层下载只有约 32 KB/s**（uv 镜像最大层 25 MB，约 13 分钟）；CUDA base 走腾讯镜像站（56 MB/s） | curl 实测 |
| ml40：GPU 空闲，系统盘剩 45 GB，rxzhou 在 docker 组；无 sudo | 实测 |
| mf4090：GPU 空闲，盘剩 22 GB，flash_chord 镜像在 | 实测 |
| 两台都有 tmux 3.2a | 实测 |
| 官方对照样例 parquet：`/v2d/assets/human_motion_data/whole_body/soma/sequence_id=2026-03-06_10-24-18_snack_box_pick_and_place_01/robot_name=g1/data.parquet` | FlashCHORD README |

## 方案

### 1. 代码改动（Mac 上改 → 提交 → push → 同步两台）

1. `scripts/dev/in-flash-chord`：按**变量名**转发一组白名单环境变量（只在宿主机上已设置时转发）：
   `WANDB_API_KEY WANDB_RUN_ID WANDB_RESUME WANDB_MODE XLA_PYTHON_CLIENT_PREALLOCATE XLA_CLIENT_MEM_FRACTION TF_CPP_MIN_LOG_LEVEL`；
   加 `V2D_CONTAINER_NAME` → `--name`，便于 `docker stop`。值不进 argv。
2. `stages/policy/fc_train.sh`：参数里没有 `logging.mode=` 时才补 `logging.mode=disabled`（现在是写死的，和 W&B 覆盖冲突）。
3. 新增 `stages/policy/fc_run.sh <run> <parquet> <world_count> <total_steps> [hydra 覆盖...]`（宿主机上执行）：
   - 校验 run 名 `[a-z0-9_-]`、步数整除 world_count；
   - 输出 `runs/flash_chord/<run>/`，日志追加到 `runs/logs/<run>.log`，GPU 采样 `runs/logs/<run>.gpu`（2 s；冒烟用 200 ms），采样进程随训练结束一起结束（记 PID，不用 pgrep）；
   - **续训**：目录里有 `state_*.safetensors` 就取步数最大的，加 `training.resume=true training.checkpoint_path=…`；
   - **W&B**：`WANDB_RUN_ID=<run>`、`WANDB_RESUME=allow`，覆盖 `logging.mode=online logging.entity=zhou-rongx-northeastern-university logging.project=v2d-track2 logging.experiment=<group> logging.run_name=<run>`；`V2D_WANDB=0` 可关；
   - 第一次启动写运行记录 `run.json`：源码 commit（由 `remote` 同步时写入 `.v2d-source-commit`）、上游 33129dd、镜像 ID、主机、GPU、驱动、parquet sha256、全部覆盖参数、开始时间；每次续训追加一条；
   - **自动重试**：非零退出时最多重试 2 次（每次从最新 checkpoint 续）；日志里出现 OOM / `RESOURCE_EXHAUSTED` / `exceeds the base limit` 直接停，不重试；
   - 正常结束：写 `DONE` 标记；`state_*` 只留最后 2 份，`policy_*` 全留。
4. 新增 `stages/policy/fc_queue.sh <队列文件>`：逐行执行 `fc_run.sh`，已有 `DONE` 的跳过；在 tmux 里跑，**机器重启或中断后重跑同一条命令即从断点继续**。
5. `scripts/dev/remote`：同步后在远端写 `.v2d-source-commit`（`git describe --always --dirty`）。

### 2. ml40：构建镜像（tmux 会话 `build`）

1. `docker pull nvidia/cuda:13.0.2-devel-ubuntu24.04`（镜像站）与 `docker pull ghcr.io/astral-sh/uv:0.11.21`（慢，约 15 分钟）先拉到本地，避免 BuildKit 构建中途慢拉。
2. `V2D_BUILD_DIRECT=1 scripts/dev/build-flash-chord > runs/logs/build_flash_chord_ml40.log`（不读 .env、不传代理）。
3. 验收：前 11 层 diff_id 与 mf4090 相同；两边容器内依赖清单（`importlib.metadata` 列表）diff 为空；记下镜像 ID；系统盘剩余 ≥ 15 GB。

### 3. W&B 端到端小测（mf4090，约 1 分钟，不占 GPU）

容器里起一个 `v2d-track2/wandb-selftest` 运行：记几步指标、上传一个小 artifact、`finish()`，确认在网页上能看到，再用同一 run id 续一次，确认续到同一条。通过后删掉这个测试运行。

### 4. 训练队列

| 机器 | 顺序 | run | 数据 | 配置 | 预计 |
|---|---|---|---|---|---|
| mf4090 | 1 | `t1-ep20-w2048-cap1m-mf4090` | Tier 1 ep20 rice_cooker | 349,999,104 步，`training.replay.capacity=1000000` | ≈ 2 h |
| mf4090 | 2 | `ctrl-snackbox-w2048-cap1m-mf4090` | 官方 snack_box 样例 | 同上 | ≈ 2 h |
| ml40 | 1 | `smoke-t1-ep20-w2048-cap10m-ml40` | Tier 1 ep20 | 4,096,000 步，默认 10M，GPU 200 ms 采样，`TF_CPP_MIN_LOG_LEVEL=0` | ≈ 10 min |
| ml40 | 2 | `t1-ep20-w2048-cap10m-ml40` | Tier 1 ep20 | 349,999,104 步，10M（冒烟判为边缘则 8M） | 未测，估 2–3 h |

- ~~续训实测（旧判据：同一个 W&B run id 曲线连续）~~ —— 审查后实现改为每段独立 id，判据在看结果**之前**（2026-09-28 02:09 CST）改为：
  **续训实测**（独立的 `resumetest-t1-ep20-cap1m-mf4090`，20,000,768 步，W&B project `v2d-selftest`）：第一个 checkpoint 之后让训练进程意外退出，通过条件：
  1. fc_run 自动重试，第 2 段命令带 `training.resume=true` 且指向 `state_10000384`；
  2. 第 2 段日志的进度从 10,000,384 起算；
  3. 结束时 DONE、`policy_20000768` 存在、日志有 `completed 20000768 environment steps`；
  4. W&B group `resumetest-t1-ep20-cap1m-mf4090` 里有 `-s1`、`-s2` 两个 run，`-s2` 的第一个 `_step` > 10,000,384，`-s1` 的最后一个 `_step` ≤ 中断点；
  5. 结束后无残留容器、锁已释放、state ≤ 2 份。
- **冒烟判据**（沿用 SOP，事先定好）：exit 0；有 `compiled FlashSAC JAX executables`；过 409,600 步；无 OOM / base limit；整卡峰值 > 44,000 MiB 则正式跑用 8M。冒烟由我看结果后再启动 ml40 第 2 条（不自动接）。
- W&B 分组：`smoke`、`tier1`、`control`。

### 5. 不做的事

- 不碰 docker 存储迁移、不建 `/lab_data/rxzhou`（没有 ml40 的 sudo）；
- 不在 ml40 以外的位置存凭据；W&B key 只在 600 权限的 `.env` 与容器环境变量里；
- 不开 Tier 2 批量（等 Day 1 结论）。

## 风险

- `docker inspect` 能看到容器环境变量，两台机器 docker 组的人（各 4 人）能看到 W&B key。docker 组本身等同 root，风险可接受，事后可在 W&B 轮换 key。
- ghcr 很慢，uv 镜像拉取可能超过 15 分钟；BuildKit 若不用本地镜像而重新拉，会再慢一次（不影响结果）。
- ml40 系统盘：镜像 22 GB + 一次全程 5.8 GB，剩约 17 GB；批量训练前必须迁移存储。
- 10M 在 L40S 上的整卡余量未证明，靠冒烟判定。
- 共享机器：两台都会连续占 GPU 数小时，需要在群里告知。
