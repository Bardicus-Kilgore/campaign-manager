/* encounter.js — Encounter Builder + Loot Generator
   Calls our own FastAPI backend (/api/encounter/*, /api/loot/*, /api/creatures)
*/

'use strict';

// ── State ──────────────────────────────────────────────────────────────────────
let currentDifficulty   = 'moderate';
let currentEncounter    = null;   // last generated encounter from API
let selectedMonsters    = [];     // [{name, level, type, quantity, xp_each}]
let selectedLootTypes   = [];     // creature types for loot
let terrainOptions      = {};     // loaded from /api/encounter/options
let adventureList       = [];     // for browser dropdown
let sessionList         = [];     // campaign sessions
let activeSessionId     = null;   // currently selected session
let lockedSlots         = {};     // { who: "a lich", modifier: "ancient", ... } — null/absent = unlocked

// ── Tabs ───────────────────────────────────────────────────────────────────────
document.querySelectorAll('.enc-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.enc-tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.enc-tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  });
});

// ── Difficulty buttons ─────────────────────────────────────────────────────────
document.querySelectorAll('.diff-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.diff-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentDifficulty = btn.dataset.value;
  });
});

// ── Load options on boot ───────────────────────────────────────────────────────
async function loadOptions() {
  const res  = await fetch('/api/encounter/options');
  const data = await res.json();
  terrainOptions = data.terrains || {};

  // Populate terrain select (filtered by environment later)
  populateTerrainSelect(document.getElementById('encEnv').value);

  // Populate encounter type descriptions as tooltips
  const typeSelect = document.getElementById('encType');
  if (data.encounter_types) {
    Array.from(typeSelect.options).forEach(opt => {
      const desc = data.encounter_types[opt.value];
      if (desc) opt.title = desc;
    });
  }
}

function populateTerrainSelect(env) {
  const sel = document.getElementById('encTerrain');
  const current = sel.value;
  sel.innerHTML = '<option value="">— aucun —</option>';
  Object.entries(terrainOptions).forEach(([key, t]) => {
    if (!env || t.environments.includes(env)) {
      const opt = document.createElement('option');
      opt.value = key;
      opt.textContent = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      opt.title = t.tactics;
      sel.appendChild(opt);
    }
  });
  // Restore selection if still valid
  if (current && sel.querySelector(`option[value="${current}"]`)) sel.value = current;
}

document.getElementById('encEnv').addEventListener('change', e => {
  populateTerrainSelect(e.target.value);
});

// ── Level shortcuts for monster search ────────────────────────────────────────
function buildLevelShortcuts() {
  const pl       = parseInt(document.getElementById('partyLevel').value) || 1;
  const container = document.getElementById('levelShortcuts');
  container.innerHTML = '';
  [-3, -2, -1, 0, 1, 2, 3].forEach(offset => {
    const lvl = pl + offset;
    if (lvl < -1 || lvl > 25) return;
    const btn = document.createElement('button');
    btn.className = 'level-shortcut';
    btn.textContent = (offset >= 0 ? '+' : '') + offset + ' (' + lvl + ')';
    btn.addEventListener('click', () => {
      document.getElementById('monsterSearch').value = '';
      searchMonsters('', lvl);
    });
    container.appendChild(btn);
  });
}

document.getElementById('partyLevel').addEventListener('input', buildLevelShortcuts);

// ── Monster search ─────────────────────────────────────────────────────────────
let monsterSearchTimer = null;

document.getElementById('monsterSearch').addEventListener('input', e => {
  clearTimeout(monsterSearchTimer);
  monsterSearchTimer = setTimeout(() => searchMonsters(e.target.value, null), 300);
});

async function searchMonsters(q, level) {
  const params = new URLSearchParams();
  if (q)     params.set('q', q);
  if (level !== null && level !== undefined) params.set('level', level);
  params.set('limit', 30);

  const res  = await fetch('/api/creatures?' + params);
  const data = await res.json();
  renderMonsterResults(data);
}

function renderMonsterResults(monsters) {
  const container = document.getElementById('monsterResults');
  container.innerHTML = '';
  if (!monsters.length) {
    container.innerHTML = '<p class="empty-state">Aucun résultat.</p>';
    return;
  }
  monsters.forEach(m => {
    const row = document.createElement('div');
    row.className = 'monster-row';
    row.innerHTML = `
      <div class="monster-info">
        <span class="monster-name">${m.name}</span>
        <span class="monster-meta">${m.type || '—'} · Niv. ${m.level ?? '?'}</span>
      </div>
      <button class="btn-ghost btn-sm" title="Ajouter">+</button>
    `;
    row.querySelector('button').addEventListener('click', () => addMonster(m));
    container.appendChild(row);
  });
}

