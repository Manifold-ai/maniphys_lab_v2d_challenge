# 计划：接管 Tier 3 重建，第 1 级——在只读防护下复现 gb5 的 CPU 段（t3takeover，10/21，第 3 版）

2026-10-21 02:3x MDT 写定，分支 track2/p1-training；取代第 2 版（`agent-doc/plan-t3takeover-v2-2026-10-21.md`，复核要求改防护、补输入、改 K1、加 focal/world）。
rxzhou 10/21 00:3x：“现在重建我们全权接管”。判据在结果出来之前登记在这里。不读 Tier 1；网格与地面平面的 `plane` 同她的管线与 t3g4。

## 0. 事实（都有记录）

1. **防护在系统层可行**（10/21 02:2x 在 ml40 上探测，只用 `access()`，没有真写）：命名空间外她的 `tier3` 对我们可写；`unshare -rm` 后把 `/lab_data/<她的目录>` 绑定挂载并改成只读，
   里面她的目录不可写、我们的目录可写、她的文件可读。ml40 的 `unprivileged_userns_clone` 是 1。
2. **她的两个解释器在只读命名空间里能用、版本与她跑 gb5 时一致**：宿主机 venv Python 3.10.12（numpy 2.2.6、pyarrow 25.0.1、scipy 1.15.3、trimesh 5.1.0），
   gate venv Python 3.11.17（numpy 2.3.5、scipy 1.15.3、trimesh 4.5.1、pyarrow 25.0.1、torch 2.7.0+cpu）。
3. 各步命令、输入、线程、随机性、参照与版本名：第 2 版第 0 节与复核（`agent-doc/plan-t3takeover-v2-2026-10-21.md`），以及 10/21 01:5x 的只读核对（代码 42f01f0，
   decode、focal、world 在 `v2d_cari4d` 镜像 ca1774d94cd9 里跑，focal/world 线程 OMP 4（ep20、ep14）或 6（ep27）；物理检查镜像、`--cpus 8`；support、usda OMP 4，
   且只有这两步设 `T3_FLOOR_FIT=floor_fit_gb5.json`、`T3_REGISTER=camera_register_gb5.json`；dr2s、dyn7 不设 OMP）。
4. 她的目录里有指向她自己文件的软链接（`root_gb5dyn7` 的 mesh、ground_plane 与 30 份 parquet；gate 仓库的 SOMA 资源），parquet 组可写、目录没有粘滞位；
   覆盖、删除、改名都不会产生属于 rxzhou 的文件，所以 `find -user rxzhou` 只能当报警。

## 1. 第 1 级做什么（只用 CPU，GPU 留给训练）

范围：decode → focal → world →（soma 复用她的 soma_params.npz 与 residual_report.json，GPU 步、不可逐位复现）→ assemble → 物理检查 → support → dr2s → 物理检查 → dyn7 → 支撑面 usda。
三集：ep20（base、一个支撑面）、ep27（FoundationPose 集、gb5 重算、有桌面）、ep14（二机位 base；usda 是空的，二机位的支撑面路径在第 2 级用 ep25 补）。

1. **防护包装** `stages/recovery/t3r_run.sh`（新写，测试 `stages/recovery/test_t3r_run.py`）：
   - 宿主机步：`unshare -rm` 里把 `/lab_data/<她的目录>` 只读绑定挂载，再 `cd /lab_data/rxzhou/v2d/t3recon` 跑命令；命令行里出现她目录下的路径只许是两个解释器（白名单），
     其余参数与当前目录按 realpath 落在她目录下就拒绝（退出码 2）；`PYTHONDONTWRITEBYTECODE=1`、`GIT_OPTIONAL_LOCKS=0`；
   - docker 步：只挂我们的目录（她的目录一律不挂），`--user 1003:1005`（我们的 uid/gid），`--network none`；
   - 每步前后：命名空间里 `[ -w <她的 tier3> ]` 必须为假；我们目录里没有链接解析到外面；`find <她的 v2d> -user rxzhou` 只能是已知的那个 `.git/index`，且它的修改时间不变；不满足就停（退出码 3）。
