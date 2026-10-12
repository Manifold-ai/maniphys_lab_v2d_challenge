# rxzhou 的训练前门槛（P2′），在我们这边用 CPU 跑

用途：交付一个 Tier 3 版本之前，先用 rxzhou 自己的门槛代码判一遍，不占他的机器和时间。门槛是他的
`stages/retarget/eps.sh`（转换 → v0.4.0 重定向 → 对齐检查）加 `p2_table.py`：重定向后物体静置时
|间隙| ≤ 30 mm 且至少一只手有接触算过，ep29（用脚推）只看间隙。

他在 mf4090 上用 Isaac 镜像 `robotic-grounding:latest` 跑，但默认不占 GPU，重定向只用到 pinocchio / pink /
soma / pxr。这里在一个 py3.11 venv 里装同样的版本，他的代码一行不改，只把 `scripts/dev/incontainer`
换成本目录的同名脚本（不起容器，`/repo` 映射到 checkout）。

## 对照（10-13）

用他 simreg 那轮的三集（ep0/9/15，parquet sha256 与他的记录相同）复跑：间隙、左右手接触帧、IK 中位、
最近的面、状态与他的 `results/t3simreg/retarget17_mf4090.txt` 逐字段相同。环境与镜像的差别只有 numpy
（2.3 对 1.26，pin 3.7.0 的 wheel 要求）。

## 文件

| 文件 | 作用 |
|---|---|
| `setup.sh` | 搭环境：他的某个 commit（stdin 传 tar）、上游 v0.4.0（含 LFS）、SOMA 资产链接、venv |
| `incontainer` | 替换他 checkout 里的 `scripts/dev/incontainer` |
| `mkroot.py` | 从一个版本目录拼他的档目录 `runs/tier3/root_<set>`；地面默认用我们清洗过的 `plane` |
| `run_parallel.sh` | 把没跑完的集分给 W 个 `eps.sh` 并行（nice 10，转换步限 3 线程） |
| `mkrecord.sh` | 把各集结果拼成 `p2_table.py` 要的记录 |
| `t3_support_usda.py` | 我们的支撑面写成 usda（`g1_retarget_world`），交付用，见下 |
| `support_recheck.sh` | 换一套支撑面重判间隙（重定向不读支撑面，不用重跑） |

## 支撑面

Tier 3 不用官方 `support_surface/`：它只在 Tier 1、Tier 2 目录里，Tier 3 没有发布输入（kit `tracks.json`
的 `input_path` 为空），Kaggle 规则 2.8.c 禁止用更容易档位的输入；它的位置也来自干净采集（放在干净物体每次
静止的位置下面，坐标系锚在发布人体的第 0 帧上）。

`t3_support_usda.py` 把 `t3_support.py` 的支撑面换算进重定向的世界系：OpenCV → SOMA 轴、第 0 帧人体根节点
锚定、地面找平、换机器人轴，全用上游函数算（`soma_to_g1.py` 359–466 行），所以文件要和交付的人体数据配套生成。
有这一版的门槛输出时，逐集用同一个变换复算物体第 0 帧位姿并与重定向输出比对，超过 0.1 mm 就拒绝。格式与官方
文件相同：每个支撑面一块不旋转的 Cube 薄板（2 cm 厚，世界系 xy 外接框，顶面在支撑面高度）。

## 用法

```bash
# 搭环境（一次）
git archive <rxzhou commit> libs stages scripts tools third_party | ssh <host> "<本目录>/setup.sh <commit>"
# 一个版本过门槛
python mkroot.py $G/repo <set> - $T/runs/<version>,$T/runs/<version>_suspect
run_parallel.sh <set> 4                      # 结束后各 logs/<set>_w*.txt 有 EPS_DONE
mkrecord.sh <set> > logs/rec_<set>.txt
$G/venv/bin/python $G/repo/stages/retarget/p2_table.py logs/rec_<set>.txt --no-contact 29
# 我们的支撑面
PYTHONPATH=$G/repo/third_party/video_to_data/robotic_grounding/source/robotic_grounding \
  $G/venv/bin/python t3_support_usda.py $G/repo <set> $T/runs/support/<support version> $T <out dir>
support_recheck.sh <set> <out dir>
```