// ── Selected monsters list ─────────────────────────────────────────────────────
const XP_BY_DIFF = {'-4':10,'-3':15,'-2':20,'-1':30,'0':40,'1':60,'2':80,'3':120,'4':160};
const BUDGETS    = {trivial:40, low:60, moderate:80, severe:120, extreme:160};

function xpForCreature(creatureLevel) {
  const pl   = parseInt(document.getElementById('partyLevel').value) || 1;
  const diff = Math.max(-4, Math.min(4, creatureLevel - pl));
  return XP_BY_DIFF[String(diff)] || 10;
}

function addMonster(m) {
  const existing = selectedMonsters.find(s => s.name === m.name);
  if (existing) { existing.quantity++; }
  else {
    selectedMonsters.push({
      name: m.name, level: m.level ?? 0, type: m.type || '',
      quantity: 1, xp_each: xpForCreature(m.level ?? 0)
    });
  }
  renderSelectedMonsters();
  updateXPMeter();
}

function renderSelectedMonsters() {
  const list = document.getElementById('creaturesList');
  if (!selectedMonsters.length) {
    list.innerHTML = '<p class="empty-state">Aucune créature ajoutée.</p>';
    document.getElementById('creaturesCard').style.display = 'none';
    document.getElementById('actionRow').style.display = 'none';
    return;
  }
  document.getElementById('creaturesCard').style.display = '';
  document.getElementById('actionRow').style.display = '';

  list.innerHTML = '';
  selectedMonsters.forEach((m, i) => {
    const row = document.createElement('div');
    row.className = 'creature-row';
    row.innerHTML = `
      <div class="creature-info">
        <span class="creature-name">${m.name}</span>
        <span class="creature-meta">${m.type || '—'} · Niv. ${m.level} · ${m.xp_each} XP</span>
      </div>
      <div class="qty-controls">
        <button class="qty-btn" data-idx="${i}" data-dir="-1">−</button>
        <span class="qty-value">${m.quantity}</span>
        <button class="qty-btn" data-idx="${i}" data-dir="1">+</button>
      </div>
      <span class="creature-xp">${m.xp_each * m.quantity} XP</span>
      <button class="remove-btn" data-idx="${i}">✕</button>
    `;
    list.appendChild(row);
  });

  list.querySelectorAll('.qty-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.dataset.idx);
      selectedMonsters[idx].quantity = Math.max(1, selectedMonsters[idx].quantity + parseInt(btn.dataset.dir));
      renderSelectedMonsters();
      updateXPMeter();
    });
  });

  list.querySelectorAll('.remove-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      selectedMonsters.splice(parseInt(btn.dataset.idx), 1);
      renderSelectedMonsters();
      updateXPMeter();
    });
  });
}

function updateXPMeter() {
  const budget   = BUDGETS[currentDifficulty] || 80;
  const used     = selectedMonsters.reduce((s, m) => s + m.xp_each * m.quantity, 0);
  const pct      = Math.min(100, Math.round(used / budget * 100));

  document.getElementById('xpBudget').textContent = budget + ' XP';
  document.getElementById('xpUsed').textContent   = used + ' XP utilisés';
  document.getElementById('xpBar').style.width    = pct + '%';
  document.getElementById('xpBar').style.background =
    pct > 110 ? 'var(--danger)' : pct > 85 ? 'var(--gold)' : 'var(--success)';

  const badge = document.getElementById('diffBadge');
  badge.textContent = currentDifficulty.charAt(0).toUpperCase() + currentDifficulty.slice(1);
  badge.className   = 'diff-badge diff-' + currentDifficulty;
}

// ── Generate encounter from API ────────────────────────────────────────────────
document.getElementById('btnGenerate').addEventListener('click', generateEncounter);
document.getElementById('btnReroll').addEventListener('click', generateEncounter);