2. **代码**：开分支 `track2/t3recon-rx`（从 42f01f0），`git archive` 到 `t3recon/code`，写我们自己的 DEPLOYED（dirty=0）与 MANIFEST.sha256（dr2s、dyn7 的来历核对要）；
   gate 仓库 = 我们仓库 `git archive f0ac98f` + 我们自己的 video_to_data v0.4.0（33129dd，与她的同版，SOMA 资源 sha256 相同）。
3. **数据**（她的源只读，`cp` 不用硬链接，逐文件比 sha256，记 `results/t3recon/copy_manifest_ml40.txt`；参照进 `ref/`，产物进 `out/`）：
   - 输入：三集的 `refined.pth` 与 `wild_export.json`（ep20、ep14 在 `runs/work/`，ep27 在 `runs/work_b050/`）、sam3d_body 的 `model.ckpt` 与 `mhr_model.pt`；三集的网格与地面文件；
     `input/meta/` 4 个文件（episodes.jsonl 列全 30 集，决定索引偏移）；`runs/floor/{intrinsics_gb3,floor_fit_gb5,camera_register_gb5,camera_register}.json`；
     `runs/tier3_cari4d_gb5_best.selection.json`；`dev/walls/moge_{ep14,ep20,ep27}*.npz`；三集的 masks_k0.h5（align 用）；三集转换目录里的 soma_params.npz 与 residual_report.json。
   - 参照：三集转换目录的 decode、focal、world 产物（除 `mhr_*.pt` 外整个目录）；gb5_best、_dr2s、_dr2s_dyn7 三版 parquet 与元数据；physics 三版的 npz 与 out；support json；
     depth_post、dynamics_post、provenance 三份 json；`gate/archive/support_usda_gb5dyn7_before_lean_1021/` 里三集的 usda 与 support_usda.json；align json。
   - 对照：负对照 = ep27 的 gb4 三版 parquet（`runs/archive/`）；已知相同对 = ep14、ep20 的物理 out（gb4 对 gb5，逐字节相同）。
   - usda 步的根：在我们的根里用 `mkroot.py` 建 `root_gb5dyn7`（只含三集），gate 的 motion_src 用 `challenge_to_soma.py`（CPU）生成，gate 的重定向（`eps.sh`，f0ac98f）对三集跑一遍。
4. **跑**：逐步调用各脚本（不跑她的链脚本），环境与线程照第 0 节第 3 条，版本名沿用她的；宿主机步 `nice -n 10`，docker 步 `--cpus 4`（物理检查照她的 `--cpus 8`）。
   重复跑（正对照）用第二个根（dr2s、dyn7 拒绝覆盖已有输出）。

## 2. 判据（登记）

- K0（防护与复制）：包装测试全过；第 1 节第 1 条的探针每步都过；复制的每个文件 sha256 与源相同。不过就停。
- K1（复现成立），逐段比、第一处不同就停：
  - decode、focal、world 的 npz：`numpy.array_equal`；
  - assemble、dr2s、dyn7 的 parquet、物理检查的 npz、support json、usda：逐字节（这些文件里没有路径与时间）；
  - `summary.json`、`depth_post.json`、`dynamics_post.json`、`support_usda.json`：按集逐行比，去掉路径与时间字段；provenance 只比 `code_files_sha256`；
  - 门槛自检：比较程序对“挪 2e-6 m”“取反一个四元数”要分别判“不同”“相同”；
  - 正对照（同步重复两遍相同）、负对照（ep27 gb4 对 gb5 不同）、已知相同对（ep14、ep20 物理 out）三项都对，比较才算数。
  三集都过记“第 1 级接管成立：从 decode 往后（soma 复用）能在我们的目录里重出 gb5”。
- K2（不成立）：报第一处不同的步、文件、列与差值，先查环境与线程；查清前不在我们的副本上改。
- 第 1b 级（另写）：用我们自己建的环境（经 HF 中转送 wheelhouse，照她两份 venv 的全部发行版钉版本）重跑，结果与第 1 级相同才停用她的解释器。
- 不提交；人工看图只作监看。

## 3. 风险与安排

