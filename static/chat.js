/* chat.js — Campaign Manager chat client */

const ROOM_ID = "pf2e";
let ws, myUsername, adminToken = null, rollTablesData = [];

// ── Login ──────────────────────────────────────────────────────────────────────

function chatLogin() {
  const name = document.getElementById("usernameInput").value.trim();
  if (!name) return;
  myUsername = name;
  localStorage.setItem("cm_username", name);
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("chat-main").classList.remove("hidden");
  connectWS();
  loadUpcoming();
  loadRollTables();
}

window.addEventListener("DOMContentLoaded", () => {
  const saved = localStorage.getItem("cm_username");
  if (saved) { document.getElementById("usernameInput").value = saved; }
  document.getElementById("usernameInput").addEventListener("keydown", e => {
    if (e.key === "Enter") chatLogin();
  });
  adminToken = localStorage.getItem("cm_admin_token");
  if (adminToken) showAdminUI();
});


// ── WebSocket ──────────────────────────────────────────────────────────────────

function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "auth", username: myUsername }));
  };

  ws.onmessage = ({ data }) => {
    const msg = JSON.parse(data);

    if (msg.type === "ready") {
      setStatus("Connecté");
      renderOnline(msg.online);
      loadHistory();
    } else if (msg.type === "user_joined") {
      renderOnline(null, msg.username, "add");
      appendSystem(`${msg.username} a rejoint le salon.`);
    } else if (msg.type === "user_left") {
      renderOnline(null, msg.username, "remove");
      appendSystem(`${msg.username} a quitté le salon.`);
    } else if (msg.type === "room_message" && msg.room_id === ROOM_ID) {
      appendMessage(msg);
    } else if (msg.type === "poll_update") {
      updatePollCard(msg);
    } else if (msg.type === "event_created") {
      appendSystem(`📅 ${msg.author} a planifié : ${msg.title} — ${msg.date}${msg.time ? " à " + msg.time : ""}`);
      loadUpcoming();
    }
  };

  ws.onclose = () => {
    setStatus("Déconnecté — reconnexion…");
    setTimeout(connectWS, 3000);
  };
}

function setStatus(txt) {
  document.getElementById("chatStatus").textContent = txt;
}


// ── Online users ───────────────────────────────────────────────────────────────

let onlineSet = new Set();

function renderOnline(list, user, action) {
  if (list) onlineSet = new Set(list);
  if (action === "add")    onlineSet.add(user);
  if (action === "remove") onlineSet.delete(user);
  const el = document.getElementById("onlineList");
  el.innerHTML = [...onlineSet].map(u =>
    `<div class="online-user ${u === myUsername ? "me" : ""}">● ${u}</div>`
  ).join("");
}


// ── Messages ───────────────────────────────────────────────────────────────────

function loadHistory() {
  fetch(`/api/rooms/${ROOM_ID}/history`)
    .then(r => r.json())
    .then(msgs => {
      document.getElementById("messages").innerHTML = "";
      msgs.forEach(m => appendMessage({
        from: m.username, msgType: m.type, content: m.content, timestamp: m.timestamp
      }));
    });
}

function appendMessage(msg) {
  const box = document.getElementById("messages");
  const wrap = document.createElement("div");
  const isMe = msg.from === myUsername;
  wrap.className = `chat-msg ${isMe ? "me" : ""}`;

  const ts = msg.timestamp ? new Date(msg.timestamp + "Z").toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";

  if (msg.msgType === "poll") {
    const poll = JSON.parse(msg.content);
    wrap.innerHTML = `
      <div class="msg-meta">${msg.from} · ${ts}</div>
      <div class="poll-card" id="poll-${poll.poll_id}" data-poll="${poll.poll_id}">
        <div class="poll-question">${poll.question}</div>
        <div class="poll-options">
          ${poll.options.map((o, i) => `
            <button class="poll-opt-btn" onclick="castVote(${poll.poll_id}, ${i})">
              <span class="poll-opt-label">${o}</span>
              <span class="poll-opt-count" id="pv-${poll.poll_id}-${i}">0</span>
            </button>
          `).join("")}
        </div>
      </div>`;
    box.appendChild(wrap);
    fetch(`/api/polls/${poll.poll_id}?viewer=${encodeURIComponent(myUsername)}`)
      .then(r => r.json()).then(updatePollCard);
  } else if (msg.msgType === "image") {
    wrap.innerHTML = `
      <div class="msg-meta">${msg.from} · ${ts}</div>
      <img src="${msg.content}" class="chat-img" onclick="window.open(this.src)">`;
    box.appendChild(wrap);
  } else {
    const text = processCommands(msg.content);
    wrap.innerHTML = `
      <div class="msg-meta">${msg.from} · ${ts}</div>
      <div class="msg-bubble">${text}</div>`;
    box.appendChild(wrap);
  }

  box.scrollTop = box.scrollHeight;
}

