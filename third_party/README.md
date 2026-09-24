# third_party

官方 starter toolkit [nvidia-isaac/video_to_data](https://github.com/nvidia-isaac/video_to_data/tree/release/0.2.0/)
的接入位。Track 2 相关的部分在其 `robotic_grounding/`。

接入方式（git submodule、固定 commit 的本地 checkout，或按需拷贝）待 ADR 定。在那之前，
本地 checkout 放在 `third_party/video_to_data/`，已被 `.gitignore` 排除。

官方代码不改源码。确需修改时以补丁文件放在这里，文件名或开头注明上游版本与修改理由。
