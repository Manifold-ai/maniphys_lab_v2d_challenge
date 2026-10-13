# 计划：Tier 3 最终交付版 best_hm 的训练（D）与两台机器接下来的排程（2026-10-12 晚，第 2 版：按 Fable 5.1 审查修改）

用户 10/12 16:40 前后：“两边机器现在跑得怎么样了 规划一下下一步”。按 `agent-doc/plan-next-training-2026-10-12.md` 第 4a 节的授权（“你来为我进行决策
并给我判断的理由”），本计划直接做决定并写理由；提交、加入 Kaggle 比赛、删本地数据不在授权内，列在第 7 节。时间一律 UTC−6，“明天”指 10/13。
第 1 版经 Fable 5.1 独立审查（GO WITH FIXES：2 条 MAJOR、8 条 MINOR、3 条 NIT），逐条处理见文末。

## 1. 事实

- **mf4090**：t1xa2 按停链标记在 ep21 之后停下，15:51 三条链都结束，GPU 空闲（`results/t1x/end_t1xa2_mf4090_1012_1551.txt`）。ep21 的 4096 世界
  MP-SR 0.806、ADD-AUC 0.556（`results/day2/eval_t1-ep21-w2048-cap4m-r3a-mf4090_s349999104.txt`）；A 的 7 条只训了 ep17、ep21，没开的 ep10、13、19、3、14
  排在 D 之后（训练计划第 2 节）。最终交付版 `best_hm` 的第二轮门槛复查在跑（`agent-doc/plan-t3-hm-p2-2026-10-12.md`）：16:38 重定向出了 13/29 集，
  间隙都是 −0.0 mm、状态都是 OK，左右手接触帧与最近的面和提供方的记录一致（`results/t3hm/progress_mf4090_1012_1638.txt`）；16:57 出了 19 集，
  预计 17:25 前后跑完。16:38 可用 4183 MB，重定向每集约写 65–72 MB，跑完约剩 3.1–3.2 GB。
- **ml40**：B（t2xb，9 条）ep9 训完用了 130 分钟、ep1 用了 111 分钟，ep13 在训，16:37 到 1.7 亿步；后面还有 ep19、2、4、14、25、28
  （`results/t2x/status_ml40_1012_1638.txt`）。训练链预计明天 04:45–06:50 结束，评测与导出之后 B 整段约 06:00–08:00 结束（估计）。可用约 1.4 TB。
- **D 的输入**：`runs/tier3/root_hm`（29 集，支撑面取自交付目录，哈希逐个核过）、`runs/motion_src/tier3_hm` 与 `runs/motion/tier3_hm`（重定向输出）。
  重定向产物的 parquet 里有 `raw_motion_file` 指向 `/repo/runs/motion_src/tier3_<名>/<序列>/soma_params.npz`；导出与起链读
  `runs/motion_src/tier3_<名>/<序列>/v2d_meta.json`（`stages/policy/arm_var_chain.sh` 核它的档位与集号）。12 集有桌面（ep2、3、6、7、9、11、13、16、17、20、25、27），
  训练链挂的 `v040_p185_nfg` 导入器把这 12 份都建成 2 cm 薄板（`results/t3hm/support_slab_check.txt`，`SLAB_OK 12/12`）；17 集只有地面。
  ep28 在 suspect 目录，提供方写明稍后单独分析，不在这一批。
- **已训练过的集**：t3p3 的 10 集参考是 f830（`agent-doc/plan-t3-v2-train10-2026-10-10.md` 的执行记录），跟上 ep24、ep0、ep18、ep22、ep26，没跟上 ep20、ep29、ep15、
  ep23、ep17（“跟上” = 对自己参考的 4096 世界 MP-SR ≥ 0.5）。换成 `best_hm` 后这 10 集的参考都变了：ep15、ep17 是重新配准（物体约 1 m，人体也换了一版），
  ep22 物体位置约 4 cm、人体也换了一版，其余 7 集只在竖直方向差 1.5–7.9 cm（`results/t3hm/version_diff_v2_hm_mf4090.txt`）。ep8 10/9 试跑过一次
  （`t3-ep8-w2048-cap4m-r3a-mf4090`，参考是更早的地面校正版，MP-SR 0.000）。其余 18 集（ep1–7、9–14、16、19、21、25、27）没在 Tier 3 训练过。
- **支撑面的基线设置**：队列生成器照抄 Tier 2 基线的期望表 `support` 列与 `scene.support=false` 覆盖；29 集里 ep1 的 Tier 2 基线
  （`t2-ep1-w2048-cap10m-p185-ml40`）开着支撑面，而 `best_hm` 的 ep1 只有地面（审查 1）。
- **机制**：`make_var_queue.py` 生成队列，`arm_var_chain.sh` 起链；起链脚本原来只认 `t2x`、`t1y`（ml40）与 `t3p`、`t1x`（mf4090）四种段名。
  mf4090 的 Tier 3 段：起链要求可用 ≥ 2500 MB，每条冒烟与正式开跑前 ≥ 1200 MB（`day2_train_chain.sh`），冒烟判过后删 state；一集约 375 MB。用时：冒烟约 5 分钟；
  训练 t3p2b 的 ep24 用了 2 小时 17 分钟、t1xa2 的 ep21 用了 2 小时 14 分钟；评测约 6 分钟。ml40 上 B 每条 111–130 分钟。
  有训练链时 `scripts/dev/remote` 拒绝同步。ml40 上没有这一版的 Tier 3 数据，要从 mf4090 经 Mac 转过去。
