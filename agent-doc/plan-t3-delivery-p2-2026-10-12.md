# 计划：Tier 3 交付版的门槛检查（P2′，mf4090，不训练；2026-10-12，第 2 版：按 Fable 5.1 审查修改）

用户 10/11 23:50 前后：“等明早交付版出来再统一做门槛检查”。时间一律 UTC−6。流程与 simreg 那次相同（`agent-doc/plan-t3-simreg-p2-2026-10-11.md`；
它的母本 `agent-doc/plan-t3-v2-retarget18-2026-10-10.md` 经 Fable 5.1 审查），这里写差异与这次的判据。这一步只数过 P2′ 的集，不训练、不出提交，
不读 Tier 1 的轨迹。第 1 版经 Fable 5.1 独立审查（GO WITH FIXES：4 条 MAJOR、6 条 MINOR、2 条 NIT），逐条处理见文末。

## 1. 事实

- **交付版还没出**。重建数据提供方的交接文档（`results/t3recon/handoff_tier3_1011_2200.txt`，分支 `track2/tier3-recon` 的 9f9f708，名字已脱敏）：
  每帧重新配准的 12 集队列跑完之后，逐集选版本（基线 / 重新选物 / 每帧配准）组装交付版，再重跑物理检查与 `t3_support.py`，
  再定物体高度的后处理（贴合放置段、防穿透，未实现）。队列 10/11 21:44 起在跑第 6 集 ep02，提供方估计 10/12 04:00–11:00 跑完（推断）。
  交付版的目录名、含哪些集、做没做高度后处理，现在都不知道。
- **现有版本**：f830（ml40 上 `runs/tier3_cari4d_f830_floor`，我们的 `tier3_v2`，正式 20 集，已训练的 10 集都用它）；
  simreg（`runs/tier3_cari4d_f830_simreg`，现在正式 21 集 + suspect 9 集；ep21 10/11 已配准进 simreg，ep06 来自重新选物版）。
- **已有的 P2′**：f830 20 集过 11 集（`results/t3p2/p2_18.txt` 18 集，第二轮的 ep8、ep24 在 `results/t3p2/p2_2.txt`，10/12 由
  `results/t3p2/retarget_mf4090.txt` 补出：ep8 不过、ep24 过）；simreg 17 集过 9 集，与 f830 逐集相同（`results/t3simreg/p2_compare_f830_simreg.txt`）。
- **已训练**（全部用 f830）：跟上 ep24、ep0、ep18、ep22、ep26；没跟上 ep20、ep29、ep15、ep23、ep17；ep21 暂不训练（`agent-doc/plan-t3-v2-train10-2026-10-10.md`）。
- **跟丢比例**（提供方 10/12 的新口径，剪影各膨胀 5 px；`results/ops/t3_queue_ml40_1011_2155.txt`）：每帧配准后 ep03 0.041、ep04 0.0299、ep11 0.0377、
  ep25 0.0501、ep13 0.2462、ep01 0.2985；重新选物后 ep06 0.0678、ep07 0.0123、ep10 0.0。f830 里判成悬空的 ep3、ep7、ep16、ep25 中，
  ep3、ep7、ep25 在新版本里跟丢比例降到 0.012–0.050；ep16 还在队列里。
- **支撑面口径不一致**：提供方定了 Tier 3 不用官方 `support_surface/`（理由：它放在干净物体每次静止的位置下面）。我们的 P2′ 按官方支撑面与地面里
  离物体最近的面算间隙：simreg 17 集里最近的面是支撑面的有 ep9、ep20（`results/t3simreg/p2_17.txt` 的“支撑面”列），训练 ep17、ep20 时开了
  `scene.support`（其余 8 集 `scene.support=False`，`results/t3p3/cfgcheck_t3p3{a,b,c}_mf4090.txt`）。怎么统一待用户定。这次照旧算，另把每集最近的面单独报出来。
