# CLAUDE.md — maniphys_lab_v2d_challenge

> 本文件是 **Claude Code 与 Codex 共用的项目规范**。Claude Code 使用本入口；Codex
> 由仓根 [`AGENTS.md`](AGENTS.md) 指引完整读取本文件。共用规则只在这里维护一份。

maniphysAI lab 参加 NVIDIA [Video to Data (V2D) Challenge](https://nvidia-isaac.github.io/video_to_data/v2d_challenge/)
的工作仓，**只做 Track 2（Robotic Grounding）**：拿到不同质量的第三人称 4D 人-物交互
数据，在固定的 G1 + Dex3 与仿真器上训出机器人策略，按三个输入档位分别计分。

**动手前先读**：[`docs/goals.md`](docs/goals.md)（为什么做、怎么衡量）→
[`docs/roadmap.md`](docs/roadmap.md)（现在在哪一阶段、离榜单冻结还有多久）→
[`docs/architecture-current.md`](docs/architecture-current.md)（此刻代码长什么样）→
[`docs/contracts/`](docs/contracts/)（每个环节交付什么、怎么验证）。契约是权威依据，
实现服务于契约。

> 本仓处于 **P0 立仓**：只有目录骨架与文档，一行实现都还没有。各目录的 `README.md`
> 说明它将来放什么；架构决定尚未落成 ADR，候选清单在 roadmap。

## 仓库结构

```
libs/v2d_infra/      各环节共用层 —— 数据集读取（LeRobot v2.1）、档位与 episode 寻址、轨迹数据模型
stages/recovery/     Tier 2/3 的轨迹恢复 —— 从带噪轨迹或 exo 视频估出更好的人体 / 物体轨迹
stages/retarget/     人体运动 → G1 + Dex3 的重定向与全身规划
stages/policy/       Isaac Lab 里的策略训练与回放（容器内跑）
stages/evaluate/     官方评测脚本的封装、本地指标复算、提交物打包
third_party/         官方 starter toolkit（nvidia-isaac/video_to_data）的接入位
tools/               仓内门禁工具（契约审阅等）
deploy/              容器镜像与 GPU 机器的运行环境
scripts/             站在被测对象外面的门禁验证脚本
docs/                正式内容：目标、路线图、ADR、契约、运行手册
agent-doc/           调研、比较、实验记录与草稿，不作为事实来源
```

数据流按档位走同一条链：`recovery → retarget → policy → evaluate`。Tier 1 输入已是
干净轨迹，跳过 `recovery`；Tier 2 从带噪轨迹恢复；Tier 3 从 exo 视频重建。每一段
**只经文件交接**，下一段读上一段落盘的产物，不 import 上一段的代码。

## 挑战规则（硬约束）

以下几条出自赛事页面与数据集 README，违反任何一条都会让提交无效或分数失去意义。
原文与出处见 [`agent-doc/track2-challenge-survey.md`](agent-doc/track2-challenge-survey.md)。

- **档位隔离。** Tier 2 / Tier 3 的管线**不得读取 Tier 1 的干净轨迹**（赛事原文：
  "using anything other than the clean trajectory captions provided in Tier 1"）。
  这条要有机制守，不能只靠自觉：落地时它是 `data.md` 契约里的一条，由共用层的读取
  入口强制，测试证明跨档读取会被拒绝。
- **一次只以一个档位目录为数据集根**，不合并档位。三档的 episode 与全局帧号刻意对齐，
  用途是逐帧比较结果，而不是互相补数据。
- **单目输入是 `observation.images.exo_camera`**，它在各档之间逐字节相同。Tier 3 的
  重建只从它出发。
- **本体与仿真器固定**：G1 + Dex3，官方提供的仿真环境。不改机器人模型、不换仿真器。
- **三档分开计分，分数不可跨档比较。** 实验记录与结论一律标明档位。

## 分层与依赖方向

- **环节之间只经文件交接。** 原因是解释器版本：Isaac Lab 钉死自己的 Python 与依赖版本，
  非 Isaac 的包默认用 Python 3.14，两边无法共用一个环境。`stages/retarget` 与
  `stages/policy` 中凡依赖 Isaac 的部分在容器里跑，其余包用 uv。具体版本边界待
  ADR 定下后写回这里。
- **共用的东西只在 `libs/v2d_infra` 声明一次**：档位名、目录布局、轨迹与产物的 schema。
  两个环节各写一份读取逻辑，迟早会在帧号或坐标系上对不上。
- **官方代码不改源码。** 需要改动的行为包一层放在本仓，改动理由写在包装处；实在绕不开
  时以补丁文件形式放在 `third_party/`，注明上游版本。

## 工具链

- Python 统一 **uv**，lint / format 用 **ruff**，一切执行走 `uv run`。
- 值对象用 `pydantic.BaseModel`；Python 3.14 的包不写 `from __future__ import annotations`。
- 每个包自带可独立执行的 lint / test 入口；仓根 `Makefile` 尚未建立，建立后统一调度。
- GPU 组件一律容器化，镜像是唯一的运行单元（见 [`deploy/`](deploy/)）。

## 数据与产物

- **数据集、checkpoint、rollout 录像、提交物一律不进 git。** 本地放在 `data/`（数据集）
  与 `runs/`（训练与评测产物），两者都在 `.gitignore` 里。
- 进 git 的是**让结果可复现的东西**：配置、种子、上游版本、命令，以及实验结论
  （写在 `agent-doc/`）。
- 每次提交榜单都要能指回一次 `runs/` 下的运行与一份记录：档位、配置、上游 commit、
  本地复算的分数。每周提交次数有限（见 goals），浪费一次是真实成本。

## 改动的顺序

**ADR → contract → code → test → contract check。** 决定先落在 ADR 上，契约从决定推导，
实现服务于契约，测试守契约。每个测试在 docstring 里标注它守的契约 ID，指不回就删掉。
契约表格式见 [`docs/contracts/README.md`](docs/contracts/README.md)。

## 文档

- `docs/`：需要长期维护的正式内容。ADR 描述当下的决定，决定变了就改正文，末尾
  `## 变更记录` 留一行摘要。
- `agent-doc/`：调研记录、实验笔记、草稿。达成共识后整理迁入 `docs/`。
- 架构图一律用 mermaid。

## 安全

- Hugging Face token、赛事账号、云 GPU 凭据只经环境变量或 stdin 注入，不落命令行、
  不写进仓库与日志。

## 沟通

文档与注释以中文为主，英文术语保留原文。不确定的地方标出来，不用笃定的语气掩盖
没验证的推测。

## 跨 agent 上下文与交接

接手任务先看 `git status --short`、相关 diff 与近期提交。未完成任务的交接写到
`agent-doc/handoff-<主题>.md`：目标、已完成内容、涉及文件、验证命令与结果、未完成项、
下一步，注明日期、分支与 commit。
