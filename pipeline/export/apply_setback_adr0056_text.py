# -*- coding: utf-8 -*-
"""ADR-0056 — 사이트의 주거 이격 정의 문구를 주거용 건물 5호 군집(외벽 간 50 m) 기준으로 교체.
문자열 정확 일치로만 바꾸고, 하나라도 못 찾으면 아무 파일도 쓰지 않고 중단한다(부분 교체 방지). 재실행 안전(이미 바뀐 곳은 건너뜀).
"""
import os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEF = '주거용 건물(건축물 용도가 주택) 5동 이상이 외벽 간 50m 이내로 모인 곳(5호 군집)에서 200m 안의 농지를 제외'

EDITS = {
    'assets/v4.js': [
        ('이격거리 적용 시 주택 위치(대지 필지)도 이 원장 기준.',
         '이격거리 적용 시 농지 필지 경계(200m 측정 기준)도 이 지적 기준.'),
        ('측정 방법 고시가 아직 없어 주거 200m를 전국에 똑같이 적용.',
         f'주택 기준·측정 방법 고시가 아직 없어 {DEF}하는 기준을 전국에 똑같이 적용(주택 자료 [30]).'),
        ("  29: '제1차 분산에너지 특화지역",
         "  30: '국토교통부, 『GIS건물통합정보』 — 공간정보 오픈플랫폼(V-World) 데이터 API 레이어 LT_C_BLDGINFO, 2026-10-08 전국 수집 18,466,558동(건물 외곽선·건축물 용도코드). API 응답에 원천 갱신일 표기 없음.<span class=\"fn-note\">용도: 주거 이격의 주택 판정 — 건축물 용도가 단독주택(01xxx)·공동주택(02xxx, 생활편익·부대·복리시설·기숙사 제외)으로 등재된 건물만 주택으로 보고(1동 = 1호, 용도 미등재 건물 제외), 외벽에 25m 버퍼를 걸어 합친 면 안에 5동 이상이면 5호 군집으로 판정.</span>',\n  29: '제1차 분산에너지 특화지역"),
        ("['데이터 원천', [1, 2, 3, 5, 17, 21, 22, 23, 24]]", "['데이터 원천', [1, 2, 3, 5, 17, 21, 22, 23, 24, 30]]"),
    ],
    'assets/v55.js': [
        ("short: s.short + (sb ? ' · 주거 이격 200m 적용' : '')", "short: s.short + (sb ? ' · 주거 이격 200m(5호 군집) 적용' : '')"),
        ('주거 이격 200m 적용 여부. 각 조합은', '주거 이격 200m(주거용 건물 5호 군집 기준) 적용 여부. 각 조합은'),
    ],
    'method.html': [
        ('이격거리는 「재생에너지 개발·이용·보급 촉진법」의 상한(주거 200m)<sup class="fnref">[11]</sup>을 전국에 똑같이 적용한 값을 함께 보임.',
         f'이격거리는 「재생에너지 개발·이용·보급 촉진법」의 상한(주거 200m)<sup class="fnref">[11]</sup>을 전국에 똑같이 적용한 값을 함께 보임 — {DEF}<sup class="fnref">[30]</sup>.'),
        ('이격거리 적용 값은 주거 200m 상한<sup class="fnref">[11]</sup>을 전국에 똑같이 적용한 것으로,\n          지자체별 실제 기준이나 측정 방법과 다를 수 있다.',
         f'이격거리 적용 값은 주거 200m 상한<sup class="fnref">[11]</sup>을 전국에 똑같이 적용한 것이다({DEF}).\n          주택은 건축물 용도가 등재된 건물만 세므로(용도 미등재 건물 제외<sup class="fnref">[30]</sup>), 지자체별 실제 기준이나 고시될 측정 방법과 다를 수 있다.'),
        ("주거 200m 이격거리를 적용하면 특별법 시행 전 면적은", "주거 200m 이격거리(5호 군집 기준)를 적용하면 특별법 시행 전 면적은"),
        ("곳</b>(간척 평야는 주거지에서 멀기 때문).`", "곳</b>.`"),
    ],
    'local.html': [
        ('이격거리 상한제(주거 200m)를 전국 일률 보수 하한으로 적용한 값만 산출되어 있습니다<sup class="fnref">[11]</sup>.',
         f'이격거리 상한제(주거 200m)를 전국에 똑같이 적용한 값만 산출되어 있습니다 — {DEF}<sup class="fnref">[11]</sup><sup class="fnref">[30]</sup>.'),
        ("'주거 200m 보수 하한 — 대상 필지 제외'", "'5호 군집 주택 200m 안 농지 제외'"),
        ("`주거 이격 200m: ${st.sb ? '적용(보수 하한)' : '미적용'}`", "`주거 이격 200m: ${st.sb ? '적용(5호 군집 기준)' : '미적용'}`"),
        ('이격은 주거 200m 상한제를 전국 일률 보수 하한으로 적용한 값입니다.',
         f'이격은 주거 200m 상한제를 전국에 똑같이 적용한 값입니다({DEF}).'),
    ],
    'regions.html': [
        ('이격거리 상한제(주거 200m)를 전국 일률 보수 하한으로 적용한 값<sup class="fnref">[11]</sup>.',
         '이격거리 상한제(주거 200m)를 전국에 똑같이 적용 — 주거용 건물 5동 이상이 외벽 간 50m 이내로 모인 곳에서 200m 안 농지 제외<sup class="fnref">[11]</sup><sup class="fnref">[30]</sup>.'),
    ],
    'scenarios.html': [
        ('<button data-v="1">적용 (주거 200m)', '<button data-v="1">적용 (주거 200m · 5호 군집)'),
        ('<button data-sb="1">이격 적용 (주거 200m)', '<button data-sb="1">이격 적용 (주거 200m · 5호 군집)'),
        ('· 이격 적용 = 주거 200m 상한<sup class="fnref">[11]</sup>.</div>',
         '· 이격 적용 = 주거 200m 상한<sup class="fnref">[11]</sup>(주거용 건물 5동 이상이 외벽 간 50m 이내로 모인 곳 기준<sup class="fnref">[30]</sup>).</div>'),
        ('· 이격 적용 = 주거 200m 상한<sup class="fnref">[11]</sup>.<br>',
         '· 이격 적용 = 주거 200m 상한<sup class="fnref">[11]</sup>(주거용 건물 5동 이상이 외벽 간 50m 이내로 모인 곳 기준<sup class="fnref">[30]</sup>).<br>'),
    ],
}


def main():
    out, missing = {}, []
    for rel, edits in EDITS.items():
        p = os.path.join(ROOT, rel)
        raw = open(p, 'rb').read()
        crlf = b'\r\n' in raw
        s = raw.decode('utf-8').replace('\r\n', '\n')
        for old, new in edits:
            if new in s and old not in s:
                continue                      # 이미 반영
            if s.count(old) != 1:
                missing.append(f'{rel}: {old[:50]!r} (발견 {s.count(old)}회)'); continue
            s = s.replace(old, new, 1)
        out[p] = (s.replace('\n', '\r\n') if crlf else s, crlf)
    if missing:
        raise SystemExit('중단 — 일치하지 않는 문구:\n  ' + '\n  '.join(missing))
    for p, (s, crlf) in out.items():
        open(p, 'wb').write(s.encode('utf-8'))
    print(f'반영: {len(out)}개 파일 · {sum(len(v) for v in EDITS.values())}곳')


if __name__ == '__main__':
    main()
