# stages/policy

在 Isaac Lab 里训练跟随参考运动的策略，产出 checkpoint 与回放。

官方 toolkit 用 RSL-RL（PPO），注册了 `SonicG1-ReconBody-v0`、`SonicG1-ReconHand-v0`
等 G1 任务；哪一个对应 Track 2 的评测任务待核对。本体与仿真器是赛题固定项，不改。
整段在容器里跑。

训练产物（checkpoint、日志、回放）写到 `runs/`，不进 git。

尚无代码。契约见 [`docs/contracts/policy.md`](../../docs/contracts/policy.md)。
