# command  : python3 tools/jev_claims.py agent-doc/experiments/2026-10-08-hf-readme.claims.json 
# md5      : f8354bbb6809ba85df98bbb43a4ec16d  tools/jev_claims.py
# md5      : 41446663cbba5254a9f999bcf5ff02f3  agent-doc/experiments/2026-10-08-hf-readme.claims.json
# source   : 10465fd28035-dirty
# host     : Rongxuans-MacBook-Air.local
# run_at   : 2026-10-08T11:08:22-0600
# ---------------------------------------------------------------
model jev-1.13.0; question: Does `source` support `claim`?
b1_repo              P(supported)=0.98  verified               [repos]  v2d-track2-archive 仓库的 mf4090 目录下有 39 个 state 文件，共 6244721044 字节。
b1_runs              P(supported)=0.97  verified               [p1]  第 1 批在 10/1 归档：清单 39 个文件、6.24 GB，删除后释放 6.24 GB，38 个 run 目录写了 ARCHIVED.json。
b2_repo              P(supported)=0.98  verified               [repos]  v2d-track2-archive 仓库的 mf4090 目录下有 1352 个 policy 文件，共 6570689816 字节。
b2_runs              P(supported)=0.94  verified               [res2]  第 2 批的清单来自 52 条 run，每条 run 26 个文件，步数从 10000384 到 260009984，共 1352 个文件。
b2_local             P(supported)=0.91  verified               [res2]  第 2 批清单里的 1352 个文件此时都还在训练机本地。
checks               P(supported)=0.97  verified               [log1, res2]  第 1 批核对 39 / 39 一致、抽查 3 个一致；第 2 批核对 1352 / 1352 一致、抽查 52 个一致且覆盖 52 条 run。
restore              P(supported)=0.94  verified               [restore]  在 mf4090 上经 tools/hf_remote.sh 用 hf download 下载了 1 个归档文件，下载的文件、本地原文件与清单的 sha256 开头一致，测试副本随后删除。
example              P(supported)=0.99  verified               [ex]  t1-ep16-w2048-cap4m-mf4090 的 ARCHIVED.json 记了 state_340013056.safetensors，大小 160121036，sha256 以 9da3ff26f01bad05 开头，时间是 2026-10-01T23:52:35+0800。
ctl_true             P(supported)=0.98  control(true) ok       [repos]  v2d-track2-archive 仓库是私有的，共 1392 个文件。
ctl_false_n          P(supported)=0.01  control(false) ok      [repos]  v2d-track2-archive 仓库里一共只有 39 个 policy 文件。
ctl_false_ex         P(supported)=0.01  control(false) ok      [ex]  t1-ep16-w2048-cap4m-mf4090 的 ARCHIVED.json 记的是 policy_10000384.safetensors。
controls behaved as expected
