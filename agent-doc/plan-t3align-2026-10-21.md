# 计划：Tier 3 用 Tier 1 第 0 帧算对齐，重做帧参考（t3align，10/21，第 1 版）

2026-10-21 11:2x MDT 写定，分支 track2/p1-training。判据在结果出来之前登记在这里。只用 CPU，不占卡，不重训。

## 0. 事实（都有出处）

1. **官方答复**（rxzhou 10/21 11:0x 转来）：“Since no camera calibration is released for Tier 3, can the first frame of the Tier 1 data be used to compute alignment?
   Yes! Using the first frame of Tier 1 data to compute alignment is fine, provided the Tier 1 caption isn't used in Tier 3 otherwise”。
   读法（解释，非裁定）：只限 Tier 3、只限 Tier 1 第 0 帧、只限算对齐；Tier 2 不变（`agent-doc/strategy-2026-10-19.md` 第 5 节）。
2. **Tier 3 的世界系是我们自己估的**：主机位相机当世界相机，加地面校正、机位配准、尺度 0.982（主机位）/0.949（第二机位），组委会没确认（`stages/evaluate/make_frame_refs_t3.py` 开头）。
3. **帧参考怎么进分**：kit `tracks/track_2/README.md`——用自己的重建时 `--frame-references` 要把策略输入表达在发布的 Track 2 世界系里，每集一个 npz
   （`episode_index`、`coordinate_frame=released_track2_world`、`frame_index [T]`、`pose_xyzw [T,1,7]`）；打包器核“帧参考与评测器参考只差一个刚体变换”
   （gb1018e22 打包记录：最大残差 1.29e-07 m、1.49e-07 rad），再按这个变换把策略的 rollout 换到发布世界系。所以**每集整体的位置、朝向偏差原样进所有帧的分数**，
   换一个更准的刚体变换就能去掉，不用重训；尺度偏差刚体变换去不掉。
4. **指标不认对称**（同一 README）：AUC 按物体固定点的 ADD，SP-SR 看平均位置 ≤ 10 cm 且平均朝向 ≤ 0.5 rad，MP-SR ≤ 3 cm 且 ≤ 30°，MPPE 用物体系 5 cm 处的 6 个点。
   第 0 帧朝向差一个对称角也照样扣分。
5. 数据：Tier 1 在 Mac 的 `data/challenge/track_2/tier_1_multiview_caption/`（`pull_submission.sh data` 拉的，mf4090 上也有）；三档的 episode 与帧号刻意对齐（CLAUDE.md）。
   现交 gb1018e22 与候选 t3m1022a 的帧参考在 Mac 的 `runs/submission/<名>/frefs/`（30 份 npz）。打包、预演一直在 Mac 上跑（uv）。
6. 物体在开头通常静止：18 集 gb5 参考里第一次接触在第 60–168 帧（`results/t3g5/ref_contact_summary_gb5_mf4090.txt`），所以第 0 帧物体对准，开头一段静止帧的分数直接跟着对准。

## 1. 做什么

1. **只读第 0 帧的读取口** `stages/evaluate/tier1_frame0.py`：只按 `frame_index == 0` 过滤读 Tier 1 parquet 的 `observation.object.pose`、`observation.object.visible`、
   `observation.human.translation`、`observation.human.pose` 第 0 个关节（根）；读到的行数必须恰好 1，否则报错；每次读打一行日志（集号、文件 sha256、读了哪几列）。
   这是 Tier 3 里唯一碰 Tier 1 的地方；别的脚本照旧 `forbid_tier1()`。测试：伪造的 parquet 上只返回第 0 帧、行数不对时报错。
2. **对齐与新帧参考** `stages/evaluate/align_frefs_t3.py <帧参考目录> <新目录> [--variant obj|pos|yaw]`：
   - obj（主方案）：T = P1₀ · F₀⁻¹，P1₀ = Tier 1 第 0 帧物体位姿，F₀ = 现帧参考第 0 帧；新帧参考 = T ∘ F_t（每集一个刚体变换，第 0 帧物体与 Tier 1 完全重合）；
   - pos（对照，只报）：只平移，使第 0 帧物体位置重合；
   - yaw（对照，只报）：平移 + 绕竖直方向的转动（只取 T 的偏航分量）。
   报表逐集给：第 0 帧物体的位置差（cm）、转角差（度，拆成偏航与倾斜）、Tier 1 第 0 帧物体可见与否、人体根的位置差与偏航差在 obj 变换前后各多少
   （人体根在同一份 Tier 3 根 parquet 里，与物体同一世界系；人体不计分，只作交叉核对：物体转角差大而人体根偏航差小，多半是物体朝向估错或对称，不是世界系错）。
