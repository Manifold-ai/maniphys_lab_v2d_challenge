# 决定记录：原定问组委会的前三问，不等答复直接定（2026-10-01 16:30 UTC-6）

用户 10/1 的要求原文：“1-3条你来决策一下 同时用jev验证”。三问出自 `agent-doc/organizer-email-draft-2026-10-01.md` 第 1 版：
方盒支撑面用哪个运行时、评测时世界被判终止就报错、空支撑面的处理。时间一律 UTC-6。

证据都由仓库里的脚本落盘：`results/submission/runtime_pin_facts.txt`（`stages/evaluate/runtime_pin_facts.sh`）、
`results/submission/eval_outcome_tally.txt`（`stages/evaluate/eval_outcome_tally.py`）、`results/submission/eval_termination_errors.txt`。
jev 核对：`results/submission/jev_claims_decision_q1_q3.txt`（第 2 轮），规格 `agent-doc/decision-organizer-q1-q3-2026-10-01.claims.json`。

## 第 1 问：方盒支撑面用哪个运行时 → 组委会已经改了，用 8c778f9

事实：
- 组委会 10/1 13:40 合并 #188，kit 重新发布（13:43，zip sha256 0f2f9f4b…）。新 kit 的 README 把 FlashCHORD 运行时钉在
  `8c778f905c…`，提交说明写明“which includes Cube support scaling”，也就是带 #185 的版本 <jev 0.89>。旧 kit（a2de2aee…）钉的是 aee95f2。
- aee95f2 到 8c778f9 之间，FlashCHORD 源码只改了 `scene/support.py` 和它的测试 <jev 0.95>。
- ml40 上 #185 补丁副本的 `support.py` 与 8c778f9 的 md5 相同（4d6eab11…）<jev 0.98>。

决定：
1. 三档的评测与导出都用 8c778f9。这一问从邮件里删掉。
2. ep1、ep7、ep28 在 Tier 1 与 Tier 2 各训一条，共 6 条，用 #185 的几何。训练运行时沿用 v0.4.0 加 #185 补丁副本
   （与其余 27 条同一份训练代码，只差 `support.py`；9/30 的对照里这个组合 8 个种子 0 发散）。
   排在 Tier 2 第 1 批之后，另写计划、review 再跑；mf4090 上还没有补丁副本，要先用 `make_patched_fc_src.sh` 生成。
   ep28 在 #185 的几何下参考仍穿过两块 2 cm 板，开训前先看参考。
3. 已训的非方盒 policy 继续作为候选：它们的支撑面是圆柱或只有地面，#185 不改这两种几何。

没验证的：v0.4.0 训出的 checkpoint 能不能直接在 8c778f9 的评测器里加载、出轨迹。放进提交流程计划里第一件事实测。

## 第 2 问：世界被判终止就报错 → 不是规则问题，不问；靠自己的流程挡住

事实：
- 评测器把 ReconBody 终止的阈值全改成 1e6（`harness.py:65, 242`），而终止判断是“误差 > 阈值”
  （`termination.py:604, 641, 644`）；配方里原来的阈值是 0.10 到 1.50 <jev 0.91>。所以评测时普通的任务失败（物体掉了、跑远了）
  不会让世界被判终止，只有误差超过 1e6 才会，这是数值发散的量级。后半句是读代码的推论。
- 已落盘的 96 份评测全部成功出分，合计 393,216 个世界，没有一份报错，`non_finite_worlds` 都是空的；其中 46 份 MP-SR 为 0，
  MPPE 最大的一份 116.7 cm <jev 0.98>。评测器只要有一个世界被判终止就整份报错，所以这 393,216 个世界里没有一个被判终止。
- 报过这个错的只有两条 run：ep7 的冒烟和 ep1 的正式训练，两条的 policy 都含非有限参数 <jev 0.84>
  （ep1 三份评测各有 2342 到 2445 个世界出现非有限位姿，ep7 冒烟 256 个里 172 个）。

决定：
1. 这一问从邮件里删掉。
2. 含非有限参数的 policy 不拿去导出：训练链已经会标 `NONFINITE` 并跳过评测（10/1 上线）。
3. 提交流程里，每条 episode 的 1 个世界导出若报这个错，退到同一条 run 里更早的一份有限 checkpoint 再导；
   这是唯一允许不用最终 checkpoint 的情形，写进提交流程计划的判据。

剩下的风险：参数有限的 policy 在官方那 1 个世界里数值发散。39 万个世界里没出现过，不能排除。

## 第 3 问：空支撑面 → 继续用 scene.support=false，不等答复

事实：
- 8c778f9 里，支撑面文件没有 Cylinder 或 Cube 时 `support.py:94` 报错；`setup.py:61` 只在 `include_support` 为真时才取支撑面，
  为假时就是只有地面；为真却找不到支撑面也报错（`setup.py:62–64`）<jev 0.92>。
  官方给的 16 个空文件在这个运行时里开着支撑面建不起场景，关掉支撑面是它自己提供的路径。
- kit 的评测配置 `use_checkpoint_config: true` <jev 0.99>，评测时按 checkpoint 里的配置重建场景，会沿用 `scene.support=false`。
- Tier 1 只有地面的 16 条里 9 条通过，MP-SR 最高的 5 条（0.992、0.979、0.975、0.962、0.956）全在这 16 条里；
  有支撑面的 11 条只过 2 条 <jev 0.99>。

决定：继续用 `scene.support=false`，Tier 2 第 1 批已经这样在跑。邮件里降成一句告知，不作为要等答复的问题。

## jev

第 2 轮 9 条全部核实（0.84–0.99），5 道对照题方向正确（真对照 0.97，假对照 0.01–0.13）。
第 1 轮（`…_run1.txt`）里“报错的两条 run 都含非有限参数”只有 0.64：当时的证据是执行记录里的转述。
换成两台服务器上评测日志的原文（`results/submission/eval_termination_errors.txt`）后是 0.84，结论措辞没改。

## 顺带查到、还没处理的两件事

1. **Tier 2 打包可能要加 `--frame-references`**。新 kit 的 Track 2 说明：打包器用“评测器记录的参考”与“这一档发布的输入”之间的一个刚体变换来换算位姿；
   自己重建的输入要用 `--frame-references` 给出。我们 Tier 2 的参考是 v5.4 降噪后的轨迹，不是发布的带噪输入。该怎么给，要先读新打包器的代码，
   放进提交流程计划；读完再定要不要问组委会。
2. **Tier 3 的输入**。新 kit 的表里写着 Tier 3 对应的发布目录是 `track_2/tier_3_cari4d/`，但 HF 数据集（最后修改 9/22）的 `track_2` 下只有
   Tier 1、Tier 2 两个目录。组委会可能之后会发一份 CARI4D 重建当 Tier 3 的输入。这会改变 Tier 3 的工作量，加进邮件问。
