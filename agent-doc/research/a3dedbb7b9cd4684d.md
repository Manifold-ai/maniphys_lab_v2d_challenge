# agent a3dedbb7b9cd4684d

## PROMPT

Deep WEB RESEARCH task. Use WebSearch and WebFetch heavily (at least 15-20 searches/fetches). Do NOT write any files. Return a dense technical report as your final message with URLs for everything.

CONTEXT: I'm building a pipeline for the NVIDIA V2D Challenge Track 2. Input = noisy 3D hand keypoints + object 6-DoF poses over time. Three noise tiers: clean multi-view GT, synthetically corrupted (jitter/DROPOUT/contact errors sampled from real reconstruction error distributions), and off-the-shelf monocular reconstruction output. These references feed an RL policy for a Unitree G1 humanoid with Dex3 3-finger hands in Isaac Lab. ~6 week timeline.

YOUR SCOPE: OCCLUSION AND DROPOUT HANDLING. Two halves:

=== HALF 1: MOTION INPAINTING / IN-BETWEENING / INFILLING MODELS ===
Find named methods with arXiv URLs, GitHub URLs, whether code+weights are ACTUALLY released (check the repo, don't trust the paper's "code will be released"), license, and a 6-week practicality verdict:
- "Robust Motion In-betweening" (Harvey et al., SIGGRAPH 2020) and its follow-ups
- "Conditional Motion In-Betweening" (Kim et al.) — CondMDI / "Flexible Motion In-betweening with Diffusion Models" (SIGGRAPH 2024, Setareh Cohan et al.)
- TweenDM / "Diffusion-based motion in-betweening"
- SinMDM (Single Motion Diffusion, ICLR 2024)
- MDM's built-in editing/inpainting mode (in-betweening + body-part editing)
- PriorMDM (Human Motion Diffusion as a Generative Prior) — DoubleTake / long-form and its infilling
- "Motion Inbetweening with Phase Manifolds", "Two-stage motion in-betweening", "Task-Oriented Human Motion In-betweening"
- RoHM (Robust Human Motion reconstruction via diffusion, CVPR 2024) — specifically its handling of occlusion/dropout
- Any 2024-2026 transformer/masked-modeling infilling: MaskedMimic (NVIDIA, SIGGRAPH Asia 2024), MotionGPT, T2M-GPT, MoMask, "masked motion modeling"
- HAND-SPECIFIC: "HandDiffuse" (HandDiffuse: Generative Controllers for Two-Hand Interactions via Diffusion Models), "Deformer" (Deformer: Dynamic Fusion Transformer for Robust Hand Pose Estimation), hand pose completion / hand motion infilling works, "HMP: Hand Motion Priors for Pose and Shape Estimation from Video" (WACV 2024), "Hand motion prior", HandMDM / HOIDiff hand infilling
- Anything that does infilling of OBJECT 6-DoF trajectories specifically (not just human body)

=== HALF 2: OBJECT 6-DoF TRACKING THROUGH OCCLUSION ===
Same format (arXiv, GitHub, weights, license, verdict):
- BundleSDF (CVPR 2023, NVIDIA)
- FoundationPose (CVPR 2024, NVIDIA) — including FoundationPose's tracking mode, its known jitter/failure modes, any 2025-2026 successor (FoundationPose++? FoundationStereo? "FoundationPose 2"?)
- MegaPose, OSOP, GigaPose, SAM-6D, Any6D, FreeZe, GenFlow, and the BOP Challenge 2024/2025 "model-free / unseen object" tracks — who actually wins now
- Deep object pose tracking under occlusion: DOPE, se(3)-TrackNet, PoseRBPF, ICG / ICG+ (Stoiber), BOP-track
- SAM2-based tracking (SAM 2 for video object segmentation) and how people combine SAM2 masks with 6-DoF pose trackers to survive occlusion — find concrete 2024-2026 pipelines/repos
- Hand-object joint tracking through occlusion: HOnnotate, "hand-object pose estimation under occlusion", HOISDF, HandOccNet, "occlusion-robust 3D hand pose"
- Anything from HOI datasets tooling: HOT3D (Meta), ARCTIC, DexYCB, OakInk2, TACO, HO-3D — what tooling they ship for filling gaps

ALSO: search for how the V2D / "Video2Dex" / NVIDIA humanoid+dexterous-hand challenge or similar competitions (e.g. the 2025-2026 "Video to Dexterity" or "HOI retargeting" challenges) handle missing/occluded frames, if anything public exists.

For EACH: 1-2 lines what it does, arXiv/project URL, GitHub URL, weights yes/no, license, practicality verdict for ~6 weeks.

Be skeptical: explicitly flag papers where code was promised but never released, and repos that are stale/abandoned. Prioritize 2023-2026.

End with a ranked "what I'd actually plug into a 6-week pipeline" list, separated into (a) hand/body infilling and (b) object pose gap-filling.

---

## REPORT

搜索预算在 200 次时被用光了,后半程全靠 WebFetch 顶(含 arXiv API / arXiv search / GitHub raw)。总共 ~60 次 fetch+search。下面是报告。

---

# 遮挡与 dropout 处理:V2D Track 2 专项调研

## 0. 先说赛题本身查到了什么(这部分比你给的 context 多)

**V2D Challenge 官方页**:https://nvidia-isaac.github.io/video_to_data/v2d_challenge/ ,代码 https://github.com/nvidia-isaac/video_to_data

确认的 Track 2 细节:
- Track 2 = "Robotic Grounding",输入 Third-Person-View 4D HOI → 输出 policy,核心问题原文是 "How much reconstruction error can be tolerated?"
- 三档噪声确实是 Tier 1 clean multi-view GT / Tier 2 从 Track 1 误差分布采样的 jitter+dropout+contact error / Tier 3 off-the-shelf 重建
- 指标:AUC、SP-SR、MP-SR、MPPE,定义在 "CHORD manuscript"(arXiv 上搜不到这个名字,大概率还没公开或者是内部稿,你可以直接发 v2d_challenge@nvidia.com 问)
- 时间线:9/21 数据发布,**11/4 17:00 EST leaderboard 冻结**,11/12 CoRL 2026 公布。每周最多 5 次提交,最后三天不限次数。从今天(9/18)到冻结是 6 周 + 几天,跟你的估计吻合。

**关键情报:Tier 3 的噪声长什么样,是可以反推的。** 我扒了 reconstruction 模块 https://github.com/nvidia-isaac/video_to_data/tree/main/reconstruction ,它包的是:

| 模块 | 底层方法 |
|---|---|
| `v2d_foundation_pose` | FoundationPose(TensorRT / PyTorch 两个后端),物体 6-DoF |
| `v2d_bundlesdf` | BundleSDF,SDF 学习 + texture baking |
| `v2d_cusfm` | CuSFM,相机位姿 |
| `v2d_sam2` | SAM 2 视频分割(给 FoundationPose 喂 mask) |
| `v2d_sam3d_body` | SAM3D-Body + multi-view MHR 优化 |
| `v2d_ego_hand_reconstruction` | **ViPE + Dyn-HaMR**,4D 手部 |
| `v2d_detectron2` | ViTDet 人体检测 |

