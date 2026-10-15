# 计划：Tier 3 动力学修复版（best_dyn4、best_dyn4s）的训练试点（2026-10-14，第 3 版）

10/14 09:21 MDT 另一位用户在 `track2/tier3-recon` 上推送了交接文档的更新（8107fef），随后提出用 best_dyn4 重训 ep3、15、16，
再用 best_dyn4 与 best_dyn4s 各训一条 ep12，看人体抖动修复有没有作用。09:50 前后用户转来这个请求。按 `agent-doc/plan-next-training-2026-10-12.md`
第 4a 节的授权（“你来为我进行决策并给我判断的理由”），已决定做这次试点，依据与 jev 记录见 9116bf3
（`results/decisions/jev_claims_t3dyn_pilot_1014.txt`）。本计划写做法、判据与判读方法。时间一律 UTC−6（MDT），服务器日志是 CST（MDT + 14 小时）。
第 1 版（cfe6976）经独立审查（Fable 5.1）为 GO WITH FIXES，第 2 版（84a4055）按审查意见修改，第 2 版再审为 GO WITH FIXES，第 3 版按第二轮意见修改，逐条处理见第 8 节。主要改动：对称判定的问题不只在 ep16，
ep3 同样适用；取消 ep16 的停手规则，改为在第 4 节预先登记判读方法（对称没确认的集跟上了只记“支持（分支待确认）”）；Q2 的门槛改为“疑似”，要补种子才算数。

## 1. 事实

- **两台机器**：ml40 的 t1yb 09:05 训完、09:32 评完，GPU 3 MiB、0%，没有长链标记（`results/t1x/status_t1yb_ml40_1014_0950.txt`、
  `results/ops/gpu_procs_ml40_1014_0950.txt`）。mf4090 上 t1xb 的最后一条 ep14 08:31 开训，09:45 到 180,006,912 步，训练、评测、候选三个长链标记都在，
  可用 87129 MB（`results/t1x/status_t1xb_mf4090_1014_0950.txt`）。按前几条的速度估，训练 10:50 前后结束，评测与导出 11:30 前后结束（估计）。
- **best_hm 上这 4 集都没跟上**：4096 世界、对照自己参考的 MP-SR，`t3-ep3`、`t3-ep15`（t3p4a）与 `t3-ep12`、`t3-ep16`（t3p4b）都是
  `w2048-cap4m-r3a-hm-mf4090`，都是 0.000；同集 Tier 2 变体 A（ml40，1000 万 buffer）是 ep3 0.806、ep15 0.987、ep12 0.988、ep16 0.938
  （`results/t3p4/eval_table_t3p4a.txt`、`results/t3p4/eval_table_t3p4b.txt`）。
- **要检验的假设**（另一位用户的交接 8107fef，`results/t3dyn/handoff_tier3_dynamics_8107fef.txt`）：best_hm 上训的 18 集里，跟上的 ep6、7、8
  与训到 0.5 的 ep21 物体转动违规都是 0；失败的 14 集里 12 集有转动违规，余下的 ep12、ep5 是根加速度最高的两集（117、111 m/s²）。只有 4 个正例，
  特征是事后挑的，交接文档自己写明只是待检验的假设。best_dyn4 把 ep3、15、16 的转动违规清零；best_dyn4s 在 best_dyn4 上只改人体（0.3 s 窗口的
  局部二次拟合），ep12、ep5 的根加速度降到 24、20 m/s²。29 集根加速度 p99 的中位数：best_dyn4 47.6、best_dyn4s 11.6、Tier 2 4.3 m/s²；物体违规帧
  6.33% 与 6.35%。
- **对称朝向**：best_dyn4 的修复记录里，ep16（喷壶）判出 24 个对称等价朝向，477 帧里 445 帧换了朝向；ep3（杯子）3 个，781 帧里 463 帧
  （`results/ops/t3_dyn_logs_ml40_1014_0730.txt`）。检查与修复用同一套对称：对称判错时，“转动违规清零”不能说明换出来的朝向分支对。
  判定方法（`results/t3dyn/sym_code_8107fef.txt`）：绕三个惯性主轴每 15° 试一次，转动后表面点到原表面的平均最近距离小于 min(1 cm, 最大半径的 5%)
  就算对称。平均值对手柄、扳机这类小部件不敏感：同一份记录里吸尘器、复活节篮、杯子、熨斗、手杖都判出 3 个，浇水壶、编织篮 7 个，球棒、碗、喷壶、
  锥桶 24 个，水瓶 26 个。ep3 的任务是“lift it by the handle”，左右手轮流拿（`results/site/task_table.txt`），手柄朝哪一边对手和物体的关系有影响。
  修复从第 0 帧的分支开始逐帧取最近的等价朝向，只保证朝向连续，不保证分支与画面一致。
- **文件**（ml40 只读记录 `results/ops/t3_episodes_ml40_1014_hm4.txt`、`…_dyn4.txt`、`…_dyn4s.txt`；并排对照 `results/t3dyn/support_meta_compare_1014.txt`）：
  4 集的 parquet 都与 best_hm 的不同；元数据的 sha256 与 best_hm 的相同；best_dyn4、best_dyn4s 的目录里只有 `data/` 与 `meta/`，没有支撑面，
  元数据指向的支撑面文件名与 best_hm 的相同。best_dyn4 的 4 个 parquet 共 3,607,380 字节，best_dyn4s 的 ep12 是 947,851 字节，合计约 4.56 MB。
- **哈希表**：网格与地面的 md5 取自今天 mf4090 官方 Tier 2 目录的只读记录（`results/ops/t2_inputs_mf4090_1014_dyn4.txt`、`…_dyn4s.txt`）。新表
  `stages/recovery/expect/t3dyn4_4_1014.tsv`（20 行）与 `t3dyn4s_1_1014.tsv`（5 行）里，parquet 以外的每一行都与 best_hm 的 `t3hm_29_1012.tsv` 相同
  （`results/t3dyn/expect_vs_hm_1014.txt`）。