3. **重新打包与预演**（Mac，照 10/18 的流程）：gb1018e22、t3m1022a 两份，各出 obj 版的 CSV，`--dry-run` 预演，与原 CSV 逐集比；不上传。
4. 结果、报表与两份 CSV 交 rxzhou；交不交、交哪一版待定（Tier 3 额度 10/22 16:14 MDT 起）。

## 2. 判据（登记）

- A0（合规）：全程 Tier 1 只经 `tier1_frame0.py` 读、只读第 0 帧（日志与测试为证）；别的脚本 `forbid_tier1()` 照旧；第 0 帧以外的 Tier 1 数据不进任何数字、任何选择。
- A1（新帧参考对）：每集新帧参考第 0 帧与 Tier 1 第 0 帧物体位姿的差 ≤ 1e-6 m、≤ 1e-6 rad；新旧帧参考逐帧只差同一个刚体变换（残差 ≤ 1e-6）；打包器的刚体核对过、预演过；
  CSV 与原版相比 30 集都变（第 0 帧偏差为 0 的集除外，照报）。
- A2（报，不判）：逐集第 0 帧偏差的分布（中位、最大），按机位分组；转角差 > 30° 的集标出来（多半是对称或朝向翻错），连同人体根的交叉核对一起交 rxzhou，
  由 rxzhou 定这些集用 obj 还是 pos。
- 收益只能从榜上看：第 0 帧以外不许用 Tier 1 核。第 0 帧偏差本身只说明“第 0 帧原来错多少”，不当作对整段分数的预测。
- 不改策略第 1 节：Tier 3 每次上传要 rxzhou 点头。

## 3. 风险

- 第 0 帧物体位姿的重建误差（尤其朝向）会通过 obj 变换转动整段世界：物体后来走了 1 m，世界转 10° 就是约 17 cm 的位置误差。所以 pos、yaw 两个对照一起算、一起交，由 rxzhou 选。
- 对称物体：Tier 1 与重建的第 0 帧朝向可能差一个对称角；obj 方案会让第 0 帧完全对上（指标不认对称，这对得分是对的），但同时转动了世界；A2 把这类集标出来。
- Tier 1 第 0 帧物体不可见的集（全数据集只有 1 帧不可见，未核是不是第 0 帧）：obj 变换不可用，照报，该集保持原帧参考。

## 复核（10/21 11:3x MDT，Opus；Fable 本周额度到 10/23 才恢复）与改动

结论 GO WITH FIXES（1 BLOCKER、5 MAJOR、3 MINOR）。复核读了 kit 打包器：它用两份参考的第 0 个计分帧算一个刚体变换（`rotation_quat = q_rel0 ⊗ conj(q_eval0)`，
`offset = p_rel0 − R p_eval0`，pack_submission.py 97–105 行），在所有帧上核到 1e-3 m / 1e-3 rad，再左乘到 rollout 上（123–127 行）；帧参考换成 T·F，计分轨迹就跟着乘 T，不用重训——机制确认。
第 0 个计分帧是干净参考第一个可见帧（kit trajectory.py 92 行），不是按定义的 frame_index 0。事实 6 部分不对：重建里有的集物体在接触前就动了（ep16、ep4、ep2）。
尺度：0.982 出自 plan-t3g4，0.949 没在那个文件里找到出处（管线总览有）。改动（都写进实现，不另出版本）：
1. （BLOCKER）判据测不出读错：Tier 1 存的是 `[x,y,z,qw,qx,qy,qz]`；四元数顺序读错，A1 拿同一个错值自比照样过，打包器的刚体核对对任何常量左变换也照样过。
   改：加**端到端核对**——打包后的 CSV 逐集第 0 帧对 P1₀：位置 ≤ 2 cm，选了 obj 的集朝向 ≤ 5°，且位置误差比原 CSV 小；加**负对照**——故意按 xyzw 读 Tier 1 四元数，端到端核对必须不过；
   核 Tier 1 `episodes_metadata` 的 sequence_id 与帧参考清单的 `sequence` 一致。
2. （MAJOR）A0 改写：kit 打包器对 Tier 3 照旧整段读 Tier 1 当干净参考并算本地分（dataset.py 20–26、pack_submission.py 540–560），这是官方工具的校验，照旧，分数那一行照旧滤掉；
   **我们的数字与选择只来自 `tier1_frame0.py` 的输出**；CSV 只与 CSV 比。