- **HF 归档第 4 批**（`agent-doc/plan-hf-archive-batch4-2026-10-12.md` 第 2 版）：t1xa2 只训完 ep21，清单是 11 条 run（t3p3 9 条、ep17、ep21），
  预计 297 个文件、约 3,151 MB（第 2 版第 3 节“少几条按条数折算”）。第一段（上传、核对、抽查）期间 mf4090 不起别的写盘任务；`hf_archive.py plan`
  只认长链标记，认不出重定向的 tmux；删除一步要求没有训练链、GPU 空闲，并且要用户点头。
- **Tier 1 重新逐条选**：上一次是 10/9，在 ml40 的 CPU 容器里跑（`results/ml40/select_t1/select_r3x.txt`、`results/ops/relay_t1x_r3x.txt`）；`select_t1.sh`
  核来历的 commit，候选要先经 `relay_t1x.sh` 转到 ml40。
- **第 4a 节的几条**（10/12 代为决定、已报给用户）：第 4 条 Tier 3 按要交准备、30 集都要有轨迹、没过门槛的也正式训练、不用官方支撑面、ep17 与 ep20 按新支撑面重训；
  第 3 条 C 按停手规则（B 的 9 条里一条 4096 世界 MP-SR ≥ 0.5 都没有就不起）；第 6 条 Tier 2 ep23 在 B 之后用 400 万 buffer 补一条；第 7 条提交不代做，
  建议 A 结束、重新逐条选之后交一次 Tier 1。训练计划第 3 节 D 写了建议的先后：①已训练、没跟上、参考明显变好的 ep15、ep17；②新过门槛的集；
  ③已跟上、参考变了的集；④没过门槛的集。

## 2. 决定与理由

1. **D 训 `best_hm` 正式目录的 29 集，已训练的 10 集也重训。** 理由：第 4a 节第 4 条要 30 集都有轨迹；10 集的参考都变了，旧策略跟的是 f830 的物体高度，
   而评分对照的是干净真值，交付版的高度后处理就是为了把静置的物体放回面上；本地分辨不出哪一版更接近真值（档位隔离），只留旧策略等于默认旧参考更好，没有依据。
   ep28 等提供方分析完、按同一流程复查后再排。
2. **顺序沿用训练计划第 3 节 D 的建议：① ep15、ep17 → ② 其余没跟上过的 19 集（18 集没训过，加 ep8）→ ③ 重训其余 8 集（ep0、18、22、24、26、20、23、29）。**
   理由：①重新配准了约 1 m，最可能翻盘；②每一集都是 Tier 3 从无到有；③的参考只差几厘米，旧策略里 5 集已跟上，重训的边际收益最小。
   ②里按集号排，不再按别的指标挑：全部训完只要约 1.5 天的 GPU 时间，排序只影响先后，不影响有没有。
3. **ml40 在 B 结束后先训 D，C 往后排。** 理由：Tier 3 现在一条能交的轨迹都没有，Tier 1、Tier 2 都已有交的版本，C（Tier 1 的 6 条外推）只是在已有提交上再挑；
   29 集只靠 mf4090 约 3 天，两台约 1.5 天 GPU 时间（ml40 明早才空，墙钟约 2 天）；离榜单冻结（11/04）还有 23 天，C、Tier 2 ep23、t1xa2 剩下的 5 条在 D 之后
   排得下。B 结束时照样按登记的停手规则判 C 起不起、记下来，只是执行推后。
4. **配方同 t3p3**：变体 A（`objective.object_position_std=0.05`、`termination.object_orientation_threshold=0.6`）、seed 42、2048 世界、3.5 亿步；buffer mf4090 400 万、
   ml40 1000 万（两台的惯例）；训练挂 `v040_p185_nfg`，评测与导出挂 `fc_8c778f9`。**支撑面按 `best_hm` 自己的定**：12 集有桌面的期望表 `support` 列为 true、
   不带覆盖；17 集只有地面的列为 false、带 `scene.support=false`；不沿用 Tier 2 基线的（审查 1，ep1 就是不一致的那一集）。
   理由：同一配方在 Tier 3 的 10 集上跟上 5 集；Tier 1 上试过它的 9 条全被逐条选中（训练计划第 1 节），Tier 2 按乙换掉的 18 条全是它
   （`agent-doc/plan-t2-select-b-2026-10-12.md` 执行记录）；换配方要另做试验，不在这一步。
5. **mf4090 今晚先做 HF 第 4 批的第一段，再起 D 的第一段；D 第一段只排 5 集。** 理由：第 4 批的第一段不能和写盘任务同时跑，删除要等没有训练链，D 一起链，
   删除就要等到段与段之间；5 集约 1.9 GB，不删第 4 批也放得下（复查结束约剩 3.1–3.2 GB，第 5 集开跑前约剩 1.5–1.6 GB，高于 1.2 GB 的下限）。
6. **Tier 1 的重新逐条选挪到明天 B 结束之后，和 Tier 2 的乙重做一起在 ml40 上做**（第 1 版写的“今晚在 Mac 上”不对，审查 8）。理由：两件都在 ml40 的 CPU 容器里跑，
   B 结束、ml40 同步之后做最省事；今晚的关键路径是复查收尾、第 4 批与 `t3p4a`；A 只训了 7 条里的 2 条，这次选是中间版，ep10、13、19、3、14 训完后还要再选。

## 3. 做法

**今晚（mf4090）**

