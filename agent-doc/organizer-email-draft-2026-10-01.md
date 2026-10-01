# 给组委会的邮件草稿（2026-10-01，由用户发送）

收件：v2d_challenge@nvidia.com
主题：Track 2 (Robotic Grounding): box support surfaces in the evaluation runtime, terminated worlds, and a few rule questions

相对 9/28 版（`agent-doc/organizer-email-draft-2026-09-28.md`）的改动：
- 删去真实时长回放的两问：9/28 23:05 已定为固定逐帧，与 kit 的计分方式一致，不再急；
- 新增第 1 问：方盒支撑面与运行时（发散计划附录 A.6 的三问）；
- 新增第 2 问：评测器遇到被判终止的世界直接报错；
- 第 4 问按用户 10/1 的决定改写：代码仓库不公开，问私有仓库加组委会访问权限行不行；
- 空支撑面一问补上 Tier 2 的数字。

依据（只写查到的事实，推断处在正文里标明）：
- 方盒支撑面：`results/diverge/support_shapes.txt`、`results/t2/support_kinds_tier2_{mf4090,ml40}.txt`、
  `results/diverge/support_py_versions.txt`（v0.4.0 与 aee95f2 的 support.py md5 都是 95e5e33f…）、
  `results/ml40/diverge/support_import_v040.txt`（实建的方盒半尺寸 0.5 m）；#185 比 aee95f2 晚 4 个提交，记在 `agent-doc/experiments/2026-09-30-divergence.md`。
- 发散对照：`results/diverge/diag_verdict_final.txt`（ep7 冒烟 8 个配对种子，v0.4.0 5/8 发散，#185 0/8，单侧 Fisher p = 0.0128）。
- “参考物体在方盒里”是我们按导入器实建几何算的（`results/diverge/support_penetration_as_v040.txt`），ep7 那句 jev 五轮都没过，正文写成“by our computation”。
- 终止即报错：`results/batch1/termination_facts.txt`（aee95f2 `harness.py:580–581`）。
- 空支撑面：`results/day2/empty_support_tier1.txt`（Tier 1 16 条）、`results/t2/support_kinds_tier2_mf4090.txt`（Tier 2 16 条）。
- commit URL：`results/submission/kit_facts.txt`（README.md:23 “Provide a GitHub commit URL for the code that produced each submission”）。

发送前 rxzhou 填署名与队名；10/7 12:00（UTC-6）的参赛说明会也可以当面问第 1、2 问。

---

Dear V2D Challenge organizers,

Thank you for the submission kit and the FlashCHORD trajectory export. We are a Track 2 (Robotic Grounding) team training G1 + Dex3 policies with FlashCHORD, using frame-by-frame playback as the kit scores it. We have a few questions after our first training batches.

1. **Box support surfaces in the evaluation runtime.** In three sequences the support surface is a USD `Cube` whose size comes from `xformOp:scale`: ep1 `vacuum_left_lean_02` (a chair back), ep7 `iron_round_table_02` (a tabletop) and ep28 `squeegee_sweep_away_from_you_03` (two plates). The Tier 2 support files of these sequences are the same kind. `flash_chord/scene/support.py` at aee95f2, the runtime the kit specifies, reads only the cube's `size` and ignores the scale (the file is identical to v0.4.0's), so each box is built as a solid cube with 1 m edges. By our computation this places the reference object inside the box for much of each sequence. Upstream #185 (8c778f905c, "Honor authored scale for Cube support geometry"), four commits after aee95f2, fixes this. Training on these three sequences diverges for us: in a controlled comparison on ep7 (8 paired seeds, short runs), 5 of 8 runs diverged with the v0.4.0 importer and 0 of 8 with #185 (one-sided Fisher p = 0.0128).
   - May we train and export trajectories with aee95f2 plus the #185 change, or with a runtime at or after 8c778f9?
   - Will the runtime that the kit specifies be updated?
   - If neither, how should these three episodes be submitted?

   As we read the packer, all trajectories in one submission must come from the same evaluation build, so the answer decides the runtime for all 30 episodes of a tier.

2. **Terminated worlds during evaluation.** `harness.py` raises "evaluation must disable task failure termination before scoring the full reference" as soon as any world is terminated (aee95f2 `harness.py:580`). The official evaluation runs one deterministic world per episode and every submission needs all scored episodes, so a policy whose single world is terminated cannot produce a trajectory for that episode. How should such an episode be handled?

3. **Empty support surfaces.** For 16 of the 30 sequences (in both Tier 1 and Tier 2), the provided `*_support.usda` contains only an empty Xform, with no Cube or Cylinder. FlashCHORD then fails to build the scene ("support surface contains no Cylinder or Cube collision shapes"). We train these floor-only sequences with `scene.support=false`, which keeps the ground plane, and the evaluator restores that setting from the checkpoint. Is this the intended handling?

4. **Code commit URL.** The kit asks for a GitHub commit URL for the code behind each submission. Our repository is private. Is a commit URL in a private repository acceptable, with read access granted to the organizers on request?

5. **Repeated evaluation.** Each submission uses one deterministic rollout per episode, and we see small differences between repeated evaluations of the same checkpoint. May a team evaluate a checkpoint more than once before packing a submission, or should each submission come from a single evaluation run?

6. **Other rules.**
   - May Tier 1 data be used during development to validate methods intended for Tiers 2 and 3?
   - May a policy trained on one tier be used to warm-start training on another?
   - May Track 1 or Track 3 data be used for Track 2?

Thank you very much for organizing the challenge.

Best regards,
[name / team]
