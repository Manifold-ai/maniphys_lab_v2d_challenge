# 计划：Tier 3 动力学修复版（best_dyn4、best_dyn4s）的训练试点（2026-10-14，第 1 版）

10/14 09:21 MDT 另一位用户在 `track2/tier3-recon` 上推送了交接文档的更新（8107fef），随后提出用 best_dyn4 重训 ep3、15、16，
再用 best_dyn4 与 best_dyn4s 各训一条 ep12，看人体抖动修复有没有作用。09:50 前后用户转来这个请求。按 `agent-doc/plan-next-training-2026-10-12.md`
第 4a 节的授权（“你来为我进行决策并给我判断的理由”），已决定做这次试点，依据与 jev 记录见 9116bf3
（`results/decisions/jev_claims_t3dyn_pilot_1014.txt`）。本计划写做法、判据与停手规则。时间一律 UTC−6（MDT），服务器日志是 CST（MDT + 14 小时）。
第 1 版还没有经过独立审查（第 8 节）。

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
  （`results/ops/t3_dyn_logs_ml40_1014_0730.txt`）。检查与修复用同一套对称：对称判错时，ep16 上“转动违规清零”不能说明问题。
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
  （`results/t3dyn/seed_pair_diff_t1_cap4m_all.txt`）。
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
3. **分两台**：mf4090 训 ep15 → ep3 → ep16（段名 `t3pdyn`），与 best_hm 基线同机同配置；ep16 放最后，等对称朝向的确认（第 4 节的停手规则）。
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

**第 1–8 步（审查通过、mf4090 的 t1xb 三条链都结束之后；Mac 上、仓库根执行）**

1. 同步与测试。t1xb 的结束记录、健康记录与 Tier 1 的接力不在本计划里。两台都没有长链标记才同步：
   `scripts/dev/record ops/sync_mf4090_1014_<时分> scripts/dev/remote`、`V2D_ENV=ml40 scripts/dev/record ops/sync_ml40_1014_<时分> scripts/dev/remote`。
   两台各跑一次测试（`results/t3dyn/tests_mf4090.txt`、`tests_ml40.txt`）：
   `ssh -o BatchMode=yes mf4090 'cd ~/v2d/maniphys_lab_v2d_challenge && echo source $(cat .v2d-source-commit) && for f in stages/policy/test_make_copy_queue.py stages/recovery/test_tier3_expect.py stages/recovery/test_tier3_root.py stages/recovery/test_tier3_relay.py; do echo "== $f"; python3 $f | tail -1; done && bash -n stages/recovery/tier3_stage.sh && bash -n stages/policy/arm_var_chain.sh && echo "bash -n ok"'`
   （ml40 换成 `/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge`）。
2. 拼目录（用户同意走 Mac 管道之后）：
   `V2D_T3_SUBDIR=tier3_cari4d_f830_best_dyn4 V2D_T3_SET=dyn4 V2D_T3_SUPPORT_DIR=runs/tier3/root_hm scripts/dev/record t3dyn/stage_dyn4_mf4090 stages/recovery/tier3_stage.sh t3dyn4_4_1014 3 12 15 16`
   `V2D_T3_SUBDIR=tier3_cari4d_f830_best_dyn4s V2D_T3_SET=dyn4s V2D_T3_SUPPORT_DIR=runs/tier3/root_hm scripts/dev/record t3dyn/stage_dyn4s_mf4090 stages/recovery/tier3_stage.sh t3dyn4s_1_1014 12`