function appendSystem(txt) {
  const box = document.getElementById("messages");
  const el  = document.createElement("div");
  el.className = "chat-system";
  el.textContent = txt;
  box.appendChild(el);
  box.scrollTop = box.scrollHeight;
}

function processCommands(text) {
  // Linkify URLs
  return text.replace(/(https?:\/\/\S+)/g, '<a href="$1" target="_blank">$1</a>');
}


// ── Send ───────────────────────────────────────────────────────────────────────

function sendChatMsg() {
  const input = document.getElementById("msgInput");
  const text  = input.value.trim();
  if (!text || !ws || ws.readyState !== 1) return;
  input.value = "";

  if (text.startsWith("/")) {
    handleCommand(text); return;
  }

  ws.send(JSON.stringify({ type: "room_message", room_id: ROOM_ID, msgType: "text", content: text }));
}

function handleCommand(text) {
  const parts = text.slice(1).split(" ");
  const cmd   = parts[0].toLowerCase();
  const args  = parts.slice(1);

  if (cmd === "roll" || cmd === "r") {
    const notation = args[0] || "1d20";
    const result   = rollDice(notation);
    if (result !== null) {
      ws.send(JSON.stringify({
        type: "room_message", room_id: ROOM_ID, msgType: "text",
        content: `🎲 /roll ${notation} → **${result}**`
      }));
    } else {
      appendSystem(`Format invalide : ${notation}. Exemple : 2d6, 1d20+5`);
    }
    return;
  }

  if (cmd === "flip") {
    const r = Math.random() < 0.5 ? "Face" : "Pile";
    ws.send(JSON.stringify({ type: "room_message", room_id: ROOM_ID, msgType: "text", content: `🪙 /flip → ${r}` }));
    return;
  }

  if (cmd === "me") {
    ws.send(JSON.stringify({ type: "room_message", room_id: ROOM_ID, msgType: "text", content: `* ${myUsername} ${args.join(" ")}` }));
    return;
  }

  if (cmd === "help") {
    appendSystem("Commandes : /roll [notation], /flip, /me [action], /help");
    return;
  }

  appendSystem(`Commande inconnue : /${cmd}`);
}

function rollDice(notation) {
  const m = notation.match(/^(\d+)d(\d+)([+-]\d+)?$/i);
  if (!m) return null;
  const count  = Math.min(parseInt(m[1]), 20);
  const sides  = Math.min(parseInt(m[2]), 1000);
  const mod    = parseInt(m[3] || "0");
  let total = mod;
  for (let i = 0; i < count; i++) total += Math.floor(Math.random() * sides) + 1;
  return total;
}


// ── Image upload ───────────────────────────────────────────────────────────────

function triggerImageUpload() {
  document.getElementById("imgFile").click();
}

async function uploadImage(input) {
  if (!input.files[0]) return;
  const form = new FormData();
  form.append("file", input.files[0]);
  const res  = await fetch("/api/upload", { method: "POST", body: form });
  const data = await res.json();
  if (data.url) {
    ws.send(JSON.stringify({ type: "room_message", room_id: ROOM_ID, msgType: "image", content: data.url }));
  }
  input.value = "";
}


// ── Polls ──────────────────────────────────────────────────────────────────────

function openPollModal() { openModal("pollModal"); }

function addPollOption() {
  const container = document.getElementById("pollOptions");
  const n   = container.querySelectorAll(".poll-opt").length + 1;
  const inp = document.createElement("input");
  inp.type = "text"; inp.className = "chat-field poll-opt"; inp.placeholder = `Option ${n}`;
  container.appendChild(inp);
}

function submitPoll() {
  const question = document.getElementById("pollQuestion").value.trim();
  const options  = [...document.querySelectorAll(".poll-opt")].map(i => i.value.trim()).filter(Boolean);
  if (!question || options.length < 2) return;
  ws.send(JSON.stringify({ type: "create_poll", room_id: ROOM_ID, question, options }));
  closeModal("pollModal");
  document.getElementById("pollQuestion").value = "";
  document.querySelectorAll(".poll-opt").forEach((el, i) => { el.value = ""; if (i > 1) el.remove(); });
}

function castVote(pollId, optIdx) {
  ws.send(JSON.stringify({ type: "vote", room_id: ROOM_ID, poll_id: pollId, option: optIdx }));
}

