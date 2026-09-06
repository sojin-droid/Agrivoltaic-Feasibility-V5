# -*- coding: utf-8 -*-
"""인사이트 탭 데이터 export — 구획 색인·필지층 매트릭스·격자에서 유형별 전수 계산.
원칙 1: 페이지는 이 파일의 산출(insights_v4.json)만 렌더. 계산식은 인사이트 노트와 동일.
사용: python pipeline/export/export_insights_v4.py"""
import os, sys, json, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, OUT, CLUSTERS, ROOT, MODEL, LR, CAD   # 경로는 한 곳에서만
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

B = os.path.join(SITE, 'data_v4')
idx = json.load(open(f'{B}\\clusters_index.json', encoding='utf-8'))['sgg']
codes = json.load(open(f'{B}\\sgg_matrix.json', encoding='utf-8'))['codes']
res = json.load(open(f'{B}\\results_v4.json', encoding='utf-8'))['runs']
summ = json.load(open(f'{B}\\summary_v4.json', encoding='utf-8'))

def v(c, cell):
    e = idx.get(c, {}).get(cell)
    return e['km2'] if e else 0.0


def k(c, cell):
    """시군별 연접 구획 **수**. θ 폐지 후 면적은 필지 면적과 같아지므로, 병합의 실체는
    수에만 남는다(병합은 면적이 아니라 덩어리 수를 바꾼다)."""
    e = idx.get(c, {}).get(cell)
    return e['k'] if e else 0

rows = []
for c in set(list(idx.keys()) + list(codes.keys())):
    r = dict(c=c, nm=codes.get(c, {}).get('name', c),
             r0=v(c, 'R0_current'), r0s=v(c, 'R0_current_SB'),
             a1=v(c, 'R1_protect'), a1s=v(c, 'R1_protect_SB'),
             r2=v(c, 'R2_promo'), r3=v(c, 'R3_zone_all'))
    r['protInc'] = round(r['a1'] - r['r0'], 2)
    r['protIncS'] = round(r['a1s'] - r['r0s'], 2)
    r['k0'], r['k1'] = k(c, 'R0_current'), k(c, 'R1_protect')
    r['k2'], r['k3'] = k(c, 'R2_promo'), k(c, 'R3_zone_all')
    r['np0'] = codes.get(c, {}).get('R0', {}).get('정본', {}).get('n', 0)
    rows.append(r)

# ① 보호 증분 이격 소멸 16곳형
wipe = sorted([r for r in rows if r['protInc'] >= 0.3 and r['protIncS'] <= 0.05],
              key=lambda r: -r['protInc'])
keepers = sorted([r for r in rows if r['protInc'] >= 0.3 and r['protIncS'] >= 0.8*r['protInc']],
                 key=lambda r: -r['protInc'])
n_base = sum(1 for r in rows if r['protInc'] >= 0.3)

# ③ 생존율 분포 (R0≥5)
# 정본 우주는 대조군의 8.8% 규모라 구판 기준(5km²)을 그대로 쓰면 24시군만 남는다.
# 기준을 1km²로 낮춘다 — 기준을 바꿨다는 사실은 산출물에 적어 둔다(아래 note).
surv = sorted([dict(nm=r['nm'], c=r['c'], r0=round(r['r0'], 1), r0s=round(r['r0s'], 1),
                    pct=round(100*r['r0s']/r['r0'], 1))
               for r in rows if r['r0'] >= 1], key=lambda x: x['pct'])

# ④ 시너지
# 병합 흡수 = 보호구역을 단독으로 열 때 생기는 구획 수 증가 − 진흥과 함께 열 때의 증가.
# 양수면 그만큼이 인접 진흥 구획에 붙어 새 덩어리가 되지 않았다는 뜻이다.
syn = sorted([dict(nm=r['nm'], c=r['c'],
                   syn=(r['k1']-r['k0']) - (r['k3']-r['k2']),
                   prot=r['k1']-r['k0'], both=r['k3']-r['k2'])
              for r in rows], key=lambda x: -x['syn'])[:10]
# θ 폐지(ADR-0041) — 등재가 아니라 연접 구획 전량 면적이다
_ca = lambda k: res[k]['component_area_km2']
_nc = lambda x: res[x]['n_component']
syn_nat = ((_nc('R1_protect') - _nc('R0_current'))
           - (_nc('R3_zone_all') - _nc('R2_promo')))

