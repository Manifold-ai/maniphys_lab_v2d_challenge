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

## 复核

待做（Fable 本周额度到 10/23 13:00 纽约时间才恢复，这次用独立的 Opus 复核）。
