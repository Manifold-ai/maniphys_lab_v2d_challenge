# command  : python3 tools/jev_claims.py agent-doc/experiments/2026-10-08-hf-readme.claims.json 
# md5      : f8354bbb6809ba85df98bbb43a4ec16d  tools/jev_claims.py
# md5      : dda2fbfafede59a8237cf54aa98a7880  agent-doc/experiments/2026-10-08-hf-readme.claims.json
# source   : 10465fd28035-dirty
# host     : Rongxuans-MacBook-Air.local
# run_at   : 2026-10-08T11:07:45-0600
# ---------------------------------------------------------------
model jev-1.13.0; question: Does `source` support `claim`?
batch1               P(supported)=0.66  UNVERIFIED             [repos, p1]  第 1 批：仓库里有 39 个 state 文件，共 6,244,721,044 字节；它们来自 38 条 run，2026-10-01 归档，本地副本在 10/1 已删除。
batch2               P(supported)=0.36  UNVERIFIED             [repos, res2, plan2]  第 2 批：仓库里有 1352 个 policy 文件，共 6,570,689,816 字节；来自 52 条 run，每条 26 份（步 10000384 到 260009984），清单里的文件此时都还在本地。
checks               P(supported)=0.97  verified               [log1, res2]  第 1 批核对 39 / 39 一致、抽查 3 个一致；第 2 批核对 1352 / 1352 一致、抽查 52 个一致且覆盖 52 条 run。
restore              P(supported)=0.94  verified               [restore]  在 mf4090 上经 tools/hf_remote.sh 用 hf download 下载了 1 个归档文件，下载的文件、本地原文件与清单的 sha256 开头一致，测试副本随后删除。
example              P(supported)=0.99  verified               [ex]  t1-ep16-w2048-cap4m-mf4090 的 ARCHIVED.json 记了 state_340013056.safetensors，大小 160121036，sha256 以 9da3ff26f01bad05 开头，时间是 2026-10-01T23:52:35+0800。
ctl_true             P(supported)=0.98  control(true) ok       [repos]  v2d-track2-archive 仓库是私有的，共 1392 个文件。
ctl_false_n          P(supported)=0.01  control(false) ok      [repos]  v2d-track2-archive 仓库里一共只有 39 个 policy 文件。
ctl_false_ex         P(supported)=0.01  control(false) ok      [ex]  t1-ep16-w2048-cap4m-mf4090 的 ARCHIVED.json 记的是 policy_10000384.safetensors。
controls behaved as expected
