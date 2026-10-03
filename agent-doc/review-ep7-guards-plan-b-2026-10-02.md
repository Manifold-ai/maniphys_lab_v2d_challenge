# 审查记录：ep7 防护计划 B 部分（2026-10-02）

审的是 `agent-doc/plan-ep7-eval-and-guards-2026-10-02.md` 的 B.1–B.7（3ce4ea5 的文本）。主会话是 Fable 5.1。
- **Opus 5.5 的审查 15:28 回来：GO WITH FIXES，没有 BLOCKER，6 条 MAJOR。** 下面是它的意见摘要（原文只在会话里，这里按条记全），都还没有处理。
- **Fable 5.1 的那一份 15:29 被停掉**（用户要求 15:30 前停掉这边要靠 Mac 的任务），没有结果；20:10 重起，审第 4 版，20:40 回来，摘要在文末“Fable 5.1 审第 4 版”一节。

计划选的三件事（终止 kernel 判非有限、重置时清 warmstart、学习器入口清洗）审查认为仍是合理的最小改动；warmstart 的读法、重置能传进 mjw_data、
清 warmstart 的位置与顺序、强制 `pelvis_failed` 能绕开冻结屏蔽、评测与导出不受影响，这几点它逐项核对后都成立。

## MAJOR（写补丁之前要改进计划）

1. **学习器侧漏了两个会进回放的入口。** 下一步写进回放的 `observation`、`critic_context` 来自上一步的 `post_reset_observation`、`post_reset_critic_context`
   （`learner.py:1069–1081, 1127–1131`）。计划没提 `post_reset_critic_context`，重置后的观测也没用 fp16 判据。环境没重置这个世界时（只有学习器判坏），这两个量会原样进 learner 状态、再进回放。
   改法：`next_*` 与 `post_reset_*` 四个数组用同一个判据（观测按回放的存储精度、上下文按 fp32），任一命中就四个一起换成这一步之前的观测与上下文。
   T3 加一例：环境给的 terminated 是 0、重置后观测含 1e5、上下文含 NaN，连续喂 n_step + 1 步以上，再查 storage 与 pending 全部有限。
2. **坏世界那一步把终止项也清零，等于奖励“把仿真弄崩”。** 第 0 个奖励分项是终止项，权重 −300（各段相同），普通失败那一步约 −6；全清零后崩掉那一步是 0，比普通失败好
   （`objectives/recon_body.py:26–39, 47, 234`、课程配置第 13 行、`replay.py:444–451`）。改法：坏世界的分项写成“终止项 1、其余 0”。T3 断言写进 pending 的分项。
3. **T4 测不到环境侧；按“观测第 356 维”硬编码会让上游测试挂掉。** 上游涉及终止与环境的测试都带 gpu 标记，CPU 容器里整批 skip；上游 learner、runner 测试的观测只有 3 维，`obs[:, 356]` 越界。
   改法：相位改从评论家上下文按名字取 `normalized_reference_phase`，没有就记 −1；带 gpu 标记的测试放到 GPU 时段跑；另写一个 CPU 上直接 launch 终止 kernel 的测试。
4. **T5 约四成概率误停，又挡不住小改动；“逐位相同”没有可用的证据。** 243–309、25.6–34.8 是 8 个种子的最小与最大值，新的一条落在外面的概率是 2/9，两条至少一条落外约 40%；
   GPU 上本来就不逐位可复现。改法：T5 只登记“跑完、各行有限、坏世界计数 0、吞吐看稳态行”；“没有事件时不变”改由组件级测试证明（新旧终止 kernel 在一批有限 body_q 上 12 个输出逐位相同；
   warmstart kernel 对有限的行不动；学习器清洗对干净输入原样返回）。可把学习器清洗做成 `runner.py` 里单独 jit 的前置函数、计数放在 LearnerState 之外，`consume_transition` 就与原来完全一样。
5. **T6 没写世界数和注入时机；注入方式只代表一种事件。** 回放满 409,600 条才开始更新（2048 个世界要 200 步，64 个世界要 6,400 步），注入太早或跑得太短就是空测。
   改法：T6 写明 2048 个世界、在回放够了之后注入、注入后再跑几百到上千步；T2、T6 再加三种注入：物体平移写 1e6（有限但超出 fp16）、物体四元数写 NaN、
   同一步坏 3 个世界（其中一个在冻结期、一个正好在截断那步）。注入点本身成立（substeps 4、`update_data_interval` 默认 1），写入要与 Warp 的流排好序。
6. **R-2 登记的内容现有记录给不出来，也没有“事件太多就停”。** 一个日志窗口 51,200 个世界步，只记“坏世界步数”和“最近一次相位”报不出各次事件；防护把坏数据挡掉后，
   每个窗口都出事训练也能“跑完”，吞吐还可能减半。改法：窗口计数拆成“环境判坏”“只有学习器判坏”两项，另记相位的最小与最大；宿主机每个窗口打一行；
   事先登记停止条件（例如“只有学习器判坏”累计超过 N 次，或同一世界连续 3 步判坏）。

