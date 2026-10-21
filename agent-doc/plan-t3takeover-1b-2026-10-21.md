# 计划：接管 Tier 3 重建，第 1b 级——换成我们自己的 Python 环境（t3takeover-1b，10/21，第 1 版）

2026-10-21 06:2x MDT 写定，分支 track2/p1-training。上接 `agent-doc/plan-t3takeover-v3-2026-10-21.md`（第 1 级，执行记录到 06:1x）。判据在结果出来之前登记在这里。
不读 Tier 1；不写、不删、不停另一位成员的东西；只读她的目录（取版本清单）。

## 0. 事实（都有记录或在 06:0x–06:2x 只读核对过）

1. 第 1 级用她的两个解释器（只读命名空间里调用）：宿主机 venv（`/usr/bin/python3.10` 为底，3.10.12，82 个发行版）跑 assemble、物理提取、比较器；
   gate venv（uv 0.13.0 管理的 CPython 3.11.17，93 个发行版）跑 support、dr2s、dyn7、mkroot、重定向（经 incontainer 替身）、usda。
   **残余风险**：gate 解释器与两个 venv 的 site-packages 对 mfshared 组可写，组里任何人都能改我们执行的代码（第 1 级计划的执行记录，05:0x 安全复核）。
2. 宿主机 venv 里 35 个发行版是 `v2d-*` 本地包装（`direct_url`，video_to_data 重建模块的 docker 包装），其余 47 个来自 PyPI（06:1x 用命令数过；初稿写成 39、43，是目测数错）；第 1 级用到的宿主机步骤
   （`t3_convert_ep.py assemble`、`t3_physics_check.py extract`、`t3r_compare.py`）只 import numpy、pyarrow、scipy、trimesh 与仓内模块（42f01f0 的 import 行）。
   gate venv 的 93 个全来自 PyPI，torch 是 `2.7.0+cpu`（PyTorch CPU 索引）。
3. ml40 能直连腾讯云、阿里云的 PyPI 镜像（200，0.2–0.3 s），pypi.org 超时；`download.pytorch.org/whl/cpu`（2.3 s）与阿里云 `pytorch-wheels/cpu` 可达；
   npmmirror 的 `python-build-standalone` 可达。ml40 上没有 uv；系统有 `/usr/bin/python3.10`。
4. 第 1 级的结论：ep14、ep20 全段逐字节复现；ep27 除 world 的缩放拟合（6 线程下不确定）外逐字节复现；重定向与 usda 在相同输入下确定。
   所以 1b 的对照能做到逐字节：拿第 1 级我们自己的产物当参照（t3、t3_refw），绕开 ep27 的 world。

## 1. 做什么（ml40，只用 CPU；新东西都放 `/lab_data/rxzhou/v2d/t3recon/env/`）

1. **版本清单**：从她两个 venv 的 `*.dist-info/METADATA` 读出名字与版本（只读），写进仓库 `stages/recovery/env/t3r_host.txt`（47 行，去掉 35 个 `v2d-*`）
   与 `stages/recovery/env/t3r_gate.txt`（93 行），每行 `名==版本`。
2. **uv 与 CPython**：`python3.10 -m venv env/boot`，从腾讯云镜像装 `uv==0.13.0`（同她的）；`UV_PYTHON_INSTALL_MIRROR=<npmmirror>`、`UV_PYTHON_INSTALL_DIR=env/.py`
   装 CPython 3.11.17；记下解释器的 sha256，与她的 `gate/.py/cpython-3.11.17-linux-x86_64-gnu/bin/python3.11` 比（相同最好，不同只记录：数值结果靠下面的对照判）。
3. **两个环境**：`env/host` = `python3.10 -m venv` + `pip install --no-deps -r t3r_host.txt`（腾讯云镜像）；`env/gate` = `uv venv -p 3.11.17` +
   `uv pip install --no-deps -r t3r_gate.txt`（腾讯云镜像，torch 走阿里云 `pytorch-wheels/cpu`，取不到再走 `download.pytorch.org`）。
   装完各列一次发行版清单，必须与第 1 条的清单逐行相同；各跑一次 import 冒烟（numpy、pyarrow、scipy、trimesh；gate 另加 torch、pinocchio、pink、soma、pxr、warp）。
4. **脚本改成可选解释器**：`t3r_level1.sh`、`t3r_level1_compare.sh`、`t3r_level1_usda.sh`、`t3r_gate_eps.sh`、`t3r_world_repeat.sh` 读环境变量 `T3R_HPY`、`T3R_GPY`、
   `T3R_GATE_VENV_BIN`（默认仍是她的，行为不变）；incontainer 替身另写一份我们的（解释器取 `T3R_GPY`），放进第二个 gate 仓库 `gate_e/repo`（同 f0ac98f），不改第 1 级用过的 `gate/`。
   改完先用默认值（她的解释器）在 t3 根上重跑一次比较驱动，结论必须与第 1 级相同（脚本改动没有改行为）。
5. **对照重跑（我们的环境）**：
   - `t3_e` = `t3r_seed_root.sh t3_e inputs`，`t3r_level1.sh t3_e`（宿主机步与 gate 步都用我们的环境；docker 步不变），与 t3 比；
   - `t3_ew` = `t3r_seed_root.sh t3_ew world-from-ref`，`T3R_FROM=assemble t3r_level1.sh t3_ew`，与参照比；
   - usda：`gate_e` 上对 t3_ew 跑 `t3r_level1_usda.sh`，与参照的三份 usda、support_usda.json 及她的重定向结果行比；
   - 比较器本身也用我们的宿主机环境跑（门槛自检、负对照、已知相同对照常）。
6. 全程每步后做第 1 级的报警检查（`find <她的 v2d> -user rxzhou` 只有已知文件、修改时间不变；t3recon 下的链接不出我们的目录）。

## 2. 判据（登记）

- E0（环境）：两个环境的发行版清单与她的逐行相同（宿主机去掉 35 个 `v2d-*`）；import 冒烟都过。不过就停，查是哪个包。
- E1（等价）：t3_e 对 t3：ep14、ep20 的全部产物逐字节相同，ep27 在 world 之前（decode、focal）逐字节相同；t3_ew 对参照：assemble 往后全部逐字节相同（每版 15/15），
  三份 summary 与 depth_post、dynamics_post 数值相同；usda 三份逐字节相同、support_usda.json 数值相同、三集重定向结果行与她的逐字段相同；三项对照与门槛自检都对。
  全过记“第 1b 级成立：不再调用她的解释器”，此后 t3takeover 的脚本默认改成我们的环境（另一次提交），第 1 级计划里的残余风险记为消除。
- E2（不成立）：报第一处不同的步、文件与差值，先查版本（哪个包、哪个构建）；查清前继续用第 1 级的做法，不在我们的代码上改数值相关的东西。
- 不提交；不碰 GPU（训练链在跑）。

## 3. 风险与安排

- 镜像上的同名同版本 wheel 与她装的是不是同一个构建：E1 的逐字节对照就是为这个；不同就按 E2 查到具体的包。
- CPython 3.11.17 的构建若与她的不同，只要 E1 过就接受；不过时先换成与她相同的构建（npmmirror 上找同一发布日期）。
- 磁盘：两个环境约 3 GB（torch CPU 约 0.8 GB），`/lab_data` 空 987 GB。
- 预计：清单与环境 30–40 分钟，脚本改动与回归 20 分钟，对照重跑约 45 分钟（t3_e 整条 30 分钟，t3_ew 与 usda 15 分钟）。
