# deploy

GPU 组件的运行环境：Isaac Lab 容器镜像、GPU 机器的准备、凭据注入。

- 镜像是唯一的运行单元，不在宿主机上装环境来跑。
- 官方 toolkit 标注的环境是 Isaac Lab 2.3.1、NVIDIA driver 580.126.09 / CUDA 13.0；
  RTX A6000 与 L40S 验证过，Blackwell 不支持 HOI 重建。以上摘自官方 README，本仓未实测。
- Hugging Face token 等凭据只经环境变量或 stdin 注入。

尚无内容。版本与机器来源待 ADR。
