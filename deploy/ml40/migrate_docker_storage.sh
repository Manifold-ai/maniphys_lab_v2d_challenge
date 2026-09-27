#!/usr/bin/env bash
# ml40：把 docker 与 containerd 的存储从系统盘（150 GB，共用）迁到 /lab_data（2 TB），并建 /lab_data/rxzhou。
#
# 为什么两个都要迁：ml40 的 Docker 29 用 containerd 镜像存储（driver-type io.containerd.snapshotter.v1），
# 镜像层在 /var/lib/containerd。只改 daemon.json 的 data-root 搬不走镜像（Docker 文档 containerd 页）。
#
# 用法（在 ml40 上，需要交互输入 sudo 密码）：
#   sudo bash deploy/ml40/migrate_docker_storage.sh            # 只做预检，不改任何东西
#   sudo bash deploy/ml40/migrate_docker_storage.sh --apply    # 预检通过后执行迁移
#   sudo bash deploy/ml40/migrate_docker_storage.sh --cleanup  # 验收满意后，删除系统盘上的旧备份
#
# 安全设计：预检不过就退出；旧目录只改名不删除；启动或验收失败自动回滚到迁移前。
set -euo pipefail

NEW_CTD=/lab_data/containerd
NEW_DKR=/lab_data/docker
OLD_CTD=/var/lib/containerd
OLD_DKR=/var/lib/docker
BAK_SUFFIX=.pre-migration
CTD_CONF=/etc/containerd/config.toml
DKR_CONF=/etc/docker/daemon.json
TS=$(date +%Y%m%d-%H%M%S)
LOGDIR=/lab_data/rxzhou/ops/docker-migration-$TS
MODE=${1:-check}

say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
die() { say "中止：$*"; exit 1; }

[ "$(id -u)" = 0 ] || die "需要 root（sudo bash ...）"

if [ "$MODE" = --cleanup ]; then
  docker info --format '{{.DockerRootDir}}' | grep -qx "$NEW_DKR" || die "docker 还没在用 $NEW_DKR，不删备份"
  for d in "$OLD_CTD$BAK_SUFFIX" "$OLD_DKR$BAK_SUFFIX"; do
    [ -d "$d" ] && { say "删除 $d"; rm -rf --one-file-system "$d"; }
  done
  df -h /; exit 0
fi

# ── 预检 ───────────────────────────────────────────────────────────
say "预检"
[ -z "$(docker ps -q)" ] || die "有运行中的容器：$(docker ps --format '{{.Names}}' | tr '\n' ' ')"
[ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null)" ] || die "GPU 上有进程在跑"
for d in "$NEW_CTD" "$NEW_DKR" "$OLD_CTD$BAK_SUFFIX" "$OLD_DKR$BAK_SUFFIX"; do
  [ ! -e "$d" ] || die "$d 已存在"
done
[ -d "$OLD_CTD" ] && [ -d "$OLD_DKR" ] || die "旧目录不全"
[ -f "$CTD_CONF" ] || die "没有 $CTD_CONF"
grep -qE '^\s*root\s*=' "$CTD_CONF" && die "$CTD_CONF 已有未注释的 root 行，先人工确认"
# root 是顶层键：有注释掉的默认行就原地取消注释，没有就插到文件第一行（任何 [表头] 之前）。
# 预检就定下改法，免得拷完几十 GB 才发现改不了、整体回滚。
if grep -qx '#root = "/var/lib/containerd"' "$CTD_CONF"; then CTD_EDIT=uncomment; else CTD_EDIT=insert-first-line; fi
say "现状：Docker Root Dir $(docker info --format '{{.DockerRootDir}}')；容器 $(docker ps -aq | wc -l) 个（运行中 0）；镜像 $(docker image ls -q | sort -u | wc -l) 个"
say "containerd 配置改法：$CTD_EDIT（$CTD_CONF 里含 root 的行：$(grep -n 'root' "$CTD_CONF" | tr '\n' ' ')）"
python3 -c "import json,sys; d=json.load(open('$DKR_CONF')); sys.exit('data-root' in d)" || die "$DKR_CONF 已有 data-root"
[ "$(findmnt -no FSTYPE /lab_data)" = ext4 ] || die "/lab_data 不是 ext4"
NEED=$(du -sxb "$OLD_CTD" "$OLD_DKR" | awk '{s+=$1} END{print s}')
FREE=$(df -B1 --output=avail /lab_data | tail -1)
say "旧数据 $((NEED/1024/1024/1024)) GiB，/lab_data 可用 $((FREE/1024/1024/1024)) GiB"
[ "$FREE" -gt $((NEED * 12 / 10)) ] || die "/lab_data 空间不足"
say "预检通过"
[ "$MODE" = --apply ] || { say "只做了预检。确认后加 --apply 执行"; exit 0; }

