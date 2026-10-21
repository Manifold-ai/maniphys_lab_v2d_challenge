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

## 复核（10/21 06:3x MDT，Opus；Fable 本周额度用完）与改动

结论 GO WITH FIXES（4 条 MAJOR、4 条 MINOR），复核没写她的目录、没跑她的东西。**事实更正两处**：
- 第 0 节第 2 条：gate venv 的 93 个不全来自 PyPI。她的 `setup.sh` 23–24 行用 `--index-strategy unsafe-best-match` 加 PyTorch 索引，uv 缓存里 8 个
  （jinja2、mpmath、networkx、numpy、pillow、sympy、torch、typing-extensions）取自 PyTorch 索引、85 个取自 PyPI；numpy、pillow 两边 sha256 相同。
  宿主机步骤的 import 清单核过是全的（assemble：numpy、pyarrow、scipy，scipy 在 `_quat_wxyz` 里；extract：numpy、pyarrow、t3_inputs；比较器：numpy、pyarrow），trimesh 用不到。
- 第 0 节第 3 条：pypi.org 不是超时，是慢（HEAD `/simple/` 200，GET `/simple/uv/` 0.59 MB 用 20 s）；我那次 curl 设了 10 s 上限。

改动（都写进实现，不另出版本）：
1. （MAJOR）**1b 模式不留默认、她的解释器跑不起来**：`t3r_run.sh` 加 `T3R_MASK`，在命名空间里用空的只读 tmpfs 盖住她的 `venv`、`gate/venv`、`gate/.py`；
   `T3R_ALLOW` 只放我们的解释器；每条记录打出实际执行的解释器 realpath 与 sha256；gate 目录改成变量（1b 用 `gate_e`），incontainer 替身另写我们自己的。
2. （MAJOR）**第 1 级的记录先保住**：已回流、脱敏、提交（`results/ml40/t3recon/`，cbcb2be；`tools/redact_stdin.sh` 加了就地改写）。之后的回归跑与 1b 的比较用新的记录名
   （`T3R_TAG` 后缀），拿判定行与第 1 级的逐行比，不覆盖第 1 级的记录。
3. （MAJOR）`t3r_gate_eps.sh` 改查 `[ ! -w "$T3R_HER" ]`；`T3R_GATE_VENV_BIN` 的 realpath 必须在 `t3recon/env` 下（1b）或她的目录下（第 1 级），否则拒绝。
4. （MAJOR）**torch 的来源**：默认索引用腾讯云，加 `-f https://mirrors.aliyun.com/pytorch-wheels/cpu/`（平铺页，只能当 find-links），不加额外索引
   （uv 默认“先到先用”，PyTorch 索引放进去会挡住 PyPI 上的 11 个钉住的版本）；gate 清单带 `--require-hashes`，哈希取她 uv 缓存里的 `.http` 记录（只读）。
   复核实测：torch 2.7.0+cpu（cp311、linux x86_64）两处都在（175969026 字节），PyTorch 列出的 sha256 与她缓存里的相同。
5. （MINOR）E0 改为逐个发行版比 RECORD 里的（路径，sha256）集合，去掉 `../../../bin/*`、pyc、INSTALLER、REQUESTED、`direct_url.json`。
   CPython：uv 0.13.0 把 3.11.17 解析到构建 20261009（install_only_stripped，uv 自己核 sha256），npmmirror 有这个文件；装完与她的 `python3.11` 比 sha256。
6. （MINOR）uv：`UV_PYTHON_INSTALL_DIR` 用绝对路径、建 venv 时再设一次；`uv python install --no-bin`（不往 `~/.local/bin` 放链接）；建 venv 时加 `--managed-python`、
   `UV_PYTHON_DOWNLOADS=never`；`uv pip install --python <我们的 env>/bin/python`；两个环境都经 `t3r_run.sh` 建（建错了也写不进她的目录）。
7. （MINOR）E1 的重定向结果行改与我们的 `gate/repo/runs/logs/batch/t3_gb5dyn7refw_ep*.tsv` 比（它们已与她的逐字段相同），不读她仍在用的 `rec_gb5dyn7.txt`。
8. （MINOR）1b 模式里 `t3r_other.sh` 只核她的目录，不核她的解释器。1b 的对照：负对照、已知相同对、门槛自检照常，比较器用我们的宿主机环境跑；
   正对照：E1 出现不同时，对那一步用我们的环境重复两遍查确定性，再按 E2 查版本。

## 执行记录

- 06:4x 改动 2 先做：第 1 级的 119 份记录回流、脱敏、提交（cbcb2be）。
- 06:4x–06:5x 改动 1、3、7、8 与选环境（a07e8c2、b335004）：`t3r_run.sh` 的 `T3R_MASK`（空的只读 tmpfs）与白名单程序的 realpath、sha256 记录（6 个测试在 ml40、mf4090 都过，
  `results/{ml40/,}t3recon/test_t3r_run_*_mask.txt`）；`stages/recovery/t3r_env.sh`（`T3R_ENV=hers|ours` 一处定解释器、遮挡与 gate 目录，ours 不留默认）；
  `t3r_other.sh` 只核目录的模式；`t3r_gate_eps.sh` 改查她的目录与 venv 的位置；`t3r_gate_setup.sh` 的 ours 模式（gate_e、我们的替身 `t3r_incontainer_ours`）；
  记录名后缀 `T3R_TAG`；重定向结果行改与第 1 级的 refw 结果行比。
