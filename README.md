# maniphys_lab_v2d_challenge

maniphysAI lab 参加 NVIDIA [Video to Data (V2D) Challenge](https://nvidia-isaac.github.io/video_to_data/v2d_challenge/)
**Track 2: Robotic Grounding** 的工作仓：从不同质量的第三人称 4D 人-物交互数据出发，
在 G1 + Dex3 上训练机器人策略，回答赛题提出的问题「下游能容忍多大的重建误差」。

- 为什么做，怎么衡量 → [`docs/goals.md`](docs/goals.md)
- 现在做到哪、下一步做什么 → [`docs/roadmap.md`](docs/roadmap.md)
- 此刻代码长什么样 → [`docs/architecture-current.md`](docs/architecture-current.md)
- 每个环节交付什么、怎么验证 → [`docs/contracts/`](docs/contracts/)
- 仓库结构、开发规范与挑战规则 → [`CLAUDE.md`](CLAUDE.md)

## 使用 Claude Code 或 Codex 开发

两者共用 [`CLAUDE.md`](CLAUDE.md) 中的项目规范。Claude Code 读它本身；Codex 从仓根
[`AGENTS.md`](AGENTS.md) 进入，按指引完整读取。修改共用规则只改 `CLAUDE.md`。

## 当前状态

**P0 立仓**：只有目录骨架与文档，尚无实现。榜单冻结时间是 **2026-11-04 17:00 EST**。
