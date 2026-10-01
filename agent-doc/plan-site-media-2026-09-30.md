# 计划：SOP 页面加任务参考动画，任务名统一用英文（2026-09-30）

时间一律丹佛时间（MDT）。用户 9/30 17:4x 的要求原文：“任务名称都写成英文 同时在SOP中加一些标准参考的动画gif或者视频去帮读者助理解任务”。

## 已核实的事实（probe，9/30 18:28–18:36）

- 数据：Tier 1 的 exo 相机视频在 mf4090 `data/challenge/track_2/tier_1_multiview_caption/videos/chunk-000/observation.images.exo_camera/episode_0000NN.mp4`，30 条，H.264、1536×1152、30 fps，共 655 MB；数据集 README 说这一路视频在三档之间逐字节相同。
  `meta/episodes.jsonl` 每条带官方英文任务描述（例：ep0 “Walk over to the tall bar stool and using both hands, tip the stool …”）。
- 编码：宿主机没有 ffmpeg；`flash_chord:latest` 与 `robotic-grounding:latest` 镜像里都有 imageio_ffmpeg 自带的 ffmpeg 7.0.2。
- G1 参考回放：FlashCHORD `scripts/debug/replay.py --config-name=sonic_replay`（零残差动作、物理回放，物体由 VOC 按参考牵引）+ `viewer.backend=mp4`（无头 GL 写 MP4）可用，需要
  `PYGLET_HEADLESS=1`（否则 pyglet 找 X display 失败）和 `markers.enabled=false`（标记点绘制在当前 Newton 版本上报类型错误）。默认相机太远，机器人在画外；
  `stages/policy/site_ref_camera.py` 按机器人根节点与物体根节点轨迹的水平包围盒算相机，ep20 渲 553 帧约 73 秒、640×480 文件 220 KB，四帧抽查机器人全程在画面里。
- `replay=kinematic collision=kinematic` 对 G1 不可用：第 150 帧起机器人不在画面里（推测是无碰撞时掉出地面，未查），不用。
- 16 条序列的支撑面文件是空 Xform，FlashCHORD 建不起场景，回放要和训练一样加 `scene.support=false`。
- ep1、ep7、ep28 的方盒支撑面在 v0.4.0 导入器下是 1 m 立方体；`V2D_FC_SRC=/lab_data/rxzhou/v2d/fc_src/v040_p185` 的 #185 副本只在 ml40 上。

## 要做的事

1. 任务名用英文：SOP 页面中文块里出现的物体中文名（电饭煲、熨斗、吸尘器、刮水器等）换成数据集的序列短名（去掉日期前缀，如 `rice_cooker_clockwise_04`），英文块同样用序列短名；口头讲稿同步改。
2. 素材（不进 git：仓库规则“数据集、rollout 录像一律不进 git”，素材放 `runs/site_media/`，已在 .gitignore 范围内）：
   - exo 片段 `exo_epNN.mp4`：全长 2 倍速，缩到 480 宽，H.264 CRF 32，无音轨，faststart；封面 `exo_epNN.jpg`（中间一帧）。
   - G1 参考回放 `ref_epNN.mp4`：sonic_replay 物理回放、640×480、全长、30 fps（逐帧回放时一帧一个源帧，等于实际时长），再转成 2 倍速 CRF 32；封面 `ref_epNN.jpg`。
   - 发散排查页另渲 ep7 一对：v0.4.0 导入器（1 m 立方体）与 #185 副本，ml40 上跑；回放若中途数值出错，就截能渲出来的部分并如实标注。
3. 页面：新加一页 `pg-tasks`“任务一览 / Task gallery”，放在训练实验组最前；每条一张卡：ep、英文序列名、官方英文任务描述（原文照抄）、帧数、支撑面类型、已有判定的 MP-SR（取 `results/batch1/error_table_with_mf4090_b.txt`）、两段视频（`preload="none"`、带封面、静音循环，进入视口才播放）。
   Day 1b（ep20）、第 1 批（ep12 通过与 ep25 失败）、发散排查（ep7 一对）三页内嵌对应片段。
4. 生成脚本进仓库：`stages/evaluate/site_media_exo.sh`、`stages/policy/site_media_ref.sh`（含相机、支撑面开关、转码）、`stages/evaluate/site_task_table.py`（任务表：ep、序列名、官方任务原文、帧数、支撑面、MP-SR → JSON），
   清单经 `scripts/dev/record` 落盘到 `results/site/media_manifest.txt`（文件名、字节数、md5、时长）。
5. `tools/site_check.py` 加 `--media-dir`：页面里每个 `media/...` 引用都要在该目录里存在。发布时用 Artifact 的 `files` 把 `media/` 一起传上去。

## 判据（执行前登记）