function updatePollCard(state) {
  const card = document.getElementById(`poll-${state.poll_id}`);
  if (!card) return;
  state.options.forEach((_, i) => {
    const el = document.getElementById(`pv-${state.poll_id}-${i}`);
    if (el) el.textContent = state.votes[i] || 0;
  });
  if (state.my_vote !== null) {
    card.querySelectorAll(".poll-opt-btn").forEach((btn, i) => {
      btn.classList.toggle("voted", i === state.my_vote);
    });
  }
}


// ── Notes ──────────────────────────────────────────────────────────────────────

function openNotes() {
  openModal("notesModal");
  document.getElementById("noteDate").value = new Date().toISOString().slice(0, 10);
  loadNotes();
}

function loadNotes() {
  fetch("/api/notes").then(r => r.json()).then(notes => {
    const el = document.getElementById("notesList");
    if (!notes.length) { el.innerHTML = "<p class='muted'>Aucune note.</p>"; return; }
    el.innerHTML = notes.map(n => `
      <div class="note-card">
        <div class="note-meta">${n.date} · ${n.author}</div>
        <div class="note-title">${n.title}</div>
        <div class="note-body">${n.content}</div>
        ${adminToken ? `<button class="btn-danger-sm" onclick="deleteNote(${n.id})">Supprimer</button>` : ""}
      </div>
    `).join("");
  });
}

function saveNote() {
  const note = {
    date:    document.getElementById("noteDate").value,
    title:   document.getElementById("noteTitle").value.trim(),
    content: document.getElementById("noteContent").value.trim(),
    author:  myUsername,
  };
  if (!note.title || !note.content) return;
  fetch("/api/notes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(note) })
    .then(() => { document.getElementById("noteTitle").value = ""; document.getElementById("noteContent").value = ""; loadNotes(); });
}

function deleteNote(id) {
  fetch(`/api/notes/${id}`, { method: "DELETE", headers: { "X-Admin-Token": adminToken } })
    .then(() => loadNotes());
}

function exportNotes() { window.open("/api/notes/export/csv"); }


// ── References ─────────────────────────────────────────────────────────────────

let allRefs = [];

function openRefs() {
  openModal("refsModal");
  document.getElementById("adminUpload").style.display = adminToken ? "block" : "none";
  fetch("/api/references").then(r => r.json()).then(refs => {
    allRefs = refs;
    renderRefs(refs);
  });
}

function renderRefs(refs) {
  const el = document.getElementById("refsList");
  if (!refs.length) { el.innerHTML = "<p class='muted'>Aucune référence.</p>"; return; }
  el.innerHTML = refs.map(r => `
    <div class="ref-card">
      <span class="ref-name">${r.original_name}</span>
      <div class="ref-actions">
        <button onclick="window.open('/api/references/${r.id}/download')">Télécharger</button>
        ${r.original_name.endsWith(".txt") || r.original_name.endsWith(".md")
          ? `<button onclick="readRef(${r.id})">Lire</button>` : ""}
        ${adminToken ? `<button class="btn-danger-sm" onclick="deleteRef(${r.id})">✕</button>` : ""}
      </div>
    </div>
  `).join("");
}

function filterRefs() {
  const q = document.getElementById("refsSearch").value.toLowerCase();
  renderRefs(allRefs.filter(r => r.original_name.toLowerCase().includes(q)));
}

async function uploadRef() {
  const file = document.getElementById("refFile").files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  await fetch("/api/references", { method: "POST", headers: { "X-Admin-Token": adminToken }, body: form });
  openRefs();
}

function deleteRef(id) {
  fetch(`/api/references/${id}`, { method: "DELETE", headers: { "X-Admin-Token": adminToken } })
    .then(() => openRefs());
}

function readRef(id) {
  fetch(`/api/references/${id}/content`).then(r => r.json()).then(data => {
    const win = window.open("", "_blank");
    win.document.write(`<pre style="font-family:monospace;padding:1rem">${data.content}</pre>`);
  });
}


// ── Calendar ───────────────────────────────────────────────────────────────────

function openCalendar() {
  openModal("calModal");
  document.getElementById("evDate").value = new Date().toISOString().slice(0, 10);
  loadEvents();
}

function loadEvents() {
  fetch("/api/events").then(r => r.json()).then(events => {
    const el = document.getElementById("eventsList");
    if (!events.length) { el.innerHTML = "<p class='muted'>Aucun événement.</p>"; return; }
    el.innerHTML = events.map(e => `
      <div class="event-card">
        <div class="event-date">${e.date}${e.time ? " à " + e.time : ""}</div>
        <div class="event-title">${e.title}</div>
        ${e.description ? `<div class="event-desc">${e.description}</div>` : ""}
        <div class="event-author">Par ${e.author}</div>
        ${adminToken ? `<button class="btn-danger-sm" onclick="deleteEvent(${e.id})">Supprimer</button>` : ""}
      </div>
    `).join("");
  });
}

function saveEvent() {
  const event = {
    date:        document.getElementById("evDate").value,
    time:        document.getElementById("evTime").value,
    title:       document.getElementById("evTitle").value.trim(),
    description: document.getElementById("evDesc").value.trim(),
    author:      myUsername,
  };
  if (!event.title) return;
  fetch("/api/events", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(event) })
    .then(() => {
      document.getElementById("evTitle").value = "";
      document.getElementById("evDesc").value  = "";
      loadEvents(); loadUpcoming();
    });
}

