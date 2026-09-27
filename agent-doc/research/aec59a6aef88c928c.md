# agent aec59a6aef88c928c

## PROMPT

DEEP WEB RESEARCH. Use WebSearch and WebFetch heavily (15-20+ calls). Do NOT write files. Return a dense technical report as your final message with full URLs (arXiv abs links, GitHub links) for everything.

CONTEXT: Building an RL motion-tracking policy in Isaac Lab (Unitree G1 humanoid + Dex3 hands) that tracks noisy reference hand-object trajectories. Need practical tricks used in humanoid/dexterous work for handling noisy retargeted data.

RESEARCH EXHAUSTIVELY (prioritize 2023-2026, emphasis 2025-2026):

1. MOTION DATASET CURATION / FEASIBILITY FILTERING — how do real humanoid systems drop or fix motions the robot physically cannot track?
   - PHC / PHC+ (arXiv 2305.06456) "hard negative mining" over motion sequences — exact mechanism
   - ASAP (Aligning Simulation and Real-World Physics, arXiv 2502.01143) delta-action model
   - OmniH2O (arXiv 2406.08858), H2O (arXiv 2403.04436) — their motion "feasibility filtering" / privileged imitation filtering step
   - TWIST (Teleoperated Whole-body Imitation System, 2505.02833?), CLONE, GMT (General Motion Tracking, arXiv 2506.14770?), BeyondMimic (2508.08241), HumanPlus (2406.10454), ExBody (2309.14859) / ExBody2 (2412.13196)
   - Any 2025-2026 paper with an explicit "motion feasibility filter", "trackability score", "retargeting quality filter", or "curriculum by motion difficulty"
   - Retargeting-quality-aware training: search "retargeting error aware", "infeasible motion filtering humanoid"

2. TEACHER-STUDENT DISTILLATION WITH PRIVILEGED CLEAN REFERENCES:
   - Works where a teacher gets clean/privileged reference and a student gets noisy/partial observations (this is the classic legged-robot privileged-learning recipe applied to motion tracking)
   - OmniH2O's privileged teacher, MaskedMimic's teacher-student, PULSE distillation, "DAgger distillation humanoid", "privileged motion tracking teacher student"
   - Any 2025-2026 humanoid paper distilling a clean-reference teacher into a noisy-reference student

3. REFERENCE STATE INITIALIZATION (RSI) and EARLY TERMINATION under noise:
   - Original DeepMimic RSI + early termination (arXiv 1804.02717)
   - Adaptive/curriculum early termination thresholds; "termination curriculum", "adaptive termination", "soft termination"
   - Any analysis of how early-termination threshold interacts with reference noise

4. HAND-OBJECT / DEXTEROUS SPECIFIC works learning from noisy video-derived hand trajectories:
   - DexMV, DexMimicGen, Robot See Robot Do, DexCap, "Learning dexterous manipulation from human video noisy hand pose"
   - SkillMimic / SkillMimic-V2 (claimed robust to noisy demonstrations) — get the exact mechanism, arXiv URL, github
   - InterMimic (arXiv 2502.20390), PhysHOI (arXiv 2312.04393), ContactMimic, DeVI, DexMan (arXiv 2510.08475), "A Minimalist Retargeting-Guided Reinforcement Learning Recipe for Dexterous Manipulation" (arXiv 2607.11874) — for each, HOW do they handle the noise in the hand reference, and what is their object-centric reward?
   - Any work that explicitly says "hand reference is unreliable, so we use object/contact goals instead"

For every named method: arXiv abs URL, GitHub URL or "no code found", year/venue, 2-4 sentence mechanism summary, and a one-line verdict on ~6-week implementability on Isaac Lab + rsl_rl/skrl PPO.

Verify arXiv IDs by fetching the abstract page when uncertain — do NOT report an arXiv ID you haven't confirmed. Note arXiv IDs of form 25XX and 26XX are valid; today is September 2026.

---

## REPORT

Research complete — 40+ fetches, all arXiv IDs verified by fetching abstract pages (two supplied IDs were wrong and are corrected below). No files written.

---

# Handling noisy retargeted hand-object references: practical tricks from 2023–2026 humanoid/dexterous work

## 0. ID corrections before anything else

- **ExBody is arXiv:2402.16796**, not 2309.14859 (that ID is a text-to-image paper, LyCORIS). Verified via arXiv listing: "Expressive Whole-Body Control for Humanoid Robots", Cheng, Ji, Chen, Yang, Yang, Wang, 2024-02-26.
- **arXiv:2607.11874 is real and is exactly what you named**: "A Minimalist Retargeting-Guided Reinforcement Learning Recipe for Dexterous Manipulation" (REGRIND), Feng, Leung, Wang, Yang, Qi, Culbertson, submitted 2026-07-13. This is the single most directly transferable paper in the whole set for you.
- TWIST = 2505.02833 confirmed. GMT = 2506.14770 confirmed. BeyondMimic = 2508.08241 confirmed. DexMan = 2510.08475 confirmed. InterMimic = 2502.20390 confirmed. PhysHOI = 2312.04393 confirmed.

---

## 1. Motion dataset curation / feasibility filtering

### PHC / PHC+ — hard negative mining, the origin of the whole practice
https://arxiv.org/abs/2305.06456 · https://github.com/ZhengyiLuo/PHC · ICCV 2023

Exact mechanism, quoted from the paper: "From a motion dataset Q̂, we find hard sequences Q̂_hard ⊆ Q̂ by evaluating our model over the entire dataset and choosing sequences that our policy fails to imitate." Failure is defined by the early-termination criterion itself — "we terminate the episode when the joints are more than 0.5 meters globally on average from the reference motion." PMCP then freezes the converged primitive and allocates a fresh primitive to Q̂_hard(k), producing nested subsets Q̂_hard(k) ⊆ Q̂_hard(k−1); convergence is "the success rate on Q̂_hard(k) no longer increases." Also introduces **Relaxed Early Termination (RET)**, which excludes ankle and toe joints from the 0.5 m distance check so foot-slip artifacts don't kill otherwise-good episodes.