async function generateEncounter() {
  const btn = document.getElementById('btnGenerate');
  btn.disabled = true;
  btn.textContent = '…';

  const body = {
    party_level:    parseInt(document.getElementById('partyLevel').value) || 1,
    difficulty:     currentDifficulty,
    encounter_type: document.getElementById('encType').value,
    environment:    document.getElementById('encEnv').value,
    terrain:        document.getElementById('encTerrain').value || null,
    session_id:     activeSessionId || null,
    arc:            document.getElementById('encArc').value || 'custom',
    locked_slots:   Object.keys(lockedSlots).length ? lockedSlots : null,
  };

  try {
    const res  = await fetch('/api/encounter/generate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    const data = await res.json();
    currentEncounter = data;
    applyGeneratedEncounter(data);
  } catch(e) {
    console.error(e);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span data-fr="Générer la rencontre" data-en="Generate encounter">Générer la rencontre</span>';
  }
}

function applyGeneratedEncounter(data) {
  // Replace selected monsters with generated ones
  selectedMonsters = data.creatures.map(c => ({
    name:     c.name,
    level:    c.level,
    type:     c.type,
    quantity: c.quantity,
    xp_each:  c.xp_each,
  }));
  renderSelectedMonsters();
  updateXPMeter();

  // Show hook
  if (data.hook) {
    renderHook(data.hook, data.tactics);
  }

  // Warnings
  if (data.warnings?.length) console.warn('Encounter warnings:', data.warnings);

  // Pre-fill loot tab with context
  if (data.loot_profile_hint) {
    document.getElementById('lootProfile').value = data.loot_profile_hint;
  }
  document.getElementById('lootLevel').value = data.party_level;

  // Pre-select creature types in loot tab
  const types = [...new Set(data.creatures.map(c => c.type).filter(Boolean))];
  document.querySelectorAll('#typePills .pill').forEach(p => {
    p.classList.toggle('active', types.includes(p.dataset.value));
  });
  selectedLootTypes = types;
}

// ── Roll loot from encounter context ──────────────────────────────────────────
document.getElementById('btnRollLoot').addEventListener('click', () => {
  document.querySelector('[data-tab="loot"]').click();
  rollLoot();
});

// ── Loot tab ───────────────────────────────────────────────────────────────────
document.querySelectorAll('#typePills .pill').forEach(pill => {
  pill.addEventListener('click', () => {
    pill.classList.toggle('active');
    selectedLootTypes = Array.from(document.querySelectorAll('#typePills .pill.active'))
      .map(p => p.dataset.value);
  });
});

document.getElementById('btnRollLootDirect').addEventListener('click', rollLoot);

async function rollLoot() {
  const level   = parseInt(document.getElementById('lootLevel').value) || 1;
  const profile = document.getElementById('lootProfile').value;
  const random  = document.getElementById('lootRandomize').checked;
  const types   = selectedLootTypes.length ? selectedLootTypes : ['humanoid'];

  const body = {
    party_level:    level,
    profile:        profile,
    creature_types: types,
    randomize:      random,
  };

  const res  = await fetch('/api/loot/generate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const data = await res.json();
  renderLoot(data);
}

function renderLoot(data) {
  const panel = document.getElementById('lootResult');
  panel.style.display = '';

  document.getElementById('lootProfileLabel').textContent = data.profile;

  const badge = document.getElementById('lootBadge');
  badge.textContent = data.creature_types.join(', ');

  const goldEl   = document.getElementById('lootGold');
  const noteEl   = document.getElementById('lootGoldNote');
  goldEl.textContent = data.gold + ' gp';
  noteEl.textContent = data.gold_note ? '(' + data.gold_note + ')' : '';

  const itemsEl = document.getElementById('lootItems');
  itemsEl.innerHTML = '';

  // Group by type
  const groups = {permanent: [], consumable: [], flavour: []};
  data.items.forEach(item => {
    const g = groups[item.type] || groups.flavour;
    g.push(item);
  });

  const typeLabels = {
    permanent:  {fr: 'Objets permanents', en: 'Permanent items'},
    consumable: {fr: 'Consommables',      en: 'Consumables'},
    flavour:    {fr: 'Butin spécifique',  en: 'Creature drops'},
  };

  Object.entries(groups).forEach(([type, items]) => {
    if (!items.length) return;
    const section = document.createElement('div');
    section.className = 'loot-section';
    section.innerHTML = `<h4 class="loot-section-title">${typeLabels[type].fr}</h4>`;
    items.forEach(item => {
      const row = document.createElement('div');
      row.className = 'loot-item-row rarity-' + item.rarity;
      row.innerHTML = `
        <span class="item-rarity-dot"></span>
        <span class="item-name">${item.name}</span>
        ${item.quantity > 1 ? `<span class="item-qty">×${item.quantity}</span>` : ''}
        <span class="item-range">${item.level_range ? 'Niv. ' + item.level_range : ''}</span>
        <span class="item-rarity-label">${item.rarity}</span>
        ${item.value_note ? `<span class="item-note">${item.value_note}</span>` : ''}
      `;
      section.appendChild(row);
    });
    itemsEl.appendChild(section);
  });

  // Roll log
  const logEl = document.getElementById('lootLog');
  logEl.innerHTML = '';
  data.roll_log.forEach(entry => {
    const li = document.createElement('li');
    li.textContent = entry;
    logEl.appendChild(li);
  });
}

// ── Encounter Browser ──────────────────────────────────────────────────────────
async function loadAdventureList() {
  const res  = await fetch('/api/adventures');
  const data = await res.json();
  adventureList = data;
  const sel = document.getElementById('browseAdventure');
  data.forEach(adv => {
    const opt = document.createElement('option');
    opt.value = adv.id;
    opt.textContent = adv.full_title.slice(0, 60);
    sel.appendChild(opt);
  });
}

document.getElementById('btnBrowse').addEventListener('click', browseEncounters);

async function browseEncounters() {
  const params = new URLSearchParams();
  const q    = document.getElementById('browseSearch').value.trim();
  const adv  = document.getElementById('browseAdventure').value;
  const diff = document.getElementById('browseDiff').value;
  const lvl  = document.getElementById('browseLevel').value;

  if (q)    params.set('q', q);
  if (adv)  params.set('adventure_id', adv);
  if (diff) params.set('difficulty', diff);
  if (lvl)  params.set('level', lvl);
  params.set('limit', 50);

  const res  = await fetch('/api/encounters?' + params);
  const data = await res.json();
  renderBrowserResults(data);
}

function renderBrowserResults(encounters) {
  const container = document.getElementById('browserResults');
  document.getElementById('browserDetail').style.display = 'none';
  container.innerHTML = '';

  if (!encounters.length) {
    container.innerHTML = '<p class="empty-state">Aucune rencontre trouvée.</p>';
    return;
  }

  encounters.forEach(enc => {
    const card = document.createElement('div');
    card.className = 'browser-card';
    card.innerHTML = `
      <div class="browser-card-header">
        <span class="enc-code">${enc.code}</span>
        ${enc.difficulty ? `<span class="diff-badge diff-${enc.difficulty.toLowerCase()}">${enc.difficulty}</span>` : ''}
        ${enc.level ? `<span class="enc-level">Niv. ${enc.level}</span>` : ''}
      </div>
      <div class="enc-name">${enc.name}</div>
      <div class="enc-adventure">${(enc.adventure_title || '').slice(0, 50)}</div>
    `;
    card.addEventListener('click', () => showEncounterDetail(enc));
    container.appendChild(card);
  });
}

async function showEncounterDetail(enc) {
  // Load creatures for this encounter
  const res  = await fetch('/api/encounters/' + enc.id);
  const data = await res.json();

  const detail = document.getElementById('browserDetail');
  detail.style.display = '';
  detail.innerHTML = `
    <div class="detail-header">
      <button class="btn-ghost" id="backToList">← Retour</button>
      <h2>${enc.code} — ${enc.name}</h2>
      <div class="detail-meta">
        ${enc.difficulty ? `<span class="diff-badge diff-${enc.difficulty.toLowerCase()}">${enc.difficulty}</span>` : ''}
        ${enc.level ? `<span class="enc-level">Niveau ${enc.level}</span>` : ''}
      </div>
    </div>
    <p class="detail-adventure">${enc.adventure_title || ''}</p>

    ${data.creatures?.length ? `
    <h3>Créatures</h3>
    <div class="detail-creatures">
      ${data.creatures.map(c => `
        <div class="detail-creature">
          <span class="creature-name">${c.name}</span>
          ${c.quantity > 1 ? `<span class="item-qty">×${c.quantity}</span>` : ''}
          <span class="creature-meta">Niv. ${c.level}</span>
        </div>
      `).join('')}
    </div>` : ''}

    <div class="detail-actions">
      <button class="btn-secondary" id="useInBuilder">Utiliser dans le Builder</button>
    </div>
  `;

  detail.querySelector('#backToList').addEventListener('click', () => {
    detail.style.display = 'none';
  });

  detail.querySelector('#useInBuilder').addEventListener('click', () => {
    if (data.creatures?.length) {
      selectedMonsters = data.creatures.map(c => ({
        name: c.name, level: c.level || 0, type: c.type || '',
        quantity: c.quantity || 1,
        xp_each: xpForCreature(c.level || 0),
      }));
      renderSelectedMonsters();
      updateXPMeter();
      document.querySelector('[data-tab="builder"]').click();
      document.getElementById('encName').value = `${enc.code} — ${enc.name}`;
    }
  });
}

// ── Campaign sessions ──────────────────────────────────────────────────────────

async function loadSessions() {
  const res  = await fetch('/api/campaign-sessions');
  sessionList = await res.json();
  renderSessionSelect();
}

function renderSessionSelect() {
  const sel = document.getElementById('sessionSelect');
  const prev = sel.value;
  sel.innerHTML = '<option value="">— Aucune session —</option>';
  sessionList.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s.id;
    opt.textContent = s.name + (s.arc !== 'custom' ? ` (${s.arc.replace(/_/g,' ')})` : '');
    sel.appendChild(opt);
  });
  if (prev && sel.querySelector(`option[value="${prev}"]`)) sel.value = prev;
  else sel.value = '';
  onSessionChange();
}