0. 代码（已做，附测试，与本计划第 2 版一起提交）：`make_var_queue.py` 加清单 `t3p4`（mf4090，400 万 buffer，run 名 `t3-ep<N>-w2048-cap4m-r3a-hm-mf4090`，
   W&B 标签 `t3p4`）与 `t3q`（ml40，1000 万，`t3-ep<N>-w2048-cap10m-r3a-hm-ml40`，标签 `t3q`），参考 `/runs/motion/tier3_hm/`，基线同 t3p3 取 Tier 2 导出清单；
   两份清单都带同一个 29 集的总顺序（段之间挪集只要 `--episodes`，审查 5）；`tables` 键按 `best_hm` 的 12 集桌面定支撑面；`arm_var_chain.sh` 加 `t3q*`
   （ml40、Tier 3，其余同 `t2x`）；`test_make_var_queue.py` 补用例（含 ep1、ep15、ep17 三种与基线不一致的情形）。四段的队列一次生成、一起提交：
   - `t3p4a`（mf4090，今晚）：ep15、17、1、2、3；
   - `t3p4b`（mf4090，`t3p4a` 之后、第 4 批删除之后）：ep12、13、14、16、19、21、25、27；
   - `t3qa`（ml40，明天 B 之后）：ep4、5、6、7、8、9、10、11；
   - `t3qb`（ml40，`t3qa` 之后）：ep0、18、22、24、26、20、23、29（第③组整组放 ml40：mf4090 训完 13 集后磁盘不够再排，见第 5 节）。
1. 门槛复查第二轮收尾（复查计划第 4 节第 9–11 步）。P2′ 不过的集照样训练（第 4a 节第 4 条），只在报告里标出。
2. HF 第 4 批第一段（第 4 批计划第 2 节第 2–5 步）。**开始条件**：tmux `v2d-t3hm-retarget` 已结束、记录 `results/t3hm/retarget_mf4090.txt` 以 `EPS_DONE` 结束
   （审查 3），没有长链标记。结束后请用户确认删除。
3. 同步 mf4090（第 4 批第一段结束后、配置展开之前；四段的队列都在这次同步里，`t3p4a` 起链后到它的三条链结束之前不能再同步，审查 4）。
4. 用户在这之前同意删除：先删第 4 批（第 4 批计划第 2 节第 6 步），再起链；还没同意：直接起 `t3p4a`，删除等 `t3p4a` 结束后的空档。
5. `t3p4a`：配置展开（`fc_config_check.sh`，`results/t3p4/cfgcheck_t3p4a_mf4090.txt`）→ 预演（`V2D_ARM_DRYRUN=1 arm_var_chain.sh t3p4a`）→ 起链。

**明天**

6. mf4090：`t3p4a` 结束 → 拉回结果、健康记录、评测表 → 第 4 批删除（用户同意时）→ `t3p4b` 的三道核对与起链（磁盘不够时按第 5 节缩段）。
7. ml40：B 结束 → 拉回结果与健康记录 → 按登记的停手规则判 C 并记下（执行推后）→ 同步 ml40 → Tier 2 用 t2xb 的候选重做一次乙（新标签，不提交）、
   Tier 1 中间版的重新逐条选（`relay_t1x.sh` 先转 t1xa、再转 t1xa2 的候选，`select_t1.sh` 用新标签与 `V2D_SELECT_CURRENT`、`V2D_SELECT_GATE`，打包只跑上传器
   `--dry-run`，不提交）。
8. ml40 的 Tier 3 数据：新写 `stages/recovery/tier3_relay.sh`（先写计划补充一节、审查后执行），把 `runs/tier3/root_hm`、`runs/motion_src/tier3_hm`、
   `runs/motion/tier3_hm` 从 mf4090 经 Mac 以 tar 流转到 ml40 的仓库副本（与 `tier3_stage.sh` 同一种管道），目标目录事先不存在，两端按 sha256 清单逐个核对。
   三个目录都转：`root_hm` 与 `motion_src` 里训练用不到的文件也带上，parquet 里的 `raw_motion_file` 指向 `motion_src`，ml40 的磁盘不缺。
9. `t3qa`：配置展开 → 预演 → 起链；结束后接 `t3qb`。
10. 每段结束：结果、健康记录、评测表（`eval_table.py`）、jev、执行记录、提交、报告。

## 4. 判据（执行前登记）

- **代码**：Mac 上 `test_make_var_queue.py` 全过。生成的四段队列：run 名、集号与第 3 节一致；17 集只有地面的（ep0、1、4、5、8、10、12、14、15、18、19、21、22、23、24、26、29，
  ep1 在内）期望表 `support` 列是 false、正式与冒烟行都带 `scene.support=false`；12 集有桌面的列是 true、不带这条覆盖；parquet 都在 `/runs/motion/tier3_hm/`。
- **`t3p4a` 起链之前**（第 1–2 步的结果是前提，审查 2）：复查的重定向记录 29 行结果、没有 `FAIL:*`（有 FAIL 的集从队列里拿掉，用 `--episodes` 重新生成）；
  `p2_vs_theirs.py` 打 `THEIRS_SAME 29/29`，或不同之处查清、写进执行记录；`reconstructed_stage` 的 29 份支撑面 md5 与 `root_hm` 的相同
  （`results/t3hm/support_kinds_stage_mf4090.txt`），不同的集不开支撑面或先查清；第 4 批第一段已结束。
- **起链**：配置展开每份配置的断言全过、意外键 0；预演 `DRYRUN_OK`；mf4090 可用 ≥ 2500 MB（ml40 ≥ 200000 MB）；来历干净、与 Mac 上提交的 commit 相同；
  起链记录里训练挂的是 `v040_p185_nfg`、评测与导出挂的是 `fc_8c778f9`。