## MINOR

1. B.1 漏了物体朝向这条路：物体四元数没有 normalize 就进夹角函数，NaN 经 clamp 得 0、夹角 π，过了冻结期（50 步）NaN 世界一定以 object 原因终止；冻结期内只看骨盆朝向。
   NaN 世界于是在“重置 → 冻结最多 50 步 → object 终止”之间循环，与 t1-ep7 第 2592 行“没有骨盆终止”一致。T1 的预期要写成原因记为 object、注入后约 51 步内被重置一次。
2. `SolverMuJoCo.step` 每个子步还写 ctrl、qfrc_applied、xfrc_applied（整行赋值，不带 NaN 跨步）。跨步保留又不被覆盖的只有 qacc_warmstart；act 在 na > 0 时也算（G1 的 na 未核实）。T2 里顺手记下重置后 act 与 warmstart 是否有限。
3. 环境侧判据建议遍历本世界全部刚体（kernel 已有 bodies_per_world）；平移用 `wp.isfinite(vec3)`、旋转用 `wp.isfinite(quat)`，不要直接对 transform 调（可能落到恒真的兜底模板，未核实）；
   可选：平移绝对值超过 1e3 m 也判坏，让环境与学习器的判据对齐。
4. 只清非有限的 warmstart 行时，很大但有限的值会留下，下一步多半变 NaN 再清一次，真实事件可能计 2 次；用 `getattr(self.solver, "mjw_data", None)` 防 CPU 后端；断言 nworld 等于 world_count。
5. T1 的后备做法（直接写 mjw_data 的速度）无效，下一个子步就被覆盖。想单独验证机理：T1b 只把一个健康世界的 warmstart 写成 NaN；T2 加一个对照“打终止补丁但不清 warmstart”。
6. “每次事件一条样本”不准：n_step 是 7，以坏那一步结尾的窗口最多 7 个。回放与 TD 目标用乘法掩码，NaN × 0 仍是 NaN，所以清洗必须在写 pending 之前、用 `jnp.where`。
7. fp16 判据只用在 observation 与 next_observation 上，并且要读配置里的存储精度。
8. 实现细节：清洗放在 `apply_stage_context` 之后；`termination_diagnostics` 一律 `where(isfinite, x, 0)`；“最近一次相位”的初值必须有限；每个 terminated 的世界至少带一个原因位。
9. `V2D_KEEP_STATES` 要写进新的队列行（方盒队列行自带 1），链里还要 `V2D_ALLOW_FC_SRC=1`；留 3 份可能正好把事件前那份挤掉，4 份更稳；给新副本出 sha256 清单，开训前用 `fc_src_check.py` 核。
10. `exports/*.tsv` 由 `export_map.py` 按登记规则生成，手改会与规则对不上，应改规则与测试后重新生成；改用打补丁的训练副本是新的决定，应补 ADR 或变更记录（ADR-00003 写的是“源码不改”）。
11. B.5 少一种结局：重训出的 policy 在 8c778f9、4096 世界的评测里仍出现非有限世界，候选条件不满足，ep7 照样缺。怎么走要事先登记。
12. 分析记录有两处要改：G1 的实验配置里每采集一步更新 4 次，不是 2 次（`g1_recon_body_flash_sac.yaml:53`）；t1-ep7 第 2592 行的动作均值 nan 更像 actor 的 BatchNorm 已经坏了，
    拿它当“NaN 世界没被清掉”的证据偏弱，改成“与之相容”。

## 替代方案（审查的看法）

关掉 warmstart：一行改动，但每步都从 qacc_smooth 起算、没有事件时动力学也不再相同，另两侧照样要做，不如现方案。每步在 `_transition` 开头清所有世界的非有限 warmstart：与放在重置里等价，二选一。
用 mujoco_warp 的 reset_data：会清更多状态、风险更大。只做学习器侧：坏世界永远在循环里、吞吐减半，不可取。

## Fable 5.1 审第 4 版（10/2 20:40 回来）

审的是第 4 版的 B.1–B.8（331aecd 的文本）与 72d4aaf 的补丁草稿。主会话是 Opus 5.5。**GO WITH FIXES，没有 BLOCKER，2 条 MAJOR。**
它逐项核对后认为成立的点：transition 的叶子是 Warp 数组的零拷贝视图，`consume_transition` 只 donate learner、AOT 编译不重追踪，前置函数排在同一个 JAX 流上，读 `learner.observation` 安全；
没有事件时 `jnp.where` 逐位保留（含 −0.0）；世界内刚体编号连续、各世界不平移（1e3 m 不会误伤）；`wp.isfinite(quat)` 有真实现、transform 没有重载；
两条重置路都经 `BaseEnv.reset`，后者录在图里；`qacc_warmstart` 的形状是 `(nworld, nv)`、录图后不重新分配；坏世界重置后接触槽、SONIC 历史都不留 NaN。