- **地面文件**：提供方把自己 `input/ground_plane/` 里的文件清理成只剩 `plane` 字段（交接文档“10-12 白天”一节），不再与官方 Tier 2 的同名文件逐字节相同；
  拼目录时用的是 mf4090 上官方 Tier 2 的地面文件（哈希表核对），不受影响。上游 v0.4.0 的重定向只读地面文件的 `plane`
  （`ground_alignment.py` 第 1036–1038 行），`foot_plane_dist_stats` 只在探针脚本 `soma_loader_probe.py` 与我们 9/24 的 `bone_flex_physics.py` 里读，
  不在 Tier 3 的链路上（`results/t3dlv/foot_stats_reads_mf4090.txt`）。
- **手部接触**：Tier 2 那批重定向里（`results/batch_summary_v040_t2v54.tsv`），除 ep29（0 / 0）以外每一集都至少一只手有接触，
  包括这次可能新进来的 ep1、2、4、6、10、11、13、19、27、28；ep6（显示器）在 Tier 2 里也静置在支撑面上。
- **机器**：mf4090 10/11 21:57 可用 8774 MB，GPU 空闲，没有长链标记，部署版本 e87da93（之后的提交还没同步；这次要同步的只有白名单与哈希表）。
  ml40 的 GPU 被提供方的队列占着，我们只经 stdin 跑只读脚本。
- **磁盘与时间的参照**：simreg 17 集拼目录 237 MB、重定向产物约 1.2 GB（每集约 85 MB）；`eps.sh` 逐集顺序跑（参数 3 是档位，不是并发），
  simreg 17 集与 f830 18 集都是 45 分钟，每集约 2.5 分钟。

## 2. 触发与范围

- **触发**：提供方的交接文档写明哪个目录是交付版，才开工。ml40 上只出现新目录、文档没说明时不开工，回报用户。
  文档写明了交付版，但每帧配准的队列还没跑完时：照 B.1 当时正式目录里的集做，另列出队列里还没跑完的集，等它们出来再补一次。
- **检测**：Mac 上后台每 20 分钟只读查一次：分支有没有新提交（提交说明或交接文档新增的行里有“交付”“deliver”就叫醒）、ml40 的
  `runs/` 下有没有新的 `tier3_*` 目录、队列日志的最后一行。Mac 离线时由 07:00 的定时更新兜底。
- **范围**：交付版正式目录里的全部集，不含 `_suspect` 目录；suspect 目录里的集只列出集号，不拼、不重定向。集号以 B.1 核对为准。
- **名字**：`V2D_T3_SET=dlv`，档目录 `runs/tier3/root_dlv`，转换与重定向目录 `runs/motion_src/tier3_dlv`、`runs/motion/tier3_dlv`，都是新目录；
  f830、simreg 的目录与已训练 run 的输入都不动。A 段标签 `float_<月日>_dlv`（如 `float_1012_dlv`），拼目录标签 `t3dlv_<集数>_<月日>`；两个标签不同，
  `tier3_stage.sh` 不会撞上 A 段的 incoming 目录。

## 3. 做法

0. 交接文档存一份脱敏记录（`tools/redact_stdin.sh`），交付版的目录名、集号、做没做高度后处理写进执行记录。目录名（正式与 `_suspect` 各一个）
   加进 `stages/recovery/tier3_pack_remote.sh` 与 `tools/t3_episode_remote.sh` 的白名单。目录名不符合 `^tier3_cari4d[a-z0-9_]*$` 时，
   同一次提交里也改 `stages/recovery/t3_float_pack.sh` 与 `stages/recovery/tier3_stage.sh` 的目录名检查、`tools/t3_queue_remote.sh` 列目录的通配。
   提交，同步到 mf4090（没有长链标记时）。
