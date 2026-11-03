# 技术报告素材：事实清单（11/03 14:01 MST 的状态）

技术报告 `docs/report/main.tex` 的事实来源。11/03 由子任务从仓库记录整理，英文；每条后面是出处路径。标 inferred 的是推断。
报告里的关键数字已用 jev 核过（`agent-doc/experiments/2026-11-03-report.claims.json`，`results/jev/report_1103.txt`，12 条全部 verified，对照正常）。

## Pipeline
- recovery → retarget → policy → evaluate, file hand-off only; Tier 1 skips recovery (CLAUDE.md).
- Tier 2 recovery `stages/recovery/export_tier2.py v5.4`, guarded by `tier_guard.forbid_tier1()`.
- Retarget: official `soma_to_g1` v0.4.0 (toolkit 33129dd) with a SOMAWithFlex wrapper, CPU container.
- Policy: FlashCHORD FlashSAC; training copies `v040_p185_nfg` and `v040_p185_nfg_oo` (r3o); eval/export with `fc_8c778f9` (docs/contracts/policy.md).
- docs/architecture-current.md and docs/roadmap.md date from 9/25 and are stale; current state is in agent-doc/plan-*.md.

## Training recipe
- Official: 349,999,104 env steps, 2048 worlds, 9-stage curriculum, object assist force decays to 0 from stage 7; 12 reward terms, only object position (σ 0.2 m); terminations object position 0.10 m, orientation 1.5 rad (plan-step3-recipe-trial-2026-10-04.md; plan-r3o-2026-10-15.md).
- Buffer 4M on RTX 4090, 10M on L40S / L40.
- Variant A (r3a): position σ 0.05 m, orientation termination 0.6 rad.
- r3o: r3a + exp(−θ²/σ²) orientation term, weight 1.0, σ 0.4, set by env var (plan-r3o §2.1).
- Tier 1 single-change fixes: r3o-nv ep17 SP-SR 0 → 0.932 (plan-t1hard); fc20 ep9 MPPE 40.5 → 17.0 cm on 10M (results/t1night/compare_t1hg_t1hf2_mac.txt); pt08 ep25 MPPE 114.1 → 68.7 cm (plan-t1hard, plan-t1mppe).

## Selection and gates
- Tier 2/3 swap rule: ADD-AUC ≥ control + 0.03; MP-SR, SP-SR ≥ control − 0.02; MPPE ≤ control + 0.5 cm; 4096 worlds, own reference.
- Upload gate: export mean +0.010, 4096-world mean +0.005, board + 0.21 × min(changes) ≥ next + 0.002 (plan-t3auc1 §2, plan-final §2).
- 0.21 from t2a1102: own-ref +0.0187, board +0.0039; b1019a own-ref +0.0077, board −0.0029.

## Tier 2 / Tier 3 methods
- v5.4: support constraints on static segments, Brownian-bridge interpolation, flip and height handling, non-penetration by minimal rotation, smoothing; parameters from Tier 2 only.
- Tier 3: Grounding DINO + SAM2 masks, CARI4D (MoGe-2 depth, FoundationPose, contact refinement), SOMA, focal 866.3 px vs default 830 (plan-t3-kfix), dr2s, dyn7, gb4 Kabsch refit, gb5 FoundationPose timeline selection, frame-0 alignment with Tier 1 frame 0 (allowed 10/21; plan-t3align).

## Board (results/board/lb_1103_1401.txt, Kaggle tie rule)
- Tier 1 0.635 (11) / 0.867 (9) / 0.700 (11) / 8.47 (9); Tier 2 0.518 (6) / 0.733 (5) / 0.533 (6) / 15.32 (9); Tier 3 0.282 (5) / 0.467 (1) / 0.100 (3) / 36.60 (4).
- History: Tier 1 MPPE 24.54 (10/13) → 8.47 (11/02); Tier 3 AUC 0.106 (10/18) → 0.282 (10/29), SP-SR 0.267 → 0.467.

## r3o ablation (4096-world ADD-AUC, own reference)
- Tier 2: ep10 0.397 → 0.594, ep0 0.400 → 0.774, ep26 0.465 → 0.715, ep18 0.521 → 0.855, ep6 0.550 → 0.777, ep21 0.516 → 0.503 (10M; 4M 0.555 but MP-SR 0.965 → 0.316).
- Tier 3: ep0 0.528 → 0.795 (10M), ep18 0.626 → 0.826, ep24 0.731 → 0.835, ep26 0.579 → 0.812 (10M arm collapsed, SR 0), ep23 0.702 → 0.783, ep12 0.507 → 0.672 (MP-SR 0.967 → 0.942, not swapped).
- Tier 1: ep24 0.580 → 0.948, ep7 0.622 → 0.915 (plan-t1r3o).

## Compute
- mf4090 RTX 4090 24 GB; ml40 L40S 48 GB; l40n L40 46 GB (from 11/02).
- About 2 h training plus about 10 min eval and export per run.
- 374 full-length eval records (results/day2 185, results/ml40/day2 187, results/l40n/day2 2), about 373 unique runs (inferred count); about 850 GPU-hours (inferred).

## Known failures
- Tier 1 lost: ep1, 2, 4, 9, 11, 25, 28; object crosses the error threshold soon after first contact.
- Tier 2 lost: ep28, 25, 4, 11, 1, 9, 17.
- Tier 3 lost: ep1, 2, 3, 4, 13, 16, 17, 19, 25; causes include reference objects rotating before contact (ep3 51°, ep4 85°), objects starting on high surfaces that fall in sim (ep16, ep25), a stool without collision (ep1).