- **重定向与转运**：ml40 没有重定向用的 `robotic-grounding` 镜像（`results/ops/docker_images_ml40_1014_1015.txt`），重定向只能在 mf4090 上做。
  ml40 的主机 Python 是 3.10.12，没有 `huggingface_hub`，也没有 `hf` 命令（`results/ops/ml40_hf_hub_probe_1014.txt`），所以 `tools/hf_transfer.py push`
  在 ml40 上跑不了，只能 `pull`。ml40 → mf4090 这一程现成的只有经 Mac 的管道（`stages/recovery/tier3_stage.sh`，约 25–30 KB/s）；
  mf4090 → ml40 有经 HF 私有仓库的 `stages/recovery/tier3_relay.sh`。
- **种子噪声**：Tier 1 在 mf4090 上 `w2048-cap4m-r3a` 种子 42 与 43 的 8 对 run，4096 世界 MP-SR 差的中位数 0.066，最大 0.348（ep29），超过 0.4 的
  0 对（`results/t3dyn/seed_pair_diff_t1_cap4m_r3a.txt`）；连同不带 r3a 的旧配置一共 13 对，最大 0.562，超过 0.4 的 2 对
  （`results/t3dyn/seed_pair_diff_t1_cap4m_all.txt`）。Tier 2 变体 A 的 5 对（ml40，1000 万 buffer）最大差 0.050，但 5 对都在 0.93 以上，
  接近上限，说明不了中段的噪声（`results/t3dyn/seed_pair_diff_t2_cap10m_r3a.txt`）。这些数只用来解读本次结果，不进任何 Tier 3 的数据或配置。
- **用时**（best_hm，mf4090）：5 条冒烟约 23 分钟；ep15 训了 2 小时 14 分、ep3 2 小时 2 分（`results/t3p4/health_t3p4a_mf4090.txt`），ep12 2 小时 33 分、
  ep16 1 小时 57 分（`results/t3p4/end_t3p4b_mf4090_1013_2354.txt`）；5 条评测 23 分钟。重定向每集 3–4 分钟（`results/t3hm/retarget_mf4090.txt`）。
  ml40 上没跑过 400 万 buffer 的 Tier 3 run，暂按 mf4090 的用时估。
- **10/13 记的重新开训条件（待定）**：另一位用户交出新版重建，训练前的门槛加上物体朝向与慢速漂移两项检查（`agent-doc/plan-d-t3hm-train-2026-10-12.md` 末尾）。
  另一位用户的动力学检查（`stages/recovery/tier3/gate/t3_dynamics_check.py`，在 `track2/tier3-recon` 上）有这两项，还没有接进我们的门槛。

## 2. 决定与理由

1. **5 条 run**：ep15、ep3、ep16 用 best_dyn4；ep12 用 best_dyn4 与 best_dyn4s 各一条。理由：这 4 集在 Tier 2 上 0.806–0.988、在 best_hm 上全是 0，
   机器人做得了这些任务，失败只能出在参考上；ep3、15、16 是转动违规被清零的集，正好检验转动这一项；ep12 在 best_hm 上没有转动违规、抖动最高，
   两版只差人体平滑，同机比较就是检验抖动这一项。全量重训 29 集约 60 个 GPU 小时，这 5 条约 11 个。
2. **配置照抄 best_hm 那批，只换参考**：变体 A、seed 42、2048 世界、3.5 亿步、400 万 buffer、支撑面开关按 best_hm（ep3、ep16 开，ep12、ep15 关）。
   队列行由 `stages/policy/make_copy_queue.py` 从 best_hm 的队列行照抄，只改 run 名、parquet 目录与 W&B 标签三处，`--check` 逐条列出改了什么
   （`results/t3dyn/copy_check_t3pdyn.txt`、`copy_check_t3qdyn.txt`，都是 `COPY_CHECK_OK`）。ml40 上也用 400 万 buffer：ep12 的 best_hm 基线就是 400 万。
3. **分两台**：mf4090 训 ep15 → ep3 → ep16（段名 `t3pdyn`），与 best_hm 基线同机同配置。三条都训，不设停手规则；ep3、ep16 的对称没确认时结果怎么算，
   第 4 节预先登记（跟上了记“支持（分支待确认）”，没跟上记“看不清”）；那段时间 mf4090 没有别的训练要跑。
   ml40 训 ep12 的 dyn4 → dyn4s（段名 `t3qdyn`），两版在同一台机器上比。理由：两台都空着时并行，结果早 4–5 小时；mf4090 在 t1xb 之后没有排好的 Tier 1 训练，
   Tier 1 最差几集的计划还没写（`agent-doc/plan-next-training-2026-10-12.md` 末尾 10/13 的记录：另写计划、审过再用 ml40），ml40 那两条约 5 小时，傍晚就空出来。
4. **支撑面沿用 best_hm 的**：best_dyn4、best_dyn4s 的目录里没有支撑面，元数据与 best_hm 的逐字节相同。拼目录时从 mf4090 上已拼好的 `runs/tier3/root_hm`
   复制，按今天 ml40 上 best_hm 交付目录的 sha256 核（`tier3_root.py --support-dir`、`tier3_expect.py --support-record`，第 3 节第 0 步）。
5. **转运**：人体层 4.56 MB 从 ml40 到 mf4090 走 Mac 管道（约 3 分钟），**要用户点头**（第 7 节第 1 条：数据转运的规矩是几 MB 以上走 HF，介于中间要先量再问；
   ml40 现在推不了 HF）。机器人层（重定向之后，约 0.4 GB）从 mf4090 到 ml40 走 HF（`tier3_relay.sh`）。`tier3_relay.sh` 按版本整目录转，
   best_dyn4 的 4 集都会转过去，ml40 只训其中的 ep12；多转的约 0.25 GB 不改代码。
6. **评测与导出照常**：评测链只评最终 checkpoint（4096 世界，对照这条 run 自己的参考），导出链导 1 个世界的轨迹。不提交 Kaggle。

## 3. 做法

**第 0 步（已做，与本计划第 1 版一起提交）**

