# -*- coding: utf-8 -*-
"""경기연구원 자문 정적 패키지 동기화 — V5 저장소의 자문 자산을 별도 공개 저장소(agrivoltaic-advisory-gg)에 바이트 동일 복사(advisory.html 만 경기연구원 표시를 붙임).

대상 파일 = 저장소의 PACKAGE_MANIFEST.json 'files' 목록(경로는 두 저장소에서 같다) + 새로 생긴 data_v4/advisory/* 파일.
복사 후 manifest 의 sha256·bytes 를 다시 적고 revision 문구를 남긴다. push 는 하지 않는다(사람이 확인 뒤).
사용: python pipeline/export/sync_advisory_gg.py "r16 2026-10-07: ..."
"""
import os, sys, json, glob, hashlib, shutil, datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
SITE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GG = r'C:\Users\user\agrivoltaic-advisory-gg'
rev = sys.argv[1] if len(sys.argv) > 1 else f'sync {datetime.date.today().isoformat()}'
mp = os.path.join(GG, 'PACKAGE_MANIFEST.json'); man = json.load(open(mp, encoding='utf-8'))
files = set(man['files'].keys())
for p in glob.glob(os.path.join(SITE, 'data_v4', 'advisory', '**', '*'), recursive=True):
    if os.path.isfile(p): files.add(os.path.relpath(p, SITE).replace(os.sep, '/'))
# 자문 자료가 가리키는 사진(assets/advisory/**) — 2026-10-21 전까지 빠져 경기 저장소에서 비농지 사례 사진이 404 였다
import re
for p in glob.glob(os.path.join(SITE, 'data_v4', 'advisory', '*.json')):
    for rel in re.findall(r'"(assets/advisory/[^"]+)"', open(p, encoding='utf-8').read()):
        files.add(rel)
# 비농지 제외 방법 자문 탭(2026-10-21 — 경기연구원 화면은 '데이터 신뢰성·보완 검토'와 이 탭 두 개) — advisory.html 이 nonfarm_cases.html 을 불러온다
files |= {'nonfarm_cases.html', 'site.js', 'assets/v5.css', 'data_v4/nonfarm_cases_v1.json', 'data_v4/meta_v4.json', 'data_v4/results_v4.json'}
for p in (os.path.join(SITE, 'nonfarm_cases.html'), os.path.join(SITE, 'data_v4', 'nonfarm_cases_v1.json')):
    for rel in re.findall(r'(assets/nonfarm_cases/[^"\s]+\.(?:jpg|png))', open(p, encoding='utf-8').read()):
        files.add(rel)
# 경기연구원 패키지 표시 — advisory.html 은 <html data-pkg="gg"> 일 때 탭 두 개만 보인다(나머지는 바이트 동일 복사)
# 경기연구원 저장소에만 다른 원본을 쓰는 파일 — 저장소 경로: V5 원본 경로(V5 의 같은 이름 파일은 지자체용으로 그대로 둔다)
SRC_OF = {'docs/ADVISORY_README.md': 'docs/ADVISORY_README_GG.md'}
TRANSFORM = {'advisory.html': lambda b: b.replace(b'<html lang="ko">', b'<html lang="ko" data-pkg="gg">', 1)}
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest()
changed, missing = [], []
for rel in sorted(files):
    src = os.path.join(SITE, SRC_OF.get(rel, rel)); dst = os.path.join(GG, rel)
    if not os.path.exists(src): missing.append(rel); continue
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if rel in TRANSFORM:
        body = TRANSFORM[rel](open(src, 'rb').read())
        assert b'data-pkg="gg"' in body, f'{rel}: 경기연구원 표시를 붙이지 못함 — <html lang="ko"> 확인'
        s = hashlib.sha256(body).hexdigest()
        if not os.path.exists(dst) or sha(dst) != s: open(dst, 'wb').write(body); changed.append(rel)
        man['files'][rel] = {'bytes': len(body), 'sha256': s}
        continue
    before = sha(dst) if os.path.exists(dst) else None; s = sha(src)
    if before != s: shutil.copy2(src, dst); changed.append(rel)
    man['files'][rel] = {'bytes': os.path.getsize(src), 'sha256': s}
man['revision'] = rev; man['source_branch'] = 'main'; man['source_state'] = f'synced {datetime.datetime.now().isoformat(timespec="minutes")}'
try:
    import subprocess; man['source_head'] = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=SITE, capture_output=True, text=True).stdout.strip()
except Exception: pass
json.dump(man, open(mp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'동기화 — 변경 {len(changed)} · 전체 {len(files)} · 원본 없음 {len(missing)}')
for c in changed[:30]: print('  ', c)
if missing: print('  ⚠ 원본 없음:', missing[:10])
