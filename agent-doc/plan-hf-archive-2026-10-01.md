# 计划：mf4090 旧 state 归档到 Hugging Face 私有仓库，核对后删除（2026-10-01，第 2 版：按 Fable 5.1 审查修改）

用户 10/1 的要求：“存储空间问题可以考虑上传到HF”，并给了账号 https://huggingface.co/Rongxuan-Zhou 和一个写权限 token。
时间一律 UTC-6。

## 事实

- mf4090 系统盘 Tier 2 开链时剩 6969 MB，08:11 剩 5438 MB；这一批靠冒烟 state 删除开关按估算放得下，之后的批次不够。
- 候选（`tools/hf_archive.py plan`，`results/ops/hf_archive_plan_mf4090.txt`，清单 `runs/hf_archive_manifest_mf4090.json` 在 mf4090 上）：
  39 个文件、38 个 run、6.24 GB。冒烟的 state 3.04 GB，正式 run 里较旧的 state 3.20 GB（ctrl-snackbox、resumetest 与 Tier 1 的 t1-*）。
  每个文件记了大小与 sha256。
- 规则：只看有 DONE 的 run，跳过名字里有 `t2-` 的（Tier 2 第 1 批在用）；冒烟删全部 state，正式 run 留步数最大的那份 state；policy、日志、评测结果不动。
- 路线：两台服务器直连 huggingface.co 超时，经 Mac `.env` 的 `V2D_PROXY` 能连（401，约 0.5 秒，`results/t2/hf_proxy_route_check.txt`）。
  token 在 Mac `.env`（600），`hf auth whoami` 返回 Rongxuan-Zhou。mf4090 的宿主 Python 有 huggingface_hub 1.32.0。
- 链在跑时不能同步，工具按 `runs/tools/` 的惯例 scp 过去、核对 md5。

## 做法

1. 上传：私有模型仓库 `Rongxuan-Zhou/v2d-track2-archive`，路径 `mf4090/runs/flash_chord/<run>/state_<步数>.safetensors`。
   清单里的文件硬链接进 `runs/hf_stage/mf4090/`（不多占盘），`upload_large_folder` 上传，可断点续传。
   token、代理经 stdin 进环境变量，`HF_ENDPOINT` 显式设成 https://huggingface.co（服务器 `.env` 里的 HF_ENDPOINT 指向下载镜像）。
   在 mf4090 上用 setsid nohup 跑，日志 `runs/logs/hf_archive_upload.log`，Mac 断开不影响。
2. 核对：`verify` 列出仓库里每个文件的大小与 LFS sha256，与清单逐个比，全部一致才往下走，结果落盘到 `results/ops/`。
   这个 sha256 是上传时客户端算的，只证明“仓库里有标着这个哈希的对象”，所以再 `spotcheck`：随机下载 3 个回来本地重算 sha256。
3. 删除：`delete --yes` 只删核对一致的文件；删之前再查一次 DONE、本地 sha256 没变、不是正式 run 的最终 state。
   冒烟目录 state 删光后写 `STATE_PRUNED`（同训练链的约定，旧冒烟重判时仍有效）；每个 run 目录写 `ARCHIVED.json` 记下文件在仓库里的位置。
   最后删掉暂存目录的硬链接，空间才真正释放。

## 判据（执行前登记）

- 上传前仓库必须是私有的，不是就停。
- 核对：39 个文件的大小与 sha256 全部一致，且随机抽查的 3 个下载后 sha256 一致，才执行删除；有一个不一致，就一个都不删。
- 删除后：mf4090 可用空间增加约 6.2 GB；正式 run 仍各有一份最终 state；t2-* 目录不受影响。训练链同时在写、按 `V2D_KEEP_STATES=1`
  剪旧 state，所以判据写成：删除期间 t2 目录里消失的只能是 state_*.safetensors，其他文件一个都不能少（`tools/hf_archive_run.sh`）。

## 审查与处理（第 2 版）

Fable 5.1 独立审查：GO WITH FIXES，没有 BLOCKER。
- MAJOR 删除时先删文件、后写 ARCHIVED.json 与 STATE_PRUNED，且只在这一轮删到东西时才写，中途断了重跑会漏写 STATE_PRUNED，旧冒烟重判出错
  → 改成先写记录再删，STATE_PRUNED 的条件不依赖这一轮删没删到（测试覆盖“中途断了重跑”）。
- MAJOR 不查 HF_ENDPOINT，服务器 `.env` 把它指向下载镜像，带 token 的请求可能经第三方转发 → 没设或等于 https://huggingface.co 才继续。
- MAJOR 核对只证明客户端声明的哈希 → 删除前加 `spotcheck`，随机下载 3 个文件本地重算，删除要求抽查通过。
- MINOR 正式 run 的“最终 state”不查完整性 → 改用与 ckpt_latest.py 相同的完整性判断，找不到完整的一份整个 run 不动。
- MINOR 上传并发默认 cpu/2 → 设 2。
- MINOR 代理地址带用户名密码 → 日志落盘前过滤含 `@` 的行。
测试：`tools/test_hf_archive.py`（挑文件规则、各道闸、先写记录再删、中途断了重跑），Mac 上全过。

测速（10/1 09:27 CST 23:27）：1 个文件 160 MB 用时 0.7 分钟，约 4 MB/s；全量 6.24 GB 预计约 25 分钟。

## 风险

- 代理带宽未知，先拿 1 个文件（160 MB）测速，再放全量。
- 上传在训练进行时做，只占网络与少量 CPU，不碰 GPU。
- token 在对话里出现过，用户可在归档后作废重建。
