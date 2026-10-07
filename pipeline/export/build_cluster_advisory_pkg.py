# -*- coding: utf-8 -*-
"""클러스터링 방법론 자문(KEI) — 검토 대상지 10곳 데이터 패키지 생성 (2026-10-07).

자문자가 21m 연접이 아닌 다른 묶음 규칙을 **처음부터 다시** 시험할 수 있도록 필지 층까지 내려서 준다.
대상지 목록은 docs/method_advisory/study_areas.json (STUDY_AREAS.md 의 선정 기준). 조건 = R2_promo(특별법 시행 후 · 법인·국공유).

시군별 산출 (Ledger_Rebuild/cluster_advisory_pkg/<sgg>/)
  parcels.gpkg / parcels.csv   적격 필지 전량(그 시군에 필지가 있는 21m 단위의 구성 필지 전부 — 이웃 시군 필지 포함) : 폴리곤(EPSG:5186), 장부 면적, 지목,
                                소유 유형, 농업진흥지역 구분, 팜맵 경작 판독비, 경사, 간척 원장 여부, 이웃 간격 d1·d2·d4·d8·d12, 소속 21m 단위(lab)
  units.gpkg / units.csv       21m 연접 단위 전량(면적 하한 없음) : 필지 dissolve 폴리곤(단순화 없음), 장부 면적, 필지 수, 소유 구성비, 간척 비중, 경작 비율,
                                대표점, 산단 거리, 계통 하한·상한, 규모 눈금, 3축 비지배 플래그(3MW 이상 · 시군 안)
  unit_pairs.csv               단위 쌍 경계 간 거리(≤ 2,000 m) — 2단계 묶음 규칙을 기하 계산 없이 시험하기 위한 것
  context/ind_complex.geojson  산업단지 경계(유형) — 시군 단위에서 15 km 안
  context/emd_grid.geojson     읍면동 경계 + 계통 여유 참고값(하한·상한·조회 상태)
  context/existing_pv.geojson  기존 태양광(위치 확인분 · 허가 주소 위치)
  README.md                    열 사전 · 기준일 · 좌표계 · 인용 금지 고지 · 선정 층·이유
공통: cluster_advisory_pkg/README.md · MANIFEST.json(파일별 sha256·행 수)

정본 산출을 읽기만 한다(수정 없음). 결과는 자문용 자료이며 보고서·논문 인용 대상이 아니다.
사용: python pipeline/export/build_cluster_advisory_pkg.py [--sgg 44270 ...] [--no-geom]
"""
import os, sys, json, gzip, hashlib, argparse, datetime, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, LR, CAD
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np, pandas as pd, duckdb, pyogrio, geopandas as gpd
from shapely.geometry import shape, Point, mapping
from shapely.strtree import STRtree
from shapely.ops import transform as sh_transform
from pyproj import Transformer

RUN = 'R2_promo'
RUND = os.path.join(LR, 'scenario_runs', RUN)
DB = os.path.join(LR, 'agrivoltaic_ledger_v1.duckdb')
OUT = os.path.join(LR, 'cluster_advisory_pkg')
SA = json.load(open(os.path.join(SITE, 'docs', 'method_advisory', 'study_areas.json'), encoding='utf-8'))
KW = 0.045
BANDS = [(1_111_111, '50MW'), (444_444, '20MW'), (222_222, '10MW'), (66_667, '3MW'), (0, '3MW 미만')]
TO4326 = Transformer.from_crs('EPSG:5186', 'EPSG:4326', always_xy=True)
TO5186 = Transformer.from_crs('EPSG:4326', 'EPSG:5186', always_xy=True)
T0 = time.time(); say = lambda *a: print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)
q = lambda p: str(p).replace('\\', '/')


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest()


def band(a):
    for v, k in BANDS:
        if a >= v: return k
    return BANDS[-1][1]


