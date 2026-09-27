# agent aa71dabc82f3ed8da

## PROMPT

Deep web research task. Do NOT write any files. Return a dense technical report as your final message, with URLs cited for every claim.

Research TWO papers in depth. Use WebSearch and WebFetch aggressively (arxiv /abs and /html pages, project pages, GitHub READMEs, raw.githubusercontent.com for LICENSE/config files).

PAPER A: **SPIDER** — a method for learning dexterous manipulation from human demonstrations. Likely an acronym like "Scalable Physics-Informed DExterous Retargeting" or similar. It is cited by the NVIDIA CHORD paper (arXiv 2607.00033) as a baseline, and the CHORD/NVIDIA V2D benchmark uses a metric called "SP-SR". Find the actual SPIDER paper (arXiv ID, authors, venue, year — probably 2025 or 2026). Search terms to try: "SPIDER dexterous retargeting", "Scalable Physics-Informed Dexterous Retargeting", "SPIDER human demonstration dexterous manipulation arXiv", "SPIDER sampling-based physics dexterous".

PAPER B: **Human2Sim2Robot** — "Human Demo to Sim to Robot", a real-to-sim-to-real RL framework learning dexterous manipulation from a SINGLE human RGB-D video (Stanford, ~arXiv 2504.12609, "Dexterous Manipulation through Imitation Learning: A Survey"? NO — find the right one. Try: "Human2Sim2Robot" site:arxiv.org, or "Sim-and-Real Co-Training", or the project page human2sim2robot.github.io).

For EACH paper report, with precision and URL citations:
1. Core idea / one-paragraph method summary.
2. EXACT input/observation representation fed to the policy (observation vector components and dimensions if stated: object pose, object velocity, fingertip positions, reference trajectory, contact, privileged info). Note teacher/student asymmetry.
3. EXACT action space (joint position targets? PD targets? residual? wrist 6-DoF? control frequency? decimation?).
4. Reward design — enumerate every reward term, formula, weight, curriculum.
5. RL algorithm + sim framework (PPO variant? IsaacGym/IsaacLab/MuJoCo/Genesis?). Physics timestep and control dt.
6. Training cost: parallel env count, GPU type/count, wall-clock or GPU-hours per task, total env steps.
7. Code public? Exact GitHub URL, LICENSE, whether checkpoints/data are released.
8. Supported hands/embodiments (Allegro, Shadow, LEAP, Ability, Inspire, Dex3, etc.), bimanual or single-hand, floating wrist vs arm.
9. Known failure modes / limitations from the paper and GitHub issues.
10. Evaluation metrics and exact definitions/thresholds. Especially: does SPIDER define a "success rate" with a specific threshold? Quote formulas verbatim.

Be exhaustive on metric definitions. Flag explicitly anything you could not verify.

---

## REPORT

I have everything. Here's the report.

---

# PAPER A — SPIDER: Scalable Physics-Informed DExterous Retargeting

**Identification.** arXiv:2511.09484, v1 12 Nov 2025, **v2 5 Feb 2026** (current). Authors: Chaoyi Pan, Changhao Wang, Haozhi Qi, Zixi Liu, Homanga Bharadhwaj, Akash Sharma, Tingfan Wu, Guanya Shi, Jitendra Malik, Francois Hogan. FAIR at Meta + CMU (Pan is CMU, work done at Meta). Subjects cs.RO; cs.CV. License CC BY 4.0. **No peer-reviewed venue is listed** — the arXiv Comments field contains only the project website; I could not verify any conference acceptance.
- https://arxiv.org/abs/2511.09484 · https://arxiv.org/html/2511.09484v2 · https://jc-bao.github.io/spider-project/

**⚠️ Framing correction for your V2D work:** SPIDER is **not** a policy-learning / RL method. It is offline **sampling-based trajectory optimization** (MPPI-family) run in a GPU physics simulator. There is no policy network, no observation vector, no PPO. Items 2/3/5/6 below therefore map onto "cost function / control parameterization / optimizer", not "obs / action / RL". RL appears only as a downstream *application* (§4.2).

### 1. Core idea
Human demos supply the global task structure (reference robot joint trajectory from IK + reference object SE(3) trajectory); physics-based sampling refines the control sequence so it is dynamically feasible. Two additions over vanilla MPPI: (a) an **annealed sampling kernel** that shrinks the search radius over both optimizer iterations and horizon index; (b) **virtual contact guidance** — a virtual constraint that "sticks" the object to the demonstrated contact configuration early and relaxes it in a curriculum. Plus min–max robustification over dynamics parameters for open-loop real deployment, and physics-aware data augmentation.