3. （MAJOR）一帧 F₀ 定整集的偏移太脆：F 改用我们自己 Tier 3 开头静止的若干帧的稳健估计 F̂（只用 Tier 3 数据，合规）：窗口取第 0 帧起、物体相对第 0 帧位移 ≤ 1 cm 且转角 ≤ 2° 的帧，最多 30 帧；
   位置取中位数、朝向取弦均值；报 F₀ 与 F̂ 的差；A1 的第 0 帧容差相应放宽为“新帧参考第 0 帧对 P1₀ 的差等于 F₀ 对 F̂ 的差（≤ 1e-6）”。
4. （MAJOR）偏航的“竖直”没定义（Tier 1 是 OpenCV 世界系）：取我们 Tier 3 根里这一集 `ground_plane` 的 `plane` 法向（管线一直用的那份；不读 Tier 1 的地面文件），绕它做 swing–twist 分解。
5. （MAJOR）打包器的锚点是第一个可见计分帧：逐集断言 Tier 1 第 0 帧可见（不可见的集保持原帧参考）；报 Tier 3 第 0 帧是不是补出来的（challenge_to_soma 用第一个可见帧往前补）。
6. （MAJOR）新目录要有清单：每集一行，`sha256` 换成新 npz 的，另写 ALIGN.json（方案、每集的 T、Tier 1 文件 sha256、选择理由）。
7. （MINOR）数学写明：位姿是 World_T_object，左乘；p′ = R_T p + t_T，q′ = q_T ⊗ q（Hamilton、xyzw）；Tier 1 的 float32 四元数先归一。
8. （MINOR）人体交叉核对弱：`human.translation` 是体型相关的模型参数，两档身份不同，几 cm 的偏差正常；只用根节点的偏航，当粗核对。
9. （MINOR）尺度刚体去不掉；obj、pos 把尺度误差的支点从相机挪到物体，会变小。

**主方案改成按第 0 帧的量逐集自动选**（登记，结果出来之前）。记 R_full = R₁ R̂ᵀ，tilt = R_full 绕地面法向的 swing 角，yaw_obj = 它的 twist 角，
yaw_hum = 人体根“Tier 1 对我们”的旋转的 twist 角（我们的人体根取同一份 Tier 3 根 parquet 第 0 帧，sha256 与清单的来源 parquet 对得上才用）：
- 人体可用且 |yaw_obj − yaw_hum| ≤ 15°（物体与人对世界偏航的看法一致）：tilt ≤ 3° 用 **obj**（地面校正后的残余倾斜是 1–2°），否则 **yaw_obj**；
- 人体可用但两者不一致（对称物体、朝向翻错）：**yaw_hum**；
- 人体不可用：**pos**。
平移一律取 t_T = p₁ − R_T p̂，第 0 帧物体位置对上真值。四个方案（obj、yaw_obj、yaw_hum、pos）全部算、全部报，交 rxzhou 时以自动选的为主。

## 执行记录（10/21 11:0x–11:3x MDT 执行；mf4090 对齐，Mac 打包）

工具在 79350ca（mf4090 上跑的 `align_frefs_t3.py`、`tier1_frame0.py` 的 md5 与这次提交的相同：29e37d1e…、664c6c86…）。测试 4 条全过（`results/t3align/test_align_frefs_t3_mf4090.txt`）。

1. **对齐**（mf4090，`results/t3align/align_{gb1018e22,t3m1022a}_auto.txt`，各 `ALIGN_FREFS_OK 30`）。每次运行 `TIER1_FRAME0` 日志恰好 30 行（每集一次，只读第 0 帧）。
   第 0 帧物体位置差（对齐前）：t3m1022a 中位 11.3 cm、最大 50.1 cm（ep21，第二机位）；gb1018e22 中位 11.5 cm、最大 50.1 cm。
   自动规则的选择（t3m1022a）：obj 15 集（2、6、7、8、15、16、18、19、20、21、22、24、26、28、29），yaw_obj 6 集（0、1、4、5、10、23），yaw_hum 9 集（3、9、11、12、13、14、17、25、27），pos 0 集，none 0 集。
   gb1018e22 只有 ep0（obj）、ep6（yaw_obj）与 t3m1022a 不同（这两集两份的重建不同）。对照方案 pos、yaw_hum 也全算了（`align_t3m1022a_{pos,yaw_hum}.txt`）。
2. **打包与预演**（Mac，`results/submission/pack/t3_<名>{,_dryrun}.txt`）：gb1018e22a、t3m1022aa、t3m1022a_pos、t3m1022a_yaw_hum、负对照 gb1018e22neg 五份全部 `PACK_OK`；
   打包器的刚体核对每份都过（最大残差 1.29e-07 m、1.49e-07 rad）；每份 22989 行。CSV 的 sha256：gb1018e22a f442e487…、t3m1022aa a941caf2…、t3m1022a_pos cdbb90d5…、t3m1022a_yaw_hum 42f106f5…。没有上传。