3. 重定向（mf4090 的 tmux，照 10/12 best_hm 的做法；可用 ≥ 2500 MB 才开）：
   `scripts/dev/record t3dyn/retarget_launch_mf4090 ssh -o BatchMode=yes mf4090 'cd ~/v2d/maniphys_lab_v2d_challenge && A=$(df -m --output=avail . | tail -1) && echo "可用 $A MB" && [ "$A" -ge 2500 ] && ! tmux has-session -t v2d-t3dyn-retarget 2>/dev/null && tmux new-session -d -s v2d-t3dyn-retarget "V2D_T3_SET=dyn4 V2D_RECORD_TRACEBACK_OK=1 scripts/dev/record t3dyn/retarget_dyn4_mf4090 stages/retarget/eps.sh 3 3 12 15 16; V2D_T3_SET=dyn4s V2D_RECORD_TRACEBACK_OK=1 scripts/dev/record t3dyn/retarget_dyn4s_mf4090 stages/retarget/eps.sh 3 12" && sleep 20 && tmux ls | cut -d: -f1'`
   两份记录都以 `EPS_DONE` 结束后用 `scripts/dev/pull-results` 拉回。
4. 数一下要转的文件（只读）：
   `scripts/dev/record t3dyn/relay_counts_mf4090 ssh -o BatchMode=yes mf4090 'cd ~/v2d/maniphys_lab_v2d_challenge && for s in dyn4 dyn4s; do echo "$s $(find runs/tier3/root_$s runs/motion_src/tier3_$s runs/motion/tier3_$s -type f | wc -l)"; done'`
5. HF 中转。先在 `docs/hf/v2d-track2-transfer/README.md` 加两行（`t3dyn4_1014a`、`t3dyn4s_1014a`，状态写“上传中”），提交，
   `scp` 到 mf4090 的 `runs/hf_readme/v2d-track2-transfer.md`，照 10/13 的做法上传：
   `scripts/dev/record ops/hf_readme_v2d_track2_transfer_t3dyn tools/hf_remote.sh 'md5sum runs/hf_readme/v2d-track2-transfer.md; python3 runs/tools/hf_archive.py readme --repo Rongxuan-Zhou/v2d-track2-transfer --file runs/hf_readme/v2d-track2-transfer.md --message "README: t3dyn4_1014a and t3dyn4s_1014a uploading" --visibility private; python3 runs/tools/hf_archive.py whoami --repo Rongxuan-Zhou/v2d-track2-transfer --visibility private'`
   然后转发（文件数取第 4 步的）：
   `caffeinate -i scripts/dev/record t3dyn/relay_dyn4_ml40_hf stages/recovery/tier3_relay.sh dyn4 4 <文件数> t3dyn4_1014a`
   `caffeinate -i scripts/dev/record t3dyn/relay_dyn4s_ml40_hf stages/recovery/tier3_relay.sh dyn4s 1 <文件数> t3dyn4s_1014a`
   两次都 `RELAY_OK` 后 README 两行改为“已传、已核对”，提交、重新上传（记录 `ops/hf_readme_v2d_track2_transfer_t3dyn_relayed`）。
6. mf4090 起 `t3pdyn`（第 3 步之后就能做，不等第 5 步）：
   `scripts/dev/record t3dyn/cfgcheck_t3pdyn_mf4090 ssh -o BatchMode=yes mf4090 'cd ~/v2d/maniphys_lab_v2d_challenge && echo source $(cat .v2d-source-commit) && stages/policy/fc_config_check.sh stages/policy/queues/mf4090_t3pdyn_smoke.txt stages/policy/queues/mf4090_t3pdyn.txt'`
   `scripts/dev/record t3dyn/arm_dryrun_t3pdyn_mf4090 ssh -o BatchMode=yes mf4090 'cd ~/v2d/maniphys_lab_v2d_challenge && echo source $(cat .v2d-source-commit) && (nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; true) && V2D_ARM_DRYRUN=1 stages/policy/arm_var_chain.sh t3pdyn'`
   `scripts/dev/record t3dyn/arm_t3pdyn_mf4090 ssh -o BatchMode=yes mf4090 'cd ~/v2d/maniphys_lab_v2d_challenge && echo source $(cat .v2d-source-commit) && (nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; true) && stages/policy/arm_var_chain.sh t3pdyn'`
