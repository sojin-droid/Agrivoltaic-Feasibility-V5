# GGI 시각화 내부 검토의견 — 반영 기록 (V5.5 · 2026-09-23)

브랜치 `v5.5-ggi-review` · 기준 커밋 ffed9b2(V5.4) · 동결본·원고·V5 production·21m 임계·후보 클러스터 정의 무변경.
연구 설계 전제: 개별 필지 → 21m 연접 → **복수 필지의 공간 분석 단위(후보 공간)** → 시군구에서 후보 공간으로 표현 → 최종 cluster 정의는 자문 전 미확정.

## 1. 검토의견별 반영 상태

status: REFLECTED / REFLECTED_WITH_METHOD_CHANGE / NOT_REFLECTED (이유 필수)

| feedback_id | feedback_text | implementation | status | evidence |
|---|---|---|---|---|
| F01 | 메뉴 명칭 — 한눈에 보기→전국 모아보기 · 정책 시나리오→시나리오별 결과 · 지역별 우선 후보→우리 동네 TOP 10 · 대상 사용자 "지자체 · 주민 · 비영리" · "우리동네 후보 클러스터 분석"→"우리 동네 영농형 태양광, 어디가 좋을까?" | 6개 페이지 nav 교체(`data-i18n` 키 유지) · CTA "우리 동네 분석하기" · local.html 히어로 제목·eyebrow 교체 · index 카드 메타 | REFLECTED | 브라우저 본문 텍스트(1280px): 6개 nav 항목 확인 · `grep 한눈에\|지역별 우선` 0건 |
| F02 | 우리동네 안내문 — 첫번째/두번째/마지막 3단계 | local.html `.v55-steps` 3카드(입력 → 조건·우선순위 → "우리 동네 분석하기" 클릭) | REFLECTED | local.html 랜딩 텍스트 · 375px 카드 폭 327px 1열 |
| F03 | 전국 페이지 제목 "전국 영농형 태양광 모아보기" · "전국 설치 가능 농지 분석" 제거 · 특별법 시나리오 핵심 표현 · 시행 여부와 시나리오 혼동 방지 | index.html h1 교체 · 리드 "영농형태양광 특별법에 따라 농업진흥지역에도 영농형 태양광을 설치할 수 있게 된다면?" · "법률의 실제 시행 여부와 무관한 제도 설계 시나리오" 명시 · 시행 전/후 배지 | REFLECTED | index 본문 텍스트 |
| F04 | "현행 제도·개방 전 / 정책 제약 완화 시" → "특별법 시행 전 / 시행 후" · R0~R3 화면 노출 제거 | `V55.SCN` 표기 사전 · index 배지 · scenarios.html CELL_LABEL·표 1~5·요약표·지도 범례·배지 문구 교체(64건) · method.html 2-1에 내부 표기 대응 각주 | REFLECTED | scenarios.html 본문 정규식 `\bR[0-3]\b` 0건(브라우저 innerText) · 등재 런 코드는 `title` 속성으로만 |
| F05 | 카드 구조 — 두 번째 카드 제거 · 3개 핵심 카드 세로 정렬 · R1/R2/R3 내부 명칭 제거 | index 비교 박스 2개 → 세로 카드 3장(`.v55-cards`) · R 필 제거 | REFLECTED | index 본문 · 375px 카드 폭 335px 1열 |
| F06 | 전국 핵심 숫자 1,078.4 / +587.7 / 259.0 (+202.8) / 25곳 — 하드코딩 금지 | summary_v4(R0·R3 정본 m2) · results_v4 size_bands(6.6667ha·111.1111ha) · narrative_v4 ge50에서 렌더. 증분은 ㎡ 원값 차 | REFLECTED | 렌더값 1,078.4 · +587.7 · 259.0 · +202.8 · 25 · 1→25 (브라우저 텍스트) · site_gate 하드코딩 경고 0(index) |
| F07 | 한 줄 결론 시각 구조 · "특구 후보 클러스터" 대신 "대규모 후보 공간" · 간척 부가 설명은 데이터 계산 시만 | `.v55-verdict` "농업진흥지역이 개방된다면? … 1곳에서 25곳으로 증가" · 간척 N곳은 narrative cp_big(reclaim_pct≥50) 계산값 | REFLECTED_WITH_METHOD_CHANGE | 텍스트 "25곳 중 16곳은 간척 지구" · 명칭은 자문 전 임시 표현(§0) |
| F08 | 방법론 더 보기 팝업 — 일반 화면은 쉬운 설명, 팝업은 실제 방법·기준·계산 원리·자료·한계 | `V55.methodButton`/`openModal` 공용 모달 · 화면별 5종 콘텐츠(index·finder·top10·local·scenarios) · 방법론 탭 유지 | REFLECTED | regions·finder에서 모달 open=true 확인 |
| F09 | 지도 설명 간결화 — "대규모 영농형 태양광 후보 공간 / 약 50MW 이상 규모의 후보 공간 25곳 / 법인·국공유 소유 농지 기준 / 농업진흥지역 개방 시나리오 기준" · 특구·cluster 표현 금지 | finder 패널 제목·리드 교체 | REFLECTED | finder 패널 텍스트 · p-n=25 |
| F10 | 기본 지도 = 21m 공간 분석 단위 단순화 polygon · 읍면동 경계로 자르지 않음 · ≤1000m cc polygon 재채택 금지 | `pipeline/geom/export_units_v4.py` → analysis_unit_v1.gpkg(v9_02 · 2m 단순화 · 경계 미절단 131개) → `data_v4/units/{sgg}` · `units_big`(25) · finder·regions·local 지도 기본 레이어 교체 · cc 층(cand/) 화면 사용 중단 | REFLECTED | 게이트: 폴리곤 14,721 = DuckDB 행 · cp_big 25 ⊂ units · finder 폴리곤 path 25 · 시행 전·이격 조건은 등재 런 시군 구간 폴리곤(15m)으로 폴백하며 범례에 명시 |
| F11 | 지도 컨트롤 — 확대/축소를 지도 오른쪽 끝으로, 1280/375에서 겹침 없음 | `zoomControl:false` + `L.control.zoom({position:'topright'})`(finder·regions·local) · `.fs-map .leaflet-control-zoom` 여백 | REFLECTED | 1280px: 패널 right 314 vs 줌 left 1221(겹침 false) · 375px: 패널 static, 줌 지도 안 |
| F12 | 화살표 더 굵게 · 네이비 · 디자인 토큰 재사용 | `.v55-arrow`/`.v55-flow` SVG stroke 3.5–4px `var(--navy)`(#0C356A 기존 토큰) · 임의 색 생성 없음 | REFLECTED | index 카드 사이 세로 화살표 2개 · 흐름 화살표 2개 |
| F13 | 계통 레이어 = 참고지표 문구 · 접속 보장 표현 금지 | `V55.GRID_NOTE` 원문 그대로 패널·팝업·표 각주에 삽입 · 팝업 "참고지표 — 실제 접속 가능 용량 아님" | REFLECTED | finder gridNote 텍스트 |
| F14 | 계통 범례·슬라이더 일치 — 단 후보 규모(MW)와 계통 여유를 한 범례로 합치지 않음 | 규모 범례(`legendHTML`, 50–100/100–200/200+ MW) 와 계통 범례(`gridLegendHTML`) 분리 · 슬라이더 문턱 아래 구간은 흐리게(dim) | REFLECTED_WITH_METHOD_CHANGE | 문턱 50MW에서 하위 5구간(포화·0–2·2–8·8–20·20–50) 흐림 실측 · 문턱 변경 시 같은 규칙(rAF 갱신 — 백그라운드 탭에서는 측정 불가) · 두 범례 독립 |
| F15 | 우선순위 3축 복수 선택(A/B/C/A+B/A+C/B+C/A+B+C) | `V55.axesControl` 체크박스 3종 · regions Step 2 · local 위저드 4단계 | REFLECTED | regions 모드 전환 검증(1·2·3축) |
| F16 | 1개 축 = 해당 축 정렬 · Pareto 미사용 | `top10.select` mode 'rank' — 값 정렬 순위, 결측은 순위 제외하고 표 아래 명시 | REFLECTED | 해남 발전 규모 TOP 10 · 산업단지 거리 TOP 10(1위 #6776740) |
| F17 | 2개 이상 축 = 기존 비교 엔진 · 새 scoring formula·가중치 금지 | 비지배 집합(전수 쌍별 지배 비교 · 결측=축 최악 · 동률≠지배)을 축 부분집합에 적용해 export 시 사전 계산(`fronts`) · 3축은 `query._frontier_mask`와 일치 검증(G1, 1,574 시군×칸 + 표시 규모 부분집합) | REFLECTED | export 로그 "G1 통과" · 화면은 플래그를 읽기만 함 |
| F18 | 3축 모두 = 자동 비교 · Pareto/non-dominated/MCDM 용어를 기본 화면에 강요하지 않음 | 3축 = 3축 비지배 집합 · 화면 표기 "주요 비교 후보" · 방법론 팝업/근거와 방법에서 실제 명칭(비지배 집합) 설명 | REFLECTED | 해남 3축 → 주요 비교 후보 6곳 |
| F19 | 탭 "우리 동네 TOP 10" · 우선순위 선택 시 실제 순위 1~10 · 자동 비교는 단일 순위 강제 금지("주요 비교 후보") | 1축 = 순위 번호 원 · 2축 이상 = ◆ 배지 "주요 비교 후보", 면적순 표시(순위 아님) | REFLECTED | regions 표 헤더 '순위'/'후보' 전환 · 마커 `.v55-mk.cmp` |
| F20 | PNU/지번 검색 · 개별 필지 클릭 기본 금지 · ① 적격+후보 공간 포함 ② 적격이나 규모 미달 ③ 적격 아님 구분 · "후보 공간에 없음"≠"부적격" | `export_pnu_v4.py`(members·clusters 등재 런 R0/R2/R3 → pnu/{sgg}) + `bjd_v4`(원장 코드→법정동명) · `V55.pnu.parse/classify/pnuCard` · local·regions 검색창 통합 · ③ 문구 "분석 기준 적격 목록에 없음 — 부적격 단정 아님" | REFLECTED_WITH_METHOD_CHANGE | PNU 4682043035110990000 → 시행 전 ③ · 시행 후 ①(#6747829 0.89 km²) · 지도 필지 클릭 없음 · ③ 표현을 검토안의 "적격 아님"에서 완화(연구 의미 보존) |
| F21 | 품질정보 VALID/CONDITIONAL/UNVERIFIED/UNKNOWN 유지(기존 시설 위치 확인 상태 · 소유주 정보 아님) · 후보 공간 폴리곤과 혼동 금지 | `export_existing_v4.py` — spatial_attribution_v1 등급별 건수 시군 집계 + VALID 좌표만 점 레이어(ADR-0053) · `existing.summaryHTML` 4등급 칩 · 후보 공간 폴리곤과 별도 pane·별도 설명 | REFLECTED | 당진: VALID 0·CONDITIONAL 1,129·UNVERIFIED 367·UNKNOWN 0 · 해남 VALID 320 표시 |
| F22 | 자료 기준일 — 실제 metadata에서, 전국 공통 날짜 임의 생성 금지 | `provenance_v4.json`(provenance_v1 값 그대로) + meta lineage → `V55.dataDates` 표 · 없는 값은 "기록 없음"(규제 레이어·경사) | REFLECTED | index/finder/regions/local 자료 기준일 표 · 추정값 0 |
| F23 | 기존 영농형 시설 전수 아님 명시 · 추천 공간=빈 부지 표현 금지 | `V55.EXISTING_NOTE` 원문을 index·finder·regions·local·팝업에 삽입 · 기존 시설 레이어 라벨 "위치 검증분 · 전수 아님" | REFLECTED | 각 화면 v55-note |
| F24 | 표시 수치가 query 결과와 일치 · 하드코딩 검사 · 모집단 변경 시 자동 연동 | 카드·결론 전부 data_v4 렌더 · site_gate PASS(FAIL 0) · 새 화면 5종을 게이트 스캔 목록에 추가 | REFLECTED | `site_gate.py` PASS — 경고 15는 기존 페이지 잔존분(신규 화면 0) |
| F25 | QA 12항목 × 1280/375 | 아래 §2 | REFLECTED | §2 |
| F26 | 최종 보고 형식 | 이 파일 | REFLECTED | — |
| F27 | 금지사항 | production·freeze·원고·21m·cluster/특구 정의·scoring·접속 보장·전수 표현·시점 추정·하드코딩 모두 미변경/미사용 · `≤1000m` cc 층은 LEGACY 보존(파일 유지, 화면 미사용) | REFLECTED | `git diff --stat` 에 model/·Ledger_Rebuild/ 변경 없음(사이트 레포만) |

예상 예외 2건은 검토의견을 거부한 것이 아니라 연구 의미 보존을 위한 조정이다: (1) cluster/특구 명칭 → 후보 공간(자문 후 후속 변경) (2) 계통·규모 단일 범례 → 각 레이어 범례를 정합화하고 분리.

## 2. QA 기록 (2026-09-23 · 로컬 정적 서버 127.0.0.1:8765 · 내장 브라우저)

| # | 항목 | 1280px | 375px | 근거 |
|---|---|---|---|---|
| ① | 전국 모아보기 | PASS — 카드 3장 값 렌더, 콘솔 오류 0 | PASS — 가로 스크롤 없음(scrollWidth 375), 카드 1열 | JS 검증 스크립트 |
| ② | 시나리오별 결과 | PASS — R코드 0건, 배지 "정본 등재 조합", 방법론 버튼 | (레이아웃 기존 유지) | innerText 정규식 |
| ③ | 우리 동네 TOP 10 | PASS — 당진 TOP 10(면적) · 해남 1축/2축/3축 전환 | PASS — 가로 스크롤 없음, 표는 컨테이너 내부 스크롤 | JS 검증 |
| ④ | 우리 동네 검색 | PASS — "당진시" → 위저드 6단계 → 결과 | PASS — 안내 3카드 1열 | JS 검증 |
| ⑤ | PNU 검색 | PASS — 19자리 PNU → ①/③ 분류 카드 · 시군 분석 연결 | — | 결과 텍스트 |
| ⑥ | 1축 우선순위 | PASS — 순위 1~10, 결측 후보 표 아래 명시 | — | 해남 |
| ⑦ | 2축 우선순위 | PASS — 주요 비교 후보(◆) | — | 해남 a+b 3곳 |
| ⑧ | 3축 우선순위 | PASS — 주요 비교 후보 | — | 해남 6곳 |
| ⑨ | 자동 비교 | PASS — 3축 = 비지배 집합, 단일 순위 없음 | — | — |
| ⑩ | 방법론 팝업 | PASS — 열림/닫힘 | — | modal.open |
| ⑪ | 계통 레이어 | PASS — 슬라이더·범례 dim 동기화(문턱 50: 하위 5구간 흐림), 참고지표 문구 | — | dim 5 실측 |
| ⑫ | 후보 공간 레이어 | PASS — 25 폴리곤(경계 미절단), 규모 범례 분리 | PASS — 줌 컨트롤 지도 안, 패널 static | JS 검증 |

텍스트 겹침·지도 컨트롤 겹침: 1280px 패널(right 314px) vs 줌(left 1221px) 겹침 없음. 375px 패널은 지도 위 static 배치. 범례 불일치: 규모/계통 분리. 카드 정렬: 세로 1열. overflow: 문서 가로 스크롤 없음(표는 자체 스크롤).
스크린샷: 후보지 찾기(1280px) 캡처로 패널·범례·오른쪽 끝 줌 컨트롤·표 서랍 배치를 육안 확인. 다른 화면은 브라우저 창이 백그라운드여서 캡처가 간헐적으로 실패해 DOM 측정값(오류 수집기 `window.__errs` = [] · 폴리곤 path 수 · 마커 수 · scrollWidth)으로 대체했다 — push 전 사용자 육안 검수 권장.

## 3. 데이터 자산 (신규 · 전부 정본 산출의 export, 새 판정 없음)

| 파일 | 원천 | 게이트 |
|---|---|---|
| data_v4/top10/{sgg}.json.gz · top10_index.json | scenario_runs block_context(8칸) · demand_sgg(표기) | G1 3축 = query._frontier_mask(1,574 시군×칸 + 규모 부분집합) · G2 행 수·면적 합 |
| data_v4/units/{sgg}.json.gz · units_big.json.gz · units_index.json | Ledger_Rebuild/analysis_units/analysis_unit_v1.gpkg(v9_02) | 14,721 = DuckDB analysis_unit_v1 · lab 집합·면적 합 일치 |
| data_v4/pnu/{sgg}.json.gz · pnu_index.json · bjd_v4.json.gz | members·clusters(R0/R2/R3) · ledger.region × bjd_code | 필지 수 = members 행 · 단위 면적 합 = clusters 합 |
| data_v4/existing_pv_v4.json.gz · provenance_v4.json | existing_pv_v1 × spatial_attribution_v1(VALID 9,379) · provenance_v1 | ADR-0053 규칙 |

## 4. 남은 일 · 주의

- **push 금지** — 로컬 커밋만. Pages 반영은 사용자 지시 후.
- `assets/cand.js`·`cand.css`·`data_v4/cand/`·`recommend_cc_v4.json.gz`는 화면에서 더 쓰지 않으나 LEGACY로 보존(≤1000m 응축 · 자문 결과에 따라 재사용 여부 결정).
- 지역별 우선 후보 화면의 보조 도구(반경 판독기 · 지역 전력판매량 대비 카드 · 분산특구 열쇠 표)는 TOP 10 재구성에서 제외했다(cc 전선 전용 자료 · "특구" 어휘). 전력판매량 대비는 표의 열로 유지.
- 시행 전·이격 조건의 지도 도형은 등재 런의 시군 구간 폴리곤(15m 단순화 · 시군 경계 절단)이다. 경계 미절단 단위 폴리곤은 진흥구역 개방 조건만 존재(analysis_unit_v1) — 다른 조건도 필요하면 v9_02를 그 런으로 실행해 export 추가.
- 방법론 팝업은 화면별 정적 서술이며 수치를 담지 않는다(수치는 화면 렌더).
- `publish.py` 의 export 목록에 신규 4개 스크립트를 추가해 두었다(§5).

## 5. publish.py 순서

수치: export_top10_v4 · export_pnu_v4 · export_existing_v4 (기존 NUM 뒤) · 지오: export_units_v4 (analysis_unit_v1.gpkg 존재 시).
