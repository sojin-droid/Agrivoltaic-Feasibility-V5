# -*- coding: utf-8 -*-
"""구획(등재 클러스터) 폴리곤 export — 지도 탭 데이터 (시나리오별·시군별).

원천: 정본 scenario_runs/{cell}/members.parquet (pnu→성분 lab, 1판·ADR-0034 승인)
      + engine_cache/nodes.parquet(장부면적) + Cadastre_All 지오메트리.
산출: data_v4/clusters/{sgg}_{cell}.json — 등재 구획을 시군 구간별로 dissolve·간소화한
      GeoJSON(4326). 성분이 여러 시군에 걸치면 각 시군 파일에 그 구간이 들어가고
      속성 a(구획 전체 km²)는 동일, part=1 로 표시.
      data_v4/clusters_index.json — 시군×시나리오 요약(선택 목록·통계용).

체크포인트: 시군 단위(6칸 전부 존재 시 건너뜀). 재실행 안전.
사용: python pipeline/geom/export_clusters_v4.py
"""
import os, sys, json, glob, datetime, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, OUT, CLUSTERS, ROOT, MODEL, LR, CAD   # 경로는 한 곳에서만
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np, pandas as pd
import geopandas as gpd
import shapely

LR = os.path.join(ROOT, 'Ledger_Rebuild')
CAD = os.path.join(ROOT, 'Cadastre_All')
RUNS = os.path.join(LR, 'scenario_runs')
OUT = CLUSTERS
os.makedirs(OUT, exist_ok=True)

# 정본 8칸 + 대조군 8칸(@all). 대조군을 그리는 이유는 **어디가 비어 있는지 보이기** 위해서다
# (사용자 결정 2026-08-29) — 개인 소유라서 정본에 없는 자리를 눈으로 확인할 수 있어야 한다.
CELLS_MAIN = ['R0_current', 'R0_current_SB', 'R1_protect', 'R1_protect_SB',
              'R2_promo', 'R2_promo_SB', 'R3_zone_all', 'R3_zone_all_SB']
CELLS_CTRL = [c + '@all' for c in CELLS_MAIN]
CELLS = CELLS_MAIN + CELLS_CTRL

# 간소화 프로파일 — 정본은 형태를 재는 데 쓰이므로 촘촘하게, 대조군은 위치를 보이는 데
# 쓰이므로 굵게. 허용오차는 구획 크기에 비례한다(등가반경 × 비율, 클립 안에서).
# 평탄 허용오차를 쓰면 작은 구획이 뭉개진다(정본 우주 구획 중앙 면적 700㎡ = 반경 약 15m).
#   ratio · min · max · grid(위상 인식 양자화 m) · dp(좌표 소수 자리)
PROFILE = {
    'main': dict(ratio=1/20.0, mn=1.0, mx=10.0, grid=0.5, dp=6),   # ≈0.11m 표기
    'ctrl': dict(ratio=1/4.0,  mn=15.0, mx=80.0, grid=6.0, dp=5),  # ≈1.1m 표기
}
prof = lambda cell: PROFILE['ctrl' if cell.endswith('@all') else 'main']
GEN = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

# ── 멤버·면적 적재 (한 번) ──
nodes = pd.read_parquet(os.path.join(LR, 'engine_cache', 'nodes.parquet'),
                        columns=['pnu', 'area'])
area = pd.Series(nodes['area'].values, index=nodes['pnu'].values)
del nodes

mem = {}
comp_area = {}
for c in CELLS:
    m = pd.read_parquet(os.path.join(RUNS, c, 'members.parquet'))
    m['sgg'] = m['pnu'].str[:5]
    m['a'] = area.reindex(m['pnu'].values).values
    comp_area[c] = m.groupby('lab')['a'].sum() / 1e6          # 구획 전체 km² (장부면적)
    mem[c] = m
    print(f"{c}: 멤버 {len(m):,} · 등재 구획 {m['lab'].nunique():,}", flush=True)

sggs = sorted(set().union(*[set(m['sgg'].unique()) for m in mem.values()]))
print(f"대상 시군 {len(sggs)}", flush=True)