- `unshare -rm` 里我们的 uid 显示为 0；docker 步放在命名空间外跑（不挂她的目录），`--user` 写死 1003:1005。
- 第 1 级依赖她的解释器（只读调用）；她改或删了 venv，第 1 级就跑不了，第 1b 级解决。
- CPU 与训练链共用；预计复制 30 分钟、防护与测试 1 小时、三集 1–2 小时。10/22 的额度不依赖这份计划。

## 复核（10/21 04:3x MDT，Opus；中途撞上会话额度，恢复后续完）与改动

结论 GO WITH FIXES，没有 BLOCKER；复核确认第 3 版改到了第 2 版复核的全部条目，并在只读命名空间里实测：直接路径与 `/proc/self/root` 都写不进她的目录，`/proc/<宿主进程>/root` 被拒，
我们的目录没有外来文件、没有指向她的硬链接或软链接，已知 `.git/index` 的修改时间没变。执行前按下面改（都写进实现，不另出版本）：
1. **usda 前的 gate 重定向**：用她 gate 里的替身 `gate/incontainer` 覆盖我们 gate 副本的 `scripts/dev/incontainer`（f0ac98f 原版要 `robotic-grounding:latest`，ml40 上没有）；
   PATH 把她的 gate venv 放最前，`T3_GATE=<我们的 gate 目录>`、`V2D_T3_SET=gb5dyn7`、`OMP_NUM_THREADS=3`、`MKL_NUM_THREADS=3`（同她的 `run_parallel.sh` 23 行）；
   mkroot：`T3_ROOT=<我们的根> <gate python> mkroot.py <我们的 gate 仓库> gb5dyn7 - <我们的 dyn7 目录>`；命名空间里把 `/dev/null` 绑定到 `/var/run/docker.sock` 上，不让任何步骤在里面起容器。
2. **K1 用两个比较器**：字节比较（自检：改一个字节要判“不同”）与数值比较（位置 ≤ 1e-6 m、四元数 q ≡ −q、≤ 1e-6 rad；自检：挪 2e-6 m 判“不同”、取反四元数判“相同”）。
   结论分三种：字节相同、字节不同但数值相同、数值不同。重复跑若不逐位相同，以两次之差作为噪声底，数值比较的门槛取它与 1e-6 的较大者。
3. **防护补缝**：每步在嵌套的 `unshare -U` 里跑（或 `setpriv --bounding-set=-all`），让外层命名空间里的 root 也不能把只读挂载改回可写；K0 加 `find <我们的根> -type f -links +1` 为空；
   解释器白名单按 realpath 比（她的 gate python 实际在 `gate/.py/…`）。
4. **ep20 的参照 decode** 写于 10/09 08:07:29（+0800），比提交 7bae0c1（08:08:18）早 49 秒：ep20 的 decode 不一致只报、不停，后面接着从参照的 object_cam.npz 跑；
   每一段都另用参照输入跑一遍，一处不同不遮住后面的。
5. ep20、ep14 的 world_calib.json 里记的文件名是 `*_gb3.json`、sha256 却是 gb5 那两份：calib 与 report 的 json 按字段比、去掉文件名字段；parquet 只记 sha256，不受影响。
6. decode 的目录布局：`/e/inference/refined.pth`、`/e/export/<恰好一个目录>/wild_export.json`、`/w/sam3d_body/checkpoints/sam-3d-body-dinov3/{model.ckpt,assets/mhr_model.pt}`；
   `/a` 挂我们 33129dd 的 SOMA 目录；镜像按 ID ca1774d94cd9 钉，不用 `:latest`。
7. 已知相同对只对物理 out 的 npz 成立（out 的 json 差 tier 字段）；gb4 的 dyn7 在 `runs/` 下，不在 `runs/archive/`；align 不进第 1 级（从运行顺序与 K1 里拿掉，它的输入与参照不复制）。

## 执行记录

- 10/21 04:5x MDT 防护实测（ml40，只用 access() 与 /proc 读）：只读绑定 + 盖住 /run/docker.sock + `setpriv --bounding-set=-all` 之后，她的目录不可写、我们的可写、docker socket 不是 socket、
  把挂载改回可写被拒、改完仍只读、CapPrm/CapEff 全 0。
