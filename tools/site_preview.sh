#!/usr/bin/env bash
# 本机预览 SOP 页面：套上发布时平台自动加的外壳（doctype、charset、viewport），不改 docs/site 里的源文件。
# 用法：bash tools/site_preview.sh [源文件] [输出文件]；默认 docs/site/v2d-track2.html → $TMPDIR/v2d-track2-preview.html，然后用默认浏览器打开。
set -euo pipefail
src=${1:-docs/site/v2d-track2.html}
out=${2:-${TMPDIR:-/tmp}/v2d-track2-preview.html}
{
  printf '<!doctype html>\n<html><head><meta charset="utf-8">\n'
  printf '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
  printf '</head><body>\n'
  cat "$src"
  printf '\n</body></html>\n'
} > "$out"
echo "PREVIEW_OK $out"
[ "${V2D_NO_OPEN:-0}" = 1 ] || open "$out"