- 第 1 节第 1 条：`stages/recovery/t3r_env_lists.py`（RECORD 摘要，3 个测试过）读她两个 venv，存成 `results/ml40/t3recon/env_list_hers_{host,gate}.txt`，
  钉版本清单 `stages/recovery/env/t3r_host.txt`（47 行）、`t3r_gate.txt`（93 行）。
- 改动 4 的偏离：没加 `--require-hashes`——她 uv 缓存里的 `.http` 是 uv 的二进制序列化，取哈希要另写解析；改由 E0 的 RECORD 逐文件比对兜底（比对的是装进去的每个文件）。
- 06:50–06:56 **E0**（`stages/recovery/t3r_env_build.sh`，全程在盖住她解释器的命名空间里建；记录 `results/t3recon/env_build.txt.failed`、`env_build_fix_antlr4{,b,c}.txt*`）：
  第一次 gate 93/93 与她的 RECORD 摘要相同、CPython 3.11.17 解释器 sha256 相同（08ad3f0a96b53608…，构建 20261009）、import 冒烟都过；host 47 个里差 antlr4-python3-runtime——
  venv 自带的 pip 22.0.2 没有 wheel 包，把这个只有源码包的发行版装成了 egg-info。改成先装清单里的 pip 26.2.1 再装其余（已写进脚本），就地重装后文件数 59 对 59、
  只差 dist-info/WHEEL 的 Generator 行（setuptools 84.2.1 对她的 84.0.0）；用 pip 26 的 `--build-constraint`（`stages/recovery/env/t3r_host_build.txt`：setuptools==84.0.0；
  PIP_CONSTRAINT 管不到构建依赖，第二次没生效）重构建后 **host 47/47、gate 93/93 全部相同，T3R_ENV_BUILD_DONE**。E0 过。
- 06:56 起 **E1**（`stages/recovery/t3r_1b_e1.sh`，tmux t3r1b，日志 `runs/logs/t3r_1b_e1.log`）：部署前逐个核对 14 个脚本在 ml40 上的 md5 与仓库相同（发现 5 个旧版、1 个没拷，补齐后才启动）。
  第 0 步回归（她的解释器、记录名 `_reg`）各段判定行与第 1 级的记录逐行相同；gate_e、t3_e、t3_ew、usda 在跑。
- 07:37 MDT **E1**（`runs/logs/t3r_1b_e1.log`；记录 `results/t3recon/t3_vs_ref_cmp_reg_*`、`t3_e_vs_t3_cmp_1b_*`、`t3_ew_vs_ref_cmp_1b_*`、`t3_ew_usda_1b_*`、`gate_e_setup.txt`）：
  - 回归（她的解释器，记录名 `_reg`）：14 段的判定行与第 1 级的记录逐行相同；
  - gate_e（我们的环境、我们的 incontainer 替身）搭好；t3_e 在我们的环境里从 decode 整条重跑 26 分钟，t3_ew 从 assemble 起；
  - t3_e 对 t3：decode 6/6、focal 9/9、support 3/3 逐字节相同；world 7/9、三版数据各 11/15，不同的都是 ep27 的文件（world 的缩放拟合在 6 线程下不确定，第 1 级已查清）；
    三份 summary 与 depth_post 只在 ep27 的条目不同，dynamics_post 逐字节相同；
  - t3_ew 对参照：负对照 3/3 不同、已知相同对 4/4、门槛自检过；world 9/9、三版数据各 15/15、support 3/3 逐字节相同，三份 summary、depth_post 与 dynamics_post 数值相同；
    usda 3/3 逐字节相同、support_usda.json 数值相同，三集重定向结果行与第 1 级的 refw 结果行（即她的）逐字段相同；
  - 记录里打出的解释器只有 `t3recon/env/.py/cpython-3.11.17…/python3.11`（sha256 08ad3f0a96b53608…，21 次）与系统 `/usr/bin/python3.10`（a2f33a6e00698927…，45 次；宿主机 venv 的基础解释器，与她的同一个），她的 venv 在命名空间里被盖住；
  - 报警检查：她目录下属于我们的文件仍只有已知的 `.git/index`，修改时间 13:33:28.66 没变；t3recon 下报了 6 条“外链”，都是我们 venv 的基础解释器链到系统 `/usr/bin/python3.10`，
    不是指向她的目录（检查已改成放行 /usr/bin）。
  **E1 全过，记“第 1b 级成立：不再调用她的解释器”。** 07:4x 起 t3takeover 脚本的默认环境改成我们的（`t3r_env.sh`：不设 `T3R_ENV` 时是 ours，hers 只在明确设了时用），
  `t3r_world_repeat.sh` 的比较器也改由 `t3r_env.sh` 定；部署后在 ml40 上核对 7 个脚本的 md5 与仓库相同。第 1 级计划里的残余风险（她的解释器与 site-packages 对组可写）记为消除。
