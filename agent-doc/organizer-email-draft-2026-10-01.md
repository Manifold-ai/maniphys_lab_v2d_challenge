# 给组委会的邮件草稿（2026-10-01，第 2 版，由用户发送）

收件：v2d_challenge@nvidia.com
主题：Track 2 (Robotic Grounding): private repository, Tier 3 input, and a few rule questions

第 2 版（10/1 16:30 UTC-6）相对第 1 版的改动，依据 `agent-doc/decision-organizer-q1-q3-2026-10-01.md`：
- 删去“方盒支撑面用哪个运行时”：组委会 10/1 13:40 的新 kit 已把运行时钉到 8c778f9（含 #185）；
- 删去“世界被判终止就报错”：读代码加 96 份评测的统计，这只在数值发散时发生，不是规则问题；
- “空支撑面”降成一句告知；
- 新增：代码发布的时间与范围、Tier 3 输入会不会发布、Kaggle 队伍怎么登记。

依据：
- commit URL 与获奖资格：kit README “Provide a GitHub commit URL for the code that produced each submission”；
  官网 “Eligibility for all awards: a valid final submission, agreed code release (research license), and the short technical report.”
- Tier 3：新 kit `tracks/track_2/README.md` 的表列出 `track_2/tier_3_cari4d/`；HF 数据集 `track_2` 下只有 Tier 1、Tier 2（10/1 查）。
- 空支撑面：`results/day2/empty_support_tier1.txt`、`results/t2/support_kinds_tier2_mf4090.txt`（两档各 16 条）。
- Kaggle：`submit/v2d_submit.py` 文件头（总榜按 Kaggle 身份合并各比赛的成绩）。

还没定要不要加的一问：Tier 2 用自己降噪后的参考训练时，打包该不该加 `--frame-references`。先读新打包器的代码再定。
发送前 rxzhou 填署名与队名；用户 10/1 说邮件先不急，10/7 12:00（UTC-6）的参赛说明会也可以当面问。

---

Dear V2D Challenge organizers,

Thank you for the updated submission kit, and for pinning the runtime to 8c778f9: that resolved the box support surface problem we were about to report. We are a Track 2 (Robotic Grounding) team training G1 + Dex3 policies with FlashCHORD, and we have a few questions.

1. **Code commit URL and code release.** The kit asks for a GitHub commit URL for the code behind each submission, and award eligibility requires an agreed code release under a research license. Our repository is private during the challenge.
   - Is a commit URL in a private repository acceptable, with read access granted to the organizers on request?
   - May the code release happen after the leaderboard freeze, and may it cover the training and evaluation pipeline without our internal notes?

2. **Tier 3 input.** The Track 2 guide in the kit lists `track_2/tier_3_cari4d/` as the released Tier 3 input, but the dataset on Hugging Face currently has only the Tier 1 and Tier 2 folders. Will a Tier 3 input be released, and when? May teams use their own reconstruction from the exo video instead?

3. **Repeated evaluation.** Each submission uses one deterministic rollout per episode, and we see small differences between repeated evaluations of the same checkpoint. May a team evaluate a checkpoint more than once before packing a submission, or should each submission come from a single evaluation run?

4. **Teams on Kaggle.** Is it enough for one team member to join the Kaggle competitions and submit, with the full team listed in the registration form, or should every member join and merge into one Kaggle team?

5. **Other rules.**
   - May Tier 1 data be used during development to validate methods intended for Tiers 2 and 3?
   - May a policy trained on one tier be used to warm-start training on another?
   - May Track 1 or Track 3 data be used for Track 2?

One note in case it is useful: for 16 of the 30 sequences, in both Tier 1 and Tier 2, the provided `*_support.usda` contains only an empty Xform, and FlashCHORD cannot build the scene with support enabled ("support surface contains no Cylinder or Cube collision shapes"). We train these floor-only sequences with `scene.support=false`. Please tell us if that is not the intended handling.

Thank you very much for organizing the challenge.

Best regards,
[name / team]
