# 交接：第三台训练机 l40n 的环境（11/02）

2026-11-02 20:4x MST 起，分支 track2/p1-training。rxzhou 11/02 晚上给了第三台机器，并同意现在装驱动与 docker（“现在就装”）。

## 机器

- 别名 `l40n`（Mac 的 `~/.ssh/config`，原文件备份 `~/.ssh/config.bak_1102`），118.195.147.51，用户 `ubuntu`，钥匙与 mf4090、ml40 相同。`ubuntu` 有免密 sudo，机器只有这一个用户。
- GPU：nvidia-smi 报 **NVIDIA L40**（不是 L40S），46068 MiB，与 ml40 显存相同；rxzhou 说明 FP16/8 算力比 L40S 低，同样步数会慢。
- Ubuntu 22.04.5，内核 5.15.0-190；48 核、184 GB 内存；系统盘 197 GB（装完前空 184 GB）。rxzhou：“数据就别全部dump过去了”。
- 仓库副本 `~/v2d/maniphys_lab_v2d_challenge`（`scripts/dev/init-remote` 建，`.env` 0600，与另两台同一做法）；Mac 上 `.env.l40n`（git 忽略），`V2D_ENV=l40n scripts/dev/remote` 同步。

## 已完成

1. 主机环境（`deploy/l40n/setup_host.sh`，日志 `~/setup_host.log`）：厂商镜像开机时的驱动安装没装完（`/var/log/nvidia-installer.log` 停在 initramfs，`nvidia` 模块不在），改用 Ubuntu 源的 `nvidia-headless-580-server` 580.178.04（ml40 是 580.126.20），modprobe 直接成功，不用重启；docker.io 29.1.3；nvidia-container-toolkit 1.20.1。11/03 11:57 CST SETUP_HOST_DONE。
2. `/etc/docker/daemon.json` 加腾讯镜像源 `https://mirror.ccs.tencentyun.com`，与 ml40 相同。
3. mf4090 上 `deploy/l40n/stage_env_tars.sh l40n_env_1102` 打 3 个 tar（STAGE_OK）：官方工具包 33129dd 的 `flash_chord` 与 `source`、FlashCHORD 副本 `v040_p185_nfg_oo` 与 `v040_p185_nfg`、`runs/motion/tier2` 与 `tier3`，合计 3.68 GB；经 HF 私有传输仓 `Rongxuan-Zhou/v2d-track2-transfer` 标签 `l40n_env_1102` 转（`docs/hf/v2d-track2-transfer/README.md` 加了一行）。

## 未完成与下一步

1. HF 上传完成（mf4090 `runs/logs/hf_push_l40n_env_1102.log` 最后一行 HF_PUSH_OK 5）后，l40n 上 `tools/hf_remote.sh` 带 `V2D_ENV=l40n` 跑 `python3 tools/hf_transfer.py pull`，要 HF_PULL_OK，再按 `TARS.sha256` 核对、解包到与 mf4090 相同的相对位置（工具包进 `third_party/video_to_data/robotic_grounding/`，副本进 `~/v2d/fc_src/`，参考轨迹进 `runs/motion/`）。
2. 用同一 Dockerfile 构建 `flash_chord:latest`（`V2D_BUILD_DIRECT=1 scripts/dev/build-flash-chord`，基础镜像已拉）；构建后在容器里跑 `stages/policy/deps_freeze.py`，与 ml40 镜像的输出逐行比较，不同就不训。
3. 一条冒烟测速度；第一份训练活另写计划并经独立复核后再开。
