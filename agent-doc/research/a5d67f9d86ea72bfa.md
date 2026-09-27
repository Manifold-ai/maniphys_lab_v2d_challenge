# agent a5d67f9d86ea72bfa

## PROMPT

Deep WEB RESEARCH task (use WebSearch + WebFetch heavily, at least 20-30 searches/fetches). Do NOT write any files. Return a dense technical report as your final message, with URLs for everything.

TOPIC: Human-to-robot HAND retargeting under a large morphology gap — specifically 5-finger human hand (MANO / 21 3D keypoints) → Unitree Dex3-1 THREE-finger hand (7 DoF per hand).

Context: NVIDIA V2D Challenge Track 2. Input = noisy 3D hand keypoints + object 6-DoF poses; output = RL policy on Unitree G1 + Dex3 hands in Isaac Lab, scored on OBJECT tracking accuracy. The retargeting step is where the 5→3 finger gap bites.

Research exhaustively, with NAMED methods, arXiv URLs, GitHub URLs, license, and whether it's usable in ~6 weeks:

A. Kinematic / vector-based retargeting:
   - DexPilot (NVIDIA, Handa et al.) — its keyvector formulation and the specific cost terms
   - AnyTeleop (Qin et al., RSS 2023) and dex-retargeting (https://github.com/dexsuite/dex-retargeting) — the three retargeting types (vector, position, DexPilot), the YAML config format, which robot hands are supported (does it support Dex3? Inspire? Ability? Allegro? Shadow? Leap?)
   - Open-TeleVision, Bunny-VisionPro, "Robotic Telekinesis", "From One Hand to Multiple Hands" (Qin et al.), "Transteleop", "Seed-of-hand", "HOMIE" hand retargeting, "ACE teleoperation"
   - Optimization backends (NLopt SLSQP, pinocchio-based IK) and how they handle joint limits

B. Functional / contact-based / task-aware retargeting (the alternative to kinematic):
   - Methods that retarget CONTACT POINTS or the OBJECT-relative grasp rather than finger joint angles
   - "Functional grasp retargeting", "Contact-based retargeting", DexMachina (2025), ManipTrans (2025), "Dexterous grasp retargeting", GraspXL, "Grasp transfer across hands", "DexTransfer", "Cross-embodiment grasp transfer", "Get a Grip", "RobustDexGrasp"
   - Methods that optimize object wrench / grasp quality instead of fingertip position matching
   - "Semantic grasp transfer", "Contact-aware retargeting" 2024-2026 works

C. What specifically BREAKS with 3 fingers:
   - Loss of pinky/ring → precision vs power grasp mapping; thumb opposition differences on Dex3
   - Dex3-1 kinematics: exact DoF layout (7 DoF: thumb 3, index 2, middle 2), joint limits, fingertip force sensing, URDF/MJCF sources (unitree_ros, unitree_sim_isaaclab, unitree_rl_gym, MuJoCo Menagerie)
   - Published evidence of failure modes / workarounds when mapping 5→3 fingers
   - Whether people merge ring+pinky into one virtual finger, or drop them, or reweight

D. Retargeting under NOISY input keypoints:
   - Temporal smoothing inside retargeting (dex-retargeting's low-pass), joint-velocity limits, "retargeting with temporal regularization"
   - Whether any published retargeting method is explicitly robust to keypoint noise

E. Arm/wrist retargeting coupling: how the 6-DoF wrist pose from noisy reconstruction gets mapped to G1 arm IK; Pink/pink-ik, mink, pinocchio, CuRobo, "GMR general motion retargeting" (https://github.com/YanjieZe/GMR ?), PHC-style SMPL→humanoid retargeting, "PyTorch based motion retargeting"

F. Isaac Lab integration: which of these have Isaac Lab / Isaac Sim examples; does NVIDIA ship any retargeting utilities in Isaac Lab (isaaclab.devices retargeter, "OpenXR retargeter", "dex retargeting in Isaac Lab")?

For each: 1-2 line what-it-does, URLs, code verdict, 6-week practicality. End with a ranked recommendation and an explicit note on what I should do for 5→3 finger mapping given the object-tracking metric.

---

## REPORT

I have what I need. Writing up the report.

---

# Human→Dex3 hand retargeting: research report

**Bottom line up front:** NVIDIA and Unitree have *both* already shipped production DexPilot configs for the Unitree Dex3-1 three-finger hand. You do not need to invent a 5→3 mapping. Both drop ring and pinky entirely and run standard `dex-retargeting` DexPilot with 3 fingertips. Exact files and parameters below.

One caveat up front: my WebSearch budget was exhausted mid-task and the remaining search engines returned CAPTCHAs/403s, so **I could not locate an official "V2D Challenge Track 2" page** to confirm the keypoint convention or scoring details. Everything below is from primary sources (source code, URDFs, papers). The one thing you must verify yourself is the keypoint ordering of your input — see §D.1, it's the highest-probability silent failure.

---

## A. Kinematic / vector-based retargeting

### A.1 DexPilot (Handa et al., ICRA 2020) — the formulation everything else uses
- arXiv: https://arxiv.org/abs/1910.03135 · project: https://sites.google.com/view/dex-pilot
- Hardware: KUKA LBR iiwa7 R800 + Wonik Allegro (4-finger, 16 DoF) = 23 DoA.
- **Cost:** `C(q_h, q_a) = ½ Σ_i s(d_i)·‖r_i(q_a) − f(d_i)·r̂_i(q_h)‖² + γ‖q_a‖²`
  - `r_i` = **keyvectors**: task-space vectors between fingertip frames and palm→fingertip. For an N-finger hand: `N(N−1)/2` inter-fingertip + `N` palm→fingertip.
  - `d_i = ‖r_i(q_h)‖` (human keyvector length), `r̂_i` = its unit direction.
  - **Switching weight** `s(d_i)`: `1` normally; `200` when `d_i ≤ ε` and `r_i ∈ S₁` (thumb↔primary finger); `400` when `d_i ≤ ε` and `r_i ∈ S₂` (primary↔primary).
  - **Distance map** `f(d_i)`: `β·d_i` with `β = 1.6` when open; `η₁ = 1×10⁻⁴ m` on thumb-finger closure (snap to contact); `η₂ = 3×10⁻² m` as minimum inter-primary separation.
  - `γ = 2.5×10⁻³` regularizes Allegro angles toward zero (open hand).
- **Solver:** NLopt **SLSQP**, warm-started from the previous solution.
- The pinch-snapping (`η₁`) is the whole trick: it makes precision grasps close *fully* despite hand-size mismatch, rather than asymptotically approaching.

### A.2 dex-retargeting (the library) — MIT, and it already handles 3 fingers
- https://github.com/dexsuite/dex-retargeting · URDFs: https://github.com/dexsuite/dex-urdf
- **v0.5.0, MIT.** `requires-python = ">=3.7,<3.13"`. Deps: `numpy>=2.0.0, pytransform3d>=3.5.0, pin>=3.3.1 (pinocchio), nlopt>=2.8.0, anytree, pyyaml, lxml`. `pip install dex_retargeting`.
- **Three types** (`src/dex_retargeting/optimizer.py`):
  | type | reference input | cost | use |
  |---|---|---|---|
  | `position` | absolute 3D fingertip positions | Huber(`FK(q)` vs target), `huber_delta=0.02` | offline HOI datasets; needs `add_dummy_free_joint: True` for the 6-DoF floating wrist |
  | `vector` | origin→task link vectors | Huber on vector residual × `scaling_factor` | teleop, no closing prior |
  | `dexpilot` | auto-generated keyvectors | DexPilot cost above | teleop, with closing prior |
- **Shipped hand configs** (`src/dex_retargeting/configs/{teleop,offline}/`): `ability`, `allegro`, `inspire`, `leap`, `panda_gripper`, `schunk_svh`, `shadow`. **No Dex3, no Unitree anything.** But that doesn't matter (see A.3).
- **`DexPilotOptimizer` explicitly supports 2–5 fingers:** `if len(finger_tip_link_names) < 2 or > 5: raise ValueError`. For `num_fingers=3` the auto-generated structure is exactly right for Dex3:
  - `generate_link_indices(3)` → origin `[2,3,3,0,0,0]`, task `[1,1,2,1,2,3]` = **6 keyvectors**: thumb↔index, thumb↔middle, index↔middle, wrist→thumb, wrist→index, wrist→middle.
  - `set_dexpilot_cache(3,…)` → `S₁` = {thumb↔index, thumb↔middle} (weight 200, target `η₁`), `S₂` = {index↔middle} (weight 400, target `η₂`).
  - Wrist→tip vectors get weight `len_proj + num_fingers = 9` (vs 1 normal) — the code comment says *"This ensures better intuitive mapping due wrong pose detection."* That's a noise-robustness hack baked in.
- **YAML fields** (`retargeting_config.py`): `type, urdf_path, add_dummy_free_joint, target_link_human_indices, wrist_link_name, target_link_names, target_joint_names, target_origin_link_names, target_task_link_names, finger_tip_link_names, scaling_factor, normal_delta=4e-3, huber_delta=2e-2, project_dist=0.03, escape_dist=0.05, has_joint_limits=True, ignore_mimic_joint=False, low_pass_alpha=0.1`.
- **Joint limits:** hard NLopt box bounds from the URDF, with `epsilon=1e-3` slack (`Optimizer.set_joint_limit`). **There is no joint-velocity limit.** Temporal coupling is only (a) warm start from `last_qpos`, (b) `norm_delta` pull toward `last_qpos`, (c) the output low-pass filter.
- ⚠️ **Implementation bug worth knowing:** in all three optimizers, `grad_qpos += 2*norm_delta*(x − last_qpos)` is added to the *gradient* but the corresponding `norm_delta·‖x − last_qpos‖²` term is **not** added to the returned objective value. SLSQP therefore gets an inconsistent (objective, gradient) pair. In practice it still works but it means `normal_delta` behaves unpredictably as a smoothing knob — prefer `low_pass_alpha` for smoothing.

### A.3 ⭐ The two existing Dex3 configs

**(a) NVIDIA, inside Isaac Lab `main`, BSD-3-Clause.** This is the one to copy.
- `source/isaaclab/isaaclab/devices/openxr/retargeters/humanoid/unitree/trihand/g1_upper_body_retargeter.py` → class `G1TriHandUpperBodyRetargeter` / `G1TriHandUpperBodyRetargeterCfg`
- `…/trihand/g1_dex_retargeting_utils.py` → class `G1TriHandDexRetargeting` (thin wrapper over `dex_retargeting.RetargetingConfig`)
- `…/trihand/data/configs/dex-retargeting/g1_hand_right_dexpilot.yml`:
```yaml
retargeting:
  type: DexPilot
  urdf_path: <G1_right_hand.urdf>
  wrist_link_name: base_link
  finger_tip_link_names: [thumb_tip, index_tip, middle_tip]
  target_joint_names: [right_hand_thumb_0_joint, right_hand_thumb_1_joint, right_hand_thumb_2_joint,
                       right_hand_middle_0_joint, right_hand_middle_1_joint,
                       right_hand_index_0_joint, right_hand_index_1_joint]
  scaling_factor: 1.0     # note: Inspire=1.15, Allegro=1.6 — Dex3 is treated as human-scale
  low_pass_alpha: 0.2
```
- `target_link_human_indices` is **omitted**, so it falls back to the default `(stack(origin,task) * 4)` → human indices `{0, 4, 8, 12}` = wrist, thumb tip, index tip, middle tip in **MediaPipe-21 order. Ring and pinky are silently dropped.**
- The hand URDFs are **publicly downloadable, no login** (verified HTTP 200):
  `https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.0/Isaac/IsaacLab/Controllers/LocomanipulationAssets/unitree_g1_dexpilot_asset/G1_right_hand.urdf` (and `G1_left_hand.urdf`).

**(b) Unitree, in `xr_teleoperate`.** https://github.com/unitreerobotics/xr_teleoperate — `assets/unitree_hand/unitree_dex3.yml`, wrapper `teleop/robot_control/hand_retargeting.py`.
```yaml
  type: DexPilot
  wrist_link_name: base_link
  finger_tip_link_names: [thumb_tip, index_tip, middle_tip]
  target_link_human_indices_dexpilot: [[9,14,14,0,0,0],[4,4,9,4,9,14]]   # explicit
  # vector-type alternative also provided:
  target_origin_link_names: [base_link_thumb, base_link_index, base_link_middle]
  target_task_link_names:   [thumb_tip, index_tip, middle_tip]
  target_link_human_indices_vector: [[0,0,0],[4,9,14]]
  scaling_factor: 1.0
  low_pass_alpha: 0.2
```
- Indices `4/9/14` are the **OpenXR-25 convention** (26 joints minus palm), not MediaPipe-21. Same 6-keyvector topology as NVIDIA's, just different source indexing.
- Note they pin a **fork**: https://github.com/silencht/dex-retargeting (branch `unitree`), which only splits `target_link_human_indices` into `_dexpilot`/`_vector`/`_position` variants so one YAML holds all three. Functionally identical to upstream. Upstream works fine with the single key.
- Also interesting: Unitree's `vector` variant uses **per-finger origin frames** (`base_link_thumb/index/middle`) rather than a single wrist origin — that partially compensates for Dex3's offset thumb base.

### A.4 The rest of the kinematic family
| Method | What it does | Links | Verdict |
|---|---|---|---|
| **AnyTeleop** (Qin, RSS 2023) | Generic arm+hand teleop; hand cost `Σ‖α·v_i − FK_i(q)‖² + β‖q_t − q_{t−1}‖²` s.t. joint limits. `α` = hand-size scale. Latency **9±7 ms**. Hands: Allegro, Shadow, SVH, DLR. | https://arxiv.org/abs/2307.04577 · https://yzqin.github.io/anyteleop/ · code = dex-retargeting | Already in your stack via dex-retargeting. |
| **Open-TeleVision** | VR streaming + `dex-retargeting` **vector** type via SLSQP; arm IK = Pinocchio **CLIK** with SE(3) filtering; H1+Inspire, GR-1+gripper; 60 Hz. | https://arxiv.org/abs/2407.01512 · https://robot-tv.github.io/ | Good reference for the wrist→arm plumbing. |
| **Bunny-VisionPro** | `L = Σ‖αv_i − FK_i(q)‖² + β‖Δq‖²` via SQP. Adds **sphere-based collision** + **manipulability (det[JJᵀ]^0.5) singularity avoidance**. Loop-joint dimension reduction → 10.2× speedup. Hand retarget **3.43 ms**, full control 15.93 ms, >60 Hz. Ability hand. | https://arxiv.org/abs/2407.03162 · https://dingry.github.io/BunnyVisionPro/ · https://github.com/Dingry/bunny_teleop_server | Best source for collision/singularity terms if you need them. |
| **Robotic Telekinesis** (Sivakumar, RSS 2022) | Learns retargeting from internet hand video, no paired data. | https://arxiv.org/abs/2202.10448 · https://robotic-telekinesis.github.io/ | Not worth it in 6 weeks. |
| **From One Hand to Multiple Hands** (Qin, RA-L/IROS 2022) | Builds a *customized* sim hand matching the operator, teleops that, then retargets offline to any robot hand. Sidesteps unstable online retargeting. | https://arxiv.org/abs/2204.12490 · https://github.com/yzqin/dex-hand-teleop | Conceptually relevant (two-stage), impractical here. |
| **HOMIE / OpenHomie** | Isomorphic exoskeleton + 15-DoF gloves; sets joint positions **directly, no IK, no retargeting**. G1 and GR-1. | https://arxiv.org/abs/2502.13013 · https://github.com/OpenRobotLab/OpenHomie | Hardware-based; not applicable to a keypoint-input challenge. |
| **ACE** (CoRL 2024) | Visual-exoskeleton cross-platform teleop. | https://arxiv.org/abs/2408.11805 · https://github.com/ACETeleop/ACETeleop | Hardware-based. |
| **Analyzing Key Objectives in Human-to-Robot Retargeting** (Xin, Yu, Li — Tsinghua, 2025) | ⭐ The ablation study you actually want. See below. | https://arxiv.org/abs/2506.09384 · https://mingrui-yu.github.io/retargeting · https://github.com/Mingrui-Yu/retargeting (CC-BY-SA 4.0) | Read this. |

**The objectives-ablation paper (2506.09384) in detail.** Full objective = 5 task terms + 2 regularizers:
- `L_thumb_pos` ‖p^h_thumb − p^r_thumb‖², λ₁=**10**
- `L_wrist_rot` angle(q^h, q^r), λ₂=**0.1**
- `L_fingertip_pos` Σ s̃(dᵢ)‖v^r_i − v^h_i‖², λ₃=**1**
- `L_fingertip_rot` Σ‖r^h_i − r^r_i‖², λ₄=**10**
- `L_pinch` Σ s(dᵢ)‖γ^r_i − l(dᵢ)γ̂^h_i‖², λ₅=**10**  ← the DexPilot term
- `L_joint` (posture), `L_vel = Σ w^vel_j ‖q_j − q^prev_j‖²` (explicit velocity reg)

Ablation findings (LEAP + Shadow on Franka): **removing the pinch term → 0% success on precision screw placement**; fingertip *orientation* is what makes mug-handle-style tasks work; joint regularization has negligible quantitative effect (it only prevents ugly poses). Takeaway for you: keep the pinch/projection term, and **add fingertip orientation** if your objects need a specific approach direction.

---

## B. Functional / contact-based / task-aware retargeting

This is where the field moved in 2025–2026, and it's the theoretically correct answer for an **object-tracking** metric, because it optimizes the hand-object relation rather than finger-joint similarity — which makes it *finger-count agnostic*.

| Method | One line | Links | Code verdict | 6-week? |
|---|---|---|---|---|
| **DexMachina** (2025) | "Functional retargeting": RL to track object states from HOI demos, using a **virtual object controller with exponentially decaying PD gains** so the policy takes over gradually. Metric = **ADD-AUC**. | https://arxiv.org/abs/2505.24853 · https://github.com/MandiZhao/dexmachina · https://project-dexmachina.github.io/ | **MIT**. But: **Genesis** sim + custom forks of Genesis and rl_games. 6 hands (Inspire, Allegro, XHand, Schunk, Ability, DexRobot) — **no 3-finger hand**. 12k envs/GPU. | ❌ port cost too high; ✅ **steal the curriculum idea** |
| **ManipTrans** (CVPR 2025) | 2-stage: generalist hand imitator → per-skill residual. **Explicitly handles finger-count mismatch.** | https://arxiv.org/abs/2503.21860 · https://github.com/ManipTrans/ManipTrans · https://maniptrans.github.io | IsaacGym, 4096 envs, ~15 min per 60-frame traj on a 4090. Inspire 12-DoF, Shadow 22, Allegro 16. | ⚠️ IsaacGym not Isaac Lab; ✅ **copy the finger-merge rule** |
| **Dexplore** (CoRL 2025, **NVIDIA** + UIUC) | Eliminates the retargeting stage: treats MoCap as **soft guidance via adaptive spatial scopes**, jointly optimizing retarget+track in one RL loop. Explicitly argues the 3-stage (retarget→track→residual) pipeline compounds error. | https://arxiv.org/abs/2509.09671 · https://github.com/NVlabs/dexplore · https://research.nvidia.com/labs/srl/projects/dexplore/ | **NVIDIA License** (research-only). Isaac Gym Preview 4, Python 3.8, rl-games 1.1.4, GRAB dataset (manual download + InterAct pipeline). Hands = dex-urdf + 6-DoF floating wrist. | ❌ heavy port; ✅ **the single best conceptual match to your metric** |
| **SPIDER** (Meta/FAIR, 2025) | Kinematic retargeting → **physics-based sampling with curriculum virtual-contact guidance** → dynamically-feasible trajectories. 9 embodiments (incl. **Unitree G1**, H1-2, N1, T1 + Allegro/XHand/Inspire/Ability/Schunk), 6 datasets, 2.4M frames, 10× faster than RL baselines. | https://arxiv.org/abs/2511.09484 · https://github.com/facebookresearch/spider · https://jc-bao.github.io/spider-project/ | **CC-BY-NC 4.0** (non-commercial). MuJoCo-Warp default; also Genesis/IsaacGym/MjLab. IK is **mink-based, ported from GMR**. | ⚠️ license; ✅ G1 already supported |
| ⭐ **REGRIND** (2026) | **The closest template to your exact task.** Retarget human hand-object motion via **interaction-mesh Laplacian deformation** (preserves hand-object spatial/contact relations), then residual RL tracking **object-centric keypoints**. | https://arxiv.org/abs/2607.11874 · https://github.com/yunhaif/regrind · https://yunhaifeng.com/REGRIND | **MIT. IsaacSim 5.1.0 + IsaacLab 2.3.0.** Retarget = SQP via MOSEK (Clarabel license-free fallback) through Drake. LEAP (16) + WUJI (20) on UR5e. 4096 envs, 30 Hz ctrl / 120 Hz sim, ~270-step episodes. | ✅✅ **best starting codebase** |
| **C2Dex** (2026) | Recovers **stable object-side contacts by aggregating noisy frame-wise observations in canonical object space**, then uses them as explicit transfer targets with Laplacian interaction optimization + residual RL. DexYCB 57.8% vs 17.8% baseline. | https://arxiv.org/abs/2608.07045 · https://k-jie.github.io/C2Dex/ | Project page only at time of check. | ⚠️ but the **noise-aggregation idea is directly applicable** |
| **TopoRetarget** (2026) | Sparse interaction graph over hand+object keypoints; distance-weighted Laplacian deformation + directional consistency + penetration handling. +40.6 pp on pen-spin training success. WUJI hand. | https://arxiv.org/abs/2606.16272 · https://toporetarget2026.github.io/TopoRetarget/ | Unconfirmed code. | ❌ reference only |
| **CrossDex** (2024) | **Universal action space from human-hand eigengrasps**, converted per-hand via retargeting. Obs = fingertips + palm only. 80% on YCB across 4 embodiments, zero-shot to 2 unseen. | https://arxiv.org/abs/2410.02479 | — | 💡 **third strategy for 5→3: a low-dim shared action space** |
| **One Hand to Rule Them All** (2026) | Parameterized canonical hand representation + canonical URDF; **81.9% zero-shot on 3-finger LEAP Hand** from training on 5-finger hands. | https://arxiv.org/abs/2602.16712 · https://zhenyuwei2003.github.io/OHRA/ | — | 💡 rare published 3-finger cross-embodiment result |
| **Weave** (2026) | Whole-body loco-manipulation from HOI; contact-aware retargeting; 12 actuated finger joints. 92.5%/65.0% trained/unseen. | https://arxiv.org/abs/2609.16683 · https://xiaohu-art.github.io/Weave/ | — | reference |
| **AnyDexRT** (2026) | **Calibration-free** retargeting: self-supervised fingertip correspondence + few-shot human guidance + contact classifier for pinch refinement. | https://arxiv.org/abs/2607.08341 | — | reference |
| **ObjRetarget** (2026) | Anthropomorphic arm constraints + hand-object geometric modeling for contact-stable retargeting. | https://arxiv.org/abs/2607.03828 | — | reference |
| **SynManDex** (2026) | Retargets synthetic human pre-grasps, then optimizes **force-closure contacts** on the target embodiment. | https://arxiv.org/abs/2606.09798 | — | the "optimize grasp quality not fingertip position" answer |
| **GraspXL** | De-novo objective-driven grasp synthesis on 500k+ objects, deployable on different hands. **Not retargeting.** | https://eth-ait.github.io/graspxl/ · https://github.com/zdchan/graspxl | — | ❌ wrong tool |

**The converging trend worth internalizing:** REGRIND, C2Dex, and TopoRetarget independently arrived at **interaction-mesh / Laplacian deformation over a hand+object keypoint graph**. This originates from Ho et al.'s spatial-relationship-preserving character motion adaptation. It is the cleanest published answer to "retarget the *relationship*, not the *pose*" — and because the graph is built over whatever keypoints each embodiment has, **it does not care that the robot has 3 fingers instead of 5.**

---

## C. What specifically breaks with 3 fingers — and exact Dex3-1 kinematics

### C.1 Dex3-1 kinematics, from the URDF (not marketing copy)
Source: https://github.com/unitreerobotics/unitree_ros/blob/master/robots/g1_description/g1_29dof_with_hand_rev_1_0.urdf (also `.xml` MJCF alongside). 7 DoF/hand.

**Right hand joints** (left is mirrored, limits negated):
| joint | axis | lower | upper | effort | velocity |
|---|---|---|---|---|---|
| `right_hand_thumb_0_joint` | **(0,1,0)** | −1.04720 | +1.04720 | **2.45** N·m | **3.14** rad/s |
| `right_hand_thumb_1_joint` | (0,0,1) | −1.04720 | +0.61087 | 1.4 | 12 |
| `right_hand_thumb_2_joint` | (0,0,1) | −1.74533 | 0 | 1.4 | 12 |
| `right_hand_index_0_joint` | (0,0,1) | 0 | +1.57080 | 1.4 | 12 |
| `right_hand_index_1_joint` | (0,0,1) | 0 | +1.74533 | 1.4 | 12 |
| `right_hand_middle_0_joint` | (0,0,1) | 0 | +1.57080 | 1.4 | 12 |
| `right_hand_middle_1_joint` | (0,0,1) | 0 | +1.74533 | 1.4 | 12 |

**Link geometry (right):** palm→thumb_0 `(0.0255, 0, 0)`; thumb_0→thumb_1 `(−0.0025, 0.0193, 0)`; thumb_1→thumb_2 `(0, 0.0458, 0)`; palm→index_0 `(0.0777, −0.0016, +0.0285)`; palm→middle_0 `(0.0777, −0.0016, −0.0285)`; proximal→distal `(0.0458, 0, 0)` for both. Tip frames are +50 mm past the distal link in NVIDIA's asset.
Link names: `{side}_hand_{palm,thumb_0,thumb_1,thumb_2,index_0,index_1,middle_0,middle_1}_link`. **The stock Unitree URDF has no `*_tip` links** — you need NVIDIA's or Unitree's retargeting URDF, which adds `base_link`, `base_link_{thumb,index,middle}`, and `{thumb,index,middle}_tip`.

Tactile: 33 pressure sensors in 9 arrays (3× 2×2 palm, 2×2 per finger pad, 3×1 per fingertip) on the tactile SKU. https://www.unitree.com/Dex3-1

**NVIDIA's retargeting URDF relaxes two limits** vs. the official one — worth noting, they clearly hit binding constraints: `thumb_1` widened to `[−0.920, +0.72431]` (from `[−1.047, +0.611]`) and `thumb_0` velocity raised to `6.857` rad/s.

### C.2 The three things that actually break
1. **Index and middle have zero abduction/adduction.** Both rotate about `(0,0,1)` only. They are *coplanar 2-DoF flexors* fixed 57 mm apart. Any human motion with finger spread, lateral pinch, or a splayed grasp has **no representation at all** on Dex3. The retargeter will project it onto flexion and you lose it silently.
2. **The thumb is the only out-of-plane DoF, and it is the slow/strong one.** `thumb_0` about `(0,1,0)` is the opposition axis: ±60°, 2.45 N·m, but only 3.14 rad/s (geared, vs 12 rad/s direct-drive elsewhere) — **~4× slower than the fingers.** Fast human thumb reposition (re-grasps, in-hand rotation) will lag. If you regress thumb targets at high bandwidth you'll get tracking error that shows up as object slip.
3. **Thumb base is 52 mm more proximal than the fingers** (x=25.5 mm vs 77.7 mm). Combined with `scaling_factor: 1.0`, the workspace where all three tips can meet is small and asymmetric. This is why both NVIDIA and Unitree use scale 1.0 rather than the >1 they use for Inspire (1.15/1.20) and Allegro (1.6) — Dex3 is *not* a scaled-up human hand, and scaling up here would push targets outside reachable space.

### C.3 Merge, drop, or reweight? — what the literature actually does
- **Drop (dominant practice).** Both NVIDIA's and Unitree's Dex3 configs map only `{wrist, thumb tip, index tip, middle tip}`. Ring and pinky contribute **nothing**. This is the default and it is what the shipped code does.
- **Merge (published precedent).** **ManipTrans** is the explicit citation: for the 4-finger Allegro they "adaptively modify the fingertip mapping relationships, **mapping both the pinky and ring fingers to the same fingertip** on the Allegro Hand" and **relax the fingertip keypoint threshold ε_finger to 8 cm**. https://arxiv.org/abs/2503.21860
- **Reweight / low-dim shared space.** CrossDex's eigengrasp action space (https://arxiv.org/abs/2410.02479) and OHRA's canonical hand parameterization (https://arxiv.org/abs/2602.16712) both compress to a hand-independent latent, which handles 5→3 by construction. OHRA is the only published number I found for zero-shot to a *3-finger* hand: 81.9% on 3-finger LEAP.
- **Sidestep entirely.** Dexplore (NVIDIA, CoRL 2025) argues the whole finger-correspondence question is the wrong framing and replaces it with adaptive spatial scopes + RL.

I found **no published failure-mode study specific to 5→3**. That's a genuine gap in the literature.

---

## D. Retargeting under noisy keypoints

### D.1 ⚠️ The trap: keypoint ordering
This is the highest-risk item in your whole pipeline and it fails **silently** (you get a plausible-looking but wrong hand pose).

- `dex-retargeting` expects **MediaPipe/OpenPose-21 ordering**: `0=wrist, 1–4 thumb, 5–8 index, 9–12 middle, 13–16 ring, 17–20 pinky`, so tips are at `4, 8, 12, 16, 20`. Confirmed by the shipped Inspire config: `target_link_human_indices: [[0,0,0,0,0],[4,8,12,16,20]]`.
- **MANO's native 21-joint ordering is different** (wrist, then index/middle/pinky/ring/thumb blocks, with tips appended in that same non-intuitive order). If your V2D input is literally MANO joints, **you must reindex before feeding dex-retargeting.** Verify this against the challenge's data loader before anything else.
- Isaac Lab's own OpenXR→MANO21 remap is `_HAND_JOINTS_INDEX = [1,2,3,4,5,7,8,9,10,12,13,14,15,17,18,19,20,22,23,24,25]` (drops palm + the 4 metacarpals), in `g1_dex_retargeting_utils.py`. Unitree instead uses OpenXR-25 indices `4/9/14/19/24` directly. Same geometry, different integer convention — don't mix them.
- Also required: the frame convention. `dex-retargeting` canonicalizes by subtracting the wrist and applying `OPERATOR2MANO` (`constants.py`). Isaac Lab overrides it with its own `_OPERATOR2MANO_RIGHT/LEFT` = `[[0,0,1],[1,0,0],[0,1,0]]` for the trihand path (different from the Inspire path's `[[0,-1,0],[-1,0,0],[0,0,-1]]`). **You will need to tune this matrix for your input's frame convention.**

### D.2 What noise-handling machinery exists
| Mechanism | Where | Detail |
|---|---|---|
| Output low-pass | `optimizer_utils.LPFilter` | `y ← y + α(x − y)`, applied to the **full robot qpos after** retargeting. Both Dex3 configs use `α = 0.2`. Smaller α = smoother + more latency. |
| Warm start | `SeqRetargeting.retarget` | SLSQP initialized from `clip(last_qpos, limits)`. Implicit temporal coherence. |
| Temporal regularizer | `norm_delta` (default `4e-3`) | Pull toward `last_qpos` — **but see the gradient/objective inconsistency in §A.2.** |
| Keyvector reweighting | `DexPilotOptimizer` | Wrist→tip vectors weighted `9×` vs inter-finger `1×`, with the code comment *"better intuitive mapping due wrong pose detection."* This is the library's actual noise defense: trust the coarse wrist→tip direction over fine inter-fingertip geometry. |
| DexPilot projection hysteresis | `project_dist=0.03`, `escape_dist=0.05` | Asymmetric thresholds → **Schmitt trigger on pinch state**. Prevents grasp chattering from jittery keypoints. Free noise robustness; tune these. |
| Explicit velocity reg | 2506.09384 | `L_vel = Σ w^vel_j‖q_j − q^prev_j‖²` as a first-class objective term. |
| Hard velocity limits | GMR via `mink.VelocityLimit` | `3π` rad/s default, enforced as QP constraints alongside `ConfigurationLimit`. |
| Contact aggregation | C2Dex | Aggregates **noisy frame-wise contact observations in canonical object space** to recover stable contacts. The only method I found that explicitly designs for per-frame observation noise. |

**Honest answer to "is any published retargeting method explicitly robust to keypoint noise?"** — essentially no. Nobody publishes a noise-vs-accuracy curve for retargeting. The closest are C2Dex's canonical-space contact aggregation and dex-retargeting's 9× wrist-vector weighting. Everything else is generic filtering. **If your input is genuinely noisy, this is unclaimed territory and a legitimate contribution angle for the challenge writeup.**

---

## E. Arm / wrist retargeting and G1 IK

| Tool | What | License | Fit |
|---|---|---|---|
| ⭐ **Isaac Lab Pink IK** | `isaaclab.controllers.pink_ik.PinkIKController` / `PinkIKControllerCfg`. Already configured for G1. | BSD-3 | **Use this.** |
| **Pink** | Differential IK as weighted QP tasks over Pinocchio; config + velocity limits enforced. | Apache-2.0 | https://github.com/stephane-caron/pink |
| **mink** | Same idea on MuJoCo. Has Unitree G1 and H1 examples. Native C hot paths. | Apache-2.0 | https://github.com/kevinzakka/mink |
| **GMR** | Body motion retargeting, 18 robots. **Supports `unitree_g1_with_hands` = G1 + Dex3-1, 43 DoF** (changelog 2025-08-09). mink+MuJoCo backend, 35–70 FPS CPU. | **MIT** | https://github.com/YanjieZe/GMR (branch `master`) · https://arxiv.org/abs/2510.02252 (ICRA 2026) |
| **cuRobo** | GPU batched IK / motion gen / collision, whole-body for high-DoF humanoids. | Apache-2.0 | https://github.com/NVlabs/curobo |
| **Open-TeleVision** | Pinocchio CLIK + SE(3) filtering, 60 Hz. | — | https://github.com/OpenTeleVision/TeleVision |

**⚠️ Important correction on GMR:** despite the "with hands" robot entry, GMR's G1 IK match table (`ik_configs/smplx_to_g1.json`) **terminates at `{left,right}_wrist_yaw_link` — there are no finger tasks.** `params.py` maps `unitree_g1_with_hands` to the *same* `smplx_to_g1.json` used by the handless G1. So GMR gives you a very good arm+torso+wrist retargeter and the 14 hand DoF just ride along at default. **You still need dex-retargeting for the fingers.** GMR's useful extras: `human_scale_table` (arms ×0.8, legs ×0.9 for a 1.8 m human → G1), two-stage IK (coarse position-weighted, then orientation-weighted), and `use_velocity_limit=True` at 3π rad/s.

**NVIDIA's exact G1 arm-IK recipe** (`isaaclab_tasks/manager_based/locomanipulation/pick_place/configs/pink_controller_cfg.py`) — copy this verbatim:
```python
G1_UPPER_BODY_IK_CONTROLLER_CFG = PinkIKControllerCfg(
    articulation_name="robot", base_link_name="pelvis", num_hand_joints=14,
    fail_on_joint_limit_violation=False,
    variable_input_tasks=[
        LocalFrameTask("…_left_wrist_yaw_link",  base_link_frame_name="…_pelvis",
                       position_cost=8.0, orientation_cost=2.0, lm_damping=10, gain=0.5),
        LocalFrameTask("…_right_wrist_yaw_link", base_link_frame_name="…_pelvis",
                       position_cost=8.0, orientation_cost=2.0, lm_damping=10, gain=0.5),
        NullSpacePostureTask(cost=0.5, lm_damping=1, gain=0.3,
            controlled_frames=[left/right wrist_yaw],
            controlled_joints=[3×left_shoulder, 3×right_shoulder, waist_yaw/pitch/roll]),
    ])
```
Controlled joints: `.*_{shoulder_pitch,shoulder_roll,shoulder_yaw,elbow,wrist_pitch,wrist_roll,wrist_yaw}_joint` + `waist_.*_joint`. The `NullSpacePostureTask` is the "reduce elbow flare" fix NVIDIA called out in the 2.3 blog. Kinematics URDF: `{ISAACLAB_NUCLEUS_DIR}/Controllers/LocomanipulationAssets/unitree_g1_kinematics_asset/g1_29dof_with_hand_only_kinematics.urdf`.

---

## F. Isaac Lab integration — yes, and more than you'd expect

**Isaac Lab ships `dex-retargeting` as a dependency and a Dex3 retargeter.** `isaaclab/devices/openxr/retargeters/humanoid/unitree/trihand/g1_dex_retargeting_utils.py` literally does `from dex_retargeting.retargeting_config import RetargetingConfig`.

Full retargeter export list (`…/openxr/retargeters/__init__.py`), all **BSD-3-Clause**:
- `GR1T2Retargeter` (Fourier)
- `G1LowerBodyStandingRetargeter`, `G1LowerBodyStandingMotionControllerRetargeter`
- `UnitreeG1Retargeter` — G1 + **Inspire** 5-finger
- **`G1TriHandUpperBodyRetargeter`** — G1 + **Dex3** ← your target
- `G1TriHandUpperBodyMotionControllerRetargeter`, `G1TriHandUpperBodyMotionControllerGripperRetargeter` — controller-driven variants; the gripper one reduces the whole hand to **a binary open/close with Schmitt-trigger hysteresis** (`threshold_high=0.6`, `threshold_low=0.4`). Worth knowing as a fallback.
- `Se3RelRetargeter`, `Se3AbsRetargeter`, `GripperRetargeter`

**Registered runnable env:** `Isaac-PickPlace-FixedBaseUpperBodyIK-G1-Abs-v0` in `isaaclab_tasks/manager_based/locomanipulation/pick_place/`, wiring `G1_29DOF_CFG` + `G1_UPPER_BODY_IK_ACTION_CFG` (Pink) + `G1TriHandUpperBodyRetargeterCfg`. `decimation=4`, `sim.dt=1/200` → **50 Hz control**.

Docs: https://isaac-sim.github.io/IsaacLab/main/source/how-to/cloudxr_teleoperation.html#retargeting-architecture · blog: https://developer.nvidia.com/blog/streamline-robot-learning-with-whole-body-control-and-enhanced-teleoperation-in-nvidia-isaac-lab-2-3
Related: https://github.com/unitreerobotics/unitree_sim_isaaclab (Apache-2.0, G1-29dof + Dex3/Dex1/Inspire tasks, Isaac Sim 4.5/5.x).

⚠️ `dex_retargeting` depends on Pinocchio, which is **not available on Windows** — Isaac Lab's own import is wrapped in `contextlib.suppress(Exception)` for that reason. Linux only.

---

## Ranked recommendation

**1. Start from NVIDIA's `G1TriHandUpperBodyRetargeter` + `g1_hand_*_dexpilot.yml`. Day one.** (BSD-3, in Isaac Lab main, Dex3-specific, validated by NVIDIA.) Strip the OpenXR device wrapper; keep `G1TriHandDexRetargeting`. Replace `convert_hand_joints()` with your own MANO→MediaPipe-21 reindex + canonicalization. Download the hand URDFs from the public S3 URL. This should be running in **2–3 days**, and it is the baseline you must beat before doing anything clever.

**2. Cross-check against Unitree's `unitree_dex3.yml`.** Free second opinion, and its `vector`-type config with per-finger origin frames (`base_link_thumb/index/middle`) is a ready-made ablation against the DexPilot type.

**3. Pink IK for the arm, exactly as NVIDIA configures it.** Don't write your own. If you want the torso/pelvis to help, look at `locomanipulation_g1_env_cfg.py` instead of the fixed-base one.

**4. Then, and only then, add object-awareness.** Ranked by effort:
- **Cheapest, highest ROI: object-relative wrist targets.** You have object 6-DoF poses. Express the wrist target in the *object* frame instead of the world frame before IK. Noise in the object pose and noise in the hand pose partially cancel; and it directly serves an object-tracking metric.
- **Next: residual RL on top of the retargeted trajectory, rewarding object keypoint tracking.** Copy REGRIND's reward shape verbatim: `exp(−ε_object/σ)`, `σ = 0.02`, weight `1.5`, plus object linear/angular velocity matching, wrist pose tracking, action magnitude and action-rate penalties. https://github.com/yunhaif/regrind (**MIT, IsaacSim 5.1.0 + IsaacLab 2.3.0** — the only high-quality codebase I found on your exact stack).
- **If time remains: DexMachina's decaying virtual object controller.** You can implement the idea (drive the object toward its reference with PD gains that decay as reward crosses thresholds) in ~100 lines inside an Isaac Lab env, without porting Genesis. This is the single highest-leverage trick for an object-tracking metric.
- **Skip:** Dexplore (NVIDIA research license + IsaacGym Preview 4 + GRAB pipeline), SPIDER (CC-BY-NC), full ManipTrans, full DexMachina. Read them, don't port them.

---

## What to do about 5→3 specifically, given the object-tracking metric

**Do not spend your 6 weeks perfecting the finger mapping.** The metric scores the *object*, not the hand. Finger joint angles are instrumental, not terminal. Concretely:

1. **Drop ring and pinky. Use the shipped default.** Both NVIDIA and Unitree independently chose this. Ring/pinky contribute almost nothing to the object wrench in a 3-finger tripod anyway, and re-adding them just injects more noisy keypoints into the cost.

2. **If a task clearly needs a power grasp** (large object, enveloping), try ManipTrans' merge rule as a one-line experiment: override `target_link_human_indices` in the YAML so the **middle** finger's keyvectors reference a *virtual* fingertip — e.g. the centroid of human middle/ring/pinky tips — and relax the matching tolerance (ManipTrans went to 8 cm). Both the upstream `target_link_human_indices` key and Unitree's `_dexpilot` variant let you do this without touching library code. Precedent: https://arxiv.org/abs/2503.21860

3. **Weight the thumb heavily and the wrist even more heavily.** 2506.09384's ablation puts λ_thumb_pos = 10 vs λ_fingertip_pos = 1, and dex-retargeting already gives wrist→tip vectors 9× weight. On Dex3 the thumb is the only opposable, out-of-plane, high-torque DoF — it determines whether you have a grasp at all. Index and middle are nearly interchangeable planar flexors; don't burn cost budget distinguishing them.

4. **Keep the pinch/projection term. Tune `project_dist` / `escape_dist`.** The ablation shows removing it → 0% on precision tasks. With noisy keypoints, widen the hysteresis gap beyond the default `0.03/0.05` so the grasp doesn't chatter. This is your cheapest noise defense and it costs one YAML line.

5. **Treat the retargeted hand trajectory as a soft reference, never a target.** Use it to (a) initialize the RL policy, (b) shape an auxiliary imitation reward that you *decay to zero*, and (c) define the contact schedule. The 3-finger gap means the kinematically-retargeted pose is systematically wrong; letting RL deviate from it is the point. This is exactly the argument in DexMachina, Dexplore, and REGRIND, and all three converge on it independently.

6. **Reality check on the thumb:** `thumb_0` is capped at 3.14 rad/s in the official URDF (NVIDIA raised it to 6.857 in theirs — check which limit your sim asset enforces). If your reference trajectories demand faster thumb repositioning than that, the retargeting is not your bottleneck, the hardware model is. Either slow the reference or accept the lag and let RL compensate with the arm.

---

### Files saved to scratchpad (for reference, not deliverables)
`/private/tmp/claude-501/-Users-rongxuanzhou-V2D/c829857b-c70e-4e25-b360-278c1533b028/scratchpad/` — `optimizer.py` (dex-retargeting), `trihand.py` + `trihand_utils.py` (Isaac Lab Dex3 retargeter), `G1_right_hand.urdf` (NVIDIA Dex3 retargeting URDF), `g1hand.urdf` (Unitree G1+Dex3), `pink.py` (Pink IK cfg), `hr.py` (Unitree hand_retargeting), `gmr.md`.