function onSessionChange() {
  const val = document.getElementById('sessionSelect').value;
  activeSessionId = val ? parseInt(val) : null;
  document.getElementById('btnDeleteSession').style.display = activeSessionId ? '' : 'none';
  // Sync arc to session's arc
  if (activeSessionId) {
    const s = sessionList.find(s => s.id === activeSessionId);
    if (s && s.arc) document.getElementById('encArc').value = s.arc;
  }
}

document.getElementById('sessionSelect').addEventListener('change', onSessionChange);

document.getElementById('btnNewSession').addEventListener('click', async () => {
  const name = prompt('Nom de la session :');
  if (!name) return;
  const arc  = document.getElementById('encArc').value || 'custom';
  const res  = await fetch('/api/campaign-sessions', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name, arc}),
  });
  const s = await res.json();
  sessionList.unshift(s);
  renderSessionSelect();
  document.getElementById('sessionSelect').value = s.id;
  onSessionChange();
});

document.getElementById('btnDeleteSession').addEventListener('click', async () => {
  if (!activeSessionId) return;
  const s = sessionList.find(s => s.id === activeSessionId);
  if (!confirm(`Supprimer la session "${s?.name}" ? L'historique sera perdu.`)) return;
  await fetch(`/api/campaign-sessions/${activeSessionId}`, {method: 'DELETE'});
  sessionList = sessionList.filter(s => s.id !== activeSessionId);
  activeSessionId = null;
  renderSessionSelect();
});