1. A 段：`scripts/dev/record t3float/pack_<月日>_dlv stages/recovery/t3_float_pack.sh float_<月日>_dlv <目录> <集>`（转到
   `runs/tier3/incoming/float_<月日>_dlv/ok`）；`scripts/dev/record t3float/gate_dlv_ok<集数>_mf4090 ssh … scripts/dev/incontainer
   stages/recovery/t3_float_facts.py /repo/runs/tier3/incoming/float_<月日>_dlv/ok --all-rest --offset-gate 30`。下文的“A 段记录”都指这份 gate 记录。
2. B.1：`V2D_T3_SUBDIR=<目录>` 经 stdin 在 ml40 上跑 `tools/t3_episode_remote.sh`（`results/ops/t3_episodes_ml40_<月日>_dlv.txt`）。
   逐集看元数据里 `mesh`、`ground_plane`、`support_surface`、`support_surface_frame` 四个键都在；缺任何一个就停在这里回报
   （`tier3_root.py` 按这些键取文件，缺键会在拼目录时报错，而 A 段不会发现）。
3. mf4090 上 `stages/recovery/tier2_inputs_md5.py` 取这些集的官方 Tier 2 网格、地面、支撑面的 md5（`results/ops/t2_inputs_mf4090_<月日>_dlv.txt`）。
4. `stages/recovery/t3_sha_match.py <B.1 记录> <A 段记录> --inputs <第 3 步的记录>`（`results/t3dlv/sha_match.txt`）。
5. `stages/recovery/tier3_expect.py` 生成 `stages/recovery/expect/t3dlv_<集数>_<月日>.tsv`，提交，同步到 mf4090。
6. `V2D_T3_SUBDIR=<目录> V2D_T3_SET=dlv stages/recovery/tier3_stage.sh t3dlv_<集数>_<月日> <集>`（`results/t3dlv/stage_mf4090.txt`），随后只读核对
   `root_dlv`、`root_simreg`、`root_v2`、`root` 四个档目录 `meta/episodes_metadata.jsonl` 的行数与修改时间（`results/t3dlv/stage_check_mf4090.txt`）。
7. mf4090 的 tmux `v2d-t3dlv-retarget` 里跑
   `V2D_T3_SET=dlv V2D_RECORD_TRACEBACK_OK=1 scripts/dev/record t3dlv/retarget_mf4090 stages/retarget/eps.sh 3 <集>`。
8. 拉回结果并汇总：
   - `stages/retarget/p2_table.py results/t3dlv/retarget_mf4090.txt --no-contact 29 --a-phase <A 段记录>`（`results/t3dlv/p2.txt`）；
   - `stages/retarget/p2_compare.py` 每次比两份表，比三次：`simreg=results/t3simreg/p2_17.txt`、`f830=results/t3p2/p2_18.txt`、
     `f830r2=results/t3p2/p2_2.txt`，各对 `dlv=results/t3dlv/p2.txt`（`results/t3dlv/p2_compare_{simreg,f830,f830r2}.txt`）；
   - 参考变了哪些列：`scripts/dev/pipe-py stages/recovery/t3_version_diff.py runs/tier3/root_v2 runs/tier3/root_dlv <已训练且在交付版里的集>`
     （`results/t3dlv/version_diff_v2_dlv_mf4090.txt`），以及对 `runs/tier3/root_simreg` 的同样比较（两边都有的集，`results/t3dlv/version_diff_simreg_dlv_mf4090.txt`）。
     只看 parquet 的 sha256 不够：simreg 已经改了 17 集的人体缩放参数，交付版的 sha256 与 f830 几乎肯定都不同；要看变的是物体位姿还是只有人体。
9. jev（带对照题），执行记录，提交，回报用户。SOP 页面在下一次定时更新里补。

## 4. 判据（执行前登记）

