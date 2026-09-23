# -*- coding: utf-8 -*-
"""PNU · 지번 검색 자산 export — data_v4/pnu/{sgg}.json.gz · data_v4/bjd_v4.json.gz (V5.5 · GGI 검토 §20).

무엇을 담는가
  pnu/{sgg}.json.gz  시나리오별(시행 전 R0_current · 진흥구역 개방 R2_promo · 농업진흥지역 전체 개방 R3_zone_all)
                     적격 필지 → 소속 21m 공간 분석 단위(lab) 사전 + 단위별 [장부면적 ㎡, 필지 수]
                     → 화면은 ① 적격 + 규모 기준 이상 단위 포함 ② 적격이나 규모 기준 미달 ③ 적격 목록에 없음 을 구분한다.
                     ③ 은 '부적격' 이 아니다 — 지목·소유(개인 소유는 분석 기준 밖)·제외조건 어느 것인지 이 자산은 구분하지 않는다.
  bjd_v4.json.gz     지번 → PNU 변환용 법정동코드(원장 PNU 앞 10자리 = 원장 표기 코드) → 법정동 전체 이름.
                     bjd_code(code.go.kr 2026-08-19 · 폐지 포함) 에서 원장에 실제 등장하는 코드만.
원천: Ledger_Rebuild/scenario_runs/{run}/members.parquet(pnu, lab) · clusters.parquet(lab, area_m2, n_parcel) · DuckDB ledger.region · bjd_code
새 판정 없음 — 등재 런의 소속표를 그대로 옮긴다. 게이트: 시나리오별 필지 수 = members 행 수 · 단위 면적 합 = clusters 합.
사용: python pipeline/export/export_pnu_v4.py
"""
import os, sys, json, gzip, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, LR
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import duckdb

RUNS = ['R0_current', 'R2_promo', 'R3_zone_all']
DB = os.path.join(LR, 'agrivoltaic_ledger_v1.duckdb')
con = duckdb.connect()
per = {}          # sgg → run → {'p': {pnu: lab}, 'u': {lab: [a, n]}}
gates = {}
for run in RUNS:
    mp = os.path.join(LR, 'scenario_runs', run, 'members.parquet').replace('\\', '/')
    cp = os.path.join(LR, 'scenario_runs', run, 'clusters.parquet').replace('\\', '/')
    n_members = con.execute(f"SELECT COUNT(*) FROM read_parquet('{mp}')").fetchone()[0]
    rows = con.execute(f"""SELECT m.pnu, m.lab, c.area_m2, c.n_parcel FROM read_parquet('{mp}') m JOIN read_parquet('{cp}') c USING(lab)""").fetchall()
    assert len(rows) == n_members, f'[FAIL] {run}: members {n_members} ≠ join {len(rows)} (clusters 에 없는 lab)'
    a_clusters = con.execute(f"SELECT SUM(area_m2) FROM read_parquet('{cp}')").fetchone()[0]
    seen = {}
    for pnu, lab, a, n in rows:
        s = pnu[:5]
        d = per.setdefault(s, {}).setdefault(run, {'p': {}, 'u': {}})
        d['p'][pnu] = int(lab)
        if lab not in seen:
            seen[lab] = True
        d['u'][int(lab)] = [round(float(a)), int(n)]
    a_units = sum(v[0] for s in per for v in per[s].get(run, {'u': {}})['u'].values())
    # 걸침 단위는 여러 시군 파일에 실리므로 합계는 고유 lab 기준으로 검증
    uniq = {}
    for s in per:
        for lab, v in per[s].get(run, {'u': {}})['u'].items(): uniq[lab] = v[0]
    assert abs(sum(uniq.values()) - float(a_clusters)) <= len(uniq), f'[FAIL] {run}: 단위 면적 합 불일치 {sum(uniq.values())} vs {a_clusters}'
    gates[run] = {'n_members': n_members, 'n_units': len(uniq), 'area_km2': round(float(a_clusters) / 1e6, 2)}
    print(f"{run}: 필지 {n_members:,} · 단위 {len(uniq):,} · {gates[run]['area_km2']} km²")

out_dir = os.path.join(SITE, 'data_v4', 'pnu'); os.makedirs(out_dir, exist_ok=True)
tot = 0
for s, runs in per.items():
    with gzip.open(os.path.join(out_dir, f'{s}.json.gz'), 'wt', encoding='utf-8') as fo:
        json.dump({'sgg': s, 'runs': runs}, fo, ensure_ascii=False, separators=(',', ':'))
    tot += os.path.getsize(os.path.join(out_dir, f'{s}.json.gz'))
print(f"pnu/ {len(per)} files · {tot/1024/1024:.1f} MB")

# ── 법정동코드(원장 표기) → 이름 ──
lc = duckdb.connect(DB, read_only=True)
bjd = lc.execute("""SELECT r.region AS code10, b.name_full, b.emd8 FROM (SELECT DISTINCT region FROM ledger) r
                    LEFT JOIN bjd_code b ON b.code10 = r.region ORDER BY r.region""").fetchall()
lc.close()
miss = [r[0] for r in bjd if r[1] is None]
rows = [[r[0], r[1]] for r in bjd if r[1]]
with gzip.open(os.path.join(SITE, 'data_v4', 'bjd_v4.json.gz'), 'wt', encoding='utf-8') as fo:
    json.dump({'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'source': 'bjd_code(code.go.kr 2026-08-19, 폐지 포함) ∩ ledger.region(원장 PNU 앞 10자리)',
               'n': len(rows), 'unmapped_codes': miss, 'rows': rows}, fo, ensure_ascii=False, separators=(',', ':'))
print(f"bjd_v4: {len(rows):,} codes · 이름 없는 원장 코드 {len(miss)}")
json.dump({'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'runs': RUNS, 'gates': gates, 'n_sgg': len(per),
           'class_rule': '① 적격 + 규모 기준 이상 단위 포함 · ② 적격이나 규모 기준 미달 · ③ 분석 기준 적격 목록에 없음(부적격 단정 아님)'},
          open(os.path.join(SITE, 'data_v4', 'pnu_index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
