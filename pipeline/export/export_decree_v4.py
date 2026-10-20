# -*- coding: utf-8 -*-
"""data_v4/decree_v4.json — 시행령 제정안 영향 탭(decree.html)의 수치.

대상: 영농형태양광법 시행령 제정안(관계기관 의견조회판, 2026.7) 제7조 6호 —
농업회사법인의 발전사업부지를 「농어촌정비법」 §14①의 매립지등 소재로 한정하고
같은 항 제2호에 따라 매각된 매립지등은 제외한다. 그 잔여 범위(미매각 유지분)가
query.py matrix_data 의 '국가관리간척지' 모집단이다(농식품부 '25.6 공표 13지구).

원칙 1(단일 출처): 판정 SQL 없음 — 정본 질의(matrix_data)만 부른다.
원칙 13(게이트): 감사 통과값(2026-08-31 auditor)과 어긋나면 파일을 만들지 않고 중단.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, OUT, MODEL
from datetime import datetime

sys.path.insert(0, MODEL)
import query as Q

os.makedirs(OUT, exist_ok=True)
GEN = datetime.now().strftime('%Y-%m-%d %H:%M')

rows_pub = Q.matrix_data(universe='pubcorp')   # 정본 우주(법인 06 + 국공유 02·04·05)
rows_all = Q.matrix_data(universe='all')       # 무필터 대조군


def cell(src, pop, code):
    r = [x for x in src if x['pop'] == pop and x['cell'] == code and x['phase'] == '본값'][0]
    return {'n': r['n'], 'km2': round(r['m2'] / 1e6, 2), 'm2': round(r['m2'], 2)}


# ── 대조값 — ADR-0060(2026-10-20 비농지 제외) 재산출값. query.matrix_data 와 엔진 런(R3_zone_all · R3_zone_all@all ·
#    R0_current@all)의 필지·km² 가 정확히 같음을 확인하고 등재했다(감사 미실시 — 다음 감사 대상).
#    종전 2026-08-31 auditor 감사 통과값(장부 기준 · 비농지 제외 전)은 이력:
#      국가관리간척지 R0 all 1,200·6.05 / R1 1,242·6.10 / R2 20,330·156.01 / R3 20,372·156.06 ·
#      pubcorp R0 627·4.31 / R1 655·4.33 / R2 10,034·102.65 / R3 10,062·102.68 ·
#      전국 R3 all 9,271,388·11,971.67 · pubcorp 1,563,683·1,078.38 · 간척 R3 all 237.42 · pubcorp 123.10 · 전국 R0 all 5,719,511·5,582.55
#    자산이 변하면 여기서 멈춘다.
AUDITED = [
    # (pop, cell, universe, n, km2)
    ('국가관리간척지', 'R0', 'all', 1_107, 5.32),
    ('국가관리간척지', 'R1', 'all', 1_149, 5.37),
    ('국가관리간척지', 'R2', 'all', 20_128, 154.43),
    ('국가관리간척지', 'R3', 'all', 20_170, 154.48),
    ('국가관리간척지', 'R0', 'pubcorp', 534, 3.57),
    ('국가관리간척지', 'R1', 'pubcorp', 562, 3.60),
    ('국가관리간척지', 'R2', 'pubcorp', 9_832, 101.07),
    ('국가관리간척지', 'R3', 'pubcorp', 9_860, 101.10),
    ('전국', 'R3', 'all', 9_115_924, 11_863.81),
    ('전국', 'R3', 'pubcorp', 1_408_219, 970.52),
    ('간척', 'R3', 'all', None, 235.55),
    ('간척', 'R3', 'pubcorp', None, 121.23),
    ('전국', 'R0', 'all', 5_633_240, 5_519.41),
]
for pop, code, uni, xn, xkm2 in AUDITED:
    c = cell(rows_all if uni == 'all' else rows_pub, pop, code)
    if (xn is not None and c['n'] != xn) or abs(c['km2'] - xkm2) > 0.005:
        raise SystemExit(f"[FAIL] {pop} {code}({uni}) {c['n']:,}·{c['km2']:,.2f}km² ≠ "
                         f"대조값 {xn}·{xkm2} — 자산 변동, export 중단")

matrix = {code: {'name': name,
                 '정본': cell(rows_pub, '국가관리간척지', code),
                 '대조군': cell(rows_all, '국가관리간척지', code)}
          for code, name, _ in Q.MATRIX_ZONES}

context = {pop_key: {'정본': cell(rows_pub, pop, code),
                     '대조군': cell(rows_all, pop, code)}
           for pop_key, pop, code in [('전국R3', '전국', 'R3'),
                                      ('간척R3', '간척', 'R3'),
                                      ('전국R0', '전국', 'R0')]}


def save(name, obj):
    fp = os.path.join(OUT, name)
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    print(f"  {name}: {os.path.getsize(fp)/1e3:.0f} KB")


save('decree_v4.json', {
    'generated': GEN,
    'basis': '2026-08-31 query.py matrix(모집단 국가관리간척지) — auditor 감사 통과, '
             '3판·실경작 무관 본값. 정본 = 법인(06)+국공유(02·04·05) 우주, 대조군 = 무필터',
    'scope_note': "'국가관리간척지' = 농어촌정비법 §14① '매립지등' 중 미매각 유지분"
                  "(농식품부 '25.6 공표 13지구) — 시행령 제정안(의견조회판) §7 6호가 "
                  '농업회사법인 부지를 한정하는 범위(매각분 제외)',
    'matrix_natmg': matrix,          # 국가관리간척지 R0–R3 · 정본/대조군 병기(제2조)
    'context': context,              # 대조 맥락: 전국 R3 · 간척(EKR 원장 전체) R3 · 전국 R0
})
print(f"완료 — decree_v4.json (생성 {GEN})")
