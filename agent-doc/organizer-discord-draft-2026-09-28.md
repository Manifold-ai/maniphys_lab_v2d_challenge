# Discord #v2d-challenge（Track 2 帖）草稿（2026-09-28，由用户发送）

只问最要紧的一件事：真实时长回放训练的 checkpoint 怎么计分。“时间轴会错位”是我们读 kit 代码得出的推断（jev 0.16，未核实），
**发之前先用新评测器在真实时长的 checkpoint 上实测一次**；实测不同就改写。依据 `results/submission/kit_facts.txt`。

---

Hi! Question on Track 2 scoring for checkpoints trained with real-time playback.

The FlashCHORD G1 recipe defaults to `task.source_frame_playback: true` (one 30 fps source frame per 50 Hz control step, ~1.67x real time). With `false` it resamples the reference to real time, e.g. 921 control steps for a 553-frame Tier 1 sequence.

As we read the kit, `evaluate_policy.py` restores each checkpoint's own playback setting, the exported trajectory numbers rows by `reference_frame = step + start_frame`, and `pack_submission.py` matches row k to reference frame k. So a real-time checkpoint would be scored out of step with the reference. Did we misread this?

1. Are `source_frame_playback: false` checkpoints valid submissions?
2. If yes, could the exporter sample at the source-frame timestamps, or should everyone use frame-by-frame playback?

It matters a lot for us: on one Tier 1 sequence, real-time training gave per-world MP-SR 0.887 in FlashCHORD's evaluator, versus 0.0005 at 1.67x. Thanks!
