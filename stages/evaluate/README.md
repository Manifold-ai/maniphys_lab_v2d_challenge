# stages/evaluate

- 调用官方评测脚本（`eval_robotic_grounding.py`，位置待核对）产出提交物。
- 本地复算 AUC / SP-SR / MP-SR / MPPE，并与官方脚本的输出对账。
- 每份提交物带上它的来历：档位、`runs/` 下的运行、配置、上游 commit。

三档分开计分，分数不可跨档比较。

尚无代码。契约见 [`docs/contracts/evaluate.md`](../../docs/contracts/evaluate.md)。