- 05:0x `stages/recovery/t3r_run.sh` 与 `test_t3r_run.py`（99e9550）：4 个测试在 ml40、mf4090 都过（`results/ml40/t3recon/test_t3r_run_ml40.txt`、`results/t3recon/test_t3r_run_mf4090.txt`），
  含对照：同一个写入脚本在命名空间里失败、在外面成功。
- 05:1x 复制（`stages/recovery/t3r_copy.sh` 读 `t3r_level1_files.tsv`，经 t3r_run.sh 在只读命名空间里跑）：第一次先查拦下 3 处（物理检查的 summary.json 在 `out/` 下），一个没复制；
  改清单后 `T3R_COPY_DONE 122 4611083846`，每个文件源与目标 sha256 相同（`results/ml40/t3recon/copy_manifest_ml40.txt`）。
- 复制之后的报警检查：`find <她的 v2d> -user rxzhou` 只有已知的 `gate/repo/third_party/video_to_data/.git/index`，修改时间仍是 10/21 13:33:28.66（CST），没变。
- 05:0x 自动安全复核（MEDIUM，不可信解释器的选择）：原先用通配符猜她的目录、不核解释器。改为 `stages/recovery/t3r_other.sh`：候选必须恰好一个、不是软链接、不属我们、对其他用户不可写；
  宿主机解释器的真实文件属 root、gate 解释器的真实文件属路径里的那个用户，都对其他用户不可写，sha256 记进日志。实测：v2d 目录本身是机器管理账户建的（不是她），
  gate 解释器属她、权限 rwxrwxr-x（组可写）。**残余风险**：mfshared 组里的成员能改 gate 解释器，这一点只有第 1b 级换成我们自己的环境才消除。
  正在跑的第 1 级 A 部分用的是改动前的脚本（bash 边跑边读，跑的时候不换文件），跑完再换；比较驱动已换。
- 05:13 MDT 第 1 级 A 部分跑完（`runs/logs/t3r_level1_t3.log` 末行 T3R_LEVEL1_DONE，三集 decode → dyn7 共 28 分钟）；换上安全修复后的 `t3r_level1.sh`。
- 05:2x **K1 第一轮比较**（`stages/recovery/t3r_level1_compare.sh t3`，记录 `results/t3recon/t3_vs_ref_cmp_*.txt`）：负对照 3/3 不同（pose 最大差 0.215）、已知相同对 4/4 逐字节相同、
  门槛自检都过；正对照（t3_rep）还没跑。
  - ep14、ep20：decode、focal、world、assemble、三版物理检查（npz 与 out）、support、dr2s、dyn7 全部**逐字节相同**；
  - ep27：decode、focal（含身体重拟合）逐字节相同，`object_world.npz` 逐字节相同；**第一处不同在 world 的 `soma_params_world.npz`**：identity_coeffs 最大差 8.24e-3；
    `world_calib.json` 的缩放拟合 joint_err_mm_max 1.03 对参照 0.85、vertex_err_mm_mean 0.52 对 0.48、vertex_err_mm_p99 1.55 对 1.58、body_rigid_max_err_mm 0.0013 对 0.0015。
    往后跟着不同：三版 parquet（gb5_best 的 identity_coeffs、dyn7 的 human.translation 最大差 6.1e-4 m）、物理 npz 与 out（feet 最大差 6.3e-4 m），metadata json 逐字节相同；
  - summary、depth_post、dynamics_post 三份 json 报“长度 3 对 30”：顶层是“每集一条”的列表，比较器的 --subset 只认字典，是比较器的缺口。
    `t3r_compare.py` 补上按 episode 配对（K1 原文“按集逐行比”）与 `--all`（列出全部不同处），测试见 `test_t3r_compare.py`，修好后重比这三份。