- **A 段**：`OFFSET_GATE_PASS`（地面上的集常数偏移在 ±30 mm 以内，同前两次）。不过就停，不拼、不重定向，回报。
- **SHA**：B.1 里每集 parquet 的 sha256 都以 A 段同一集的前 12 位开头。不同的集去掉，重跑 B.1、重新生成哈希表，其余照做（同前两次）。
- **输入**：网格要 `INPUTS_SAME`；某集网格是 `INPUTS_DIFF` 就去掉这一集，回报。地面文件的 `INPUTS_DIFF` 是预期的（第 1 节，提供方只留了 `plane`），只报。
- **元数据键**：见第 3 节第 2 步，缺键就停。
- **拼目录**：记录里有 `V2D_T3_SET=dlv` 与 `TIER3_ROOT_OK`；`root_dlv` 的行数等于这次拼的集数、修改时间在拼目录之后；`root_simreg` 17 行、
  `root_v2` 20 行、`root` 2 行，修改时间都不变。不满足就停。
- **重定向的目录**：记录的正文第一行含 `目录 runs/motion_src/tier3_dlv、runs/motion/tier3_dlv`。不是就停，结果不判读。
- **P2′**（同前两次）：重定向后 |间隙| ≤ 30 mm（正负都算）且至少一只手有接触，记“过”；否则记“不过”；结果行是 `FAIL:*` 或没有结果行，记“失败”，
  不重试。只有 ep29 的接触一条不适用、只按间隙判（第 1 节：其余各集在 Tier 2 里都有手部接触）。阈值不因结果调整。
- **磁盘**：重定向前 mf4090 可用不到 2500 MB 不起（这次预计用 2–3 GB，估计）。
- **只报**：每集的间隙、最近的面（地面或支撑面）、左右手接触帧数、IK 残差中位；与 simreg、f830 两轮逐集并列（结论变了的集、间隙之差）；
  `SURFACE_TO_FLOOR`；已训练的集里物体位姿变了的集。最近的面是支撑面的集单独列出：按提供方的口径（不用官方支撑面）这些集只能对地面算间隙，
  面高 0.47–0.88 m，必然判成悬空，要等提供方从 Tier 3 信号估出的支撑面接进来。
- 这一步不训练。过 P2′ 的集训不训、已训练的集要不要换参考重训、支撑面口径，都由用户定。

## 5. 停手条件与已知限制

- 停手条件同前两次：哈希表核对不符、拼目录或重定向的目录不对、磁盘不够、mf4090 上出现别的用户的进程（不停别人的进程，回报用户）。
  `tier3_root.py` 拒绝之后同一标签不能重试：换新标签与新哈希表，或先删掉那个 incoming 目录。
- 提供方的目录在变（simreg 的 ep21 在我们转发期间被改过）：靠 B.1 与 A 段的 sha 比对和哈希表核对挡住。
- 交付版若做了物体高度后处理，间隙会系统地变小，P2′ 更容易过；这是后处理的目的，不算异常，回报里注明。
- P2′ 用官方支撑面，结论依赖支撑面口径（第 1 节）。评分对照干净的多视角真值，本地看不到（档位隔离），P2′ 回答不了哪一版更接近真值。
- ep21 的配准精度约平移 0.3 m、偏航 1°（提供方推断）；P2′ 只看高度，看不出水平配准的误差。
- P2′ 不预言训练能不能跟上：f830 过 P2′ 的 10 集训练后跟上 5 集（含 ep24）。
- `eps.sh` 每集只打日志的最后 15 行（另单独打脚底高度一行）；支撑面几何体多的集，日志里列出的各候选面可能被挤掉，结果行不受影响。

## 6. 时间（估计）

A 段转发约 25 分钟（20 集约 15 分钟）；B.1 到拼目录约 20 分钟；重定向每集约 2.5 分钟（21 集约 55 分钟、30 集约 75 分钟）；汇总、jev 与记录约 20 分钟。
交付版出来后约 2–2.5 小时出结论。

## 审查与处理（第 2 版）

