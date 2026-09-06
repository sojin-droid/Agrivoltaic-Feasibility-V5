# -*- coding: utf-8 -*-
"""구획 GeoJSON 후처리 — **gzip 만** 한다. 산출: {sgg}_{cell}.json.gz, 원본 .json 삭제.

좌표 재양자화를 하지 않는다(2026-08-29): 구판은 소수 4자리(≈10m)로 반올림했는데,
정본 우주 구획의 중앙 면적이 700㎡(반경 약 15m)라 그 격자로는 형태가 남지 않는다.
게다가 단순 반올림은 얇은 구획을 자기교차(무효 폴리곤)로 만든다 — 실측 2,707개 중 131개.
양자화는 export_clusters_v4 가 위상 인식(shapely.set_precision)으로 이미 끝냈다.
사용: python pipeline/geom/compress_clusters.py"""
import os, sys, io, glob, gzip
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, OUT, CLUSTERS, ROOT, MODEL, LR, CAD   # 경로는 한 곳에서만
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CL = CLUSTERS

before = after = 0
fs = sorted(glob.glob(os.path.join(CL, '*.json')))
for i, fp in enumerate(fs, 1):
    before += os.path.getsize(fp)
    raw = io.open(fp, 'rb').read()        # 그대로 압축한다 — 좌표를 다시 건드리지 않는다
    fo = fp + '.gz'
    with gzip.open(fo + '.tmp', 'wb', compresslevel=9) as z:
        z.write(raw)
    os.replace(fo + '.tmp', fo)
    after += os.path.getsize(fo)
    os.remove(fp)
    if i % 200 == 0 or i == len(fs):
        print(f"  [{i}/{len(fs)}] {before/1e6:,.0f} → {after/1e6:,.0f} MB", flush=True)
print(f"완료: {len(fs)}파일 {before/1e6:,.1f} MB → {after/1e6:,.1f} MB")
