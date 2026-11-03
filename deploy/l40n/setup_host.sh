#!/usr/bin/env bash
# 新 L40 机（l40n，118.195.147.51，Ubuntu 22.04，用户 ubuntu）的主机环境：NVIDIA 驱动、docker、nvidia-container-toolkit。
# rxzhou 11/02 20:4x MST 同意现在装。厂商镜像开机时的驱动安装没装完（/var/log/nvidia-installer.log 停在 initramfs），这里改用
# Ubuntu 源（mirrors.tencentyun.com）里的 580 服务器版驱动，与 ml40 同一大版本（ml40 是 580.126.20）。
# 用法（在 l40n 上）：sudo bash setup_host.sh > ~/setup_host.log 2>&1；每一步结束写一行 STEP_OK <名字>，最后一行 SETUP_HOST_DONE 或 SETUP_HOST_FAIL <步骤>。
# 装完驱动先试 modprobe；模块载不上就在日志里写 NEED_REBOOT，由人决定什么时候重启。
set -uo pipefail
fail() { echo "SETUP_HOST_FAIL $*"; exit 1; }
[ "$(id -u)" = 0 ] || fail "要 root"
export DEBIAN_FRONTEND=noninteractive
echo "=== $(date '+%F %T %Z') start, kernel $(uname -r)"

apt-get update -qq || fail apt-update
apt-get install -y -qq "linux-headers-$(uname -r)" nvidia-headless-580-server nvidia-utils-580-server || fail driver
echo "STEP_OK driver $(dpkg-query -W -f='${Version}' nvidia-utils-580-server)"

if modprobe nvidia 2>&1 && nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader; then
  echo "STEP_OK modprobe"
else
  echo "NEED_REBOOT 驱动装好了，模块现在载不上"
fi

apt-get install -y -qq docker.io docker-buildx || fail docker   # buildx：Dockerfile 用 RUN --mount，要 BuildKit（11/03 第一次构建时缺它，补装）
systemctl enable --now docker || fail docker-service
usermod -aG docker ubuntu || fail docker-group
echo "STEP_OK docker $(docker --version)"

KEYRING=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --batch --yes --dearmor -o "$KEYRING" || fail toolkit-key
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed "s#deb https://#deb [signed-by=${KEYRING}] https://#g" > /etc/apt/sources.list.d/nvidia-container-toolkit.list || fail toolkit-list
apt-get update -qq || fail apt-update-2
apt-get install -y -qq nvidia-container-toolkit || fail toolkit
nvidia-ctk runtime configure --runtime=docker || fail ctk-configure
systemctl restart docker || fail docker-restart
echo "STEP_OK toolkit $(dpkg-query -W -f='${Version}' nvidia-container-toolkit)"

echo "=== $(date '+%F %T %Z') SETUP_HOST_DONE"
