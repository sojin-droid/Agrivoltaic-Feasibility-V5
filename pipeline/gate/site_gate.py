# -*- coding: utf-8 -*-
"""site_gate — 시연·push 전 필수 관문 (REWORK_PLAN 원칙 13).
검사: ①무효 수치 ②금지어·물결표 ③data_v4 내부 정합(T14·가산성) ④외부 자원 로드 ⑤하드코딩 수치 ⑥폐기된 1km 응축(cc) 참조 ⑦행정코드 다리 회귀.
새 함정 발견 시 문서에 적기 전에 여기 검사부터 추가한다.

사용: python pipeline/gate/site_gate.py    → PASS면 종료코드 0, 위반 있으면 1
"""
import os, re, json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')   # cp949 콘솔에서 '—' 출력 크래시 방지 (2026-08-31 실측: 크래시가 '검사 통과'를 exit 1로 둔갑시킴)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import SITE, OUT, CLUSTERS, ROOT, MODEL, LR, CAD   # 경로는 한 곳에서만

# 전 탭 스캔 — 새 탭 추가 시 반드시 여기에도 추가 (2026-08-26: map·insight·candidates 누락 적발)
PAGES = ['index.html', 'finder.html', 'scenarios.html', 'regions.html', 'local.html', 'method.html', 'advisory.html', 'cluster_advisory.html',
         'evidence.html', 'map.html', 'candidates.html', 'proximity.html', 'decree.html', 'insight.html', 'about.html']
DATA = os.path.join(SITE, 'data_v4')

# ① 무효·구세대 수치 (원칙 3) — 발견 즉시 FAIL. 새 무효값 확정 시 여기에 추가.
FORBIDDEN_NUMBERS = [
    '5,039.81', '5039.81',          # 초판 앵커 (이력 전용)
    '4,001,803',                    # 초판 앵커 필지수
    '6,755', '6755MW',              # 판독률=휴경 오류 계열
    '16.2%',                        # 간척 휴경 오판율
]
# ② 금지어 (원칙 5·6) — 평균 개념, 물결표 범위, 임의 용어
FORBIDDEN_WORDS = [
    (r'평균', "'평균' 사용 금지 — 실측값으로"),
    (r'\d\s*~\s*\d', "물결표 범위 금지 — '–' 사용"),
    (r'밖만', "임의 축약 금지 — '농업진흥지역 밖의 농지'"),
    (r'지렛대', "은유 금지"),
]
# ④ 외부 자원 로드 (원칙 10) — 하이퍼링크(<a href>)는 허용, '로드'만 금지.
# 예외(원칙 10 개정 2026-08-25): Google Fonts(폴백 필수)만 허용. 라이브러리는 내장(vendored).
FONT_OK = re.compile(r'https?://fonts\.(googleapis|gstatic)\.com')
EXTERNAL_LOAD = [
    (r'src\s*=\s*["\']https?://', '외부 스크립트/이미지 로드'),
    (r'<link[^>]+href\s*=\s*["\']https?://', '외부 스타일시트'),
    (r'@import\s+url\(["\']?https?://', '외부 CSS import'),
    (r'fetch\(["\']https?://', '외부 API 호출'),
]

fails, warns = [], []

def scan(fp, rel):
    txt = open(fp, encoding='utf-8').read()
    for pat in FORBIDDEN_NUMBERS:
        if pat in txt:
            fails.append(f"{rel}: 무효 수치 '{pat}'")
    # 어휘 규칙은 우리가 쓴 서술문(html)에만 — 계보(meta) 등 원문 기록 인용은 교정 대상 아님.
    # 단 summary는 페이지에 그대로 렌더되는 라벨을 담으므로 어휘 규칙 적용.
    if rel.endswith('.html') or 'summary' in rel or 'funnel' in rel:
        for pat, msg in FORBIDDEN_WORDS:
            for m in re.finditer(pat, txt):
                fails.append(f"{rel}: {msg} — …{txt[max(0,m.start()-20):m.end()+20]}…")
    if rel.endswith('.html'):
        for pat, msg in EXTERNAL_LOAD:
            for m in re.finditer(pat, txt):
                seg = txt[m.start():m.start()+160]
                if FONT_OK.search(seg):
                    continue                      # 웹폰트 예외 (원칙 10 개정)
                fails.append(f"{rel}: {msg} (자족형 위반) — …{seg[:80]}…")
        # ⑤ 하드코딩 수치: 본문에 콤마 큰 수가 직접 있으면 경고 (수치는 data_v4에서 렌더)
        body = re.sub(r'<script.*?</script>', '', txt, flags=re.S)
        body = re.sub(r'<style.*?</style>', '', body, flags=re.S)   # rgba(12,53,106) 오탐 제거
        body = re.sub(r'<link[^>]*>', '', body)              # 폰트 URL 웨이트 숫자 오탐 제거
        body = re.sub(r'(?:href|src)\s*=\s*"[^"]*"', '', body)
        body = re.sub(r'style\s*=\s*"[^"]*"', '', body)      # inline rgba(255,216,…) 색상 오탐 제거
        body = re.sub(r'rgba?\([\d\s,.]+\)', '', body)       # JS 문자열 안 색상값
        for m in set(re.findall(r'\d{1,3}(?:,\d{3}){1,}', body)):
            warns.append(f"{rel}: 본문 하드코딩 수치 의심 '{m}' — data_v4 렌더로 옮길 것")

