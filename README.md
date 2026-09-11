# 영농형 태양광 설치 가능 농지 — 전국 분석 사이트 (V5.1)

전국 필지 전수 분석의 결과를 공개하는 정적 사이트.
데이터 세대는 **격자 선언이 정한다** — 지금은 `ADR-0040+0041` (`grids/adr0041_25.yaml`).
페이지 푸터에 그 표식이 그대로 찍히므로 화면과 산출물의 판이 어긋날 수 없다.

> **공개 사이트 (GitHub Pages)**: https://sojin-droid.github.io/Agrivoltaic-Feasibility-V5/

## 페이지 — V5.1 5탭 + 우리동네 (레포 루트 = Pages 루트)

| 화면 | 파일 | 질문 · 내용 |
|---|---|---|
| 한눈에 보기 | `index.html` | 전국적으로 얼마나 더 쓸 수 있는가 — 현행(R0) 대 제약 완화(R1–R3) 비교 박스(필지 → 연접 구획 → 규모 눈금 이상) · 한 줄 결론 · Explore(다음 화면) |
| 후보지 찾기 | `finder.html` | 전국 어디가 후보인가 — 전면 지도 + 왼쪽 레이어 패널(대규모 후보 25곳·산업단지·계통 여유·반경) + 표 서랍 |
| 정책 시나리오 | `scenarios.html` | 조건을 바꾸면 어떻게 달라지는가 — 광역→시군 2단계 선택 × 제약 조건 조합(진흥·보호 개방, 이격, 매립지 범위, **시행령 고려/미고려**, 소유) → 필지·구획·규모 눈금 결과 + 미고려/고려 비교표 · 증분 지도 · 요약표(시행령 고려 표 포함) |
| 지역별 우선 후보 | `regions.html` | 우리 지역에서는 어디를 우선 검토할 것인가 — 시군 지도 + 공동 1등 후보(비지배 집합) 표 + 면적/산단 거리/계통 여유 3축 토글·★ 배지 |
| 우리동네 클러스터 고르기 | `local.html` | 주소 입력 → 정책 조건 위저드 → 후보 클러스터 지도·표 → 인쇄용 보고서(`window.print`) — 지자체·주민용 별도 흐름 |
| 근거와 방법 | `method.html` | 이 숫자와 방법은 어디에서 왔는가 — 1 배경(핵심 결과 다섯 가지) · 2 법·제도 근거(`#law`, 시행령 조문·함의) · 3 공간분석 방법(판정 조건·`#datarules`·검증·`#caveats`) · 4 우선 후보 선정(`#ranking`) · 5 데이터 출처 · 6 Sources(`#fnsec`, 전 화면의 출처를 여기로 통합) |

출처 목록은 「근거와 방법」에만 렌더된다(`body[data-sources=full]`) — 다른 화면의 각주 마커 [n]은 `method.html#fn-n`으로 연결.
공통 부품: `assets/region.js`(광역→시군 선택기 · 읍면동 이름 검색 — `sgg_matrix`·`grid_emd` 재사용), `assets/v5.css`(비교 박스·전면 지도·선택기·토글·위저드·인쇄).
비지배 집합 계산은 `model/query.py`에 그대로 있고, 화면은 "공동 1등 후보"라는 말로 같은 결과를 보인다 — 새 점수 체계는 없다.

구 탭은 리다이렉트 스텁으로만 남아 있다(링크 보호):
`proximity.html`·`map.html`·`candidates.html` → 후보지 찾기 ·
`evidence.html` → 정책 시나리오 · `estimate.html` → 정책 시나리오 `#builder` · `decree.html` → 정책 시나리오 `#decree` ·
`about.html` → 근거와 방법 `#caveats` · `insight.html` → 한눈에 보기.

## 구조

```
publish.py            발행 오케스트레이션 — 순서를 사람이 아니라 코드가 안다
pipeline/
  paths.py            경로는 여기서만 정한다 (SITE·OUT·ROOT·MODEL·LR·CAD)
  export/  7개        정본 질의 → data_v4/*.json (수치)
  geom/    4개        구획 폴리곤 → data_v4/clusters/ (지오메트리)
  gate/    1개        site_gate — FAIL 이면 발행하지 않는다
  legacy/  36개       구세대 — 돌리지 않음 (legacy/README.md)
data_v4/              발행 자산 — 브라우저가 받는 유일한 데이터
assets/               v4.js · v4.css · 로고
```

## 데이터 규율

- **화면은 계산하지 않는다.** 수치는 전부 `data_v4/*.json` 에서 렌더한다.
  본문 산문의 숫자도 마찬가지다 — 게이트가 하드코딩 의심 수치를 잡는다.
- **칸 목록도 데이터다.** 정책 시나리오 탭 표 5 는 `results_v4.cells.policy` 를 순회한다.
  격자 선언에 칸이 늘면 표에 줄이 늘고, 표시 이름은 시나리오 선언의 `label` 에서 온다.
- **판정 SQL 은 한 곳에만.** `data_v4/` 는 정본 질의 모듈(`model/query.py`)을
  직접 불러 만든다. 조건이 바뀌면 `query.py` 한 곳만 바뀐다.
- **어긋난 값은 파일이 되지 않는다.** export 가 기준값(T14) 정확 일치를 내장 검증한다.
- **판 표식은 선언에서 읽는다.** 사람이 문자열을 고치지 않는다 — 선언 파일은 sha12(바이트
  해시)로 세대를 식별하므로, 구용어가 남아 있으면 선언을 고치는 대신 발행 층에서 표기만
  교정한다(`export_v4.py` 의 `_NOTE_FIX`).
- 자족형 — 외부 CDN·API 로드 없음.

## 갱신

```bash
python publish.py
```

```bash
python publish.py --geom
```

```bash
python publish.py --commit "메시지"
```

기본은 수치만 다시 만든다(빠름). `--geom` 은 구획 폴리곤까지 다시 굽는다(수십 분).
`publish.py` 는 push 하지 않는다 — 바깥으로 나가는 일은 사람이 누른다.

값 자체를 다시 만들려면 모델 쪽에서 격자를 돌린 뒤 발행한다.

```bash
agv grid run adr0041_25
```

구세대(2026-07, 21개 분석구역·MW 1차·구 S0/S1/S2) 페이지·데이터는 git 이력에 보존.
전체 설계와 원칙 4축 13항은 `REWORK_PLAN.md`.