- 30 条都有 exo 片段、参考回放与两张封面；单个 exo ≤ 3 MB、参考回放 ≤ 1.5 MB，素材总量 ≤ 60 MB（Artifact 一次发布上限 64 MB）。
- 参考回放逐条抽 4 帧拼图人工看：机器人在画面里、没有明显穿模或飞出；不合格的条目在卡片上如实标注（例如“物理回放中机器人摔倒”），不删、不换别的渲染方式凑数。
- `site_check.py --media-dir runs/site_media` 输出 SITE_OK；`git ls-files` 里没有任何 .mp4 / .jpg 素材。
- 中文块里不再出现物体中文名作 ep 的称呼（按一张中文名清单 grep 为 0）。

## 资源与风险

- GPU：mf4090、ml40 都空闲（9/30 14:35 起），渲染总量估约 30 × 75 s，两台各一半约 20 分钟；放 tmux 跑，写 `runs/.chain-active-sitemedia` 标记，跑完删除。
- 页面变大：视频不内嵌进 HTML，HTML 只多几十 KB；Artifact 里视频按相对路径加载，发布后实开核对一次能否播放。
- 档位隔离：这些是给人看的文档素材，不进入任何 Tier 2 / Tier 3 管线；exo 视频本来三档相同。
- 物理回放不是参考本身：页面写明“G1 用零残差动作物理回放参考，物体由 VOC 牵引”，不当作 policy 效果，也不当作参考可行性的证据。

## 审查与处理（9/30 19:00 前后，独立审查：GO WITH FIXES，无 BLOCKER）——第 2 版

- M1 参考动画改渲运动学参考：上游 `replay.py` 的 "Show kinematic reference" 模式（`step()` 里 `runner.reset(f)`，不跑物理）。新增 `stages/policy/site_ref_replay.py`
  继承 `Replay`、固定 reference 模式、`viewer.realtime=false`，不改上游源码。不再用 sonic_replay 的物理回放（它是 SONIC 零残差闭环，画面里混着控制器的表现）。
  ep7 在 v0.4.0 几何下也就不会因物理炸开，能直接看到物体嵌在 1 m 立方体里。
- M2 ep1、ep7、ep28 的图库动画在 ml40 上挂 `V2D_FC_SRC=/lab_data/rxzhou/v2d/fc_src/v040_p185`（#185 几何）；发散排查页另渲 ep7 的 v0.4.0 版（后缀 `_v040`）。
- M3 可检的判据：wrapper 逐帧记录第 0 个刚体（机器人根）的位姿是否有限与高度，写 `ref_epNN.json`；判据改为“全部帧有限、渲染帧数 = 参考帧数”，
  不满足就从第一帧非有限处截断、不足 30 帧只放封面加文字；每条的 json 汇总进 `results/site/media_manifest.txt`。人工看拼图保留为补充。
  相机改为逐帧跟随（机器人与物体中点、平滑、从机器人在物体附近时的朝向一侧看），避免长距离行走时机器人太小。
- M4 卡片上的 MP-SR 写明“Tier 1、第 1 批（或 Day 2）、逐帧满配、最终 checkpoint、本地 4096 世界”，同时给判定列与来源文件；ep1、ep7、ep28 写“无效，未评”。
- M5 中文名清单（9/30 已执行替换，中文块里 ep 编号后跟中文名的 50 处换成序列短名，单独出现的 16 处换成英文物体名）：电饭煲、熨斗、吸尘器、刮水器、喷瓶、交通锥、白桌子、
  滑板、高脚凳、浇水壶、拉杆箱、行李箱、编织篮、零食盒、复活节篮、咖啡杯、棒球棒、黑色平台、细腿木椅、玩具推车、折梯、显示器、蓝色垃圾桶、箱子、圆桌、“小心地滑”牌、红色大碗、浅蓝色书、手杖、青色水瓶。
  判据：中文块里按这张清单 grep 为 0（“方盒”是支撑面类型，不在清单里）。
- M6 视频播放：发布后在 Chrome 实开核对（Safari 本机无法自动化，标“未测”）；播不了就改成 `fetch` 取回再 `URL.createObjectURL(blob)`。`<video>` 加 `playsinline muted`，`prefers-reduced-motion` 时不自动播放。
- MINOR：素材与任务表改读 tier_2 目录（与 tier_1 逐字节相同），新代码里不出现 Tier 1 路径；转码加 `-map_metadata -1`；页面注明数据集 CC BY 4.0、经重编码与 2 倍速；
  `.gitignore` 加 `docs/site/media/`；超时按容器名 `docker stop`；任务表支撑面 `missing` 时报错；尺寸超限时只调 CRF（32→35）或宽度，不剪长度；
  任务原文照抄并做 HTML 转义（ep14 原文开头多一个引号）；口头讲稿在 scratchpad 的 `talk/talk_final.md`，不进仓库；
  记忆里“看策略用 viewer、不导 mp4”这次是用户点名要视频，作例外；素材经 scp 拉回 Mac 的 `runs/site_media/`，发布到 https://claude.ai/artifact/Y3bxcJt4oMMMrBKAr4fkhj 。
