# -*- coding: utf-8 -*-
"""JS 문법 검사 — 공용 스크립트와 각 화면의 인라인 <script> 를 node --check 로 확인한다.

브라우저에서만 드러나는 문법 오류(괄호 하나)는 화면 전체를 빈칸으로 만든다. push 전에 잡는다.
사용: python pipeline/gate/check_js.py   (node 필요) → 통과 0 · 실패 1
"""
import glob, os, re, subprocess, sys, tempfile
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
SITE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

targets = [os.path.join(SITE, p) for p in ['site.js', 'assets/v4.js', 'assets/v55.js', 'assets/region.js']]
bad = []
with tempfile.TemporaryDirectory() as tmp:
    for page in sorted(glob.glob(os.path.join(SITE, '*.html'))):
        html = open(page, encoding='utf-8').read()
        for k, m in enumerate(re.finditer(r'<script(?![^>]*\bsrc=)([^>]*)>(.*?)</script>', html, re.S)):
            if 'json' in m.group(1):          # <script type="application/json"> 등 데이터 블록은 제외
                continue
            fp = os.path.join(tmp, f"{os.path.basename(page)}.{k}.mjs" if 'module' in m.group(1) else f"{os.path.basename(page)}.{k}.js")
            open(fp, 'w', encoding='utf-8').write(m.group(2))
            targets.append(fp)
    for fp in targets:
        if not os.path.exists(fp):
            continue
        r = subprocess.run(['node', '--check', fp], capture_output=True, text=True, encoding='utf-8')
        if r.returncode != 0:
            bad.append(f"{os.path.relpath(fp, SITE) if fp.startswith(SITE) else os.path.basename(fp)}: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else '실패'}")
    print(f"── check_js ── {len(targets)}개 검사 · 실패 {len(bad)}")
for b in bad:
    print('  [FAIL]', b)
sys.exit(1 if bad else 0)