# ③ data_v4 내부 정합
sfp = os.path.join(DATA, 'summary_v4.json')
if os.path.exists(sfp):
    s = json.load(open(sfp, encoding='utf-8'))
    a = s['anchor']
    # ADR-0040: 정본(법인·국공유)과 대조군(무필터)을 둘 다 검사한다. 앵커는 폐지됐고
    # summary_v4.anchor 는 R0 정본, anchor.control 이 R0 대조군이다.
    r0 = s['matrix']['전국']['R0']['정본']
    if r0['n'] != a['n'] or abs(r0['km2'] - round(a['m2']/1e6, 1)) > 0.05:
        fails.append("summary_v4: 매트릭스 R0(정본) ≠ anchor 블록 불일치")
    if 'control' in a:
        ct = s['matrix']['전국']['R0']['대조군']
        if ct['n'] != a['control']['n']:
            fails.append("summary_v4: 매트릭스 R0(대조군) ≠ anchor.control 불일치")
    else:
        fails.append("summary_v4: 대조군(anchor.control) 없음 — 정본 단독 제시 금지(제2조)")
    for pop in ['전국', '간척']:
        m = s['matrix'][pop]
        for ph in ['정본', '대조군']:
            add = m['R0'][ph]['n'] + (m['R1'][ph]['n']-m['R0'][ph]['n']) + (m['R2'][ph]['n']-m['R0'][ph]['n'])
            if add != m['R3'][ph]['n']:
                fails.append(f"summary_v4: {pop} {ph} 가산성 위반 (R0+풀 ≠ R3)")
else:
    fails.append("data_v4/summary_v4.json 없음 — export_v4 먼저")

for name in PAGES:
    fp = os.path.join(SITE, name)
    if os.path.exists(fp):
        scan(fp, name)
    else:
        warns.append(f"{name}: 아직 없음")
for name in os.listdir(DATA) if os.path.isdir(DATA) else []:
    fp = os.path.join(DATA, name)
    if not os.path.isfile(fp) or name.endswith('.gz'):
        continue                     # clusters/ 등 지오메트리 폴더·gzip 파일은 수치·어휘 스캔 대상 아님
    scan(fp, f"data_v4/{name}")

# ⑥ 폐기된 ≤1,000m 응축(cc) 계보가 활성 화면·공용 JS·발행 순서에 다시 들어오지 않는가 (ADR-0054 · 감사 F-07/F-23)
#   LEGACY 자산(data_v4/cand/ · recommend_cc_v4 · recommend_emd_v4 · assets/cand.js)은 파일로 남아 있어도 되지만, 부르면 FAIL.
CC_REF = [r'assets/cand\.js', r'cand\.css', r'recommend_cc_v4', r'recommend_emd_v4', r'data_v4/cand/', r'cand_index', r'\bCand\.']
ACTIVE_JS = ['assets/v4.js', 'assets/v55.js', 'assets/region.js', 'site.js']
for rel in ['index.html', 'finder.html', 'scenarios.html', 'regions.html', 'local.html', 'method.html', 'advisory.html'] + ACTIVE_JS:
    fp = os.path.join(SITE, rel)
    if not os.path.exists(fp):
        continue
    txt = open(fp, encoding='utf-8').read()
    for pat in CC_REF:
        if re.search(pat, txt):
            fails.append(f"{rel}: 폐기된 1km 응축(cc) 자산 참조 '{pat}' — ADR-0054")
_pub = open(os.path.join(SITE, 'publish.py'), encoding='utf-8').read()
for bad in ('export_cand_v4', 'export_emd_v4', 'make_sgg_briefs'):
    if bad in _pub:
        fails.append(f"publish.py: 폐기된 1km 응축 exporter '{bad}' 가 발행 순서에 있음 — ADR-0054")

# ⑦ 행정코드 다리 회귀(감사 NEW-F-03) — 합성 fixture(인천·부산·대전·대구 중구 동명) 검사가 깨지면 FAIL
import subprocess as _sp
_tb = _sp.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_admin_bridge.py')],
              capture_output=True, text=True, encoding='utf-8')
if _tb.returncode != 0:
    fails.append('test_admin_bridge: ' + (_tb.stdout.strip().splitlines() or ['실행 실패'])[-1] + ' ' + _tb.stderr.strip()[-200:])

print(f"── site_gate ── FAIL {len(fails)} · WARN {len(warns)}")
for f in fails:
    print(f"  [FAIL] {f}")
for w in warns:
    print(f"  [warn] {w}")
print("결과:", "PASS — 시연·push 가능" if not fails else "FAIL — 해소 전 시연·push 불가")
sys.exit(1 if fails else 0)