7. ml40 起 `t3qdyn`（第 5 步之后）：同第 6 步，主机换成 ml40、目录换成 `/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge`、段名 `t3qdyn`、记录名 `…_ml40`。
   起链要求 GPU 上没有别的进程；另一位用户若在用 ml40 的 GPU（交接文档写了要约 GPU 做逐帧评测），等它结束再起，不停别人的进程。
8. ep16（第 4 节的停手规则）：train 日志出现 `正式 t3-ep3-w2048-cap4m-r3a-dyn4-mf4090` 之后，还没收到另一位用户对喷壶 24 个对称朝向的确认，就建停链标记：
   `scripts/dev/record t3dyn/stop_t3pdyn_after_ep3_mf4090 ssh -o BatchMode=yes mf4090 'cd ~/v2d/maniphys_lab_v2d_challenge && grep -q "正式 t3-ep3-w2048-cap4m-r3a-dyn4-mf4090" runs/logs/t3pdyn_train_mf4090.log && date "+%F %T %Z" && touch runs/.chain-stop-t3pdyn_train_mf4090 && ls -l runs/.chain-stop-t3pdyn_train_mf4090 && tail -2 runs/logs/t3pdyn_train_mf4090.log'`。
   ep3 训完之前收到确认，就删掉标记（`t3dyn/unstop_t3pdyn_mf4090`）。链结束后标记一律删掉、留记录。
9. 每段结束：拉回结果、健康记录（`chain_health_remote.sh`）、评测表——`stages/evaluate/eval_table.py` 把这段的 run 与同集的 best_hm run、Tier 2 run 并列
   （`results/t3dyn/eval_table_t3pdyn.txt`、`eval_table_t3qdyn.txt`）、按第 4 节判读、jev、执行记录、提交、报告。

## 4. 判据（执行前登记，不改）

- **第 0 步**：Mac 上 5 份测试 `ALL_OK`、`bash -n` 通过；`make_copy_queue.py --check` 两段都 `COPY_CHECK_OK`，每条只差 W&B 标签、run 名、parquet 目录（冒烟行只差后两处）；
  哈希表 parquet 以外的行与 `t3hm_29_1012.tsv` 相同。
- **第 1–7 步**：两台测试全过；拼目录两次都 `TIER3_ROOT_OK`，`root_dyn4` 4 集、`root_dyn4s` 1 集，provenance 的 `support_source` 是 `runs/tier3/root_hm`；
  重定向两份记录都以 `EPS_DONE` 结束、5 行结果都没有 `FAIL:*`（有 `FAIL` 的集从队列里拿掉、重新生成、再核；`ALIGN` 或 `NOCONTACT` 照训，在报告里标出，
  并与 best_hm 同集的状态并列）；转发两次 `RELAY_OK`；配置展开通过、意外键 0；预演 `DRYRUN_OK`；起链 `ARMED`，起链记录里训练挂 `v040_p185_nfg`、
  评测与导出挂 `fc_8c778f9`；两台部署的 commit 相同。
- **每条 run**：冒烟过；正式 run 有 DONE、最后一步 349999104、看守扫描非有限 0；4096 世界评测完成。
- **Q1（转动违规是不是 best_hm 训不动的主因）**：训完的 ep3、ep15、ep16（ep16 被停就只看前两集），对照各自参考的 4096 世界 MP-SR：
  - 至少 2 集 ≥ 0.5：**支持**。接着写剩下那些有转动违规的失败集用 best_dyn4 重训的计划（另审），GPU 与 Tier 1 怎么分到时再定。
  - 全部 < 0.1：**不支持**。不在 best_dyn4 上全量重训，先做逐帧终止分析（每个世界在第几帧、因为哪一项被终止），再谈 Tier 3 的下一轮训练。
  - 其余：**看不清**，同样先做逐帧终止分析。
  ep12 dyn4 也与它的 best_hm 基线（0.000）并列报，但不计入 Q1：best_hm 的 ep12 没有转动违规。