function deleteEvent(id) {
  fetch(`/api/events/${id}`, { method: "DELETE", headers: { "X-Admin-Token": adminToken } })
    .then(() => { loadEvents(); loadUpcoming(); });
}

function loadUpcoming() {
  fetch("/api/events/upcoming").then(r => r.json()).then(events => {
    const el = document.getElementById("upcomingEvents");
    if (!events.length) { el.innerHTML = "<p class='muted' style='font-size:0.8rem'>Aucune session planifiée.</p>"; return; }
    el.innerHTML = events.map(e =>
      `<div class="upcoming-item"><span class="upcoming-date">${e.date}</span> ${e.title}</div>`
    ).join("");
  });
}


// ── Roll tables ────────────────────────────────────────────────────────────────

function loadRollTables() {
  fetch("/static/tables.json").then(r => r.json()).then(data => {
    // Keep only Pathfinder tables
    rollTablesData = (data.tables || data).filter(t =>
      (t.system || "").toLowerCase().includes("pathfinder") ||
      (t.universe || "").toLowerCase().includes("pathfinder") ||
      (t.game || "").toLowerCase().includes("pathfinder") ||
      (t.game || "").toLowerCase().includes("pf2") ||
      (t.system || "").toLowerCase().includes("pf2")
    );
  }).catch(() => { rollTablesData = []; });
}

function openRollTables() {
  openModal("rollModal");
  renderRollTables(rollTablesData);
}

function filterRollTables() {
  const q = document.getElementById("rollSearch").value.toLowerCase();
  renderRollTables(rollTablesData.filter(t => (t.name || t.title || "").toLowerCase().includes(q)));
}

function renderRollTables(tables) {
  const el = document.getElementById("rollTablesList");
  if (!tables.length) { el.innerHTML = "<p class='muted'>Aucune table PF2e trouvée.</p>"; return; }
  el.innerHTML = tables.map((t, idx) => {
    const name    = t.name || t.title || "Table";
    const entries = t.entries || t.results || [];
    return `
      <div class="roll-table">
        <div class="roll-table-header" onclick="toggleRollTable(${idx})">
          <span>${name}</span>
          <button class="roll-btn" onclick="event.stopPropagation(); rollOnTable(${idx})">🎲 Lancer</button>
        </div>
        <div class="roll-table-body hidden" id="rt-${idx}">
          ${entries.map(e => `<div class="rt-entry"><span class="rt-range">${e.range || e.roll || ""}</span> ${e.result || e.text || e.description || ""}</div>`).join("")}
        </div>
        <div class="roll-result" id="rr-${idx}"></div>
      </div>`;
  }).join("");
}

function toggleRollTable(idx) {
  document.getElementById(`rt-${idx}`).classList.toggle("hidden");
}

function rollOnTable(idx) {
  const t       = rollTablesData[idx];
  const entries = t.entries || t.results || [];
  if (!entries.length) return;
  const pick = entries[Math.floor(Math.random() * entries.length)];
  document.getElementById(`rr-${idx}`).textContent =
    `→ ${pick.result || pick.text || pick.description || ""}`;
}


// ── Admin ──────────────────────────────────────────────────────────────────────

function openAdminLogin() { openModal("adminModal"); }

function doAdminLogin() {
  const pass = document.getElementById("adminPass").value;
  fetch("/api/admin/login", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password: pass })
  }).then(r => r.json()).then(data => {
    if (data.token) {
      adminToken = data.token;
      localStorage.setItem("cm_admin_token", adminToken);
      showAdminUI();
      closeModal("adminModal");
    } else {
      alert("Mot de passe incorrect.");
    }
  });
}

function showAdminUI() {
  document.getElementById("adminSection").style.display = "none";
}


// ── Modal helpers ──────────────────────────────────────────────────────────────

function openModal(id)  { document.getElementById(id).classList.remove("hidden"); }
function closeModal(id) { document.getElementById(id).classList.add("hidden"); }
