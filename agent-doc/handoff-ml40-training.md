# 交接：ml40（L40S）上开 FlashCHORD 训练

- 日期：2026-09-26（MDT）＝ 2026-09-27 凌晨（北京时间）
- 分支：`main`，HEAD `4f160e3`；本文涉及的改动**尚未提交**（首次 commit 待用户批准）
- 时区：ml40 管理员在北京时间，比 Mac（MDT）早 14 小时

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

- 迁移完成前，在 ml40 上 docker load / pull / build / run（会写 `/var/lib/containerd`，系统盘放不下，也会干扰管理员拷贝）。
- `ssh -A` 转发 agent 进 mf4090（多人共用，有 sudo 的人能借用）。
- 让 `.env`（含代理凭据）进 ml40 的构建环境。
