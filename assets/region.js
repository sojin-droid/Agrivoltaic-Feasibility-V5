// 지역 계층 선택기 + 읍면동 색인 — 표시 전용 (sgg_matrix·grid_emd 재사용, 새 산정 없음)
window.Region = (() => {
  const METRO_ORDER = ['서울','부산','대구','인천','광주','대전','울산','세종',
                       '경기','강원','충북','충남','전북','전남','경북','경남','제주'];
  // 읍면동 경계(V-World)의 구 시도코드 → 현행 시군 코드 접두 (z81 emd_alias와 같은 지식)
  const ALT = {'12': '46', '24': '29', '45': '52', '42': '51', '49': '50'};
  let _codes = null, _groups = null, _emd = null;

  async function gz(path) {
    const r = await fetch(path);
    if (!r.ok) return null;
    const ds = r.body.pipeThrough(new DecompressionStream('gzip'));
    return JSON.parse(await new Response(ds).text());
  }
  async function load() {
    if (_codes) return {codes: _codes, groups: _groups};
    const sm = await V4.data('sgg_matrix');
    _codes = sm.codes; _groups = {};
    for (const [c, v] of Object.entries(_codes)) {
      const m = (v.name || '').split(' ')[0];
      (_groups[m] = _groups[m] || []).push(c);
    }
    for (const m in _groups)
      _groups[m].sort((a, b) => _codes[a].name.localeCompare(_codes[b].name, 'ko'));
    return {codes: _codes, groups: _groups};
  }
  const metros = () => METRO_ORDER.filter(m => _groups && _groups[m]);
  const metroOf = code => ((_codes && _codes[code] && _codes[code].name) || '').split(' ')[0];
  const nameOf = code => (_codes && _codes[code] && _codes[code].name) || code;
  const shortName = code => { const n = nameOf(code); const p = n.split(' '); return p.length > 1 ? p.slice(1).join(' ') : n; };

  // 2단계 선택기: 광역 버튼 → 시군 버튼. opts: {value, allowAll, onChange, restrict(Set|null)}
  function picker(el, opts = {}) {
    let metro = opts.value ? metroOf(opts.value) : null;
    let value = opts.value || (opts.allowAll ? 'ALL' : null);
    const restrict = opts.restrict || null;     // 표시할 시군 코드 집합(예: 비지배 데이터 보유 209곳)
    function render() {
      const ms = metros();
      el.innerHTML = `<div class="rp">
        <div class="rp-metro">${opts.allowAll ? `<button class="all ${value === 'ALL' ? 'on' : ''}" data-m="ALL">전국</button>` : ''}
          ${ms.map(m => `<button class="${m === metro ? 'on' : ''}" data-m="${m}">${m}</button>`).join('')}</div>
        <div class="rp-sgg">${metro ? _groups[metro].filter(c => !restrict || restrict.has(c))
          .map(c => `<button class="${c === value ? 'on' : ''}" data-c="${c}">${shortName(c)}</button>`).join('')
          : `<span class="empty">${opts.allowAll && value === 'ALL' ? '전국 전체를 보고 있음 — 광역지역을 고르면 시군 목록이 열림' : '광역지역을 먼저 고르세요'}</span>`}</div>
        <div class="rp-crumb">${value === 'ALL' ? '<b>전국</b>' : value ? `${metro} › <b>${shortName(value)}</b>` : '선택 없음'}</div>
      </div>`;
      el.querySelectorAll('.rp-metro button').forEach(b => b.onclick = () => {
        if (b.dataset.m === 'ALL') { metro = null; value = 'ALL'; render(); opts.onChange && opts.onChange('ALL'); return; }
        metro = b.dataset.m; render();
      });
      el.querySelectorAll('.rp-sgg button').forEach(b => b.onclick = () => {
        value = b.dataset.c; render(); opts.onChange && opts.onChange(value);
      });
    }
    render();
    return {get value() { return value; }, set(code) { value = code; metro = code && code !== 'ALL' ? metroOf(code) : null; render(); }};
  }

  // 읍면동 색인 — 이름 검색용. 시군 귀속은 코드 접두(구 시도코드는 ALT 변환)로 잡고, 안 되면 null
  async function emdIndex() {
    if (_emd) return _emd;
    const [fc] = await Promise.all([gz('data_v4/grid_emd.json.gz'), load()]);
    _emd = fc.features.map(f => {
      const c = f.properties.c; let s = c.slice(0, 5);
      if (!_codes[s]) { const a = ALT[s.slice(0, 2)]; s = (a && _codes[a + s.slice(2)]) ? a + s.slice(2) : null; }
      return {name: f.properties.n, sgg: s, code: c, feat: f};
    });
    return _emd;
  }
  // 검색: 시군명·읍면동명 부분 일치 (최대 12건)
  async function search(q) {
    q = (q || '').trim().replace(/\s+/g, ' ');
    if (q.length < 1) return [];
    await load(); const emd = await emdIndex();
    const out = [];
    for (const c of Object.keys(_codes)) {
      const n = _codes[c].name;
      if (n.includes(q) || n.replace(' ', '').includes(q.replace(' ', '')))
        out.push({type: 'sgg', sgg: c, label: n, sub: '시군'});
    }
    const toks = q.split(' ');
    const last = toks[toks.length - 1];
    // "시군 읍면동" 꼴이면 앞 토큰으로 시군을 잡아, 코드 매핑이 없는 읍면동에도 사용자가 적은 시군을 귀속시킨다
    const sggHit = toks.length > 1
      ? Object.keys(_codes).find(c => _codes[c].name.includes(toks[0]) || shortName(c).startsWith(toks[0])) : null;
    for (const e of emd) {
      if (!e.name.includes(last)) continue;
      let s = e.sgg;
      if (toks.length > 1) {
        if (s && !nameOf(s).includes(toks[0])) continue;      // 다른 시군의 동명 읍면동은 제외
        if (!s) { if (!sggHit) continue; s = sggHit; }        // 매핑 없음 → 사용자가 적은 시군으로 귀속
      }
      out.push({type: 'emd', sgg: s, emd: e, label: e.name, sub: s ? nameOf(s) + (e.sgg ? '' : ' (입력한 시군으로 귀속)') : '시군 미확정'});
      if (out.length > 60) break;
    }
    return out.slice(0, 12);
  }
  return {load, metros, metroOf, nameOf, shortName, picker, emdIndex, search, gz};
})();