| 编号 | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | MAJOR | `t3_float_pack.sh`、`tier3_stage.sh` 只认 `tier3_cari4d*` 的目录名，检测也只列这个前缀；交付版换个名字就过不了参数检查，也检测不到 | 第 0 步：名字不符合时同一次提交里改这两处检查与 `t3_queue_remote.sh` 的通配；检测改为列 `runs/` 下所有 `tier3_*` 目录，并看提交说明与交接文档 |
| 2 | MAJOR | 提供方把地面文件清理成只剩 `plane`，第 4 步对每集的地面都会报 `INPUTS_DIFF`，判据没说怎么读 | 第 4 节登记：网格必须相同，不同就去掉那一集；地面的 `INPUTS_DIFF` 是预期的，只报。另在 mf4090 上查过：上游重定向只读 `plane` |
| 3 | MAJOR | 与 f830 的并列漏掉 ep8、ep24（`p2_18.txt` 只有 18 集），ep24 是已训练、结果最好的一集 | 10/12 补记 `results/t3p2/p2_2.txt`（ep8 不过、ep24 过）；第 8 步加第三次并列 |
| 4 | MAJOR | 已训练 10 集“参考变没变”按 sha256 比没有信息量（simreg 已改了全部人体缩放），也没有比两份 B.1 记录的脚本 | 第 8 步改为 `t3_version_diff.py` 分别对 `root_v2` 与 `root_simreg` 逐列比较，报物体位姿变没变 |
| 5 | MINOR | 新进来的集的手部接触没核过 | 审查已按 Tier 2 批量记录核过：除 ep29 都有接触；写进第 1、4 节，ep6 也用支撑面 |
| 6 | MINOR | 交付版的元数据若去掉 `support_surface` 键，拼目录时才报错 | 第 2 步先查四个键，缺就停 |
| 7 | MINOR | 标签与“A 段记录”指代不清，同一标签会让拼目录撞上 A 段的目录 | 第 2 节与第 3 节写明两个标签与 gate 记录的名字 |
| 8 | MINOR | 支撑面口径的决定需要每集离地面与离最近支撑面两个间隙，表里只有到最近面的一个 | 部分采纳：登记读法——最近的面是支撑面的集，按提供方口径只能对地面算、必然判悬空（面高 0.47–0.88 m），决定要的是“哪些集依赖支撑面”，这一栏表里已有；两个间隙都列要改 `eps.sh` 与 `p2_table.py`，这一版不改，第 5 节注明日志尾可能截掉候选面 |
| 9 | MINOR | “并发 3”“GPU 空闲”不对：`eps.sh` 逐集顺序跑，3 是档位；重定向不用 GPU | 第 1、6 节改为每集约 2.5 分钟、顺序跑 |
| 10 | MINOR | 交付版写明了、但队列还有集没跑完时怎么办没说 | 第 2 节登记：照 B.1 当时的正式目录做，列出没跑完的集，出来后补一次 |
| 11 | NIT | `eps.sh` 的正文第一行是“来历 …；目录 …”，“是”应为“含” | 已改 |
| 12 | NIT | `challenge_to_soma.py` 没调 `forbid_tier1()`（只靠 `paths.tier(3)`）；官方 Tier 2 地面文件带 `foot_plane_dist_stats` | 后者已查：Tier 3 链路不读它（第 1 节）。前者不是这一版引入的，另记待办：转换入口加守卫并补测试，单独提交 |

### 10/12 观察（时间 UTC-6）

- 11:22 检测脚本看到 ml40 上新出现 `tier3_cari4d_f830_best`（29 集，只缺 ep28）与 `tier3_cari4d_f830_best_suspect`（ep28），11:14 组装；
  随后另一位用户在跑这一版的物理检查（`t3_physics_all.sh`）与支撑面估计（`t3_support.py`），都是 CPU（`results/ops/t3_queue_ml40_1012_1124.txt`）。
- 分支新提交 3511d42、58ed198 只改检查脚本（关节索引、脚算不算接触），交接文档自 9f9f708 起没有改动，没有写明交付目录。
  按第 2 节的触发条件，门槛复查不开始；另挂检测，等交接写明交付目录或目录再变。
