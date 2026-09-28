"""按官方评测路径跑一次，同时把 rollout 的逐帧数据存成 npz（在 FlashCHORD 容器里跑，占 GPU）。

评测只输出汇总，逐帧诊断需要 rollout 本身。这里照 scripts/evaluate_policy.py 的 main() 组好评测配置、调用
harness.evaluate_checkpoint，只额外包一层 harness.record_object_pose_rollout 与 harness.score_reference_tracking
（harness 在模块顶层导入它们、在 evaluate_checkpoint 里按名字调用），存下 rollout 与任务原生判据。
所以存下的逐帧数据和同一次评测的汇总指标出自同一个 rollout。包装没被调用（上游改了调用方式）就报错退出，
不会悄悄产出空结果。不向 W&B 发布。

用法：python /repo/stages/evaluate/diag_rollout.py <policy.safetensors> <输出前缀> [--worlds 256]
输出：<前缀>.npz（逐帧数据与判据）、<前缀>.json（与 fc_eval 同格式的评测报告）
"""
import argparse
import dataclasses
import json
import sys

import numpy as np

CONFIG_DIR = "/workspace/src/flash_chord/configs"  # scripts/evaluate_policy.py：config_path="../src/flash_chord/configs"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("policy")
    ap.add_argument("out_prefix")
    ap.add_argument("--worlds", type=int, default=256)
    a = ap.parse_args()

    from flash_chord.configuration import instantiate_typed, resolve_path
    from flash_chord.evaluation import harness
    from flash_chord.training.flash_sac.evaluation import EvaluationConfig
    from hydra import compose, initialize_config_dir

    captured = {}
    record, score = harness.record_object_pose_rollout, harness.score_reference_tracking

    def record_wrapper(*args, **kwargs):
        captured["rollout"] = record(*args, **kwargs)
        return captured["rollout"]

    def score_wrapper(rollout, criteria):
        captured["criteria"] = criteria
        captured["tracking"] = score(rollout, criteria)
        return captured["tracking"]

    harness.record_object_pose_rollout = record_wrapper
    harness.score_reference_tracking = score_wrapper

    with initialize_config_dir(config_dir=CONFIG_DIR, version_base="1.3"):
        cfg = compose(config_name="evaluate_policy",
                      overrides=[f"evaluation.checkpoint={a.policy}", f"evaluation.world_count={a.worlds}"])
    evaluation = instantiate_typed(cfg.evaluation, EvaluationConfig)
    outcome = harness.evaluate_checkpoint(
        resolve_path(evaluation.checkpoint),
        world_count=evaluation.world_count,
        start_frame=evaluation.start_frame,
        reset_mode=evaluation.reset_mode,
        motion_start_frame=evaluation.motion_start_frame,
        motion_end_frame=evaluation.motion_end_frame,
        source_root=evaluation.source_root,
    )
    if "rollout" not in captured or "criteria" not in captured:
        print("包装没有被调用：上游不再按名字调用 harness.record_object_pose_rollout / score_reference_tracking",
              file=sys.stderr)
        return 2
    r, c = captured["rollout"], captured["criteria"]
    criteria = dataclasses.asdict(c) if dataclasses.is_dataclass(c) else dict(vars(c))
    np.savez_compressed(
        a.out_prefix + ".npz",
        achieved_pose_w=r.achieved_pose_w,
        reference_pose_w=r.reference_pose_w,
        tracking_error=r.tracking_error,
        tracking_error_names=np.array(r.tracking_error_names),
        control_fps=np.float64(r.control_fps),
        start_frame=np.int64(r.start_frame),
        non_finite_worlds=np.array(r.non_finite_worlds, dtype=np.int64),
        completion_truncated=np.asarray(r.completion.truncated),
        completion_progress=np.asarray(r.completion.reference_progress, dtype=np.float64),
        criteria_json=np.array(json.dumps(criteria)),
        reported_success_rate=np.float64(captured["tracking"].success_rate),
        policy=np.array(str(a.policy)),
        world_count=np.int64(evaluation.world_count),
    )
    report = harness.write_evaluation_report(a.out_prefix + ".json", outcome)
    print(json.dumps(harness.evaluation_scalars(outcome), indent=2, sort_keys=True))
    print(f"rollout: {a.out_prefix}.npz  report: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