- **每集**：冒烟过 `smoke_check.sh`，256 世界 diag 没有非有限世界；正式 run 有 DONE、35 份 policy、最后一步 349999104，看守扫描非有限 0；
  4096 世界评测完成；1 世界导出 ok 或 fallback。
- **读法**（同 t3p3，只报，不据此改配置或重跑）：对 `best_hm` 参考的 4096 世界 MP-SR ≥ 0.5 记“跟上”，< 0.5 记“没跟上”；与同一集 t3p3 的旧结果（ep8 与 10/9 的试跑）、
  Tier 2 同配方的结果并列。没跟上的集要不要补 seed 43，等②做完再定。
- **ml40 的数据转发**：目标的三个目录事先不存在；两端的文件清单与 sha256 逐个相同；29 个 parquet、29 份 `v2d_meta.json`（档位 3、集号与目录对得上）、
  29 份支撑面都在；`reconstructed_stage` 的支撑面 md5 与 `root_hm` 的相同。
- **`t3q` 起链**（ml40）：L40S、可用 ≥ 200000 MB、`fc_src` 下两份副本都在且核对通过；ml40 与 mf4090 部署的 commit 相同。
- **第 4 批**：照第 4 批计划第 3 节（11 条、297 个文件、约 3,151 MB ± 1 MB 按条数折算）。
- **Tier 2 乙重做与 Tier 1 中间版逐条选**：照各自上一次的判据（`CHECK_T2_SELECT_OK`；Tier 1 的选择与打包门）；都不提交。
- **停**：任何一项不满足就停在那一步，查原因，不改判据。

## 5. 风险与限制

- 这一版的门槛间隙是构造出来的（复查计划第 6 节），P2′ 过不说明训练能跟上；t3p3 过门槛的 10 集只跟上 5 集。
- 手持段人体随物体平移后，机器人脚目标的竖直偏移变大（提供方报 ep19 −0.14 m，ep10、ep1、ep2 约 −0.12 m；ep28 −0.33 m 不在这批），腿姿可能别扭，
  门槛看不出；这几集若没跟上，先用 viser 看重定向的结果再定。ep1、ep2 在 `t3p4a` 里，最早暴露。
- 支撑面要靠打了 #185 补丁的导入器才建得对；`chain_preflight.sh` 默认核的是未打补丁的 `/workspace`，有桌面的集以起链记录里挂的副本为准。
- 评测对照的是 `best_hm` 自己的参考，不是干净真值，“跟上”只说明策略跟得住参考，不说明分数。
- **mf4090 磁盘**（每集约 375 MB，起链 ≥ 2500 MB，每条开跑前 ≥ 1200 MB）：`t3p4a` 之后约剩 1.2–1.3 GB。
  - 两样都不删：起链门不过，`t3p4b` 起不来，8 集全挪到 ml40（`t3q` 清单带 29 集的总顺序，`--episodes` 生成，在 `t3qa` 与 `t3qb` 之间的空档同步 ml40）。
  - 只删第 4 批（+约 3.15 GB）：约 4.4 GB，8 集放得下（第 8 集开跑前约 1.7 GB）。
  - 只删 `tier3_dlv`（+1925 MB）：约 3.1–3.2 GB，放得下 5–6 集，其余挪到 ml40。
  - 两样都删：约 6.3 GB，8 集之后还剩约 3.3 GB。
- ml40 的数据转发约 2.3 GB，经 Mac 走两段 ssh，Mac 离线就推后；转发不碰另一位用户的目录。
- 时长都是估计。

## 6. 时间（估计）

今晚：复查收尾 17:30–18:00；第 4 批第一段 17:30–18:30；同步、配置展开、预演约 40 分钟，`t3p4a` 约 19:15–19:30 起链，5 集约 12 小时，明天 07:30 前后结束。
明天：B 06:00–08:00 结束；同步、两次逐条选、数据转发约 1.5 小时；`t3qa` 约 09:30 起，8 集约 16–18 小时，10/14 01:30–03:30 结束；`t3p4b` 约 08:30 起，8 集约 19 小时，
10/14 03:30 前后结束；`t3qb` 接着 `t3qa`，8 集约 16–18 小时，D 的 29 集大约 10/14 晚上训完（GPU 时间约 1.5 天，墙钟约 2 天）。
之后排 C、Tier 2 ep23、t1xa2 剩下的 5 条与 seed 43；mf4090 再排之前先做第 5 批归档（`t3p4a`、`t3p4b` 的旧 policy 与最终 state），另写计划。

## 7. 要用户定的

1. HF 第 4 批核对通过后删 mf4090 本地的 297 个文件（约 3.15 GB），今晚 18:30 前后请示。不删的话 `t3p4b` 起不来，8 集挪到 ml40（第 5 节）。
2. 第一轮 `tier3_dlv` 的转换与重定向产物 1925 MB（能由 `root_dlv` 与代码重建，`best_hm` 定下后用不上）删不删。只删它不删第 4 批，`t3p4b` 放得下 5–6 集。
3. 加入 Tier 3 的 4 个 Kaggle 比赛（Tier 3 要交，30 集训完之前加入就行）。
4. Tier 1 中间版逐条选之后交不交一次（第 4a 节第 7 条的建议）。

## 8. 补充：ml40 的数据转发（第 3 节第 8 步；10/13 00:30 写，第 2 版按 Fable 5.1 审查修改，第 3 版改经 HF 私有仓库中转，审查后执行）

- **为什么今晚做**：B（t2xb）估计 07:00–07:30 结束，之后 ml40 要等同步、转发、`t3qa` 起链。转发只在 ml40 上新建三个原本不存在的目录，
  不碰 t2xb 用的 Tier 2 目录，也不改仓库代码（“链在跑时不同步”管的是代码，这一步不同步）；先做掉，早上只剩同步与起链。
