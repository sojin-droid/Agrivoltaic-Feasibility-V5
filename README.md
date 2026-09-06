# 영농형 태양광 설치 가능 농지 — 전국 분석 사이트

전국 필지 전수 분석의 결과를 공개하는 정적 사이트.
데이터 세대는 **격자 선언이 정한다** — 지금은 `ADR-0040+0041` (`grids/adr0041_25.yaml`).
페이지 푸터에 그 표식이 그대로 찍히므로 화면과 산출물의 판이 어긋날 수 없다.

> **공개 사이트 (GitHub Pages)**: https://sojin-droid.github.io/Agrivoltaic-Feasibility/

## 페이지 (레포 루트 = Pages 루트)

| 페이지 | 내용 |
|---|---|
| `index.html` | 결론 — 현행법 기준값과 네 가지 제도 조합 |
| `evidence.html` | 근거 — 조합 매트릭스(전국·간척) · 풀 분해 · 소유 세 무리 |
| `map.html` | 지도 — 시나리오별 연접 구획, 대조군 겹쳐 보기 |
| `candidates.html` | 특구 후보 — 법인·국공유 구획 |
| `proximity.html` | 산단 연계 — 구획 × 산업단지 × 읍면동 계통 여유 |
| `atlas.html` | 간척 아틀라스 — 필지 단위 소유 구분 |
| `insight.html` | 인사이트 |
| `method.html` | 방법·재현 — 깔때기, 판정 조건, 검증 체계 |
| `about.html` | 자료·한계 — 데이터 계보, 단위·환산 가정 |

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
- **칸 목록도 데이터다.** 근거 탭 표 5 는 `results_v4.cells.policy` 를 순회한다.
  격자 선언에 칸이 늘면 표에 줄이 늘고, 표시 이름은 시나리오 선언의 `label` 에서 온다.
- **판정 SQL 은 한 곳에만.** `data_v4/` 는 정본 질의 모듈(`model/query.py`)을
  직접 불러 만든다. 조건이 바뀌면 `query.py` 한 곳만 바뀐다.
- **어긋난 값은 파일이 되지 않는다.** export 가 기준값(T14) 정확 일치를 내장 검증한다.
- **판 표식은 선언에서 읽는다.** 사람이 문자열을 고치지 않는다.
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
