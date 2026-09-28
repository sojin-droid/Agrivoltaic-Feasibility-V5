// v4 데이터 렌더 도우미 — 수치는 전부 data_v4에서 (원칙 1). chrome(내비·푸터 골격)은 각 페이지 정적.
// 각주: 브리프 공통 번호 [1]–[16] + 사이트 확장 [17]–[21]. 본문 마커 <sup class="fnref">[n]</sup>.
// 통일 형식 — 발행처, 『자료명』, 판·취득 경로 (일자). 그리고 '용도' 설명 한 줄.
const FOOTNOTES = {
  1: '『연속지적도(LSMD_CONT_LDREG, 원본 zip 내부 파일명 기준 2026-07)』 및 『토지·임야 원장 속성 정리본(Land_Processed — 제공기관·판·기준 시점 기록 없음, 로컬 스냅숏 2026-05-28)』 — 252개 시군 전수 39,726,310필지 (지오메트리·지목·소유 유형·용도지역·장부면적).<span class="fn-note">용도: 분석의 뼈대 — 필지 식별(PNU)과 면적·지목·소유 구분·용도지역 판정의 원천. 이격거리 적용 시 주택 위치(대지 필지)도 이 원장 기준.</span>',
  2: '농림축산식품부, 『팜맵(농경지 전자지도)』, 2025년판 — 공공데이터포털 15104481–15104491, 항공·위성 판독(촬영 2019–2024 혼재).<span class="fn-note">용도: 지목 농지의 공간교차 검증(전답과 필지의 99.4% 실측 확인). 설치 가능 판정 조건에는 들어가지 않음.</span>',
  3: '한국농어촌공사, 『지구·공구 토지정보』, 2025년판 — 공공데이터포털 15116438, 지번 원장 45,193필지.<span class="fn-note">용도: "간척 농지" 식별의 유일한 근거. 민간 공유수면 매립지는 이 원장에 없어 분석 범위 밖.</span>',
  4: '농림축산식품부, 「국가관리 간척지 13지구 고시」, 2025년 6월.<span class="fn-note">용도: 국가관리 간척지 명단 — 간척 원장의 지구 구분 검증에 사용.</span>',
  5: '국토교통부 V-World, 『농업진흥지역도(LT_C_AGRIXUE101)』 — 2026-08-21 수집, 진흥구역 16,996·보호구역 43,442 폴리곤(속성 코드 UEA110/120 검증).<span class="fn-note">용도: 진흥구역·보호구역 구분 — 필지 대표점 교차로 농업보호구역·농업진흥구역 시나리오를 계산.</span>',
  6: '「농지법」 §2·§28②·§32 · 「국토의 계획 및 이용에 관한 법률 시행령」 별표15·18·22 · 「개발제한구역법 시행령」 §19 — 법제처 국가법령정보센터 원문 대조 (2026-08-21~24).<span class="fn-note">용도: 배제 3종(개발제한구역·보전관리지역·보전녹지지역)의 확정 근거 — 법문에 열거된 경우만 배제한다는 원문 재검증의 결과.</span>',
  7: '「농지법」 §36①4호의2 — 시행규칙 2025-10-31판 확인 (부령 미제정).<span class="fn-note">용도: 영농형 대상 농지의 부령 위임 조항 — 농업보호구역에 설치를 허용할 수 있는 법적 경로.</span>',
  8: '「농지법 시행령」 §30①3호 — 2025-06-02 개정 반영판.<span class="fn-note">용도: 농업보호구역 내 태양에너지 설비 1만㎡ 미만 허용 — 농업보호구역에 태양광 설비를 허용한 기존 선례 조항.</span>',
  9: '「농지법 시행령」 §28①3호다목.<span class="fn-note">용도: 저수지 상류 500m를 보호구역 변경 대상으로 명시 — 보호구역의 지정 성격(수자원 인접) 해석 근거.</span>',
  10: '「영농형 태양광 발전사업의 활성화 및 지원에 관한 법률」 — 법률 제21804호, 2026-06-16 공포, 2026-12-17 시행, §6①·§8·§10.<span class="fn-note">용도: 사업 규모를 부지면적부터 정의(면적을 1차 단위로 쓰는 근거)하고, 재생에너지지구 경로(§6①2호)를 규정.</span>',
  11: '「재생에너지 개발·이용·보급 촉진법」 §27조의3 및 시행령 개정안 — 기후에너지환경부 보도자료(2026-08-11 국무회의 의결), 원문 PDF 보존(sha256 관리), 법 시행 2026-09-18.<span class="fn-note">용도: 이격거리 상한제(주거 200m·도로 이격 금지) — 본 분석 "이격거리 적용" 값의 기준. 측정 방법 고시가 아직 없어 주거 200m를 전국에 똑같이 적용.</span>',
  12: '본 연구의 분석 데이터베이스 — 필지 원장·판정 결과·농업진흥지역과 간척지 표시·21m 연접·시나리오 결과를 담은 표 (2026-08-31 생성).<span class="fn-note">용도: 이 사이트 모든 수치의 출처.</span>',
  13: '환산 계수 0.045 kW/㎡ = 설치밀도(GCR) 0.225 × 모듈 효율 0.20 — 솔라시도 영농형 실계획과 ±0.6% 이내 대조 검증.<span class="fn-note">용도: 참고 MW 환산 — 면적이 1차 산출이고 MW는 이 가정이 얹힌 파생값이라 항상 "참고"로 병기.</span>',
  14: '특별법 시행 전 설치 가능 농지 — 법인·국공유 1,011,491필지 · 490.71 km² / 개인 소유 포함 5,719,511필지 · 5,582.55 km² (2026-08-29).<span class="fn-note">용도: 법인·국공유 농지가 전체의 몇 %인지 비교하기 위해 개인 소유를 포함한 값을 함께 표시함.</span>',
  15: '「농지법」 §37② — 국가법령정보센터 원문 대조.<span class="fn-note">용도: 우량농지 등에 대한 제한이 §36 타용도 일시사용 허가·협의에도 적용됨을 명시 — 시나리오의 법적 층위 해석.</span>',
  16: '「농촌공간 재구조화 및 재생지원에 관한 법률」 §12①5호·§13② — 원문 대조.<span class="fn-note">용도: 재생에너지지구의 지정 절차와 총량 상한 — 농업진흥구역에 설치를 허용하는 재생에너지지구의 지정 절차.</span>',
  17: '행정표준코드관리시스템(code.go.kr), 『법정동코드 전체자료』(2026-08-19 취득) 및 시군 경계 2023년판(신·구 행정코드 대조).<span class="fn-note">용도: 시군 이름·경계 표기 — 표기용 참조 자료로, 수치 산출에는 쓰지 않음.</span>',
  18: '「농지법 시행규칙」 §32 — 2025-10-31판.<span class="fn-note">용도: 타인 소유 농지의 타용도 일시사용 신청에 소유자 사용승낙서 경로를 규정 — 간척지 임차 논의의 절차적 근거.</span>',
  19: 'Esri World Imagery — © Esri, Maxar, Earthstar Geographics.<span class="fn-note">용도: 사이트 지도의 위성 배경 — 표시 전용이며 수치 산출에는 쓰지 않음.</span>',
  20: 'Leaflet 1.9.4 (오픈소스, BSD-2 라이선스) — 외부 CDN이 아니라 저장소에 내장.<span class="fn-note">용도: 사이트 지도의 대화형 렌더링 — 표시 전용.</span>',
  22: '한국전력공사, 『분산전원 연계정보』 온라인 조회 — 읍면동 단위 남은 연계 가능 용량(배전선로, 표준 연계한도 반영). 전국 5,066 읍면동, 2026-08-19 한 시점 수집, 원자료 26,801건 보존.<span class="fn-note">용도: 후보지 찾기 탭의 계통 여유 색과 우리 동네 TOP 10의 비교 기준 중 하나 — 설치 가능 면적 판정에는 쓰지 않음. 같은 선로의 값이 여럿이면 가장 작은 값을 쓰고, 응답이 없는 589곳은 "알 수 없음"으로 표시.</span>',
  23: '국토교통부 V-World 데이터 API — 산업단지 경계 LT_C_DAMDAN(산업입지정보시스템 등재 전국 1,363개: 일반 763·농공 483·국가 65·도시첨단 52, 2026-08-20 수집) · 읍면동 경계 LT_C_ADEMD_INFO(5,067개, 2026-08 수집).<span class="fn-note">용도: 후보지 찾기 탭의 경계 표시와, 후보 공간에서 가장 가까운 산업단지까지의 <b>거리 계산</b> — 우리 동네 TOP 10의 비교 기준 중 하나. 설치 가능 면적 판정에는 쓰지 않음.</span>',
  24: '한국산업단지공단, 『전국등록공장현황』 등록공장현황자료(2024-12-31 기준) — 공공데이터포털 15105482, 취득일 기록 없음, 217,048사(산단 입주 84,111사).<span class="fn-note">용도: 후보지 찾기 탭의 입주기업명 검색 — 기업명→소재 산업단지 이동의 표기 참고용이며 판정에는 쓰지 않음. 단지명 대조는 별칭·유형 힌트 기준, 경계 미등재 단지 소재 기업은 검색 제외.</span>',
  21: '경사 판정 자료 — 분석 데이터베이스의 경사 15 초과 표시. 원천 자료와 단위(도/퍼센트) 기록이 불완전해 확인 중이다(원고는 팜맵 경사 15°, 과거 사이트는 흙토람 토양 경사 15%로 적음).<span class="fn-note">용도: 경사 15 초과 필지 제외.</span>',
  25: '「영농형 태양광 발전사업의 활성화 및 지원에 관한 법률 시행령」 제정안 — 관계기관 의견조회판, 2026년 7월, 농림축산식품부 농촌에너지정책과.<span class="fn-note">용도: 시행령 제정안 탭의 조문 근거(§7 농업법인의 범위·§8 발전사업의 기간) — <b>입법예고 전 초안</b>이라 확정 조문이 아니며, 모든 인용에 "제정안(의견조회판)" 표기를 병기함.</span>',
  26: '「영농형 태양광 발전사업의 활성화 및 지원에 관한 법률 시행규칙」 제정안 — 관계기관 의견조회판, 2026년 7월, 농림축산식품부 농촌에너지정책과.<span class="fn-note">용도: 농업회사법인 허가신청 첨부서류(매립지등 임대통지서·시행자 확인서) 조항 근거 — 입법예고 전 초안.</span>',
  27: '「농어촌정비법」 제14조제1항 — 법제처 국가법령정보센터 원문.<span class="fn-note">용도: "매립지등"의 정의(매립지·간척지·개간지·취토장 등)와 처분 방법 4종(임대·매각·직접사용·일시사용) — 시행령 제정안 §7 6호가 인용하는 조문.</span>',
  28: '한전 빅데이터센터 개방 API "산업분류별 전력사용량"(powerUsage/industryType) — 2023.01~2025.12 36개월 합 ÷ 3 = 시군별 연평균 GWh.<span class="fn-note">용도: 지산지소 참고 표기(구획 참고 발전량 ÷ 시군 수요) — 발전량은 MW × 1,314h(이용률 15% 가정) 파생값이라 표기 전용, 판정·선별 불사용. 시 단위 자료만 있는 시군은 시 전체 값 배정(† 각주).</span>',
  29: '제1차 분산에너지 특화지역 7곳 — 경기 의왕·경북 포항·부산·제주·울산·전남 해남·충남 서산 (기후에너지환경부, 2025년 말 지정). 특화지역 안에서는 분산에너지사업자가 전력시장을 거치지 않고 전기사용자에게 직접 공급 가능(분산에너지 활성화 특별법 제43조).<span class="fn-note">용도: 지산지소 대조 절의 제도 경로 언급 — 지정 현황은 인용 시점(2025년 말 1차) 기준.</span>',
};
const FN_GROUPS = [
  ['데이터 원천', [1, 2, 3, 5, 17, 21, 22, 23, 24]],
  ['법령·행정자료', [4, 6, 7, 8, 9, 10, 11, 15, 16, 18, 25, 26, 27, 29]],
  ['본 연구 자료', [12, 14]],
  ['환산·배경지도·소프트웨어', [13, 19, 20, 28]],
];
const V4 = {
  cache: {},
  async data(name) {
    if (!this.cache[name]) {
      const r = await fetch('data_v4/' + name + '.json');
      this.cache[name] = await r.json();
    }
    return this.cache[name];
  },
  n(x) { return x.toLocaleString('ko-KR'); },
  km2(x, d = 1) { return x.toLocaleString('ko-KR', {minimumFractionDigits: d, maximumFractionDigits: d}); },
  mw(m2) { return Math.round(m2 * 0.045 / 1000).toLocaleString('ko-KR'); }, // 참고 환산: ㎡ 원값 기준
  // 카운트업 — 동적 삽입 수치용 (site.js .count는 정적 DOM 전용이라 별도 구현)
  countup(el, target, decimals = 0) {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
      el.textContent = this.km2(target, decimals); return;
    }
    const io = new IntersectionObserver(es => {
      es.forEach(e => {
        if (!e.isIntersecting) return;
        io.unobserve(el);
        const dur = 1400, t0 = performance.now(), self = this;
        (function tick(t) {
          const p = Math.min((t - t0) / dur, 1);
          el.textContent = self.km2(target * (1 - Math.pow(1 - p, 3)), decimals);
          if (p < 1) requestAnimationFrame(tick);
        })(t0);
      });
    }, {threshold: .5});
    io.observe(el);
  },
  // 각주 목록 — 모든 페이지 최하단(푸터 앞) 자동 삽입. 본문의 [n] 마커가 여기로 앵커된다.
  footnotes() {
    const ftr = document.querySelector('footer.v4');
    if (!ftr || document.getElementById('fnsec')) return;
    // 출처 목록은 「근거와 방법」(body[data-sources=full]) 한 곳에만 — 다른 화면의 각주 마커는 그곳으로 연결
    if (document.body.dataset.sources !== 'full') {
      document.querySelectorAll('sup.fnref').forEach(s => {
        const n = (s.textContent.match(/\d+/) || [])[0];
        if (n) s.innerHTML = `<a href="method.html#fn-${n}" title="출처 ${n} — 근거와 방법">[${n}]</a>`;
      });
      return;
    }
    const sec = document.createElement('section');
    sec.id = 'fnsec';
    sec.innerHTML = `<div class="wrap">
      <div class="sec-head" style="margin-bottom:18px"><div>
        <p class="eyebrow">Sources</p><h2>출처</h2></div></div>
      <div class="fn" id="read-note" style="margin-bottom:18px"><b>읽을 때 주의</b> — MW는 토지면적을
      기준으로 환산한 참고값(0.045 kW/㎡)이며 실제 발전량 예측값이 아님. 계통 여유·지역 전력수요
      대비·산업단지 거리는 후보 비교를 위한 참고 지표로, 실제 계통연계·지역 전력자립·직접 PPA
      가능성을 확정하지 않음. '대규모 후보 공간'은 약 50MW 이상(1.111 km² 이상) 규모의 후보 공간을 뜻하는 분석상 표현이며, 법적 특구나 최종 사업 단위가 아님. 설치 가능 농지는 이 분석의 판정 조건을 통과한 땅이며 인허가 가능
      여부와 다름. 연접 21m는 데이터에서 유도한 분석 기준이며 법정 기준이 아님.</div>` +
      FN_GROUPS.map(([g, nums]) =>
        `<div class="fn-group">${g}</div><ol class="fnlist">` +
        nums.map(n => `<li id="fn-${n}" value="${n}">${FOOTNOTES[n]}</li>`).join('') +
        `</ol>`).join('') +
      `<div class="fn">번호 [1]–[16]은 정책 브리프와 공통, [17]–[27]은 사이트 추가분.
      본문 위첨자 [n]을 누르면 해당 출처로 이동.</div>
    </div>`;
    ftr.parentNode.insertBefore(sec, ftr);
    // 본문 마커를 링크로 활성화
    document.querySelectorAll('sup.fnref').forEach(s => {
      const n = (s.textContent.match(/\d+/) || [])[0];
      if (n) s.innerHTML = `<a href="#fn-${n}">[${n}]</a>`;
    });
  },
  async footer() {
    this.footnotes();
    const m = await this.data('meta_v4');
    const el = document.querySelector('footer.v4 .wrap');
    const full = document.body.dataset.sources === 'full';
    if (el) el.innerHTML = full
      ? `<div>PLANiT Institute · 영농형 태양광 — 전국 영농형 태양광 모아보기</div>` +
        `<div>수치 생성일 ${String(m.generated).split(' ')[0]} · MW는 면적 환산 참고값(0.045 kW/㎡) · 소유 구분은 지적 원장의 소유 유형 구분(개인 식별 아님)</div>` +
        `<div style="margin-top:6px"><a href="local.html">우리 동네 분석하기 →</a> · <a href="#contact">문의</a></div>`
      : `<div>PLANiT Institute · 영농형 태양광 · 수치 생성일 ${String(m.generated).split(' ')[0]} · MW는 면적 환산 참고값 · 설치 가능 농지는 인허가 가능 여부와 다름 — ` +
        `<a href="method.html"><b>출처·방법론은 근거와 방법 →</b></a> · <a href="local.html">우리 동네 분석하기 →</a></div>`;
  },
};

// ── 접근성: 토글의 켜짐 상태를 색만이 아니라 aria-pressed로도 노출 (표시 전용, 로직 무관) ──
document.addEventListener('DOMContentLoaded', () => {
  const SEL = '.seg button, .axis-tgl button, .cmp-pills button, .rp-metro button, .rp-sgg button, .allbtn, .scn-btns button, .sb-toggle button, .opt';
  const mark = b => b.setAttribute('aria-pressed', b.classList.contains('on') ? 'true' : 'false');
  const sync = () => document.querySelectorAll(SEL).forEach(mark);
  sync();
  new MutationObserver(ms => {
    let full = false;
    for (const m of ms) {
      if (m.type === 'attributes' && m.target.matches && m.target.matches(SEL)) mark(m.target);
      else if (m.type === 'childList' && m.addedNodes.length) full = true;
    }
    if (full) sync();
  }).observe(document.body, {subtree: true, childList: true, attributes: true, attributeFilter: ['class']});
});