- `tools/t3_episode_remote.sh`、`stages/recovery/tier3_pack_remote.sh` 的白名单加 `tier3_cari4d_f830_best_dyn4`、`…_best_dyn4s` 与各自的 `_suspect`（两处一起改）。
- `stages/recovery/tier3_expect.py` 加 `--support-record <记录>`：支撑面的行取另一份远端记录里的 sha256，只取主记录元数据指到的那几份。
- `stages/recovery/tier3_root.py` 加 `--support-dir <目录>`：支撑面从这个目录复制，按哈希表的 sha256 核，provenance 记 `support_source`。
- `stages/recovery/tier3_stage.sh` 加 `V2D_T3_SUPPORT_DIR=runs/tier3/root_<名>`，转给 `tier3_root.py --support-dir`；与 `V2D_T3_SUPPORT=delivery` 只能设一个。
- `stages/policy/make_copy_queue.py`（新）：照抄 best_hm 的队列行生成 `t3pdyn`、`t3qdyn` 两段的期望表、冒烟与正式队列、导出清单；`--check` 核对。
  段名以 `t3p`、`t3q` 开头，`arm_var_chain.sh` 不用改（`t3p*` 认作 mf4090、`t3q*` 认作 ml40，都是 Tier 3）。
- `tools/t3_record_compare.py`（新）：几份 `t3_episode_remote.sh` 记录按相对路径并排比 sha256。
- 测试：`test_make_copy_queue.py`（新）、`test_tier3_expect.py` 与 `test_tier3_root.py` 补用例；Mac 上连同 `test_make_var_queue.py`、`test_tier3_relay.py`
  都是 `ALL_OK`，三个改过的 shell 脚本 `bash -n` 通过（`results/t3dyn/tests_mac_1014.txt`）。
- 哈希表 `stages/recovery/expect/t3dyn4_4_1014.tsv`、`t3dyn4s_1_1014.tsv`：
  `python3 stages/recovery/tier3_expect.py results/ops/t3_episodes_ml40_1014_dyn4.txt results/ops/t2_inputs_mf4090_1014_dyn4.txt --support-record results/ops/t3_episodes_ml40_1014_hm4.txt`
  （dyn4s 同样，换成 `…_dyn4s.txt` 两份记录）。
- 队列：`python3 stages/policy/make_copy_queue.py t3pdyn`、`… t3qdyn`。
- jev：第 1 节里本计划新查的 10 条都核实（0.92–0.99），对照 5 道正常（`results/t3dyn/jev_claims_plan_1014.txt`；前两轮留作 `_run1`、`_run2`：
  一次是哈希表比对的证据里没带命令行，一次是三件事合成了一条说法）。两台机器的状态、best_hm 与 Tier 2 的分数、交接文档、对称朝向、种子噪声、
  镜像这几条在做决定时已核（11/11，对照 5 道正常，`results/decisions/jev_claims_t3dyn_pilot_1014.txt`）。
  第 2 版新补的 5 条（对称判定方法两条、各集对称数、ep3 的任务、Tier 2 的种子对）核实 0.88–0.98，对照 3 道正常
  （`results/t3dyn/jev_claims_plan_v2_1014.txt`；第 1 轮留作 `_run1`：两件事合成了一条说法，证据少抓了一行；第 2 轮 0.76–0.98 留作 `_run2`，
  代码记录重录、包进第 57 行之后重跑）。

**第 1–8 步（审查通过、mf4090 的 t1xb 三条链都结束之后；Mac 上、仓库根执行）**

1. 同步与测试。t1xb 的结束记录、健康记录与 Tier 1 的接力不在本计划里。两台都没有长链标记才同步：
   `scripts/dev/record ops/sync_mf4090_1014_<时分> scripts/dev/remote`、`V2D_ENV=ml40 scripts/dev/record ops/sync_ml40_1014_<时分> scripts/dev/remote`。
   两台各跑一次测试（`results/t3dyn/tests_mf4090.txt`、`tests_ml40.txt`）：
   `ssh -o BatchMode=yes mf4090 'cd ~/v2d/maniphys_lab_v2d_challenge && echo source $(cat .v2d-source-commit) && for f in stages/policy/test_make_copy_queue.py stages/recovery/test_tier3_expect.py stages/recovery/test_tier3_root.py; do echo "== $f"; python3 $f | tail -1; done && bash -n stages/recovery/tier3_stage.sh && bash -n stages/policy/arm_var_chain.sh && echo "bash -n ok"'`
   （ml40 换成 `/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge`）。`tier3_relay.sh` 在 Mac 上跑，它的测试只在 Mac 上跑（`results/t3dyn/tests_mac_1014.txt`）。
   同步之后 ml40 部署的就是本计划的提交；Tier 1 的接力与逐条选（`relay_t1x.sh`、`select_t1`）用这份部署，只写 `runs/` 下的目录，
   `t3qdyn` 在跑时也能做；要改代码的话等 `t3qdyn` 三条链结束再同步。
2. 拼目录（用户同意走 Mac 管道之后）：
   `V2D_T3_SUBDIR=tier3_cari4d_f830_best_dyn4 V2D_T3_SET=dyn4 V2D_T3_SUPPORT_DIR=runs/tier3/root_hm scripts/dev/record t3dyn/stage_dyn4_mf4090 stages/recovery/tier3_stage.sh t3dyn4_4_1014 3 12 15 16`
   `V2D_T3_SUBDIR=tier3_cari4d_f830_best_dyn4s V2D_T3_SET=dyn4s V2D_T3_SUPPORT_DIR=runs/tier3/root_hm scripts/dev/record t3dyn/stage_dyn4s_mf4090 stages/recovery/tier3_stage.sh t3dyn4s_1_1014 12`
3. 重定向（mf4090 的 tmux，照 10/12 best_hm 的做法；可用 ≥ 2500 MB 才开）：
   `scripts/dev/record t3dyn/retarget_launch_mf4090 ssh -o BatchMode=yes mf4090 'cd ~/v2d/maniphys_lab_v2d_challenge && A=$(df -m --output=avail . | tail -1) && echo "可用 $A MB" && [ "$A" -ge 2500 ] && ! tmux has-session -t v2d-t3dyn-retarget 2>/dev/null && tmux new-session -d -s v2d-t3dyn-retarget "V2D_T3_SET=dyn4 V2D_RECORD_TRACEBACK_OK=1 scripts/dev/record t3dyn/retarget_dyn4_mf4090 stages/retarget/eps.sh 3 3 12 15 16; V2D_T3_SET=dyn4s V2D_RECORD_TRACEBACK_OK=1 scripts/dev/record t3dyn/retarget_dyn4s_mf4090 stages/retarget/eps.sh 3 12" && sleep 20 && tmux ls | cut -d: -f1'`
   两份记录都以 `EPS_DONE` 结束后用 `scripts/dev/pull-results` 拉回。然后照 10/13 第 ④ 步，在 mf4090 的容器里（不占 GPU）对 5 个 parquet 跑
   `check_inputs.py`（parquet 能读、帧数与 fps、引用的资产与支撑面在容器内都在）：
   `scripts/dev/record t3dyn/check_inputs_mf4090 ssh -o BatchMode=yes mf4090 'cd ~/v2d/maniphys_lab_v2d_challenge && echo source $(cat .v2d-source-commit) && md5sum stages/policy/check_inputs.py && scripts/dev/in-flash-chord "python /repo/stages/policy/check_inputs.py $(ls runs/motion/tier3_dyn4/whole_body/soma/sequence_id=*/robot_name=g1/data.parquet runs/motion/tier3_dyn4s/whole_body/soma/sequence_id=*/robot_name=g1/data.parquet | sed s,^,/repo/, | tr "\n" " ")"; echo "check_inputs 退出码 $?"'`
