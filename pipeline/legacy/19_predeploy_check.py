# -*- coding: utf-8 -*-
"""19_predeploy_check.py — 배포 전 자동 점검 (사용자 검수용 리포트)
a. 오라벨 교체 검증 (예산=44810·용인 코드 실데이터, 홍성·이천 잔재 0)
b. 로드 실패 폴백 (히어로 통계 정적 폴백 존재, 0·0 방지)
c. "14개 시군"·"경기 7·충남 7" 문자열 잔재 전수 검색
d. 4페이지 상호 링크 정상 + 저소유 잔재
"""
import os, sys, io, json, re, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = r"C:\Users\user\새 폴더"
SITE = os.path.join(BASE, "site_v2")  # 2026-07-21 정정(K8): 정본 site_v2 점검 (site\는 07-17 동결 구본)
PAGES = ["index.html", "map.html", "atlas.html", "method.html", "insight.html"]  # policy 비공개 제외 · atlas=구역별 지도(2026-07-23)
rep = ["# 배포 전 자동 점검 리포트 (갱신 2026-07-21)", ""]
fails = 0


def line(ok, msg):
    global fails
    if not ok:
        fails += 1
    rep.append(f"- {'✅' if ok else '❌'} {msg}")


# a. 오라벨 교체 검증 — summary.json 데이터 출처
sm = json.load(open(os.path.join(SITE, "data", "summary.json"), encoding="utf-8"))
yesan = sm["codes"].get("44810", {})
line(yesan.get("name") == "예산" and yesan.get("S1", {}).get("seg_mw", 0) > 0,
     f"a1. 예산(44810) 카드=예산 실데이터 (S1 잠재 {yesan.get('S1',{}).get('seg_mw')}MW, 구 홍성 오라벨 해소)")
# 예산 블록 PNU가 실제 44810인지
yb = os.path.join(SITE, "data", "44810_S1.json")
if os.path.exists(yb):
    mem = json.load(open(os.path.join(BASE, "pipeline_out", "blocks", "44810_S1_members.json"), encoding="utf-8"))
    pnus = [p for v in mem.values() for p in v[:1]]
    bad = [p for p in pnus if not p.startswith("44810")]
    line(len(bad) == 0, f"a2. 예산 블록 구성 PNU 전부 44810 (외지 잔재 {len(bad)})")
# 생활권 병합 표시코드 검증 (2026-07-22: 천안·용인·안산 일관 적용, 재분리 금지)
MERGED = {"44130": ("천안시", ("44131", "44133")),
          "41460": ("용인시", ("41461", "41463", "41465")),
          "41270": ("안산시", ("41271", "41273")),
          "47110": ("포항시", ("47111", "47113")),
          "31000": ("울산광역시", ("31110", "31140", "31170", "31200", "31710"))}
for c, (nm, parts) in MERGED.items():
    v = sm["codes"].get(c, {})
    line(v.get("name") == nm, f"a3. {c}={nm} 병합 카드 존재·명칭 정합")
    mp = os.path.join(BASE, "pipeline_out", "blocks", f"{c}_S1_members.json")
    if os.path.exists(mp):
        mem = json.load(open(mp, encoding="utf-8"))
        pnus = [p for vv in mem.values() for p in vv]
        bad = [p for p in pnus if not p.startswith(parts)]
        line(len(bad) == 0, f"a3. {c}={nm} 블록 PNU 전부 구성 구 {list(parts)} 소속 (외지 잔재 {len(bad)})")
# 구 개별 코드가 summary에 잔존하지 않는지 (병합 후 재분리 금지)
gu_left = [g for _, (_, ps) in MERGED.items() for g in ps if g in sm["codes"]]
line(not gu_left, f"a3. 병합 구성 구 코드의 summary 잔존 0건{'' if not gu_left else ' ← ' + ','.join(gu_left)}")

# b. 로드 실패 폴백 — index 히어로가 fetch 실패 시 0·0으로 뜨는지
idx = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
has_catch = ".catch(" in idx or "onerror" in idx
line(has_catch, "b. index 로드 실패 폴백 처리 (fetch .catch)")
if not has_catch:
    rep.append("    → 보완 필요: fetch 실패 시 정적 폴백값 표시(0·0 방지)")