- **按 K2 处理 ep27 world**（先查环境与线程，查清前不在我们的副本上改）。已知事实：镜像同一个（ca1774d94cd9，9/25 建；她的 `t3_sel_full.sh` 用 `:latest`，指向同一 ID）；
  她的 world 也是 `--cpus 6 -e OMP_NUM_THREADS=6`（`t3_sel_full.sh` 37 行），当时最多 3 集的转换并行（MAX_CONVERT）；我们跑时 ml40 上有训练链。
  s≠1 的集 world 步用 torch Adam 在 CPU 上走 400 步拟合 frame-0 身份（`_scale_body`，float32、8 帧、种子 0）。
  **登记（重跑之前）**：用 `stages/recovery/t3r_world_repeat.sh` 只重跑 world 步，输入取 t3 根里 focal 之后的文件（与参照逐字节相同）：
  1. ep27 同配置（6 线程）跑两遍 a、b；ep14 同配置（4 线程）跑一遍当对照，应与 t3、参照都逐字节相同，否则这套重跑本身有问题，整轮不判。
  2. a、b、t3 三者两两逐字节相同 → world 步在固定配置下确定，参照的差来自她当时的环境，接着按线程与 BLAS 设置逐项试（不改代码），找不到就如实记“ep27 world 不能逐位复现，差值如上”；
     三者之间有不同 → world 步本身不确定：按复核第 2 条，噪声底取三者两两之差的最大值（逐键），参照的差逐键不超过噪声底才记“在噪声底内复现”，超过就记不成立。
  3. 不论哪种结果，下游 ep27 的段（assemble 往后）另用参照的 world 产物当输入跑一遍（复核第 4 条“一处不同不遮住后面的”），逐字节比。
- 05:2x–05:3x **K2 登记第 1、2 条的结果**（`results/t3recon/world_repeat_ep{14,27}_*.txt`、`world_noise_ep27.txt.failed`）：
  - 对照成立：ep14 的 world 重跑（4 线程）与 t3、参照都逐字节相同。注意 ep14（scale 0.949）、ep20（0.98187）同样走 400 步 Adam 缩放拟合，三遍（她、t3、重跑）逐字节相同。
  - ep27 同配置（6 线程）三遍 t3、a、b 两两都不同 → **world 步在 ep27 上不确定**。逐键两两之差的最大值（噪声底）与参照对 t3 的差：
    identity_coeffs 1.57e-2 对 8.24e-3（过）；scale_params 2.75e-3 对 2.95e-3（不过）；world_calib 的 joint_err_mm_max 0.12 对 0.18（不过）、joint_err_mm_mean 0.06 对 0.09（不过）、
    vertex_err_mm_mean 0.04 对 0.04（过）、vertex_err_mm_p99 0.08 对 0.03（过）、body_rigid_max_err_mm 2e-4 对 2e-4（过）。**按登记的规则记“ep27 world 不成立”。**
  - 事后观察（不改上面的结论）：三遍的两两最大差是偏小的噪声估计——可交换的第四个样本落在前三个范围之外的概率是 1/2；参照的 joint_err_mm_max 0.85 在我们三遍（0.91–1.03）之外，
    joint_err_mm_mean 0.34 也在外（0.37–0.43），vertex 两项在内。下游影响：ep27 的 human.translation 最大差 6.1e-4 m、物理 feet_p50 差 0.5 mm、depth_post 的 human_feet_cut_frames 185 对 180。
  - 三份每集一条的 json（修好比较器后重比）：ep14、ep20 的条目与参照相同；不同只在 ep27 的条目；dynamics_post 数值相同。
- **K2 继续查线程（登记，跑之前）**：`t3r_world_repeat.sh` 再跑 ep27 的 1 线程两遍（c、d）、4 线程两遍（e、f），ep14 的 6 线程两遍（g、h）。某个配置两遍逐字节相同记“该配置确定”。
  判读：ep27 的 1 线程确定而 6 线程不确定 → 不确定来自多线程；ep27 的 4 线程也不确定、ep14 的 6 线程确定 → 与集有关；ep14 的 6 线程也不确定 → 与线程数有关（4 线程碰巧确定）。
  这一步只定来源，不改代码；我们自己的管线怎么定 world 的线程，等来源清楚后另写进第 2 级计划。