### MAJOR

A. **M1 改过头。** 环境判坏的世界在 `_rl_step` 里已经重置，`post_reset_observation / post_reset_critic_context` 是新回合的第一帧观测，有限且正确；
   计划写的“四个数组任一命中就一起换”会把它换成上一回合崩之前的观测，下一步的动作与回放样本都错一条（`learner.py:1072, 1078, 1130–1131`）。
   改法：`next_*` 与 `post_reset_*` 各用自己的判据（自身非有限或存不进存储精度才换）；K3 加“环境已重置、`next_*` 是 NaN、`post_reset_*` 有限 → 原样返回”；
   只有学习器判坏、环境没重置的世界仍换成旧观测，并写明这一步与仿真脱节一步。
B. **`V2D_ALLOW_FC_SRC=1` 写进队列行会让链在开头就停。** 链读的是自己的环境（`day2_train_chain.sh:58–61`、`precheck_expect.sh:17`），队列行的前缀只经 `run_q` 传给 `fc_run*.sh`；
   方盒链的 ALLOW 与 FC_SRC 写在 `arm_box_chains.sh:27` 的 tmux 命令里。改法：队列行只带 `V2D_KEEP_STATES=4` 等，链的启动命令带 `V2D_ALLOW_FC_SRC=1 V2D_FC_SRC=<副本>`；
   另要新的期望表（含冒烟行）、冒烟队列，以及先用 `fc_config_check.sh` 生成 `runs/cfgcheck/<run>.yaml`（`precheck_expect.sh:31` 缺它就不过）。

### MINOR

1. ADR-00003 正文写“源码不改”，与训练用补丁副本矛盾，要改正文；`docs/contracts/policy.md` 全空，K1–K3、T2 的 docstring 要能指回契约 ID。
2. 哨兵 −1 经 `packed_diagnostics` 进 `tracking_error/pelvis_position_m_*`，把均值拉低；前置函数计数之后应把它清成 0 再交给学习器。
3. 停训在链里会被记成普通失败（`fc_run.sh:224` 重试用尽、退出码 2）；停训前打一行固定前缀的标记，事件行也用固定前缀。
4. 计数不进 checkpoint，续训从 0 起；写明或另存。
5. 前置函数的实现约束：不许宿主端分支、一律 `jnp.where`、输出是新缓冲、`terminated` 保持 int32、终止项按名字找。
6. 相位取 `next_critic_context`（由 timestep 算，NaN 世界也有限），不取重置后的。
7. T2 的注入写 `joint_q / joint_qd`，不写 `body_q`（下一个子步只从 joint_q、joint_qd 推 qpos、qvel，body_q 随后被覆盖）；物体平移与四元数写物体自由关节的 `joint_q`。
8. T2(d) 的冻结期与截断步要用 `RLEnv.reset(reset_frame=…, reset_mask=…)` 显式造；T2 全部在 `capture_step()` 之后跑。
9. T1 的预期：注入时已过冻结期的 NaN 世界当步就以 object 或 palm 原因终止，之后每 51 步一次。
10. K1 要同时录 `timestep`、`episode_step`。
11. “不清 warmstart”的对照别用环境变量开关（会成为训练里看不见的旋钮），用配置字段或第三份副本。
12. `act` 在 na = 0 时宽度为 0，跳过。
13. T5 的吞吐 97% 偏紧（单机两次冒烟常差 2–3%）；T5 的 run 名取链的冒烟名，链见 DONE 就跳过。
14. `export_map.py` 的 `tier1()` 正则不认新名、`exports/*.tsv` 已存在会拒绝覆盖，规则写成“同 episode 有 `-p185g-` 的 run 就用它”，测试同步改。
15. 只有学习器判坏的世界 `terminated=1` 会让学习器多记一个完成回合，环境的 `episode_step` 照旧；写明即可。
16. `make_patched_fc_src.sh` 的清单循环不跳 `#` 行（`fc_src_check.py` 跳），清单别写注释头。

### 替代设计（审查的看法，未采用）

重置的世界一律清零 warmstart（MuJoCo `mj_resetData` 的语义）：更稳，但正常重置后的第一次求解起点变了，“没有事件时逐位不变”不再成立。
只改环境侧、不碰 JAX：没有 AOT、donate 的坑，但丢掉“只有学习器判坏”这张安全网与停止条件。`mjw.reset_data(reset=mask)`：清得太多，不建议。