for i, sgg in enumerate(sggs, 1):
    outs = {c: os.path.join(OUT, f'{sgg}_{c}.json') for c in CELLS}
    # 압축본(.json.gz)이 있으면 이미 만든 것이다 — 정본을 다시 굽지 않는다
    done = lambda p: os.path.exists(p) or os.path.exists(p + '.gz')
    if all(done(p) for p in outs.values()):
        continue
    g = gpd.read_file(os.path.join(CAD, f'{sgg}.gpkg')).to_crs(5186)
    g = g.drop_duplicates('pnu').set_index('pnu')
    for c in CELLS:
        fo = outs[c]
        if done(fo):
            continue
        ms = mem[c][mem[c]['sgg'] == sgg]
        feats = []
        if len(ms):
            sub = g.reindex(ms['pnu'].values)
            ok = sub.geometry.notna().values
            geoms = sub.geometry.values[ok]
            labs = ms['lab'].values[ok]
            if len(geoms):
                # ── 구획별 합집합을 한 번에 (구획 수가 30만이라 파이썬 루프는 못 버틴다) ──
                grouped = (gpd.GeoSeries(geoms)
                           .groupby(labs).agg(lambda gs: shapely.union_all(gs.values)))
                uniq = grouped.index.values
                merged = np.asarray(grouped.values, dtype=object)
                # 적응 허용오차 — 등가반경의 1/20, [1,10]m. 평탄 허용오차는 작은 구획을 죽인다
                _pf = prof(c)
                area = shapely.area(merged)
                tol = np.clip(np.sqrt(area / np.pi) * _pf['ratio'], _pf['mn'], _pf['mx'])
                merged = shapely.simplify(merged, tol)
                # 양자화 전에 유효화한다 — set_precision 은 무효 입력에서 TopologyException 을
                # 던진다(실측: side location conflict). 던지면 그 시군 전체가 멈춘다.
                bad = ~shapely.is_valid(merged)
                if bad.any():
                    merged[bad] = shapely.make_valid(merged[bad])
                try:
                    merged = shapely.set_precision(merged, _pf['grid'])   # 위상 인식 양자화
                except Exception:
                    # 배열 단위로 실패하면 개별로 시도하고, 끝내 안 되는 것은 양자화를
                    # 건너뛴다 — 좌표가 조금 길어질 뿐, 형태를 잃거나 버리지는 않는다
                    out_g, n_skip = [], 0
                    for _g in merged:
                        try:
                            out_g.append(shapely.set_precision(_g, _pf['grid']))
                        except Exception:
                            out_g.append(_g)
                            n_skip += 1
                    merged = np.asarray(out_g, dtype=object)
                    if n_skip:
                        print(f"    ※ {sgg}/{c}: 양자화 건너뜀 {n_skip}구획(위상 충돌)",
                              flush=True)
                bad = ~shapely.is_valid(merged)
                if bad.any():
                    merged[bad] = shapely.make_valid(merged[bad])
                keep = ~shapely.is_empty(merged)
                gs = gpd.GeoSeries(merged[keep], crs=5186).to_crs(4326)
                n_by = pd.Series(1, index=labs).groupby(level=0).sum()
                _dp = _pf['dp']

                def _rnd(cc, dp=_dp):
                    if isinstance(cc[0], (list, tuple)):
                        return [_rnd(x, dp) for x in cc]
                    return [round(cc[0], dp), round(cc[1], dp)]

                for lab, geo in zip(uniq[keep], gs.values):
                    gj = shapely.geometry.mapping(geo)
                    # 좌표는 여기서 반올림하지 않는다 — 양자화는 위상 인식으로 이미 끝났고,
                    # 여기서 또 자르면 그때 자기교차가 생긴다(인수인계 §7 실측).
                    # 표기 자릿수는 상류 양자화보다 촘촘해야 꼭짓점이 붙지 않는다
                    # (정본 0.5m 격자 ↔ 6자리 0.11m · 대조군 2m 격자 ↔ 5자리 1.1m)
                    feats.append({'type': 'Feature',
                                  'geometry': {'type': gj['type'],
                                               'coordinates': _rnd(list(gj['coordinates']))},
                                  'properties': {'id': int(lab),
                                                 'a': round(float(comp_area[c].get(lab, 0.0)), 2),
                                                 'n': int(n_by.get(lab, 0))}})
        tmp = fo + '.tmp'
        json.dump({'type': 'FeatureCollection', 'cell': c, 'sgg': sgg,
                   'features': feats},
                  open(tmp, 'w', encoding='utf-8'), ensure_ascii=False,
                  separators=(',', ':'))
        os.replace(tmp, fo)
    if i % 10 == 0 or i == len(sggs):
        print(f"  [{i}/{len(sggs)}] {sgg} 완료", flush=True)

# ── 걸침 표시 + 색인 ──
# 여기서 만들지 않는다. 색인 단계는 확장자에 무관해야 하는데(정본은 이미 .json.gz),
# 이 안에서 하면 압축본을 못 읽고 색인에서 통째로 빠진다 — 지도가 빈 화면이 된다.
subprocess.run([sys.executable,
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'rebuild_cluster_index.py')], check=True)
print(f"완료 — clusters/ {len(glob.glob(os.path.join(OUT, '*.json*'))):,}파일 ({GEN})", flush=True)
