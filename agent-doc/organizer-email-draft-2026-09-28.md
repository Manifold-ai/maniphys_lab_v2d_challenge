# 给组委会的邮件草稿（2026-09-28，由用户发送）

收件：v2d_challenge@nvidia.com
主题：Track 2 (Robotic Grounding) — questions on eval_robotic_grounding.py, reference playback speed, and empty support surfaces

依据：`agent-doc/experiments/2026-09-28-playback.md`（回放速度对照、官方来源查证）、`results/playback/eval_script_search.txt`、
`results/day2/palm_frame_probe_all.txt`、`results/day2/empty_support_tier1.txt`。只写我们查到的事实，不写解读当成官方口径。

---

Dear V2D Challenge organizers,

We are a Track 2 (Robotic Grounding) team training G1 + Dex3 policies with FlashCHORD (release v0.4.0). We have a few questions that directly affect how we train and evaluate, and would be grateful for your guidance.

1. **Evaluation script.** The challenge page says submissions are produced with the provided `eval_robotic_grounding.py`. We could not find it in the Hugging Face dataset or in any branch or release of nvidia-isaac/video_to_data (as of September 28). When do you expect to release it?

2. **Reference playback speed during evaluation.** Our retargeted Tier 1 references are 30 fps. The FlashCHORD G1 recipe uses `task.source_frame_playback: true`, which plays one source frame per 50 Hz control step, so the references run at about 1.67x real time. The Isaac Lab whole-body tracking command resamples to real time from release/0.3.0 on, and FlashCHORD's own evaluator restores each checkpoint's playback setting. Which playback will the official evaluation use?
   - Frame-by-frame (one source frame per control step)?
   - Real time at the capture frame rate?
   - Or whatever setting is stored in the submitted checkpoint?

   The choice matters a lot for us. On one sequence (rice_cooker_clockwise_04, Tier 1), the full-recipe policy trained and evaluated at real time reached ADD-AUC 0.547 and MP-SR 0.887. The same recipe at 1.67x reached ADD-AUC 0.431 and MP-SR 0.0005.

3. **Real-time playback and the G1 palm-frame check.** With `source_frame_playback: false`, FlashCHORD's G1 embodiment rejects the resampled reference. `_validate_palm_frames` requires palm frames to match joint FK within 1e-4 m / 1e-4 rad on every frame. After interpolation we measure up to 4.8 mm / 0.028 rad across the 30 Tier 1 sequences. We relaxed only these two validation tolerances to make real-time playback run. Is real-time playback with G1 intended to be supported? If so, what tolerances do you recommend?

4. **Empty support surfaces.** For 16 of the 30 Tier 1 sequences, the provided `*_support.usda` contains only an empty Xform, with no Cube or Cylinder. FlashCHORD then fails to build the scene: "support surface contains no Cylinder or Cube collision shapes". We train these floor-only sequences with `scene.support=false`, which keeps the ground plane. Is this the intended handling? Will the official evaluation do the same?

5. **Other questions.**
   - Is there a hidden holdout for Track 2?
   - May Tier 1 data be used during development to validate methods intended for Tiers 2 and 3?
   - May a policy trained on one tier be used to warm-start training on another?
   - May Track 1 or Track 3 data be used for Track 2?

Thank you very much for organizing the challenge.

Best regards,
[name / team]
