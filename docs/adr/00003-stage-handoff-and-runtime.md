# ADR-00003：环节间交接格式与运行方式

**Status:** Proposed
**Date:** 2026-09-25
**Deciders:** rxzhou；仓库维护者

## Context

CLAUDE.md 要求环节之间只经文件交接，下游不 import 上游代码；Isaac 相关部分在容器里跑。roadmap
的待写 ADR 里有三项在实现中已经有了事实上的做法，需要成文：toolkit 接入方式、Isaac 侧运行环境、
环节交接格式。

事实：

- 官方 `soma_to_g1` 需要 `soma_params.npz` + `poses.npy` + `reconstructed_mesh/output_aligned.glb` 的目录；
  输出 motion_v1 parquet，分区 `whole_body/soma/sequence_id=<seq>/robot_name=g1/`，support 从
  `whole_body/reconstructed_stage/<seq>[_g1]_support.usda` 查找，机器人专属文件优先。
- 官方 `read_soma` 不读 `bone_length_flexibles`；丢掉它关节整体偏 13.5 mm。
- v0.4.0 起 `soma_to_g1` 自带 `--fps`（默认 30）与地面找平；在此版本下挑战原版 support 与物体对齐（ep20 间隙 −1.3 mm）。
- 官方常驻容器只挂 `third_party/video_to_data`，看不到本仓 `stages/`、`libs/`、`runs/`。
- 训练机经代理用 git 访问 GitHub 被重置，git-lfs 可用。

## Decision

**交接格式**

| 边 | 产物 | 位置 |
|---|---|---|
| recovery → retarget | 每条序列一个 npz：`object_pose (T,7)`（OpenCV 系、全长、wxyz）、`visible`、`meta`（方法版本、参数、md5） | `runs/recovery/tier2_v5X/episode_*.npz` |
| retarget 输入 | 官方目录结构 + `v2d_meta.json`（档位、源帧率、物体位姿来源） | `runs/motion_src/tier{N}/<seq>/` |
| retarget → policy | 官方 motion_v1 parquet，按档位分开的 motion root | `runs/motion/tier{N}/whole_body/...` |
| policy → evaluate | FlashCHORD checkpoint（`policy_*.safetensors`）+ 评测 JSON | `runs/flash_chord/<run>/` |

每档一个独立的 motion root，不混档。

**toolkit 接入**：`third_party/video_to_data` 为固定 tag 的本地 checkout（当前 v0.4.0），源码不改。
行为改动一律在本仓包装：`stages/retarget/soma_flex.py`（注入 flex）、`run_soma_to_g1.py`（强制
`--save` 与 `--motion-root`，防止写进上游资产目录）。升级方式：Mac 上 `git bundle` 增量，训练机 fetch 后快进，
再 `git lfs pull`。

**运行方式**：一律用一次性容器（`--rm`），整仓挂 `/repo`，以宿主 uid 运行（加 isaac-sim 组）：
`scripts/dev/incontainer`（Isaac 镜像）、`scripts/dev/in-flash-chord`（FlashCHORD 镜像）。
GPU 默认不占，显式 `V2D_GPU=1` 才加。

**多台训练机**：mf4090（RTX 4090）与 ml40（L40S）用同一挂载布局（`/repo`）。`.env` 放共用变量与凭据，
`.env.<名字>` 只覆盖 `V2D_HOST` / `V2D_REMOTE`，由 `V2D_ENV=<名字>` 选择；名字写错直接报错，不回落到默认主机
（`remote` 带 `--delete`）。回流按主机分目录：`runs/<主机>/`、`results/<主机>/`，只拉 policy 与日志，不拉 state。

**ml40 的镜像就地重建**，不从 mf4090 搬：经 Mac 中转实测 0.23–1.2 MB/s，7.5 GB 要数小时；ml40 经腾讯镜像站拉到的
CUDA base 与 mf4090 上 `flash_chord:latest` 的前 11 层 diff_id 逐一相同，PyPI / ghcr 直连可达。构建走
`V2D_BUILD_DIRECT=1`（不读 `.env`、不传代理）。镜像 ID 与 4090 不同，运行记录写 base 层 diff_id 与依赖 freeze 以便对账。
ml40 的 docker 用 containerd 镜像存储，镜像层在 `/var/lib/containerd`，系统盘放不下；须等管理员把 containerd root
一并迁到 `/lab_data` 之后才能构建。

## Options Considered

### 交接格式

| 选项 | 评估 |
|---|---|
| A. 沿用 LeRobot v2.1，自定义扩展列 | 要改官方读取器或写适配层；官方重定向不认 |
| **B. 官方目录结构与 motion_v1 parquet，外加小的侧车文件（选定）** | 官方工具原样可用；来源与参数写在 `v2d_meta.json` 与 npz 的 meta 里 |

### 容器

| 选项 | 评估 |
|---|---|
| A. 官方 `run.sh` 常驻容器 | 看不到本仓代码与 `runs/`；改挂载要改官方脚本 |
| **B. 本仓一次性容器，整仓挂 `/repo`（选定）** | 不改官方脚本；产物路径统一；代价是每次启动几秒 |

### toolkit 接入

| 选项 | 评估 |
|---|---|
| A. git submodule | 训练机拉不到 GitHub，submodule 更新同样受阻 |
| **B. 固定 tag 的本地 checkout + bundle 升级（选定）** | 可在代理受限下升级；版本记录在本 ADR 与 `architecture-current.md` |

## Consequences

- 更容易：官方工具升级时，只需重跑包装层测试（`test_soma_flex.py`，v0.4.0 上 4 项通过）。
- 更难：parquet 里写死了 `/repo/...` 的网格绝对路径，换机器必须用相同的挂载布局（L40S 上也一样）。
- 要回看：上游若开始处理 flex 或改 `SOMA` 的引用方式，`soma_flex.py` 会主动报错，需要重看；
  `runs/` 每次运行必须落盘的元数据尚未成文（roadmap 候选，另写 ADR）。

## Action Items

1. [ ] `docs/contracts/retarget.md` 落条目：npz/parquet 的键、坐标系、帧数、flex 必须生效
2. [ ] 租用机器按同一挂载布局部署（`/repo`）；`scripts/dev/remote` 支持第二台主机（`V2D_ENV`，2026-09-26 已实现），
   ml40 镜像待存储迁移后重建
3. [ ] 另写 ADR：本地评测与官方评测的对账；`runs/` 元数据约定

## 变更记录

- 2026-09-25：初稿（Proposed）。
- 2026-09-26：加多主机（`V2D_ENV`）与 ml40 就地重建镜像的决定。