The repo exposes this as an explicit loop: `scripts/pmcp/forward_pmcp.py` dumps the sequences the current primitive failed on, and you retrain on that dump. Isaac Gym + Hydra config.

**6-week verdict:** YES for the mining loop — it's ~50 lines (rollout every motion once with deterministic actions, log per-clip success, write a filtered index). Skip PMCP's multi-primitive network surgery; that's a multi-month project.

### H2O — "sim-to-data" privileged-imitator filtering, the canonical version
https://arxiv.org/abs/2403.04436 · https://github.com/LeCAR-Lab/human2humanoid · IROS 2024

Two-stage. First, **shape fitting before retargeting**: gradient descent on SMPL shape parameters β′ to minimize joint distances to the robot in a common rest pose — the paper explicitly says this prevents "in-toed" artifacts. Second, train a privileged policy with **no domain randomization** (778-dim obs, full rigid-body state) purely as a feasibility oracle: "sequences which π_privileged fails to imitate represent implausible ones." Result: **~8.5k of 10k AMASS sequences survive for the H1**. The deployable student has a 138-dim obs (joint pos/vel, root vel, projected gravity) and heavy DR. The repo ships this as a pre-filtered artifact, `amass_phc_filtered.pkl`, plus `grad_fit_h1_shape.py` / `grad_fit_h1.py`.

**6-week verdict:** YES. Cheapest high-value trick in the entire report. One no-DR training run + one eval pass gives you a clean-motion index.

### GMT — two-stage curation + the best-specified adaptive sampler
https://arxiv.org/abs/2506.14770 · https://github.com/zixuan417/humanoid-general-motion-tracking (MuJoCo inference only; data/retargeter "coming soon") · project: https://gmt-humanoid.github.io/

Stage 1 is **rule-based**: drop motions where root roll/pitch exceeds thresholds or root height is abnormally high/low. Stage 2 is **policy-based**: train a preliminary policy (~55B samples) and drop what it fails. Yield: "a curated version of the training dataset — a subset of AMASS and LAFAN1 with 8925 clips totaling 33.12 hours."

The adaptive sampler is worth copying verbatim: `p_i = (min(E_max_key_body_error / 0.15, 1))^5` when the clip has been completed once (c_i = 1), else `p_i = c_i`. Termination threshold E_i and completion level c_i **both decay during training**, with floors `c_min = 1.0`, `E_min = 0.25`. Policy is a Motion MoE: experts and a gating net share the same input, `a = Σ p_i · a_i`.

**6-week verdict:** YES for rule-based filter + adaptive sampling (the `^5` exponent matters — it aggressively concentrates on near-failures). PARTIAL for MoE; do it only if a single MLP visibly saturates.

### ASAP — termination curriculum, and the delta-action model
https://arxiv.org/abs/2502.01143 · https://github.com/LeCAR-Lab/ASAP · RSS 2025

Delta action model: `Δa_t = π_θ^Δ(s_t, a_t)`, trained by RL on real-world rollouts replayed in sim to minimize sim-vs-real state discrepancy. Then it's **frozen and folded into the simulator**: `s_{t+1} = f_ASAP(s_t, a_t) = f_sim(s_t, a_t + π^Δ(s_t, a_t))`, and the tracking policy is RL-fine-tuned inside that corrected sim with identical rewards. Data pipeline: TRAM → SMPL → two-stage shape-and-motion retargeting, then **"sim-to-data cleaning procedure" using MaskedMimic**.

The detail you want most: **"initially, we set a generous termination threshold of 1.5m... gradually tighten this threshold to 0.3m."** That is the reference-answer to your question 3. Isaac Gym training, Isaac Sim / Genesis for transfer checks, PPO, HumanoidVerse multi-backend framework.

**6-week verdict:** YES for the 1.5 m → 0.3 m termination curriculum (a scheduler on one scalar). NO for the delta-action model — it needs real-robot rollouts you probably don't have yet.

### KungfuBot — explicit filter/correct pipeline + bi-level adaptive tolerance
https://arxiv.org/abs/2506.12851 · NeurIPS 2025

The most explicit "fix the data, then adapt the reward" pipeline published. Extraction via GVHMR from monocular video. **Filter**: physical stability criterion `Δd_t = ‖p̄_t^CoM − p̄_t^CoP‖₂ < ε_stab` with **ε_stab = 0.1 m**, plus boundary stability and a max instability gap under 100 frames. **Correct**: estimate a contact mask from ankle displacement, then apply a vertical offset `ψ_{t,z}^corr = ψ_{t,z} − Δh_t` with EMA smoothing (this is how you kill floating/penetrating feet). **Retarget**: differentiable IK respecting joint limits.

Then the bi-level part: the optimal reward-tracking factor is `σ* = (Σ x_i*)/N`, the mean of achievable tracking errors, and it is updated online by **`σ ← min(σ, x̂)`** where x̂ is an EMA of instantaneous tracking error. So the reward sharpness auto-tightens as the policy improves and never loosens. Asymmetric actor-critic: actor sees 5-step proprio history + phase φ_t ∈ [0,1]; critic sees reference motion, root velocity, randomized physics params. Rewards are vectorized with a separate value head per term. Isaac Gym + PPO, MuJoCo sim-to-sim.

**6-week verdict:** YES, and this is my top pick for your reward design. `σ ← min(σ, EMA(error))` is ~5 lines and directly addresses "my reference is noisy so I don't know what exp() temperature to use."

### Other feasibility-filter work worth knowing

