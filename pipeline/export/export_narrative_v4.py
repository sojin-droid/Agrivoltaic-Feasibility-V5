# -*- coding: utf-8 -*-
"""5단 결론 서사 수치 export — data_v4/narrative_v4.json (ADR-0038 포함).

전량 model/query.py 표준 질의·scenario_runs 등재분에서만 산출(즉석 정의 없음).
게이트: scenario_runs의 R0_current(정본)·R0_current@all(대조군)이 표준 질의 값과
     어긋나면 중단. 앵커는 폐지됐다(ADR-0040 §2) — R0 는 기준값이 아니라 한 칸이다.
사용: python pipeline/export/export_narrative_v4.py
"""
import os, sys, json, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, OUT, CLUSTERS, ROOT, MODEL, LR, CAD   # 경로는 한 곳에서만
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, MODEL)
import query as Q


con = Q.db()
# ── 게이트: 대조군 R0 = 상수 · 정본 R0 = 매트릭스 정본과 일치 ──
a = con.execute("""SELECT n_eligible, eligible_area_km2
                   FROM scenario_runs WHERE name='R0_current@all'""").fetchone()
assert a and a[0] == Q.R0_ALL_N and abs(a[1] - Q.R0_ALL_M2/1e6) < 0.01, \
    f"[FAIL] R0 대조군 ≠ 상수(ADR-0040): {a}"
b = con.execute("""SELECT n_eligible, eligible_area_km2
                   FROM scenario_runs WHERE name='R0_current'""").fetchone()
_mx = [r for r in Q.matrix_data(universe='pubcorp')
       if r['pop'] == '전국' and r['cell'] == 'R0' and r['phase'] == '본값'][0]
assert b and b[0] == _mx['n'], f"[FAIL] R0 정본 런 ≠ 매트릭스 정본: {b} vs {_mx['n']}"

# ── 런 요약 + 크기 분포 ──
# 정본 8칸 + 대조군 8칸 — 이름은 ADR-0040 개명판. 구 이름(ANCHOR·SOFT_*·*_CP)은 뜻이
# 달라 그대로 옮기면 안 된다(구 ANCHOR 는 소유 무필터, 신 R0_current 는 정본 우주).
RUNS = ['R0_current', 'R0_current_SB', 'R1_protect', 'R1_protect_SB',
        'R2_promo', 'R2_promo_SB', 'R3_zone_all', 'R3_zone_all_SB',
        'R0_current@all', 'R0_current_SB@all', 'R1_protect@all', 'R1_protect_SB@all',
        'R2_promo@all', 'R2_promo_SB@all', 'R3_zone_all@all', 'R3_zone_all_SB@all']
size = {d['run']: d for d in Q.clusters_size_data(RUNS)}
runs = {}
for name, ne, ek, nl, lk, mw in con.execute(f"""
    SELECT name, n_eligible, eligible_area_km2, n_component, component_area_km2, m_total_mw
    FROM scenario_runs WHERE name IN ({','.join(['?']*len(RUNS))})""", RUNS).fetchall():
    s = size.get(name, {})
    # θ 폐지(ADR-0041) — 등재가 아니라 **연접 구획 전량**이다. 크기 기준은 대역으로만 본다.
    runs[name] = {'n_eligible': ne, 'eligible_km2': ek, 'n_component': nl,
                  'component_km2': lk, 'mw': round(mw or 0),
                  'ge50': s.get('ge50'), 'ge100': s.get('ge100'),
                  'ge50_km2': round(s.get('ge50_km2', 0.0), 1),
                  'ge50_mw': round(s.get('ge50_km2', 0.0) * 1e6 * Q.KW / 1e3),
                  'max_ha': round(s.get('max_ha', 0))}

# ── 소유 × 이격 (필지층) ──
owner_sb = Q.owner_setback_data()

