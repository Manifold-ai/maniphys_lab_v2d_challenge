"""Run an official toolkit docker wrapper with the lab proxy forwarded into the container by NAME only.

    source ~/proxy.sh; python t3_run.py v2d.sam3d.docker.run_image_to_mesh --image_path ... (wrapper args)

Why: SAM 3D Objects (DINO embedder) and CARI4D stage 6 call torch.hub, which contacts github.com even with
the repo cached; without the proxy the request is reset (Track 1: 8 meshes failed with RemoteDisconnected).
The wrapper renders env as `-e KEY=VALUE`, which put the proxy password on the docker command line, in
`ps` and in the logs (Track 1 run_cari4d.py). Here the proxy variables are added as bare `-e KEY`, so docker
reads the values from this process's environment and they never appear in argv.

Non-secret extras: T3_FORWARD_ENV="NAME,NAME" forwards host variables by name (e.g. PYTORCH_CUDA_ALLOC_CONF);
T3_CONTAINER_ENV="KEY=VALUE,..." sets container-side values the wrapper does not (CARI4D needs TORCH_HOME inside
the mounted weights so torch.hub's DINOv2 checkout survives across containers). A proxy key in either is refused.
T3_EXTRA_MOUNTS="host:container:ro;..." adds bind mounts (used to lay a third_party patch over one image file).
"""

from __future__ import annotations

import os
import runpy
import subprocess
import sys

from v2d.docker import container as container_mod

PROXY_KEYS = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "no_proxy", "NO_PROXY")
SECRET_MARKERS = ("proxy",)


class _Subprocess:
    def __getattr__(self, name):
        return getattr(subprocess, name)

    @staticmethod
    def run(cmd, *args, **kwargs):
        if cmd[:3] == ["docker", "run", "--rm"]:
            names = list(PROXY_KEYS) + [n for n in os.environ.get("T3_FORWARD_ENV", "").split(",") if n]
            forwarded = [a for k in names if os.environ.get(k) for a in ("-e", k)]
            extras = [kv for kv in os.environ.get("T3_CONTAINER_ENV", "").split(",") if kv]
            if any("proxy" in kv.split("=", 1)[0].lower() for kv in extras):
                raise SystemExit("refusing: T3_CONTAINER_ENV must not carry a proxy setting")
            forwarded += [a for kv in extras for a in ("-e", kv)]
            forwarded += [a for m in os.environ.get("T3_EXTRA_MOUNTS", "").split(";") if m for a in ("-v", m)]
            cmd = cmd[:3] + forwarded + cmd[3:]
            leaked = [a for a in cmd if "=" in a and any(m in a.split("=", 1)[0].lower() for m in SECRET_MARKERS)]
            if leaked:
                raise SystemExit("refusing: a proxy value would be on the docker command line")
        return subprocess.run(cmd, *args, **kwargs)  # noqa: PLW1510 - the wrapper passes check=True itself


container_mod.subprocess = _Subprocess()

if __name__ == "__main__":
    if not os.environ.get("https_proxy"):
        raise SystemExit("source ~/proxy.sh first: torch.hub inside the container needs github.com")
    module = sys.argv[1]
    sys.argv = [module] + sys.argv[2:]
    runpy.run_module(module, run_name="__main__", alter_sys=True)
