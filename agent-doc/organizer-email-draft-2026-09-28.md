# 给组委会的邮件草稿（2026-09-28，由用户发送）

收件：v2d_challenge@nvidia.com
主题：Track 2 (Robotic Grounding) — scoring real-time-playback checkpoints, empty support surfaces, and a few rule questions

依据：`results/submission/kit_facts.txt`（官方 submission kit 与上游 aee95f2 的原文摘录，jev 8 条核实）、
`agent-doc/experiments/2026-09-28-playback.md`（回放速度对照）、`results/day2/palm_frame_probe_all.txt`、`results/day2/empty_support_tier1.txt`。
只写查到的事实；第 1 问里“时间轴会错位”是我们读代码得出的推断（jev 0.16，未核实），**发送前先用新评测器在真实时长的 checkpoint 上实测一次**，
实测结果不同就改写这一问。

9/28 22:40 改写：kit 发布后，原第 1 问（评测脚本何时发布）与 holdout 一问已有答案，删去；回放一问改成对齐问题；新增代码仓库可见性与重复评测两问。
上一版见 git 历史。

---

Dear V2D Challenge organizers,

Thank you for releasing the submission kit and the FlashCHORD trajectory export. We are a Track 2 (Robotic Grounding) team training G1 + Dex3 policies with FlashCHORD, and we have a few questions after reading the kit.

1. **Checkpoints trained with real-time playback.** Our retargeted Tier 1 references are 30 fps. The FlashCHORD G1 recipe plays one source frame per 50 Hz control step (`task.source_frame_playback: true`, about 1.67x real time); with `source_frame_playback: false` it resamples the reference to real time. As we read the kit, `evaluate_policy.py` rebuilds each checkpoint's own config, the exported trajectory numbers its rows by `reference_frame = step + start_frame`, and `pack_submission.py` matches row k to reference frame k of the released 30 fps reference. If that reading is right, a checkpoint trained at real time (for example 921 control steps for a 553-frame sequence) would have its rollout compared with the reference out of step. Please correct us if we misread the kit.
   - Are checkpoints trained with `source_frame_playback: false` valid submissions?
   - If they are, how should their trajectories be aligned with the reference frames? Could the exporter sample the rollout at the source-frame timestamps, or should all teams use frame-by-frame playback?

   This matters a lot for us. On one sequence (rice_cooker_clockwise_04, Tier 1), the full-recipe policy trained and evaluated at real time reached ADD-AUC 0.547 and a per-world MP-SR of 0.887 in FlashCHORD's evaluator. The same recipe at 1.67x reached ADD-AUC 0.431 and a per-world MP-SR of 0.0005.

2. **Real-time playback and the G1 palm-frame check.** With `source_frame_playback: false`, FlashCHORD's G1 embodiment rejects the resampled reference. `_validate_palm_frames` requires palm frames to match joint FK within 1e-4 m / 1e-4 rad on every frame. After interpolation we measure up to 4.8 mm / 0.028 rad across the 30 Tier 1 sequences. We relaxed only these two validation tolerances. If real-time playback is allowed, is that acceptable, and what tolerances do you recommend?

3. **Empty support surfaces.** For 16 of the 30 Tier 1 sequences, the provided `*_support.usda` contains only an empty Xform, with no Cube or Cylinder. FlashCHORD then fails to build the scene: "support surface contains no Cylinder or Cube collision shapes". We train these floor-only sequences with `scene.support=false`, which keeps the ground plane, and the evaluator restores that setting from the checkpoint. Is this the intended handling?

4. **Code commit URL.** The packer records a GitHub commit URL for the code behind each submission. Does that repository need to be public, or accessible to the organizers?

5. **Repeated evaluation.** Each submission uses one deterministic rollout per episode, and we see small differences between repeated evaluations of the same checkpoint. May a team evaluate a checkpoint more than once before packing a submission, or should each submission come from a single evaluation run?

6. **Other rules.**
   - May Tier 1 data be used during development to validate methods intended for Tiers 2 and 3?
   - May a policy trained on one tier be used to warm-start training on another?
   - May Track 1 or Track 3 data be used for Track 2?

Thank you very much for organizing the challenge.

Best regards,
[name / team]
