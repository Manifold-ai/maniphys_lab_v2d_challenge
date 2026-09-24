# stages

管线的四段，每段一个独立的包，按档位走 `recovery → retarget → policy → evaluate`。

| 段 | 输入 | 输出 | 契约 |
|---|---|---|---|
| [`recovery/`](recovery/) | Tier 2 带噪轨迹 / Tier 3 exo 视频 | 恢复后的人体与物体轨迹 | [`recovery.md`](../docs/contracts/recovery.md) |
| [`retarget/`](retarget/) | 人体与物体轨迹 | G1 + Dex3 参考运动 | [`retarget.md`](../docs/contracts/retarget.md) |
| [`policy/`](policy/) | 参考运动 | 策略 checkpoint 与回放 | [`policy.md`](../docs/contracts/policy.md) |
| [`evaluate/`](evaluate/) | checkpoint 与回放 | 提交物、本地复算分数 | [`evaluate.md`](../docs/contracts/evaluate.md) |

段与段之间只经文件交接，不互相 import：Isaac 侧与非 Isaac 侧的 Python 环境无法共用，
经文件交接也让每一段可以单独重跑、单独换实现。