// ── Hook display ───────────────────────────────────────────────────────────────

const SLOT_KEYS = ['who', 'action', 'modifier', 'object'];
const SLOT_IDS  = { who: 'slotWho', action: 'slotAction', modifier: 'slotModifier', object: 'slotObject' };

function renderHook(hook, terrainTactics) {
  const card = document.getElementById('hookCard');
  card.style.display = '';
  document.getElementById('hookSentence').textContent = hook.hook;

  SLOT_KEYS.forEach(key => {
    const el = document.getElementById(SLOT_IDS[key]);
    el.textContent = hook[key];

    // Restore or clear locked state
    if (lockedSlots[key]) {
      el.classList.add('locked');
      el.title = 'Cliquer pour déverrouiller';
    } else {
      el.classList.remove('locked');
      el.title = 'Cliquer pour verrouiller ce résultat';
    }

    // Attach click handler (replace each time to avoid duplicates)
    el.onclick = () => toggleLock(key, hook[key], el);
  });

  document.getElementById('hookTerrain').textContent = terrainTactics || '';
}

function toggleLock(key, value, el) {
  if (lockedSlots[key]) {
    delete lockedSlots[key];
    el.classList.remove('locked');
    el.title = 'Cliquer pour verrouiller ce résultat';
  } else {
    lockedSlots[key] = value;
    el.classList.add('locked');
    el.title = 'Cliquer pour déverrouiller';
  }
}

// ── Init ───────────────────────────────────────────────────────────────────────
loadOptions();
loadSessions().catch(() => {});
buildLevelShortcuts();
loadAdventureList().catch(() => {}); // non-critical
updateXPMeter();
searchMonsters('', null);