4. 数一下要转的文件（只读）：
   `scripts/dev/record t3dyn/relay_counts_mf4090 ssh -o BatchMode=yes mf4090 'cd ~/v2d/maniphys_lab_v2d_challenge && for s in dyn4 dyn4s; do echo "$s $(find runs/tier3/root_$s runs/motion_src/tier3_$s runs/motion/tier3_$s -type f | wc -l)"; done'`
5. HF 中转。先在 `docs/hf/v2d-track2-transfer/README.md` 加两行（`t3dyn4_1014a`、`t3dyn4s_1014a`，状态写“上传中”），提交，
   `scp` 到 mf4090 的 `runs/hf_readme/v2d-track2-transfer.md`，照 10/13 的做法上传：
   `scripts/dev/record ops/hf_readme_v2d_track2_transfer_t3dyn tools/hf_remote.sh 'md5sum runs/hf_readme/v2d-track2-transfer.md; python3 runs/tools/hf_archive.py readme --repo Rongxuan-Zhou/v2d-track2-transfer --file runs/hf_readme/v2d-track2-transfer.md --message "README: t3dyn4_1014a and t3dyn4s_1014a uploading" --visibility private; python3 runs/tools/hf_archive.py whoami --repo Rongxuan-Zhou/v2d-track2-transfer --visibility private'`
   然后转发（文件数取第 4 步的）：
   `caffeinate -i scripts/dev/record t3dyn/relay_dyn4_ml40_hf stages/recovery/tier3_relay.sh dyn4 4 <文件数> t3dyn4_1014a`
   `caffeinate -i scripts/dev/record t3dyn/relay_dyn4s_ml40_hf stages/recovery/tier3_relay.sh dyn4s 1 <文件数> t3dyn4s_1014a`
   两次都 `RELAY_OK` 后，ml40 的容器里对转过去的 parquet 同样跑一次 `check_inputs.py`（记录 `t3dyn/check_inputs_ml40`，命令同第 3 步，
   主机与目录换成 ml40 的），再把 README 两行改为“已传、已核对”，提交、重新上传（记录 `ops/hf_readme_v2d_track2_transfer_t3dyn_relayed`）。
6. mf4090 起 `t3pdyn`（第 3 步之后就能做，不等第 5 步）：
   `scripts/dev/record t3dyn/cfgcheck_t3pdyn_mf4090 ssh -o BatchMode=yes mf4090 'cd ~/v2d/maniphys_lab_v2d_challenge && echo source $(cat .v2d-source-commit) && stages/policy/fc_config_check.sh stages/policy/queues/mf4090_t3pdyn_smoke.txt stages/policy/queues/mf4090_t3pdyn.txt'`
   `scripts/dev/record t3dyn/arm_dryrun_t3pdyn_mf4090 ssh -o BatchMode=yes mf4090 'cd ~/v2d/maniphys_lab_v2d_challenge && echo source $(cat .v2d-source-commit) && (nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; true) && V2D_ARM_DRYRUN=1 stages/policy/arm_var_chain.sh t3pdyn'`
   `scripts/dev/record t3dyn/arm_t3pdyn_mf4090 ssh -o BatchMode=yes mf4090 'cd ~/v2d/maniphys_lab_v2d_challenge && echo source $(cat .v2d-source-commit) && (nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; true) && stages/policy/arm_var_chain.sh t3pdyn'`
7. ml40 起 `t3qdyn`（第 5 步之后）：同第 6 步，主机换成 ml40、目录换成 `/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge`、段名 `t3qdyn`、记录名 `…_ml40`。
   起链要求 GPU 上没有别的进程；另一位用户若在用 ml40 的 GPU（交接文档写了要约 GPU 做逐帧评测），等它结束再起，不停别人的进程。
8. 对称朝向：不建停链标记（第 1 版的停手规则已取消，见第 8 节）。请另一位用户核对 ep3（杯子，3 个）与 ep16（喷壶，24 个）修复后的朝向分支
   与画面是否一致（手柄、扳机朝哪边），结果只用于第 4 节的判读和全量重训之前的核对，不影响这次起链。
9. 每段结束：拉回结果、健康记录（`chain_health_remote.sh`）、评测表——`stages/evaluate/eval_table.py` 把这段的 run 与同集的 best_hm run、Tier 2 run 并列
   （`results/t3dyn/eval_table_t3pdyn.txt`、`eval_table_t3qdyn.txt`）、按第 4 节判读、jev、执行记录、提交、报告。

## 4. 判据（执行前登记，不改）

- **第 0 步**：Mac 上 5 份测试 `ALL_OK`、`bash -n` 通过；`make_copy_queue.py --check` 两段都 `COPY_CHECK_OK`，每条只差 W&B 标签、run 名、parquet 目录（冒烟行只差后两处）；
  哈希表 parquet 以外的行与 `t3hm_29_1012.tsv` 相同。
