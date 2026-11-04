---
license: other
pretty_name: Maniphys Lab V2D Challenge Track 2 submission
---

# Maniphys Lab: V2D Challenge Track 2 submission

This repository holds the verification container and the technical report of team Maniphys Lab for Track 2 (Robotic Grounding) of the NVIDIA Video to Data (V2D) Challenge.

| File | Contents |
|---|---|
| `maniphys-lab-v2d-submission.tar.zst` | The Docker image `maniphys-lab-v2d-submission:final`, saved with `docker save` and compressed with `zstd`. |
| `maniphys-lab-v2d-submission.tar.zst.sha256` | sha256 of the tarball and the image ID. |
| `v2d-track2-technical-report.pdf` | The technical report. |

## Load and run

```bash
sha256sum -c maniphys-lab-v2d-submission.tar.zst.sha256
zstd -dc maniphys-lab-v2d-submission.tar.zst | docker load
# verify one tier (no GPU); /path/to/dataset holds track_2/
docker run --rm --network none -v /path/to/dataset:/data:ro \
    -e MANIFEST=/submission/submission.tier1.json maniphys-lab-v2d-submission:final \
    /submission/run.sh verify --dataset-root /data
```

The container covers three counted files, one per tier: Tier 1 `t1x1102`, Tier 2 `b1014` and Tier 3 `t3m1029a`. Each file was packed from its own code commit, so the container has one manifest per tier. `/submission/README.md` inside the image explains the layout, the manifests and the `reproduce` command.

Code: https://github.com/Manifold-ai/maniphys_lab_v2d_challenge