### 2. Cost function (verbatim, v2 Eq. 1a)
```
min_{u_{0:T-1}} J(u_{0:T-1}) = min ‖x_T − x_T^ref‖²_{Q_T}
                             + Σ_{t=0}^{T-1} ( ‖x_{t+1} − x_{t+1}^ref‖²_{Q_t} + ‖u_t‖²_{R_t} )
s.t.  x_{t+1} = f(x_t, u_t, t),   x_{0:T} ∈ X,  u_{0:T-1} ∈ U
```
with diagonal `Q_t = diag({q_robot, q_object})`, `R_t = diag({r_robot, r_object})`. Reference state `x_t^ref = {q_t^ref, q̇_t^ref}`, `q_t^ref = {q_t^ref,robot, q_t^ref,object}`, robot part = joint positions `q^ref,joint ∈ R^{n_u}` plus base transform `T^ref,base ∈ SE(3)`, object `q^ref,object ∈ SE(3)`.

**Actual weights are not in the paper — they are in the released code** (`spider/config.py`, defaults):
`base_pos_rew_scale=1.0`, `base_rot_rew_scale=0.3`, `joint_rew_scale=0.003`, `pos_rew_scale=1.0` (object pos), `rot_rew_scale=0.3` (object rot), `vel_rew_scale=0.0001`, `terminal_rew_scale=1.0`, **`contact_rew_scale=0.0`** (contact reward off by default — GitHub issue #32 confirms users hit this).
- https://raw.githubusercontent.com/facebookresearch/spider/main/spider/config.py

**Sampling update (v2 Eq. 2):**
```
U^{i+1} = U^i + [ Σ_j exp(−J(U^i+[W]_j)/λ) [W]_j ] / [ Σ_j exp(−J(U^i+[W]_j)/λ) ]
Σ^i_h  = exp( −(N−i)/(β₁N) − (H−h)/(β₂H) ) · I
```

**Virtual contact guidance (v2 Eq. 4):** for contact pair *k*, relative positions `^robot p_{k,t}^object = p^robot_{k,t} − p^object_{k,t}`, indicator `c_{k,t} = 1(‖^robot p_{k,t}^{object,ref}‖₂ ≤ ε_contact)`, constraint
```
c_{k,t} ‖ ^robot p_{k,t}^object − ^robot p_{k,t}^{object,ref} ‖²₂  ≤  η_i ,    η_i → ∞ as i → N
```
Contact filter: a contact is marked unstable and its constraint disabled if duration < `t_{c,min}` or the contact point drifts > `d_{c,max}`. Neither ε_contact, t_c,min nor d_c,max is given numerically anywhere in the paper — **unverified**.

**Robustification (Eq. 5):** `J_rob(U) = max_{d∈D} J(U,d)`, evaluated as `max_{k≤K} J(U_j, d_k)` over a minibatch `d_{1:K} ~ D`; D spans contact margin, friction coefficient, object mass.

**IK preprocessing loss (Appendix A.1, verbatim):**
```
L_IK = Σ_{i=1}^n ‖p_i^robot − p_i^human‖² + 0.1 ‖R_wrist^robot − R_wrist^human‖²_F
```
21D per-hand keypoint representation (3D fingertips + 6D wrist from MANO); trajectories resampled to 50 Hz, low-pass filtered at 10 Hz.

### 3. Action / control space
`u_t` = **MuJoCo `<position>` actuator targets**, i.e. PD position targets. Confirmed from the released hand XMLs: each hand has a **floating 6-DoF wrist** built as 3 `slide` + 3 `hinge` joints (`right_pos_x/y/z`, `right_rot_x/y/z`) each with a `<position>` actuator at **kp=1000**, plus one `<position>` actuator per finger joint under the default class `<position kp="300" dampratio="1.0" inheritrange="1"/>`. No arm in simulation.
- `spider/assets/robots/inspire/right.xml` in https://github.com/facebookresearch/spider

Timing — **paper vs. code disagree**:
| | Paper (App. A.2) | Code default (`config.py`) |
|---|---|---|
| physics dt | 100 Hz (0.01 s) | `sim_dt=0.01` ✓ |
| control | 50 Hz | `ctrl_dt=0.4` (knot spacing 2.5 Hz), `ref_dt=0.02` (50 Hz reference) |
| horizon | H = 1.2 s | `horizon=1.6`, `knot_dt=0.4` |
| samples | N = 1024 particles | `num_samples=2048` |
| iterations | M = 16 | `max_num_iterations=16` ✓ |
| temperature | β₁=0.85, β₂=0.9 | `temperature=0.3` (λ), `improvement_threshold=0.01` |

The control is a spline over knots spaced `knot_dt=0.4 s`, interpolated to the sim rate — so "50 Hz control" in the paper means the applied rate, not the number of free decision variables. Per-component sampling noise: `joint_noise_scale=0.15` (rad), `pos_noise_scale=0.03` (m), `rot_noise_scale=0.03` (rad).

Real deployment: Franka Emika Panda (7-DoF) + Allegro; **arm under operational-space control, hand executes the optimized joint actions directly, open-loop** (§3.3).

### 4. Virtual contact guidance — implementation vs. paper
The code implements guidance via **six virtual `<position>` actuators on the object itself** (`right_object_pos_x/y/z`, `right_object_rot_x/y/z`, and left equivalents; `init_pos_actuator_gain=10.0`, `init_rot_actuator_gain=0.1`, `guidance_decay_ratio=0.5`), with `run_mjwp.py` asserting these gains have decayed to ~0 (`_assert_object_actuator_gains_zero`). That is an *absolute* object-pose constraint — structurally the DexMachina-style `‖p^obj − p^obj,ref‖² ≤ η` that the paper explicitly distinguishes itself from in §2.3. A second path, `spider/simulators/mjwp_eq.py`, implements guidance as MuJoCo **equality constraints** with `eq_solref`/`eq_solimp` annealed linearly across a `num_dyn` batch — but it is wired into **no example entrypoint** (GitHub issues #17, #50). Flagging this as a real ambiguity, not a resolved fact; issue #41 is a user asking exactly this question.

### 5. Algorithm + simulator
Sampling-based optimization with annealed kernel + early stopping (Alg. 1), no gradients, no policy. Simulators supported: **MuJoCo Warp, MJX, Genesis, Isaac Gym**. MuJoCo Warp used for most datasets; Genesis for ARCTIC (to match DexMachina). Physics 100 Hz, control 50 Hz.

### 6. Compute
- Ablations + speed tests: **RTX 4090**. Dataset generation: **H100**. 5 seeds per experiment.
- Throughput reported as FPS = frames-in-trajectory / wall-clock: SPIDER **2.5 FPS** on Oakink, **1.5 FPS** on ARCTIC; annealed-only ablation 3.0 Hz vs 2.5 Hz for the full method. Baselines: ManipTrans 0.1 FPS, DexMachina 0.05 FPS (the "10× faster" / "order of magnitude" claim).
- Per-trajectory wall-clock, total GPU-hours and total node counts are **not reported** — unverified.
- Downstream RL (§4.2, App. A.3): PPO ported from Weng et al. 2025 (HDMI). Env count, GPU count, and step budget for that experiment are **not reported** — unverified.

### 7. Code / data release
- **Official: https://github.com/facebookresearch/spider** — LICENSE = **CC BY-NC 4.0** (Meta Platforms; GitHub reports SPDX `NOASSERTION`). 546 stars, 61 forks, 12 open issues, created 2025-12-09, last push 2026-06-30. Python 3.12, PyTorch 2.0+.
  - https://raw.githubusercontent.com/facebookresearch/spider/main/LICENSE
- **Author mirror: https://github.com/jc-bao/spider** — 177 stars, last push 2025-12-11, **no LICENSE file at all**, but the README carries an **MIT** badge. This directly contradicts the official CC BY-NC repo. Treat the Meta repo as authoritative; the MIT badge is not backed by a license file.
- Docs: https://facebookresearch.github.io/spider/
- **Data: only examples are released.** HuggingFace org `retarget` hosts exactly two datasets: `retarget/retarget_example` (**5.31 GB**, license `apache-2.0`, dataset viewer broken) and `retarget/example_video_data`. **The headline 2.4M-frame / 103-object retargeted dataset is NOT publicly downloadable** — the paper's own wording is "We release the full data generation *pipeline*", not the dataset.
  - https://huggingface.co/datasets/retarget/retarget_example
- No policy checkpoints (none exist — it's an optimizer).

### 8. Embodiments
5 dexterous hands: **Allegro, XHand, Inspire, Ability, Schunk** (+ `metahand` and `mano` asset dirs in-repo). 4 humanoids: **Unitree G1, Unitree H1-2, Fourier N1, Booster T1** = 9 total. Bimanual and single-hand both supported (`embodiment_type ∈ {left, right, bimanual, CMU}`). **Inspire and Ability are simulated as 12-DoF models with joint coupling constraints removed** (following ManipTrans) — real Inspire has 6 actuated DoF; GitHub issue #31 raises exactly this. Simulation is floating-wrist only; the Franka+Allegro arm+hand sim model used for the real-robot section was **not released** (issue #62, closed).

### 9. Known failure modes / limitations
From paper: Oakink is harder than GigaHands because objects are often pre-grasped, so success hinges on precise initial contact; SPIDER **lags DexMachina badly on ARCTIC** (42.0% vs 67.1%); low-DoF hands (Schunk, Ability) retarget worse. §2.3 acknowledges sampling converges to wrong contact modes without guidance. Notably **there is no Limitations section** in either version.

From GitHub issues (https://github.com/facebookresearch/spider/issues):
- **#78 (open)** — cannot reproduce the OMOMO humanoid+object results in Table 4; the exact OMOMO split / preprocessed data used for the paper is not published.
- **#69** — same code, same keypoints, `lift_board`: works for XHand, produces a **numerically-exploded trajectory for Allegro**.
- **#12 open on H2S2R side**; here **#61** — `uv sync` unsatisfiable, pinned `mujoco==3.5.1.dev880735671` doesn't exist.
- **#58, #17** — memory blowups: default `num_samples=1024` needs ~3 GB, `mjwp_eq` path tried to allocate **40 GB** on one GPU.
- **#50, #17** — `trajectory_mjwpeq.npz` (which outperforms the standard path on some OakInk/Inspire tasks) has **no runnable generation entrypoint** in the public repo.
- **#48, #35** — OakInk/ARCTIC preprocessing scripts ("preprocessed by maniptrans") not included; `ik.py` doesn't write `trajectory_kinematic_act.npz` needed by contact guidance.
- **#32** — contact reward silently disabled by default.
- **#34** — Python version conflict: SPIDER needs 3.12, HDMI/IsaacLab need 3.10.

### 10. ⭐ Success metric — exact definition (this is your SP-SR)

**v2 text (authoritative, §3.1), verbatim:**
> "We follow the same evaluation setting as ManipTrans (Li et al., 2025c) and DexMachina (Mandi et al., 2025), where we report task success **only concerning object motion**. Task success is defined using: (1) the rotation error **E_rot < 0.5 rad**, and (2) the average per-step translation error **E_pos < 0.1 m**."

**v1 text said `E_pos < 3 cm`.** The threshold was loosened ~3.3× between v1 and v2, **yet Tables 2 and 3 are byte-identical across versions** (Oakink 0.413/0.459/0.479/0.431/0.422; GigaHands 0.741/0.810/0.879/0.706/0.812; SPIDER-Oakink 47.9%). Only the ablation Table 1 changed. Either v1's "3 cm" was a typo or the large-scale numbers were never recomputed. **Use 0.1 m.**

**Error definitions (verbatim, unchanged v1→v2):**
```
E_rot = (1/T) Σ_{t=1}^T arccos( 2 ⟨q_obj,t , q_obj,t^ref⟩² − 1 )
E_pos = (1/T) Σ_{t=1}^T ‖ p_obj,t − p_obj,t^ref ‖₂
```

**Ground truth from the released code** — `spider/postprocess/get_success_rate.py`, `main()` defaults `pos_err_threshold: float = 0.1`, `quat_err_threshold: float = 0.5`:
```python
success = (obj_pos_err <= pos_err_threshold) & (obj_quat_err <= quat_err_threshold)
```
This confirms v2. Note `<=` in code vs `<` in the paper (immaterial).

**Two implementation details the paper does not disclose, and they matter:**
1. **For `embodiment_type == "bimanual"`, position error is computed on mean-centered trajectories**: `pos_object_*_traj -= pos_object_*_traj.mean(axis=0)` and likewise for the reference, *then* the L2 per-step error is taken. So the bimanual E_pos is a **shape/trajectory-similarity error that discards any constant world-frame offset**. The single-hand branch uses raw absolute positions. Since Oakink/GigaHands results are bimanual, the reported success rates are on the offset-invariant metric — not what Eq. for E_pos implies.
2. Rotation error in code is `mean_t ‖quat_sub(q_traj, q_ref)‖₂` (norm of the axis-angle difference), numerically equal to the geodesic angle, so it agrees with the paper's `arccos(2⟨·⟩²−1)` form.
3. Two objects present → errors are averaged across right and left; a side whose reference displacement < 1e-3 m is treated as absent (single-object setup) and dropped. An `ADD-AUC10` metric (`compute_add_auc10`, raw world-frame positions, no centering) is also computed but is not reported in the paper.

**On "SP-SR" in CHORD** (arXiv:2607.00033v1, 22 Jun 2026, Xinghao Zhu et al., NVIDIA): CHORD defines it only by reference — "success rate from SPIDER (SP-SR) [29]" (§4.1) — and **never restates the threshold**. Appendix G.3 says they reproduced SPIDER's original codebase, ported Sharpa hands, used CHORD's IK solver ("several alternative IK solutions with extensive parameter tuning, but none produced consistently satisfactory results"), 5 seeds/task, 3 SPIDER tasks after excluding assets that don't simulate in Isaac Lab. CHORD Table 1 (Ref. Score = SPIDER, Our Score = CHORD): SP suite 0.333±0.488 vs 0.359±0.482; Ours-1 0.133±0.327 vs 0.999±0.000; Ours-2 0.533±0.503 vs 0.982±0.022. Since CHORD post-dates v2 and used the released code, SP-SR is almost certainly `E_pos ≤ 0.1 m ∧ E_rot ≤ 0.5 rad` — but **CHORD never says so, so this is inference, not a verified quote.**

### ⚠️ Internal inconsistencies in SPIDER (both versions)
- **Dataset size**: contributions bullet says "**262 episodes**, 800 hours of data, and 2.4M frames"; §3.1 says "**1262 episodes** and 2.4M frames"; Table 2 sums to **1778** trajectories (1022 Oakink + 756 GigaHands). Also 2.4M frames at the stated 50 Hz = **13.3 hours**, not 800.
- **Ablation N**: v2 text says 7 Oakink + 3 GigaHands trajectories; the v2 Table 1 caption still says "eight … Oakink … and five … GigaHands" (v1 wording left in).
- **"18%" claim doesn't reproduce from v2 Table 1**. v2 mean over 10 rows: annealed-only = 0.715, +contact = 0.787 → **+7.2 points absolute / +10.1% relative**. From v1's table it was +15.0 points / +21.9%. Neither is 18%.
- **Caption vs data**: Table 1 claims contact guidance "consistently achieves the highest success rates across all robot–dataset combinations," but in v2 Oakink/Inspire ties (0.45 = 0.45) and Oakink/Schunk **regresses** (0.54 → 0.53).
- **Table 4 caption in v1** claims superiority over "GMR and OmniRetarget" but OmniRetarget is absent from the table; fixed in v2.

---

# PAPER B — Human2Sim2Robot

**Identification.** Tyler Ga Wei Lum\*, Olivia Y. Lee\*, C. Karen Liu, Jeannette Bohg (Stanford). "Crossing the Human-Robot Embodiment Gap with Sim-to-Real RL using One Human Demonstration." **arXiv:2504.12609**, v1 17 Apr 2025, v2 22 Apr 2025, **v3 16 Aug 2025** (current; reformatted to CoRL numbering, adds Appendix C). **Venue: CoRL 2025.** License: arXiv perpetual non-exclusive. cs.RO; cs.AI.
- https://arxiv.org/abs/2504.12609 · https://arxiv.org/html/2504.12609v3 · https://human2sim2robot.github.io/ · https://mlanthology.org/corl/2025/lum2025corl-crossing/

*(Note: arXiv 2504.12609 is **not** "Dexterous Manipulation through Imitation Learning: A Survey" — that guess in your brief was wrong.)*

### 1. Core idea
Record **one** monocular RGB-D human demo. Extract exactly two things: (a) the **object 6D pose trajectory** → an object-centric, embodiment-agnostic dense tracking reward; (b) a **single pre-manipulation hand pose** (one frame) → retargeted via IK to seed the RL initial-state distribution. Build a digital twin (LiDAR-scanned object + scene mesh), train PPO in IsaacGym with heavy domain randomization, deploy zero-shot. No per-frame action labels, no hand-tracking reward, no task-specific reward tuning.

Pipeline: Kiri Engine (object mesh) + 3D Scanner App (scene mesh); **FoundationPose** for object 6D pose (needs **SAM 2** masks); **HaMeR** for MANO hand pose, with ICP depth alignment; **cuRobo** for two-step IK retargeting (step 1: arm aligns robot middle-knuckle to human middle knuckle; step 2: hand joints align fingertips).

Pre-manipulation timestep: `τ = t₀ − t_offset`, where `t₀` = first timestep object velocity exceeds **`v_min = 5 cm/s`**; `t_offset = 30` (1 s at 30 Hz) by default, slightly varied per demo. (v2 said `t_offset = 10` in the main text and `30` in the appendix — v3 uses 30 consistently.)

### 2. Observation (verbatim, v3 Eq. in §3.2)
```
o_t = [ q_t , q̇_t , X_t^fingertips , x_t^palm , X_t^obj , X_{τ+t}^target ]
```
- `q_t, q̇_t ∈ R^{N_joints}` — joint angles and velocities
- `X_t^fingertips ∈ R^{N_fingers × 3}` — fingertip positions
- `x_t^palm ∈ R^3` — palm center position
- `X_t^obj, X_{τ+t}^target ∈ R^{N_anchor × 3}` — **anchor-point positions** for current and target object pose (not quaternions — pose is represented purely by 3 transformed anchor points)

For the paper's robot: KUKA iiwa 14 (7) + Allegro (16) → **N_joints = 23**, **N_fingers = 4**, **N_anchor = 3** ⇒ **o_t ∈ R^79** (23+23+12+3+9+9). *The paper never states 79; this is my arithmetic — flagging as derived.*

**Explicitly absent from the policy observation: object linear/angular velocity, contact/force, timestep, any tactile signal.** Object pose observations are corrupted with noise during training.

**Teacher/student asymmetry — Asymmetric Actor-Critic.** Critic state (v3 App. E, verbatim):
```
s_t = [ o_t , v_t , ω_t , t , f_t^dof , F_t^fingers ]
```
`v_t ∈ R³` object linear velocity, `ω_t ∈ R³` object angular velocity, `t ∈ R` current timestep, `f_t^dof ∈ R^{N_joints}` joint forces, `F_t^fingers ∈ R^{N_fingers}` fingertip contact forces ⇒ **s_t ∈ R^113** (derived). This is asymmetric-critic, **not** teacher-student distillation — there is no second training stage.

### 3. Action space (verbatim)
```
a_t = [ x_t^palm-target , r_t^palm-target , x_t^pca-target ]
```
- `x^palm-target ∈ R³` target palm center position
- `r^palm-target ∈ R³` target palm orientation as **Euler angles**
- `x^pca-target ∈ R^{N_pca}`, **N_pca = 5** — target PCA coefficients for the hand configuration

⇒ **a_t ∈ R¹¹**. Absolute targets, **not residual**. Hand DoF are controlled through a 5-D PCA subspace (16 Allegro joints → 5 dims), following Lum et al. 2024 (DexGraspNet 2 / geometric fabrics line).

**Control stack:** policy **15 Hz** (control timestep 66.7 ms) → **geometric fabric controller at 60 Hz** → **joint PD targets executed by a low-level PD controller at 200 Hz** on hardware. In sim: each action step = **8 sim substeps of 8.33 ms** ⇒ **decimation = 8, physics at 120 Hz**. Actions smoothed by EMA — *no, that EMA detail is CHORD's, not this paper's; H2S2R states no action EMA.*

### 4. Reward — there is exactly **one** term
```
r_t = r_t^obj = exp( −α · d(T^target_{τ+t} , T^obj_t) )

  where  d(T₁,T₂) = Σ_{i=1}^{N^anchor} ‖ T₁ k_i − T₂ k_i ‖
```
**α = 10.** `N_anchor = 3` for most objects, with `k₁=[L,0,0]`, `k₂=[0,L,0]`, `k₃=[0,0,L]` in the object local frame, **L = 0.2 m**. Larger L weights orientation more heavily. The *same* L is used for every task.

**That is the entire reward.** No contact reward, no hand-tracking reward, no action-rate penalty, no energy penalty, no success bonus, **no curriculum**. The paper's central claim is that this eliminates reward engineering. For rotationally symmetric objects, anchor points orthogonal to the symmetry axis are removed (App. C) — this changes both reward and observation.

**Termination / reset** (v3 §3.2 footnote), `D_max = 0.25 m`:
- `d(T^target_{τ+t}, T^obj_t) > D_max` (object too far from current target), or
- `‖x_t^palm − x_t^obj‖ > D_max` (palm too far from object), or
- `τ + t > T` (target trajectory exhausted).

**Initial-state distribution** (v3 App. D — **changed from v2**): `T^obj_1 = T^target_τ · T^random`. v3: **yaw only**, `y ~ U(−θ_max, θ_max)`, `θ_max = 20°`, roll/pitch fixed 0; translation `x,y ~ U(−t_max, t_max)`, `t_max = 0.1 m`, `z = 0`. (v2 sampled full roll/pitch/yaw and 3-D translation — a real methodological narrowing between versions.) Wrist then placed at `T^obj_1 · T^relative` where `T^relative = (T^target_τ)^{-1} T^wrist`, plus small noise on wrist pose and hand joints; arm IK via cuRobo (parallelized, collision-free).

### 5. RL algorithm + sim
**PPO** via **`rl-games`** (GPU-vectorized), in **IsaacGym**. LR `5e-4`, `γ = 0.998`, entropy coefficient **0**, `ε_clip = 0.2`, 4 mini-epochs per update, horizon length 16, normalized observations / values / advantages. Architecture: MLP **[512, 512]** → **LSTM 1024** hidden units; critic **[1024, 512]**. Asymmetric actor-critic.
Physics **120 Hz** (8.33 ms), control **15 Hz** (66.7 ms), decimation **8**.

**Domain randomization** (applied every 720 sim steps): Gaussian σ=0.01 noise on observations *and* actions; gravity perturbed additively with σ=0.3; object & table scale/mass/friction scaled by U[0.7, 1.3]; robot scale/damping/stiffness/friction/mass scaled by U[0.7, 1.3]; random object force perturbations — **5% probability per timestep of a force of magnitude 50× the object's mass along a random unit vector**.

### 6. Training cost
**4096 parallel envs on a single NVIDIA A100 40 GB**, ~**7k FPS**, **5–24 h wall-clock per task**, ~**0.6 billion frames** ≈ one year of simulated experience (0.6B / 15 / 3600 / 24 / 365). One policy per task; 7 tasks.

### 7. Code / data release
**https://github.com/tylerlum/human2sim2robot** — **MIT License**, "Copyright (c) 2025 Tyler Lum".
- https://raw.githubusercontent.com/tylerlum/human2sim2robot/main/LICENSE

Full official implementation: real-to-sim, human-demo processing, PPO training, hardware deployment. **Assets, raw + processed human-demo data for all tasks, and pretrained models are released** — but **behind a Google Form** (https://forms.gle/rUfrbuzKHW5BexcH6) that returns a download URL consumed by `human2sim2robot/utils/download.py` (`--include_assets --all_tasks --include_human_demo_raw_data --include_human_demo_processed_data --include_pretrained_models`). Not on HuggingFace (issue #1 requests it; still open). Star/fork counts unavailable — GitHub API was rate-limited from this host.

### 8. Embodiments
**Single hand only.** **16-DoF Allegro hand on a 7-DoF KUKA LBR iiwa 14** — a *real arm*, not a floating wrist (this is a genuine differentiator vs. most dexterous-RL work and vs. SPIDER's sim setup). ZED 1 stereo camera, table-mounted. Tabletop scene with static box, saucepan, dishrack. **No other hand is supported or demonstrated**; the paper argues nothing in the method is embodiment-specific but provides zero cross-embodiment evidence. GitHub issue #12 ("Can it only handle the right hand?") is open and unanswered. Not bimanual.

### 9. Failure modes / limitations
**From the paper (§Limitations + §4.2):**
- Single embodiment evaluated; no other hands or grippers tested.
- **Single-object tasks only** — multi-object requires modification.
- Requires a **high-quality object pose tracker and rigid-body simulator**; rigid objects only. **Articulated or deformable objects would need different state estimation and simulation.**
- FoundationPose struggles with **symmetric-object pose ambiguity** and **reflective-object depth noise**.
- **Single-task, single-object policies** — one 5–24 h training run per task; no multi-task generalist.
- No bimanual / whole-body.
- Observed real failures: policies **exploiting simulation inaccuracies** (notably imperfect tabletop/static-object friction modeling), and pose estimation error under occlusion.
- Hardest task: **plate-pivot-lift-rack** — the thin plate slips out of the large Allegro hand.

**From GitHub issues (https://github.com/tylerlum/human2sim2robot/issues):**
- **#7 / #10 (open)** — `fabrics-sim` (the geometric fabric controller, a hard dependency for the action space) is at `https://gitlab.com/tylerlum/fabrics-sim.git` and **returns "repository not found" / is not publicly accessible**. This blocks reproduction of the control stack.
- **#11 (open)** — Allegro self-collision problems.
- **#12 (open)** — right-hand-only limitation.
- **#9, #8 (open)** — pipeline-flow clarifications, `iiwa_allegro.yml` config issues.
- **#1 (open)** — HuggingFace artifact release request.

### 10. Evaluation metrics
**There is no threshold-based success criterion.** Success is **human-judged task completion**, defined per task in Appendix G, over **10 policy rollouts per task per method**:

| Task | Criterion | Grading |
|---|---|---|
| snackbox-push | snackbox reaches and contacts the static box | binary |
| plate-push | plate contacts the static box | binary |
| snackbox-pivot | pivoted against the box into a **stable sideways orientation** | binary |
| pitcher-pour | lifted **by its handle** with spout positioned above the saucepan | binary |
| snackbox-push-pivot | push then pivot | **0 / 0.5 / 1** |
| plate-lift-rack | lift off table, then place in dishrack **maintaining upright orientation** | **0 / 0.5 / 1** |
| plate-pivot-lift-rack | pivot upright, lift, place in rack upright | **0 / 0.33 / 0.66 / 1** |

Object-position randomization ranges are part of the task spec: 4×4 cm for snackbox-push / plate-push / pitcher-pour / snackbox-push-pivot; **1×4 cm** for snackbox-pivot; **0.5×4 cm** for both plate-lift-rack and plate-pivot-lift-rack.

Simulation ablations (§4.3–4.5) report **reward curves only** — no success rate, 3 seeds each, all on plate-pivot-lift-rack.

**Per-task real-world numbers** (from the project page; the paper puts them only in a bar chart):

| Task | Ours | Replay | OA Replay | BC (Diffusion) |
|---|---|---|---|---|
| snackbox-push | 100% | 10% | 10% | 30% |
| snackbox-pivot | 100% | 100% | 100% | 80% |
| snackbox-push-pivot | 100% | 40% | 70% | 20% |
| plate-push | 100% | 0% | 0% | 0% |
| plate-lift-rack | 60% | 0% | 0% | 0% |
| plate-pivot-lift-rack | 86.6% | 0% | 33.3% | 0% |
| pitcher-pour | 100% | 30% | 50% | 40% |
| **mean** | **92.4%** | **25.7%** | **37.6%** | **24.3%** |

The paper's headline "+67% / +55% / +68%" are **absolute percentage-point differences of these 7-task means** — I verified all three reproduce exactly. Note **plate-lift-rack (60%) is actually the worst task**, not plate-pivot-lift-rack (86.6%), despite the text calling the latter "most challenging" — the graded 0/0.33/0.66/1 scale inflates partial credit on the 3-step task.

Baselines: **Replay** (open-loop PD-target replay of retargeted joints), **Object-Aware Replay** (warps the trajectory by the relative transform between demo and test initial object pose, à la PEP/OKAMI), **BC** (diffusion policy on **30 demos** synthesized from the one demo via OA Replay over the same object-pose sampling range as RL). Ablations: Fixed Target / Interpolated Target (slerp+lerp) / Downsampled Trajectory (`t_down = ⌊t/D⌋·D`, `D = 90` = 3 s at 30 Hz); Default Init / Overhead Init (palm 5 cm above object, open hand) / Pre-Manipulation Far (palm moved 20 cm away); Hand Tracking Reward `r_t^hand = exp(−α‖X^fingertips − X^desired-fingertips‖)` added to `r_t^obj`; Residual Policy (open-loop replay + learned delta PD joint targets).

Real-time perception detail worth noting for V2D: FoundationPose registration ~1 s (Grounding DINO box → SAM2 mask, text prompt optionally auto-generated by GPT-4o rendering the mesh); tracking at 30 Hz; a watchdog runs SAM 2 at **1 Hz** and **re-registers whenever mask IoU < 0.1**.

---

## Head-to-head summary

| | SPIDER | Human2Sim2Robot |
|---|---|---|
| Class | Sampling-based trajectory optimization (MPPI + annealing + contact guidance) | Sim-to-real RL (PPO) |
| Output | Open-loop control sequence per trajectory | Closed-loop LSTM policy per task |
| Input scale | 6 datasets, 1022+756 trajectories | **1 RGB-D video** |
| Sim | MuJoCo Warp / MJX / Genesis / IsaacGym, 100 Hz phys / 50 Hz ctrl | IsaacGym, 120 Hz phys / 15 Hz ctrl, decimation 8 |
| Compute | 2.5 FPS generation, RTX 4090 / H100 | 4096 envs, 1×A100-40GB, 0.6B frames, 5–24 h/task |
| Embodiments | 9 (5 hands + 4 humanoids), floating wrist in sim; Franka+Allegro OSC in real | 1 (Allegro + KUKA iiwa 14), real arm |
| Action | MuJoCo position targets: 6-DoF floating wrist (kp=1000) + finger joints (kp=300) | R¹¹: palm pos(3) + Euler(3) + hand PCA(5), absolute, through geometric fabrics |
| Reward/cost | Quadratic tracking + control effort, 8 weight scales, contact reward off by default | **Single** term `exp(−10·d)`, 3 anchor points at L=0.2 m |
| Success metric | **E_rot ≤ 0.5 rad ∧ E_pos ≤ 0.1 m** on object motion (bimanual: mean-centered!) | Human-judged task completion, graded, 10 rollouts |
| License | **CC BY-NC 4.0** (Meta) — non-commercial | **MIT** |
| Data | Examples only (5.31 GB); 2.4M-frame dataset **not** released | All assets + demos + checkpoints, via Google Form |

## Explicitly unverified
- Any peer-reviewed venue for SPIDER; ε_contact, t_c,min, d_c,max values; per-trajectory wall-clock and total GPU-hours; env count / step budget for SPIDER's §4.2 PPO experiment; the numeric Q_t/R_t used for the *paper's* results (I have code defaults, not the per-experiment Hydra overrides).
- Whether CHORD's SP-SR used the 0.1 m or 3 cm threshold — CHORD never states it.
- Whether jc-bao/spider's MIT badge reflects any actual grant (no LICENSE file exists there).
- tylerlum/human2sim2robot star/fork/issue counts and full closed-issue bodies (GitHub API rate-limited; open-issue list obtained via HTML).
- Whether SPIDER's code-level "virtual contact guidance" (object actuators tracking absolute object reference) truly implements the paper's Eq. 4 (relative hand-object constraint), or is the DexMachina-style absolute variant the paper distinguishes itself from.