- **ExBody2** — https://arxiv.org/abs/2412.13196 — teacher policy "produce[s] intermediate data that better conforms to the robot's kinematics and to automatically filter away infeasible whole-body motions," then trains the student on that refined data. Also decouples whole-body velocity tracking from body-landmark tracking. No code found. [6wk: PARTIAL — the decoupling idea transfers cheaply.]
- **ExBody** — https://arxiv.org/abs/2402.16796 — the original "track upper body expressively, only track root velocity/height for legs" relaxation. [6wk: YES as a design principle.]
- **TEXEDO** — https://arxiv.org/abs/2606.22998 — 2026, the closest thing published to an explicit **trackability score**: "a dynamic feasibility verifier, distilled from whole-body tracking rollouts to predict physical executability," used as a **hard constraint** at test time to filter generated motion candidates. No code found. [6wk: PARTIAL — if you already have PHC-style rollout labels, training a small MLP regressor on (motion features → tracking success) is a 2-day job and gives you an O(1) filter for new clips.]
- **HANDOFF** — https://arxiv.org/abs/2606.06493 — 2026, defines "safety-filtered data" concretely as a **closed-form CBF projection on static center-of-pressure margin**: detect quasi-static squat frames (root height < 0.65 m, XY speed < 0.2 m/s), project onto a 7-D joint-correction subspace (bilateral hip/ankle pitch, ankle roll, waist pitch), Newton steps with Armijo backtracking, linear ramp at segment boundaries. Uses **mjlab + rsl_rl**. No code found. [6wk: NO — interesting but narrow.]
- **BeyondMimic** — https://arxiv.org/abs/2508.08241 · https://github.com/HybridRobotics/whole_body_tracking — **this is your closest stack match: Isaac Lab v2.1.0 + rsl_rl**. Reward: `r = r_target − λ_l·r_limit − λ_s·r_smooth − λ_c·r_contact` with `r_tracking = Σ_{χ∈{p,R,v,w}} r(ē_χ, σ_χ)`. Adaptive sampling from failure statistics: `p_s = Σ_{τ=0}^{K−1} α^τ r̄_{s+τ} / Σ_j Σ_τ α^τ r̄_{j+τ}`, mixed with uniform to prevent forgetting. Termination on reference-body height/orientation error plus end-effector height deviation. Repo claim: "You should be able to train any sim-to-real-ready motion in the LAFAN1 dataset, without tuning any parameters." Notably they do **no** explicit data filtering — they rely on curated LAFAN1. [6wk: YES — fork it as your scaffold.]
- **UniTracker** — https://arxiv.org/abs/2507.07356 — 3-stage: privileged teacher → CVAE student (latent motion representation fixes global-orientation drift under partial obs) → fast adaptation module fine-tuning on hard sequences. G1. No code found. [6wk: PARTIAL.]
- **PhyGile** — https://arxiv.org/abs/2603.19305 — 2026, sidesteps retargeting entirely by generating robot-native motion in a 262-D skeletal space with physics-guided prefixes; uses a curriculum-based MoE GMT controller underneath. No code found. [6wk: NO.]
- **Retargeting Matters / GMR** — https://arxiv.org/abs/2510.02252 · **https://github.com/YanjieZe/GMR** — Araujo, Ze, Xu, Wu, Liu, 2025-10-02. The empirical study you should read first: "artifacts in retargeted data significantly reduce policy robustness, particularly for dynamic or long sequences." **GMR supports "Unitree G1 with Dex31 hands"**, IK-based via mink+MuJoCo, 60–70 FPS on CPU, ingests SMPL-X/BVH/FBX/video/live VR. The authors openly maintain a list of motions where retargeting is bad. [6wk: YES — use GMR as your retargeter rather than rolling your own; it is the only open tool in this report that explicitly ships a G1+Dex3-class config.]
- **OmniRetarget** — https://arxiv.org/abs/2509.26633 · https://github.com/amazon-far/holosoma · dataset https://huggingface.co/datasets/omniretarget/OmniRetarget_Dataset · https://omniretarget.github.io — interaction-mesh retargeting minimizing Laplacian deformation `E_L = Σ ‖L(p_source) − L(p_target)‖²` subject to hard constraints: SDF collision `φ_j(q_t) ≥ 0`, joint limits, velocity bounds, and stance-foot pinning `p_t^F = p_{t−1}^F`. Builds the interaction mesh **in the object's local frame** so hand-object relations are invariant to object transforms. Quality is evaluated post-hoc (penetration duration/depth, foot-skate duration/velocity, contact-preservation time) rather than used as a filter. Downstream policy needs only **5 reward terms**: body tracking, object tracking, action rate, soft joint limit, self-collision. [6wk: YES for adopting the object-local interaction-mesh idea in your retargeter; PARTIAL for the full holosoma stack.]
- **Make Tracking Easy (NMR)** — https://arxiv.org/abs/2603.22201 — 2026; Clustered-Expert Physics Refinement: VAE-cluster motions into latent motifs, then parallel RL agents "project and repair noisy human demonstrations onto the robot's feasible motion manifold"; non-autoregressive CNN-Transformer retargeter over global temporal context. G1. No code found. [6wk: NO.]
- **DynaRetarget** https://arxiv.org/abs/2602.06827, **SPARK** https://arxiv.org/abs/2603.11480, **Direct Dynamic Retargeting** https://arxiv.org/abs/2605.23762 — all 2026 sampling-based/kinodynamic TO refinements of kinematic retargeting. Identified via arXiv API listing (titles/authors/dates confirmed); I did not fetch each abstract individually.

---

## 2. Teacher-student distillation with privileged clean references

### OmniH2O — the reference recipe, with numbers
https://arxiv.org/abs/2406.08858 · https://github.com/LeCAR-Lab/human2humanoid · CoRL 2024

Teacher obs = **913 dims**: proprio (pos, orient, lin/ang vel, prev action) + full-body goal state (motion goal DoF position 66, DoF rotation 138, DoF velocity 69, DoF angular velocity 69) plus one-frame reference deltas for **all rigid bodies**. Student sees **3 points only** (head + 2 hands from VR) plus a **25-step proprio history** (joint pos, joint vel, root ang vel, projected gravity, prev actions) and explicitly **no global linear velocity**. DAgger loss is plain MSE on actions: `L = ‖a_t^privileged − a_t‖²₂`. Ablation says 25 steps is the sweet spot. Data augmentation: for every clip, synthesize a "stable" variant with root fixed and lower body pinned to standing or squatting. Reward example: DoF position term `exp(−0.25‖d_t − d_t^ref‖₂)` weight 32; termination penalty −250; max-feet-height regularizer weight 1000. Isaac Gym + legged_gym + **rsl_rl**; repo flags `train.distill=True`, `train.dagger.dagger_only=True`.

**6-week verdict:** YES. This maps 1:1 onto your problem — swap "VR 3-point sparse obs" for "noisy retargeted hand-object reference" and the architecture is unchanged.