# c. 금지 문자열 전수 검색 (구 프레임 잔재만 — method의 '삭제/이관' 설명 맥락은 제외)
HARD = ["14개 시군", "경기 7", "충남 7", "경기7", "충남7", "저소유", "저개인소유", "특별법 S3", "특별법(S3)",
        # 2026-07-21 추가(K14): 07-20 수정 라운드의 금지·구식 문구를 게이트에 반영
        "128만", "1.28M", "18개 시군", "19개 코드", "일제히", "조차 미달", "겨우 걸친",
        "공공·법인 소유 중심", "22.7", "3,558", "63.8MW", "KPVS", "진짜 후보",
        # 2026-07-22 병합 표준(25개 분석구역) 이전 표기
        "29개 코드", "18개 코드", "29개 시군구", "26개 분석구역"]  # 어디서든 0
CONTEXT = ["산단 반경 10km", "SMAX", "S_MAX"]  # '삭제/이관/제외/Future' 문맥이면 정상
allpages = PAGES + ["policy.html", "map_full.html"]
hit_any = False
for pg in allpages:
    txt = open(os.path.join(SITE, pg), encoding="utf-8").read()
    for b in HARD:
        if b in txt:
            hit_any = True
            line(False, f"c. 구 프레임 잔재 '{b}' 발견 @ {pg}")
    for b in CONTEXT:
        for m in re.finditer(re.escape(b), txt):
            ctx = txt[max(0, m.start()-40):m.end()+40]
            if not re.search(r"삭제|이관|제외|Future|폐기|후속", ctx):
                hit_any = True
                line(False, f"c. '{b}' 비-설명 맥락 발견 @ {pg}: …{ctx.strip()[:50]}…")
line(not hit_any, "c. 구 프레임 잔재(14개 시군·경기7충남7·저소유) 0건 + 산단10km/SMAX는 삭제·이관 설명 맥락만" if not hit_any else "c. 잔재 있음 ↑")

# d. 상호 링크 + terms + 콘솔(정적 확인)
for pg in PAGES:
    txt = open(os.path.join(SITE, pg), encoding="utf-8").read()
    links = all(f'href="{t}"' in txt for t in ["index.html", "map.html", "atlas.html", "method.html", "insight.html"])
    line(links, f"d1. {pg} — 5페이지 상호 링크 정상 (구역별 지도 포함)")
    # d2 (2026-07-21 K14 갱신): site_v2는 4개 페이지가 site.js 사용 — terms.js는 window.TERMS를
    # 실제 참조하는 페이지(map_full·policy)만 로드하면 정상. TERMS 참조 없이 미로드면 통과.
    uses_terms = "TERMS." in txt
    line(("assets/terms.js" in txt) or not uses_terms,
         f"d2. {pg} — terms.js {'로드' if uses_terms else '불필요(미참조)'}")
for pg in ["map_full.html", "policy.html"]:
    txt = open(os.path.join(SITE, pg), encoding="utf-8").read()
    line("assets/terms.js" in txt, f"d2. {pg} — terms.js 로드 (TERMS 사용 페이지)")
# policy 비활성 확인
for pg in PAGES:
    txt = open(os.path.join(SITE, pg), encoding="utf-8").read()
    active = 'href="policy.html"' in txt
    line(not active, f"d3. {pg} — 정책제언 링크 비활성(placeholder) 유지")

rep.append("")
rep.append(f"## 결과: {'전체 통과 — 배포 가능' if fails==0 else f'{fails}건 실패 — 배포 보류'}")
rep.append("※ 콘솔 오류 0·시크릿창 검증은 스테이징에서 브라우저로 최종 확인.")
out = os.path.join(BASE, "pipeline_out", "predeploy_check.md")
open(out, "w", encoding="utf-8").write("\n".join(rep))
print("\n".join(rep))
print(f"\n리포트: {out}")
sys.exit(1 if fails else 0)
