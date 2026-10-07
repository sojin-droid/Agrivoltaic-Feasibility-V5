# 클러스터링 방법론 자문 — 제공 자료 목록

작성 2026-10-07 · PLANiT · 한국환경연구원(KEI) 서면 자문 · 저장소 `sojin-droid/Agrivoltaic-Feasibility-V5` (main `96a49e4`)

## 1. 자문자에게 보내는 링크 (메일 본문)

| 구분 | 자료 | 링크 | 용도 |
|---|---|---|---|
| 화면 | 자문 화면 `cluster_advisory.html` | https://sojin-droid.github.io/Agrivoltaic-Feasibility-V5/cluster_advisory.html | ① 공간 분석 방법 ② 방법 비교·우선순위 비교 ③ 검토 대상지 10곳 지도 ④ 자문 질문 M1–M9 입력 ⑤ 응답 JSON/CSV 내보내기 |
| 문서 | 자문 자료 `METHOD_ADVISORY.md` | https://github.com/sojin-droid/Agrivoltaic-Feasibility-V5/blob/main/docs/METHOD_ADVISORY.md | 화면과 같은 내용의 문서판 — 연구 개요 · 공간 분석 절차 · 연접 거리 산정 · 후보 공간 분포 · 묶음 방법 비교 · 우선순위 비교 방법 · 비교 축 자료 분포 · 용어 · 질문 · 참고 자산 |
| 문서 | 검토 대상지 선정 기준 `STUDY_AREAS.md` | https://github.com/sojin-droid/Agrivoltaic-Feasibility-V5/blob/main/docs/method_advisory/STUDY_AREAS.md | 10곳 선정 원칙·층 정의·시군별 프로파일 |
| 문서 | 평가 지표 정의서 `METRICS_DEFINITIONS.md` | https://github.com/sojin-droid/Agrivoltaic-Feasibility-V5/blob/main/docs/method_advisory/METRICS_DEFINITIONS.md | 묶음 방법 비교에 쓴 5축 11지표의 입력 규격·계산식·방향 |
| 데이터 | 검토 대상지 10곳 데이터 패키지 (Release) | https://github.com/sojin-droid/Agrivoltaic-Feasibility-V5/releases/tag/cluster-advisory-20261007 | 시군별 zip 10개 + 전체 zip + 체크섬 |
| 참고 | 공개 사이트 「근거와 방법」 | https://sojin-droid.github.io/Agrivoltaic-Feasibility-V5/method.html | 판정 조건(3-3) · 연접 기준 · 우선순위 비교 방법(4) |

## 2. 데이터 패키지 구성 (시군별 zip 공통)

| 파일 | 내용 | 비고 |
|---|---|---|
| `parcels.gpkg` · `parcels.csv` | 적격 필지 전량(이웃 시군 필지 포함): PNU · 소속 21m 단위(lab) · 장부 면적 · 지목 · 소유 유형 · 농업진흥지역 구분 · 팜맵 경작 판독비 · 경사 · 간척 원장 여부 · 이웃 간격 d1·d2·d4·d8·d12 · 필지 폴리곤 | 처음부터 다시 묶을 때 쓰는 층 |
| `units.gpkg` · `units.csv` | 21m 연접 단위 전량: 면적 · 필지 수 · 소유 구성비 · 간척 비중 · 경작 비율 · 대표점 · 산단 거리 · 계통 하한·상한 · 규모 눈금(1/3/10/20/50MW) · 3축 비지배 여부 · dissolve 폴리곤(단순화 없음) | 현행 기준선 |
| `unit_pairs.csv` | 단위 쌍 경계 간 거리(≤ 2,000 m) | 2단계 묶음 규칙 시험용 |
| `context/ind_complex.geojson` | 산업단지 경계(유형) — 15 km 안 | |
| `context/emd_grid.geojson` | 읍면동 경계 + 계통 여유 참고값(하한·상한·조회 상태) | 공간 교차로 선택 |
| `context/existing_pv.geojson` | 기존 태양광(위치 확인분 · 허가 주소 위치) | |
| `README.md` | 열 사전 · 기준일 · 좌표계(EPSG:5186) · 기하 결손 수 · 선정 층·이유 | |

전체: `cluster_advisory_pkg_all_20261007.zip`(68 MB) · 시군별 3.8–9.9 MB · `SHA256SUMS.json`. 2026-10-07 2판(규모 구분에 1MW 추가 · 체크섬 갱신).

| 층 | 시군 | 코드 | 단위(전량) | 필지 | 면적 km² | 1MW↑ | 3MW↑ | 50MW↑ |
|---|---|---|---:|---:|---:|---:|---:|---:|
| S1 | 충남 당진시 | 44270 | 4,129 | 15,198 | 35.11 | 124 | 43 | 4 |
| S1 | 전남 해남군 | 46820 | 4,154 | 19,188 | 63.45 | 185 | 111 | 5 |
| S1 | 충남 보령시 | 44180 | 3,079 | 13,027 | 12.42 | 65 | 16 | 1 |
| S2 | 경기 평택시 | 41220 | 4,201 | 27,972 | 18.04 | 157 | 49 | 0 |
| S2 | 전북 익산시 | 52140 | 5,227 | 23,894 | 17.78 | 110 | 25 | 0 |
| S2 | 전남 영광군 | 46830 | 3,404 | 12,891 | 17.52 | 82 | 30 | 0 |
| S3 | 전북 김제시 | 52210 | 4,444 | 17,639 | 15.89 | 92 | 20 | 0 |
| S3 | 경기 파주시 | 41480 | 2,258 | 9,377 | 5.55 | 43 | 6 | 0 |
| S3 | 충북 음성군 | 43770 | 3,633 | 16,400 | 10.47 | 68 | 13 | 0 |
| S4 | 경기 용인시처인구 | 41461 | 3,589 | 13,816 | 7.58 | 44 | 4 | 0 |

## 3. 저장소 안의 보조 자료 (링크로 도달 가능)

| 자료 | 경로 |
|---|---|
| 그림 8점 · 그림 수치 CSV | `docs/method_advisory/fig/` · `docs/method_advisory/data/` |
| 묶음 방법 비교 결과(10곳 × A/B/C/D 6조합) | `docs/method_advisory/data/method_comparison_sites.csv` |
| 현재 기준선 지표(전국 + 10곳) | `docs/method_advisory/data/metrics_current_21m.csv` |
| 검토 대상지 목록(기계 판독) | `docs/method_advisory/study_areas.json` |
| 자문 페이지 ③탭 전용: 기존 시설 허가 주소 필지 폴리곤 | `data_v4/existing_parcels/` |

## 4. 요청 시 제공 (비공개 저장소 발췌)

- 결정 기록 ADR-0041(기준값 폐지 원칙) · ADR-0055(전량 재산출)
- 방법 비교 보고(PR-0042) · 다기준 방법 비교(PR-0036)
- 공간 단위 개념 정본 `SPATIAL_UNITS.md`
- 평가 지표 계산 스크립트(`metrics.py`) — 자문자가 직접 시험을 원할 때

## 5. 회신 방식

- 자문 화면 ④탭에서 M1–M9에 답한 뒤 ⑤「의견 내보내기」에서 JSON 또는 CSV 내려받아 회신(파일명에 자문자 코드·날짜 자동).
- 또는 문서판 §9의 번호(M1–M9)를 붙여 서면 회신.