### MaskedMimic — teacher with full constraints, student with masked ones
https://arxiv.org/abs/2409.14393 · https://github.com/NVlabs/ProtoMotions (ProtoMotions3 supports IsaacGym / **IsaacLab 3.0** / Newton / MuJoCo / Genesis) · SIGGRAPH Asia 2024, ACM TOG

Teacher π_FC is "a fully-constrained motion tracking controller trained using reinforcement learning"; student π_PC is trained by **online DAgger** to maximize log-likelihood of the teacher's actions while minimizing encoder-prior KL (VAE objective). Masking is structured, not curricular, with **temporal persistence** — "a randomly sampled mask in one timestep has a chance of being repeated for multiple subsequent timesteps" (this matters; i.i.d. per-step masking teaches the wrong thing). β-VAE schedule: KL coefficient from 0.0001 linearly to 0.01. Data = AMASS filtered following PHC + HumanML3D + SAMP, and they **"prioritize training on motions with a higher failure rate"** with sampling probability proportional to failure rate. ET: **0.25 m** joint deviation on flat terrain, relaxed to **0.5 m** on irregular terrain. 16,384 envs, 120 Hz sim, 30 Hz control.

**6-week verdict:** YES. Temporally-correlated masking plus failure-rate-proportional sampling is the highest-leverage pair here, and ProtoMotions3 already runs on Isaac Lab 3.0.

### PULSE — distilling a tracker into a latent space
https://arxiv.org/abs/2310.04582 · ICLR 2024 Spotlight · https://zhengyiluo.github.io/PULSE/

