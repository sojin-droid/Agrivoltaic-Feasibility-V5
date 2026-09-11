/* V5.2 후보 클러스터 층(candidate cluster) — 두 화면(지역별 우선 후보·우리동네)이 **같은 파일·같은 함수**로 소비한다.
   화면은 계산하지 않는다: 전선은 data_v4/recommend_cc_v4.json.gz 에 칸(런)·시군·최소 표시 규모(필터)별로 사전 산출되어 있고,
   여기서는 상태값으로 행을 고르고 그리기만 한다. 최소 표시 규모는 생성 조건이 아니라 모집단 필터다(PR-0040 §6). */
window.Cand = (() => {
  const KAPPA = 0.045;                                   // 참고 환산 — 라벨 전용
  const FILTERS = [66667, 222222, 444444, 1111111];      // UI 선택지 3/10/20/50MW 등가(㎡). 0(전량)은 데이터에만 있음
  const MW_LBL = {66667: '3 MW', 222222: '10 MW', 444444: '20 MW', 1111111: '50 MW'};
  const DEFAULT_MIN = 66667, DEFAULT_CELL = 'R2_promo';
  const TOP = 3;
  const AXC = {ra: '#0C356A', ri: '#2A9D8F', rl: '#3E7A2E'};
  const AXN = {ra: '면적', ri: '산단 거리', rl: '계통 여유'};
  let _rec = null;

  async function rec() { if (!_rec) _rec = await Region.gz('data_v4/recommend_cc_v4.json.gz'); return _rec; }
  const cellOf = c => (_rec && _rec.cells && _rec.cells[c || DEFAULT_CELL]) || null;
  const has = (sgg, cell) => { const C = cellOf(cell); return !!(C && C.sgg[sgg]); };
  const info = (sgg, cell) => { const C = cellOf(cell); return C ? (C.sgg[sgg] || null) : null; };
  const frontier = (sgg, minM2, cell) => { const S = info(sgg, cell); return S ? (S.by_filter[String(minM2)] || {n_pop: 0, frontier: []}) : null; };
  const geo = (sgg, cell) => Region.gz(`data_v4/cand/${sgg}_${cell || DEFAULT_CELL}.json.gz`);   // 없으면 null
  const status = () => (_rec && _rec.status) || '';
  const cellsFor = sgg => _rec && _rec.cells ? Object.keys(_rec.cells).filter(c => _rec.cells[c].sgg[sgg]) : [];

  const fmtA = a => a >= 1e6 ? (a / 1e6).toFixed(3) + ' km²' : (a || 0).toLocaleString('ko-KR') + ' ㎡';
  const isTop = (f, ax) => ax && f[ax] != null && f[ax] <= TOP;
  const stars = f => ['ra', 'ri', 'rl'].map(ax => `<span class="${f[ax] != null && f[ax] <= TOP ? 'on' : 'off'}" title="${AXN[ax]} ${f[ax] ?? '—'}위">★</span>`).join('');
  const bandOf = am2 => am2 >= 1111111 ? 'ge50' : am2 >= 444444 ? 'b20' : am2 >= 222222 ? 'b10' : am2 >= 66667 ? 'b3' : 'lt3';
  const BAND_FILL = {lt3: '#E6E0CF', b3: '#FFD84D', b10: '#F2B233', b20: '#D98E1B', ge50: '#A8651A'};
  const BAND_LBL = {lt3: '<3MW', b3: '3–10MW', b10: '10–20MW', b20: '20–50MW', ge50: '≥50MW'};
  const legendHTML = () => Object.keys(BAND_FILL).map(k => `<span><i style="background:${BAND_FILL[k]}"></i>${BAND_LBL[k]}</span>`).join('') +
    '<span><i style="border:2px dashed #0C356A;background:#fff"></i>다구획 클러스터 외곽(볼록껍질)</span><span><i style="border:1px solid #9AA5B1;background:#fff"></i>최소 표시 규모 미만(윤곽만 — 숨기지 않음)</span>';

  // ── 컨트롤: 최소 규모 (생성 규칙 아님 — 비교 범위) ──
  function minSizeControl(el, {value = DEFAULT_MIN, onChange, label = '최소 규모', hint = '선택한 규모 이상의 후보 클러스터를 비교합니다. 클러스터 생성 자체에는 영향을 주지 않습니다.'} = {}) {
    let v = value;
    const render = () => {
      el.innerHTML = `<span class="q">${label}</span>` + FILTERS.map(m =>
        `<button type="button" data-v="${m}" class="${m === v ? 'on' : ''}">${MW_LBL[m]} 이상</button>`).join('') +
        (hint ? `<span class="cand-hint">${hint}</span>` : '');
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

  // ── 지도 레이어: cc 전량. 필터 미만은 윤곽만(숨기지 않음), 필터 이상은 band 채움 + 다구획 남색 외곽 ──
  function layer(gj, {minM2 = DEFAULT_MIN, pane, interactive = true, frontierIds = []} = {}) {
    const FR = new Set(frontierIds);
    return L.geoJSON(gj, {pane, interactive,
      style: f => { const p = f.properties, below = p.am2 < minM2, multi = p.nc > 1;
        return below ? {color: '#9AA5B1', weight: .5, opacity: .55, fillColor: '#9AA5B1', fillOpacity: .06}
                     : {color: multi ? '#0C356A' : '#8A7A55', weight: multi ? 1.6 : .6, fillColor: BAND_FILL[bandOf(p.am2)], fillOpacity: .82, opacity: 1}; },
      onEachFeature: (f, l) => { const p = f.properties;
        l.bindTooltip(`후보 클러스터 ${p.id} · 구획 ${p.nc} · 필지 ${p.n} · ${fmtA(p.am2)} · 참고 ${(p.am2 * KAPPA / 1000).toFixed(1)} MW` +
          (p.nc > 1 ? ` · 안정 ${p.td}–${p.tb} m` : ' · 고립(1구획)') + ` · 산단 ${p.d == null ? '—' : p.d.toFixed(1) + ' km'} · 계통 lo ${p.lo == null ? '—' : p.lo + ' MW'}` +
          (p.am2 < minM2 ? ' · 최소 표시 규모 미만(모집단 밖)' : FR.size ? (FR.has(p.id) ? ' · <b>공동 1등</b>' : ' · 모집단 안이지만 <b>지배됨</b>(면적·산단·계통 모두 같거나 나은 후보가 있음)') : '')); }});
  }
  // ── 다구획 cc 의 볼록껍질 외곽(필터 이상만) — "여기가 한 권역" 으로 읽히게 하는 표시. 기하 정점에서 클라이언트 계산(표시 전용, 값 아님) ──
  function hull(pts) {
    pts = pts.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    const cr = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
    const lo = [], up = [];
    for (const p of pts) { while (lo.length >= 2 && cr(lo[lo.length - 2], lo[lo.length - 1], p) <= 0) lo.pop(); lo.push(p); }
    for (const p of pts.reverse()) { while (up.length >= 2 && cr(up[up.length - 2], up[up.length - 1], p) <= 0) up.pop(); up.push(p); }
    up.pop(); lo.pop(); return lo.concat(up);
  }
  function hullLayer(gj, {minM2 = DEFAULT_MIN, pane} = {}) {
    const g = L.layerGroup();
    gj.features.forEach(f => { const p = f.properties; if (p.nc < 2 || p.am2 < minM2) return;
      const pts = []; JSON.stringify(f.geometry.coordinates, (k, v) => { if (Array.isArray(v) && typeof v[0] === 'number') pts.push(v); return v; });
      const h = hull(pts); if (h.length < 3) return;
      L.polygon(h.map(([x, y]) => [y, x]), {pane, color: '#0C356A', weight: 1.6, dashArray: '5 4', fill: true, fillColor: '#0C356A', fillOpacity: .06, interactive: false}).addTo(g); });
    return g;
  }
  // ── 후보 상세 카드 (§17) + 「구성 구획 보기」 — 연접 구획은 여기에서만 세부 단위로 노출 ──
  const _compCache = {};
  async function components(sgg, cell) {          // 구획 층 파일(V5.1 그대로): properties {id=lab, a(km² 2dp), n}
    const k = `${sgg}_${cell || DEFAULT_CELL}`;
    if (!(k in _compCache)) _compCache[k] = await Region.gz(`data_v4/clusters/${k}.json.gz`);
    return _compCache[k];
  }
  function detail(el, f, {sgg, cell, index, total, compFrontier = [], onMembers} = {}) {
    if (!f) { el.innerHTML = ''; return; }
    const big = f.nc >= 20;
    el.innerHTML = `<div class="cand-detail">
      <div class="cand-detail-h"><span class="cand-detail-id">CC-${f.id}</span>${index != null ? `<span class="cand-detail-no">후보 ${index}/${total}</span>` : ''}
        ${f.front ? '<span class="badge-front">★ 공동 1등</span>' : '<span class="badge-dom" title="면적·산단 거리·계통 여유 모두에서 같거나 나은 후보가 있음">지배됨</span>'}</div>
      <div class="cand-detail-kv"><div><b>${fmtA(f.a)}</b><small>면적</small></div><div><b>≈ ${f.mw} MW</b><small>참고 환산</small></div>
        <div><b>${f.d == null ? '알 수 없음' : f.d.toFixed(2) + ' km'}</b><small>산단 거리</small></div><div><b>${f.lo == null ? '알 수 없음' : f.lo + ' MW'}</b><small>계통 여유(하한)</small></div></div>
      <div class="cand-detail-sub">구성 연접 구획 ${f.nc}개 · 필지 ${f.n.toLocaleString('ko-KR')}${f.nc > 1 ? ` · 안정 구간 ${f.td}–${f.tb} m` : ' · 고립(구획 1개)'} · 면적 ${f.ra}위 · 산단 ${f.ri}위 · 계통 ${f.rl}위${f.recl != null ? ` · 간척 ${f.recl}%` : ''}</div>
      ${big ? `<div class="cand-detail-note">이 후보는 하나의 큰 공간권역으로 연결되어 있습니다. 내부의 세부 우선 후보는 구성 구획 기준으로 확인할 수 있습니다.</div>` : ''}
      <button type="button" class="cand-x" id="ccMembersBtn">구성 구획 보기</button> <span class="cand-detail-members" id="ccMembers"></span></div>`;
    const btn = el.querySelector('#ccMembersBtn'), box = el.querySelector('#ccMembers');
    btn.onclick = async () => {
      btn.disabled = true; box.textContent = '불러오는 중…';
      const gj = await components(sgg, cell);
      const feats = gj ? gj.features.filter(x => (f.labs || []).includes(x.properties.id)) : [];
      const fset = new Set(compFrontier.map(c => c.lab));
      feats.sort((a, b) => (b.properties.a || 0) - (a.properties.a || 0));
      box.innerHTML = feats.length ? `<div class="cand-members-list">` + feats.map(x => `<span class="cand-lab">구획 ${x.properties.id} · ${x.properties.a >= 0.01 ? x.properties.a.toFixed(2) + ' km²' : '<0.01 km²'} · 필지 ${x.properties.n}${fset.has(x.properties.id) ? ' · <b>구획 기준 공동 1등</b>' : ''}</span>`).join('') +
        `</div><span class="cand-hint">연접 구획 = 21m 이내로 이어진 땅 조각(내부 분석 단위). 구획 기준 공동 1등은 V5.1 recommend_v4 그대로.</span>` : '구획 파일 없음';
      onMembers && onMembers(feats, gj);
      btn.textContent = '구성 구획 표시 중'; };
  }
  function memberLayer(feats, {pane} = {}) {
    return L.geoJSON({type: 'FeatureCollection', features: feats}, {pane, interactive: true,
      style: {color: '#B3261E', weight: 1.6, dashArray: '3 3', fillColor: '#FFD84D', fillOpacity: .35},
      onEachFeature: (x, l) => l.bindTooltip(`구성 구획 ${x.properties.id} · ${(x.properties.a || 0).toFixed(2)} km² · 필지 ${x.properties.n}`)});
  }

  // ── 공동 1등 후보의 폴리곤 테두리(구획 파일·cc 파일 공용: properties.id ∈ ids) — 번호 원 밑의 실제 범위를 보인다 ──
  function outline(gj, ids, {pane, color = '#0C356A', weight = 2.6, fill = true} = {}) {
    const set = new Set(ids);
    return L.geoJSON({type: 'FeatureCollection', features: gj.features.filter(f => set.has(f.properties.id))},
      {pane, interactive: false, style: {color, weight, opacity: 1, fill, fillColor: '#FFD84D', fillOpacity: fill ? .55 : 0}});
  }
  // ── 모집단 행(표에 싣는 것): 필터별 사전 산출 pop(면적순·순위·비지배 배지). pop 이 없는 필터(전량 0)는 전선만 ──
  const rowsOf = F => (F && F.pop && F.pop.length) ? F.pop : (F ? F.frontier.map(f => ({...f, front: true})) : []);
  // ── 마커: 모집단 전량에 표 순번 배지. 공동 1등 = 남색 굵은 링, 나머지 = 회색 링. 우선 기준 선택 시 3위 이내만 진하게 ──
  function markers(group, rows, {axis = '', onPick} = {}) {
    group.clearLayers(); const refs = {}, coords = [];
    rows.forEach((f, i) => { if (f.lat == null) return; coords.push([f.lat, f.lon]);
      const hi = axis ? isTop(f, axis) : true, fr = !!f.front;
      refs[f.id] = L.circleMarker([f.lat, f.lon], {radius: Math.max(8, Math.sqrt(f.a) / 170) * (axis && hi ? 1.2 : 1),
        color: axis && hi ? AXC[axis] : (fr ? '#0C356A' : '#6B7B8C'), weight: axis && hi ? 3.5 : (fr ? 2.8 : 1.5),
        fillColor: '#FFD84D', fillOpacity: axis ? (hi ? .95 : .3) : (fr ? .9 : .6), opacity: axis && !hi ? .4 : 1})
        .bindTooltip(`${i + 1}/${rows.length} ${fr ? '· <b>공동 1등</b>' : ''} · ${fmtA(f.a)} · 구획 ${f.nc} · 면적 ${f.ra}위 · 산단 ${f.ri}위 · 계통 ${f.rl}위`)
        .on('click', () => onPick && onPick(f)).addTo(group);
      L.marker([f.lat, f.lon], {icon: L.divIcon({className: 'mk-num' + (fr ? '' : ' mk-dom'), html: `${i + 1}`, iconSize: [22, 22], iconAnchor: [11, 11]}), interactive: false, keyboard: false}).addTo(group); });
    return {refs, coords};
  }

  // ── 표: 최소 표시 규모 이상 후보 클러스터 **전량**(모집단) — 공동 1등은 배지, 정렬은 사용자 우선 기준(보기 조작, 방법론 아님 — ADR-0044) ──
  function table(el, sgg, minM2, {cell, axis = '', pickId = null, onPick, compFrontier = []} = {}) {
    const F = frontier(sgg, minM2, cell); if (!F) { el.innerHTML = ''; return null; }
    const rows = rowsOf(F), n = rows.length;
    const order = rows.map((f, i) => ({f, i}));                       // i = 면적순 표시 번호(지도 배지와 같음)
    if (axis) order.sort((x, y) => (x.f[axis] ?? 1e9) - (y.f[axis] ?? 1e9));
    const rk = (f, ax) => `<span class="chip-n ${isTop(f, ax) ? 'top' : ''}">${f[ax] ?? '—'}</span>`;
    let h = `<tr><th>후보</th><th>비지배</th><th>조건 충족<br><small>면적·거리·계통</small></th><th>면적</th><th>참고 MW</th><th>산단 거리 km</th><th>계통 여유 MW<br><small>(하한)</small></th>
      <th>면적 순위</th><th>산단 순위</th><th>계통 순위</th><th>구성</th><th>안정 구간<br><small>m</small></th><th>내부 공동 1등 구획</th></tr>`;
    for (const {f, i} of order) {
      const inner = f.front_labs || [];
      h += `<tr data-cc="${f.id}" class="${isTop(f, axis) ? 'hi-a' : ''} ${f.id === pickId ? 'pick' : ''} ${f.front ? 'front' : ''}" style="cursor:pointer">
        <td class="l"><b>${i + 1}</b><span style="color:var(--muted)">/${n}</span></td>
        <td>${f.front ? '<span class="badge-front">공동 1등</span>' : '<span class="badge-dom" title="면적·산단·계통 모두 같거나 나은 후보가 있음">—</span>'}</td>
        <td><span class="star">${stars(f)}</span></td>
        <td>${fmtA(f.a)}</td><td>${f.mw}</td><td>${f.d == null ? '알 수 없음' : f.d.toFixed(1)}</td><td>${f.lo == null ? '알 수 없음' : f.lo}</td>
        <td>${rk(f, 'ra')}</td><td>${rk(f, 'ri')}</td><td>${rk(f, 'rl')}</td>
        <td>구획 ${f.nc} · 필지 ${f.n.toLocaleString('ko-KR')}${f.iso ? ' <span class="cand-iso">고립</span>' : ''}</td>
        <td>${f.nc > 1 ? `${f.td}–${f.tb}` : '—'}</td>
        <td>${inner.length ? `<button type="button" class="cand-x" data-cc="${f.id}">${inner.length}곳 펼치기</button>` : (compFrontier.length ? '없음' : '—')}</td></tr>
        <tr class="cand-sub" data-sub="${f.id}" hidden><td colspan="13" class="l">이 후보 클러스터를 이루는 구획 ${f.nc}개 중 <b>구획 층 공동 1등</b>(recommend_v4) ${inner.length}곳:
          ${inner.map(l => { const c = compFrontier.find(x => x.lab === l); return c ? `<span class="cand-lab">구획 ${l} · ${fmtA(c.a)} · 면적 ${c.ra}위 · 산단 ${c.ri}위 · 계통 ${c.rl}위</span>` : `<span class="cand-lab">구획 ${l}</span>`; }).join(' ')}
          <span style="color:var(--muted)"> — 내부 비교는 구획 단위 표(구획 층 모집단 ≥11,111㎡)에서.</span></td></tr>`;
    }
    el.innerHTML = h;
    el.querySelectorAll('tr[data-cc]').forEach(tr => tr.onclick = e => { if (e.target.classList.contains('cand-x')) return; onPick && onPick(rows.find(f => f.id === +tr.dataset.cc)); });
    el.querySelectorAll('.cand-x').forEach(b => b.onclick = () => { const s = el.querySelector(`tr[data-sub="${b.dataset.cc}"]`); s.hidden = !s.hidden; b.textContent = b.textContent.replace(s.hidden ? '접기' : '펼치기', s.hidden ? '펼치기' : '접기'); });
    return F;
  }
  function note(sgg, minM2, axis, cell) {
    const S = info(sgg, cell), F = frontier(sgg, minM2, cell); if (!S || !F) return '';
    const one = F.frontier.length === 1;
    return `후보 클러스터 <b>${S.n_cc.toLocaleString('ko-KR')}</b>개(다구획 ${S.n_multi.toLocaleString('ko-KR')} · 고립 ${S.n_iso.toLocaleString('ko-KR')}) 중 최소 표시 규모 <b>${MW_LBL[minM2] || '전량'}</b> 이상 <b>${F.n_pop.toLocaleString('ko-KR')}</b>개를 표에 <b>전부</b> 싣고, 그중 세 축 어느 것에서도 다른 후보에 밀리지 않는 <b>공동 1등 ${F.frontier.length}곳</b>에 배지를 붙임(탈락 아님 — 나머지도 후보).
      ${one ? '<b>이 규모에서는 후보 클러스터 한 곳이 세 축 모두 우위 — 내부 비교는 구획 단위로.</b>' : ''}
      정렬: <b>${axis ? AXN[axis] + ' 순 · ' + TOP + '위 이내 강조' : '면적순'}</b> — 정렬은 보기 조작이며 새 점수·가중치가 아님. 필터는 생성이 아니라 모집단에만 작용 — 필터마다 배지가 달라질 수 있음(정상). 조건 ${cell || DEFAULT_CELL} · 규칙 ${_rec.rule} · ${status()}`;
  }
  return {rec, has, info, frontier, rowsOf, geo, status, cellsFor, FILTERS, MW_LBL, DEFAULT_MIN, DEFAULT_CELL, TOP, AXC, AXN, BAND_FILL, BAND_LBL, bandOf, fmtA, isTop, stars, legendHTML,
          minSizeControl, unitControl, layer, hullLayer, outline, markers, table, note, detail, components, memberLayer};
})();