- **第 1–7 步**：两台测试全过；两次 `check_inputs.py` 都没有缺失（退出码 0）；拼目录两次都 `TIER3_ROOT_OK`，`root_dyn4` 4 集、`root_dyn4s` 1 集，provenance 的 `support_source` 是 `runs/tier3/root_hm`；
  重定向两份记录都以 `EPS_DONE` 结束、5 行结果都没有 `FAIL:*`（有 `FAIL` 的集从队列里拿掉、重新生成、再核；`ALIGN` 或 `NOCONTACT` 照训，在报告里标出，
  并与 best_hm 同集的状态并列）；转发两次 `RELAY_OK`；配置展开通过、意外键 0；预演 `DRYRUN_OK`；起链 `ARMED`，起链记录里训练挂 `v040_p185_nfg`、
  评测与导出挂 `fc_8c778f9`；两台部署的 commit 相同。
- **每条 run**：冒烟过；正式 run 有 DONE、最后一步 349999104、看守扫描非有限 0；4096 世界评测完成。
- **Q1（转动违规是不是 best_hm 训不动的主因）**：训完的 ep3、ep15、ep16，对照各自参考的 4096 世界 MP-SR。先定每集算不算数：
  - ep15 照常算（2 个对称，只换了 8 帧）。
  - ep3、ep16：出结果之前另一位用户确认了修复后的朝向分支与画面一致，就照常算；确认为相反的分支，这一集不论高低都记“看不清”；
    没有确认时，≥ 0.5 算数但标“分支待确认”，< 0.5 不算，这一集记“看不清”。分支错了对跟踪的影响方向不定：手和物体对不上会更难跟，
    但手柄、扳机转离了手，伸手时不会撞上，策略改抱杯身也可能更好跟，所以没确认的集只能带标记算。
  - 冒烟没过、没训的集不算。

  再看算数的集：
  - 至少 2 集 ≥ 0.5：**支持**。其中用到了标“分支待确认”的集时记“支持（分支待确认）”，全量重训的计划不能把 Q1 当已定，
    要先核对分支。接着写剩下那些有转动违规的失败集用 best_dyn4 重训的计划（另审），GPU 与 Tier 1 怎么分到时再定。
  - 至少 2 集算数，而且都 < 0.1：**不支持**。不在 best_dyn4 上全量重训，先做逐帧终止分析（每个世界在第几帧、因为哪一项被终止），再谈 Tier 3 的下一轮训练。
  - 其余（包括算数的不到 2 集）：**看不清**，同样先做逐帧终止分析。
  ep12 dyn4 也与它的 best_hm 基线（0.000）并列报，但不计入 Q1：best_hm 的 ep12 没有转动违规。
- **Q2（人体平滑有没有用）**：ep12 的 MP-SR，dyn4s 减 dyn4：
  - ≥ 0.4 记“平滑疑似有用”。要拿 best_dyn4s 去全量重训，先给 ep12 的两版各补一条 seed 43，同向、差也 ≥ 0.4 才算数。
  - ≤ −0.4 记“平滑疑似变差”，同样要补种子才算数。
  - 绝对值 < 0.4 记“看不出差别”。dyn4 已经 ≥ 0.6 时差值到不了 0.4，这种情况记“平滑不是 ep12 的瓶颈”。
  - 看不出差别、不是瓶颈或没有补种子时，重训用 best_dyn4（改动少）。
  依据：r3a 同配置换种子的 8 对里最大差 0.348（`results/t3dyn/seed_pair_diff_t1_cap4m_r3a.txt`）；旧配置 13 对里有 2 对超过 0.4（最大 0.562），
  所以单集单种子的 0.4 只能算疑似。这些数只用来解读，不进任何 Tier 3 的数据或配置。
- **全量重训之前**（不论 Q1 怎么判）：凡是修复里换了朝向分支、物体又有手柄或扳机这类不对称部件的集，要先核对分支与画面一致，或在 best_dyn4 的
  下一版里改掉对称判定。这一条是第 1 节“对称朝向”那条事实带出来的，试点本身不检验它。
- **并列报**（只报，不据此改判据）：SP-SR、ADD-AUC、MPPE、三类失败比例，与同集 best_hm、Tier 2 的行并列；重定向的左右手接触帧、间隙与 best_hm 同集比。
- **停**：任何一步不满足就停在那一步，查原因，不改判据、不改配置重跑。

## 5. 试点不检验什么、风险

- **不检验分数**：评测对照的是 run 自己的参考，不是干净真值。“跟上”只说明参考训得动，不说明更接近真值。best_dyn4 改了物体轨迹（质心改动 p95 0.8–11 cm），
  本地能看的只有画面对齐 IoU（0.700 → 0.697）。真值只有提交才看得到；档位隔离不许拿 Tier 1 来比。
- **样本小**：Q1 只有 3 集，ep3、ep16 没确认对称时失败不算数，特征又是事后挑的；Q2 是 1 集 1 个种子，0.4 以上的差别也只算疑似。
- **机器**：ep12 的 best_hm 基线在 mf4090 上训，试点在 ml40 上训，配置相同、GPU 不同；Q2 的两条在同一台，不受影响。
- **对称判定**：判定对小部件不敏感，杯子的手柄、喷壶的扳机都可能被当成对称。修复后朝向连续，但分支可能与画面相反：
  对训练的影响方向不定（手和物体对不上会更难跟，手柄、扳机转离了手又可能更好跟），对分数的影响是朝向离真值更远（试点看不到）。
  第 4 节的判读与全量重训前的核对针对这一条。
- **门槛**：动力学检查还没接进我们的门槛；这次用另一位用户跑出的检查结果。全量重训之前要先接进来（10/13 的重新开训条件）。
- **用时**：ml40 上 400 万 buffer 没跑过，按 mf4090 估；ep12 在 mf4090 上训了 2 小时 33 分，是这几集里最慢的。
- **转运**：Mac 离线时第 2、5 步推后；第 2 步约 4.56 MB 走 Mac 管道（要用户同意），第 5 步经 HF，不碰另一位用户的目录。

## 6. 时间（估计）

- 11:30 前后 mf4090 的 t1xb 链结束；11:30–11:45 同步与测试；11:45 前后拼目录（约 3 分钟）；11:50–12:10 重定向 5 集；
  12:10–12:30 转发两版到 ml40。
- mf4090 约 12:20 起链：冒烟约 15 分钟，ep15 约 12:35–14:50，ep3 约 14:50–16:50，ep16 约 16:50–18:50，评测与导出约 19:10 结束。
  另一位用户对 ep3、ep16 朝向分支的核对最好在 19:10 之前，这样出结果时就能按第 4 节判读；晚了也不影响起链。