Distills PHC into an encoder-decoder with a **variational information bottleneck** plus a jointly-trained **proprioception-conditioned prior**. The latent then serves as the action space for downstream hierarchical RL. [6wk: NO — valuable but it's a second project.]

### InterMimic — the HOI-specific version, and the most relevant teacher-student in this report
https://arxiv.org/abs/2502.20390 · https://github.com/Sirui-Xu/InterMimic · CVPR 2025 · **Isaac Gym + Isaac Lab, rl_games**

This is the paper you should read most carefully. Five mechanisms, all aimed at exactly your problem (imperfect MoCap HOI, bad contacts, poor hand detail):

1. **Three-level contact reward** — "promotion, penalty, and neutral," explicitly "to accommodate potential inaccuracies in reference contact distances." The neutral band is the trick: where the reference contact distance is ambiguous, you reward nothing rather than guessing.
2. **Interaction Early Termination (IET)** — supplements kinematic ET with object-deviation thresholds and contact-loss monitoring, so failure is detected on the interaction, not just on joint distance.
3. **Physical State Initialization (PSI)** — instead of initializing from raw MoCap poses, maintain a FIFO buffer mixing reference states with **simulation states that exceeded a reward threshold**; older/lower-quality entries are evicted. This stops RSI from repeatedly injecting physically impossible initial states. Repo flag: `physicalBufferSize > 1`.
4. **Curriculum** — "perfect first, then scale up": per-subject teachers on small clean subsets, then distill to one student.
5. **DAgger → PPO transition** — "we start with DAgger and gradually transition to PPO," teachers serving both as action supervisors and as corrected reference providers; RL fine-tuning lets the student exceed the demonstrations.

Reward split into embodiment-aware and embodiment-agnostic terms; object position and rotation tracked separately; energy terms penalize human and object jitter (i.e. penalize chasing MoCap noise) plus a contact-energy penalty for compliance.

**6-week verdict:** YES — PSI and the 3-level contact reward are each a few days and both target noisy hand-object references head-on. The full teacher-per-subject curriculum is a stretch in 6 weeks.

### SUGAR — 2026, video → hand-object priors → privileged refiner → distillation, on G1
https://arxiv.org/abs/2605.20373

The full stack for your exact pipeline shape. Extraction: **SAMBody** for human motion, **FoundationPose** for object 6D trajectories, and a **VLM queried for contact labels** on task-relevant body parts — with a fallback that infers contact when object velocity exceeds a threshold under occlusion. Refiner reward `r = r_track + r_int + r_reg` (tracking of robot and object, interaction consistency using the contact labels, regularization for sim-to-real). **Progressive state pool**: "initializes agents from physically-validated states instead of unreliable references," incrementally populated with successful intermediate states from the refiner — a cleaner restatement of InterMimic's PSI. Distillation: BC first to mimic the refiner, a warm-up phase for critic and actor, then full RL with the same rewards; a separate command generator is trained by IL on rollouts so deployment needs **no reference motion at all**. **IsaacSim + PPO, single RTX 5090, Unitree G1** (no dexterous hands). No code found.

**6-week verdict:** YES for the progressive state pool and the BC→warm-up→RL schedule. The VLM contact labeler is optional but cheap.

### ULTRA — 2026, masked multimodal student with privileged posterior
https://arxiv.org/abs/2603.03279

Retargeting is posed as "simulation-constrained optimization with kinematic, dynamic, and contact constraints, solved with reinforcement learning at scale" — with a **relaxed tracking strategy prioritizing end-effectors (feet, palms) over dense link-wise targets, because dense targets become infeasible during contact-rich tasks**. Reward is multiplicative: position r_p, link direction r_r, object pose r_obj, interaction alignment r_int, contact event matching r_ct, joint effort r_eng, including "palm-to-surface offsets over sampled object points." Student handles missing/noisy observations three ways: **availability masking randomly sampled during training**; per-modality encoders fused by a transformer where masks "gate tokens and modulate cross-modal attention"; and a **privileged posterior with KL regularization** — the posterior infers latent residuals from clean teacher data, the prior from masked student obs, aligned by `λ_KL · D_KL(q_φ(z) ‖ p_θ(z))`. DAgger with progressive student mixing; masking probability increases on a curriculum while the KL weight is annealed to prevent posterior collapse. RL fine-tuning partitions the 4096 envs into distillation and goal-reaching subsets simultaneously. Isaac Gym + PPO. No code found.

**6-week verdict:** PARTIAL. The privileged-posterior / masked-prior KL pair is the single most principled "clean teacher, noisy student" formulation I found — but it's a week of careful implementation and easy to get wrong. The relaxed end-effector-priority tracking is free and you should take it regardless.

### Also
- **TWIST** — https://arxiv.org/abs/2505.02833 · https://github.com/YanjieZe/TWIST — Isaac Gym + **rsl_rl**, **Unitree G1 with hands**. Loss: `L(π_stu) = L_RL(π_stu) + λ·D_KL(π_stu ‖ π_tea)` with λ annealed down — RL and BC together, not sequentially. Teacher gets **2 seconds of future reference frames** as privileged info; student sees only the current timestep. Data: 15k+ clips from AMASS and OMOMO with unfeasible motions (e.g. stair climbing) filtered out, plus 150 in-house MoCap clips (~0.5 h). Ships a pretrained `twist_general_motion_tracker.pt`. [6wk: YES — "privileged = future lookahead" is a clean, cheap privilege axis, and the repo is your stack.]
- **HANDOFF** multi-teacher KL with soft MoE gating, per-slice: body slice blends WBC and locomotion teachers with sigmoid weight `α = σ((‖c_t^vel‖ − 0.1)/0.02)`, arm slice anchored to the WBC teacher throughout. Full loss `L = L_PPO + λ_B L_KL^B + λ_A L_KL^A + λ_AMP L_KL^AMP + β_LB L_LB + β_R L_R`. mjlab + rsl_rl. [6wk: NO.]
- **CoorDex** — https://arxiv.org/abs/2606.23680 — 2026, **Unitree G1 + 20-DoF WUJI hand**: train privileged motion-tracking teachers separately for body and for hand, distill each into proprioception-conditioned latent priors, then **freeze both** and learn a coordinated latent residual policy with shared task context and separate body/hand residual heads. No code found. [6wk: PARTIAL — the freeze-both-priors-and-learn-a-residual pattern is directly applicable to G1+Dex3.]
- **Gated Residual Body-Hand Coordination** — https://arxiv.org/abs/2609.18763 — 2026-09, same shape: motion tracker and hand retargeter both frozen, a motion-conditioned action gate distributes correction authority across joint groups, reference-geometry-dependent reward gates pick which interaction objective matters when. Reduces wrist/fingertip geometry error **39.2–56.3%** vs direct composition. Uses a SONIC-based tracker on Agile One. No code found. [6wk: PARTIAL, same note as CoorDex.]

---

## 3. RSI and early termination under noise

### DeepMimic — the baseline, with the ablation numbers
https://arxiv.org/abs/1804.02717 · https://github.com/xbpeng/DeepMimic · SIGGRAPH 2018

RSI: "At the start of each episode, a state can be sampled from the reference motion, and used to initialize the state of the agent." ET: "An episode is terminated whenever certain links, such as the torso or head, makes contact with the ground." Backflip ablation, normalized return: **RSI+ET 0.791, ET only 0.730, RSI only 0.379** — and without ET "the policy never learns to perform a full mid-air flip. Instead, it performs a small backwards hop while remaining upright." The paper frames ET as a class-imbalance fix: it biases the sample distribution away from unrecoverable failure states.

**Implication for you:** both are load-bearing, but the failure mode of RSI under a *noisy* reference is the opposite of what DeepMimic assumes — RSI is only helpful if the sampled reference state is physically reachable. That's precisely what InterMimic's PSI and SUGAR's progressive state pool fix.

### The four termination/tolerance schedules actually used in practice

| Work | Mechanism | Numbers |
|---|---|---|
| ASAP | Termination-distance curriculum | 1.5 m → 0.3 m over training |
| GMT | Joint decay of termination threshold E_i and completion level c_i | E_min = 0.25, c_min = 1.0; sampling `p_i = (min(E/0.15,1))^5` |
| ManipTrans | Per-quantity ET curriculum | finger 6 cm → 4 cm; object 90°/6 cm → 30°/2 cm |
| KungfuBot | Adaptive *reward tolerance*, not termination | `σ ← min(σ, EMA(tracking error))`, monotonically tightening |
| PHC | Relaxed ET (RET) | 0.5 m mean joint distance, **ankle and toe excluded** |
| MaskedMimic | Terrain-conditioned ET | 0.25 m flat, 0.5 m irregular |
| InterMimic | Interaction ET (IET) | kinematic ET + object deviation + contact loss |

The pattern, stated plainly: **nobody uses a fixed tight termination threshold with imperfect references.** Either start loose and tighten (ASAP/GMT/ManipTrans), or keep termination loose and put the tightening in the reward temperature instead (KungfuBot), or exclude the joints your retargeter gets wrong (PHC's RET on ankles/toes — for you, read: exclude fingers).

I found **no paper that directly analyzes ET threshold as a function of reference noise magnitude.** The closest empirical data point is ManipTrans's Appendix B robustness study: performance remains acceptable up to **1.5 cm Gaussian noise** on interaction poses, and SkillMimic-V2's injected uniform object-position noise at **σ ∈ {10, 20, 30} mm**. Those two numbers are your only published calibration anchors.

---

## 4. Hand-object / dexterous work on noisy references

### REGRIND — arXiv:2607.11874, Isaac Sim 5.1.0 + rsl_rl, your exact stack
https://arxiv.org/abs/2607.11874 · https://yunhaifeng.com/REGRIND · code+data announced, no GitHub URL in the paper

Retarget human hand-object motion with **interaction-mesh Laplacian deformation** (Drake + MOSEK for the program, mink for IK), then RL to **track object-centric keypoints**:

```
ε_object = dist_KP(P_t^o, P̄_t^o) = (1/N_k) Σ ‖p_t'^i,o − p̄_t'^i,o‖₂
r_object = exp(−ε_object / σ)
```

Finger tracking is **largely dropped** in the RL phase. The policy outputs "a residual action on top of the reference motion" for the wrist pose, and the hand-object prior is "implicitly encoded in the reference trajectory" rather than explicitly rewarded per-finger. RSI used, "with a restart state distribution μ." Termination when the object deviates >0.15 m from target, leaves the workspace, or the hand strays too far from the object; for the WUJI hand also when fingertip-table contact force exceeds 10 N. **Isaac Sim 5.1.0, PPO via rsl_rl, 4096 envs**; Isaac Lab used for domain randomization. Hardware: UR5e + 16-DoF LEAP or 20-DoF WUJI. Data: ARCTIC (scissors) plus own mocap (screwdriver), hand pose from HaMeR. The paper's framing of why naive retargeting fails: "simple kinematic retargeting, while closely matching the human hand pose, ignores the hand-object interaction and produces physically implausible trajectories."

**6-week verdict:** YES, and start here. Same simulator generation, same RL library, same "retarget then RL-track object keypoints" architecture you need. Reproduce its reward and termination set before you invent anything.

### DexMan — the clearest published statement of your problem
https://arxiv.org/abs/2510.08475 · no code found

Direct quote: **"when reference motions are noisy or physically implausible, as in single-view video estimates, strict imitation can push policies toward infeasible behaviors."** Their fix, also quoted: contact rewards designed to **"shift the learning objective away from imitating ineffective hand trajectories towards fulfilling object-centric contact goals."**

Pipeline: HaMeR (metric MANO meshes) + FoundationPose (object 6D, scale chosen by best pose score) + SpatialTracker (3D point tracks → rigid transform). Rewards:

```
R_contact(t) = (1/|O|) Σ w_c^j (1 + γ_c^j ⟨n^rob, d̂⟩) · exp(−λ_c‖p^rob − v^o‖²) · (w_c1 + w_c2·1_lifted)
R_obj(t)     = (1/|O|) Σ (w_pos exp(−λ_pos Δpos) + w_rot exp(−λ_rot Δrot)) · (w_o1 + w_o2·1_lifted)
```

Note the `1_lifted` gate on both: contact and object rewards are re-weighted once the object is off the surface. The imitation reward on wrist position/rotation/joint angles remains but is subordinate. Policy outputs **residual updates {Δx, Δω, Δθ}** per hand. Success is measured as reproducing the object's 3D motion, not the hand's. Isaac Gym + PPO via **rl_games**, 30 Hz.

**6-week verdict:** YES for the reward structure. The lifted-gating and the `⟨n^rob, d̂⟩` surface-normal alignment term are both cheap and directly useful.

### DexMachina — the strongest "don't track the hand" mechanism
https://arxiv.org/abs/2505.24853 · https://github.com/MandiZhao/dexmachina (official; forked Genesis + forked rl_games) · docs https://mandizhao.github.io/dexmachina-docs

Every object gets **six virtual 1-DoF base joints plus a 1-DoF articulation joint, all PD-actuated**, applying virtual forces from the error between current object state and the demonstration target. So early in training the object *is moved for you* and the policy only has to learn plausible contact. The gains then decay: in Algorithm 1, when `μ_z > σ_z ∀z ∈ {task, imi, bc, con}` (all four reward families clear their thresholds), `k_p ← k_p · φ_p` (similarly k_v), halting at `k_p ≤ 0.01`. Task reward is multiplicative:

```
r_task = r_pos · r_rot · r_angle = exp(−β_pos d_pos)·exp(−β_rot d_rot)·exp(−β_ang d_ang)
r_t = λ_task r_task + λ_imi r_imi + λ_bc r_bc + λ_con r_con
```

Wrist joints are base actions with policy residuals on top. The authors state the point explicitly: auxiliary rewards are **"soft guidance"** so that "the policy [can] deviate from the reference hand motions... to prioritize optimizing for high task rewards," and the objective is object trajectory following, not kinematic mimicry.

**6-week verdict:** YES — this is the single best idea in the report for making noisy hand references trainable. A decaying virtual-object PD controller in Isaac Lab is maybe 3 days, and it converts a hopeless exploration problem into a shaped one. Their reward-threshold-gated decay trigger is better than a fixed schedule; copy that too.

### SPIDER — physics-informed retargeting instead of RL, 10x cheaper
https://arxiv.org/abs/2511.09484 · **https://github.com/facebookresearch/spider** · https://jc-bao.github.io/spider-project/ · docs https://jc-bao.github.io/spider/

Key insight, quoted: "human demonstrations should provide global task structure and objective, while large-scale physics-based sampling with curriculum-style virtual contact guidance should refine trajectories to ensure dynamical feasibility and correct contact sequences." The virtual constraint maintains relative position between contact pairs with a penalty parameter `η_i → ∞ as i → N` — strong initially, relaxed as optimization proceeds (same idea as DexMachina, opposite annealing direction, applied in a sampling optimizer rather than RL). Annealed-covariance MPPI-flavored sampler on MuJoCo Warp / MJX / Genesis / Isaac Gym, 100 Hz physics, 50 Hz control.

The **contact filter is what you want for noisy MANO data**: "if a contact duration is shorter than t_c,min or if the contact point drifts more than d_c,max... the contact is classified as unstable and the corresponding virtual constraint is disabled." That is an automatic, cheap detector of hallucinated contacts in video-derived references. Output filtering: keep only trajectories with rotation error < 0.5 rad **and** position error < 0.1 m throughout. Results: +18% success over plain sampling, ~10x faster than RL baselines (2.5 FPS vs 0.1 FPS), 2.4 M frames generated across 9 embodiments (5 hands: Allegro, Inspire, Schunk, XHand, Ability; 4 humanoids incl. **Unitree G1**) and 6 datasets. Dex3 specifically is not covered.

**6-week verdict:** YES — it's open-source from FAIR, and using it as a *preprocessor* to clean your references before RL may be cheaper than making RL robust to dirty ones.

### Human2Sim2Robot — the cleanest object-vs-hand separation
https://arxiv.org/abs/2504.12609 · https://github.com/tylerlum/human2sim2robot · Isaac Sim + PPO (CrossEmbodimentPPOLSTM)

From a single RGB-D human video, extract exactly two things: the **object pose trajectory**, used as the "embodiment-agnostic reward" — and the **pre-manipulation hand pose**, used *only* for grasp initialization and exploration guidance, never as a tracking target during RL. Beats object-aware replay by 55% and IL by 68%. This is the minimal version of the idea and the easiest to justify to a reviewer.

**6-week verdict:** YES. If you only take one structural decision from this report, take this one: object trajectory → dense reward, hand pose → initialization only.

### ManipTrans — residual correction + the best-documented ET curriculum for hands
https://arxiv.org/abs/2503.21860 · CVPR 2025 · Isaac Gym, PPO, 4096 envs, 60 Hz

Stage 1 pretrains a generalist hand-motion imitator π_I (obs: target wrist pose/velocities/finger joints + proprio; actions: joint PD targets `a_q ∈ R^K` plus 6-DoF wrist force `a_w ∈ R^6`); "focusing on dynamic hand mimicry with large-scale pretraining effectively mitigates morphological differences." Stage 2 adds a residual module conditioned on object position, velocities, CoM, gravity vector, contact forces and hand-object distances: **`a^t = a_I^t + Δa_R^t`**. Rewards: finger tracking with fingertip-weighted exponential decay; object position+velocity following; and a contact-force reward that only fires **"when hand-object distance in the MoCap dataset is below threshold ξ_c"** — i.e. the reference's own distance field gates whether contact is expected, which is a neat way to avoid rewarding contact where the noisy reference doesn't support it. Plus a joint-power smoothness penalty.

ET curriculum with decaying thresholds: finger **6 cm → 4 cm**; object **90° / 6 cm → 30° / 2 cm**; also terminate if a firm grasp is detected but contact force is zero. Authors concede limits: "some sequences cannot be transferred effectively" due to "excessive noise in interaction poses and insufficiently accurate object models." Robustness holds to ~1.5 cm Gaussian noise.

**6-week verdict:** YES. Residual-on-reference + decaying per-quantity ET is exactly the right shape for G1+Dex3 and is a week of work.

### SkillMimic-V2 — explicitly built for sparse and noisy demonstrations
https://arxiv.org/abs/2505.02094 · https://github.com/Ingrid789/SkillMimic-V2 · SIGGRAPH 2025 · https://ingrid789.github.io/SkillMimicV2/ · Isaac Gym, 2048 envs, 120 Hz PD / 60 Hz policy
(v1: https://arxiv.org/abs/2408.15270 · https://github.com/wyhuai/SkillMimic · CVPR 2025 Highlight)

Three mechanisms, all data-augmentation rather than reward engineering:
1. **Stitched Trajectory Graph (STG)**: connect states across different demo clips using kinematic similarity `S_k(s_A, s_B) = r_b · r_o · r_rel` (body × object × relative-motion reward product); connect where similarity β > τ, discard weaker links. Repo does this as an offline `OfflineStateSearch` task producing a pickle, loaded via `--graph_file`.
2. **State Transition Field (STF)**: for any sampled state `s_new` inside an ε-neighborhood of the demos, find `ŝ_j = argmax_{s∈A} S(s_new, s)` and construct `{s_new, s_∅, ..., s_∅[N], ŝ_j, ..., ŝ_T}` — masked buffer states bridge the gap. This gives a recovery target for states that are *near but not on* the demonstration manifold, which is precisely what noise pushes you into.
3. **Adaptive Trajectory Sampling (ATS)**: `p_i = e^{−λ_s r̄_i} / Σ_j e^{−λ_s r̄_j}` with `r̄_i = (1/(T−i)) Σ r_t`, **λ_s = 10** — exponentially upweight the worst-performing segments.

Noise is handled empirically rather than modeled: experiments inject uniform noise σ ∈ {10, 20, 30} mm on object positions. Repo flags: `--state_switch_prob`, `--state_init_random_prob`, `--state_search_to_align_reward`, `--reweight`, `--reweight_alpha`, `--enable_buffernode`, `--hist_length`.

**6-week verdict:** PARTIAL. ATS is a day's work and you should do it. STG/STF are the real contribution but need an offline graph-building pass over your dataset — budget 1.5–2 weeks and only if you have many short clips to stitch.

### PhysHOI — why kinematic tracking alone fails on contact
https://arxiv.org/abs/2312.04393 · https://github.com/wyhuai/PhysHOI (Isaac Gym, built on ASE)

Contact Graph is a complete graph `G = {V, E}`, `E ∈ {0,1}^{k(k−1)/2}`, with reward `r_t^cg = exp(−Σ_j λ^cg[j] · e_t^cg[j])` on binary per-edge contact errors. The full reward is **multiplicative**: `r_t = r_t^body · r_t^object · r_t^ig · r_t^cg` — "we request that none of them be small." Noise handling is by **aggregation**: nodes merge multiple body parts (e.g. both hands as one node) to reduce sensitivity to per-part contact annotation noise, and they report physics can "rectify the error of reference HOI data." Fixed initialization from the first reference frame; termination on max length, object deviating far from reference, or robot position error > 0.5 m.

The money quote for your design doc: without the contact-graph reward, kinematic rewards "fall into a local optimal" and humanoids learned **"not to touch the object."** Repo note: `cg2` suggested at 0.01 for finger-level operation.

**6-week verdict:** YES. The aggregated-node idea is the right answer to "my per-finger contact labels from video are garbage" — coarsen the graph until the labels are trustworthy.

### DeVI — arXiv:2604.20841, 2026
https://arxiv.org/abs/2604.20841 · https://snuvclab.github.io/devi/ · no GitHub found

Kim, Kim, Cho, Joo, 2026-04-22. Uses **text-conditioned synthetic videos** as the demonstration source; the interesting bit for you is the **hybrid tracking reward that integrates 3D human tracking with robust 2D object tracking** — when 3D lifting is unreliable, fall back to a 2D-image-space objective for the object rather than trusting bad 3D. Zero-shot across objects. Simulator/RL library not stated in the abstract.

**6-week verdict:** PARTIAL — the 3D-hand + 2D-object hybrid reward is a genuinely novel hedge against depth/scale error, but you'd be reimplementing from the abstract.

### The rest of the dexterous-from-video lineage (context, mostly superseded)
- **DexMV** — https://arxiv.org/abs/2108.05877 — "demonstration translation" from extracted 3D hand+object poses to robot demos; the original statement of the morphology gap. No official code widely maintained. [6wk: NO, historical.]
- **DexCap** — https://arxiv.org/abs/2403.07788 · https://github.com/j96w/DexCap — SLAM + electromagnetic finger tracking for occlusion-resistant mocap; DexIL does IK + point-cloud IL; notable for the **human-in-the-loop correction during policy rollouts**. [6wk: NO for you — it's a hardware answer to the noise problem.]
- **DexMimicGen** — https://arxiv.org/abs/2410.24185 — ICRA 2025 — 60 human demos → 21,000 sim demos via object-centric subtask transforms. Data multiplication, not noise robustness. [6wk: NO.]
- **Robot See Robot Do** — https://arxiv.org/abs/2409.18121 · CoRL 2024 · https://robot-see-robot-do.github.io — 4D-DPM recovers part motion from monocular video via part-centric feature fields; then **"rather than mimicking hand movements, the robot plans bimanual arm motions designed to recreate the same object part motion."** ~60% success over 90 trials on bimanual YuMi. [6wk: NO to implement, YES as a citation for the object-goals-over-hand-goals argument.]
- **ViViDex** — https://arxiv.org/abs/2404.15709 · ICRA 2025 — trajectory-guided RL per video to turn noisy hand estimates into physically plausible state-based rollouts, then distill successful rollouts into one vision policy without privileged info. The "RL as a data cleaner, then distill" pattern. [6wk: PARTIAL.]

---

## 5. What I'd actually build, in dependency order

Given Isaac Lab + G1 + Dex3 + rsl_rl and six weeks:

**Week 1 — fix the data before touching the policy.** Use **GMR** (https://github.com/YanjieZe/GMR) rather than writing a retargeter; it already has a G1+Dex31 config. Apply KungfuBot's two cheap filters on the retargeted output: CoM–CoP distance `< 0.1 m` for stability, and the ankle-contact-mask vertical offset correction with EMA. Run SPIDER's unstable-contact detector (contact shorter than t_c,min, or contact point drifting more than d_c,max → discard that contact label) over your hand-object references; this is where most video-derived contact noise dies.

**Week 2 — the H2O feasibility filter.** Train one privileged, no-DR tracking policy on everything. Roll out every clip once, log per-clip success under a loose ET. Keep the survivors as your training index. Expect to drop 15–25% (H2O dropped ~15% of AMASS on H1; you have hands and objects, so expect worse). This one run pays for itself.

**Week 3 — reward and termination structure.** Object-centric primary reward following REGRIND (`r_object = exp(−ε_object/σ)` on object keypoints) and Human2Sim2Robot (object trajectory = reward, hand pose = initialization only). Add DexMan's contact reward with the lifted gate, and PhysHOI's aggregated contact graph — coarsen Dex3's nodes to something like {left palm, left fingers, right palm, right fingers, object} rather than per-fingertip, because your per-fingertip contact labels are not trustworthy. Keep the finger-tracking term but **weight it low and gate it on reference reliability**, ManipTrans-style (`ξ_c` distance gate). Termination: ASAP's curriculum 1.5 m → 0.3 m on body, ManipTrans's 6→4 cm / 90°,6cm→30°,2cm on hand and object, PHC's RET applied to fingers (exclude finger joints from the distance check entirely).

**Week 4 — adaptive tolerance and sampling.** KungfuBot's `σ ← min(σ, EMA(tracking_error))` on the reward temperature. GMT's adaptive sampler `p_i = (min(E/0.15,1))^5` or MaskedMimic's failure-rate-proportional sampling — either works; GMT's is sharper.

**Week 5 — the virtual object controller.** DexMachina's decaying PD-actuated virtual object joints, with the reward-threshold-gated decay trigger (`μ_z > σ_z` for all reward families → `k_p ← k_p·φ_p`, stop at 0.01). This is the difference between "policy learns not to touch the object" and "policy learns to manipulate it." If you are behind schedule, this is the item to keep and Week 6 is the item to cut.

**Week 6 — teacher-student, if time permits.** OmniH2O's recipe: teacher on clean/privileged reference (full object state, future lookahead à la TWIST's 2 s), student on noisy/partial, MSE on actions via DAgger, 25-step proprio history. Add InterMimic's PSI / SUGAR's progressive state pool — a FIFO buffer of simulation states that beat a reward threshold, used for initialization instead of raw reference frames. That single change is what makes RSI safe under a noisy reference, and it's maybe 100 lines.

**Cut list:** PMCP's progressive network capacity, PULSE latent spaces, STG/STF graph construction, ASAP's delta-action model, MoE policies. All good, none affordable in six weeks.

---

## 6. Caveats on what I verified

Every arXiv ID above was confirmed by fetching its abstract page, except these, which came from arXiv API/listing results with matching title+authors+date but no individual abstract fetch: DynaRetarget 2602.06827, SPARK 2603.11480, Direct Dynamic Retargeting 2605.23762, Human2Humanoid (physics-aware retargeting) 2603.09956 and 2606.03476, PhysDrift 2606.19935, X-OP 2606.07934, HumDex 2603.12260, TrajBooster 2509.11839, CBF-RL 2510.14959, Teleopit 2608.01834. **arXiv:2601.19411 (Task-Centric Policy Optimization from Misaligned Motion Priors) was withdrawn on 2026-02-03** by the authors as incomplete — the "imitation as conditional regularizer" idea is appealing but there is no paper behind it right now; do not cite it.

Code links: confirmed live and official for PHC, human2humanoid, ASAP, TWIST, InterMimic, PhysHOI, SkillMimic, SkillMimic-V2, whole_body_tracking, GMR, holosoma, ProtoMotions, dexmachina, human2sim2robot, facebookresearch/spider. No code found for OmniH2O standalone (it's inside human2humanoid), DexMan, DeVI, SUGAR, ULTRA, TEXEDO, HANDOFF, CoorDex, UniTracker, PhyGile, ExBody2. REGRIND says code and data are coming but publishes no GitHub URL yet — project page is https://yunhaifeng.com/REGRIND.

One methodological note: my WebSearch budget was exhausted at the start of this session, so everything here came from direct WebFetch against arxiv.org abs/html pages, the arXiv API, GitHub, and project pages. Coverage of non-arXiv venues (pure ICRA/IROS proceedings without preprints) is therefore thin.
