# -*- coding: utf-8 -*-
"""k 도출 근거 분석: 내부 간격 분포 백분위 vs 미세 k 스윕 (당진 S3 t=0.30)"""
import os, sys, importlib.util
import numpy as np

BASE = r"C:\Users\user\새 폴더"
spec = importlib.util.spec_from_file_location(
    "c4", os.path.join(BASE, "pipeline", "04_cluster.py"))
c4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c4)

df = c4.load_parcels("44270", "S3", local=True)
blobs, leftover, n_noise, n_seeds, pts = c4.grow_blobs(df, t_cap=0.30)
area = df["area_m2"].values

# 1) 클러스터 내부 NN 간격 분포
from scipy.spatial import cKDTree
nn = []
for blob in blobs:
    if len(blob) < 2:
        continue
    sub = pts[blob]
    t = cKDTree(sub)
    d, _ = t.query(sub, k=2)
    nn.extend(d[:, 1].tolist())
nn = np.array(nn)
med = np.median(nn)
print(f"내부 NN 간격: n={len(nn):,} median={med:.1f}m")
for p in [75, 90, 95, 99]:
    v = np.percentile(nn, p)
    print(f"  P{p} = {v:.1f}m  (환산 k = {v/med:.2f})")

# 2) 미세 k 스윕
print(f"\n{'k':>5} {'r_m':>7} {'병합':>5} {'지구수':>6} {'감소':>5} {'거부cap':>7} {'거부지름':>7}")
prev_n = len(blobs)
for k in np.arange(1.0, 5.01, 0.25):
    merged, st = c4.merge_pass(blobs, pts, area, float(k), 30.0, med)
    print(f"{k:>5.2f} {st['r_m']:>7.1f} {st['n_merged']:>5} {len(merged):>6} "
          f"{prev_n-len(merged):>5} {st['rejected_cap']:>7} {st['rejected_diam']:>7}")