- ml40 约 12:40 起链：冒烟约 10 分钟，ep12 dyn4 约 12:50–15:20，dyn4s 约 15:20–17:50，评测约 18:05 结束。

## 7. 要用户定的

1. **人体层 4.56 MB 走 Mac 管道**（约 3 分钟）。数据转运的规矩是几 MB 以上走 HF、介于中间要先量再问；ml40 的主机 Python 没有 `huggingface_hub`，现在推不了 HF。
   建议同意。不同意的话，要先在 ml40 上找一个带 `huggingface_hub` 的环境（容器或虚拟环境）做推送，另写、另审，起链推后约 1–2 小时。
2. **对称朝向的核对**请另一位用户做：ep3（杯子，3 个对称，781 帧里 463 帧换了朝向）与 ep16（喷壶，24 个，477 帧里 445 帧）修复后的朝向分支与画面
   是否一致。不卡起链，只影响第 4 节的判读；全量重训之前，其他换了分支又有不对称部件的集也要核对。
3. 另一位用户要用 ml40 的 GPU 做逐帧评测的话，最好在 12:30 前用完；起链时 GPU 上有别的进程，`arm_var_chain.sh` 会停下，要等。

## 8. 审查

第 1 版（cfe6976）由 Fable 5.1 独立审查，只读，结论 **GO WITH FIXES**（1 MAJOR、3 MINOR、5 NIT）。审查核过、没有问题的部分：第 1 节的数字与记录一致；
两张哈希表从记录重新生成，与仓库里的逐字节相同；`--check` 两段 `COPY_CHECK_OK`，新 run 与 best_hm 源行只差 W&B 标签、run 名、parquet 目录；
重定向、共用层自 a5bdf6f、训练与评测脚本自 a629fbd 没有改动；第 3 节各命令的参数、环境变量与各脚本的前置检查对得上；常设规矩都守住了。

| # | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | MAJOR | ep3 是带手柄的杯子（任务 “lift it by the handle”），判出 3 个对称、463 帧换了朝向，同一判定对熨斗、吸尘器、手杖也给 3；第 1 版只对 ep16 设了确认，ep3 直接计入 Q1 | 采纳并扩大：第 1 节补判定方法与 29 集的对称数；第 4 节登记 ep3、ep16 没确认时失败不算数、跟上照算；全量重训之前要核对分支或改判定 |
| 2 | MINOR | ep16 的停链标记要人在 14:50–16:50 之间手动建，Mac 离线就建不上；ep3 冒烟没过时“正式 t3-ep3”不出现，触发条件失效 | 取消停手规则，ep16 照训（第 2 节第 3 条），判读在第 4 节预先登记 |
| 3 | MINOR | Q2 的 0.4 依据是 r3a 8 对最大差 0.348，旧配置有 2 对超过 0.4；dyn4 已经高时差值有上限 | 采纳：≥ 0.4 只记“疑似”，补 seed 43 才算数；dyn4 ≥ 0.6 时记“平滑不是 ep12 的瓶颈” |
| 4 | MINOR | ep16 被停时导出链对没训的 run 记失败、Q1 的门从 2/3 变 2/2、确认迟到怎么补训，都没写 | 取消停手规则后前两条不再出现；Q1 补“冒烟没过、没训的集不算”“算数的不到 2 集记看不清” |
| 5 | NIT | 拿 Tier 1 的种子差校准 Tier 3 的读数，容易被读成越线 | 采纳：注明只用于解读、不进 Tier 3 的数据或配置；补 Tier 2 变体 A 的 5 对（最大 0.050，都在 0.93 以上，说明不了中段） |
| 6 | NIT | `tier3_relay.sh` 在 Mac 上跑，服务器上跑它的测试不守任何东西，ml40 有没有 `shasum` 没记录过 | 采纳：服务器上只跑三份测试，relay 的测试留在 Mac |
| 7 | NIT | 10/13 转运后的第 ④ 步（容器里对 parquet 跑 `check_inputs.py`）没了 | 采纳：mf4090 重定向之后、ml40 转运之后各跑一次 |
| 8 | NIT | `t3qdyn` 起链后 ml40 约 5.5 小时不能同步，Tier 1 的 ml40 接力与逐条选没安排 | 采纳：第 1 步注明接力与逐条选用这次同步的部署、只写 `runs/`，可与 `t3qdyn` 并行；要改代码就等链结束 |
| 9 | NIT | `tools/t3_record_compare.py` 没有测试，而它的输出是第 1 节的依据 | 不补测试：审查从记录重新生成两张哈希表，与仓库里的逐字节相同，已交叉核过；记在这里 |

第 2 版（84a4055）再请同一位审查者只看改动，结论 **GO WITH FIXES**（1 MINOR、1 NIT）。审查核过：第 3 节不再有命令碰停链标记，各节都不再假设 ep16 会停；
两条 `check_inputs.py` 命令与 10/13 跑通的那条同构，目录名与 `V2D_T3_SET=dyn4`、`dyn4s` 的产出一致；第 1 版的 F2–F9 已处理，第 1 节新补的事实与记录一致。

| # | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | MINOR | “对称判错只会让手和物体对不上，不会让参考更好跟”不成立：错分支里手柄转离了手，伸手不会撞上，策略改抱杯身可能更好跟；另一位用户确认“分支相反”时，按原文仍照常算 | 采纳：三处删掉这句；没确认的集跟上了记“支持（分支待确认）”，全量重训不能把 Q1 当已定；确认相反的集两个方向都记“看不清” |
| 2 | NIT | `sym_code_8107fef` 的 sed 范围跳过了第 57 行 `SYM_STEP_DEG = 15` | 采纳：重录包进第 57 行（第一次留作 `_run1`） |

## 9. 执行记录

- 11:27 mf4090 的 t1xb 三条链都结束（`results/t1x/end_t1xb_mf4090_1014_1131.txt`、`results/t1x/health_t1xb_mf4090.txt`）；Tier 1 的接力与第二次逐条选
  另记（af011f6）。
- 11:33 两台都同步到 af011f6（`results/ops/sync_mf4090_1014_1133.txt`、`results/ops/sync_ml40_1014_1133.txt`）；三份测试两台都是 `ALL_OK`，
  `bash -n` 通过（`results/t3dyn/tests_mf4090.txt`、`results/t3dyn/tests_ml40.txt`）。
