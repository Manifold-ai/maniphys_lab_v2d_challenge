"""G1 参考的 palm 坐标帧与关节 FK 之间的偏差：逐帧回放 vs 按真实时长重采样（在 FlashCHORD 容器里执行，占一点 GPU）。

上游 G1 在绑定参考时逐帧要求：参考里的 palm 位置 / 朝向与由参考关节角做 FK 得到的手腕位姿相差 ≤ 1e-4 m / 1e-4 rad
（embodiments/g1_dex3.py 的 _validate_palm_frames，G1Dex3Config.frame_position_tolerance / frame_orientation_tolerance），
不区分插值帧。按真实时长回放时关节角与 palm 位置各自线性插值，FK 与插值结果不再逐位一致，校验失败（回放速度对照冒烟的报错）。
这里把校验换成只记录，两种回放各建一次场景（1 个世界），报出每只手的最大偏差与所在帧，用来定放宽后的容差。
用法（仓库根）：scripts/dev/in-flash-chord "python /repo/stages/policy/palm_frame_probe.py <容器内 parquet 路径>"
"""
import argparse

import numpy as np
import warp as wp
from hydra import compose, initialize_config_dir

import flash_chord.embodiments.g1_dex3 as g1
from flash_chord.configuration import instantiate_typed
from flash_chord.embodiments.base import Embodiment
from flash_chord.envs.rl import RLEnvConfig
from flash_chord.scene.collision import CollisionPolicy
from flash_chord.scene.setup import setup_scene

CONFIG_DIR = "/workspace/src/flash_chord/configs"
RECORDED = []


def record_palm_frames(binding, reference, config) -> None:
    """与上游 _validate_palm_frames 同样的误差算法，只记录、不抛错。"""
    names = tuple(reference.robot_frame_names())
    index = {name: i for i, name in enumerate(names)}
    pos = np.asarray(reference.robot_frame_pos_w(), dtype=np.float64)
    quat = np.asarray(reference.robot_frame_quat_w(), dtype=np.float64)
    for side in ("left", "right"):
        name = f"{side}_hand_palm_link"
        hand = binding.hand(side)
        pe = np.linalg.norm(np.asarray(hand.wrist_pos_w, dtype=np.float64) - pos[:, index[name]], axis=1)
        qa = np.asarray(hand.wrist_quat_w, dtype=np.float64)
        qe = quat[:, index[name]].copy()
        qa /= np.linalg.norm(qa, axis=1, keepdims=True)
        qe /= np.linalg.norm(qe, axis=1, keepdims=True)
        oe = 2.0 * np.arccos(np.clip(np.abs(np.sum(qa * qe, axis=1)), -1.0, 1.0))
        RECORDED.append((name, pe, oe, config.frame_position_tolerance, config.frame_orientation_tolerance))


def probe(parquet: str, frame_playback: bool) -> None:
    overrides = ["experiment=g1_recon_body_flash_sac", f"task.parquet='{parquet}'", "scene.world_count=1",
                 f"task.source_frame_playback={str(frame_playback).lower()}"]
    with initialize_config_dir(version_base="1.3", config_dir=CONFIG_DIR):
        cfg = compose(config_name="train_flash_sac", overrides=overrides)
    env_config = instantiate_typed(cfg.env, RLEnvConfig)
    embodiment = instantiate_typed(cfg.embodiment, Embodiment)
    collision = instantiate_typed(cfg.collision, CollisionPolicy)
    RECORDED.clear()
    with wp.ScopedDevice("cuda:0"):
        setup = setup_scene(
            parquet=cfg.task.parquet, control_fps=env_config.sim.fps, motion_speed=cfg.task.motion_speed,
            embodiment=embodiment, collision=collision, world_count=1, include_support=cfg.scene.support,
            decompose_objects=cfg.scene.decompose_objects, object_scale_min=cfg.scene.object_scale_min,
            object_scale_max=cfg.scene.object_scale_max, object_scale_seed=cfg.scene.object_scale_seed,
            contact_friction=cfg.scene.get("contact_friction", 1.0),
            object_free_joint_damping=cfg.scene.get("object_free_joint_damping", 0.0),
            source_frame_playback=frame_playback, motion_start_frame=int(cfg.task.motion_start_frame),
            motion_end_frame=int(cfg.task.motion_end_frame),
        )
    ref = setup.reference
    print(f"== source_frame_playback={frame_playback}: {ref.num_frames} frames, is_resampled {ref.metadata.is_resampled}")
    for name, pe, oe, pt, ot in RECORDED:
        print(f"  {name}: position max {pe.max() * 1000:.4f} mm (frame {int(pe.argmax())}), p99 {np.percentile(pe, 99) * 1000:.4f} mm; "
              f"orientation max {oe.max():.3e} rad (frame {int(oe.argmax())}), p99 {np.percentile(oe, 99):.3e} rad; "
              f"upstream tolerances {pt:g} m / {ot:g} rad")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("parquet")
    a = ap.parse_args()
    g1._validate_palm_frames = record_palm_frames   # 只在本进程里替换，上游源码不动
    probe(a.parquet, frame_playback=True)
    probe(a.parquet, frame_playback=False)


if __name__ == "__main__":
    main()