# ── 대형 구획(무필터)의 소유 구성 — 국공유 = 02/04/05, 법인 = 06 (ADR-0038 코드 확정) ──
NODES = os.path.join(LR, 'engine_cache', 'nodes.parquet').replace('\\', '/')
T50 = 50_000 / Q.KW
comp = {}
for run in ['R0_current@all', 'R2_promo@all']:
    mp = os.path.join(LR, 'scenario_runs', run, 'members.parquet').replace('\\', '/')
    r = con.execute(f"""
      WITH m AS (SELECT lab, pnu FROM read_parquet('{mp}')),
      ca AS (SELECT lab, SUM(n.area) a FROM m JOIN read_parquet('{NODES}') n USING(pnu)
             GROUP BY lab HAVING a >= {T50}),
      c AS (SELECT m.lab, SUM(l.calculatedarea) tot,
              SUM(l.calculatedarea) FILTER (l.ownership IN ('02','04','05','06')) op,
              SUM(l.calculatedarea) FILTER (l.ownership='01') indiv
            FROM m JOIN ca USING(lab) JOIN ledger l USING(pnu) GROUP BY m.lab)
      SELECT COUNT(*), COUNT(*) FILTER (COALESCE(op,0)/tot >= 0.5),
             100*SUM(COALESCE(indiv,0))/SUM(tot) FROM c""").fetchone()
    comp[run] = {'ge50': r[0], 'majority_op': r[1], 'indiv_share_pct': round(r[2], 0)}

# ── CP 대형 구획 소재(상위) — 간척 여부·지구명 ──
def cp_big_of(run):
    cpp = os.path.join(LR, 'scenario_runs', run, 'clusters.parquet').replace('\\', '/')
    mpp = os.path.join(LR, 'scenario_runs', run, 'members.parquet').replace('\\', '/')
    out = []
    for lab, mw, n, rec, dist, sgg in con.execute(f"""
        WITH big AS (SELECT lab, mw FROM read_parquet('{cpp}') WHERE mw >= 50),
        m AS (SELECT b.lab, b.mw, mm.pnu FROM big b JOIN read_parquet('{mpp}') mm USING(lab))
        SELECT m.lab, ANY_VALUE(m.mw), COUNT(*),
          100.0*COUNT(*) FILTER (rt.pnu IS NOT NULL)/COUNT(*),
          ANY_VALUE(rt.ekr_district), MODE(SUBSTR(m.pnu,1,5))
        FROM m LEFT JOIN reclaim_tag rt USING(pnu)
        GROUP BY m.lab ORDER BY 2 DESC""").fetchall():
        out.append({'id': int(lab), 'mw': round(mw), 'n': n, 'reclaim_pct': round(rec),
                    'district': dist, 'sgg': sgg})
    return out

cp_top = cp_big_of('R2_promo')
cp_top_sb = cp_big_of('R2_promo_SB')
cp_top_anchor = cp_big_of('R0_current')
con.close()

out = {
    'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
    'edition': '3판 — 우주 = 법인·국공유(ADR-0040) · 등재 문턱 폐지(ADR-0041) · '
               '실경작 비율은 적격 조건 아님(ADR-0039)',
    'universe': {'정본': 'pubcorp — 국공유(02·04·05)+법인(06)',
                 '대조군': 'all — 무필터, 정책 값 아님(병기 전용)'},
    'kw_per_m2': Q.KW,
    'threshold': {'mw50_m2': round(50_000/Q.KW), 'mw100_m2': round(100_000/Q.KW),
                  'mw50_ha': round(50_000/Q.KW/1e4, 1), 'mw100_ha': round(100_000/Q.KW/1e4, 1)},
    'runs': runs,
    'owner_setback': owner_sb,
    'big_composition': comp,
    'cp_big': cp_top,
    'cp_big_sb': cp_top_sb,
    'cp_big_anchor': cp_top_anchor,
}
fo = os.path.join(SITE, 'data_v4', 'narrative_v4.json')
json.dump(out, open(fo, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"완료 — narrative_v4.json ({out['generated']}) · 런 {len(runs)} · CP 대형 {len(cp_top)}")
