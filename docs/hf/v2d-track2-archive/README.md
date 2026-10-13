---
tags:
- archive
- v2d-challenge
---

# v2d-track2-archive

NVIDIA V2D Challenge Track 2（G1 + Dex3，FlashCHORD FlashSAC 训练）的 checkpoint 归档。这些文件来自训练机 mf4090，
在训练机上已不再需要或暂时不需要，归档到这里是为了腾出训练机的磁盘空间。仓库自 2026-10-11 起公开。
训练数据是 V2D Challenge 发布的比赛数据；比赛规则写明，公开发布的比赛数据按 CC BY 4.0 使用与分享。

## 内容

| 批次 | 归档日期（UTC-6） | 内容 | 文件数 | 大小 | 训练机上的本地副本 |
|---|---|---|---|---|---|
| 1 | 2026-10-01 | `state_<步数>.safetensors`：冒烟 run 的全部 state，正式 run 除最后一份以外的 state；共 38 条 run | 39 | 6.24 GB | 10/1 已删除 |
| 2 | 2026-10-08 | `policy_<步数>.safetensors`：52 条 run 的中间 checkpoint，每条 26 份（步 10000384–260009984） | 1352 | 6.57 GB | 10/8 已删除 |
| 3a | 2026-10-11 | 第 3 批计划 299 个文件（11.55 GB），提交到 125 个时账号的私有存储额度用完。已提交的是：28 条已完成的正式 run 各自的最后一份 `state_<步数>.safetensors`，1 条 run 除最后一份以外的 3 份 state，4 条 run 的 94 份 `policy_<步数>.safetensors` 中间 checkpoint（步 10000384–260009984） | 125 | 5.42 GB | 10/11 已删除 |
| 3b | 2026-10-11 | 第 3 批其余 174 个，仓库改为公开后上传：34 条已完成的正式 run 各自的最后一份 state，6 条 run 的 140 份 policy 中间 checkpoint（步 10000384–260009984） | 174 | 6.12 GB | 10/11 已删除 |
| 4 | 2026-10-12 | 11 条已完成的正式 run（Tier 3 的 9 条、Tier 1 的 2 条）：各自 26 份 `policy_<步数>.safetensors` 中间 checkpoint（步 10000384–260009984）与最后一份 `state_<步数>.safetensors` | 297 | 3.15 GB | 10/13 已删除 |

- `state`：续训用的训练状态；续训时须与同一步数的 `policy` 成对。
- `policy`：策略网络参数，供导出与评测使用。训练过程中约每 1000 万步保存一份。
- 第 2 批的 52 条 run 在训练机上各保留最新的 9 份 policy（步 270010368–349999104）。导出使用最后一份；评测器报错时，
  导出链最多向前回退 8 份，因此这 9 份留在本地。第 3、4 批的 policy 按同样的规则挑选，最新的 9 份不归档。
- 第 3 批起，已完成的正式 run 的最后一份 state 也归档。训练链不续训已完成的 run，这份 state 只在续训时需要；
  同一步数的 policy 留在训练机上，导出与评测不受影响。
- 文件名中的数字是训练步数。run 目录名标明了档位（`t1`、`t2`、`t3`）、episode（`ep18`）、并行世界数（`w2048`）、
  replay buffer 上限（`cap4m`）和训练机（`mf4090`），其余后缀的含义见代码仓库中的实验记录。

## 目录结构

```
README.md
.gitattributes
mf4090/                                   # 来源训练机
  runs/flash_chord/<run>/                 # 与训练机上代码仓库根目录下的相对路径相同
    state_<步数>.safetensors              # 第 1、3 批
    policy_<步数>.safetensors             # 第 2、3 批
```

## 与训练机上的记录对应

训练机删除本地副本之前，先在每个 run 目录里写 `ARCHIVED.json`（追加，不覆盖）。下面是
`runs/flash_chord/t1-ep16-w2048-cap4m-mf4090/ARCHIVED.json` 的原文（时间为训练机使用的北京时间）：

```json
[
 {
  "time": "2026-10-01T23:52:35+0800",
  "files": [
   {
    "file": "state_340013056.safetensors",
    "step": 340013056,
    "size": 160121036,
    "sha256": "9da3ff26f01bad0590c0fc4621bcbf087453ba34bcfcef7966b33acf828a800e",
    "repo": "Rongxuan-Zhou/v2d-track2-archive",
    "path_in_repo": "mf4090/runs/flash_chord/t1-ep16-w2048-cap4m-mf4090/state_340013056.safetensors"
   }
  ]
 }
]
```