- **第 2 版经 Mac 管道太慢**：00:51 起跑，2 分钟只到 3 MB（约 25 KB/s，2.3 GB 要一天以上），00:57 停掉，`RELAY_FAILED 2（转发）`，暂存目录已删，
  ml40 上什么都没留下（`results/t3hm/relay_ml40.txt.failed`）。第 1 次（00:48）因脚本没有执行权限没跑起来，什么都没动。用户 10/13 01:00 前后定：
  “需要传数据还是得HF”。
- **事实**（00:25 与 01:05–01:15）：mf4090 上 `runs/tier3/root_hm` 363 MB、117 个文件，`runs/motion_src/tier3_hm` 1096 MB、232 个，`runs/motion/tier3_hm` 829 MB、174 个，
  合计约 2288 MB、523 个文件，没有符号链接；`runs/motion/tier3_hm` 下 data.parquet 29 个、`reconstructed_stage` 支撑面 29 份（`<序列>_support.usda`，
  没有 `<序列>_g1_support.usda`；文件名里带 `_g1_` 的那份是序列名 `g1_box_rotate_01` 本身），`motion_src` 29 个序列目录；`root_hm/support_surface` 29 份同名支撑面。
  ml40 仓库副本（`/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge`，来历 3e517ff，还没有 `t3q` 的队列）里三个目标都不存在，`/lab_data` 可用约 1.39 TB。
  ml40 经 http 代理能到 huggingface.co：接口 0.74 秒返回，从公开归档仓库下载一份 160 MB 的 state，30 秒下了 157 MB，约 5.2 MB/s（未落盘的临时查看）；
  mf4090 上传约 5.6 MB/s（第 4 批 3.15 GB 用 9.3 分钟）。ml40 的主机 Python 与 flash_chord 镜像里都没有 huggingface_hub，接收端只用标准库下载，
  不在 ml40 上装包。账号私有存储已用 81.73 GB（`results/ops/hf_storage_1013_0110.txt`）；第 3 批撞过私有额度，这次再加约 2.3 GB。
- **做法**：
  ① 新建私有仓库 `Rongxuan-Zhou/v2d-track2-transfer`，只做中转：`docs/hf/v2d-track2-transfer/README.md` 拷到 mf4090 的 `runs/hf_readme/v2d-track2-transfer.md`，
  经 `tools/hf_remote.sh` 跑 `hf_archive.py readme --repo Rongxuan-Zhou/v2d-track2-transfer --file … --visibility private`（仓库不存在时只建私有仓库）与
  `hf_archive.py whoami --repo Rongxuan-Zhou/v2d-track2-transfer --visibility private`（`results/ops/hf_readme_v2d_track2_transfer.txt`）。
  ② `tools/hf_transfer.py` 与 `tools/test_hf_transfer.py` 经 ssh 的 stdin 复制到 mf4090 与 ml40 的 `runs/tools/`，两端 md5 对比，两台都跑测试
  （`results/t3hm/hf_transfer_deploy.txt`）。
  ②′ 冒烟（审查 F5，`results/t3hm/hf_transfer_smoke.txt`）：mf4090 上建 `runs/xfer_smoke_1013/`（一个文本文件、一个 64 KB 的 `.npy`，后者按仓库默认的
  `.gitattributes` 走 LFS，下载时会跳到 CDN），push 标签 `smoke_1013`；ml40 上 pull 到 `runs/.xfer_smoke_1013.partial/`；两端 sha256 逐行相同后删掉两边的冒烟目录。
  这一步验证 ml40 上标准库经带密码的 http 代理走 CONNECT、证书校验、跳 CDN 不带 token 这条路，不过就不传正式数据。
  ③ `caffeinate -i scripts/dev/record t3hm/relay_ml40_hf stages/recovery/tier3_relay.sh hm 29 523 t3hm_1013a`（测试 `stages/recovery/test_tier3_relay.py` 6 组在 Mac 上全过）：
  第 1 步同第 2 版；第 2 步 mf4090 上 `hf_transfer.py push` 三个目录（硬链接进 `runs/hf_xfer/t3hm_1013a/` 再上传，不多占盘；仓库必须私有、有 README、
  标签下原本没有文件；传完列仓库核对路径、大小与 LFS sha256，删掉暂存的硬链接），ml40 上 `hf_transfer.py pull` 到暂存目录（只对 huggingface.co 带 token，
  跳到 CDN 时不带；每个文件边下边算 sha256，与清单不同重下一次，仍不同就停）；第 3–5 步同第 2 版：两端 sha256 清单（发送端现场列、接收端现场列，
  不信任仓库里的清单）在 Mac 上逐行比对，文件数 523；暂存目录里查集数、档位、集号、`sequence_id`、支撑面与 `root_hm` 同名文件的 sha256；挪之前再查目标、
  同一个文件系统；挪完再比一次清单。②–④ 任何一步不过就删暂存目录；⑤ 中途不过什么都不删。
  ④ 之后在 ml40 容器里（不占 GPU）对 29 个 parquet 跑 `stages/policy/check_inputs.py`（parquet 能读、帧数与 fps、引用的资产与支撑面在容器内都在），
  记录 `results/t3hm/check_inputs_ml40.txt`。