def frontier(df):
    """3축 비지배(면적↑ · 계통 하한↑ · 산단 거리↓) — query._frontier_mask 와 같은 규칙(결측 = 축 최악값 · 동률 ≠ 지배)."""
    v = df[['area_m2', 'lo', 'dist_ind_km']].to_numpy(float).copy()
    v[:, 0] = np.nan_to_num(v[:, 0], nan=-np.inf); v[:, 1] = np.nan_to_num(v[:, 1], nan=-np.inf); v[:, 2] = -np.nan_to_num(v[:, 2], nan=np.inf)
    dom = np.array([bool((np.all(v >= v[i], axis=1) & np.any(v > v[i], axis=1)).any()) for i in range(len(v))])
    return ~dom


def load_common():
    con = duckdb.connect(DB, read_only=True)
    bc = pd.read_parquet(os.path.join(RUND, 'block_context.parquet'))
    bj = json.load(open(os.path.join(RUND, 'block_context.json'), encoding='utf-8'))
    assert (bj.get('subset') or {}).get('all') is True, '거부: block_context 가 전량(--all)이 아니다 — 먼저 전량 재산출'
    ind = json.load(gzip.open(os.path.join(SITE, 'data_v4', 'ind_bnd.json.gz'), 'rt', encoding='utf-8'))
    ind_g = []
    for f in ind['features']:
        try:
            g = sh_transform(TO5186.transform, shape(f['geometry']))
            if not g.is_empty: ind_g.append((g, f['properties']))
        except Exception: pass
    ind_tree = STRtree([g for g, _ in ind_g])
    emd = json.load(gzip.open(os.path.join(SITE, 'data_v4', 'grid_emd.json.gz'), 'rt', encoding='utf-8'))
    # 읍면동 경계는 2026 개편 신 코드(전남광주통합 12xxx 등)라 PNU 앞자리로 고를 수 없다 — 공간 교차로 고른다
    emd_g = []
    for f in emd['features']:
        try:
            g = sh_transform(TO5186.transform, shape(f['geometry']))
            if not g.is_empty: emd_g.append((g, f))
        except Exception: pass
    emd['_g'] = emd_g; emd['_tree'] = STRtree([g for g, _ in emd_g])
    ex = json.load(gzip.open(os.path.join(SITE, 'data_v4', 'existing_pv_v4.json.gz'), 'rt', encoding='utf-8'))
    prov = json.load(open(os.path.join(SITE, 'data_v4', 'provenance_v4.json'), encoding='utf-8'))
    return con, bc, ind_g, ind_tree, emd, ex, prov


