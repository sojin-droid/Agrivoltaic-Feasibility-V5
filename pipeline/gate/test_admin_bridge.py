# -*- coding: utf-8 -*-
"""행정코드 다리 회귀 검사 (감사 NEW-F-03 · F-26, 2026-09-24) — 합성 fixture 로 emd_alias.name_alias 를 직접 부른다.

재현하는 사고: 시도 이름을 뗀 키('중구 선화동')로 대조해 인천 중구 동이 부산·대전·대구 중구의 같은 이름 동에 붙었다.
검사: ① 다른 시도 동명 연결 0 ② 같은 시도의 유일 후보만 연결 ③ 기록된 시도 통합(광주·전남 → 전남광주통합특별시)만 시도를 넘는다
     ④ 같은 시도 안 복수 후보·다대일은 AMBIGUOUS 로 남고 연결되지 않는다.
사용: python pipeline/gate/test_admin_bridge.py   (site_gate 가 함께 부른다) → 통과 0 · 실패 1
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'export'))
from emd_alias import name_alias, check_sido_merge

# (emd8, 법정동 전체 이름, alive) — 코드는 fixture 식별자일 뿐이다(대조는 이름으로만).
ROWS = [
    ('OLD_IC01', '인천광역시 중구 선화동', False),       # 인천 중구(개편으로 폐지) — 같은 이름이 대전 중구에 현행으로 있다
    ('OLD_IC02', '인천광역시 중구 중앙동1가', False),    # 부산 중구에 같은 이름
    ('OLD_IC03', '인천광역시 중구 도원동', False),       # 대구 중구에 같은 이름
    ('NEW_DJ01', '대전광역시 중구 선화동', True),
    ('NEW_BS01', '부산광역시 중구 중앙동1가', True),
    ('NEW_DG01', '대구광역시 중구 도원동', True),
    ('OLD_GJ01', '광주광역시 북구 가동', False),         # 기록된 통합 — 전남광주통합특별시로 넘어간다
    ('NEW_12_01', '전남광주통합특별시 북구 가동', True),
    ('NEW_BS02', '부산광역시 북구 가동', True),           # 다른 시도의 같은 이름(통합 대상 아님) — 끌려가면 안 된다
    ('OLD_JN01', '전라남도 해남군 해남읍', False),
    ('NEW_12_02', '전남광주통합특별시 해남군 해남읍', True),
    ('OLD_GG01', '경기도 가시 나동', False),             # 같은 시도 안 복수 후보 → AMBIGUOUS
    ('NEW_GG01', '경기도 가시 나동', True),
    ('NEW_GG02', '경기도 가시 나동', True),
]
BND = {r[0] for r in ROWS if r[2]}
OLD = [r[0] for r in ROWS if not r[2]]

fails = []
alias, rep = name_alias(ROWS, OLD, BND)
linked = {o: n for n, o in alias.items()}
cross = [(o, n) for o, n in linked.items() if o.startswith('OLD_IC')]
if cross:
    fails.append(f'다른 시도 동명 연결 {cross}')
if linked.get('OLD_GJ01') != 'NEW_12_01':
    fails.append(f"기록된 통합(광주→전남광주통합특별시) 연결 실패: {linked.get('OLD_GJ01')}")
if linked.get('OLD_JN01') != 'NEW_12_02':
    fails.append(f"기록된 통합(전남→전남광주통합특별시) 연결 실패: {linked.get('OLD_JN01')}")
if 'OLD_GG01' in linked or not any(o == 'OLD_GG01' for o, _ in rep['ambiguous']):
    fails.append('같은 시도 복수 후보가 AMBIGUOUS 로 남지 않았다')
if {o for o, *_ in rep['cross_sido_rejected']} != {'OLD_IC01', 'OLD_IC02', 'OLD_IC03'}:
    fails.append(f"다른 시도 동명 거부 보고 불일치 {rep['cross_sido_rejected']}")

# 다대일: 서로 다른 구 코드 둘이 같은 현행 코드 하나로 모이면 둘 다 연결하지 않는다
R2 = [('OLD_A', '경기도 가시 다동', False), ('OLD_B', '경기도 가시 다동', False), ('NEW_A', '경기도 가시 다동', True)]
a2, r2 = name_alias(R2, ['OLD_A', 'OLD_B'], {'NEW_A'})
if a2 or {o for o, _ in r2['ambiguous']} != {'OLD_A', 'OLD_B'}:
    fails.append(f'다대일이 AMBIGUOUS 로 남지 않았다: alias={a2}')

# 시도 폐지 상태 관문 — 기록 밖 폐지 시도의 코드가 쓰이면 멈춰야 한다
try:
    check_sido_merge([('인천광역시', False), ('광주광역시', False), ('전라남도', False), ('전남광주통합특별시', True)], {'인천광역시'})
    fails.append('기록 밖 폐지 시도(인천광역시)를 통과시켰다')
except SystemExit:
    pass

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print('── test_admin_bridge ──', 'PASS' if not fails else 'FAIL ' + str(len(fails)))
    for f in fails:
        print('  [FAIL]', f)
    sys.exit(1 if fails else 0)
