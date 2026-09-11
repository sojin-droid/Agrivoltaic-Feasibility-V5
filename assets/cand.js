/* V5.2 후보 클러스터 층(candidate cluster) — 두 화면(지역별 우선 후보·우리동네)이 **같은 파일·같은 함수**로 소비한다.
   화면은 계산하지 않는다: 전선은 data_v4/recommend_cc_v4.json.gz 에 최소 표시 규모(필터)별로 사전 산출되어 있고,
   여기서는 필터 상태값으로 행을 고르고 그리기만 한다. 최소 표시 규모는 생성 조건이 아니라 모집단 필터다(PR-0040 §6). */
window.Cand = (() => {
  const KAPPA = 0.045;                                   // 참고 환산 — 라벨 전용
  const FILTERS = [66667, 222222, 444444, 1111111];      // UI 선택지 3/10/20/50MW 등가(㎡). 0(전량)은 데이터에만 있음
  const MW_LBL = {66667: '3 MW', 222222: '10 MW', 444444: '20 MW', 1111111: '50 MW'};
  const DEFAULT_MIN = 66667;
  const TOP = 3;
  const AXC = {ra: '#0C356A', ri: '#2A9D8F', rl: '#3E7A2E'};
  const AXN = {ra: '면적', ri: '산단 거리', rl: '계통 여유'};
  let _rec = null;

  async function rec() { if (!_rec) _rec = await Region.gz('data_v4/recommend_cc_v4.json.gz'); return _rec; }
  const has = sgg => !!(_rec && _rec.sgg && _rec.sgg[sgg]);
  const info = sgg => (_rec && _rec.sgg[sgg]) || null;
  const frontier = (sgg, minM2) => { const S = info(sgg); return S ? (S.by_filter[String(minM2)] || {n_pop: 0, frontier: []}) : null; };
  const geo = sgg => Region.gz(`data_v4/cand/${sgg}_R2_promo.json.gz`);   // 없으면 null
  const status = () => (_rec && _rec.status) || '';

  const fmtA = a => a >= 1e6 ? (a / 1e6).toFixed(3) + ' km²' : (a || 0).toLocaleString('ko-KR') + ' ㎡';
  const isTop = (f, ax) => ax && f[ax] != null && f[ax] <= TOP;
  const stars = f => ['ra', 'ri', 'rl'].map(ax => `<span class="${f[ax] != null && f[ax] <= TOP ? 'on' : 'off'}" title="${AXN[ax]} ${f[ax] ?? '—'}위">★</span>`).join('');
  const bandOf = am2 => am2 >= 1111111 ? 'ge50' : am2 >= 444444 ? 'b20' : am2 >= 222222 ? 'b10' : am2 >= 66667 ? 'b3' : 'lt3';
  const BAND_FILL = {lt3: '#E6E0CF', b3: '#FFD84D', b10: '#F2B233', b20: '#D98E1B', ge50: '#A8651A'};
  const BAND_LBL = {lt3: '<3MW', b3: '3–10MW', b10: '10–20MW', b20: '20–50MW', ge50: '≥50MW'};

  // ── 컨트롤: 최소 표시 규모 ──
  function minSizeControl(el, {value = DEFAULT_MIN, onChange} = {}) {
    let v = value;
    const render = () => {
      el.innerHTML = `<span class="q">최소 표시 규모</span>` + FILTERS.map(m =>
        `<button type="button" data-v="${m}" class="${m === v ? 'on' : ''}">${MW_LBL[m]}</button>`).join('') +
        `<span class="cand-hint">생성 조건이 아님 — 지도·표·공동 1등 판정의 <b>모집단</b>을 이 규모 이상으로 한정(0.045 kW/㎡ 참고 환산)</span>`;
      el.querySelectorAll('button').forEach(b => b.onclick = () => { v = +b.dataset.v; render(); onChange && onChange(v); });
    };
    render();
    return {get value() { return v; }, set(x) { v = x; render(); }};
  }
  // ── 컨트롤: 단위 ──
  function unitControl(el, {value = 'cc', onChange, ccAvailable = true} = {}) {
    let v = ccAvailable ? value : 'comp';
    const render = () => {
      if (!ccAvailable && v === 'cc') v = 'comp';
      el.innerHTML = `<span class="q">후보 단위</span>
        <button type="button" data-v="cc" class="${v === 'cc' ? 'on' : ''}" ${ccAvailable ? '' : 'disabled title="후보 클러스터 층 미등재 시군(프로토타입 3시군만)"'}>후보 클러스터</button>
        <button type="button" data-v="comp" class="${v === 'comp' ? 'on' : ''}">구획(연접 21m)</button>
        <span class="cand-hint">${ccAvailable ? '후보 클러스터 = 서로 가까운 연접 구획의 묶음(거리 임계 고정 없음 · 묶음별 안정 구간 표기) · 두 단위 모두 3축 비지배, 새 점수 없음' : '이 시군은 후보 클러스터 층이 아직 등재되지 않음(프로토타입: 당진·해남·고흥)'}</span>`;
      el.querySelectorAll('button:not([disabled])').forEach(b => b.onclick = () => { v = b.dataset.v; render(); onChange && onChange(v); });
    };
    render();
    return {get value() { return v; }, set(x) { v = x; render(); }, setAvail(a, x) { ccAvailable = a; if (x) v = x; render(); }};
  }

  // ── 지도 레이어: cc 전량(필터 미만은 옅게 — 숨기지 않음) ──
  function layer(gj, {minM2 = DEFAULT_MIN, pane, interactive = true} = {}) {
    return L.geoJSON(gj, {pane, interactive,
      style: f => { const p = f.properties, below = p.am2 < minM2, multi = p.nc > 1;
        return {color: multi ? '#0C356A' : '#8A7A55', weight: multi ? (below ? .8 : 1.8) : .5,
                fillColor: BAND_FILL[bandOf(p.am2)], fillOpacity: below ? .25 : .8, opacity: below ? .35 : 1}; },
      onEachFeature: (f, l) => { const p = f.properties;
        l.bindTooltip(`후보 클러스터 ${p.id} · 구획 ${p.nc} · 필지 ${p.n} · ${fmtA(p.am2)} · 참고 ${(p.am2 * KAPPA / 1000).toFixed(1)} MW` +
          (p.nc > 1 ? ` · 안정 ${p.td}–${p.tb} m` : ' · 고립(1구획)') + ` · 산단 ${p.d == null ? '—' : p.d.toFixed(1) + ' km'} · 계통 lo ${p.lo == null ? '—' : p.lo + ' MW'}` +
          (p.am2 < minM2 ? ' · 최소 표시 규모 미만(모집단 밖)' : '')); }});
  }
  // ── 공동 1등 cc 마커 ──
  function markers(group, fr, {axis = '', onPick} = {}) {
    group.clearLayers(); const refs = {}, coords = [];
    fr.forEach((f, i) => { if (f.lat == null) return; coords.push([f.lat, f.lon]);
      const hi = axis ? isTop(f, axis) : true;
      refs[f.id] = L.circleMarker([f.lat, f.lon], {radius: Math.max(8, Math.sqrt(f.a) / 170) * (axis && hi ? 1.25 : 1),
        color: axis && hi ? AXC[axis] : '#0C356A', weight: axis && hi ? 3.5 : 2.5, fillColor: '#FFD84D', fillOpacity: axis ? (hi ? .95 : .35) : .9, opacity: axis && !hi ? .45 : 1})
        .bindTooltip(`공동 1등 후보 클러스터 ${i + 1}/${fr.length} · ${fmtA(f.a)} · 구획 ${f.nc} · 면적 ${f.ra}위 · 산단 ${f.ri}위 · 계통 ${f.rl}위`)
        .on('click', () => onPick && onPick(f)).addTo(group); });
    return {refs, coords};
  }

  // ── 표: 공동 1등 후보 클러스터(필터별 사전 산출 전선) ──
  function table(el, sgg, minM2, {axis = '', pickId = null, onPick, compFrontier = []} = {}) {
    const F = frontier(sgg, minM2); if (!F) { el.innerHTML = ''; return null; }
    const fr = F.frontier, n = fr.length, compSet = new Set(compFrontier.map(f => f.lab));
    const order = fr.map((f, i) => ({f, i}));
    if (axis) order.sort((x, y) => (x.f[axis] ?? 1e9) - (y.f[axis] ?? 1e9));
    const rk = (f, ax) => `<span class="chip-n ${isTop(f, ax) ? 'top' : ''}">${f[ax] ?? '—'}</span>`;
    let h = `<tr><th>후보</th><th>조건 충족<br><small>면적·거리·계통</small></th><th>면적</th><th>참고 MW</th><th>산단 거리 km</th><th>계통 여유 MW<br><small>(하한)</small></th>
      <th>면적 순위</th><th>산단 순위</th><th>계통 순위</th><th>구성</th><th>안정 구간<br><small>m</small></th><th>내부 공동 1등 구획</th></tr>`;
    for (const {f, i} of order) {
      const inner = f.front_labs || [];
      h += `<tr data-cc="${f.id}" class="${isTop(f, axis) ? 'hi-a' : ''} ${f.id === pickId ? 'pick' : ''}" style="cursor:pointer">
        <td class="l"><b>${i + 1}</b><span style="color:var(--muted)">/${n}</span></td><td><span class="star">${stars(f)}</span></td>
        <td>${fmtA(f.a)}</td><td>${f.mw}</td><td>${f.d == null ? '알 수 없음' : f.d.toFixed(1)}</td><td>${f.lo == null ? '알 수 없음' : f.lo}</td>
        <td>${rk(f, 'ra')}</td><td>${rk(f, 'ri')}</td><td>${rk(f, 'rl')}</td>
        <td>구획 ${f.nc} · 필지 ${f.n.toLocaleString('ko-KR')}${f.iso ? ' <span class="cand-iso">고립</span>' : ''}</td>
        <td>${f.nc > 1 ? `${f.td}–${f.tb}` : '—'}</td>
        <td>${inner.length ? `<button type="button" class="cand-x" data-cc="${f.id}">${inner.length}곳 펼치기</button>` : '없음'}</td></tr>
        <tr class="cand-sub" data-sub="${f.id}" hidden><td colspan="12" class="l">이 후보 클러스터를 이루는 구획 ${f.nc}개 중 <b>구획 층 공동 1등</b>(recommend_v4) ${inner.length}곳:
          ${inner.map(l => { const c = compFrontier.find(x => x.lab === l); return c ? `<span class="cand-lab">구획 ${l} · ${fmtA(c.a)} · 면적 ${c.ra}위 · 산단 ${c.ri}위 · 계통 ${c.rl}위</span>` : `<span class="cand-lab">구획 ${l}</span>`; }).join(' ')}
          <span style="color:var(--muted)"> — 내부 비교는 구획 단위 표(구획 층 모집단 ≥11,111㎡)에서.</span></td></tr>`;
    }
    el.innerHTML = h;
    el.querySelectorAll('tr[data-cc]').forEach(tr => tr.onclick = e => { if (e.target.classList.contains('cand-x')) return; onPick && onPick(fr.find(f => f.id === +tr.dataset.cc)); });
    el.querySelectorAll('.cand-x').forEach(b => b.onclick = () => { const s = el.querySelector(`tr[data-sub="${b.dataset.cc}"]`); s.hidden = !s.hidden; b.textContent = s.hidden ? `${b.textContent.replace(' 접기', '').replace('펼치기', '펼치기')}` : b.textContent.replace('펼치기', '접기'); });
    return F;
  }
  function note(sgg, minM2, axis) {
    const S = info(sgg), F = frontier(sgg, minM2); if (!S || !F) return '';
    const one = F.frontier.length === 1;
    return `후보 클러스터 <b>${S.n_cc.toLocaleString('ko-KR')}</b>개(다구획 ${S.n_multi.toLocaleString('ko-KR')} · 고립 ${S.n_iso.toLocaleString('ko-KR')}) 중 최소 표시 규모 <b>${MW_LBL[minM2] || '전량'}</b> 이상 <b>${F.n_pop.toLocaleString('ko-KR')}</b>개가 모집단 · 그중 공동 1등 <b>${F.frontier.length}</b>곳.
      ${one ? '<b>이 규모에서는 후보 클러스터 한 곳이 세 축 모두 우위 — 내부 비교는 구획 단위로.</b>' : ''}
      ${axis ? `<b>${AXN[axis]}</b> 기준 ${TOP}위 이내 강조.` : ''} 필터는 생성이 아니라 모집단에만 작용 — 필터마다 전선이 달라질 수 있음(정상). 규칙 ${S && _rec.rule} · ${status()}`;
  }
  return {rec, has, info, frontier, geo, status, FILTERS, MW_LBL, DEFAULT_MIN, TOP, AXC, AXN, BAND_FILL, BAND_LBL, bandOf, fmtA, isTop, stars,
          minSizeControl, unitControl, layer, markers, table, note};
})();
