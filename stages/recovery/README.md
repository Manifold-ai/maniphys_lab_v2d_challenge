# stages/recovery

Tier 2 / Tier 3 的轨迹恢复：从带噪轨迹（Tier 2）或 exo 视频（Tier 3）估出更好的人体与
物体轨迹，按 `libs/v2d_infra` 的 schema 落盘，交给 `retarget`。Tier 1 不经过这一段。

**这一段不得读取 Tier 1 的干净轨迹**，包括作为监督信号、校准参考或验证集。

Tier 2 的扰动类型（抖动、丢帧、接触错误）按 Track 1 的误差分布采样；Tier 3 的参考
方案是 CARI4D。方法选型待 ADR。

尚无代码。契约见 [`docs/contracts/recovery.md`](../../docs/contracts/recovery.md)。