所以 Tier 3 的手部误差分布 ≈ Dyn-HaMR 的失败模式,物体误差分布 ≈ FoundationPose + SAM2 mask 丢失的失败模式。这两条我下面都单独展开。

**另一个关键情报:官方 baseline 没有做任何 infilling。** robotic_grounding 的 README(https://github.com/nvidia-isaac/video_to_data/tree/main/robotic_grounding)里对噪声的唯一应对是换 reward:clean 多视角数据(arctic/taco/hot3d)用 `contact_wrench_support_reward`,单目噪声数据要把 contact-matching 项全部清零、改用 `force_closure`(weight=5.0),原文说 "rewards the fraction of live wrench-basis directions the hand actually supports, so it never reads the noisy reference geometry"。还有一个手工的 per-sequence gravity 校正(shipped 的 `tissue_box_simple` 需要 8.4° 修正)和 MANO 穿模点投影到 OBB。**没有插值、没有滤波、没有 gap-filling、没有 validity flag。** 这就是你的空档。

---

# HALF 1:Motion Infilling / In-betweening

## A 档:代码 + 权重确实放出来了,6 周内能跑

### HaWoR infiller ⭐ 最对口
手部专用 infiller,单独放了权重。HaWoR 主干是 egocentric 世界坐标手部重建,但它的 `infiller` 是**可独立使用的子模块**,专门补"手出画面"的缺帧。
- arXiv: https://arxiv.org/abs/2501.02973 (CVPR 2025 Highlight)
- GitHub: https://github.com/ThunderVVV/HaWoR (362 star / 43 fork / 22 commits)
- 权重:**有**,`infiller.pt` 在 HuggingFace 上,跟 `hawor.ckpt`、`detector.pt` 一起
- 架构(我读了 https://raw.githubusercontent.com/ThunderVVV/HaWoR/main/infiller/lib/model/network.py):`TransformerModel`,输入投影 → `SinPositionalEncoding` → `TransformerEncoder`,输入 shape `[seq_len, batch, emb_dim]`,默认 out_dim=91。关键是它有三套 mask:`src_mask`、**`data_mask`(可见性 mask 直接 concat 进输入)**、`atten_mask`。`data_mask` 就是你要的 per-frame 可见性标志位,天生支持任意缺帧 pattern,不是 BERT 式随机 mask
- 目录:`infiller/lib/model/{network.py, positional_encoding.py, preprocess.py, skeleton.py}`
- License: **CC-BY-NC-ND** —— ND 是个雷,严格讲不允许 distribute 改动版。比赛内部用/学术提交没问题,但你不能把 fine-tune 后的权重公开发出来。**这点要提前确认比赛规则**
- 6 周判决:**第一优先**。唯一一个「手部 + 缺帧 mask + 权重已放出 + 有 skeleton 抽象」的组合。缺点是 wrapper 依赖 DROID-SLAM + Metric3D,你要自己把 infiller 从 pipeline 里拆出来(它是独立目录,拆起来不难)

### CondMDI (Flexible Motion In-betweening with Diffusion Models)
- arXiv: https://arxiv.org/abs/2405.11126 (SIGGRAPH 2024, Cohan/Tevet/Reda/Peng/van de Panne)
- GitHub: https://github.com/setarehc/diffusion-motion-inbetweening (14 commits,2024-06-21 首发)
- 项目页: https://setarehc.github.io/CondMDI/ ,NVIDIA Research 页: https://research.nvidia.com/publication/2024-05_flexible-motion-betweening-diffusion-models
- 权重:**有**,三个 ckpt(`condmdi_randomframes`、`condmdi_uncond`、`condmdi_randomframes_joints`)走 Google Drive
- License: **MIT**(依赖 CLIP/SMPL/HumanML3D 各自的 license)
- 实用信息:`--edit_mode benchmark_sparse` / `gmd_keyframes` / `uncond`;`--imputate --stop_imputation_at 1`(inference-time inpainting)、`--reconstruction_guidance --reconstruction_weight 20`。README 的 keyframe 条件只演示了 root joint 的 ground location,**partial-joint keyframe 在文档里没有明确支持**,虽然有个 `_joints` ckpt
- 6 周判决:**body 侧第一优先**。但它只训在 HumanML3D(22 joints,body only,**没有手指**),对 Dex3 手指关键点直接没用。适合做 body/wrist 轨迹层的补洞

### MDM 内置 editing
- GitHub: https://github.com/GuyTevet/motion-diffusion-model ,MIT,权重齐全
- 两种 edit mode:`in_between`(补中间帧)和 `upper_body`(下半身固定重生成上半身),都可选 text 条件
- 2025-02 更新了 DiP(ultra-fast)、DistilBERT encoder、50-step 模型(比 1000-step **快 20×**,质量相当)+ CLIP caching 再 2×
- 6 周判决:**最稳的 fallback**。仓库活、文档全、社区大。但同样是 body-only。如果 CondMDI 环境搞不定就退这个

### PriorMDM (DoubleTake)
- arXiv: https://arxiv.org/abs/2303.01418 ,GitHub: https://github.com/priorMDM/priorMDM ,项目页 https://priormdm.github.io/priorMDM-page/
- 权重:有(DoubleTake / ComMDM / fine-tuned motion control 三类)。License **MIT**
- **仓库 news 更新到 2026-04-20**(性能优化 + bugfix),是这批 MDM 系里维护最新的
- DoubleTake 是 inference-time 的长序列拼接,能从 10s 先验拼到 10 分钟。ComMDM 支持 prefix completion
- 6 周判决:**中等**。如果你的 dropout 是"长段整块丢失"(比如遮挡 2-3 秒),DoubleTake 的 transition 机制比逐帧 imputation 更合适。但要自己改造成 infilling

### SinMDM (Single Motion Diffusion)
- arXiv: https://arxiv.org/abs/2302.05905 ,ICLR 2024 Spotlight,OpenReview: https://openreview.net/pdf?id=DrhZneqz4n
- GitHub: https://github.com/SinMDM/SinMDM (24 commits),项目页 https://sinmdm.github.io/SinMDM-page/
- 权重:有(Mixamo / HumanML3D / Truebones Zoo)。License **MIT**
- `python -m sample.edit --edit_mode in_betweening`,支持 BVH 和 npy,**任意 skeleton topology**(这点对 Dex3 有潜在价值)
- 6 周判决:**低**。它是 single-motion 模型,每段动作要单独训,轻量网络但仍要小时级。除非你想给每个 demo 单独过拟合一个 prior,否则不划算

### HandX(2026 新,双手专用)⭐ 意外之喜
- arXiv: https://arxiv.org/abs/2603.28766 (CVPR 2026, 2026-03-30)
- GitHub: **https://github.com/handx-project/HandX —— 我验证过,不是占位仓库**。29 commits,有 `diffusion/`、`autoregressive/`、`evaluation/`、`simulation/`(IsaacGym)、`data/processing/`
- 数据集 2026-05-29 全量发布(Google Drive + HuggingFace),ARCTIC 和 H2O 因 redistribution policy 要自己跑预处理脚本
- **明确支持的任务里就有 "Motion in-betweening: filling gaps between fixed first and last frames"**,还有 contact-keyframe conditioning、固定一只手生成另一只、锚定 wrist 轨迹
- Checkpoint:evaluation encoder 有下载;生成模型权重 README 里没写死,需要确认
- 项目页 https://handx-project.github.io
- 6 周判决:**高**,但有风险。它是双手 + 用了 ARCTIC(V2D Track 2 数据源之一!)+ 带 IsaacGym 可视化,契合度非常高。风险在于生成模型 ckpt 是否真放出来 —— 这个你第一天就该 clone 下来验证

### Motion In-betweening via Two-Stage Transformers (SIGGRAPH Asia 2022)
- GitHub: https://github.com/victorqin/motion_inbetweening ,**MIT**,Releases 里有预训练模型,LaFAN1
- Context Transformer + Detail Transformer 两阶段,也可以只用 context-only
- 4 commits / 4 open issues,**基本停更**,但代码是完整的
- 6 周判决:**中**。纯确定性 transformer,没有 diffusion 的采样开销,批量补洞时延迟优势明显。skeleton-agnostic 程度比 MDM 系高

### Delta-Interpolator
- arXiv: https://arxiv.org/abs/2201.06701 ,GitHub: https://github.com/boreshkinai/delta-interpolator
- **Apache-2.0**(这批里 license 最宽松的),预训练模型走 Google Storage,有 Docker,LaFAN1 + Anidance
- 44 commits,停更
- 6 周判决:**中**。学 delta(相对于插值基线的残差)这个设计对你特别有用 —— 它天然把"线性插值 + 学到的修正"分开,坏掉的时候能优雅退化到 lerp/slerp。做 baseline 很合适

### CMIB (Conditional Motion In-betweening, Kim et al.)
- arXiv: https://arxiv.org/abs/2202.04307 ,Pattern Recognition 2022;GitHub: https://github.com/jihoonerd/Conditional-Motion-In-Betweening (382 commits)
- 权重:有(单独链接)。**License 未声明** —— 这是个法律风险点
- pose-conditioned + semantic-conditioned 统一模型,LaFAN1
- 6 周判决:**中低**。代码质量不错但 license 空白

### RoHM(遮挡/dropout 的教科书写法)
- arXiv: https://arxiv.org/abs/2401.08570 (CVPR 2024),GitHub: https://github.com/sanweiliti/RoHM ,项目页 https://sanweiliti.github.io/ROHM/ROHM.html
- 权重:**有**,在 GitHub Releases v0。License: **CC-BY-NC**(代码/ckpt/数据集),部分组件 MIT/Apache
- 我读了 v2 全文,细节:
  - **TrajNet**(1D temporal conv U-Net,处理 root position/rotation/height,**刻意不用速度以避免 drift**)+ **PoseNet**(transformer encoder,局部关节)+ **TrajControl**(zero-init conv 的 ControlNet 式模块,用去噪后的 pose 反过来精修 trajectory)
  - 遮挡 mask 格式:binary mask `M_R`/`M_P` 逐元素相乘,1=可见。RGB(-D) 下的判据是 **confidence < 0.2 且被场景深度遮挡**
  - 迭代推理 K=2,每轮完整去噪(TrajNet 100 步,PoseNet 1000 步)
  - 补洞实验 "Occ-10%":**整段连续帧(序列长度的 10%)全关节缺失**
  - 运行时:144 帧 / A100 **59 秒**(HuMoR 要 30 分钟)
  - **明确不建模手**:原文 "we do not use θ_h and φ and consider only the main body parameters, with a total of 22 body joints"
- 6 周判决:**别直接用,但一定要抄设计**。三点可直接搬:(1) 轨迹/局部姿态解耦;(2) confidence<0.2 + depth 双判据生成 occlusion mask;(3) TrajNet 不吃速度。59s/144帧太慢,不适合大批量

### HMP (Hand Motion Priors, WACV 2024)
- arXiv: https://arxiv.org/abs/2312.16737 ,项目页 https://hmp.is.tue.mpg.de/ ,GitHub: **https://github.com/enesduran/HMP**
- 权重:**有**,预训练 motion prior 已经放在 `./outputs/generative/results/model`。License **MIT**(仓库),但 MPI 系一般另有数据 license
- 输入:video / 2D keypoints(MediaPipe、MMPose)/ MANO 参数。在 AMASS 手部数据上训 prior,做 latent optimization
- 10 commits。依赖重:PyMAF-X + METRO 已内嵌在 `./external/`,还要 PyTorch3D、mmpose,环境锁死 Ubuntu 20.04 / Py3.10 / CUDA 12.1 / PyTorch 2.1
- HO3D 的 occlusion 子集上专门评过
- 6 周判决:**中**,但**优先级被 Dyn-HaMR 部分替代**(见下)。latent optimization 是 per-sequence 优化,慢。如果你只要 prior 本身当正则项,可以只取模型不取优化循环

### Dyn-HaMR ⭐ 这个必须重点看
因为 **V2D 官方 egocentric 手部重建就是用它**。
- arXiv: https://arxiv.org/abs/2412.12861 (v3 2025-05-31)
- GitHub: **https://github.com/ZhengdiYu/Dyn-HaMR** —— 代码 2025-06-04 released,**2025-11-20 还在更新**(集成了 ViPE 相机估计 + 手部追踪改进),ckpt 走 `prepare.sh`
- License: **MIT** 但附加 "non-commercial research purposes only" + MANO 单独协议
- 它的 generative infilling 用的就是 **HMP** 的 prior(README 原话:"For biomechanical constraints and motion prior, we use the code from [here] and HMP"),开关是 `run_prior=True`
- 6 周判决:**必做**。两个理由:(1) 你能直接复现 Tier 3 的误差分布 —— 把 Dyn-HaMR 跑在已知 GT 的 ARCTIC/HOT3D 序列上,量出来的 residual 就是 Tier 2 该采样的分布;(2) `run_prior=True` 这条路已经被官方 pipeline 验证过能跑通

### MaskedMimic / ProtoMotions ⭐ 战略级
- arXiv: https://arxiv.org/abs/2409.14393 (SIGGRAPH Asia 2024),项目页 https://research.nvidia.com/labs/par/maskedmimic/ 和 https://xbpeng.github.io/projects/MaskedMimic/
- GitHub: **https://github.com/NVlabs/ProtoMotions**,**Apache-2.0**
- **权重:有**。我查到 pretrained models 页 https://nvlabs.github.io/ProtoMotions/getting_started/pretrained_models.html 列了 8 个 ckpt,其中 **"SMPL MaskedMimic — Sparse/masked future-motion control — IsaacLab only"**。另外有 **"G1 BONES-SEED deployment tracker"**,注明 "IsaacLab; expected to transfer"
- 支持的机器人:SMPL / SMPL-X / **Unitree G1** / **H1_2** / 自定义 XML。仿真器:Newton 1.0.0、IsaacLab 3.0、IsaacGym Preview 4、MuJoCo 3.0+、Genesis(未测)
- **但**:docs 里**没有提 dexterous hands 或 Dex3**,支持的是 G1 全身 tracking。MaskedMimic 训练需要先有 pretrained Mimic expert(两段式:先 RL 训 Mimic,再 behavioral cloning 蒸馏),从零训成本很高
- Issue #65 (https://github.com/NVlabs/ProtoMotions/issues/65) 有人问 v2.0 的 pretrained ckpt 和长距离目标插值能力,issue 已关但页面上看不到维护者回复
- 6 周判决:**当作架构参考,不要当作 6 周内能训出来的东西**。核心思想值一整段:**把"参考轨迹缺帧"直接建模成 policy 的 masked observation,而不是在数据侧补洞**。也就是给 policy 喂 `(reference, visibility_mask)`,训练时随机 mask —— 这样 Tier 1/2/3 用同一个 policy,不需要三套 pipeline。这条路对 Track 2 的 "how much error can be tolerated" 命题是正面回答。而且 ProtoMotions 已经支持 G1,retarget 用 PyRoki,跟 V2D 的 IsaacLab + RSL-RL PPO 栈天然兼容

### MoMask / MotionGPT / T2M-GPT(masked modeling 一路)
- **MoMask**: https://arxiv.org/abs/2312.00063 (CVPR 2024),https://github.com/EricGuo5513/momask-codes ,**MIT**,权重有,最后更新 2024-08-02。`edit_t2m.py -msec 0.4,0.7` 做时间段 inpainting(RVQ token 层面 mask + 重生成 residual)。**但编辑基本要 `--text_prompt`**,你的场景没有 text
- **MotionGPT**: https://github.com/OpenMotionLab/MotionGPT ,**MIT**,权重有(Google Drive + HF),原生支持 motion prediction 和 **in-between** 任务,prediction 上 FID 0.905 优于 MDM 和 T2M-GPT。2025 年出了 MotionGPT3
- **T2M-GPT**: https://github.com/Mael-zys/T2M-GPT ,Apache-2.0,权重有,但**最后更新 2023-02,且不支持 inpainting/in-betweening**。跳过

## B 档:论文好,代码有坑 —— 点名批评

| 方法 | 问题 |
|---|---|
| **HandDiffuse** (AAAI 2025) | arXiv https://arxiv.org/abs/2312.04867 ,项目页 https://handdiffuse.github.io/ 写 "will be disseminated"。GitHub **https://github.com/HandDiffuse/HandDiffuse 我验证过:5 commits,只有 README,没有代码、没有权重、没有 HandDiffuse12.5M 数据集下载**。论文 2023-12 挂出,到今天 2026-09 还是空的 —— **典型的 "code will be released" 烂尾**。别等 |
| **Deformer** (ICCV 2023) | https://arxiv.org/abs/2303.04991 ,https://github.com/fuqichen1998/Deformer ,Apache-2.0。**只有训练/评估代码,没有 pretrained weights**,5 commits 后停更。而且它是 RGB 图像输入的,不能只吃 keypoints。你的输入是已经重建好的 keypoints,用不上 |
| **UniHand** (2026-02) | https://arxiv.org/abs/2602.21631 。JVAE 把 MANO 参数和 2D skeleton 嵌到共享 latent + latent diffusion,**明确支持 motion infilling / incomplete sequences**,最对口的 formulation。但 arXiv 页面**没有任何 code/weights/project URL**。写信问作者吧,别排进 plan |
| **SILK** (CVPR 2025 workshop) | https://arxiv.org/abs/2506.09075 ,单个 transformer encoder,核心论点是"数据建模选择(pose representation、velocity feature、数据量)比模型复杂度重要"。项目页 silk-paper.github.io,**abstract 没确认代码放出**。论点值得读(直接指导你的特征设计),代码别指望 |
| **Less is More: Sparse Keyframes** | https://arxiv.org/abs/2503.13859 (v2 2025-05-12)。mask 掉非关键帧 + 高效插值,推理时动态精修 keyframe mask。**无 code/repo 信息** |
| **Scalable Motion In-betweening via Diffusion + Physics** | https://arxiv.org/abs/2504.09413 。两阶段:character-agnostic diffusion 在 canonical skeleton 上生成 transition,再用 RL 适配目标形态。**跟你的 pipeline 结构几乎一样**(infill → retarget → RL),但**无代码、无项目页** |
| **Motion In-Betweening for Densely Interacting Characters** | https://arxiv.org/abs/2510.00314 (2025-09-30, ACM venue)。Cross-Space In-Betweening + 对抗学习 + latent refinement 防误差累积。**无代码** |
| **Robust Motion In-betweening** (Harvey, SIGGRAPH 2020) | arXiv https://arxiv.org/abs/2102.04942 。**官方从未放代码**。数据集在 https://github.com/ubisoft/ubisoft-laforge-animation-dataset (LaFAN1,77 seq / 496,672 frames / 30fps / BVH,**CC BY-NC-ND 4.0**,含 L2Q/L2P/NPSS benchmark 代码)。社区复现:https://github.com/jihoonerd/Robust-Motion-In-betweening (80 commits,88 star,**license 未声明,权重不明**)、https://github.com/xjwxjw/Pytorch-Robust-Motion-In-betweening 。**2020 年的 RNN+GAN,已被 2022+ transformer / diffusion 全面超越,不建议复现** |
| **TweenDM** | arXiv 搜不到这个名字的论文。可能是你记混了,或者是某个非 arXiv 的工作。当作不存在 |
| **Motion Inbetweening with Phase Manifolds** (SCA 2023) | 代码托管在 Starke 的 AI4Animation 体系里而非独立 repo,`paulstarke/PhaseManifolds` 是 404。Unity/C# 栈,接进 Python pipeline 成本高。**跳过** |
| **Task-Oriented Human Motion In-betweening** | arXiv search 多次 429,没验证到。优先级低,跳过 |

## C 档:物体 6-DoF 轨迹的 infilling —— 这块基本是空白

我专门搜了 "object pose trajectory infilling occlusion" 和 "6DoF object pose denoising diffusion trajectory refinement",arXiv **两个查询都是 0 结果**。结论:**没有现成的、专门做物体 6-DoF 轨迹补洞的方法**。能借的只有 HOI 生成模型(它们把物体轨迹当作生成目标的一部分):

| 方法 | URL | 权重/License | 能否做 infilling |
|---|---|---|---|
| **HOI-Diff** | https://github.com/neu-vi/HOI-Diff | 有权重,**MIT**,134 commits | 文档只演示 full-sequence 从 text 生成,**没有 partial trajectory completion** |
| **CHOIS** (ECCV 2024) | https://github.com/lijiaman/chois_release | 有权重,**MIT**,13 commits | "object motion and human motion given text, object geometry, and **initial states**",提到 3D scene waypoints。**最接近可用的条件生成**,但稀疏 waypoint conditioning 要读代码确认 |
| **OMOMO** (SIGGRAPH Asia 2023) | https://github.com/lijiaman/omomo_release ,https://arxiv.org/abs/2309.16237 | 有权重,**MIT**,11 commits | object motion → human motion 单向,不能补物体 |
| **InterDiff** (ICCV 2023) | https://github.com/Sirui-Xu/InterDiff | 有权重(2023-10-27),**MIT**,45 commits | 是 **anticipation / forward prediction**,不是 infilling。停更 |
| **Text2HOI** (CVPR 2024) | https://github.com/JunukCha/Text2HOI | 有权重(Google Drive),**MIT**,33 commits | 手-物交互生成,支持 H2O/GRAB/**ARCTIC**。数据源跟 V2D 重合,值得看 |
| **MAD-HOI** (2026-08) | https://arxiv.org/abs/2608.10162 | **无代码信息** | **明确支持 "conditioned motion completion and infilling"**,hand/object 双流解耦。formulation 最对口但拿不到代码 |

**我的建议是别指望 learned 方法**。物体是刚体、6-DoF、短时间尺度上运动光滑,用经典方法就够:
- 位置:constant-velocity / constant-acceleration Kalman + RTS smoother,或 cubic spline
- 旋转:SLERP / SQUAD,或者在 SO(3) 上做 geodesic B-spline;长洞用 `scipy.spatial.transform.RotationSpline`
- 接触约束:被手抓住的帧段,物体位姿直接从手腕位姿 + 抓取时刻的相对变换刚性外推(rigid grasp assumption)。这一条在 Track 2 场景下比任何生成模型都准,因为 contact 期间物体和手就是刚性连接的
- 判据:用 contact label 决定用哪套 —— 接触中 → 手腕外推;自由飞行 → 抛物线 + Kalman;静置 → hold last pose + support surface 约束(V2D 已经有 `reconstruct_support_surfaces.py`)

---

# HALF 2:物体 6-DoF 穿越遮挡的跟踪

## 现役主力

### FoundationPose ⭐(V2D 官方就在用)
- arXiv: https://arxiv.org/abs/2312.08344 (CVPR 2024 Highlight),GitHub: **https://github.com/NVlabs/FoundationPose**(3.6k star / 535 fork / **135 open issues**)
- 权重:有(Google Drive);HF 镜像 https://huggingface.co/nvidia/foundationpose ;NGC https://catalog.ngc.nvidia.com/orgs/nvidia/teams/isaac/models/foundationpose ;推理库 https://github.com/nvidia-isaac/foundation-pose-inference-library
- License: **NVIDIA Source Code License**,权重非商用、不可再分发衍生
- **已知失败模式(README 自陈 + 社区)**:
  1. 放出的权重**没有 diffusion-augmented 数据训练**(Stable Diffusion / LAION 的法律限制),官方承认 "slight performance degradation expected"
  2. **tracking 是伪 tracking** —— 每帧拿上一帧的解当初值做优化,没有真正的时序模型。所以需要 **20-50Hz** 才好用,**降到 ~5Hz 就严重退化**
  3. **丢了之后不会自己恢复**,必须外部 reset
  4. 需要 CAD mesh(model-based)或少量 reference images 训 Neural Object Field(model-free)
- 6 周判决:**你大概率不用自己跑它**(Tier 3 数据是官方给的)。但要理解它的失败模式来建模 Tier 2 的噪声:**不是高斯白噪 —— 是"跟到一半慢慢漂,然后整段崩掉,直到 mask 重新出现"**。你的 corruption 模型应该是 burst dropout + 低频 drift,不是 i.i.d. jitter

### FoundationPose++ ⚠️
- GitHub: https://github.com/teal024/FoundationPose-plus-plus
- 四模块:FoundationPose + 2D tracker(Cutie / Samurai / OSTrack)+ Kalman filter(roll/pitch/yaw)+ **Amodal Completion**
- **Amodal completion 模块没真正放出来** —— README 原话 "This module might run slowly and have some compatibility issues, we are still working on the optimization"。2025-03-12 public preview 之后没大动静
- **License 缺失**
- 没有任何定量 benchmark,只报速度(3090 上 FoundationPose >30 FPS,OSTrack >100 FPS)
- 6 周判决:**别依赖它,但抄它的结构**。「2D tracker 管 xy + Kalman 管旋转 + 深度补 z」这个分解本身是对的,而且你自己实现只要两天

### BundleSDF(V2D 也在用)
- CVPR 2023,项目页 https://bundlesdf.github.io/ ,GitHub: **https://github.com/NVlabs/BundleSDF**(1.4k star / 171 fork / 29 open issues / **18 commits**)
- 权重:有(XMem 分割网络 + LoFTR outdoor)。License:LICENSE.txt(NVIDIA 系)
- 不需要 CAD,只要第一帧分割。"near real-time",论文宣称对 "large pose changes, partial and full occlusion, untextured surfaces, specular highlights" 鲁棒
- Docker 安装,`build.sh` 编译机器相关包
- 6 周判决:**中**。V2D 已经封装成 `v2d_bundlesdf` 了,你要用就走官方 wrapper。自己从源码起环境会烧掉好几天

### SAM 2
- GitHub: https://github.com/facebookresearch/sam2 ,**Apache 2.0**,四档权重(tiny 38.9M / small 46M / base+ 80.8M / large 224.4M)
- streaming memory 做实时视频传播。**README 层面没有明确文档化 occlusion prediction head 或 memory bank 对"消失后重现"的处理**(论文里有 occlusion head,但仓库文档没强调)
- 最新是 SAM 2.1 (2024-09),README 里没提 SAM 3
- 6 周判决:**你的 mask 层就是它**。V2D 的 `v2d_sam2` 已经封好

### SAM2 + FoundationPose 的具体 pipeline(2024-2026 实际存在的)

| 仓库 | 内容 | License | 状态 |
|---|---|---|---|
| **FoundationPoseROS2** | https://github.com/ammar-n-abbas/FoundationPoseROS2 ,RealSense + SAM2 + FoundationPose,**193 commits / 296 star / 42 fork** —— 这批里最成熟的 | **MIT** | 活跃 |
| **FoundationPoseROS** (IRVLUTD) | https://github.com/IRVLUTD/FoundationPoseROS ,SAM2 交互式点选分割初始化 FoundationPose,ROS1+ROS2 双支持 | MIT + NVIDIA Source Code License 双重 | 只有 7 commits |
| **SuperPose** | https://arxiv.org/abs/2409.19986 (2024-10)。免 mask 初始化(点一下 + LightGlue 特征匹配自动恢复)+ SAM2 解决 tracking loss + 对称物体自旋 | 代码未见 | 论文 only |
| **Any6D** (CVPR 2025) | https://github.com/taeyeopl/Any6D ,单张 RGB-D anchor 估计未知物体的 6D pose **和尺寸**,render-and-compare。权重是拼的(FoundationPose + SAM2 + InstantMesh) | LICENSE 文件存在,类型未明 | 8 commits,**单次估计不是 tracking** |

- 6 周判决:**FoundationPoseROS2 是最值得抄的参考实现**,它的 SAM2→mask→FoundationPose 数据流可以直接搬成非 ROS 的 Python 脚本。但你的输入是离线 Tier 3 数据,这些在线 pipeline 主要是给你看**恢复策略**怎么写

### 经典跟踪器(都能用,都老)

| 方法 | URL | 权重/License | 判决 |
|---|---|---|---|
| **se(3)-TrackNet** (IROS 2020) | https://arxiv.org/abs/2007.13866 ,https://github.com/wenbowen123/iros20-6d-pose-tracking | 有权重 | **~90 fps**,论文称"对大遮挡和突然重定向鲁棒"。**但每个物体要单独训**,2020 年的东西。跳过 |
| **BundleTrack** (IROS 2021) | https://github.com/wenbowen123/BundleTrack | 权重有(LF-Net + 视频分割),**Apache-2.0** | **不需要 CAD**,CUDA 实现 **10Hz**。**4 commits,2021 后完全停更**。BundleSDF 是它的后继 |
| **PoseRBPF** | https://github.com/NVlabs/PoseRBPF | 权重有(YCB + T-LESS 的 auto-encoder + PoseCNN),**NVIDIA 非商用** | Rao-Blackwellized 粒子滤波,**天然带不确定性估计**。96 commits / 9 open issues。**每个物体要训 auto-encoder**。想要"遮挡期间的 pose 分布"而不是点估计的话,这个思路值得借 |
| **ICG / ICG+ / M3T / SRT3D** (Stoiber, DLR) | https://github.com/DLR-RM/3DObjectTracking (**1.0k star / 185 fork / 42 commits**) | **MIT** | 六个算法,最新在 `M3T/` 目录。region-based + depth,**真·实时**(CPU 上几百 Hz)。需要 3D mesh + kinematic info。**C++,无 Python binding**。作为轻量级 refiner/smoother 很香,但接进 Python pipeline 要写 pybind |
| **DOPE** | https://github.com/NVlabs/Deep_Object_Pose | YCB + HOPE 权重,**CC BY-NC-SA 4.0**,276 commits | 只认已知物体类别,单帧,不 tracking。**你的场景用不上** |

### BOP Challenge:现在谁在赢

- BOP 2025 主页 https://bop.felk.cvut.cz/challenges/bop-challenge-2025/ ,**11 个 track**:
  - BOP-Classic-Core (T1-3):model-based unseen 的 6D localization / 6D detection / 2D detection
  - **BOP-H3 (T4-7)**:数据集 = **HOT3D、HANDAL、HOPEv2**(手-物交互!)。**T6 = model-free 6D detection of unseen objects**、T7 = model-free 2D detection
  - BOP-Industrial (T8-11)
- 时间线(https://bop.felk.cvut.cz/home/):2025-08-19 放出了 model-free 任务的新 object-onboarding 序列(含更新的 **HOT3D 和 HANDAL**);**2025-11-16 BOP 2025 Awards 公开(Google Drive)**;2025-11-23 ICCV'25 R6D workshop 录像上线(含获奖者报告和结果分析)。Workshop 页 https://cmp.felk.cvut.cz/sixd/workshop_2025/ ,2026 版 https://cmp.felk.cvut.cz/sixd/workshop_2026/
- **BOP 2024 的硬数字**(论文 https://arxiv.org/abs/2504.02812 ,拿了 CVPR 2025 CV4MR Best Paper):
  - **FreeZeV2.1** 最准,比 2023 最佳(GenFlow)高 **22%**,但 **24.9 s/image**
  - **Co-op** 才是实用解:**0.8 s/image**,比 GenFlow 准 **13%** —— 快 31 倍
  - 获奖名单还有 FoundationPose (Wen/Yang/Kautz/Birchfield)、GigaPose、SAM6D、CNOS、GFreeDet
  - **最关键的一句**:unseen object 的 **2D detection 精度比 seen object 落后 35%,2D detection 是整个 pipeline 的主要瓶颈** —— 换句话说,**遮挡下丢的不是 pose,是 detection/mask**。这直接印证了"SAM2 mask 一断,FoundationPose 就废"的因果链
- 我多次尝试抓 BOP-H3 model-free 的具体 leaderboard 页(`/leaderboards/pose-detection-unseen-modelfree-bop-h3*/hot3d/`),服务端一直返回 model-based Classic-Core 的内容,**没拿到 2025 的具体排名**。你自己去 https://bop.felk.cvut.cz/leaderboards/ 点进 BOP-H3 看

### 零样本单帧方法(可当 re-init 用)

| 方法 | URL | 权重/License | 备注 |
|---|---|---|---|
| **SAM-6D** (CVPR 2024) | https://github.com/JiehongLin/SAM-6D | 权重有,**license 未声明** | RGB-D,需要 CAD,支持 SAM 和 FastSAM。**最后更新 2024-03-05**。逐帧,无 tracking |
| **GigaPose** (CVPR 2024) | https://arxiv.org/abs/2311.14155 ,https://github.com/nv-nguyen/gigaPose | 权重有,**MIT** | 模板恢复 out-of-plane 2DoF + patch correspondence 补剩下的。2024-05 适配了 BOP 2024。HOPEv2 6D detection **22.57 mAP**(无 refine)。**快**,适合做 re-init |
| **MegaPose / HappyPose** | https://github.com/agimus-project/happypose | 权重有(CosyPose + MegaPose),**BSD-2-Clause** | **780+ commits,有 CI,这批里维护最好的**。render-and-compare |
| **FreeZe** (ECCV 2024) | https://arxiv.org/abs/2312.00947 | ⚠️ **https://github.com/AndreaCaraffa/FreeZe 只是项目网站的源码(6 commits,CC BY-SA 4.0),不是实现** | BOP 2024 最准但 24.9 s/image。**实际实现代码我没找到,flag 为未确认释出** |
| **GenFlow** | BOP 2023 winner (Moon et al.) | ⚠️ **GitHub 搜索 0 结果,官方 repo 找不到** | flag 为**未释出** |
| **SinRef-6D** | https://arxiv.org/abs/2503.05578 (T-RO 2026) | 项目页有 code + robot demo | 单张 RGB-D reference,state space model,免 CAD |
| **ProxyPose** | https://arxiv.org/abs/2607.06555 (2026-07-07) | 项目页 https://ruihangzhang97.github.io/proxypose/ ,**代码状态未确认** | 把 6-DoF tracking 重铸成 video-to-video translation:只给视频 + 一个像素点,video diffusion 生成一个"彩色多面体"代理视频。宣称吃掉了 "challenging materials, occlusions, deformations"。**免 CAD、免 depth、免 mask**。概念上最激进,6 周内不可用,但值得盯 |

### FoundationStereo(顺带)
- https://github.com/NVlabs/FoundationStereo ,CVPR 2025。两档权重(ViT-Large `23-51-11` 最准 / ViT-Small `11-33-40` 更快),2025 年加了 ONNX/TensorRT/Jetson 支持
- 跟 6-DoF pose 不直接相关,但**如果你的 Tier 3 是 RGB-only 而 FoundationPose 需要 depth,这是补 depth 的路子**

## 手-物联合 + 数据集工具链

| 项目 | URL | 权重/License | 遮挡相关 |
|---|---|---|---|
| **HOISDF** (CVPR 2024) | https://arxiv.org/abs/2402.17062 ,https://github.com/amathislab/HOISDF | **权重在 Zenodo(2024-07)**,license 未声明,2024-08 最后更新 | SDF 引导手-物姿态。**必须有 SDF 文件**(自己下载或用 AlignSDF 生成),1000 顶点简化模型。DexYCB + HO3Dv2 SOTA |
| **HandOccNet** (CVPR 2022) | https://arxiv.org/abs/2203.14564 ,https://github.com/namepllet/HandOccNet | 有 | feature injection 把手部信息注入被遮挡区域。2022 年的,单帧 |
| **HOnnotate / HO-3D** | https://github.com/shreyashampali/ho3d | **学术非商用,禁止再分发** | v3 精度更高,含 extrinsics + 多相机点云融合。专门为 severe occlusion 设计。**2024-11-03 还更新过**(放了 v2/v3 GT + eval 脚本) |
| **HOT3D** (Meta) ⭐ | https://github.com/facebookresearch/hot3d | API **Apache 2.0**,数据集另有 HOT3D license;MANO 需单独同意 | **关键:ships `mask_hand_visible` 和 `mask_object_visible` 两个可见性 mask** —— 这是现成的 dropout ground truth。手部有 UmeTrack 和 MANO 双格式。73 commits。**但只提供过滤,不提供 gap-filling** |
| **ARCTIC** | https://github.com/zc-alexfan/arctic | **非商用(数据+软件都是)** | 2.1M 图 / 9 视角(8 第三人称 + 1 egocentric)/ 54 台 Vicon。SMPL-X + MANO + articulated object。**README 完全没提遮挡/缺帧处理**。ECCV'24 办过 competition |
| **DexYCB** | https://github.com/NVlabs/dex-ycb-toolkit | **GPL-3.0**(注意传染性!) | **无效帧有明确标记**:没有手部标注时 `pose_m` 全 0、`joint_3d` 全 -1。还有 `is_bop_target` 标记关键帧。83 commits,基本停在 2021 |
| **OakInk2** | https://github.com/oakink/OakInk2 | license 未声明 | MANO + SMPL-X + 物体 4×4 变换矩阵 + primitive task 标注。2024-12 修过标注上传,2025-04 加了向后兼容文件。**无 gap-filling** |
| **TACO** | https://github.com/leolyliu/TACO-Instructions | **CC BY 4.0**(这批里最宽松) | 2317 序列 / 151 个 `<tool, action, object>` 三元组 / 206 个物体模型。**提供 marker-removed 的 12 视角视频**。egocentric RGB-D + 多视角 allocentric。CVPR 2024 |

**注意**:V2D robotic_grounding README 里点名的 clean 多视角数据集正好是 **arctic / taco / hot3d** 三个。所以:
- **HOT3D 的 `mask_*_visible` 就是你生成 Tier 2 dropout pattern 的 ground truth 来源** —— 不用瞎猜 dropout 分布,直接从 HOT3D 统计真实的遮挡段长度分布
- **DexYCB 的 `pose_m` 全 0 / `joint_3d` 全 -1** 是现成的缺失表示约定,你的 schema 可以沿用

### ViDiHand(2026,值得一提)
- https://arxiv.org/abs/2606.30308 (v2 2026-07-09),项目页 vidihand.github.io
- 论点很激进:**不需要 detection、不需要 infilling**,直接用预训练 video diffusion 的表征 + hand-overlay rendering objective 微调,在全帧上解码 metric-scale pose。理由是 internet-scale video 预训练本身就学到了遮挡推理和手-物交互
- 在 **ARCTIC、HOT3D、HOI4D** 上大幅超过前人 —— 这三个数据集跟 V2D 的重合度极高
- 代码状态未确认。**6 周内不可用,但如果它放代码了,对 Tier 3 是降维打击**

---

# 最后:6 周里我会真正插进 pipeline 的东西

## (a) 手/身体 infilling —— 排序

**1. 先写一个不用学习的 baseline,当天就能跑完(半天)**
不是凑数。理由:dropout 段通常短(FoundationPose/Dyn-HaMR 丢帧多在 0.1-1s),短洞上 spline + SLERP 的误差远低于任何 diffusion 模型的采样噪声,而且零延迟、零 license 风险、零环境debug。具体:
- 手腕 6-DoF:位置 cubic spline / Kalman-RTS,旋转 SQUAD 或 `scipy.spatial.transform.RotationSpline`
- 手指关节:MANO PCA 空间(或 axis-angle)上线性插值 + Savitzky-Golay 平滑
- **同时输出一个 per-frame `validity` 通道**,下游 policy 能看见哪些帧是编的
这条是你的 floor,后面所有学习方法都要打赢它才配上线。

**2. HaWoR infiller**(https://github.com/ThunderVVV/HaWoR)—— 手部专用、权重已放、`data_mask` 天然吃任意缺帧 pattern。把 `infiller/` 拆出来当独立模块。**唯一的 blocker 是 CC-BY-NC-ND 的 ND 条款,第一天就去确认比赛规则允不允许**。

**3. MaskedMimic 式的 masked-observation 训练**(架构思想,不是代码)—— 别在数据侧补洞,直接给 policy 喂 `(reference, visibility_mask)`,训练时随机 mask。这直接回答 Track 2 的命题 "how much reconstruction error can be tolerated",而且 Tier 1/2/3 共用一个 policy。ProtoMotions(Apache-2.0,已支持 G1 + IsaacLab 3.0 + RSL-RL,https://github.com/NVlabs/ProtoMotions)是你能参考的现成实现。**这条是我认为投入产出比最高的一条**,因为它是方法论创新而不是接个库。

**4. HandX**(https://github.com/handx-project/HandX)—— 双手 + 原生 in-betweening 任务 + 数据源含 ARCTIC + 带 IsaacGym。**第一天就 clone 下来验证生成模型 ckpt 是否真在**。在的话它是 2 的强力竞争者;不在的话 3 天内放弃。

**5. CondMDI**(https://github.com/setarehc/diffusion-motion-inbetweening,MIT)—— body/wrist 轨迹层的补洞。不碰手指。只在你发现 body 层的 dropout 也很严重时才上。

**6. Dyn-HaMR**(https://github.com/ZhengdiYu/Dyn-HaMR)—— **不是当 infiller 用,是当噪声标定器用**。跑在有 GT 的 ARCTIC/HOT3D 序列上,量 residual,拿到真实的 Tier 3 误差分布,再用它生成你自己的 Tier 2 corruption。**这一步能让你的 corruption 模型比官方描述更准**。

**不做**:SinMDM(要 per-sequence 训)、MoMask(要 text)、T2M-GPT(不支持 infilling)、Harvey RMIB(2020 RNN,无官方码)、HandDiffuse(空仓库)、Deformer(无权重且要 RGB)、UniHand / MAD-HOI / SILK / Less is More(全部无码)。

## (b) 物体 6-DoF 补洞 —— 排序

**1. Contact-aware 刚性外推** —— 接触期间物体位姿 = 手腕位姿 × 抓取瞬间的相对变换。这比任何生成模型都准,因为接触期间刚性约束是物理事实。用 V2D 已有的 contact label 做分段。**这是 (b) 里最重要的一条,别跳过**。

**2. SE(3) Kalman + RTS smoother** —— 自由段用 constant-velocity/acceleration,R³ 上标准 Kalman,SO(3) 上用 error-state / Lie-algebra 形式。静置段 hold last pose,配 V2D 的 `reconstruct_support_surfaces.py` 加平面约束。RoHM 那个"TrajNet 刻意不吃速度以避免 drift"的经验教训在这里要反着用:短洞用速度,长洞退化成位置插值。

**3. 从 FoundationPose 失败模式建噪声模型** —— **burst dropout(mask 丢) + 低频 drift(伪 tracking 累积)**,不是 i.i.d. 高斯。FoundationPose 在 5Hz 严重退化这条,意味着 Tier 3 里帧率低的段落质量会显著更差,可以当作一个可检测的信号。结合 BOP 2024 那个"unseen object 2D detection 落后 35%,是主要瓶颈"的结论:遮挡下真正丢的是 mask,不是 pose 精度。**所以你的 dropout mask 生成器应该由 SAM2 mask IoU / 面积突变驱动,而不是随机 drop**。

**4. HOT3D 的 `mask_object_visible`** —— 直接统计真实遮挡段的长度分布、频率、与接触事件的相关性,拿来标定 Tier 2。https://github.com/facebookresearch/hot3d

**5. 不确定性传播** —— PoseRBPF 的粒子滤波思路(https://github.com/NVlabs/PoseRBPF,NVIDIA 非商用)。遮挡期间输出的不该是点估计而是分布,给 policy 一个"这帧我不确定"的信号。不用跑它的代码,自己在 Kalman 里带协方差就行。

**不做**:FoundationPose++ 的 amodal completion(没放出来)、FreeZe(实现未确认释出)、GenFlow(repo 找不到)、se(3)-TrackNet / BundleTrack / DOPE(全停更或需 per-object 训练)、ProxyPose(2026-07,太新)。ICG/M3T(https://github.com/DLR-RM/3DObjectTracking,MIT,真实时)如果你有 C++ 人力可以当 refiner,否则跳过。

---

## 三个需要立刻确认的事

1. **HaWoR 的 CC-BY-NC-ND 在比赛提交语境下算不算 distribute derivative**。这决定 (a) 的第 2 项能不能上。
2. **HandX 的生成模型 ckpt 是否真的放出来了**(数据集确认放了,模型权重 README 没写死)。clone 一下就知道。
3. **"CHORD manuscript" 在哪**。AUC / SP-SR / MP-SR / MPPE 的精确定义决定了你该优化什么 —— 如果 SR 是 success rate 且按序列算,那么"一段里有几帧编得不准"可能完全不影响分数,整个 infilling 的投入就要重新权衡。直接发 v2d_challenge@nvidia.com。

Sources:
- https://nvidia-isaac.github.io/video_to_data/v2d_challenge/
- https://github.com/nvidia-isaac/video_to_data
- https://github.com/ThunderVVV/HaWoR
- https://arxiv.org/abs/2501.02973
- https://github.com/setarehc/diffusion-motion-inbetweening
- https://arxiv.org/abs/2405.11126
- https://github.com/GuyTevet/motion-diffusion-model
- https://github.com/priorMDM/priorMDM
- https://github.com/SinMDM/SinMDM
- https://github.com/sanweiliti/RoHM
- https://arxiv.org/html/2401.08570v2
- https://github.com/enesduran/HMP
- https://github.com/ZhengdiYu/Dyn-HaMR
- https://github.com/NVlabs/ProtoMotions
- https://nvlabs.github.io/ProtoMotions/getting_started/pretrained_models.html
- https://arxiv.org/abs/2409.14393
- https://github.com/handx-project/HandX
- https://arxiv.org/abs/2603.28766
- https://github.com/HandDiffuse/HandDiffuse
- https://github.com/fuqichen1998/Deformer
- https://arxiv.org/abs/2602.21631
- https://arxiv.org/abs/2608.10162
- https://arxiv.org/abs/2606.30308
- https://github.com/victorqin/motion_inbetweening
- https://github.com/boreshkinai/delta-interpolator
- https://github.com/jihoonerd/Conditional-Motion-In-Betweening
- https://github.com/ubisoft/ubisoft-laforge-animation-dataset
- https://github.com/EricGuo5513/momask-codes
- https://github.com/OpenMotionLab/MotionGPT
- https://github.com/NVlabs/FoundationPose
- https://github.com/teal024/FoundationPose-plus-plus
- https://github.com/NVlabs/BundleSDF
- https://github.com/facebookresearch/sam2
- https://github.com/ammar-n-abbas/FoundationPoseROS2
- https://github.com/IRVLUTD/FoundationPoseROS
- https://github.com/taeyeopl/Any6D
- https://github.com/DLR-RM/3DObjectTracking
- https://arxiv.org/abs/2504.02812
- https://bop.felk.cvut.cz/challenges/bop-challenge-2025/
- https://github.com/facebookresearch/hot3d
- https://github.com/NVlabs/dex-ycb-toolkit
- https://github.com/zc-alexfan/arctic
- https://github.com/leolyliu/TACO-Instructions
- https://arxiv.org/abs/2607.06555
