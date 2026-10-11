# 计划：Tier 3 simreg 版本 17 集的重定向与 P2′（mf4090，不训练；2026-10-11，第 1 版）

时间一律为 UTC-6。流程与 f830 那次相同（`agent-doc/plan-t3-v2-retarget18-2026-10-10.md`，已经 Fable 5.1 审查），这里只写差异。

## 1. 事实

- 重建数据的提供方 10/11 告知（经用户转告，原话）：“我现在目录里有一个simreg版本，相对f830版本，改动主要是把人体随场景一起缩放，
  以及把第二机位的五集（ep12, 14 ,16, 25 ,28）配准到主机位了。我看你现在写的结果里面，ep12,14是穿入最多的，这个新版本可能可以修正这个问题。
  以及有4集（3，7，16，25）因为悬空问题没过门槛，这4集在我这边都属于位姿跟丢的比例相对偏高的，我现在在跑的每帧配准应该对这个有点帮助。”
  另：ep21 单机位、未配准，先跳过。每帧重新配准在 ml40 上排队，约占卡 14–24 小时，结果另出版本，不在本计划内。
- 现用版本 f830（`tier3_v2`）18 集的 P2′（`results/t3p2/p2_18.txt`）：过 10 集；不过 8 集，|间隙| 依次是 ep3 90.0 mm（悬空）、ep5 34.9（穿地）、
  ep7 710.9（悬空）、ep9 31.6（穿地）、ep12 63.5（穿地）、ep14 79.3（穿地）、ep16 238.3（悬空）、ep25 728.6（悬空）。
- simreg 目录（ml40 上 `runs/tier3_cari4d_f830_simreg`）有 20 集，与 f830 的 20 集相同；ep28 在 `_suspect` 里，不在本计划内。
- A 段（只读分析）已做：
  - 转发 20 集到 mf4090 的 `runs/tier3/incoming/float_1011_simreg/ok`（`results/t3float/pack_1011_simreg.txt`，对方部署版本 ae06e75）。
    ep21 的 parquet 修改时间是 UTC 10/11 18:27（即 12:27），在转发期间被改过，其余 19 集是 UTC 10/10 21:29–23:43。
  - `t3_float_facts.py --all-rest --offset-gate 30`（`results/t3float/gate_simreg_ok20_mf4090.txt`）：OFFSET_GATE_PASS，地面上 14 集，
    常数模型 o = −4.8 ± 3.9 mm（f830 那次见 `results/t3float/gate_f830_ok20_mf4090.txt`）。
- B.1 只读核对：18 集的那份（`results/ops/t3_episodes_ml40_1011_simreg_18.txt`）在 ep21 被改之前读的；去掉 ep21 重跑 17 集
  （`results/ops/t3_episodes_ml40_1011_simreg_17.txt`），与 A 段比对 `SHA_MATCH 17/17`、`INPUTS_SAME 34/34`（`results/t3simreg/sha_match_17.txt`）。
  官方 Tier 2 输入的 md5 按 17 集重取（`results/ops/t2_inputs_mf4090_1011_17.txt`，51 个文件）。哈希表 `stages/recovery/expect/t3simreg_17_1011.tsv`，
  85 行（parquet、元数据、网格、地面、支撑面各 17）。
- 代码：只有转发与核对脚本的白名单加了 simreg 目录（5d9f1f2），`tier3_stage.sh`、`tier3_root.py`、`eps.sh`、`p2_table.py` 没有改动。
- mf4090 22 核，训练时负载约 1。重定向是 CPU 一次性容器、并发 3，f830 那次每集 80–151 秒，18 集约 1.0 GB。t3p3c 同时在训练（约 1.5 GB）。

## 2. 做法（不训练）

17 集：ep0 3 5 7 9 12 14 15 16 17 18 20 22 23 25 26 29（f830 的 18 集去掉 ep21）。

1. 哈希表与 t3p3c 的队列一起提交、同步到 mf4090（有长链标记时不能同步，所以赶在 t3p3c 起链之前）。
2. `V2D_T3_SUBDIR=tier3_cari4d_f830_simreg V2D_T3_SET=simreg stages/recovery/tier3_stage.sh t3simreg_17_1011 <17 集>`，拼进 `runs/tier3/root_simreg`
   （`results/t3simreg/stage17_mf4090.txt`）。随后只读核对三个档目录的 `meta/episodes_metadata.jsonl` 的行数与修改时间（`results/t3simreg/stage17_check_mf4090.txt`）。
3. mf4090 的 tmux `v2d-t3simreg-retarget17` 里跑
   `V2D_T3_SET=simreg V2D_RECORD_TRACEBACK_OK=1 scripts/dev/record t3simreg/retarget17_mf4090 stages/retarget/eps.sh 3 <17 集>`：
   转换写到 `runs/motion_src/tier3_simreg`，重定向写到 `runs/motion/tier3_simreg`。与 t3p3c 同时运行。
4. 拉回结果，`stages/retarget/p2_table.py results/t3simreg/retarget17_mf4090.txt --no-contact 29 --a-phase results/t3float/gate_simreg_ok20_mf4090.txt`
   （`results/t3simreg/p2_17.txt`），与 f830 的 `results/t3p2/p2_18.txt` 逐集并列（只报），过 jev（带对照题），提交，回报。

## 3. 判据（执行前登记，同 f830 那次）

- **拼目录**：拼目录的记录里有 `V2D_T3_SET=simreg` 与 `TIER3_ROOT_OK`；`runs/tier3/root_simreg/meta/episodes_metadata.jsonl` 有 17 行、修改时间在拼目录之后；
  `runs/tier3/root_v2` 仍是 20 行、`runs/tier3/root` 仍是 2 行，修改时间都不变。不满足就停。哈希表核对不符时 `tier3_root.py` 什么也不写，停下重新核对。
- **重定向的目录**：记录的第一行正文是 `目录 runs/motion_src/tier3_simreg、runs/motion/tier3_simreg`。不是就停，结果不判读。
- **P2′**：重定向后 |间隙| ≤ 30 mm（正负都算）且至少一只手有接触，记“过”；否则“不过”；结果行是 `FAIL:*` 或没有结果行，记“失败”，不重试。
  ep29 的接触一条不适用，只按间隙判。阈值不因结果调整。
- **只报**：每集 simreg 与 f830 的间隙、接触帧数、IK 残差中位并列；`SURFACE_TO_FLOOR`；过 P2′ 的集数与集号。
- **磁盘**：重定向前可用不到 2500 MB 不起；t3p3c 不因磁盘停链（链在可用不到 1200 MB 时停）。
- 这一步不训练。simreg 过 P2′ 的集训不训、已用 f830 训过的集要不要换 simreg 重训，由用户定（待定）。

## 4. 已知限制

- P2′ 只说明重定向后物体静置时贴着支撑面、手有接触，不预言训练能不能跟上。f830 过 P2′ 的 ep20、ep29、ep15 训练后都没跟上。
- 评分对照的是干净的多视角真值，本地看不到（档位隔离），simreg 与 f830 哪一版更接近真值，P2′ 回答不了。
- ml40 上只经 stdin 跑两个只读脚本，不同步、不起长进程；提供方的目录在变（ep21 转发期间被改），拼目录时按哈希表核对，不符就停。

## 5. 时间（估计）

拼目录要从 ml40 经 Mac 再转一次（A 段 20 集约 15 分钟）；重定向 17 集约 25–45 分钟；汇总、jev 与记录约 15 分钟。约 14:30 结束。

## 执行记录
