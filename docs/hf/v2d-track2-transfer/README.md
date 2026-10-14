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
| `t3dyn4_1014a` | 2026-10-14 | mf4090 → ml40 | Tier 3 动力学修复版 best_dyn4（ep3、12、15、16）的档目录 `runs/tier3/root_dyn4`、转换结果 `runs/motion_src/tier3_dyn4`、重定向结果 `runs/motion/tier3_dyn4`；ml40 只训其中的 ep12。状态：上传中 | 74 | 约 328 MB |
| `t3dyn4s_1014a` | 2026-10-14 | mf4090 → ml40 | best_dyn4s（在 best_dyn4 上加人体时间平滑）ep12 的 `runs/tier3/root_dyn4s`、`runs/motion_src/tier3_dyn4s`、`runs/motion/tier3_dyn4s`。状态：上传中 | 20 | 约 118 MB |

## 目录结构

```
<标签>/
  MANIFEST.sha256          # 这个标签下全部数据文件的 sha256（sha256sum 格式，路径相对训练机上的代码仓库根目录）
  runs/...                 # 与训练机上的相对路径完全相同
```

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

## 保留

接收端核对通过、对应的训练用完之后，这里的副本删不删另定。
