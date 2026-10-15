"""Shape-aware rotation distance and an object's symmetry rotations, shared by t3_dynamics_post and t3_dynamics_check.

A rotation counts as a symmetry only if it moves no point of the surface by more than SYM_M (the largest shift, not the
mean: the mean let every 15 deg turn of the spray bottle about its long axis through, because the nozzle and trigger
are a small part of the surface while they moved 1-3.4 cm), and only if the whole set closes: an n-fold axis needs
every multiple of 360/n deg to pass, a continuous axis every multiple of CONT_STEP_DEG.

Distances are from QUERY points sampled on the surface to the nearest of DENSE points sampled on the same surface, so
the sampling floor is about the dense spacing (1-6 mm for these meshes) rather than the spacing of the query set.
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

SYM_M = 0.01
FOLDS = (2, 3, 4, 5, 6, 8, 12)
CONT_STEP_DEG = 5
DENSE = 200_000
QUERY = 2000


class Shape:
    """The surface of a mesh centred on com_b, in the body frame."""

    def __init__(self, mesh, com_b):
        import trimesh

        com_b = np.asarray(com_b, np.float64)
        self.dense = trimesh.sample.sample_surface(mesh, DENSE, seed=0)[0] - com_b
        self.query = trimesh.sample.sample_surface(mesh, QUERY, seed=1)[0] - com_b
        self.tree = cKDTree(self.dense)

    def shift(self, g) -> float:
        """Largest distance a surface point lands from the surface after body-frame rotation g."""
        return float(self.tree.query(self.query @ np.asarray(g).T)[0].max())


def _rot(axis, deg):
    return Rotation.from_rotvec(np.asarray(axis) * np.deg2rad(deg)).as_matrix()


def _angle(a, b):
    return float(np.arccos(np.clip((np.trace(a.T @ b) - 1) / 2, -1, 1)))


def symmetries(shape: Shape, inertia):
    """(G, axis): the discrete symmetry rotations (identity first, closed under composition) and the unit body-frame axis
    of a continuous symmetry, or None. Candidate axes are the principal axes of the inertia."""
    _, axes = np.linalg.eigh(np.asarray(inertia))
    cont = None
    gens = []
    for k in range(3):
        a = axes[:, k]
        if all(shape.shift(_rot(a, d)) <= SYM_M for d in range(CONT_STEP_DEG, 360, CONT_STEP_DEG)):
            cont = a if cont is None else cont  # two continuous axes would be a sphere; keep the first
            continue
        for n in sorted(FOLDS, reverse=True):
            if all(shape.shift(_rot(a, 360 * j / n)) <= SYM_M for j in range(1, n)):
                gens.append(_rot(a, 360 / n))
                break
    # a generator joins only if the group it closes into still passes: two near-symmetric flips whose product is
    # not a symmetry (the book's 180 deg turns: 8 mm each, their product 10.4 mm) keep the better one only
    G = [np.eye(3)]
    for g in sorted(gens, key=shape.shift):
        H = _closure(G, g)
        if H is not None and all(shape.shift(h) <= SYM_M for h in H[1:]):
            G = H
    return G, cont


def _closure(G, g, limit=48):
    H = list(G)
    frontier = list(G)
    while frontier:
        nxt = []
        for f in frontier:
            for x in (g, *G[1:]):
                h = f @ x
                if all(_angle(h, y) > 1e-3 for y in H):
                    H.append(h)
                    nxt.append(h)
                    if len(H) > limit:
                        return None
        frontier = nxt
    return H


def nearest_equivalent(R, R_prev, G, axis):
    """The orientation equivalent to R (R g, then a turn about the continuous axis if any) closest to R_prev."""
    best, best_ang = R, np.inf
    for g in G:
        C = R @ g
        if axis is not None:
            # maximise trace(R_prev^T C Rot(axis, phi)) over phi, in closed form
            M = R_prev.T @ C
            a = axis
            ax = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
            phi = np.arctan2(np.trace(M @ ax), np.trace(M) - a @ M @ a)
            C = C @ Rotation.from_rotvec(a * phi).as_matrix()
        ang = _angle(R_prev, C)
        if ang < best_ang:
            best, best_ang = C, ang
    return best