# ── 记录迁移前状态 ─────────────────────────────────────────────────
install -d -o rxzhou -g mfshared -m 2775 /lab_data/rxzhou /lab_data/rxzhou/ops
install -d -o rxzhou -g mfshared -m 2770 "$LOGDIR"   # 记录留给 rxzhou 不用 sudo 就能查（setgid，文件随组可读）
docker image ls --no-trunc --format '{{.Repository}}:{{.Tag}} {{.ID}}' | sort > "$LOGDIR/images.before"
docker info > "$LOGDIR/docker_info.before" 2>&1 || true
cp -a "$CTD_CONF" "$CTD_CONF.bak-$TS"
cp -a "$DKR_CONF" "$DKR_CONF.bak-$TS"
say "迁移前镜像 $(wc -l < "$LOGDIR/images.before") 个，记录在 $LOGDIR"

MOVED=0
rollback() {
  say "回滚"
  systemctl stop docker.socket docker containerd || true
  cp -a "$CTD_CONF.bak-$TS" "$CTD_CONF"
  cp -a "$DKR_CONF.bak-$TS" "$DKR_CONF"
  if [ "$MOVED" = 1 ]; then
    [ -d "$OLD_CTD$BAK_SUFFIX" ] && [ ! -e "$OLD_CTD" ] && mv "$OLD_CTD$BAK_SUFFIX" "$OLD_CTD"
    [ -d "$OLD_DKR$BAK_SUFFIX" ] && [ ! -e "$OLD_DKR" ] && mv "$OLD_DKR$BAK_SUFFIX" "$OLD_DKR"
  fi
  systemctl start containerd docker
  say "已回滚到迁移前；/lab_data 上的副本保留在 $NEW_CTD、$NEW_DKR 供排查"
}
trap 'rc=$?; [ $rc -ne 0 ] && rollback; exit $rc' EXIT

# ── 停服务、拷贝 ───────────────────────────────────────────────────
say "停止 docker / containerd"
systemctl stop docker.socket docker containerd
say "拷贝 $OLD_CTD → $NEW_CTD"
rsync -aHAXS --numeric-ids "$OLD_CTD/" "$NEW_CTD/"
say "拷贝 $OLD_DKR → $NEW_DKR"
rsync -aHAXS --numeric-ids "$OLD_DKR/" "$NEW_DKR/"

# ── 改配置 ─────────────────────────────────────────────────────────
if [ "$CTD_EDIT" = uncomment ]; then
  sed -i 's|^#root = "/var/lib/containerd"$|root = "/lab_data/containerd"|' "$CTD_CONF"
else
  sed -i '1i root = "/lab_data/containerd"' "$CTD_CONF"
fi
grep -qx 'root = "/lab_data/containerd"' "$CTD_CONF" || die "containerd 配置没改成功"
python3 - "$DKR_CONF" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["data-root"] = "/lab_data/docker"
json.dump(d, open(p, "w"), indent=2); open(p, "a").write("\n")
PY

# ── 旧目录改名，确保新路径真的在用 ─────────────────────────────────
mv "$OLD_CTD" "$OLD_CTD$BAK_SUFFIX"
mv "$OLD_DKR" "$OLD_DKR$BAK_SUFFIX"
MOVED=1

# ── 启动与验收 ─────────────────────────────────────────────────────
say "启动 containerd / docker"
systemctl start containerd docker
sleep 3
[ "$(docker info --format '{{.DockerRootDir}}')" = "$NEW_DKR" ] || die "Docker Root Dir 不是 $NEW_DKR"
containerd config dump 2>/dev/null | grep -qE "^root = \"$NEW_CTD\"" || die "containerd root 不是 $NEW_CTD"
docker image ls --no-trunc --format '{{.Repository}}:{{.Tag}} {{.ID}}' | sort > "$LOGDIR/images.after"
diff -u "$LOGDIR/images.before" "$LOGDIR/images.after" || die "镜像列表或 ID 变了"
# 用镜像 ID 而不是名字：排在第一的可能是 <none>:<none>，按名字 docker run 会失败并把成功的迁移回滚掉
IMG=$(awk '$1=="flash_chord:latest"{print $2; exit}' "$LOGDIR/images.after")
[ -n "$IMG" ] || IMG=$(head -1 "$LOGDIR/images.after" | cut -d' ' -f2)
docker run --rm --runtime=nvidia --gpus all --entrypoint nvidia-smi "$IMG" -L | tee "$LOGDIR/gpu_check.txt" | grep -q "L40S" \
  || die "容器里看不到 GPU"
docker info > "$LOGDIR/docker_info.after" 2>&1
trap - EXIT
say "迁移完成并验收通过"
df -h / /lab_data
say "旧数据仍在 $OLD_CTD$BAK_SUFFIX 与 $OLD_DKR$BAK_SUFFIX（占系统盘）。确认一切正常后运行 --cleanup 删除"