def build_sgg(a, con, bc, ind_g, ind_tree, emd, ex, prov, geom=True, context_only=False):
    sgg, name, stratum = a['sgg'], a['name'], a['stratum']
    d = os.path.join(OUT, sgg); os.makedirs(os.path.join(d, 'context'), exist_ok=True)
    say(f"=== {sgg} {name} ({stratum})")
    # 단위: 이 시군에 필지가 하나라도 있는 21m 단위(touch) — 속성은 전량 block_context(이 시군 행)
    b = bc[bc.sgg == sgg].drop_duplicates('lab').copy()
    labs = set(b.lab)
    mem = con.execute(f"SELECT pnu, lab FROM read_parquet('{q(RUND)}/members.parquet') WHERE lab IN (SELECT lab FROM read_parquet('{q(RUND)}/block_context.parquet') WHERE sgg='{sgg}')").df()
    mem['sgg_p'] = mem.pnu.str[:5]; mem['emd8'] = mem.pnu.str[:8]
    say(f"  단위 {len(labs):,} · 구성 필지 {len(mem):,} (이웃 시군 필지 {int((mem.sgg_p != sgg).sum()):,})")

    # ── 필지 속성 ──
    _mdf = mem[['pnu', 'lab']].copy(); con.register('_m', _mdf)
    P = con.execute(f"""
      SELECT m.pnu, m.lab, l.sgg, substr(m.pnu,1,8) emd8, l.calculatedarea area_ledger_m2, l.category_name jimok, l.ownership_name ownership,
             l.govtorg_name gov_org, l.agpromo, l.subagpromo_name agpromo_zone, l.farmmap_ratio, l.farmmap_matched,
             s.slope_mean_w slope_mean, s.slope_max,
             r.in_ekr_reclaim_register reclaim_register, r.ekr_district reclaim_district, r.nat_managed_district,
             g.n_touch, g.d1, g.d2, g.d4, g.d8, g.d12
      FROM _m m LEFT JOIN ledger l USING(pnu) LEFT JOIN pnu_slope s USING(pnu) LEFT JOIN reclaim_tag r USING(pnu)
      LEFT JOIN read_parquet('{q(os.path.join(LR, 'gaps'))}/S1_*.parquet') g USING(pnu)""").df()
    P['reclaim_register'] = P.reclaim_register.fillna(False).astype(bool)
    P.to_csv(os.path.join(d, 'parcels.csv'), index=False, encoding='utf-8-sig')
    say(f"  parcels.csv {len(P):,}행")

    # ── 필지 폴리곤 → 단위 dissolve(단순화 없음) ──
    U = b[['lab', 'area_m2', 'n_parcel', 'mw', 'farm_ratio', 'reclaim_pct', 'lo', 'hi', 'cls', 'n_emd', 'dist_ind_km', 'x', 'y', 'n_in_sgg']].copy()
    own = P.groupby('lab').ownership.value_counts(normalize=True).unstack(fill_value=0)
    for k, col in (('법인', 'share_corp'), ('국유지', 'share_national'), ('시/도유지', 'share_sido'), ('군유지', 'share_gun')):
        U[col] = U.lab.map(own[k] if k in own else pd.Series(dtype=float)).fillna(0).round(3)
    U['n_sgg'] = U.lab.map(mem.groupby('lab').sgg_p.nunique())
    U['n_emd_geom'] = U.lab.map(mem.groupby('lab').emd8.nunique())
    U['size_band'] = U.area_m2.map(band)
    U['mw_ref'] = (U.area_m2 * KW / 1000).round(3)
    U['in_top10_population'] = U.area_m2 >= 66_667
    fr = U[U.in_top10_population]
    U['nondominated_3ax'] = False
    if len(fr): U.loc[fr.index, 'nondominated_3ax'] = frontier(fr)
    gdf = None
    n_geom_missing_units = n_geom_missing_parcels = None
    if context_only and os.path.exists(os.path.join(d, 'units.csv')):
        uc = pd.read_csv(os.path.join(d, 'units.csv')); n_geom_missing_units = int((~uc.has_geom).sum()) if 'has_geom' in uc else None
        n_geom_missing_parcels = len(P) - int(pyogrio.read_info(os.path.join(d, 'parcels.gpkg'))['features']) if os.path.exists(os.path.join(d, 'parcels.gpkg')) else None
    if geom and not context_only:
        # ADR-0047 회수 대응표 — 법정동 코드 개편으로 원장 pnu(구 코드)와 지적도 pnu(신 코드)가 다른 필지는 신 pnu 로 읽는다
        _recp = os.path.join(LR, 'engine_cache', 'parcel_geom_pubcorp_recovery.parquet')
        rec = pd.read_parquet(_recp, columns=['old_pnu', 'new_pnu']).drop_duplicates('old_pnu').set_index('old_pnu')['new_pnu'] if os.path.exists(_recp) else pd.Series(dtype=str)
        mem['pnu_geom'] = mem.pnu.map(rec).fillna(mem.pnu)
        n_rec = int((mem.pnu_geom != mem.pnu).sum())
        parts = []
        for s5, grp in mem.groupby(mem.pnu_geom.str[:5]):
            fp = os.path.join(CAD, f'{s5}.gpkg')
            if not os.path.exists(fp): say(f"  ⚠ 지적 파일 없음 {s5}"); continue
            g = pyogrio.read_dataframe(fp, columns=['pnu']).rename(columns={'pnu': 'pnu_geom'})
            g = g.merge(grp[['pnu', 'pnu_geom', 'lab']], on='pnu_geom', how='inner').drop(columns='pnu_geom')
            if len(g): parts.append(g)
        say(f"  지적 읽기 — 회수 대응표 적용 {n_rec:,}필지")
        G = pd.concat(parts, ignore_index=True) if parts else None
        if G is not None:
            G = gpd.GeoDataFrame(G, geometry='geometry', crs='EPSG:5186')
            Pg = G.merge(P.drop(columns=['lab']), on='pnu', how='left')
            Pg.to_file(os.path.join(d, 'parcels.gpkg'), layer='parcels', driver='GPKG')
            dis = G.dissolve(by='lab')[['geometry']].reset_index()
            from shapely import make_valid
            dis['geometry'] = [g if g.is_valid else make_valid(g) for g in dis.geometry]
            gdf = gpd.GeoDataFrame(U.merge(dis, on='lab', how='left'), geometry='geometry', crs='EPSG:5186')
            gdf['area_geom_m2'] = gdf.geometry.area
            gdf['has_geom'] = gdf.geometry.notna() & ~gdf.geometry.is_empty
            gdf.to_file(os.path.join(d, 'units.gpkg'), layer='units', driver='GPKG')
            n_geom_missing_units = int((~gdf.has_geom).sum()); n_geom_missing_parcels = len(P) - len(Pg)
            say(f"  parcels.gpkg {len(Pg):,} · units.gpkg {len(gdf):,} (기하 없음 {n_geom_missing_units})")
            # 단위 쌍 거리 ≤ 2 km
            gg = gdf[gdf.has_geom].reset_index(drop=True)
            tree = STRtree(gg.geometry.values); rows = []
            for i, geo in enumerate(gg.geometry.values):
                for j in tree.query(geo.buffer(2000)):
                    j = int(j)
                    if j <= i: continue
                    dd = geo.distance(gg.geometry.values[j])
                    if dd <= 2000: rows.append((int(gg.lab[i]), int(gg.lab[j]), round(float(dd), 2)))
            pd.DataFrame(rows, columns=['lab_a', 'lab_b', 'boundary_distance_m']).to_csv(os.path.join(d, 'unit_pairs.csv'), index=False)
            say(f"  unit_pairs.csv {len(rows):,}쌍 (≤2,000 m)")
    if not context_only: (gdf.drop(columns='geometry') if gdf is not None else U).to_csv(os.path.join(d, 'units.csv'), index=False, encoding='utf-8-sig')

    # ── 맥락 레이어 ──
    pts = [Point(x, y) for x, y in zip(U.x, U.y) if not (np.isnan(x) or np.isnan(y))]
    hull = gpd.GeoSeries(pts, crs='EPSG:5186').union_all().convex_hull.buffer(15_000)
    feats = [{'type': 'Feature', 'properties': pr, 'geometry': mapping(sh_transform(TO4326.transform, g))} for g, pr in ind_g if g.intersects(hull)]
    json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(d, 'context', 'ind_complex.geojson'), 'w', encoding='utf-8'), ensure_ascii=False)
    core = gpd.GeoSeries(pts, crs='EPSG:5186').union_all().convex_hull.buffer(1_000)
    ef = [f for g, f in emd['_g'] if g.intersects(core)]
    json.dump({'type': 'FeatureCollection', 'note': '단위 대표점 볼록껍질(+1 km)과 교차하는 읍면동(이웃 시군 일부 포함 · 경계 코드는 2026 개편 신 코드) · c=읍면동 코드 · n=이름 · s=계통 조회 상태(ok/unknown) · lo/hi=분산전원 잔여 연계가능용량 참고값 MW(한전 2026-08-19 조회 · 읍면동 단위 · 접속 보장 아님)', 'features': ef},
              open(os.path.join(d, 'context', 'emd_grid.geojson'), 'w', encoding='utf-8'), ensure_ascii=False)
    xp = [p for p in ex['pts'] if str(p[6]) == sgg]
    json.dump({'type': 'FeatureCollection', 'note': '기존 태양광 — 위치 검증(VALID)된 허가·설비 자료만 · 점 = 허가 주소(지번) 위치(패널 위치 아님) · 전수 아님 · 필드: kind(p=일반/y=영농형) status source',
               'features': [{'type': 'Feature', 'properties': {'kind': p[3], 'status': p[4], 'source': p[5], 'emd8': p[7]}, 'geometry': {'type': 'Point', 'coordinates': [p[0], p[1]]}} for p in xp]},
              open(os.path.join(d, 'context', 'existing_pv.geojson'), 'w', encoding='utf-8'), ensure_ascii=False)
    say(f"  context: 산단 {len(feats)} · 읍면동 {len(ef)} · 기존 시설 점 {len(xp)}")

    # ── README ──
    n3 = int((U.area_m2 >= 66_667).sum()); n50 = int((U.area_m2 >= 1_111_111).sum())
    open(os.path.join(d, 'README.md'), 'w', encoding='utf-8').write(f"""# {name} ({sgg}) — 클러스터링 방법론 자문용 데이터 (층 {stratum})

생성 {datetime.date.today().isoformat()} · 조건 R2_promo = 특별법 시행 후(농업진흥구역 설치 가능 · 농업보호구역 제외) · 법인·국공유 소유 농지 · 좌표계 EPSG:5186(gpkg·csv x,y) / WGS84(geojson)
**자문용 자료입니다.** 보고서·논문 인용 대상이 아니며, 수치는 정본 산출(`model/query.py`)과 시금석을 거친 값만 인용합니다. 자료 기준일은 사이트 「자료 기준일」 표와 같습니다(provenance 생성 {prov.get('generated', '')}).

요약: 21m 연접 단위 {len(U):,}곳(면적 하한 없음 · 이 시군에 필지가 하나라도 있는 단위) · 구성 필지 {len(P):,}개(이웃 시군 필지 {int((mem.sgg_p != sgg).sum()):,} 포함) · 면적 {U.area_m2.sum() / 1e6:.2f} km² · 3MW 이상 {n3} · 50MW 이상 {n50} · 1필지 단위 {int((U.n_parcel == 1).sum()):,}

**기하 결손(값으로 남김 · 조용히 빼지 않음)** — 지적도에서 찾지 못한 필지 {n_geom_missing_parcels if n_geom_missing_parcels is not None else '—'}개 · 그 때문에 폴리곤이 없는 단위 {n_geom_missing_units if n_geom_missing_units is not None else '—'}곳(`has_geom = False`, 속성은 전부 있음). 원인은 지번 코드 개편·지적 미등재 등이며(ADR-0047 회수 대응표 적용 후 잔여), 데이터 보완 과제로 관리한다.

## parcels — 적격 필지 (처음부터 다시 묶을 때 쓰는 층)
| 열 | 뜻 |
|---|---|
| pnu | 필지 고유번호(19자리) |
| lab | 현재 21m 연접 단위 번호(기준선) |
| sgg · emd8 | 시군 코드 · 읍면동 코드(PNU 앞 8자리) |
| area_ledger_m2 | 장부 면적(토지 원장) |
| jimok | 지목(전·답·과수원) |
| ownership · gov_org | 소유 유형(법인 · 국유지 · 시/도유지 · 군유지 등) · 국공유 관리기관 |
| agpromo · agpromo_zone | 농업진흥지역 여부 · 구분(농업진흥구역/농업보호구역) |
| farmmap_ratio · farmmap_matched | 팜맵 경작 판독 비율(참고 · 휴경 판단 아님) |
| slope_mean · slope_max | 경사 통계(단위 확인 중 — 도/퍼센트 미확정) |
| reclaim_register · reclaim_district · nat_managed_district | 농어촌공사 간척 원장 등재 여부 · 지구 · 국가관리간척지 |
| n_touch · d1 · d2 · d4 · d8 · d12 | 다른 적격 필지와의 접촉 수 · k번째 최근접 적격 필지까지 경계 거리(m) — 21m 유도에 쓴 값(S1 적격 전량 기준) |
| geometry (gpkg) | 연속지적도 필지 폴리곤 |

## units — 21m 연접 단위 (기준선)
| 열 | 뜻 |
|---|---|
| lab · n_parcel · area_m2 · mw_ref · size_band | 단위 번호 · 필지 수 · 장부 면적 합 · 0.045 kW/㎡ 환산 참고 MW · 규모 눈금(표시용) |
| share_corp · share_national · share_sido · share_gun | 구성 필지의 소유 유형 비율 |
| farm_ratio · reclaim_pct | 경작 판독 비율 · 간척 원장 필지 비중(%) |
| n_in_sgg · n_sgg · n_emd · n_emd_geom | 이 시군 안 필지 수 · 관여 시군 수 · 관여 읍면동 수 |
| x · y | 대표점(구성 필지 대표점의 면적 가중 평균, EPSG:5186) |
| dist_ind_km | 가장 가까운 산업단지 경계까지 거리 |
| lo · hi · cls | 읍면동 계통 여유 참고값 하한·상한(MW)·등급 — 접속 보장 아님 |
| in_top10_population · nondominated_3ax | 3MW 이상(TOP 10 모집단) 여부 · 그 안에서 3축(면적↑·계통 하한↑·산단 거리↓) 비지배 여부(시군 안 비교) |
| area_geom_m2 · has_geom · geometry (gpkg) | 필지 dissolve 폴리곤 면적(단순화 없음) · 기하 존재 여부 |

## unit_pairs — 단위 쌍 경계 거리(≤ 2,000 m)
lab_a · lab_b · boundary_distance_m. 2단계 묶음 규칙(거리 임계·그래프 등)을 시험할 때 기하 계산 없이 쓸 수 있다. 2 km 초과 쌍은 없다.

## context
ind_complex.geojson(산업단지 경계 · 유형 t) · emd_grid.geojson(읍면동 경계 + 계통 참고값) · existing_pv.geojson(기존 태양광 위치 확인분)

## 이 시군을 고른 이유
순위(TOP 10) 선정이 아니다 — 규모 프로파일 층 {stratum}, 산단·계통 조합, 지역이 10곳 안에서 고루 들어가도록 연구자가 고른 사례다. 기준 전문은 `docs/method_advisory/STUDY_AREAS.md`.
""")
    return {'sgg': sgg, 'name': name, 'stratum': stratum, 'n_units': int(len(U)), 'n_parcels': int(len(P)), 'km2': round(float(U.area_m2.sum() / 1e6), 2), 'n_ge3mw': n3, 'n_ge50mw': n50}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--sgg', nargs='*'); ap.add_argument('--no-geom', action='store_true'); ap.add_argument('--context-only', action='store_true', help='맥락 레이어·README·MANIFEST 만 다시 쓴다(기하·쌍 거리 유지)'); a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    con, bc, ind_g, ind_tree, emd, ex, prov = load_common()
    areas = [x for x in SA['areas'] if not a.sgg or x['sgg'] in a.sgg]
    summ = [build_sgg(x, con, bc, ind_g, ind_tree, emd, ex, prov, geom=not a.no_geom, context_only=a.context_only) for x in areas]
    man = {'generated': datetime.datetime.now().isoformat(timespec='seconds'), 'run': RUN, 'rule': SA['rule'], 'areas': summ, 'files': {}}
    for root, _, files in os.walk(OUT):
        for f in files:
            if f == 'MANIFEST.json': continue
            p = os.path.join(root, f); man['files'][os.path.relpath(p, OUT).replace(os.sep, '/')] = {'sha256': sha(p), 'bytes': os.path.getsize(p)}
    json.dump(man, open(os.path.join(OUT, 'MANIFEST.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(OUT, 'README.md'), 'w', encoding='utf-8').write(
        "# 클러스터링 방법론 자문 — 검토 대상지 10곳 데이터 패키지\n\n" + f"생성 {man['generated']} · 선정 기준 {SA['rule']} · 조건 {RUN}\n\n"
        "자문용 자료이며 보고서·논문 인용 대상이 아니다. 시군 폴더마다 README.md(열 사전)가 있다. 파일 지문은 MANIFEST.json.\n\n| 층 | 시군 | 코드 | 단위(전량) | 필지 | 면적 km² | 3MW↑ | 50MW↑ |\n|---|---|---|---:|---:|---:|---:|---:|\n" +
        '\n'.join(f"| {s['stratum']} | {s['name']} | {s['sgg']} | {s['n_units']:,} | {s['n_parcels']:,} | {s['km2']} | {s['n_ge3mw']} | {s['n_ge50mw']} |" for s in summ) + '\n')
    say('완료', json.dumps(summ, ensure_ascii=False))


if __name__ == '__main__':
    main()
