# 审查记录：Tier 1 逐条选与 SOP 案例视频两份计划（Fable 5.1，2026-10-08）

两份计划第 1 版各经一个 Fable 5.1 独立审查，结论都是 **GO WITH FIXES**。逐条意见与处理写在各自计划文末的“审查与处理”一节：

- `agent-doc/plan-t1-per-episode-select-2026-10-08.md`：8 条（2 条 must：ml40 上打包的来历守卫；不解析有损的打印、缺指标与打包失败的候选剔除）。
- `agent-doc/plan-site-cases-video-2026-10-08.md`：9 条（刚体顺序改为三道确定性门、骨盆跳变截断、案例 3、4 同为 seed 42、清单钉住来历等）。

执行中的偏差（如实记下）：
- kit 依赖原定钉成 10/3 Mac 上的版本；`numpy 2.5.3` 要求 Python ≥ 3.12，ml40 容器是 3.11，numpy 用容器自带的 2.4.6，其余照钉（pandas 2.3.3、pyarrow 25.0.1、trimesh 5.1.1）。
  环境是否等价由打分门 B（整份打包与 10/3 打印值相差 ≤ 1e-4）判定。
- kit 放在 ml40 的 `runs/kit/update_0f2f9f4b/`（`scripts/dev/remote` 的 `--delete` 会删掉 `third_party/` 下被忽略的文件，`runs/` 受保护），由官方 zip 解出，zip sha256 = 0f2f9f4b…。