- **判据**：README 上传 `HF_README_OK`，`whoami` 报仓库私有；两台的测试全过、复制的文件 md5 相同；冒烟 `HF_PUSH_OK 2`、`HF_PULL_OK 2`、两端 sha256 相同；上传 `HF_PUSH_OK 523`，下载 `HF_PULL_OK 523`；
  最后一行 `RELAY_OK`；两端清单都是 523 个文件、逐行相同，挪到位后的清单与来源逐行相同；parquet、`v2d_meta.json`、支撑面各 29 份，档位都是 3，
  集号 29 个各不相同（记录里应是 0–27 与 29，ep28 还没交付，人工核对），`sequence_id` 与目录全同名，支撑面与 `root_hm` 同名文件 29/29 相同；
  `check_inputs.py` 29 个都没有缺失（退出码 0）。不过就停，不重试，查清再说。
- **风险与收尾**：凭据只经 `tools/hf_remote.sh` 的 stdin 进到两台机器上这两条命令的环境里，命令结束就没了；`hf_transfer.py` 不打印 token，输出经同样的过滤。
  私有额度若不够，上传在第 2 步失败，什么都不删，停下报告。仓库里的副本在 `t3qa`、`t3qb` 用完之后删不删待定。上传或下载中途失败时，暂存目录删掉、
  目标不受影响；仓库里的 `t3hm_1013a/` 留着，同一条命令可以重跑（push 见到与清单一致的副本就不重传、传了一半就接着传，只有内容不对或有清单外的文件才要换标签）。⑤ 中途失败（三次 `mv` 只做了一部分）时不删任何东西：
  看暂存目录里剩什么，把剩下的手动挪完再按 ③ 的命令核一遍清单，或删掉已挪到位的目录与暂存目录后重跑。mf4090 上读盘、上传与 `t3p4a` 的训练同时进行，
  只读；ml40 上写盘与 t2xb 同时进行，空间充足。转发不碰另一位用户的目录。
- **之后**：B 结束 → 拉回结果与健康记录 → 同步 ml40（带上 `t3q` 的队列与 `arm_var_chain.sh` 的 `t3q*`；`scripts/dev/remote` 不删 `runs/`，转来的数据不受影响）
  → `t3qa` 配置展开 → 预演 → 起链（第 3 节第 7、9 步）。

### 第 8 节的审查与处理（第 2 版）

| 编号 | 级别 | 意见 | 处理 |
|---|---|---|---|
| F1 | MAJOR | 第 5 步挪之前不再查目标；转发的几分钟里若有人建了同名目录，`mv` 会把整棵树挪进去，照样写 RELAY_OK | 采纳：挪之前再查目标都不存在；挪完在目标位置重列清单、与来源逐行比对；测试补“下载后有人建了目标”一例 |
| F2 | MINOR | 三次 `mv` 不是一个事务，中途失败会留下一半；跨文件系统时 `mv` 是复制加删除 | 采纳：挪之前查暂存目录与三个上级目录在同一个文件系统；手动收尾写进“风险与收尾” |
| F3 | MINOR | Mac 断网时删不了暂存目录，重跑会被第 1 步拒；ssh 没有保活，Mac 睡着会挂很久 | 采纳：ssh 加 `ServerAliveInterval=30`、`ServerAliveCountMax=6`；命令前加 `caffeinate -i`；第 3 版不再经 Mac 传数据 |
| F4 | MINOR | 第 4 节“集号与目录对得上”“支撑面 md5 与 root_hm 的相同”没有实现；523 与集号列表只打印不判 | 采纳：查 `sequence_id` 与目录同名；在 Mac 上用清单比对 29 份支撑面与 `root_hm/support_surface` 同名文件；文件数作为参数（523）判；集号列表在记录里人工核对 |
| F5 | MINOR | 测试缺：转发途中出现目标、残留暂存目录、传输失败、清单失败、集号重复、目标外的哨兵文件、来源不变 | 采纳：全部补上（6 组，每例都核来源不变、哨兵文件不变） |
| F6 | NIT | `xargs -0 sha256sum` 没有 `-r`，空列表时会给出一行 | 采纳：`xargs -0r`；另有文件数判据 |
| F7 | NIT | 数支撑面会把 `<序列>_g1_support.usda` 也算进去，而它加载时优先 | 采纳：分开数，有 `_g1_support` 就停 |
| F8 | NIT | 非普通文件数的两次查询没有查退出码，ssh 失败时报成“两端清单不一致” | 采纳：分别查，失败时写明是哪一端 |
| F9 | NIT | parquet 里的路径、属主、权限从 Mac 上查不了 | 采纳：第 ④ 步在 ml40 容器里对 29 个 parquet 跑 `check_inputs.py` |
| F10 | NIT | 读的时候训练若在写这些文件会出错 | 记录：不放宽检查，失败就等当前这一集结束后重跑 |

### 第 8 节的审查与处理（第 3 版）

