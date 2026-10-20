---
tags:
- v2d-challenge
- transfer
---

# v2d-track2-transfer

NVIDIA V2D Challenge Track 2（G1 + Dex3，FlashCHORD FlashSAC 训练）训练机之间的中转仓库。两台训练机之间没有直连，
经本地电脑转发又太慢，所以要在机器之间搬的中间数据先从发送端传到这里，再由接收端下载、按 sha256 清单逐个核对。
仓库是私有的，只用于中转，不是数据发布。内容由比赛数据派生（重建、转换、重定向的结果），不公开。

## 内容

| 标签 | 上传日期（UTC-6） | 发送端 → 接收端 | 内容 | 文件数 | 大小 |
|---|---|---|---|---|---|
| `smoke_1013` | 2026-10-13 | mf4090 → ml40 | 冒烟：一个文本文件与一个 LFS 文件，验证上传、经代理下载、跳转到 CDN 这条路 | 2 | 约 64 KB |
| `t3hm_1013a` | 2026-10-13 | mf4090 → ml40 | Tier 3 最终交付版（best_hm）的档目录 `runs/tier3/root_hm`、转换结果 `runs/motion_src/tier3_hm`、重定向结果 `runs/motion/tier3_hm`；29 集（不含 ep28）。状态：已传、已核对（ml40 收到 523/523，两端 sha256 逐行相同，已挪到位） | 523 | 2.40 GB |
| `t3dyn4_1014a` | 2026-10-14 | mf4090 → ml40 | Tier 3 动力学修复版 best_dyn4（ep3、12、15、16）的档目录 `runs/tier3/root_dyn4`、转换结果 `runs/motion_src/tier3_dyn4`、重定向结果 `runs/motion/tier3_dyn4`；ml40 只训其中的 ep12。状态：已传、已核对（ml40 收到 74/74，两端 sha256 逐行相同，已挪到位） | 74 | 约 328 MB |
| `t3dyn4s_1014a` | 2026-10-14 | mf4090 → ml40 | best_dyn4s（在 best_dyn4 上加人体时间平滑）ep12 的 `runs/tier3/root_dyn4s`、`runs/motion_src/tier3_dyn4s`、`runs/motion/tier3_dyn4s`。状态：已传、已核对（ml40 收到 20/20，两端 sha256 逐行相同，已挪到位） | 20 | 约 118 MB |
| `t3kfix_5_1016` | 2026-10-16 | ml40 → mf4090 | k-fix 新参考（按标定内参重新表达的 `tier3_kfix_F`）ep0、18、24、26、29 的 parquet、元数据与部署版本，放在 `<标签>/pack/` 下；接收端由 `stages/recovery/tier3_stage_hf.sh` 按哈希表逐个核对后拼进 `runs/tier3/root_kfix`。状态：已传、已核对（11/11） | 11 | 4.8 MB |
| `t3v2s_20_1016` | 2026-10-16 | ml40 → mf4090 | ep20 的 v2 参考加交付版方块桌面（`<标签>/pack/`），拼进 `runs/tier3/root_v2s`。状态：已传、已核对（3/3） | 3 | 0.7 MB |
| `t3gb3_11_1017` | 2026-10-17 | ml40 → mf4090 | 另一位用户的 gb3 交付版（标定内参，`tier3_cari4d_gb_best_dr2s_dyn7`）ep0、6、7、8、18、20、21、22、24、26、29 的 parquet、元数据、支撑面与部署版本（`<标签>/pack/`），拼进 `runs/tier3/root_gb3`。状态：已传、已核对（34/34） | 34 | 10.2 MB |
| `t3gb4_11_1019` | 2026-10-19 | ml40 → mf4090 | 另一位成员的 gb4 交付版（标定内参、人体按 PoseInversion 重解，`tier3_cari4d_gb4_best_dr2s_dyn7`）ep0、6、7、8、18、20、21、22、24、26、29 的 parquet、元数据、支撑面与部署版本（`<标签>/pack/`），拼进 `runs/tier3/root_gb4`。状态：已传、已核对（34/34） | 34 | 11.8 MB |
| `t12replay_1020` | 2026-10-20 | mf4090 → ml40 | Tier 2 ep4、ep25、ep1 的参考回放 checkpoint（`smoke-t2-ep{4,25,1}-w2048-cap4m-r3a-sd-mf4090/policy_409600.safetensors`，零残差），在 ml40 上做摔倒诊断（计划 `agent-doc/plan-t12replay-2026-10-20.md`）。状态：待传 | 3 | 约 15 MB |
| `t3gb3_1017a` | 2026-10-17 | mf4090 → ml40 | gb3 的档目录 `runs/tier3/root_gb3`、转换结果 `runs/motion_src/tier3_gb3`、重定向结果 `runs/motion/tier3_gb3`；11 集（ep0、6、7、8、18、20、21、22、24、26、29）。状态：已传、已核对（ml40 收到 199/199，两端 sha256 逐行相同，已挪到位） | 199 | 850.5 MB |

## 目录结构

```
<标签>/
  MANIFEST.sha256          # 这个标签下全部数据文件的 sha256（sha256sum 格式，路径相对训练机上的代码仓库根目录）
  runs/...                 # 与训练机上的相对路径完全相同
```

`tier3_stage_hf.sh` 转的标签（`t3kfix_5_1016`、`t3v2s_20_1016`、`t3gb3_11_1017`、`t3gb4_11_1019`）下面是 `pack/`：发送端打包解开的文件（`DEPLOYED`、`data/`、`meta/`、`support_surface/`），接收端按哈希表核对后才拼进档目录。

## 下载与校验

接收端在代码仓库根目录执行（`hf_transfer.py` 在训练机上的副本放在 `runs/tools/`；凭据只经环境变量 `HF_TOKEN` 传入，不写在命令行里）：

```bash
mkdir runs/.relay_tier3_hm.partial
python3 runs/tools/hf_transfer.py pull --repo Rongxuan-Zhou/v2d-track2-transfer --tag t3hm_1013a --dest runs/.relay_tier3_hm.partial
```

`pull` 只用 Python 标准库：先下载 `MANIFEST.sha256`，再逐个下载文件，边下边算 sha256，与清单不同就隔几秒重下，最多 3 次，仍不同就停。
token 只发给 huggingface.co 本身，跳转到 CDN 时不带。
全部一致时最后一行是 `HF_PULL_OK <文件数>`。接收端随后还要把整份 sha256 清单与发送端现场列出的清单逐行比对，
核对集数、档位、支撑面，才把目录挪到最终位置（`stages/recovery/tier3_relay.sh`）。

## 与代码仓库的对应

- 上传与下载：`tools/hf_transfer.py`（`push` 在发送端，`pull` 在接收端）。
- 整套转发与核对：`stages/recovery/tier3_relay.sh`；计划与判据：`agent-doc/plan-d-t3hm-train-2026-10-12.md` 第 8 节。
- 每次转发的记录在 `results/t3hm/` 下（`relay_ml40_hf.txt` 等）；10/14 的两个标签见 `agent-doc/plan-t3dyn-pilot-2026-10-14.md` 第 3 节第 5 步，记录在 `results/t3dyn/` 下。
- 10/16 的两个标签见 `agent-doc/plan-t3-kfix-2026-10-16.md` 方案 4，记录 `results/t3kfix/stage_hf_mf4090.txt`、`stage_hf_v2s_mf4090.txt`；10/17 的 gb3 标签见 `agent-doc/plan-t3-gb3-switch-2026-10-17.md` 做法 2，记录在 `results/t3gb3/` 下。

## 保留

接收端核对通过、对应的训练用完之后，这里的副本删不删另定。
