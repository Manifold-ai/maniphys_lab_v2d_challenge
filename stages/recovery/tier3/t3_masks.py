"""Tier 3 (Track 2 exo videos) -> SAM2 masks for CARI4D. Copied from the Track 1 t1_masks2.py; changes:
reads the Tier 3 input layout, builds the detector prompt from the object name (Track 2 metadata has no
object_prompt), refuses Tier 1 paths, and never asks for a manual prompt: Kaggle Foundational Rule 4.b
forbids hand labeling of test data, so an episode without an automatic prompt fails with NO_AUTO_PROMPT.

Track 1 notes, second version: choose the prompt frame, do not trust frame 0.

Why v2: in ep06 the frame-0 Grounding DINO box for "an metallic iron" covered the whole round table the
iron was resting on (confidence 0.50), SAM2 segmented the table, and CARI4D then tracked a table with an
iron mesh and still reported PASS. Nothing in the pipeline noticed. This version

  1. runs Grounding DINO on a handful of frames spread over the clip with the prompt
     "person . <object_prompt> . table . desk .";
  2. scores every object box: confidence x (1 - IoU with the best table/desk box) x a penalty when the
     box covers more than 12% of the frame, and takes the best frame as the SAM2 prompt frame
     (SAM2 propagates both ways from any frame);
  3. after SAM2, checks the object mask is the manipulated object and not a support or a background
     thing: it touches the person mask on some sampled frame; on the prompt frame its box agrees with the
     detector's object box and is not a detected table/desk box; and it does not grow far past its
     prompt-frame size (SAM2 leaking onto a support). Tier 3 changes: the Track 1 rule "the mask leaves its
     first-frame footprint" rejected in-place manipulation (rice_cooker_clockwise_04) and "the mask is larger
     than the person" rejected big objects near the camera (big_black_box), so footprint, travel and the
     object/person ratio are reported only. Failures leave a MASK_SUSPECT file
     and still write overlays for diagnosis (they never feed back into a Tier 3 episode by hand);
  4. re-prompts SAM2 where it lost the object: a run of at least GAP_MIN_FRAMES empty object masks is probed
     with the detector, and a detection near where the object was before/after the run is added as another
     object prompt (ep01: SAM2 dropped a clearly visible vacuum for frames 582-642). A run with no such
     detection is left empty: it is treated as real occlusion;
  5. re-prompts SAM2 where it kept only part of the object: a confident detector box that holds the mask but is
     more than twice its size is added as another object prompt (ep14: the mask held the round table's top only);
  6. packs the H5 CARI4D reads, with the human mask minus the object mask: a held object is not an occluder
     (ep03: 96% of the mug's pixels sat inside the human mask, so FoundationPose saw no object).

Runs on the L40S from the host venv (official docker wrappers). Idempotent per stage. Paths under --work.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "libs" / "v2d_infra"))
from tier_guard import forbid_tier1

PERSON = "person"
SUPPORT_WORDS = ("table", "desk")
BIG_BOX_FRACTION = 0.12
#: The manipulated object is at the person's hands: a candidate's score decays with its gap to the person
#: box, in units of the person box height (ep06: a tripod leg 0.5 m right of the person outscored the iron).
NEAR_PERSON_SCALE = 0.25
#: Reported only (Tier 3): share of the object mask outside its dilated first-frame footprint. Track 1 failed
#: masks below 0.5, which also rejects in-place rotation; the touch test replaces it. Known gap: a static
#: thing the person walks in front of touches the person mask in 2D too (Track 1 ep06 tripod); the prompt
#: scoring (static-box and near-person penalties) is what keeps those out.
FOOTPRINT_DILATE_PX = 21
#: Two boxes on different frames at IoU above this are "the same place".
STATIC_IOU = 0.7
#: The manipulated object is touched: on some sampled frame its mask comes within this many pixels of the
#: person mask. A tripod or a background chair never does.
TOUCH_PX = 15
#: A run of at least this many consecutive empty object masks is probed for a lost object.
GAP_MIN_FRAMES = 15
GAP_PROBES = 5
#: A gap detection must lie within this many object-box diagonals of the object's last/next mask centroid.
GAP_NEAR_DIAGONALS = 2.0
#: Bump when the packed H5 changes meaning: 2 = human mask minus object mask.
PACK_VERSION = 2
#: The object mask's box overlapping a detected table/desk box above this IoU is a support, not the object.
SUPPORT_MASK_IOU = 0.5
#: On the prompt frame SAM2 was given the detector's object box; its mask box must agree with it at least this much.
PROMPT_BOX_IOU = 0.5
#: A mask that exceeds this multiple of its prompt-frame area on most sampled frames has leaked onto something.
MAX_GROWTH = 4.0
#: Incomplete mask: on a detector frame, a confident object box that holds the mask's box (at least
#: COMPLETE_INSIDE of it) while the mask's box covers less than COMPLETE_RATIO of the object box. SAM2 kept a part
#: (ep14: the round table's top, without its post and base, so the silhouette gate failed a correct pose).
COMPLETE_CONF = 0.4
COMPLETE_INSIDE = 0.9
COMPLETE_RATIO = 0.5


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def n_frames(video: Path) -> int:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(video)],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return int(out)


def extract(video: Path, idx: int, out: Path) -> None:
    if not out.exists():
        run(["ffmpeg", "-loglevel", "error", "-y", "-noautorotate", "-i", str(video), "-vf", f"select=eq(n\\,{idx})", "-frames:v", "1", str(out)])


def label_matches(label: str, want: str) -> bool:
    key = {w for w in want.lower().replace(".", " ").split() if len(w) > 2}
    return bool(set(label.lower().split()) & key)


def iou(a: dict, b: dict) -> float:
    x0, y0 = max(a["x0"], b["x0"]), max(a["y0"], b["y0"])
    x1, y1 = min(a["x1"], b["x1"]), min(a["y1"], b["y1"])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    area = lambda r: (r["x1"] - r["x0"]) * (r["y1"] - r["y0"])
    return inter / (area(a) + area(b) - inter + 1e-9)


def detections(path: Path) -> list[dict]:
    dets = json.loads(path.read_text())
    return dets if isinstance(dets, list) else dets.get("detections", dets.get("0", []))


def choose_prompt_frame(d: Path, video: Path, total: int, object_prompt: str, weights: str, thr: float, samples: int,
                        object_name: str = "", frames: list[int] | None = None) -> dict:
    """Detect on `samples` frames (or the given ones), return the best (frame, object box, person box) with all candidates."""
    if frames is None:
        frames = sorted({round(k * (total - 1) / (samples - 1)) for k in range(samples)})
    # The dataset's short object name is a phrase of its own: the descriptive prompt alone can pull the
    # detector elsewhere ("an metallic iron" boxed metal tripods in ep06, never the iron).
    name = object_name.replace("_", " ").strip()
    want = f"{object_prompt} {name}"
    # When the object itself is a table or desk (white_desk), those words are the target, not a support to avoid.
    support_words = tuple(w for w in SUPPORT_WORDS if w not in want.lower().split())
    prompt = f"{PERSON} . {object_prompt.rstrip('.')} . " + (f"{name} . " if name else "") + " . ".join(support_words) + " ."
    candidates = []
    for idx in frames:
        img = d / f"frame_{idx:06d}.png"
        extract(video, idx, img)
        boxes = d / f"boxes_{idx:06d}.json"
        if not boxes.exists():
            run([sys.executable, "-m", "v2d.grounding_dino.docker.run_image_to_object_bboxes",
                 "--image_path", str(img), "--output_path", str(boxes), "--prompt", prompt,
                 "--model_dir", f"{weights}/gdino", "--box_threshold", str(thr)])
        dets = detections(boxes)
        w, h = Image.open(img).size
        persons = [x for x in dets if label_matches(x["label"], PERSON)]
        supports = [x for x in dets if any(label_matches(x["label"], s) for s in support_words)]
        objects = [x for x in dets if label_matches(x["label"], want) and x not in persons and x not in supports]
        person = max(persons, key=lambda x: x["confidence"], default=None)
        for o in objects:
            b = o["box"]
            frac = (b["x1"] - b["x0"]) * (b["y1"] - b["y0"]) / (w * h)
            overlap = max((iou(b, s["box"]) for s in supports), default=0.0)
            near = 1.0
            if person is not None:
                pb = person["box"]
                gap_x = max(0.0, max(pb["x0"] - b["x1"], b["x0"] - pb["x1"]))
                gap_y = max(0.0, max(pb["y0"] - b["y1"], b["y0"] - pb["y1"]))
                near = 1.0 / (1.0 + ((gap_x**2 + gap_y**2) ** 0.5) / (NEAR_PERSON_SCALE * (pb["y1"] - pb["y0"])))
            score = o["confidence"] * (1.0 - overlap) * (0.3 if frac > BIG_BOX_FRACTION else 1.0) * near
            candidates.append({"frame_index": idx, "confidence": o["confidence"], "label": o["label"], "box": b,
                               "box_fraction": round(frac, 4), "support_iou": round(overlap, 3), "near_person": round(near, 3), "score": round(score, 4),
                               "person_box": person["box"] if person else None, "support_boxes": [s["box"] for s in supports]})
    # A static thing is detected at the same place on nearly every sampled frame; the manipulated object
    # is not (it gets picked up). Penalise each candidate by how many OTHER frames have a box at its place.
    # ep06: three metal tripods scored 0.44-0.51 on all frames; the iron itself was boxed only while held.
    for c in candidates:
        same = {o["frame_index"] for o in candidates if o["frame_index"] != c["frame_index"] and iou(o["box"], c["box"]) > STATIC_IOU}
        c["static_frames"] = len(same)
        c["score"] = round(c["score"] / (1.0 + len(same)), 4)
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return {"candidates": candidates, "frames": frames}


def dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    """Square dilation (same footprint as PIL's MaxFilter(2r+1), which took seconds per 1536x1152 frame)."""
    import cv2

    return cv2.dilate(mask.astype(np.uint8), np.ones((2 * radius + 1, 2 * radius + 1), np.uint8)) > 0


def mask_box(mask: np.ndarray) -> dict:
    ys, xs = np.nonzero(mask)
    return {"x0": float(xs.min()), "y0": float(ys.min()), "x1": float(xs.max() + 1), "y1": float(ys.max() + 1)}


def load_mask(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("L")) > 0


def object_gaps(masks: Path, total: int) -> list[tuple[int, int]]:
    """Runs [start, end] of at least GAP_MIN_FRAMES frames whose object mask is empty."""
    empty = [not load_mask(masks / "1" / f"{i:06d}.png").any() for i in range(total)]
    runs, start = [], None
    for i, e in enumerate([*empty, False]):
        if e and start is None:
            start = i
        elif not e and start is not None:
            if i - start >= GAP_MIN_FRAMES:
                runs.append((start, i - 1))
            start = None
    return runs


def gap_prompts(d: Path, video: Path, masks: Path, total: int, gaps: list[tuple[int, int]], object_prompt: str,
                object_name: str, weights: str, thr: float) -> list[dict]:
    """One extra object prompt per gap where the detector finds the object near its last/next known place."""
    found = []
    for a, b in gaps:
        anchors = []
        for j in (a - 1, b + 1):
            if 0 <= j < total:
                m = load_mask(masks / "1" / f"{j:06d}.png")
                if m.any():
                    box = mask_box(m)
                    anchors.append((np.array([(box["x0"] + box["x1"]) / 2, (box["y0"] + box["y1"]) / 2]),
                                    float(np.hypot(box["x1"] - box["x0"], box["y1"] - box["y0"]))))
        if not anchors:
            continue
        probes = sorted({round(a + k * (b - a) / (GAP_PROBES - 1)) for k in range(GAP_PROBES)})
        pick = choose_prompt_frame(d / "detect", video, total, object_prompt, weights, thr, GAP_PROBES,
                                   object_name=object_name, frames=probes)
        for c in pick["candidates"]:
            centre = np.array([(c["box"]["x0"] + c["box"]["x1"]) / 2, (c["box"]["y0"] + c["box"]["y1"]) / 2])
            if any(np.linalg.norm(centre - p) <= GAP_NEAR_DIAGONALS * diag for p, diag in anchors):
                found.append({"gap": [a, b], "frame_index": c["frame_index"], "box": c["box"], "confidence": c["confidence"]})
                break
    return found


def completion_prompts(masks: Path, candidates: list[dict]) -> list[dict]:
    """Detector boxes that hold an incomplete object mask on their frame (see COMPLETE_RATIO), as extra object prompts."""
    found = []
    for c in candidates:
        if c["confidence"] < COMPLETE_CONF:
            continue
        m = load_mask(masks / "1" / f"{c['frame_index']:06d}.png")
        if not m.any():
            continue
        mb, b = mask_box(m), c["box"]
        inter = max(0.0, min(mb["x1"], b["x1"]) - max(mb["x0"], b["x0"])) * max(0.0, min(mb["y1"], b["y1"]) - max(mb["y0"], b["y0"]))
        area_m = (mb["x1"] - mb["x0"]) * (mb["y1"] - mb["y0"])
        area_b = (b["x1"] - b["x0"]) * (b["y1"] - b["y0"])
        if area_m > 0 and inter / area_m >= COMPLETE_INSIDE and area_m / area_b < COMPLETE_RATIO:
            found.append({"frame_index": c["frame_index"], "box": b, "confidence": c["confidence"],
                          "mask_over_box": round(area_m / area_b, 3)})
    return found


def pack_human_minus_object(masks: Path) -> Path:
    """Human mask minus object mask, so a held object is not counted as occluded by the hand holding it."""
    out = masks.parent / "sam2_masks_human_minus_object"
    out.mkdir(exist_ok=True)
    for hp in sorted((masks / "0").glob("*.png")):
        op = masks / "1" / hp.name
        human = load_mask(hp)
        if op.exists():
            human &= ~load_mask(op)
        Image.fromarray(human.astype(np.uint8) * 255).save(out / hp.name)
    return out


def check_masks(masks: Path, total: int, width: int, prompt_frame: int, object_box: dict, support_boxes: list[dict]) -> dict:
    """Touched by the person; on the prompt frame it is the detected object and not a support; no leak."""
    pm = masks / "1" / f"{prompt_frame:06d}.png"
    prompt_mask = np.asarray(Image.open(pm).convert("L")) > 0 if pm.exists() else np.zeros((1, 1), bool)
    if not prompt_mask.any():
        return {"ok": False, "why": f"object mask empty on the prompt frame {prompt_frame}"}
    prompt_area = float(prompt_mask.sum())
    centroids, ratios, outside, touched, growth = [], [], [], [], []
    footprint = None
    for idx in range(0, total, max(1, total // 40)):
        op, pp = masks / "1" / f"{idx:06d}.png", masks / "0" / f"{idx:06d}.png"
        if not op.exists():
            continue
        obj = np.asarray(Image.open(op).convert("L")) > 0
        if obj.sum() == 0:
            continue
        if footprint is None:
            footprint = dilate(obj, FOOTPRINT_DILATE_PX // 2)
        outside.append(float((obj & ~footprint).sum()) / float(obj.sum()))
        growth.append(float(obj.sum()) / prompt_area)
        ys, xs = np.nonzero(obj)
        centroids.append((float(xs.mean()), float(ys.mean())))
        if pp.exists():
            person = np.asarray(Image.open(pp).convert("L")) > 0
            ratios.append(float(obj.sum()) / max(1.0, float(person.sum())))
            near = dilate(person, TOUCH_PX)
            touched.append(bool((near & obj).any()))
    if not centroids:
        return {"ok": False, "why": "object mask empty on every sampled frame"}
    cx = [c[0] for c in centroids]
    cy = [c[1] for c in centroids]
    travel = max(max(cx) - min(cx), max(cy) - min(cy)) / width
    problems = []
    left_share = max(outside) if outside else 0.0
    touch_share = float(np.mean(touched)) if touched else 0.0
    if touch_share == 0.0:
        problems.append(f"object mask never comes within {TOUCH_PX}px of the person on {len(touched)} sampled frames")
    mbox = mask_box(prompt_mask)
    prompt_iou = iou(mbox, object_box)
    if prompt_iou < PROMPT_BOX_IOU:
        problems.append(f"object mask box disagrees with the detector box on the prompt frame (IoU {prompt_iou:.2f})")
    support_iou = max((iou(mbox, b) for b in support_boxes), default=0.0)
    if support_iou > SUPPORT_MASK_IOU:
        problems.append(f"object mask box overlaps a detected table/desk box at IoU {support_iou:.2f} on the prompt frame")
    grown = float(np.mean([g > MAX_GROWTH for g in growth])) if growth else 0.0
    if grown > 0.5:
        problems.append(f"object mask exceeds {MAX_GROWTH:g}x its prompt-frame area on {grown:.0%} of sampled frames")
    return {"ok": not problems, "why": "; ".join(problems), "touch_share": round(touch_share, 3), "prompt_box_iou": round(prompt_iou, 3),
            "support_iou": round(support_iou, 3), "growth_median": round(float(np.median(growth)), 3) if growth else None,
            "travel_fraction": round(travel, 4), "max_outside_share": round(left_share, 3),
            "object_over_person_median": round(float(np.median(ratios)), 3) if ratios else None}


def overlay(video: Path, masks: Path, idx: int, out: Path) -> None:
    tmp = out.with_suffix(".frame.png")
    extract(video, idx, tmp)
    f = Image.open(tmp).convert("RGB")
    a = np.asarray(f).copy()
    m = np.asarray(Image.open(masks / "1" / f"{idx:06d}.png").convert("L")) > 0
    pm = np.asarray(Image.open(masks / "0" / f"{idx:06d}.png").convert("L")) > 0
    a[m] = (a[m] * 0.4 + np.array([255, 0, 0]) * 0.6).astype("uint8")
    a[pm & ~m] = (a[pm & ~m] * 0.6 + np.array([0, 0, 255]) * 0.4).astype("uint8")
    ys, xs = np.nonzero(m | pm)
    if len(xs):
        box = (max(0, xs.min() - 60), max(0, ys.min() - 60), min(f.width, xs.max() + 60), min(f.height, ys.max() + 60))
        Image.fromarray(a).crop(box).save(out)
    else:
        Image.fromarray(a).save(out)
    tmp.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Tier 3 input dir: videos/, meta/")
    ap.add_argument("--work", required=True)
    ap.add_argument("--weights", required=True, help="dir holding gdino/ and sam2/ weights")
    ap.add_argument("--episodes", default="", help="comma list; default all")
    ap.add_argument("--box-threshold", type=float, default=0.3)
    ap.add_argument("--samples", type=int, default=13, help="frames to run the detector on")
    ap.add_argument("--recheck", action="store_true", help="re-run the self-check on episodes already packed (reuses cached detections, masks and h5)")
    args = ap.parse_args()
    forbid_tier1()
    inp, work = Path(args.input), Path(args.work)
    for p in (inp, work, Path(args.weights)):
        if "tier_1" in str(p.resolve()):
            raise SystemExit(f"refusing a Tier 1 path: {p}")
    meta = [json.loads(l) for l in (inp / "meta/episodes_metadata.jsonl").read_text().splitlines()]
    wanted = {int(e) for e in args.episodes.split(",") if e} or {m["episode_index"] for m in meta}
    summary = []
    for m in meta:
        ep = m["episode_index"]
        if ep not in wanted:
            continue
        name = f"ep{ep:02d}_{m['object']}"
        d = work / name
        (d / "detect").mkdir(parents=True, exist_ok=True)
        video = inp / "videos" / f"episode_{ep:06d}.mp4"
        total = n_frames(video)
        packed = d / "masks_k0.h5"
        report_path = d / "mask_report.json"
        if not args.recheck and packed.exists() and report_path.exists() and json.loads(report_path.read_text()).get("check", {}).get("ok"):
            print(f"skip {name}: packed and checked")
            continue
        object_prompt = "a " + m["object"].replace("_", " ")
        pick = choose_prompt_frame(d / "detect", video, total, object_prompt, args.weights, args.box_threshold, args.samples,
                                   object_name=m["object"])
        if not pick["candidates"]:
            print(f"!! {name}: no object box on any of {pick['frames']}")
            (d / "NO_AUTO_PROMPT").write_text(json.dumps(pick, indent=1))
            summary.append({"episode": name, "ok": False, "why": "no object box"})
            continue
        best = pick["candidates"][0]
        person_box = best["person_box"] or next((c["person_box"] for c in pick["candidates"] if c["person_box"]), None)
        if person_box is None:
            print(f"!! {name}: no person box")
            (d / "NO_AUTO_PROMPT").write_text(json.dumps(pick, indent=1))
            summary.append({"episode": name, "ok": False, "why": "no person box"})
            continue
        prompts = d / "prompts.json"
        prompts.write_text(json.dumps({"prompts": [
            {"frame_index": best["frame_index"], "object_id": 0, "box": person_box},
            {"frame_index": best["frame_index"], "object_id": 1, "box": best["box"]},
        ]}, indent=1))
        masks = d / "sam2_masks"
        if not (masks / "1").exists():
            run([sys.executable, "-m", "v2d.sam2.docker.run_video_to_masks", "--video_path", str(video),
                 "--prompts_path", str(prompts), "--masks_dir", str(masks), "--weights_dir", f"{args.weights}/sam2"])
        gaps_before = object_gaps(masks, total)
        extra = []
        if gaps_before and not (d / "sam2_masks_v1").exists():
            extra = gap_prompts(d, video, masks, total, gaps_before, object_prompt, m["object"], args.weights, args.box_threshold)
            if extra:
                prompts.write_text(json.dumps({"prompts": [
                    {"frame_index": best["frame_index"], "object_id": 0, "box": person_box},
                    {"frame_index": best["frame_index"], "object_id": 1, "box": best["box"]},
                    *({"frame_index": e["frame_index"], "object_id": 1, "box": e["box"]} for e in extra),
                ]}, indent=1))
                masks.rename(d / "sam2_masks_v1")
                run([sys.executable, "-m", "v2d.sam2.docker.run_video_to_masks", "--video_path", str(video),
                     "--prompts_path", str(prompts), "--masks_dir", str(masks), "--weights_dir", f"{args.weights}/sam2"])
                packed.unlink(missing_ok=True)
        complete = []
        if not (d / "sam2_masks_incomplete").exists():
            complete = completion_prompts(masks, pick["candidates"])
            if complete:
                current = json.loads(prompts.read_text())["prompts"]
                prompts.write_text(json.dumps({"prompts": [
                    *current, *({"frame_index": e["frame_index"], "object_id": 1, "box": e["box"]} for e in complete),
                ]}, indent=1))
                masks.rename(d / "sam2_masks_incomplete")
                run([sys.executable, "-m", "v2d.sam2.docker.run_video_to_masks", "--video_path", str(video),
                     "--prompts_path", str(prompts), "--masks_dir", str(masks), "--weights_dir", f"{args.weights}/sam2"])
                packed.unlink(missing_ok=True)
        gaps_after = object_gaps(masks, total)
        width = Image.open(d / "detect" / f"frame_{best['frame_index']:06d}.png").size[0]
        check = check_masks(masks, total, width, best["frame_index"], best["box"], best.get("support_boxes", []))
        for idx in (0, best["frame_index"], total - 1):
            overlay(video, masks, idx, d / f"overlay_{idx:06d}.png")
        report = {"episode": name, "prompt_frame": best["frame_index"], "object_box": best, "check": check, "candidates": pick["candidates"][:5],
                  "gaps_before": gaps_before, "gap_prompts": extra, "completion_prompts": complete, "gaps_after": gaps_after,
                  "pack_version": PACK_VERSION}
        previous = json.loads(report_path.read_text()) if report_path.exists() else {}
        if previous.get("pack_version") != PACK_VERSION:
            packed.unlink(missing_ok=True)
        report_path.write_text(json.dumps(report, indent=1))
        if not check["ok"]:
            (d / "MASK_SUSPECT").write_text(check["why"])
            print(f"!! {name}: {check['why']}")
        else:
            (d / "MASK_SUSPECT").unlink(missing_ok=True)
        cari_video = d / f"episode_{ep:06d}.0.color.mp4"
        if not cari_video.exists():
            try:
                os.link(video, cari_video)
            except OSError:
                shutil.copy2(video, cari_video)
        if not packed.exists():
            human = pack_human_minus_object(masks)
            run([sys.executable, "-m", "v2d.cari4d.docker.run_pack_masks", "--video_path", str(cari_video),
                 "--human_masks_path", str(human), "--object_masks_path", str(masks / "1"), "--output_path", str(packed)])
        summary.append({"episode": name, "ok": check["ok"], "prompt_frame": best["frame_index"], "why": check["why"]})
        print(f"{'ok' if check['ok'] else 'SUSPECT'} {name} prompt_frame={best['frame_index']}")
    (work / "masks_summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