每完成一批的归档与删除，就追加一条记录。第 1 批删除后，state 已删空的冒烟 run 还写入了 `STATE_PRUNED`（训练链的约定）。
第 2 批的记录时间是北京时间 2026-10-09 01:27，即 UTC-6 的 10/8 11:27；第 1、2 批都归档过的 run 有 19 条。
第 3a 批的记录时间是北京时间 2026-10-11 23:21，即 UTC-6 的 10/11 09:21；第 3a 批的 28 条 run 中，`ARCHIVED.json` 里有 1 条记录的 4 条、
2 条记录的 15 条、3 条记录的 9 条。第 3b 批的记录时间是北京时间 2026-10-12 11:56，即 UTC-6 的 10/11 21:56；第 3b 批的 35 条 run 中，
`ARCHIVED.json` 里有 1 条记录的 5 条、2 条记录的 20 条、3 条记录的 10 条。

## 下载与放回

仓库公开，下载不需要 token。`HF_ENDPOINT` 应未设置或等于 https://huggingface.co：训练机上代码仓库的 `.env` 把它指向下载镜像，
镜像上有没有本仓库的文件没有核实。训练机无法直连 huggingface.co，需经代理。

恢复到训练机时，在 Mac 的代码仓库根目录用 `tools/hf_remote.sh` 执行。它从 `.env` 读取 token 与代理地址，经 stdin 传到训练机，
把 `HF_ENDPOINT` 固定为 https://huggingface.co，命令在训练机的代码仓库根目录运行。

```bash
# 某条 run 的全部归档文件先下到 runs/restore/，再移回原路径 runs/flash_chord/<run>/
tools/hf_remote.sh 'hf download Rongxuan-Zhou/v2d-track2-archive --include "mf4090/runs/flash_chord/<run>/*" --local-dir runs/restore && mv runs/restore/mf4090/runs/flash_chord/<run>/*.safetensors runs/flash_chord/<run>/'
```

2026-10-08 在 mf4090 上用这条命令实测下载过 1 个文件，sha256 与清单一致（代码仓库 `results/ops/hf_restore_test_mf4090.txt`）。

在其他机器上，确认 `HF_ENDPOINT` 未设置或等于 https://huggingface.co，再用同样的 `hf download` 命令，或者用 Python：

```python
from huggingface_hub import hf_hub_download

# 单个文件；下载到 runs/restore/mf4090/runs/flash_chord/<run>/policy_<步数>.safetensors
p = hf_hub_download("Rongxuan-Zhou/v2d-track2-archive",
                    "mf4090/runs/flash_chord/<run>/policy_<步数>.safetensors",
                    repo_type="model", local_dir="runs/restore")
```

## 校验

下载后计算 sha256，与 `ARCHIVED.json` 中同名文件的 `sha256` 比较；网页文件信息中的 LFS SHA256 是同一个值。

```bash
sha256sum runs/flash_chord/<run>/policy_<步数>.safetensors
```

上传时做了两道核对：全部文件的大小与 sha256 逐个与清单比对（第 1 批 39 / 39，第 2 批 1352 / 1352）；
随后随机下载部分文件重算 sha256（第 1 批 3 个，第 2 批每条 run 1 个，共 52 个），全部一致。
第 3a 批的 125 个文件：大小与 sha256 全部一致（125 / 125）；抽查下载 33 个，即 28 条 run 各自的最后一份 state，
加上另有其他文件的 5 条 run 各随机 1 个，全部一致。删除训练机上的本地副本之前，又对仓库核对了一遍，仍是 125 / 125 一致。
第 3b 批的 174 个文件：大小与 sha256 全部一致（174 / 174）；抽查下载 40 个，即 34 条 run 各自的最后一份 state，加上另有 policy 的 5 条 run
各随机 1 个、只有 policy 的 1 条 run 随机 1 个，全部一致。删除训练机上的本地副本之前，又对仓库核对了一遍，仍是 174 / 174 一致；
训练机上的 174 个文件也逐个重算了 sha256，与清单一致。
第 4 批的 297 个文件：大小与 sha256 全部一致（297 / 297）；抽查下载 22 个，即 11 条 run 各自的最后一份 state 与随机 1 份 policy，全部一致。
删除训练机上的本地副本之前，又对仓库核对了两遍，都是 297 / 297 一致；删除时训练机上的 297 个文件也逐个重算了 sha256，与清单一致。

## 相关代码与记录

以下路径都在代码仓库（私有）中。

- `tools/hf_archive.py`：挑选文件（plan）、上传、核对、抽查、删除，以及上传本 README（readme）。
- `tools/hf_archive_run.sh`：在训练机上按顺序跑上传、核对、抽查与删除，任何一步不过就停。
- `tools/hf_remote.sh`：带凭据在训练机上执行命令，凭据只经 stdin 传递，`HF_ENDPOINT` 固定为 https://huggingface.co。
- `tools/hf_archive_report.py`：汇总核对、抽查与本地状态。
- 计划：`agent-doc/plan-hf-archive-2026-10-01.md`（第 1 批）、`agent-doc/plan-hf-archive-policies-2026-10-08.md`（第 2 批）、
  `agent-doc/plan-hf-archive-batch3-2026-10-10.md`（第 3 批）、`agent-doc/plan-hf-archive-batch4-2026-10-12.md`（第 4 批）。
- 记录：`results/ops/hf_archive_*.txt`。
