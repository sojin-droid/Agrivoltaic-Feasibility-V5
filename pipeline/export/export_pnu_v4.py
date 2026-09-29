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
# ── 현행 코드 → 원장 코드 다리 (감사 F-05) ──
# 원장 PNU 는 개편 전 법정동코드를 쓴다. 현행 PNU(개편 후 코드)로 검색하면 시군 파일을 못 찾는다.
# 근거는 bjd_code(code.go.kr 법정동코드 전체자료, 폐지 포함) 한 가지뿐이다 — 그 표가 **시도 통합(광주·전남 → 전남광주통합특별시)**
# 을 폐지(46·29)·신설(12) 쌍으로 싣고, 시도 이름 뒤의 법정동 이름이 **완전히 같다**. 이 경우만 잇는다:
#   · 원장 코드가 폐지(alive=False)이고 시도 접두가 46 또는 29
#   · 현행(alive) 코드 중 시도 접두 12 이고 시도 뒤 이름이 정확히 같은 코드가 **정확히 1개**
#   · 역방향도 1:1 (한 현행 코드에 원장 코드 둘이 붙으면 둘 다 버린다)
# 부분 문자열·이름 어간·공간 매칭은 쓰지 않는다. 인천 구 개편(28)·화성 구 신설(41590) 등은 이름이 바뀌어 근거가 없으므로 잇지 않는다
# (그 코드는 화면이 '원장 코드와 연결 근거 없음 — 지번으로 검색' 으로 안내한다). 필지 본번·부번은 행정코드 개편으로 바뀌지 않는다는 전제를 쓴다.
lc2 = duckdb.connect(DB, read_only=True)
_rows = lc2.execute("SELECT code10, name_full, alive FROM bjd_code").fetchall()
lc2.close()
_led = {r[0] for r in bjd}
_alive12 = {}
for c, nm, al in _rows:
    if al and c.startswith('12'):
        _alive12.setdefault(' '.join(nm.split()[1:]), []).append(c)
_info = {c: (nm, al) for c, nm, al in _rows}
_pairs = {}
for c in _led:
    if c in _info and not _info[c][1] and c[:2] in ('46', '29'):
        t = _alive12.get(' '.join(_info[c][0].split()[1:]), [])
        if len(t) == 1 and t[0] not in _led:
            _pairs.setdefault(t[0], []).append(c)
bridge = {new: olds[0] for new, olds in _pairs.items() if len(olds) == 1}
_dead_led = sorted(c for c in _led if c in _info and not _info[c][1])
bridge_unlinked = sorted(set(_dead_led) - set(bridge.values()))
print(f"코드 다리: 현행→원장 {len(bridge):,} (광주·전남 통합 · 이름 완전 일치 1:1) · 원장의 폐지 코드 {len(_dead_led):,} 중 근거 없어 잇지 않음 {len(bridge_unlinked):,}")
miss = [r[0] for r in bjd if r[1] is None]
rows = [[r[0], r[1]] for r in bjd if r[1]]
with gzip.open(os.path.join(SITE, 'data_v4', 'bjd_v4.json.gz'), 'wt', encoding='utf-8') as fo:
    json.dump({'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'source': 'bjd_code(code.go.kr 2026-08-19, 폐지 포함) ∩ ledger.region(원장 PNU 앞 10자리)',
               'n': len(rows), 'unmapped_codes': miss, 'rows': rows,
               'bridge': bridge, 'bridge_rule': '현행 법정동코드 → 원장(개편 전) 코드. bjd_code 의 폐지 46·29 ↔ 신설 12(전남광주통합특별시) 중 시도 뒤 이름 완전 일치 1:1 만. 그 외 개편(인천 구·화성 구 등)은 근거 없음 — 잇지 않음.',
               'n_dead_ledger_codes': len(_dead_led), 'n_dead_unlinked': len(bridge_unlinked)}, fo, ensure_ascii=False, separators=(',', ':'))
print(f"bjd_v4: {len(rows):,} codes · 이름 없는 원장 코드 {len(miss)}")
json.dump({'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'runs': RUNS, 'gates': gates, 'n_sgg': len(per),
           'class_rule': '① 적격 + 규모 기준 이상 단위 포함 · ② 적격이나 규모 기준 미달 · ③ 분석 기준 적격 목록에 없음(부적격 단정 아님)'},
          open(os.path.join(SITE, 'data_v4', 'pnu_index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
