# stages/retarget

读人体与物体轨迹，产出 G1 + Dex3 上的参考运动。

官方 toolkit 的 `robotic_grounding/` 已有这条链（SOMA → G1 重定向、由 Dex3 末端路径做
全身规划），这一段优先包住官方实现，只在需要时替换其中某一步。依赖 Isaac 的部分在
容器里跑（见 [`deploy/`](../../deploy/)）。

尚无代码。契约见 [`docs/contracts/retarget.md`](../../docs/contracts/retarget.md)。