- 13:50 前后用户同意人体层走 Mac 管道（“可以走mac”）。13:55 先核对另一位用户的文件：dyn4 四集与 dyn4s 的 ep12 与上午的记录 sha256 逐个相同，
  `track2/tier3-recon` 仍停在 8107fef（`results/t3dyn/recheck_inputs_1355.txt`）。
- 13:55 拼目录两次都 `TIER3_ROOT_OK`：`root_dyn4` 4 集、`root_dyn4s` 1 集，5 集的 `support_source` 都是 `runs/tier3/root_hm`
  （`results/t3dyn/stage_dyn4_mf4090.txt`、`stage_dyn4s_mf4090.txt`、`root_provenance_eps_mf4090.txt`）。来源记录里另一位用户的部署版本仍写 ae06e75
  （与 best_hm 时相同），生成 best_dyn4、best_dyn4s 的代码按交接文档是 `track2/tier3-recon` 上的 7a4bf37 与 cabb668，部署标记没跟着更新，记在这里。
- 13:56–14:08 mf4090 重定向 5 集：两份记录都以 `EPS_DONE` 结束，5 行 `ok=1`、没有 `FAIL`，间隙 −0.4 到 0.2 mm（`results/t3dyn/retarget_dyn4_mf4090.txt`、
  `retarget_dyn4s_mf4090.txt`）。接触帧与 best_hm 同集并列（只报）：ep3 右手 421 帧（best_hm 512），左手两版都是 0；ep12 左 426、右 310（best_hm 353、414；
  dyn4s 426、307）；ep15 右手 422（399）；ep16 左手 182（180）。
- 14:10 mf4090 容器里 `check_inputs.py` 对 5 个 parquet 退出码 0（`results/t3dyn/check_inputs_mf4090.txt`）。
- 14:11 `t3pdyn` 配置展开 6 份、意外 0 个；预演 `DRYRUN_OK`（来历 af011f6，可用 86557 MB，训练挂 `v040_p185_nfg`，评测与导出挂 `fc_8c778f9`）；
  起链 `ARMED`（`results/t3dyn/cfgcheck_t3pdyn_mf4090.txt`、`arm_dryrun_t3pdyn_mf4090.txt`、`arm_t3pdyn_mf4090.txt`）。14:16 ep15 冒烟通过
  （715 帧，256 世界里非有限 0 个）。
- 14:12 中转仓库 README 加两行（上传中）并上传，`HF_README_OK`、仓库私有。14:13–14:18 转发：dyn4 `RELAY_OK`（74 个文件，上传 19 秒、下载 188 秒），
  dyn4s `RELAY_OK`（20 个文件），两端 sha256 清单逐行相同（`results/t3dyn/relay_dyn4_ml40_hf.txt`、`relay_dyn4s_ml40_hf.txt`）。
- 14:18 ml40 容器里 `check_inputs.py` 对 5 个 parquet 退出码 0（`results/t3dyn/check_inputs_ml40.txt`）；README 两行改为“已传、已核对”后重传，`HF_README_OK`
  （`results/ops/hf_readme_v2d_track2_transfer_t3dyn_relayed.txt`）。
- 14:20 `t3qdyn` 配置展开 4 份、意外 0 个；预演 `DRYRUN_OK`（来历 af011f6，可用 1,373,568 MB）；起链 `ARMED`，第一条冒烟 ep12 dyn4
  （`results/t3dyn/cfgcheck_t3qdyn_ml40.txt`、`arm_dryrun_t3qdyn_ml40.txt`、`arm_t3qdyn_ml40.txt`）。第 4 节“第 1–7 步”的判据全部满足。
- 估计：ml40 两条约 20:00–20:30 评完，mf4090 三条约 21:00–21:20 评完（按 best_hm 那批的用时）。
- 19:46 前后 ml40 的 `t3qdyn` 结束：dyn4 14:31–17:03、dyn4s 17:03–19:32 训练，随后评测与导出，非有限 0（`results/t3dyn/end_t3qdyn_ml40_1014_1949.txt`、
  `results/t3dyn/health_t3qdyn_ml40.txt`，结果在 1c5ef75）。对照各自参考的 4096 世界（`results/t3dyn/eval_table_t3qdyn.txt`）：ep12 dyn4 MP-SR 0.562、
  SP-SR 0.730、ADD-AUC 0.453、MPPE 13.38 cm、骨盆失败比例 0.292；dyn4s MP-SR 0.000、SP-SR 0.779、ADD-AUC 0.275、MPPE 8.65 cm、骨盆失败比例 0.973；
  同集 best_hm（mf4090）MP-SR 0.000，Tier 2 变体 A 0.988。Q2：dyn4s 减 dyn4 为 −0.562，不大于 −0.4，记“平滑疑似变差”，没补种子不算数，重训照规则用
  best_dyn4。ep12 dyn4 与 best_hm 并列报，不计入 Q1；best_hm 基线在 mf4090 上训、试点在 ml40 上训（第 5 节已记）。
