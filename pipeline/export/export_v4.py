# -*- coding: utf-8 -*-
"""data_v4 export — 정본(model/query.py)의 함수를 직접 불러 사이트 데이터를 만든다.
원칙 1(단일 출처): 이 스크립트에는 판정 SQL이 없다. 조건이 바뀌면 query.py 한 곳만 바뀐다.
원칙 13(게이트): matrix_data()가 T14 불일치 시 스스로 중단하므로 어긋난 값은 파일이 되지 않는다.

사용: python pipeline/export/export_v4.py            (사이트 레포 어디서든)
출력: data_v4/summary_v4.json · sgg_matrix.json · meta_v4.json
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, OUT, CLUSTERS, ROOT, MODEL, LR, CAD   # 경로는 한 곳에서만
from datetime import datetime
# stdout 래핑은 query.py가 import 시 수행 — 여기서 중복 래핑하면 버퍼가 닫힌다

sys.path.insert(0, MODEL)
import query as Q                     # 정본 질의 모듈
from engine.grid_spec import load as load_grid, DEFAULT_GRID

os.makedirs(OUT, exist_ok=True)

def save(name, obj):
    fp = os.path.join(OUT, name)
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    print(f"  {name}: {os.path.getsize(fp)/1e3:.0f} KB")

GEN = datetime.now().strftime('%Y-%m-%d %H:%M')

# ── 1. summary_v4: 매트릭스(전국·간척) + 풀 분해 + 소유 세 무리 ─────────────
# 정본(법인·국공유)과 대조군(무필터)을 **둘 다** 낸다 — 정본 단독 제시 금지(제2조).
# 각 우주는 자기 검증을 내장한다(정본은 런 산출과, 대조군은 상수와 일치) — 실패 시 중단.
rows = Q.matrix_data(universe='pubcorp')
rows_ctl = Q.matrix_data(universe='all')
def cell(pop, code, phase, src=None):
    src = rows if src is None else src
    r = [x for x in src if x['pop'] == pop and x['cell'] == code and x['phase'] == phase][0]
    # m2 원값 동봉 — MW 참고 환산은 반올림 km²가 아니라 원값에서 (브리프와 자릿수 일치)
    return {'n': r['n'], 'km2': round(r['m2']/1e6, 1), 'm2': round(r['m2'], 2)}

# 키 이름 = query.py 의 phase 그대로 ('본값' = 정본, '구정의' = 폐지된 ρ≥0.30 참고값).
# 구판 키 '전'/'후' 는 쓰지 않는다 — 같은 자리에 뜻이 다른 값이 들어가는 사고를 막는다
# (구 '전' = 새 '본값', 구 '후' = 새 '구정의').
# 키: '정본' = 법인·국공유 우주(ADR-0040), '대조군' = 무필터. 구판 키('본값'/'구정의',
# 그 전의 '전'/'후')는 뜻이 달라 쓰지 않는다 — 같은 자리에 다른 값이 들어가는 사고를 막는다.
matrix = {pop: {code: {'name': name,
                       '정본': cell(pop, code, '본값'),
                       '대조군': cell(pop, code, '본값', rows_ctl)}
                for code, name, _ in Q.MATRIX_ZONES}
          for pop in ['전국', '간척']}

# 풀 분해(서로소·가산): 보호 = R1−R0, 진흥 = R2−R0 — ㎡ 원값 차분 후 반올림 (반올림값끼리 빼면 0.1 오차)
pools = {}
for pop in ['전국', '간척']:
    pools[pop] = {}
    for pool, hi in [('보호구역', 'R1'), ('진흥구역', 'R2')]:
        _src = {'정본': rows, '대조군': rows_ctl}
        pools[pop][pool] = {ph: {'n': cell(pop, hi, '본값', _src[ph])['n']
                                      - cell(pop, 'R0', '본값', _src[ph])['n'],
                                 'km2': round((cell(pop, hi, '본값', _src[ph])['m2']
                                               - cell(pop, 'R0', '본값', _src[ph])['m2'])/1e6, 1),
                                 'm2': round(cell(pop, hi, '본값', _src[ph])['m2']
                                             - cell(pop, 'R0', '본값', _src[ph])['m2'], 2)}
                            for ph in ['정본', '대조군']}

groups = Q.owner_groups_data()
owner = [{'group': g['group'], 'n': g['n'], 'km2': round(g['m2']/1e6, 1),
          'anchor_n': g['anchor_n'], 'anchor_km2': round(g['anchor_m2']/1e6, 1),
          'zones': {z: {'n': v[0], 'km2': round(v[1]/1e6, 1)} for z, v in g['zones'].items()}}
         for g in groups]

# 판정 보류(용도지역 미상) 병기값 — 엔진 ANCHOR summary에서 (ADR-0035)
pend = {}
_asp = os.path.join(LR, 'scenario_runs',
                    'R0_current', 'summary.json')
if os.path.exists(_asp):
    pend = json.load(open(_asp, encoding='utf-8')).get('pending_zone_null', {})

_r0 = cell('전국', 'R0', '본값')
_r0c = cell('전국', 'R0', '본값', rows_ctl)
save('summary_v4.json', {
    'generated': GEN,
    'unit_note': '1차 단위 km². 참고 MW = 면적(㎡)×0.045/1000 (GCR 0.225×효율 0.20 가정) — 표시 시 가정 병기',
    # 앵커는 폐지됐다(ADR-0040 §2) — R0 칸은 남되 '기준값'이 아니라 한 칸일 뿐이다.
    # 정본은 런 산출에서, 대조군은 상수에서 온다.
    'anchor': {'n': _r0['n'], 'km2': round(_r0['m2']/1e6, 2), 'm2': _r0['m2'],
               'def': '우주 = 법인(06)+국공유(02·04·05) (ADR-0040) ∧ 지목 농지 ∧ 물리 통과'
                      '(건물·수역·산단 없음) ∧ ¬경사15 ∧ ¬지목결측 ∧ ¬개발제한 ∧ ¬보전관리 '
                      '∧ ¬보전녹지 (실경작 비율은 적격 조건 아님 — ADR-0039)',
               'touchstone': '정본 R0 = R0_current 런 산출과 일치 검증 · 대조군 R0 = 상수 정확 일치',
               'control': {'n': _r0c['n'], 'km2': round(_r0c['m2']/1e6, 2),
                           'def': '무필터(전 소유) 대조군 — 정본 아님, 병기 전용'},
               'legacy': {'n': Q.R0_ALL_LEGACY_N, 'km2': round(Q.R0_ALL_LEGACY_M2/1e6, 2),
                          'def': '구 정의 ρ≥0.30 — 폐지(참고값, 정책 인용 금지)'},
               'pending_zone_null': pend},
    'matrix': matrix,          # 독립 조합 R0–R3 · 각 정본/대조군 — 누적 사다리 아님
    'reclaim_ledger': Q.reclaim_ledger_data(),   # 화면 산문이 쓰던 45,193 — 이제 렌더
    'pools': pools,            # R1−R0(보호)·R2−R0(진흥), 서로소라 정확
    'owner_groups': owner,     # 유형 구분(개인 식별 아님)
})

# ── 1b. funnel: 전국 깔때기 (전체 → 전답과 → R0 대조군) ───────────────────
# ADR-0039: 실경작 비율은 적격 조건이 아니므로 깔때기 단계에서 제외한다. 팜맵 실측률과
# 구 정의(ρ≥0.30) 통과 수는 참고 항목(_ 접두)으로만 남긴다 — 단계로 그리면 폐지된 조건이
# 다시 판정처럼 읽힌다.
comp = Q.composition_data()
tot = comp[['전체필지', '전답과', '지목결측', '팜맵실측', '구정의30통과', '앵커적격']].sum()
funnel = {
    '전체 필지': int(tot['전체필지']),
    '지목 전·답·과수원': int(tot['전답과']),
    '현행법 적격(무필터 대조군)': int(tot['앵커적격']),
    '_지목결측': int(tot['지목결측']),
    '_팜맵 공간교차 실측': int(tot['팜맵실측']),
    '_구 정의(실경작 30% 이상)': int(tot['구정의30통과']),
}
save('funnel_v4.json', {'generated': GEN, 'national': funnel,
                        'note': '깔때기는 **무필터 대조군** 기준이다 — 소유 우주를 걸기 전의 '
                                '전국 선별 과정을 보이기 위한 것(정본은 여기서 다시 8.8%로 좁혀진다). '
                                '지목결측은 구제 필지(복구 진행 중). _ 접두 항목은 참고값(단계 아님)'})

# ── 2. sgg_matrix: 시군별 R0–R3 (지도 채색·시군 표) ─────────────────────────
srows = Q.matrix_data(group_by='sgg', universe='pubcorp')
srows_ctl = Q.matrix_data(group_by='sgg', universe='all')
# 시군 이름: 표준 경계 자산(sgg_boundary)에서 — 전 시군 커버 (config.toml 경로 단일 출처)
import toolconf
import geopandas as gpd
SIDO = {'11': '서울', '26': '부산', '27': '대구', '28': '인천', '29': '광주', '30': '대전',
        '31': '울산', '36': '세종', '41': '경기', '43': '충북', '44': '충남', '46': '전남',
        '47': '경북', '48': '경남', '50': '제주', '51': '강원', '52': '전북'}
bnd = gpd.read_file(toolconf.BND, columns=['sgg_cd', 'sgg_cd_new', 'sgg_nm'],
                    ignore_geometry=True)
names = {}
for r in bnd.itertuples():                    # 신구 코드 모두 등록 (PNU는 신코드 체계)
    for c in {str(r.sgg_cd), str(getattr(r, 'sgg_cd_new', '') or r.sgg_cd)}:
        names[c] = f"{SIDO.get(c[:2], '')} {r.sgg_nm}".strip()
# 2023 경계 이후 신설·개편 구 보완 (행정 표준명 — 수치 아님)
names.update({'27720': '대구 군위군', '28177': '인천 미추홀구',
              '41192': '경기 부천시원미구', '41194': '경기 부천시소사구',
              '41196': '경기 부천시오정구', '41670': '경기 여주시',
              '43112': '충북 청주시서원구', '43114': '충북 청주시청원구'})
sgg = {}
for uname, src in [('정본', srows), ('대조군', srows_ctl)]:
    for r in src:
        if r['phase'] != '본값':
            continue
        d = sgg.setdefault(r['sgg'], {'name': names.get(r['sgg'], r['sgg'])})
        d.setdefault(r['cell'], {})[uname] = {'n': r['n'], 'km2': round(r['m2']/1e6, 2)}
save('sgg_matrix.json', {'generated': GEN, 'codes': sgg,
                         'note': '시군별 실측값이 1차 산출 — 반경·구간 묶음 없음. '
                                 '칸마다 정본(법인·국공유)과 대조군(무필터)을 함께 둔다 — '
                                 '정본 단독 제시 금지(제2조)'})

# ── 3. meta_v4: 계보 (각 페이지 푸터의 근거) ────────────────────────────────
con = Q.db()
lineage = [{'tbl': t, 'built': str(b), 'source': s, 'layer': (l or '')}
           for t, b, s, l in con.execute(
               "SELECT tbl, built, source, layer FROM meta_versions ORDER BY layer, tbl").fetchall()]
con.close()
# 판 표식은 격자 선언에서 읽는다 — 여기에 적으면 판이 바뀔 때마다 사람이 고쳐야 하고,
# 실제로 3판 문자열이 4판 산출물 위에 남아 있었다.
_g = load_grid(DEFAULT_GRID)
save('meta_v4.json', {'generated': GEN,
                      'data_generation': f'{_g.edition} · {_g.name} · {_g.note}',
                      'grid': {'name': _g.name, 'edition': _g.edition,
                               'sha12': _g.sha12, 'n_runs': len(_g.plan())},
                      'verification': 'export 시 앵커 상수 정확 일치 검증 통과 (T16-①)', 'lineage': lineage})

print(f"완료 — data_v4/ (생성 {GEN})")