3. **端到端核对**（判据：复核改动第 1 条，`results/t3align/csv_frame0_<名>.txt`）：gb1018e22a、t3m1022aa、pos、yaw_hum 四份 `CSV_FRAME0_OK`。CSV 第 0 帧位置差从 2.9–50.1 cm 降到 0.01–0.77 cm（30 集都降）；
   选 obj 的集，朝向差降到 ≤ 0.7°。剩下的位置差是策略在第 0 帧的跟踪误差，加上 F₀ 对 F̂ 的差（报表“F0对F̂”一列，最大 0.39 cm / 0.62°）。
   **负对照**（`--variant obj --swap-quat`）`CSV_FRAME0_FAIL 30 集不过`：位置照样过（平移总是把第 0 帧物体位置对上），朝向差 52.8–179.4°。所以四元数顺序读错会被朝向这一项抓到，读对了 obj 集朝向才会 ≤ 0.7°。
4. **CSV 逐集比**（`results/t3align/csv_diff_<名>.txt`）：四份对原 CSV 都是 30 集全变、行号逐行相同，`CSV_EPISODE_DIFF_OK`。判据 A1 过。
5. **A2（报，不判）**：
   - 对齐后第 0 帧朝向差仍 > 30° 的有 10 集：3（45°）、4（67°）、9（83°）、11（180°）、12（180°）、13（178°）、14（141°）、17（95°）、25（102°）、27（67°）。
     刚体变换只能左乘，改不了物体自身的朝向（打包器也只认左乘一个刚体变换）。9 集的物体偏航与人体偏航不一致，多半是对称物体或朝向翻错；ep4 偏航一致而倾斜差 67.5°，多半是重建把物体放倒的方式错了。
     这 10 集的朝向误差原样进分（指标不认对称）。要改它，得在物体系里右乘一个固定旋转，帧参考换了、策略要重训或至少重评；这算不算官方说的 “alignment” 是解读问题，待 rxzhou 定（必要时问组委会）。
   - 人体根交叉核对：t3m1022a 第 0 帧人体根与 Tier 1 的距离，对齐前中位 21.4 cm，auto 后 28.6、pos 后 29.3、yaw_hum 后 30.8 cm；三个方案都比对齐前大。
     第 0 帧人体离物体往往几米远，人体与物体的相对位置本身就差几十厘米（单目深度与尺度误差），所以这一项分不出方案好坏。按复核第 8 条只当粗核对，不改登记的选择。
     个别集差别大（ep24：obj 47.4 cm、pos 8.2 cm；ep2：obj 61.0、yaw_hum 29.3），一并交 rxzhou。
6. **合规（A0）**：Tier 1 只经 `tier1_frame0.py` 读第 0 帧（日志为证）；kit 打包器照旧整段读 Tier 1 当干净参考，那一行本地分数照旧滤掉，没有进任何数字与选择。
   第 0 帧偏差只说明第 0 帧原来错多少，不当作对整段分数的预测（第 2 节）。

交 rxzhou 定：交不交、交哪一份（主方案 t3m1022aa，或 gb1018e22a，或对照）；上面 10 集的物体朝向要不要另立计划。Tier 3 本周额度 10/22 16:14 MDT 起（预演显示 Kaggle 当天 5 次，那是 Kaggle 的日额度，不是赛事的周额度）。

- 10/26 13:3x MDT：rxzhou 同意上传 t3m1022aa（“Tier 3 清单 t3m1022aa 交”）。CSV md5 fff0dd72… 与 10/21 预演相同；PyPI 连不上，用上次 Tier 3 提交的缓存环境（kit update_0f2f9f4b）交四个榜，记录 `results/submission/submit_t3_t3m1022aa.txt`，提交号 57676686–57676691。
  榜上分数（对 gb1018e22）：AUC 0.10649 → 0.22590，SP-SR 0.26666 → 0.33333，MP-SR 0.00000 → 0.10000，MPPE 54.99 → 49.94 cm。策略与重建都没换，只做了第 0 帧对齐，四项全涨，世界系偏差确实是主要损失之一。
  名次：Tier 3 AUC、SP-SR、MP-SR 第 2（MP-SR 与 nima arki 同分，Kaggle 规则按先交者在前，官网规则按字母序我们第 1），MPPE 第 3；读法 B 59 / 61 → 57 / 57，读法 A 14 → 13，仍第 4。