| 编号 | 级别 | 意见 | 处理 |
|---|---|---|---|
| F1 | MINOR | 带不带 token 只比主机不比协议，同主机的 http 跳转会把 token 明文发出去 | 采纳：比协议加主机；补单元测试 |
| F2 | MINOR | 清单行是 `.` 时落点是暂存目录本身，`.part` 会写到它外面 | 采纳：拒绝 `.`、`//`、结尾 `/`，并核实落点在暂存目录里面；补 `.`、绝对路径、反斜杠、`./`、`//`、大写或长度不对的 sha256、重复、空清单的测试 |
| F3 | MINOR | push 没有 `HF_ENDPOINT` 的闸，手动在 mf4090 上跑会把 token 发给镜像 | 采纳：同 `hf_archive.py` 的闸，另要 `HF_TOKEN` |
| F4 | MINOR | 下载失败后同一个标签不能重传，只能换标签再传 2.3 GB，旧的还占私有额度 | 采纳：push 见到与清单一致就不重传，传了一半且内容都对就接着传；内容核对用 LFS sha256 与 git blob sha1 |
| F5 | MINOR | ml40 上经代理的这条路没测过（测试去掉了代理，用的是 http） | 采纳：正式数据之前先跑两个文件的冒烟（第 ②′ 步） |
| F6 | MINOR | 重试不隔时间，429、5xx 与哈希不符一样只试两次 | 采纳：最多 3 次，每次间隔 5 秒乘次数 |
| F7 | MINOR | 测试缺：同主机换协议、重定向转圈、单个文件 404、清单的各种坏行、上传抛错、上传后缺文件、下载报的数目不对、hf_remote 的凭据过滤 | 采纳：全部补上（`test_hf_transfer.py` 8 组、`test_tier3_relay.py` 6 组、新 `test_hf_remote.py` 2 组） |
| F8 | NIT | 读写清单没写 `encoding="utf-8"` | 采纳 |
| F9 | NIT | 硬链接或上传出错时暂存目录留着，下次要换标签 | 采纳：出错时删掉暂存的硬链接与 `.cache` 再报错 |
| F10 | NIT | 每次跳转的 `HTTPError` 没关 | 采纳：`e.close()` |
| F11 | NIT | README 里的命令路径是 `tools/`，训练机上是 `runs/tools/`；`t3hm_1013a` 一行写在上传之前 | 采纳：改路径；这一行先写“上传中”，核对通过后改 |
| F12 | NIT | 转发脚本里的主机与路径和 `hf_remote.sh` 的取自两处，没有核对 | 采纳：两次输出里 `_load-env` 打的“→ 主机:路径”要与脚本里的一致，否则停 |

## 审查与处理（第 2 版）

| 编号 | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | MAJOR | 生成器照抄 Tier 2 基线的 `support` 列与覆盖；ep1 的基线开着支撑面，`best_hm` 的 ep1 只有地面 | 采纳：新清单的 `tables` 键按 `best_hm` 定列与覆盖，测试覆盖 ep1、ep15、ep17；判据写明 17 集与 12 集 |
| 2 | MAJOR | 复查登记的结果（`THEIRS_SAME`、`reconstructed_stage` 的 md5、29 行没有 FAIL）没成为起链前提 | 采纳：第 4 节“`t3p4a` 起链之前”一项 |
| 3 | MINOR | 第 4 批按钟点起，重定向可能还在写 | 采纳：开始条件改为 tmux 结束、记录以 `EPS_DONE` 结束 |
| 4 | MINOR | 缺 mf4090 的同步一步；`t3p4b` 的队列要在同一次同步里 | 采纳：第 3 节第 3 步 |
| 5 | MINOR | “其余挪到 ml40”做不到：`--episodes` 只能取清单里的集 | 采纳：两份清单都带 29 集的总顺序，测试覆盖 `t3qc --episodes 13,12` |
| 6 | MINOR | 不删第 4 批时 `t3p4b` 起不来，几种情形没量化 | 采纳：第 5 节列四种情形，第 7 节写明后果 |
| 7 | MINOR | “用户 10/12 定的先后”“用户已定 30 集”说错了出处 | 采纳：改为第 4a 节（代为决定、已报用户）与训练计划第 3 节 D 的建议顺序 |
| 8 | MINOR | Tier 1 重选不在 Mac 上跑，上一次是 10/9 在 ml40；A 只训了 2 条，是中间版 | 采纳：挪到明天 B 之后在 ml40 上做，写明两次转发、新标签与环境变量，标明中间版 |
| 9 | MINOR | 缺 ml40 数据转发、`t3q` 起链、乙重做的判据 | 采纳：第 4 节补三项；三个目录都转（审查说只需 `motion` 与 `v2d_meta.json`，parquet 里有指向 `motion_src` 的字段，全转更稳） |
| 10 | MINOR | ep8 10/9 试跑过 | 采纳：第 1 节写明，②写成“18 集没训过，加 ep8” |
| 11 | NIT | “两台约 1.5 天”是 GPU 时间 | 采纳：写明墙钟约 2 天 |
| 12 | NIT | ep22 的人体也换了一版 | 采纳：第 1 节照实写 |
| 13 | NIT | “训练计划第 2 节”应为第 1 节；第 1 版提交说明写了“五段”，实际四段 | 采纳：改出处；提交说明的笔误记在这里 |

## 执行记录（10/12，时间 UTC−6）

- 第 0 步：代码、测试、四段队列与本计划第 2 版提交 6efc9e8（`test_make_var_queue.py` 11 项全过；四段队列逐集核过支撑面：12 集有桌面的开、17 集只有地面的关）。
- 第 1 步：门槛复查第二轮做完（`agent-doc/plan-t3-hm-p2-2026-10-12.md` 执行记录）：P2′ 29/29、没有 FAIL；`THEIRS_SAME 29/29`；`STAGE_COPY_SAME 29/29`。
  第 4 节“`t3p4a` 起链之前”的三项都满足。
- 第 2 步：17:20 重定向结束、记录以 `EPS_DONE` 结束之后开始第 4 批第一段：清单 297 个文件、3151.3 MB（`results/ops/hf_archive_batch4_plan_mf4090.txt`、
  `results/ops/hf_archive_batch4_manifest_sum_mf4090.txt`）；17:24–17:41 上传 9.3 分钟、核对 297/297、抽查 22/22，停在删除前（`HF_ARCHIVE_VERIFIED`，
  `results/ops/hf_archive_batch4_run_mf4090.txt`、`results/ops/hf_archive_batch4_verified_mf4090.txt`）；README 改为“已上传、已核对，本地未删”后仓库 1989 个文件、
  27.51 GB（`results/ops/hf_readme_v2d_track2_archive_batch4_verified.txt`）。jev 5/7 verified、对照 3/3 正常（`results/ops/jev_claims_hf_batch4.txt`）。
  删除等用户确认。