- 20:57 mf4090 的 `t3pdyn` 结束：ep15 14:25–16:41、ep3 16:41–18:43、ep16 18:43–20:40 训练，评测 20:40–20:53，导出 20:53–20:56；完成 3、失败 0、发散 0，
  非有限 0，3 条导出都过核对（`results/t3dyn/end_t3pdyn_mf4090_1014_2100.txt`、`results/t3dyn/health_t3pdyn_mf4090.txt`）。对照各自参考的 4096 世界
  （`results/t3dyn/eval_table_t3pdyn.txt`，同集 best_hm 与 Tier 2 变体 A 并列）：

  | ep | dyn4 MP-SR | SP-SR | ADD-AUC | MPPE cm | 骨盆失败 | best_hm MP-SR | SP-SR | ADD-AUC | MPPE cm | 骨盆失败 | Tier 2 MP-SR |
  |---|---|---|---|---|---|---|---|---|---|---|---|
  | 15 | 0.000 | 0.000 | 0.305 | 22.91 | 1.000 | 0.000 | 0.000 | 0.310 | 22.19 | 0.994 | 0.987 |
  | 3 | 0.106 | 0.500 | 0.439 | 36.23 | 0.471 | 0.000 | 0.000 | 0.117 | 76.42 | 0.984 | 0.806 |
  | 16 | 0.000 | 0.000 | 0.344 | 55.08 | 1.000 | 0.000 | 0.000 | 0.009 | 87.04 | 1.000 | 0.938 |

  Q1 判读（第 4 节）：ep15 照常算，MP-SR 0.000；ep3、ep16 出结果前没有收到朝向分支的确认，MP-SR 都低于 0.5，按规则不算，各记“看不清”。算数的只有
  ep15 一集，不到 2 集，Q1 记**看不清**。按第 4 节：不在 best_dyn4 上全量重训，先做逐帧终止分析（每个世界在第几帧、因为哪一项被终止），再谈 Tier 3 的
  下一轮训练；逐帧终止分析的做法另写计划、审过再做。并列报（不改判据）：ep3 的 SP-SR 0 → 0.500、ADD-AUC 0.117 → 0.439、MPPE 76.42 → 36.23 cm、骨盆失败
  比例 0.984 → 0.471；ep16 的 ADD-AUC 0.009 → 0.344、MPPE 87.04 → 55.08 cm，骨盆失败比例仍是 1.000；ep15 各项基本不变。jev 9 条核实（0.97–0.99），
  对照 4 道正常（`results/t3dyn/jev_claims_t3dyn_result_1014.txt`）。两台 GPU 都已空出，本计划不再起新链。
- 21:30 更正：另一位用户分支上的 4dd545b（10-14 18:54 MDT 提交，早于 mf4090 出结果）与 3e38561 写明 dyn4 的对称判据有误，ep03、ep16 的 dyn4 朝向错
  （转错的帧 461/781、472/477；`results/t3dyn/handoff_tier3_dynamics_3e38561.txt`）。上一条“出结果前没有收到朝向分支的确认”不准：确认已在分支上，
  只是当时没拉。按第 4 节，这两集属“确认为相反的分支”，不论高低都记“看不清”；算数的仍只有 ep15，Q1 仍是看不清，结论不变。ep12、ep15 不受这个判据
  影响（同一份交接）。同一份交接还写明：检查端的转动判据也用平均最近点距离，各版本的转动违规计数偏低，“转动违规与成败”的对照要在判据修好后重算；
  ep06 的 MP-SR 是 0.198（此前误作 0.815，那是 chord_sr），是这个假设的反例；best_dyn5、best_dyn6 不要用；best_dyn7 是新候选（新对称判据、第 3 步
  稳健化），21:14 起在 ml40 上用 CPU 跑重定向、门槛与动力学检查（`results/ops/t3_queue_ml40_1014_2125.txt`），尚未交付。两台 GPU 21:30 都空着
  （`results/ops/gpu_procs_mf4090_1014_2125.txt`、`results/ops/gpu_procs_ml40_1014_2125.txt`）。
- 10/15 09:23 ml40 的 Q2 补种子（`t3qdyn_s43`，计划 `agent-doc/plan-overnight-2026-10-15.md`）结束：dyn4 s43 04:07–06:38、dyn4s s43 06:38–09:08 训练，
  评测 09:09–09:20，导出 09:21–09:23；训练完成 2、失败 0、发散 0，看守扫描非有限 0，导出 world_count 4096、non_finite_worlds 0
  （`results/q2/health_t3qdyn_s43_ml40.txt`；其中 `DIVERGE_IN_CHAIN … 1` 数的是 `DAY2_TRAIN_DONE（… 发散 0）` 这一行本身）。两种分数并列，4096 世界为主
  （`results/t3dyn/eval_table_t3qdyn_s43.txt`；导出那 1 局见 `results/ml40/submission/exports/cand_t3_t3qdyn*_ml40_*`）：

  | run | 4096 世界 MP-SR / SP-SR / ADD-AUC / MPPE / 骨盆失败比例 | 导出那 1 局 MP / SP / ADD-AUC / MPPE |
  |---|---|---|
  | dyn4 s43 | 0.000 / 0.094 / 0.239 / 21.84 cm / 0.998 | 0 / 1 / 0.235 / 8.73 cm |
  | dyn4s s43 | 0.000 / 0.000 / 0.233 / 23.11 cm / 1.000 | 0 / 0 / 0.233 / 22.31 cm |
  | dyn4 s42（10/14） | 0.562 / 0.730 / 0.453 / 13.38 cm / 0.292 | 1 / 1 / 0.542 / 2.86 cm |
  | dyn4s s42（10/14） | 0.000 / 0.779 / 0.275 / 8.65 cm / 0.973 | 0 / 1 / 0.259 / 6.58 cm |

  Q2 判读（第 4 节，以及 plan-overnight 第 4 节新登记的两条）：s43 这一对 dyn4s 减 dyn4 为 0.000，绝对值小于 0.4，记“两种子不一致，看不出差别”；
  s42 那一对的“平滑疑似变差”没有得到 s43 的印证，不算数。s43 的 dyn4 低于 0.6，“不是瓶颈”不适用。按登记，全量重训若做仍用 best_dyn4（这一对只供参考）。
  并列报（计划外，不改判据）：同一配置的 dyn4，seed 42 是 0.562、seed 43 是 0.000，差 0.562，大于 Tier 1 r3a 同配置 8 对种子的最大差 0.348
  （`results/t3dyn/seed_pair_diff_t1_cap4m_r3a.txt`，只用来解读）。试点里唯一的正面结果“ep12 在 best_dyn4 上跟上 56%”换种子没有复现，
  不能当作 best_dyn4 有用的证据；seed 43 两版的骨盆失败比例都接近 1。
  jev 5 条核实（0.98–0.99），对照 4 道正常（`results/t3dyn/jev_claims_q2_s43.txt`；规格 `agent-doc/experiments/2026-10-15-q2-s43.claims.json`）。
  第一次核对整批作废：假对照“dyn4 s43 的 MP-SR 是 0.562”得 0.92，jev 把 s43 与 s42 两行认混了；改为按种子分别取证据行、加一道读错列的假对照后重跑
  （作废那次的输出没有留下：`scripts/dev/record` 重跑成功时删掉同名的 `.failed`。那次 5 条说法 0.94–0.99，失败的就是这道假对照
  `ctl_false_s43 P(supported)=0.92 CONTROL(false) FAILED`，另两道对照正常）。
