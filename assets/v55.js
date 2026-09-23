/* V5.5 — GGI 내부 검토 반영 공용 모듈. 모든 화면이 같은 표기·같은 팝업·같은 검색·같은 TOP 10 규칙을 쓴다.
   원칙: 화면은 계산하지 않는다 — 수치·비지배 플래그·소속은 전부 data_v4 export 에서 읽고, 여기서는 고르고 정렬하고 그린다.
   용어: 21m 연접 단위 = "후보 공간"(공간 분석 단위). cluster·특구라 부르지 않는다(최종 cluster 정의는 자문 전). */
window.V55 = (() => {
  const $ = (s, r = document) => r.querySelector(s);
  const n = x => x == null ? '—' : Number(x).toLocaleString('ko-KR');
  const km2 = (m2, d = 1) => m2 == null ? '—' : (m2 / 1e6).toLocaleString('ko-KR', {minimumFractionDigits: d, maximumFractionDigits: d});
  const mw = m2 => m2 == null ? '—' : (m2 * 0.045 / 1000).toLocaleString('ko-KR', {maximumFractionDigits: m2 * 0.045 / 1000 >= 10 ? 0 : 1});
  async function gz(path) { const r = await fetch(path); if (!r.ok) return null; const ds = r.body.pipeThrough(new DecompressionStream('gzip')); return JSON.parse(await new Response(ds).text()); }

  // ── 시나리오 표기 — 사용자 화면에는 R0~R3 코드를 쓰지 않는다 ──
  const SCN = {
    R0_current: {short: '특별법 시행 전', long: '영농형태양광 특별법 시행 전 — 농업진흥지역 밖의 농지만', tag: '시행 전'},
    R1_protect: {short: '농업보호구역만 개방', long: '재생에너지지구에 농업보호구역만 포함되는 경우(가정)', tag: '보호구역 개방'},
    R2_promo:   {short: '특별법 시행 후 · 농업진흥구역 개방', long: '재생에너지지구에 농업진흥구역이 포함되는 경우(가정) — 대규모 후보 공간은 이 조건에서 나타남', tag: '시행 후(진흥구역 개방)'},
    R3_zone_all:{short: '특별법 시행 후 · 농업진흥지역 전체 개방', long: '재생에너지지구에 농업진흥구역·농업보호구역이 모두 포함되는 경우(가정)', tag: '시행 후(농업진흥지역 개방)'},
  };
  const scn = run => { const base = run.replace(/_SB(@.*)?$/, '$1').replace(/@.*$/, ''); const sb = /_SB/.test(run); const s = SCN[base] || {short: run, long: run, tag: run};
    return {...s, short: s.short + (sb ? ' · 주거 이격 200m 적용' : ''), tag: s.tag + (sb ? ' · 이격 적용' : ''), sb, base}; };

  // ── 공용 모달 ──
  function modal() {
    let bg = $('#v55modal');
    if (bg) return bg;
    bg = document.createElement('div'); bg.id = 'v55modal'; bg.className = 'v55-modal-bg'; bg.setAttribute('role', 'dialog'); bg.setAttribute('aria-modal', 'true');
    bg.innerHTML = `<div class="v55-modal"><button class="v55-x" aria-label="닫기">✕</button><div class="v55-modal-body"></div></div>`;
    document.body.appendChild(bg);
    const close = () => bg.classList.remove('open');
    bg.querySelector('.v55-x').onclick = close; bg.onclick = e => { if (e.target === bg) close(); };
    document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
    return bg;
  }
  function openModal(html) { const bg = modal(); bg.querySelector('.v55-modal-body').innerHTML = html; bg.classList.add('open'); bg.querySelector('.v55-modal').scrollTop = 0; }

  // ── 방법론 더 보기 — 화면별 팝업(실제 분석 방법 · 기준 · 계산 원리 · 자료 · 한계). 수치는 넣지 않는다(수치는 화면의 data_v4 렌더가 담당) ──
  const COMMON_TAIL = `
    <h4>자료</h4><ul>
      <li>연속지적도·토지 원장(필지 형상·지목·소유 구분·용도지역·장부면적) · 농업진흥지역도(V-World) · 팜맵 2025 · 규제 레이어(복합) · 경사 레이어 · 한전 분산전원 연계정보(단일 시점 스냅숏) · 산업단지 경계(V-World) · 법정동코드(code.go.kr).</li>
      <li>각 자료의 기준일은 화면의 <b>자료 기준일</b> 표에 provenance 기록값 그대로 표시한다. 기록이 없는 항목은 "기록 없음"으로 두고 추정하지 않는다.</li></ul>
    <h4>한계</h4><ul>
      <li>적격 = 이 분석의 판정 조건을 통과한 땅. 인허가 가능 토지·사업 승인이 아니다.</li>
      <li>MW는 면적 × 0.045 kW/㎡의 참고 환산값이며 실제 발전량·설치용량이 아니다.</li>
      <li>계통 여유는 한전 연계정보를 이용한 <b>참고지표</b>다. 실제 접속 가능 여부와 접속 가능 용량은 한전의 개별 연계 검토로만 확인된다.</li>
      <li>본 분석은 기존 설치 여부를 판별하는 서비스가 아니다. 결과에 포함된 지역에 기존 발전설비가 이미 있을 수 있다. 확보한 기존 시설 자료는 전국 전수가 아니다.</li>
      <li>후보 공간(21m 연접 단위)은 공간 분석 단위이며 최종 cluster·특구 정의가 아니다. 최종 정의는 전문가 자문 후 확정한다.</li></ul>`;
  const METHOD = {
    index: `<h3>방법론 더 보기 — 전국 모아보기</h3>
      <h4>쉽게 말하면</h4><p>전국의 모든 땅 조각(필지)을 하나씩 검사해 영농형 태양광을 놓을 수 있는 땅을 고르고, 특별법 시행 전(농업진흥지역 밖의 농지만)과 시행 후(농업진흥지역까지 개방된다고 가정)에서 그 땅이 얼마나 되는지, 서로 붙어 있는 땅을 묶으면 사업이 될 규모가 몇 곳 생기는지를 비교한 화면입니다.</p>
      <h4>실제 분석 방법</h4><ol>
        <li><b>필지 판정</b> — 지목(전·답·과수원) → 건축물·수역·산업단지 등 구조 제외 → 경사 15% 초과 제외 → 용도지역 3종 제외 → 농업진흥지역 구분. 소유는 법인·국공유(02·04·05·06)만 분석 기준 필지로 세고, 개인 소유를 포함한 값은 대조군으로 병기한다.</li>
        <li><b>시나리오</b> — 시행 전 = 농업진흥지역 밖 농지만. 시행 후 = 재생에너지지구에 농업진흥구역·농업보호구역이 포함되는 경우(가정). 법률 시행 여부와 무관한 <b>제도 설계 시나리오</b>다.</li>
        <li><b>21m 연접</b> — 경계가 서로 21m 이내인 적격 필지를 하나의 <b>후보 공간</b>(공간 분석 단위)으로 묶는다. 21m는 필지 간격 자료에서 유도한 분석 기준이며 법정 기준이 아니다. 묶어도 면적은 변하지 않는다.</li>
        <li><b>규모 눈금</b> — 3MW·50MW는 0.045 kW/㎡ 환산의 읽기 눈금(66,667㎡·1,111,111㎡)이다. 법정 규모 기준이 아니다.</li></ol>
      <h4>계산 원리</h4><p>화면의 모든 숫자는 정본 데이터베이스의 표준 질의 결과를 내보낸 파일에서 읽는다. 시행 전 대비 증가분은 ㎡ 원값끼리 빼서 계산하고, 세 풀(농업진흥지역 밖·보호구역·진흥구역)이 겹치지 않아 합계가 정확히 맞는지 발행마다 검사한다.</p>` + COMMON_TAIL,
    finder: `<h3>방법론 더 보기 — 대규모 후보 공간 지도</h3>
      <h4>쉽게 말하면</h4><p>특별법 시행 후 농업진흥구역이 개방된다고 가정했을 때, 법인·국공유 농지만 이어 붙여도 약 50MW 이상이 되는 큰 땅 덩어리가 전국 어디에 있는지 보여주는 지도입니다. 산업단지와 계통 여유는 비교를 돕는 배경 레이어이며 후보를 고르는 조건이 아닙니다.</p>
      <h4>실제 분석 방법 · 기준</h4><ul>
        <li>후보 공간 = 21m 연접 단위. 지도의 도형은 그 단위에 속한 필지의 지적 폴리곤을 합쳐 2m 허용오차로 단순화한 것이다(면적 수치는 장부면적 원값). 시군·읍면동 경계로 자르지 않는다 — 경계를 넘는 단위는 하나로 표시한다.</li>
        <li>대규모 = 장부면적 1,111,111㎡ 이상(≈50MW 등가 읽기 눈금). 상한은 없다.</li>
        <li>계통 여유(읍면동) = 한전 분산전원 연계정보의 배전선로 잔여 연계가능용량을 담당 읍면동에 균등 배분한 하한(lo)과 공유 미조정 상한(hi). 단일 시점 스냅숏이며 매핑된 선로 수와 함께 변한다 — 실제 접속 가능 용량이 아니다.</li>
        <li>산업단지 = V-World 산업단지 경계. 반경·거리는 표시용 직선거리다.</li>
        <li>기존 시설 = 확보한 공개 자료 중 위치가 독립 검증된(VALID) 좌표만 점으로 표시한다. 나머지 등급(CONDITIONAL·UNVERIFIED·UNKNOWN)은 건수만 적는다.</li></ul>
      <h4>계산 원리</h4><p>후보 공간의 규모 범례(MW)와 계통 여유 범례는 서로 다른 지표이므로 색상 체계를 분리한다. 계통 슬라이더는 표시 문턱만 바꾸며 값을 바꾸지 않는다.</p>` + COMMON_TAIL,
    top10: `<h3>방법론 더 보기 — 우리 동네 TOP 10</h3>
      <h4>쉽게 말하면</h4><p>고른 시군 안의 후보 공간(21m 연접 단위)을 발전 규모·계통 여유·산업단지 거리 중 원하는 기준으로 줄 세우거나, 여러 기준을 동시에 만족하는 후보를 골라 보여줍니다.</p>
      <h4>실제 분석 방법 · 기준</h4><ul>
        <li><b>모집단</b> — 그 시군에 관여하는 후보 공간 전량(정본 block_context · 규모 문턱 11,111㎡ 선언값). 최소 규모 선택은 표시 범위이며 후보를 만들거나 지우지 않는다.</li>
        <li><b>세 축</b> — A 발전 규모 = 장부면적(참고 MW 병기) · B 계통 = 소재 읍면동 잔여 연계가능용량 하한(lo, MW) · C 산업단지 = 최근접 산업단지 경계까지 직선거리(km).</li>
        <li><b>1개 축</b> — 그 축의 값으로 정렬한 순위(1~10). 점수·가중치 없음.</li>
        <li><b>2개 이상 축</b> — 기존 비교 엔진(비지배 집합)을 쓴다: 선택한 축 모두에서 다른 후보에 지지 않는 후보만 남긴다. 순위가 아니라 <b>주요 비교 후보</b> 집합이며, 새 점수·가중치를 만들지 않는다. 결측 축은 그 축의 최악값으로 두고 비교한다(숨은 배제 금지).</li>
        <li><b>3개 축 자동 비교</b> — 3축 비지배 집합. 정본 질의(query.py)의 함수와 같은 결과임을 발행 시 검사한다.</li></ul>
      <h4>계산 원리</h4><p>비지배 플래그는 발행 파일에 사전 계산되어 있고, 화면은 축 선택에 맞는 플래그를 읽어 표시한다. 걸침 후보(시군 경계를 넘는 단위)는 관련 시군마다 나타나므로 시군별 수를 더하지 않는다.</p>` + COMMON_TAIL,
    local: `<h3>방법론 더 보기 — 우리 동네 분석</h3>
      <h4>쉽게 말하면</h4><p>시·군이나 읍·면·동 이름(또는 필지 번호·지번)을 넣고 제도 조건과 우선순위를 고르면, 그 지역의 후보 공간을 지도와 표로 보여주고 인쇄용 보고서를 만듭니다.</p>
      <h4>실제 분석 방법 · 기준</h4><ul>
        <li><b>분석 단위는 시군</b>. 읍·면·동은 위치를 이해하는 배경(경계선)과 집계 기준으로만 쓰며, 후보 공간을 읍·면·동 경계로 자르지 않는다.</li>
        <li><b>제도 조건</b> — 시행 전 / 시행 후(농업진흥구역 개방) · 주거 이격 200m 적용 여부. 각 조합은 정본에 등재된 시나리오 실행값에서 읽는다.</li>
        <li><b>우선순위</b> — 발전 규모 · 계통 · 산업단지 중 복수 선택. 1개면 정렬, 2개 이상이면 비지배 집합(주요 비교 후보). 새 점수·가중치는 없다.</li>
        <li><b>PNU·지번 검색</b> — 필지가 ① 적격이고 규모 기준 이상 후보 공간에 포함 ② 적격이나 규모 기준 미달 ③ 분석 기준 적격 목록에 없음 중 어디인지 시행 전·후로 보여준다. ③은 부적격 판정이 아니다 — 지목·소유(개인 소유는 분석 기준 밖)·제외조건 어느 것인지 이 화면은 구분하지 않는다.</li></ul>` + COMMON_TAIL,
    scenarios: `<h3>방법론 더 보기 — 시나리오별 결과</h3>
      <h4>쉽게 말하면</h4><p>농업진흥구역·농업보호구역 개방, 주거 이격, 매립지 범위, 소유 기준을 바꿔 가며 설치 가능 면적과 후보 공간이 어떻게 달라지는지 비교합니다.</p>
      <h4>실제 분석 방법 · 기준</h4><ul>
        <li>필지층 값은 사전 집계 큐브(시군 × 소유 × 구역 × 이격 × 간척 범위)를 화면에서 다시 더한 것이며, 후보 공간(21m 연접) 값은 정본에 등재된 시나리오 실행에서만 제공한다.</li>
        <li>"시행령 고려"는 제정안 조문의 부지 한정을 범위로 적용한 것이며 후보를 늘리지 않는다.</li></ul>` + COMMON_TAIL,
  };
  function methodButton(el, key, {label = '방법론 더 보기', cls = 'btn btn-ghost'} = {}) {
    if (!el) return null;
    const b = document.createElement('button'); b.type = 'button'; b.className = cls + ' v55-method'; b.textContent = label;
    b.onclick = () => openModal(METHOD[key] || METHOD.index);
    el.appendChild(b); return b;
  }

  // ── 자료 기준일 — provenance_v4(값 그대로) + meta lineage. 기록이 없으면 "기록 없음" ──
  const DATE_ROWS = [   // [표시명, provenance dataset_id 후보(순서), 참고 lineage tbl]
    ['지적 원장·연속지적도', ['raw:cadastre_all', 'raw:land_processed_db'], null],
    ['농업진흥지역 경계', ['raw:agpromo_raw'], 'agpromo_bnd'],
    ['팜맵(경작 판독)', ['raw:farmmap_2025'], 'fm2025'],
    ['규제 레이어(복합)', ['raw:regulation_composite'], null],
    ['경사 레이어', ['raw:slope'], null],
    ['한전 분산전원 연계정보(계통)', ['raw:kepco_raw_v4'], 'kepco_record_v3'],
    ['산업단지 경계', ['raw:damdan_raw'], 'ind_complex_bnd'],
    ['읍면동 경계(표시용)', ['raw:emd_bnd_raw'], 'emd_bnd'],
    ['시군 전력판매량(참고)', ['raw:kepco_demand_cache'], null],
    ['기존 태양광 시설(공개 자료)', ['src:kpx_plants_raw', 'src:permit_raw'], null],
  ];
  async function dataDates(el, {compact = false} = {}) {
    if (!el) return;
    const [P, M] = await Promise.all([fetch('data_v4/provenance_v4.json').then(r => r.ok ? r.json() : null).catch(() => null), V4.data('meta_v4')]);
    const rows = P ? Object.fromEntries(P.rows.map(r => [r[0], Object.fromEntries(P.cols.map((c, i) => [c, r[i]]))])) : {};
    const lin = Object.fromEntries((M.lineage || []).map(r => [r.tbl, r]));
    const unk = v => !v || v === 'unknown' || v === 'not_documented';
    el.innerHTML = `<table class="v55-dates"><tr><th>자료</th><th>수집·기준일</th><th>원천 판</th></tr>` + DATE_ROWS.map(([nm, ids, tbl]) => {
      const p = ids.map(i => rows[i]).find(Boolean); const l = tbl ? lin[tbl] : null;
      const date = p && !unk(p.collection_date) ? p.collection_date : (l ? l.built + ' <small>(구축일)</small>' : '<span class="v55-unk">기록 없음</span>');
      const ver = p && !unk(p.original_source_version) ? p.original_source_version : (p ? '<span class="v55-unk">원천 판 기록 없음</span>' : '<span class="v55-unk">기록 없음</span>');
      return `<tr><td>${nm}</td><td>${date}</td><td>${compact ? '' : ver}</td></tr>`; }).join('') +
      `</table><div class="v55-hint">provenance 레지스트리(ADR-0053) 기록값. 없는 값은 추정하지 않고 "기록 없음"으로 둔다.</div>`;
  }
  const EXISTING_NOTE = '본 분석은 현재 설치 여부를 완전히 판별하는 서비스가 아니라, 확보된 토지·입지·계통 및 공간정보를 바탕으로 영농형 태양광의 입지 적합성과 후보 공간을 분석한 결과입니다. 따라서 분석 결과에 포함된 지역에 기존 발전설비가 이미 존재할 가능성이 있습니다. 확보한 기존 시설 자료는 전국 전수가 아닙니다.';
  const GRID_NOTE = '한전 연계정보를 바탕으로 산출한 계통 여유 참고지표입니다. 실제 발전설비의 계통 접속 가능 여부와 접속 가능 용량은 한전의 개별 연계 검토를 통해 확인해야 합니다.';

  // ── 규모(MW) 범례 — 후보 공간 규모 전용. 계통 범례와 섞지 않는다 ──
  const MW_BANDS = [[1111111, '#A8651A', '50MW 이상'], [444444, '#D98E1B', '20–50MW'], [222222, '#F2B233', '10–20MW'], [66667, '#FFD84D', '3–10MW'], [0, '#E6E0CF', '3MW 미만']];
  const BIG_BANDS = [[4444444, '#7A3E0A', '200MW 이상'], [2222222, '#A8651A', '100–200MW'], [1111111, '#D98E1B', '50–100MW']];
  const bandOf = (a, bands = MW_BANDS) => bands.find(([min]) => a >= min) || bands[bands.length - 1];
  const legendHTML = (bands, title) => `<div class="v55-leg"><b>${title}</b>` + bands.map(([, c, l]) => `<span><i style="background:${c}"></i>${l}</span>`).join('') + `</div>`;
  const GRID_BINS = [[50, '#1C5F86', '50+'], [20, '#4A94BA', '20–50'], [8, '#8FC0D8', '8–20'], [2, '#CFE3EE', '2–8'], [0.0001, '#F0F4F6', '0–2']];
  const GRID_SAT = '#EFDFDD', GRID_UNK = '#CFCFCF';
  // 계통 범례 — 슬라이더 문턱과 색상 일치: 문턱 아래 구간은 흐리게
  const gridLegendHTML = (threshold) => `<div class="v55-leg v55-leg-grid"><b>계통 여유 참고지표(읍면동 하한, MW)</b>` +
    [[null, GRID_SAT, '포화(0)', 0], ...GRID_BINS.slice().reverse().map(([th, c, l]) => [th, c, l, th])].map(([th, c, l, v]) =>
      `<span class="${threshold > 0 && v < threshold ? 'dim' : ''}"><i style="background:${c}"></i>${l}</span>`).join('') +
    `<span><i style="background:${GRID_UNK}"></i>알 수 없음</span></div>`;

  // ── 후보 공간 폴리곤(21m 연접 단위 · analysis_unit_v1 · 진흥구역 개방 기준) ──
  const units = {
    async load(sgg) { return gz(`data_v4/units/${sgg}.json.gz`); },
    async big() { return gz('data_v4/units_big.json.gz'); },
    layer(fc, {pane, bands = MW_BANDS, onClick, dimBelow = 0, highlight = new Set(), tooltip} = {}) {
      return L.geoJSON(fc, {pane, style: f => { const p = f.properties, b = bandOf(p.a, bands), hi = highlight.has(p.id), below = p.a < dimBelow;
          return below ? {color: '#9AA5B1', weight: .5, opacity: .5, fillColor: '#9AA5B1', fillOpacity: .08}
                       : {color: hi ? '#0C356A' : '#6B4E16', weight: hi ? 3 : (p.ns > 1 ? 1.6 : .8), dashArray: p.ns > 1 ? '5 4' : null, fillColor: b[1], fillOpacity: .78}; },
        onEachFeature: (f, ly) => { const p = f.properties;
          ly.bindTooltip(tooltip ? tooltip(p) : `후보 공간 #${p.id} · ${km2(p.a, 2)} km² ≈ ${mw(p.a)} MW · 필지 ${n(p.n)}${p.ns > 1 ? ' · 시군 경계 걸침(하나로 유지)' : ''}`);
          if (onClick) ly.on('click', () => onClick(p, ly)); }});
    },
    // 다른 시나리오(시행 전·이격) 는 등재 런의 시군 구간 폴리곤 파일(clusters/)로 폴백 — 시군 경계 걸침은 sp 로 표기
    async loadRun(sgg, run) { const gj = await gz(`data_v4/clusters/${sgg}_${run}.json.gz`); if (!gj) return null;
      gj.features.forEach(f => { const p = f.properties; p.a = Math.round((p.a || 0) * 1e6); p.ns = p.sp ? 2 : 1; }); return gj; },
  };

  // ── TOP 10 엔진 — data_v4/top10/{sgg}.json.gz (전량 + 비지배 플래그) ──
  const AXES = {a: {name: '발전 규모', key: 'a', dir: -1, unit: (r) => `${km2(r.a, 2)} km² ≈ ${mw(r.a)} MW`},
                b: {name: '계통 여유(참고)', key: 'lo', dir: -1, unit: (r) => r.lo == null ? '알 수 없음' : `${n(r.lo)} MW`},
                c: {name: '산업단지 거리', key: 'd', dir: +1, unit: (r) => r.d == null ? '알 수 없음' : `${r.d.toFixed(1)} km`}};
  const FLAG = {'ab': 'fab', 'ac': 'fac', 'bc': 'fbc', 'abc': 'f3'};
  const top10 = {
    _cache: {}, _idx: null,
    async index() { if (!this._idx) this._idx = await V4.data('top10_index'); return this._idx; },
    async load(sgg) { if (!(sgg in this._cache)) this._cache[sgg] = await gz(`data_v4/top10/${sgg}.json.gz`); return this._cache[sgg]; },
    rows(data, run, minM2 = 0) { if (!data || !data.runs[run]) return null; const C = data.cols;
      return data.runs[run].rows.map(r => Object.fromEntries(C.map((c, i) => [c, r[i]]))).filter(r => r.a >= minM2); },
    /** axes: Set of 'a','b','c'. 1개 → 정렬 순위(top N) · 2개 이상 → 비지배 플래그(사전 계산) 집합. 새 점수 없음. */
    select(rows, axes, top = 10, {fronts = null, minM2 = 0} = {}) {
      const ax = ['a', 'b', 'c'].filter(k => axes.has(k));
      if (!rows) return {mode: 'none', list: [], note: '자료 없음'};
      if (ax.length === 0) { return {mode: 'area', list: rows.slice().sort((x, y) => y.a - x.a).slice(0, top), note: '우선순위 미선택 — 면적순 표시(순위 아님)'}; }
      if (ax.length === 1) { const A = AXES[ax[0]];
        const list = rows.filter(r => r[A.key] != null).sort((x, y) => A.dir * (x[A.key] - y[A.key])).slice(0, top).map((r, i) => ({...r, rank: i + 1}));
        const unk = rows.filter(r => r[A.key] == null).length;
        return {mode: 'rank', axis: ax[0], list, note: `${A.name} 기준 정렬 순위 — 값이 큰(가까운) 순. 점수·가중치 없음.${unk ? ` 값을 알 수 없는 후보 ${n(unk)}곳은 순위에서 제외하고 표 아래에 적음.` : ''}`, unknown: unk}; }
      const fl = FLAG[ax.join('')];
      // 비지배 플래그는 표시 모집단(최소 규모 이상)에 맞춘 사전 계산값을 쓴다 — 없으면 전량 모집단 플래그로 폴백
      const fr = fronts && fronts[String(minM2)] && fronts[String(minM2)][fl];
      const set = fr ? new Set(fr) : null;
      const list = rows.filter(r => set ? set.has(r.lab) : r[fl]).sort((x, y) => y.a - x.a);
      return {mode: 'compare', axes: ax, flag: fl, list, note: `${ax.map(k => AXES[k].name).join(' · ')} — 선택한 축 모두에서 다른 후보에 지지 않는 <b>주요 비교 후보</b>(비지배 집합 · 비교 모집단 = 표시 규모 이상 후보 전량). 순위가 아니며 새 점수·가중치를 만들지 않음. 표시는 면적순.`};
    },
    // 모집단 안에서의 축별 순위(표시용 — 정렬은 같은 규칙)
    ranks(rows) { const out = new Map(rows.map(r => [r.lab, {}]));
      for (const k of ['a', 'b', 'c']) { const A = AXES[k]; const s = rows.filter(r => r[A.key] != null).sort((x, y) => A.dir * (x[A.key] - y[A.key]));
        s.forEach((r, i) => { out.get(r.lab)['r' + k] = i + 1; }); }
      return out; },
    AXES,
  };

  // ── PNU · 지번 검색 ──
  const pnu = {
    _bjd: null, _cache: {},
    async bjd() { if (!this._bjd) this._bjd = await gz('data_v4/bjd_v4.json.gz'); return this._bjd; },
    async load(sgg) { if (!(sgg in this._cache)) this._cache[sgg] = await gz(`data_v4/pnu/${sgg}.json.gz`); return this._cache[sgg]; },
    /** 입력 해석: 19자리 PNU | "시군 읍면동 리 본번-부번" | "… 산 본번-부번". 반환 {kind:'pnu', pnu} | {kind:'jibun', cands:[{pnu,name}]} | {kind:'none'} */
    async parse(q) {
      q = (q || '').trim();
      const digits = q.replace(/[^\d]/g, '');
      if (/^\d{19}$/.test(q.replace(/\s|-/g, ''))) return {kind: 'pnu', pnu: q.replace(/\s|-/g, '')};
      const m = q.match(/^(.*?)(산\s*)?(\d{1,4})(?:\s*-\s*(\d{1,4}))?\s*$/);
      if (!m || !m[1].trim()) return {kind: 'none'};
      const names = m[1].trim().split(/\s+/).filter(Boolean), san = !!m[2], bon = m[3], bu = m[4] || '0';
      const B = await this.bjd(); if (!B) return {kind: 'none'};
      const norm = s => s.replace(/\s+/g, '');
      const hits = B.rows.filter(([code, name]) => { const nm = norm(name); return names.every(t => nm.includes(norm(t))); });
      // 리(leaf) 우선 — 마지막 토큰이 이름의 끝과 맞는 것
      const last = names[names.length - 1];
      const leaf = hits.filter(([, name]) => name.endsWith(last) || name.split(' ').pop().startsWith(last));
      const use = (leaf.length ? leaf : hits).slice(0, 8);
      return {kind: 'jibun', san, bon, bu, cands: use.map(([code, name]) => ({pnu: code + (san ? '2' : '1') + bon.padStart(4, '0') + bu.padStart(4, '0'), name, code10: code}))};
    },
    async nameOf(pnu) { const B = await this.bjd(); const r = B && B.rows.find(([c]) => c === pnu.slice(0, 10)); const san = pnu[10] === '2';
      const bon = String(+pnu.slice(11, 15)), bu = +pnu.slice(15, 19); return (r ? r[1] + ' ' : '') + (san ? '산 ' : '') + bon + (bu ? '-' + bu : ''); },
    /** 분류: 1 = 적격 + 규모 기준 이상 후보 공간 포함 · 2 = 적격이나 규모 기준 미달 · 3 = 분석 기준 적격 목록에 없음(부적격 단정 아님) */
    classify(data, pnuStr, run, minM2 = 66667) {
      const R = data && data.runs[run]; if (!R) return {cls: null};
      const lab = R.p[pnuStr]; if (lab == null) return {cls: 3};
      const [a, np] = R.u[lab] || [null, null];
      return {cls: a != null && a >= minM2 ? 1 : 2, lab, a, n: np};
    },
    CLS: {1: ['①', '적격 · 규모 기준 이상 후보 공간에 포함', '#3E7A2E'], 2: ['②', '적격이나 현재 규모 기준 미달', '#B8860B'], 3: ['③', '분석 기준 적격 목록에 없음 — 부적격 단정 아님(지목·소유·제외조건 미구분)', '#8A8F98']},
  };

  // ── 기존 태양광 시설(VALID 좌표만) ──
  const existing = {
    _d: null,
    async load() { if (!this._d) this._d = await gz('data_v4/existing_pv_v4.json.gz'); return this._d; },
    layer(d, {pane, sgg = null} = {}) { const g = L.layerGroup(); if (!d) return g;
      const pts = sgg ? d.pts.filter(p => p[6] === sgg) : d.pts;
      const canvas = L.canvas({pane, padding: .3});
      pts.forEach(([lon, lat, kw, t, st, src]) => L.circleMarker([lat, lon], {renderer: canvas, pane, radius: 3, weight: 1, color: '#fff', fillColor: t === 'y' ? '#2A9D8F' : '#6B7B8C', fillOpacity: .9})
        .bindTooltip(`기존 시설(위치 VALID) · ${d.meta.type_codes[t]}${kw ? ` · ${n(kw)} kW` : ' · 용량 원천 없음'} · ${d.meta.status_codes[st] || st} · ${src}`).addTo(g));
      return g; },
    summaryHTML(d, sgg) { if (!d) return ''; const s = d.by_sgg[sgg];
      if (!s) return `<div class="v55-hint">이 시군에는 확보한 기존 시설 기록이 없음(자료 부재이며 시설 부재 아님).</div>`;
      return `<div class="v55-qual"><b>기존 시설 기록 ${n(s.n)}건</b>(영농형 표기 ${n(s.yeongnong)}) · 위치 검증 등급 —
        <span class="q-valid">VALID ${n(s.valid)}</span> <span class="q-cond">CONDITIONAL ${n(s.cond)}</span> <span class="q-unv">UNVERIFIED ${n(s.unver)}</span> <span class="q-unk">UNKNOWN ${n(s.unk)}</span>
        ${s.nolocstatus ? `<span class="q-none">좌표 없음 ${n(s.nolocstatus)}</span>` : ''} · 지도에는 VALID만 표시(ADR-0053)</div>`; },
  };

  // ── TOP 10 표 · 마커 렌더(두 화면 공용) ──
  top10.table = function (el, sel, rows, {onPick, pickId = null, nameOf = c => c} = {}) {
    if (!el) return;
    const rk = this.ranks(rows || []);
    const isRank = sel.mode === 'rank', ax = sel.axis;
    const hdr = `<tr><th class="l">${isRank ? '순위' : '후보'}</th><th>면적</th><th>참고 MW</th><th>계통 여유<br><small>참고 · lo MW</small></th><th>산단 거리<br><small>km</small></th><th>간척 %</th><th>시군 전력판매량<br><small>대비 %(참고)</small></th><th>필지</th><th>걸침</th></tr>`;
    const cell = (k, v, cls = '') => `<td class="${cls}${isRank && ax === k ? ' hi' : ''}">${v}</td>`;
    const body = sel.list.map((r, i) => { const R = rk.get(r.lab) || {};
      const lead = isRank ? `<span class="rk">${r.rank}</span>` : `<span class="cmp">주요 비교 후보</span> <span style="color:var(--muted);font-size:11px">${i + 1}</span>`;
      return `<tr class="rowbtn ${r.lab === pickId ? 'pick' : ''}" data-lab="${r.lab}"><td class="l">${lead}<div style="font-size:11px;color:var(--muted)">#${r.lab} · 면적 ${R.ra ?? '—'}위 · 계통 ${R.rb ?? '—'}위 · 산단 ${R.rc ?? '—'}위</div></td>` +
        cell('a', `${km2(r.a, 2)} km²`) + `<td>${mw(r.a)}</td>` + cell('b', r.lo == null ? '<span class="unk">알 수 없음</span>' : n(r.lo)) + cell('c', r.d == null ? '<span class="unk">알 수 없음</span>' : r.d.toFixed(1)) +
        `<td>${r.recl == null ? '—' : n(r.recl)}</td><td>${r.dsh == null ? '—' : r.dsh}</td><td>${n(r.n)}</td><td>${r.ne > 1 ? `읍면동 ${r.ne}곳` : '—'}</td></tr>`; }).join('');
    el.innerHTML = hdr + (body || `<tr><td colspan="9" class="l" style="color:var(--muted)">이 조건에 해당하는 후보 공간이 없음</td></tr>`);
    el.querySelectorAll('tr.rowbtn').forEach(tr => tr.onclick = () => onPick && onPick(sel.list.find(r => r.lab === +tr.dataset.lab)));
  };
  top10.markers = function (group, sel, {onPick} = {}) {
    group.clearLayers(); const coords = [];
    sel.list.forEach((r, i) => { if (r.lat == null) return; coords.push([r.lat, r.lon]);
      const isRank = sel.mode === 'rank';
      L.marker([r.lat, r.lon], {icon: L.divIcon({className: 'v55-mk' + (isRank ? '' : ' cmp'), html: isRank ? `${r.rank}` : '◆', iconSize: [24, 24], iconAnchor: [12, 12]}), keyboard: false})
        .bindTooltip(`${isRank ? r.rank + '위' : '주요 비교 후보'} · #${r.lab} · ${km2(r.a, 2)} km² ≈ ${mw(r.a)} MW`).on('click', () => onPick && onPick(r)).addTo(group); });
    return coords;
  };
  // 축 다중 선택 컨트롤
  function axesControl(el, {value = new Set(), onChange} = {}) {
    const AXC = {a: '#0C356A', b: '#3E7A2E', c: '#2A9D8F'};
    const render = () => {
      const k = [...value].sort().join('');
      const mode = value.size === 0 ? '우선순위를 고르지 않으면 면적순으로 보입니다(순위 아님).' :
        value.size === 1 ? `<b>1개 기준</b> — 그 기준으로 정렬한 순위(TOP 10). 점수·가중치 없음.` :
        value.size === 2 ? `<b>2개 기준</b> — 두 기준 모두에서 다른 후보에 지지 않는 <b>주요 비교 후보</b>(비지배 집합). 순위를 억지로 매기지 않음.` :
        `<b>3개 기준 · 자동 비교</b> — 세 기준 모두에서 지지 않는 <b>주요 비교 후보</b>. 학술 용어로는 비지배 집합(근거와 방법 참조).`;
      el.innerHTML = `<div class="v55-axes"><span class="q">무엇을 우선해서 볼까요? — 여러 개 선택 가능</span>` +
        [['a', '발전 규모'], ['b', '계통 여유(참고)'], ['c', '산업단지 거리']].map(([kk, nm]) => `<label class="${value.has(kk) ? 'on' : ''}"><input type="checkbox" value="${kk}" ${value.has(kk) ? 'checked' : ''}><i style="background:${AXC[kk]}"></i>${nm}</label>`).join('') +
        `<span class="v55-mode">${mode}</span></div>`;
      el.querySelectorAll('input').forEach(cb => cb.onchange = () => { cb.checked ? value.add(cb.value) : value.delete(cb.value); render(); onChange && onChange(new Set(value)); });
    };
    render();
    return {get value() { return new Set(value); }, set(v) { value = new Set(v); render(); }};
  }
  // 세그먼트 컨트롤(제도·이격·최소 규모)
  function seg(el, opts, value, onChange) {
    const render = () => { el.innerHTML = `<div class="seg">` + opts.map(([v, t]) => `<button type="button" data-v="${v}" class="${String(v) === String(value) ? 'on' : ''}">${t}</button>`).join('') + `</div>`;
      el.querySelectorAll('button').forEach(b => b.onclick = () => { value = b.dataset.v; render(); onChange && onChange(value); }); };
    render(); return {get value() { return value; }, set(v) { value = v; render(); }};
  }
  // PNU 결과 카드 — 시행 전(R0) / 시행 후(R3) 분류 + 진흥구역 개방(R2) 지도 연결
  async function pnuCard(el, pnuStr, {minM2 = 66667, nameOf = c => c, onGo} = {}) {
    const sgg = pnuStr.slice(0, 5);
    const data = await pnu.load(sgg);
    const nm = await pnu.nameOf(pnuStr);
    if (!data) { el.innerHTML = `<div class="v55-pnu"><div class="h">PNU ${pnuStr}</div><div class="nm">${nm}</div><div class="v55-hint">이 시군의 필지 소속 자산이 없음(분석 모집단 밖 시군).</div></div>`; return; }
    const rowHTML = (label, run) => { const c = pnu.classify(data, pnuStr, run, minM2); const C = pnu.CLS[c.cls] || ['—', '자료 없음', '#999'];
      return `<div class="row"><div class="s">${label}</div><div><span class="v55-cls" style="background:${C[2]}">${C[0]}</span>${C[1]}${c.lab != null ? `<div class="v55-hint">후보 공간 #${c.lab} · ${km2(c.a, 2)} km² ≈ ${mw(c.a)} MW · 필지 ${n(c.n)} · 규모 기준 ${km2(minM2, 3)} km²(${mw(minM2)} MW 등가)</div>` : ''}</div></div>`; };
    const c2 = pnu.classify(data, pnuStr, 'R2_promo', minM2);
    el.innerHTML = `<div class="v55-pnu"><div class="h">PNU ${pnuStr} · 시군 ${nameOf(sgg)}</div><div class="nm">${nm}</div>
      ${rowHTML('특별법 시행 전', 'R0_current')}${rowHTML('특별법 시행 후<br><small>(농업진흥지역 개방 가정)</small>', 'R3_zone_all')}
      <div class="v55-hint" style="margin-top:8px">③은 부적격 판정이 아님 — 지목·소유(개인 소유 농지는 분석 기준 밖)·제외조건 중 어느 것인지 이 화면은 구분하지 않음. 필지 단위 클릭 대신 검색으로만 확인함.</div>
      <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap"><button type="button" class="btn btn-primary" id="pnuGo">이 필지의 시군(${nameOf(sgg)})으로 분석하기</button></div></div>`;
    el.querySelector('#pnuGo').onclick = () => onGo && onGo(sgg, c2.lab != null ? c2.lab : null);
  }
  async function pnuSearchBox(input, out, {nameOf, onGo, minM2} = {}) {
    const q = input.value.trim(); const P = await pnu.parse(q);
    if (P.kind === 'pnu') { await pnuCard(out, P.pnu, {nameOf, onGo, minM2}); return true; }
    if (P.kind === 'jibun') {
      if (!P.cands.length) { out.innerHTML = `<div class="v55-pnu"><div class="v55-hint">지번의 법정동을 찾지 못함 — "시군 읍면동 리 본번-부번" 순서로 적어 주세요.</div></div>`; return true; }
      if (P.cands.length === 1) { await pnuCard(out, P.cands[0].pnu, {nameOf, onGo, minM2}); return true; }
      out.innerHTML = `<div class="v55-pnu"><div class="nm">어느 법정동인가요?</div><div class="cands">${P.cands.map(c => `<button type="button" data-p="${c.pnu}">${c.name} ${P.san ? '산 ' : ''}${+P.bon}${+P.bu ? '-' + (+P.bu) : ''}</button>`).join('')}</div></div>`;
      out.querySelectorAll('button').forEach(b => b.onclick = () => pnuCard(out, b.dataset.p, {nameOf, onGo, minM2}));
      return true;
    }
    return false;
  }
  return {n, km2, mw, gz, SCN, scn, openModal, methodButton, METHOD, dataDates, EXISTING_NOTE, GRID_NOTE, MW_BANDS, BIG_BANDS, bandOf, legendHTML, GRID_BINS, GRID_SAT, GRID_UNK, gridLegendHTML, units, top10, pnu, existing, axesControl, seg, pnuCard, pnuSearchBox};
})();