- **Q2（人体平滑有没有用）**：ep12 的 MP-SR，dyn4s 减 dyn4 ≥ 0.4 记“平滑有用”，≤ −0.4 记“平滑变差”，绝对值 < 0.4 记“看不出差别”。
  依据：r3a 同配置换种子的 8 对里最大差 0.348（`results/t3dyn/seed_pair_diff_t1_cap4m_r3a.txt`）；旧配置有过 0.562，单集单种子只能看出大差别。
  看不出差别时，重训用 best_dyn4（改动少）。
- **并列报**（只报，不据此改判据）：SP-SR、ADD-AUC、MPPE、三类失败比例，与同集 best_hm、Tier 2 的行并列；重定向的左右手接触帧、间隙与 best_hm 同集比。
- **停**：任何一步不满足就停在那一步，查原因，不改判据、不改配置重跑。

## 5. 试点不检验什么、风险

- **不检验分数**：评测对照的是 run 自己的参考，不是干净真值。“跟上”只说明参考训得动，不说明更接近真值。best_dyn4 改了物体轨迹（质心改动 p95 0.8–11 cm），
  本地能看的只有画面对齐 IoU（0.700 → 0.697）。真值只有提交才看得到；档位隔离不许拿 Tier 1 来比。
- **样本小**：Q1 只有 3 集（可能只有 2 集），特征是事后挑的；Q2 是 1 集 1 个种子，只能看出 0.4 以上的差别。
- **机器**：ep12 的 best_hm 基线在 mf4090 上训，试点在 ml40 上训，配置相同、GPU 不同；Q2 的两条在同一台，不受影响。
- **ep16 的对称**：喷壶如果有扳机，24 个对称朝向就不对，ep16 的参考可能在不等价的朝向之间切换。没确认就不训（停手规则）。
- **门槛**：动力学检查还没接进我们的门槛；这次用另一位用户跑出的检查结果。全量重训之前要先接进来（10/13 的重新开训条件）。
- **用时**：ml40 上 400 万 buffer 没跑过，按 mf4090 估；ep12 在 mf4090 上训了 2 小时 33 分，是这几集里最慢的。
- **转运**：Mac 离线时第 2、5 步推后；第 2 步约 4.56 MB 走 Mac 管道（要用户同意），第 5 步经 HF，不碰另一位用户的目录。

## 6. 时间（估计）

- 11:30 前后 mf4090 的 t1xb 链结束；11:30–11:45 同步与测试；11:45 前后拼目录（约 3 分钟）；11:50–12:10 重定向 5 集；
  12:10–12:30 转发两版到 ml40。
- mf4090 约 12:20 起链：冒烟约 15 分钟，ep15 约 12:35–14:50，ep3 约 14:50–16:50，ep16 约 16:50–18:50，评测与导出约 19:10 结束。
  ep16 被停的话，评测约 17:15 结束。**ep16 的确认要在 16:50 前后之前**（ep3 开训之后、训完之前处理停链标记）。
- ml40 约 12:40 起链：冒烟约 10 分钟，ep12 dyn4 约 12:50–15:20，dyn4s 约 15:20–17:50，评测约 18:05 结束。

## 7. 要用户定的

1. **人体层 4.56 MB 走 Mac 管道**（约 3 分钟）。数据转运的规矩是几 MB 以上走 HF、介于中间要先量再问；ml40 的主机 Python 没有 `huggingface_hub`，现在推不了 HF。
   建议同意。不同意的话，要先在 ml40 上找一个带 `huggingface_hub` 的环境（容器或虚拟环境）做推送，另写、另审，起链推后约 1–2 小时。
2. **ep16 的对称朝向**请另一位用户确认（喷壶 24 个对称等价朝向、477 帧里 445 帧换了朝向是否合理）。16:50 前后之前没有确认，ep16 不训。
3. 另一位用户要用 ml40 的 GPU 做逐帧评测的话，最好在 12:30 前用完；起链时 GPU 上有别的进程，`arm_var_chain.sh` 会停下，要等。

## 8. 审查

第 1 版待独立审查（GO、GO WITH FIXES 或 NO GO），结论与逐条处理写在这里。

## 9. 执行记录

（未开始）
