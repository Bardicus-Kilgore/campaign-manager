/* grimoire.js — Live search and entry rendering for pf2e-baudot */

/* ── Action cost symbols ────────────────────────────────────────────────────── */
function actionSymbol(cost) {
  const map = {
    '1': '◆', '2': '◆◆', '3': '◆◆◆',
    'reaction': '↺', 'free': '◇',
    '1 to 3': '◆–◆◆◆',
  };
  if (!cost) return '';
  return map[cost] || cost;
}

/* ── Trait pill ─────────────────────────────────────────────────────────────── */
function traitPill(t) {
  const upper = t.toUpperCase();
  let cls = 'trait';
  if (upper === 'UNCOMMON') cls += ' trait-uncommon';
  else if (upper === 'RARE') cls += ' trait-rare';
  else if (upper === 'UNIQUE') cls += ' trait-unique';
  return `<span class="${cls}">${t}</span>`;
}

function traitPills(traitsStr) {
  if (!traitsStr) return '';
  return traitsStr.split(',').map(t => traitPill(t.trim())).join('');
}

/* ── Toggle open/close ──────────────────────────────────────────────────────── */
function toggleEntry(el) {
  el.closest('.entry').classList.toggle('open');
}

/* ── Description with optional FR overlay ──────────────────────────────────── */
function descBlock(en, fr) {
  if (fr) {
    return `<div class="description has-fr">${en || ''}<span class="fr-badge">FR</span><div class="fr-overlay">${fr}</div></div>`;
  }
  return `<div class="description">${en || ''}</div>`;
}

/* ── Renderers ──────────────────────────────────────────────────────────────── */
function renderSpell(s) {
  const statRows = [];
  if (s.traditions) statRows.push(`<span><b>Traditions:</b> ${s.traditions}</span>`);
  if (s.range)      statRows.push(`<span><b>Range:</b> ${s.range}</span>`);
  if (s.area)       statRows.push(`<span><b>Area:</b> ${s.area}</span>`);
  if (s.targets)    statRows.push(`<span><b>Targets:</b> ${s.targets}</span>`);
  if (s.duration)   statRows.push(`<span><b>Duration:</b> ${s.duration}</span>`);
  if (s.defense)    statRows.push(`<span><b>Defense:</b> ${s.defense}</span>`);
  if (s.trigger)    statRows.push(`<span><b>Trigger:</b> ${s.trigger}</span>`);

  const typeLabel = s.type === 'focus' ? ' · Focus' : '';
  return `
<div class="entry">
  <div class="entry-header" onclick="toggleEntry(this)">
    <span class="entry-name">${s.name}</span>
    <span class="entry-level">Lvl ${s.level}${typeLabel}</span>
    <span class="entry-action">${actionSymbol(s.action_cost)}</span>
  </div>
  ${s.traits ? `<div class="traits">${traitPills(s.traits)}</div>` : ''}
  <div class="entry-body">
    ${statRows.length ? `<div class="stat-row">${statRows.join('')}</div>` : ''}
    ${descBlock(s.description, s.desc_fr)}
    <div class="source-tag">${s.source}</div>
  </div>
</div>`;
}

function renderCreature(c) {
  return `
<div class="entry">
  <div class="entry-header" onclick="toggleEntry(this)">
    <span class="entry-name">${c.name}</span>
    <span class="entry-level">${c.type || ''} · Lvl ${c.level}</span>
    <span class="entry-action">${c.size || ''}</span>
  </div>
  ${c.traits ? `<div class="traits">${traitPills(c.traits)}</div>` : ''}
  <div class="entry-body">
    <div class="creature-stats">
      <div class="creature-stat">
        <div class="creature-stat-label">AC</div>
        <div class="creature-stat-value">${c.ac || '—'}</div>
      </div>
      <div class="creature-stat">
        <div class="creature-stat-label">HP</div>
        <div class="creature-stat-value">${c.hp || '—'}</div>
      </div>
      <div class="creature-stat">
        <div class="creature-stat-label">Perception</div>
        <div class="creature-stat-value">${c.perception ? c.perception.split(';')[0] : '—'}</div>
      </div>
      <div class="creature-stat">
        <div class="creature-stat-label">Speed</div>
        <div class="creature-stat-value" style="font-size:0.8rem">${c.speed || '—'}</div>
      </div>
    </div>
    ${c.saves ? `<div class="stat-row"><span>${c.saves}</span></div>` : ''}
    ${c.ability_scores ? `<div class="stat-row"><span>${c.ability_scores}</span></div>` : ''}
    ${c.attacks ? `<div class="attacks-block">${c.attacks}</div>` : ''}
    ${c.abilities ? `<div class="description">${c.abilities}</div>` : ''}
    <div class="source-tag">${c.source}</div>
  </div>
</div>`;
}