# ⑤ 뭉침도 — 구획당 평균 필지 수. θ 폐지로 '필지→구획 전환율'은 항상 100%가 되어
# 뜻을 잃었다(면적이 같아진다). 병합이 실제로 무엇을 했는지는 **덩어리 수**에 남는다.
conv = []
for r in rows:
    if r['k0'] >= 50 and r['np0'] >= 100:      # 표본이 너무 작은 시군은 비율이 튄다
        conv.append(dict(nm=r['nm'], c=r['c'], pk=r['np0'], ck=r['k0'],
                         pct=round(r['np0']/r['k0'], 2)))
conv.sort(key=lambda x: x['pct'])

# ② 전국 이격 감소율
nat = [dict(t=t, pre=_ca(a), post=_ca(b),
            drop=round(100*(_ca(a)-_ca(b)) / _ca(a), 1))
       for a, b, t in [('R0_current', 'R0_current_SB', '진흥✕·보호✕'),
                       ('R1_protect', 'R1_protect_SB', '+보호구역'),
                       ('R2_promo', 'R2_promo_SB', '+진흥구역'),
                       ('R3_zone_all', 'R3_zone_all_SB', '둘 다')]]

# 실경작 30% 미만 비중 — 정본 우주에서 본값 대비 구 정의(ρ≥0.30)의 차. 표준 질의 직접 호출
# (제1조: 즉석 SQL 금지 — query.py 가 유일한 출구다).
sys.path.insert(0, MODEL)
import query as Q
_mx = Q.matrix_data(universe='pubcorp')


def _lowratio(pop):
    g = lambda ph: [r for r in _mx if r['pop'] == pop and r['cell'] == 'R3'
                    and r['phase'] == ph][0]['m2']
    b, l = g('본값'), g('구정의')
    return round(100 * (b - l) / b, 1) if b else None


# ⑧ 간척 특화 (필지층 매트릭스·소유)
K = summ['matrix']['간척']
NA = summ['matrix']['전국']
og = {g['group']: g for g in summ['owner_groups']}
reclaim = dict(
    # 실경작 30% 미만 면적 비중 (서술 지표 — 적격 조건 아님, ADR-0039).
    # summary_v4 는 정본/대조군만 담으므로 구 정의 층은 표준 질의에서 직접 받는다.
    lowratio_reclaim=_lowratio('간척'),
    lowratio_nat=_lowratio('전국'),
    prot_inc=round(K['R1']['정본']['km2']-K['R0']['정본']['km2'], 1),
    r2_share=round(100*(K['R2']['정본']['km2']-K['R0']['정본']['km2'])
                   / (K['R3']['정본']['km2']-K['R0']['정본']['km2']), 1),
    out_anchor=og['간척지 외 법인']['anchor_km2'],
    in_anchor=og['간척지 내 법인']['anchor_km2'],
    pool=og['간척지 내 비법인']['km2'],
    lease_ratio=round(og['간척지 내 비법인']['km2']/og['간척지 외 법인']['anchor_km2'], 2),
    r0=K['R0']['정본']['km2'], r2=K['R2']['정본']['km2'],
)

out = dict(generated=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
           note=('θ 폐지(ADR-0041) 반영: 병합 시너지와 뭉침도는 **면적이 아니라 구획 수** '
                 '기준이다 — 문턱이 없으면 구획 면적 = 필지 면적이고 구역은 서로소라 면적 '
                 '시너지는 항등적으로 0이다(구판 +125.6km²는 문턱이 만든 현상). '
                 '생존율 대상 기준은 정본 규모에 맞춰 5km² → 1km²로 낮췄다.'),
           universe='정본(법인·국공유) — 대조군 병기는 근거 탭 표가 맡는다',
           n_base=n_base, wipe=wipe, keepers=keepers[:3],
           surv=surv, syn=syn, syn_nat=syn_nat, conv=conv, nat=nat, reclaim=reclaim)
fp = os.path.join(B, 'insights_v4.json')
json.dump(out, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print(f"insights_v4.json: 소멸형 {len(wipe)} · 생존율 {len(surv)}시군 · 전환율 {len(conv)}시군 "
      f"· 시너지 전국 {syn_nat} · {os.path.getsize(fp)/1e3:.0f} KB")