- 第 3 步：17:48 同步 mf4090 到 a629fbd（`results/ops/sync_mf4090_1012_1748.txt`），四段队列都在。
- 第 4 步：用户还没回复删除，按本计划直接起链，删除等 `t3p4a` 结束后的空档。
- 第 5 步：配置展开 10 份配置意外键 0，ep15、ep1 `scene.support=False`，ep17、2、3 保持开（`results/t3p4/cfgcheck_t3p4a_mf4090.txt`）；预演 `DRYRUN_OK`，
  来历 a629fbd、可用 3153 MB，训练挂 `v040_p185_nfg`、评测与导出挂 `fc_8c778f9`（`results/t3p4/arm_dryrun_t3p4a_mf4090.txt`）；17:46 起链 `ARMED`，
  第一条冒烟 ep15（`results/t3p4/arm_t3p4a_mf4090.txt`）。预计明早 05:30–06:30 结束（估计）。

## 执行记录（10/13，时间 UTC−6）

- 00:09 前后用户确认删除第 4 批（“确认过HF和本地一样的就可以删”）。删除一步要求没有训练链、GPU 空闲，`t3p4a` 还在跑；按
  `agent-doc/plan-mf4090-handover-2026-10-13.md`（第 2 版，审查 GO WITH FIXES 后全部采纳）在 mf4090 上挂接续，00:48 起
  （`results/t3p4/arm_after_launch_mf4090.txt`）：`t3p4a` 三条链结束、卡空后先做删除前的对齐核对与演习，过了再删；`t3p4a` 训练、评测、导出全部做完才起 `t3p4b`。
  `t3p4b` 的配置展开 00:22 已做（16/16、意外 0，支撑面随 `best_hm`，`results/t3p4/cfgcheck_t3p4b_mf4090.txt`）。
- ep3 的磁盘：在训的 run 比训完的大约 120 MB，训完缩回 360 MB；按这个算 ep3 开跑前约剩 1.6 GB，高于 1200 MB 的闸（未落盘的临时查看）。
- 第 8 步（ml40 的数据转发）：第 2 版经 Mac 管道，00:48 第 1 次脚本没有执行权限、什么都没动；00:51 第 2 次约 25 KB/s，00:57 停掉，
  `RELAY_FAILED 2（转发）`、暂存目录已删（`results/t3hm/relay_ml40.txt.failed`）。用户定改经 HF；第 3 版审查 GO WITH FIXES（0 MAJOR），12 条全部采纳（1e96765）。
  私有中转仓库 `Rongxuan-Zhou/v2d-track2-transfer` 建好，README `HF_README_OK`、`HF_WHOAMI_OK`、私有（`results/ops/hf_readme_v2d_track2_transfer.txt`）；
  账号私有存储 81.73 GB（`results/ops/hf_storage_1013_0110.txt`）。
- 冒烟第 1 次停在 push：标签目录还不存在时 `list_repo_tree` 回 404，工具当成了出错，什么都没传（`results/t3hm/hf_transfer_smoke_run1.txt.failed`）；
  改成当作空目录、假 API 也照真的抛 404 后重新部署（两台 md5 相同、测试全过，`results/t3hm/hf_transfer_deploy2.txt`）。冒烟第 2 次 `HF_SMOKE_OK`：
  上传 2 个文件加清单，`.npy` 走 LFS，ml40 经代理下载 2/2，两端 sha256 相同，两边冒烟目录已删（`results/t3hm/hf_transfer_smoke.txt`）。
- 01:34–01:56 经 HF 转发 `RELAY_OK`（`results/t3hm/relay_ml40_hf.txt`）：mf4090 上传 523 个文件、2395.4 MB 用 118 秒，仓库里 524 个（含清单）缺 0、不符 0、多出 0；
  ml40 下载 523/523 用 1156 秒（约 2 MB/s）；两端 sha256 清单都是 523 个、逐行相同（摘要 5c696a8cb24f2fb7），非普通文件 0；支撑面与 `root_hm` 同名文件 29/29 相同；
  parquet、`v2d_meta.json`、支撑面各 29 份，`_g1_support` 0，档位 3，集号 0–27 与 29（人工核对，与预期一致），`sequence_id` 与目录不符 0；挪到位后清单与来源逐行相同。
  上传期间 mf4090 的可用空间没有因为上传变少（暂存是硬链接，xet 缓存 95 → 96 MB；可用 1701 → 1545 MB 是 ep2 在长）。
- 01:56 ml40 容器里 `check_inputs.py`（md5 2a0e1527…，来历 3e517ff）对 29 个 parquet：mesh 与 urdf 58 处都在、缺失 0，支撑面 29 份都找到，fps 都是 30，退出码 0
  （`results/t3hm/check_inputs_ml40.txt`）。第 8 节的判据全部满足。中转仓库的 README 改为“已传、已核对”后重传，`HF_README_OK`，仓库私有、529 个文件、2.40 GB
  （`results/ops/hf_readme_v2d_track2_transfer_relayed.txt`）。仓库里的副本删不删，待 `t3qa`、`t3qb` 用完后定。
- 之后：B 结束 → 拉回结果与健康记录 → 同步 ml40 → `t3qa` 配置展开 → 预演 → 起链（第 3 节第 7、9 步）。07:00 的 SOP 定时任务不同步、不起链，这几步等下一次交互。
