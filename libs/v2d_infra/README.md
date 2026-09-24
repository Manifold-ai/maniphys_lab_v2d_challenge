# libs/v2d_infra

各环节共用的东西只在这里声明一次：

- 数据集读取：Track 2 各档目录是完整的 LeRobot v2.1 数据集（`meta/`、`data/`、`videos/`、`mesh/`）。
- 档位与 episode 寻址：档位名、目录布局、episode 与全局帧号。
- **档位隔离**：Tier 2 / 3 的读取入口拒绝打开 Tier 1 的干净轨迹（`docs/contracts/data.md`）。
- 环节之间交接产物的 schema：轨迹、坐标系、帧号约定。

不放任何只有一个环节用的逻辑。契约见 [`docs/contracts/data.md`](../../docs/contracts/data.md)。

尚无代码。