function renderFeat(f) {
  return `
<div class="entry">
  <div class="entry-header" onclick="toggleEntry(this)">
    <span class="entry-name">${f.name}</span>
    <span class="entry-level">${f.class || ''} · Lvl ${f.level}</span>
    <span class="entry-action">${actionSymbol(f.action_cost)}</span>
  </div>
  ${f.traits ? `<div class="traits">${traitPills(f.traits)}</div>` : ''}
  <div class="entry-body">
    ${f.prerequisites ? `<div class="stat-row"><span><b>Prerequisites:</b> ${f.prerequisites}</span></div>` : ''}
    ${f.trigger ? `<div class="stat-row"><span><b>Trigger:</b> ${f.trigger}</span></div>` : ''}
    ${descBlock(f.description, f.desc_fr)}
    <div class="source-tag">${f.source}</div>
  </div>
</div>`;
}

function renderItem(i) {
  const statRows = [];
  if (i.price) statRows.push(`<span><b>Price:</b> ${i.price}</span>`);
  if (i.usage) statRows.push(`<span><b>Usage:</b> ${i.usage}</span>`);
  if (i.bulk)  statRows.push(`<span><b>Bulk:</b> ${i.bulk}</span>`);

  const lvlLabel = i.level_variable ? `${i.level}+` : `${i.level}`;
  return `
<div class="entry">
  <div class="entry-header" onclick="toggleEntry(this)">
    <span class="entry-name">${i.name}</span>
    <span class="entry-level">Lvl ${lvlLabel}</span>
    <span class="entry-action">${i.price || ''}</span>
  </div>
  ${i.traits ? `<div class="traits">${traitPills(i.traits)}</div>` : ''}
  <div class="entry-body">
    ${statRows.length ? `<div class="stat-row">${statRows.join('')}</div>` : ''}
    ${descBlock(i.description, i.desc_fr)}
    <div class="source-tag">${i.source}</div>
  </div>
</div>`;
}

/* ── Live search engine ─────────────────────────────────────────────────────── */
function initSearch(endpoint, filterIds, filterParams, renderFn) {
  const searchEl  = document.getElementById('search');
  const resultsEl = document.getElementById('results');
  let debounce;

  function fetch_results() {
    const q      = searchEl ? searchEl.value.trim() : '';
    const params = new URLSearchParams();
    if (q) params.set('q', q);

    filterIds.forEach((id, idx) => {
      const el = document.getElementById(id);
      if (el && el.value) params.set(filterParams[idx], el.value);
    });

    fetch(`/api/${endpoint}?${params}`)
      .then(r => r.json())
      .then(data => {
        if (!data.length) {
          resultsEl.innerHTML = `
            <div class="empty-state">
              <strong>Aucun résultat</strong>
              <p>Essayez d'autres mots-clés ou filtres.</p>
            </div>`;
          return;
        }
        resultsEl.innerHTML = data.map(renderFn).join('');
      })
      .catch(() => {
        resultsEl.innerHTML = `<div class="empty-state"><strong>Erreur de chargement.</strong></div>`;
      });
  }

  function trigger() {
    clearTimeout(debounce);
    debounce = setTimeout(fetch_results, 250);
  }

  if (searchEl) searchEl.addEventListener('input', trigger);

  filterIds.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', fetch_results);
  });

  // Initial load with no filters
  fetch_results();
}
