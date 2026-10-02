# 执行记录：8c778f9 兼容性验证 + 方盒三条两档重训（10/1 晚部署，10/2 自动执行）

计划 `agent-doc/plan-box6-and-eval-runtime-2026-10-01.md` 第 2 版（3b55a0e），按 Fable 5.1 的计划与代码两份审查修改（两份都是 GO WITH FIXES，没有 BLOCKER）。
时间一律 UTC-6；服务器日志是北京时间（UTC+8）。

## 部署与预检（10/1 20:49–21:02，不占 GPU，Tier 2 链没动）

| 项 | 结果 | 落盘 |
|---|---|---|
| 放新文件 | 两台各 27 个新文件，md5 全对，`.v2d-source-commit` 仍是 90a73fa8e852；之后按需覆盖了 4 个我们自己放上去的文件（`V2D_PUSH_REPLACE_FROM`，只许覆盖先前那一版） | `results/box/deploy{,2,3,4,5}_{mf4090,ml40}.txt` |
| 源码副本 | mf4090：p185、8c778f9 两份都 FC_SRC_OK；ml40：新建 8c778f9 副本 FC_SRC_OK，已有的 p185 副本复核 FC_SRC_OK | `results/box/fc_src_{mf4090,ml40}.txt` |
| 副本核对的一处修正 | ml40 的 p185 副本第一次核对不过，差异全在 `assets/.cache/convex/*.npz`：FlashCHORD 建场景时写的凸包缓存，npz 带时间戳，同名文件字节也不同；`support.py` 本身一致。核对改为跳过 `.cache/`（f779ffc） | `results/box/fc_src_ml40.txt.failed` |
| 宿主机测试 | mf4090 宿主机 6 套全过（python 3.10.12、numpy 2.2.6、pyarrow 25.0.1）；ml40 宿主机没有 numpy：4 套只用标准库的在宿主机过，2 套要 numpy 的在容器里过。check_export 因此改由 `check_export.sh` 在缺库时进容器跑（781accd） | `results/box/tests_{mf4090,ml40}.txt`、`tests2_mf4090.txt`、`tests3_mf4090.txt` |
| compat 预检 | 两台 COMPAT_DRYRUN_OK：每行 fc_export 的预检退出码对（守卫行 12），要等的日志在，副本核得过；ml40 的 check_export 走容器 | `results/box/compat_dryrun{,2}_{mf4090,ml40}.txt` |
| 配置核对与正向预检 | mf4090 8 份、ml40 4 份配置与官方配方的意外差异都是 0；PRECHECK_OK（4 条、2 条 run） | `results/box/cfgcheck_{mf4090,ml40}.txt` |
| P5′ 打包换算 | Tier 1 30 条对发布输入、Tier 2 30 条对 v5.4，全部 FRAME_REF_OK，残差约 0.0001 mm、0.0001 mrad；计分帧合计 22,989，与样例提交的行数相同 | `results/box/frame_ref_t{1,2}_mf4090.txt` |
| Tier 2 方盒参考的穿透（#185 几何） | ep1 对椅背 121 帧嵌入超过 5 mm、52 帧穿板；ep7 熨斗 123 帧有顶点穿到 1 cm 桌板另一侧；ep28 两块板 244、211 帧穿过，160 帧低于地面超过 5 mm。已补进计划的事先登记 | `results/box/support_penetration_t2_mf4090.txt` |

P5′ 的结论：只要评测器记下的参考就是 motion parquet 的物体位姿（导出后由 check_export 复核），两档打包时的刚体换算都不会挡住；Tier 2 给 `--frame-references` 传 v5.4。

## 起链（10/1 20:58 失败、21:01 重起）

- **20:58 第一次起链，失败**（安全地失败：没有任何 GPU 任务开跑，Tier 2 链没动）。compat 往自己日志里写了等待提示
  “等 … 的最后一行变成 DAY2_EVAL_DONE / DAY2_EVAL_FAILED”。chain_after.sh 盯着 compat 日志的最后一行找 `DAY2_EVAL_(DONE|FAILED)`，
  当场把这句等待提示当成 compat 已经结束，去读门槛文件，门槛还没写，就在方盒训练日志里写了 DAY2_TRAIN_FAILED；
  方盒评测链随即开始，GPU 检查发现 Tier 2 的进程，停下（`results/box/arm_{mf4090,ml40}.txt`）。
  两边的测试与审查原型都是先跑完 compat 再跑 chain_after，没测到两者同时在跑的情形。
- **处理**：停掉在等的 compat 会话，三份日志改名为 `*.aborted-10021059` 留档；compat 日志里只有最后一行带结束标记的原文
  （等待提示改写，上一段评测链的结束行抄进来时把标记换成中文）；补测试“compat 在等时 chain_after 同时盯着，不许提前决定”，
  它在旧脚本上失败、新脚本上通过，另断言 compat 日志里只有一行带结束标记（c354d7a）。服务器上重跑测试与两台预检，都过。
- **21:01 重起**，两台各三个会话都在等（`results/box/arm2_{mf4090,ml40}.txt`）：
  compat 等上一段评测链结束；chain_after 有进程（mf4090 899044、ml40 37234），挺过了第一次检查；方盒评测链在等方盒训练日志。

## 接下来（自动）

| 时间（估计） | 机器 | 事件 |
|---|---|---|
| 10/2 06:15 前后 | mf4090 | Tier 2 B 段评完 → compat 开始（约 15 分钟）：4 行导出、1 行 4096 世界比对、守卫与反向对照 → 门槛 → 方盒 4 条（t1-ep1、t1-ep7、t1-ep28、t2-ep28） |
| 10/2 08:15 前后 | ml40 | Tier 2 B 段评完 → C 段（ep10）约 2.5 小时 |
| 10/2 10:45 前后 | ml40 | C 段评完 → compat（约 10 分钟）→ 门槛 → 方盒 2 条（t2-ep1、t2-ep7） |
| 10/2 15:00–16:00 | 两台 | 方盒 6 条评完（8c778f9 副本，4096 世界，只评最终 checkpoint） |

Mac 回来后要做的：拉回 compat 结果与导出，按计划第 3.5 节的判据与决策表下结论，写进本记录、过 jev；方盒评完后跑
`batch_verdict.py --steps 349999104` 与 `mount_check.py`；链跑完后整体同步一次（来历会从 90a73fa 更新）。
