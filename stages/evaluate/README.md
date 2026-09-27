# stages/evaluate

- 调用官方评测脚本（`eval_robotic_grounding.py`，位置待核对）产出提交物。
- 本地复算 AUC / SP-SR / MP-SR / MPPE，并与官方脚本的输出对账。
- 每份提交物带上它的来历：档位、`runs/` 下的运行、配置、上游 commit。

三档分开计分，分数不可跨档比较。

- `static_baseline.py`：“物体全程不动”的 ADD-AUC 基线与参考旋转剖面。按评测器同一方式载入参考、用评测器自己的
  `object_add` / `add_auc` 计算；policy 的 ADD-AUC 不高于它，说明跟踪不比“不碰物体”好（在 FlashCHORD 容器里跑）。

官方 `eval_robotic_grounding.py` 的封装尚无代码。契约见 [`docs/contracts/evaluate.md`](../../docs/contracts/evaluate.md)。
