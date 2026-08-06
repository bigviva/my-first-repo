/* Corrective Actions Tracking — single-page frontend (no build step). */

const $main = document.getElementById("main");
let users = [];
let me = null;

const canWrite = () => me && (me.role === "admin" || me.role === "quality");
const isAdmin = () => me && me.role === "admin";

/* ------------------------------------------------------------ utilities */

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: opts.body instanceof FormData ? {} : { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function toast(msg, isError = false) {
  const el = document.createElement("div");
  el.className = "toast" + (isError ? " error" : "");
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), isError ? 6000 : 3000);
}

const STATUS_COLORS = {
  Open: "blue", Containment: "amber", "In Progress": "blue", "Pending Closure": "amber",
  Closed: "green", Draft: "gray", Validated: "blue", Issued: "amber",
  "Response Submitted": "blue", "Response Accepted": "green", "Response Rejected": "red",
  "RCCA In Progress": "blue", "Actions In Progress": "amber",
  "Effectiveness Verification": "amber",
};
function statusBadge(s) { return `<span class="badge ${STATUS_COLORS[s] || "gray"}">${esc(s)}</span>`; }
function escalationBadge(level) {
  if (!level || level === "None") return "";
  const color = level === "Executive" ? "red" : level === "Level 2" ? "amber" : "blue";
  return `<span class="badge ${color}">&#9650; ${esc(level)}</span>`;
}
function overdueBadge(r) { return r.overdue ? '<span class="badge red">Overdue</span>' : ""; }
function field(k, v) {
  return `<div class="field"><div class="k">${esc(k)}</div><div class="v">${v || "&mdash;"}</div></div>`;
}
function ownerOptions(selected) {
  return `<option value="">— unassigned —</option>` + users.map(u =>
    `<option value="${u.id}" ${u.id === selected ? "selected" : ""}>${esc(u.name)} (${esc(u.department)})</option>`
  ).join("");
}

function modal(title, bodyHtml, onMount) {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `<div class="modal"><h2>${esc(title)}</h2>${bodyHtml}</div>`;
  backdrop.addEventListener("click", e => { if (e.target === backdrop) backdrop.remove(); });
  document.body.appendChild(backdrop);
  if (onMount) onMount(backdrop);
  return backdrop;
}

function historyHtml(items) {
  if (!items || !items.length) return '<div class="empty">No history yet</div>';
  return items.map(h => `
    <div class="history-item">
      <strong>${esc(h.action)}</strong> ${esc(h.detail)}
      <div class="when">${esc(h.changed_at)} &middot; ${esc(h.changed_by)}</div>
    </div>`).join("");
}

/* ---------------------------------------------------------------- router */

const views = {};
let currentView = "dashboard";

function navigate(view, ...args) {
  currentView = view;
  document.querySelectorAll("#nav button").forEach(b =>
    b.classList.toggle("active", b.dataset.view === view));
  views[view](...args);
}

document.getElementById("nav").addEventListener("click", e => {
  if (e.target.dataset.view) navigate(e.target.dataset.view);
});

/* ------------------------------------------------------------- dashboard */

views.dashboard = async function () {
  const d = await api("/api/dashboard");
  const section = (name, s) => `
    <div class="panel">
      <h3>${name}</h3>
      <div class="cards">
        <div class="card"><div class="num">${s.open}</div><div class="label">Open</div></div>
        <div class="card good"><div class="num">${s.closed}</div><div class="label">Closed</div></div>
        <div class="card ${s.overdue ? "bad" : ""}"><div class="num">${s.overdue}</div><div class="label">Overdue</div></div>
        ${s.escalated !== undefined ? `<div class="card ${s.escalated ? "warn" : ""}"><div class="num">${s.escalated}</div><div class="label">Escalated</div></div>` : ""}
        ${s.effective_rate !== undefined && s.effective_rate !== null ? `<div class="card good"><div class="num">${s.effective_rate}%</div><div class="label">Effective rate</div></div>` : ""}
      </div>
      <div>${Object.entries(s.by_status).map(([k, v]) => `${statusBadge(k)} ${v}`).join(" &nbsp; ")}</div>
    </div>`;
  $main.innerHTML = `
    <div class="toolbar">
      <div class="spacer"></div>
      ${canWrite() ? '<button class="secondary" id="run-esc">Run overdue escalation sweep</button>' : ""}
    </div>
    ${section("Escapes", d.escapes)}
    ${section("Corrective Action Reports", d.cars)}
    ${section("CAPA", d.capas)}
    <div class="panel"><h3>Recent activity</h3>${historyHtml(d.recent_history)}</div>`;
  const runEsc = document.getElementById("run-esc");
  if (runEsc) runEsc.onclick = async () => {
    try {
      const r = await api("/api/run-escalation", { method: "POST" });
      toast(r.count ? `Escalated ${r.count} overdue record(s): ${r.escalated.map(x => x.ref).join(", ")}` : "Nothing overdue to escalate");
      views.dashboard();
    } catch (e) { toast(e.message, true); }
  };
};

/* --------------------------------------------------------------- escapes */

views.escapes = async function () {
  const rows = await api("/api/escapes");
  $main.innerHTML = `
    <div class="toolbar">
      <input type="text" id="q" placeholder="Search title, ref, customer, part number...">
      <select id="f-status"><option value="">All statuses</option>
        ${["Open", "Containment", "In Progress", "Pending Closure", "Closed"].map(s => `<option>${s}</option>`).join("")}
      </select>
      <select id="f-type"><option value="">Internal + External</option>
        <option value="internal">Internal</option><option value="external">External</option>
      </select>
      ${canWrite() ? '<button class="primary" id="new">+ New Escape</button>' : ""}
    </div>
    <div id="list"></div>`;
  const render = list => {
    document.getElementById("list").innerHTML = list.length ? `
      <table><thead><tr><th>Ref</th><th>Title</th><th>Type</th><th>Customer</th>
        <th>Rating</th><th>Escalation</th><th>Status</th><th>Owner</th><th>Due</th></tr></thead>
      <tbody>${list.map(r => `
        <tr data-id="${r.id}">
          <td>${esc(r.ref)}</td><td>${esc(r.title)}</td><td>${esc(r.escape_type)}</td>
          <td>${esc(r.customer)}</td><td>${r.rating_score}</td>
          <td>${escalationBadge(r.escalation_level)}</td>
          <td>${statusBadge(r.status)} ${overdueBadge(r)}</td>
          <td>${esc(r.owner_name)}</td><td>${esc(r.due_date || "")}</td>
        </tr>`).join("")}</tbody></table>`
      : '<div class="empty">No escapes match</div>';
    document.querySelectorAll("#list tr[data-id]").forEach(tr =>
      tr.onclick = () => escapeDetail(+tr.dataset.id));
  };
  render(rows);
  const refilter = async () => {
    const q = document.getElementById("q").value;
    const status = document.getElementById("f-status").value;
    const type = document.getElementById("f-type").value;
    render(await api(`/api/escapes?q=${encodeURIComponent(q)}&status=${encodeURIComponent(status)}&escape_type=${type}`));
  };
  ["q", "f-status", "f-type"].forEach(id =>
    document.getElementById(id).addEventListener("input", refilter));
  const newEsc = document.getElementById("new");
  if (newEsc) newEsc.onclick = () => escapeForm();
};

function escapeForm() {
  modal("New Escape", `
    <form id="f">
      <label>Title <input name="title" required></label>
      <label>Description <textarea name="description"></textarea></label>
      <div class="row">
        <label>Type <select name="escape_type">
          <option value="internal">Internal</option><option value="external">External (customer)</option>
        </select></label>
        <label>Customer <input name="customer" placeholder="required for external"></label>
      </div>
      <div class="row">
        <label>Program <input name="program"></label>
        <label>Part number <input name="part_number"></label>
      </div>
      <div class="row">
        <label>Severity <select name="severity">
          <option value="1">1 — Minor</option><option value="2">2 — Moderate</option>
          <option value="3" selected>3 — Major</option><option value="4">4 — Critical</option>
        </select></label>
        <label>Likelihood of recurrence <select name="likelihood">
          <option value="1">1 — Rare</option><option value="2" selected>2 — Occasional</option>
          <option value="3">3 — Likely</option><option value="4">4 — Frequent</option>
        </select></label>
      </div>
      <label>Containment plan <textarea name="containment_plan" placeholder="Immediate actions to stop the bleeding — required before closure"></textarea></label>
      <div class="row">
        <label>Due date <input type="date" name="due_date"></label>
        <label>Owner <select name="owner_id">${ownerOptions()}</select></label>
      </div>
      <div class="form-actions">
        <button type="button" class="secondary" data-close>Cancel</button>
        <button class="primary">Create</button>
      </div>
    </form>`, wrap => {
    wrap.querySelector("[data-close]").onclick = () => wrap.remove();
    wrap.querySelector("#f").onsubmit = async e => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      fd.severity = +fd.severity; fd.likelihood = +fd.likelihood;
      fd.owner_id = fd.owner_id ? +fd.owner_id : null;
      fd.due_date = fd.due_date || null;
      try {
        const rec = await api("/api/escapes", { method: "POST", body: JSON.stringify(fd) });
        wrap.remove(); toast(`${rec.ref} created (rating ${rec.rating_score}, escalation: ${rec.escalation_level})`);
        escapeDetail(rec.id);
      } catch (err) { toast(err.message, true); }
    };
  });
}

async function escapeDetail(id) {
  const r = await api(`/api/escapes/${id}`);
  const transitions = {
    Open: ["Containment", "In Progress", "Closed"], Containment: ["In Progress"],
    "In Progress": ["Pending Closure"], "Pending Closure": ["Closed", "In Progress"],
    Closed: ["In Progress"],
  }[r.status] || [];
  $main.innerHTML = `
    <div class="back"><a class="link" id="back">&larr; All escapes</a></div>
    <div class="panel">
      <h3>${esc(r.ref)} — ${esc(r.title)} &nbsp; ${statusBadge(r.status)} ${escalationBadge(r.escalation_level)} ${overdueBadge(r)}</h3>
      <div class="detail-grid">
        ${field("Type", esc(r.escape_type))}
        ${field("Customer", esc(r.customer))}
        ${field("Program", esc(r.program))}
        ${field("Part number", esc(r.part_number))}
        ${field("Severity", `${r.severity} — ${esc(r.severity_label)}`)}
        ${field("Likelihood", `${r.likelihood} — ${esc(r.likelihood_label)}`)}
        ${field("Rating score", `${r.rating_score} / 16`)}
        ${field("Owner", esc(r.owner_name))}
        ${field("Due", esc(r.due_date))}
        ${field("Created", esc(r.created_at))}
        ${field("Closed", esc(r.closed_at))}
      </div>
      <div class="field"><div class="k">Description</div></div>
      <div class="longtext">${esc(r.description) || "—"}</div>
      <div class="field"><div class="k">Containment plan</div></div>
      <div class="longtext">${esc(r.containment_plan) || "— none yet —"}</div>
      <div class="actions">
        ${canWrite() ? transitions.map(t => `<button class="secondary" data-status="${t}">Move to ${t}</button>`).join("") : ""}
        ${canWrite() ? `<button class="secondary" id="edit">Edit</button>
        <button class="secondary" id="notify">Send notification</button>
        <button class="secondary" id="new-car">Raise CAR from this escape</button>` : ""}
      </div>
    </div>
    <div class="panel"><h3>Linked CARs</h3>
      ${r.linked_cars.length ? r.linked_cars.map(c =>
        `<div class="history-item"><a class="link" data-car="${c.id}">${esc(c.ref)}</a> ${esc(c.title)} ${statusBadge(c.status)}</div>`).join("")
      : '<div class="empty">None</div>'}
    </div>
    <div class="panel"><h3>Notifications sent</h3>
      ${r.notifications.length ? r.notifications.map(n =>
        `<div class="history-item">To <strong>${esc(n.recipient)}</strong>: ${esc(n.message)}<div class="when">${esc(n.sent_at)}</div></div>`).join("")
      : '<div class="empty">None</div>'}
    </div>
    <div class="panel"><h3>History</h3>${historyHtml(r.history)}</div>`;

  document.getElementById("back").onclick = () => navigate("escapes");
  document.querySelectorAll("[data-status]").forEach(b => b.onclick = async () => {
    try {
      await api(`/api/escapes/${id}/status`, { method: "POST", body: JSON.stringify({ status: b.dataset.status }) });
      escapeDetail(id);
    } catch (e) { toast(e.message, true); }
  });
  document.querySelectorAll("[data-car]").forEach(a => a.onclick = () => {
    navigate("cars"); carDetail(+a.dataset.car);
  });
  const notifyBtn = document.getElementById("notify");
  if (notifyBtn) notifyBtn.onclick = () => modal("Send notification", `
    <form id="f">
      <label>Recipient <input name="recipient" required placeholder="person, team, or customer"></label>
      <label>Message <textarea name="message" required></textarea></label>
      <div class="form-actions"><button class="primary">Send</button></div>
    </form>`, wrap => {
    wrap.querySelector("#f").onsubmit = async e => {
      e.preventDefault();
      await api(`/api/escapes/${id}/notify`, {
        method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(e.target))) });
      wrap.remove(); toast("Notification recorded"); escapeDetail(id);
    };
  });
  const editEscBtn = document.getElementById("edit");
  if (editEscBtn) editEscBtn.onclick = () => modal(`Edit ${r.ref}`, `
    <form id="f">
      <label>Title <input name="title" value="${esc(r.title)}"></label>
      <label>Description <textarea name="description">${esc(r.description)}</textarea></label>
      <div class="row">
        <label>Severity <select name="severity">${[1, 2, 3, 4].map(n =>
          `<option value="${n}" ${n === r.severity ? "selected" : ""}>${n}</option>`).join("")}</select></label>
        <label>Likelihood <select name="likelihood">${[1, 2, 3, 4].map(n =>
          `<option value="${n}" ${n === r.likelihood ? "selected" : ""}>${n}</option>`).join("")}</select></label>
      </div>
      <label>Containment plan <textarea name="containment_plan">${esc(r.containment_plan)}</textarea></label>
      <div class="row">
        <label>Due date <input type="date" name="due_date" value="${esc(r.due_date || "")}"></label>
        <label>Owner <select name="owner_id">${ownerOptions(r.owner_id)}</select></label>
      </div>
      <div class="form-actions"><button class="primary">Save</button></div>
    </form>`, wrap => {
    wrap.querySelector("#f").onsubmit = async e => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      fd.severity = +fd.severity; fd.likelihood = +fd.likelihood;
      fd.owner_id = fd.owner_id ? +fd.owner_id : null;
      if (!fd.due_date) delete fd.due_date;
      try {
        await api(`/api/escapes/${id}`, { method: "PATCH", body: JSON.stringify(fd) });
        wrap.remove(); escapeDetail(id);
      } catch (err) { toast(err.message, true); }
    };
  });
  const newCarBtn = document.getElementById("new-car");
  if (newCarBtn) newCarBtn.onclick = () => carForm(r.id, r.title);
}

/* ------------------------------------------------------------------ cars */

views.cars = async function () {
  const rows = await api("/api/cars");
  $main.innerHTML = `
    <div class="toolbar">
      <input type="text" id="q" placeholder="Search title, ref, supplier...">
      <select id="f-status"><option value="">All statuses</option>
        ${["Draft", "Validated", "Issued", "Response Submitted", "Response Accepted", "Response Rejected", "Closed"]
          .map(s => `<option>${s}</option>`).join("")}
      </select>
      ${canWrite() ? '<button class="primary" id="new">+ New CAR</button>' : ""}
    </div>
    <div id="list"></div>`;
  const render = list => {
    document.getElementById("list").innerHTML = list.length ? `
      <table><thead><tr><th>Ref</th><th>Title</th><th>Type</th><th>Supplier</th>
        <th>Status</th><th>Owner</th><th>Due</th></tr></thead>
      <tbody>${list.map(r => `
        <tr data-id="${r.id}">
          <td>${esc(r.ref)}</td><td>${esc(r.title)}</td><td>${esc(r.car_type)}</td>
          <td>${esc(r.supplier)}</td>
          <td>${statusBadge(r.status)} ${overdueBadge(r)} ${escalationBadge(r.escalation_level)}</td>
          <td>${esc(r.owner_name)}</td><td>${esc(r.due_date || "")}</td>
        </tr>`).join("")}</tbody></table>`
      : '<div class="empty">No CARs match</div>';
    document.querySelectorAll("#list tr[data-id]").forEach(tr =>
      tr.onclick = () => carDetail(+tr.dataset.id));
  };
  render(rows);
  const refilter = async () => {
    const q = document.getElementById("q").value;
    const status = document.getElementById("f-status").value;
    render(await api(`/api/cars?q=${encodeURIComponent(q)}&status=${encodeURIComponent(status)}`));
  };
  ["q", "f-status"].forEach(id => document.getElementById(id).addEventListener("input", refilter));
  const newCar = document.getElementById("new");
  if (newCar) newCar.onclick = () => carForm();
};

function carForm(escapeId, escapeTitle) {
  modal(escapeId ? `New CAR from escape: ${escapeTitle}` : "New CAR", `
    <form id="f">
      <label>Title <input name="title" required value="${escapeId ? esc("CA for: " + escapeTitle) : ""}"></label>
      <label>Description <textarea name="description"></textarea></label>
      <div class="row">
        <label>Type <select name="car_type">
          <option value="internal">Internal</option><option value="external">External (supplier)</option>
        </select></label>
        <label>Supplier <input name="supplier" placeholder="for external CARs"></label>
      </div>
      <div class="row">
        <label>Severity <select name="severity">${[1, 2, 3, 4].map(n =>
          `<option value="${n}" ${n === 3 ? "selected" : ""}>${n}</option>`).join("")}</select></label>
        <label>Response due <input type="date" name="due_date"></label>
      </div>
      <label>Owner <select name="owner_id">${ownerOptions()}</select></label>
      <div class="form-actions">
        <button type="button" class="secondary" data-close>Cancel</button>
        <button class="primary">Create draft</button>
      </div>
    </form>`, wrap => {
    wrap.querySelector("[data-close]").onclick = () => wrap.remove();
    wrap.querySelector("#f").onsubmit = async e => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      fd.severity = +fd.severity;
      fd.owner_id = fd.owner_id ? +fd.owner_id : null;
      fd.due_date = fd.due_date || null;
      if (escapeId) fd.escape_id = escapeId;
      try {
        const rec = await api("/api/cars", { method: "POST", body: JSON.stringify(fd) });
        wrap.remove(); toast(`${rec.ref} created as draft — validate before issuing`);
        navigate("cars"); carDetail(rec.id);
      } catch (err) { toast(err.message, true); }
    };
  });
}

async function carDetail(id) {
  const r = await api(`/api/cars/${id}`);
  const act = [];
  const supplierHere = me && me.role === "supplier";
  if (canWrite()) {
    if (r.status === "Draft") act.push(`<button class="primary" id="a-validate">Validate for issuance</button>`);
    if (r.status === "Validated") act.push(`<button class="primary" id="a-issue">Issue CAR</button>`);
    if (r.status === "Response Submitted") {
      act.push(`<button class="primary" id="a-accept">Accept response</button>`);
      act.push(`<button class="danger" id="a-reject">Reject response</button>`);
    }
    if (r.status === "Response Accepted") act.push(`<button class="primary" id="a-close">Close CAR</button>`);
  }
  if ((canWrite() || supplierHere) && (r.status === "Issued" || r.status === "Response Rejected"))
    act.push(`<button class="primary" id="a-respond">Submit response</button>`);
  $main.innerHTML = `
    <div class="back"><a class="link" id="back">&larr; All CARs</a></div>
    <div class="panel">
      <h3>${esc(r.ref)} — ${esc(r.title)} &nbsp; ${statusBadge(r.status)} ${overdueBadge(r)} ${escalationBadge(r.escalation_level)}</h3>
      <div class="detail-grid">
        ${field("Type", esc(r.car_type))}
        ${field("Supplier", esc(r.supplier))}
        ${field("Source escape", r.escape_ref ? `<a class="link" id="goto-escape">${esc(r.escape_ref)}</a>` : "")}
        ${field("Severity", r.severity)}
        ${field("Owner", esc(r.owner_name))}
        ${field("Response due", esc(r.due_date))}
        ${field("Validated", r.validated_at ? esc(r.validated_at) : "")}
        ${field("Closed", esc(r.closed_at))}
      </div>
      <div class="field"><div class="k">Description</div></div>
      <div class="longtext">${esc(r.description) || "—"}</div>
      ${r.response_text ? `<div class="field"><div class="k">Submitted response</div></div>
        <div class="longtext">${esc(r.response_text)}</div>` : ""}
      ${r.response_decision_notes ? `<div class="field"><div class="k">Decision notes</div></div>
        <div class="longtext">${esc(r.response_decision_notes)}</div>` : ""}
      <div class="actions">
        ${act.join("")}
        ${!supplierHere ? '<button class="secondary" id="a-recs">Response recommendations</button>' : ""}
        ${canWrite() ? `<button class="secondary" id="a-bulletin">Issue quality alert bulletin</button>
        <button class="secondary" id="a-capa">Create CAPA from this CAR</button>` : ""}
      </div>
      <div id="recs"></div>
    </div>
    <div class="panel"><h3>Linked CAPAs</h3>
      ${r.linked_capas.length ? r.linked_capas.map(c =>
        `<div class="history-item"><a class="link" data-capa="${c.id}">${esc(c.ref)}</a> ${esc(c.title)} ${statusBadge(c.status)}</div>`).join("")
      : '<div class="empty">None</div>'}
    </div>
    <div class="panel"><h3>Quality alert bulletins</h3>
      ${r.bulletins.length ? r.bulletins.map(b =>
        `<div class="history-item"><strong>${esc(b.ref)}</strong> ${esc(b.title)} &middot; to ${esc(b.audience)}<div class="when">${esc(b.issued_at)}</div></div>`).join("")
      : '<div class="empty">None</div>'}
    </div>
    <div class="panel"><h3>History</h3>${historyHtml(r.history)}</div>`;

  document.getElementById("back").onclick = () => navigate("cars");
  const goEscape = document.getElementById("goto-escape");
  if (goEscape) goEscape.onclick = () => { navigate("escapes"); escapeDetail(r.escape_id); };
  document.querySelectorAll("[data-capa]").forEach(a => a.onclick = () => {
    navigate("capas"); capaDetail(+a.dataset.capa);
  });

  const on = (elId, fn) => { const el = document.getElementById(elId); if (el) el.onclick = fn; };

  on("a-validate", () => modal(`Validate ${r.ref} prior to issuance`, `
    <form id="f">
      <label>Validator <select name="validated_by">${ownerOptions()}</select></label>
      <label>Validation notes <textarea name="validation_notes" placeholder="Scope correct? Right supplier/owner? Severity justified? Duplicate check done?"></textarea></label>
      <div class="form-actions">
        <button type="button" class="danger" id="reject-val">Reject (stays draft)</button>
        <button class="primary">Approve for issuance</button>
      </div>
    </form>`, wrap => {
    const submit = async approved => {
      const fd = Object.fromEntries(new FormData(wrap.querySelector("#f")));
      fd.validated_by = fd.validated_by ? +fd.validated_by : null;
      fd.approved = approved;
      await api(`/api/cars/${id}/validate`, { method: "POST", body: JSON.stringify(fd) });
      wrap.remove(); carDetail(id);
    };
    wrap.querySelector("#f").onsubmit = e => { e.preventDefault(); submit(true).catch(err => toast(err.message, true)); };
    wrap.querySelector("#reject-val").onclick = () => submit(false).catch(err => toast(err.message, true));
  }));

  on("a-issue", async () => {
    try { await api(`/api/cars/${id}/issue`, { method: "POST" }); toast("CAR issued and notification recorded"); carDetail(id); }
    catch (e) { toast(e.message, true); }
  });

  on("a-respond", () => modal(`Submit response for ${r.ref}`, `
    <form id="f">
      <label>Response (root cause + corrective action taken)
        <textarea name="response_text" required style="min-height:140px">${esc(r.response_text)}</textarea></label>
      <div class="form-actions"><button class="primary">Submit</button></div>
    </form>`, wrap => {
    wrap.querySelector("#f").onsubmit = async e => {
      e.preventDefault();
      await api(`/api/cars/${id}/respond`, {
        method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(e.target))) });
      wrap.remove(); carDetail(id);
    };
  }));

  const decide = accept => modal(accept ? "Accept response" : "Reject response", `
    <form id="f">
      <label>Notes <textarea name="notes" ${accept ? "" : "required placeholder='Why is the response insufficient?'"}></textarea></label>
      <div class="form-actions"><button class="primary">${accept ? "Accept" : "Reject"}</button></div>
    </form>`, wrap => {
    wrap.querySelector("#f").onsubmit = async e => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      fd.accept = accept;
      await api(`/api/cars/${id}/decision`, { method: "POST", body: JSON.stringify(fd) });
      wrap.remove(); carDetail(id);
    };
  });
  on("a-accept", () => decide(true));
  on("a-reject", () => decide(false));

  on("a-close", async () => {
    try { await api(`/api/cars/${id}/close`, { method: "POST" }); toast("CAR closed"); carDetail(id); }
    catch (e) { toast(e.message, true); }
  });

  on("a-recs", async () => {
    const recs = await api(`/api/cars/${id}/response-recommendations`);
    document.getElementById("recs").innerHTML = `
      <div class="panel"><h3>Recommended responses from similar closed CARs</h3>
      ${recs.length ? recs.map(x => `
        <div class="rec"><span class="score">similarity ${x.score}</span>
          <strong>${esc(x.car_ref)}</strong> ${esc(x.car_title)}
          <div class="longtext" style="margin-top:8px">${esc(x.response_text)}</div>
        </div>`).join("")
      : '<div class="empty">No similar closed CARs with accepted responses yet — recommendations improve as history builds</div>'}
      </div>`;
  });

  on("a-bulletin", () => modal(`Quality alert bulletin for ${r.ref}`, `
    <form id="f">
      <label>Title <input name="title" required value="${esc("Alert: " + r.title)}"></label>
      <label>Body <textarea name="body" required placeholder="What impacted employees need to know or check"></textarea></label>
      <div class="row">
        <label>Target audience <input name="audience" value="All Quality" placeholder="e.g. Manufacturing - Line 3"></label>
        <label>Issued by <select name="issued_by">${ownerOptions()}</select></label>
      </div>
      <div class="form-actions"><button class="primary">Issue bulletin</button></div>
    </form>`, wrap => {
    wrap.querySelector("#f").onsubmit = async e => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      fd.car_id = id;
      fd.issued_by = fd.issued_by ? +fd.issued_by : null;
      await api("/api/bulletins", { method: "POST", body: JSON.stringify(fd) });
      wrap.remove(); toast("Bulletin issued to " + fd.audience); carDetail(id);
    };
  }));

  on("a-capa", () => capaForm(id, r.title));
}

/* ----------------------------------------------------------------- capas */

views.capas = async function () {
  const rows = await api("/api/capas");
  $main.innerHTML = `
    <div class="toolbar">
      <input type="text" id="q" placeholder="Search title, ref, root cause...">
      <select id="f-status"><option value="">All statuses</option>
        ${["Open", "RCCA In Progress", "Actions In Progress", "Effectiveness Verification", "Closed"]
          .map(s => `<option>${s}</option>`).join("")}
      </select>
      ${canWrite() ? '<button class="primary" id="new">+ New CAPA</button>' : ""}
    </div>
    <div id="list"></div>`;
  const render = list => {
    document.getElementById("list").innerHTML = list.length ? `
      <table><thead><tr><th>Ref</th><th>Title</th><th>RCCA method</th><th>Category</th>
        <th>Status</th><th>Effective?</th><th>Owner</th><th>Due</th></tr></thead>
      <tbody>${list.map(r => `
        <tr data-id="${r.id}">
          <td>${esc(r.ref)}</td><td>${esc(r.title)}</td><td>${esc(r.rcca_method)}</td>
          <td>${esc(r.root_cause_category)}</td>
          <td>${statusBadge(r.status)} ${overdueBadge(r)}</td>
          <td>${r.effective === null ? "" : r.effective ? '<span class="badge green">Yes</span>' : '<span class="badge red">No</span>'}</td>
          <td>${esc(r.owner_name)}</td><td>${esc(r.due_date || "")}</td>
        </tr>`).join("")}</tbody></table>`
      : '<div class="empty">No CAPAs match</div>';
    document.querySelectorAll("#list tr[data-id]").forEach(tr =>
      tr.onclick = () => capaDetail(+tr.dataset.id));
  };
  render(rows);
  const refilter = async () => {
    const q = document.getElementById("q").value;
    const status = document.getElementById("f-status").value;
    render(await api(`/api/capas?q=${encodeURIComponent(q)}&status=${encodeURIComponent(status)}`));
  };
  ["q", "f-status"].forEach(id => document.getElementById(id).addEventListener("input", refilter));
  const newCapa = document.getElementById("new");
  if (newCapa) newCapa.onclick = () => capaForm();
};

function capaForm(carId, carTitle) {
  modal(carId ? `New CAPA from CAR: ${carTitle}` : "New CAPA", `
    <form id="f">
      <label>Title <input name="title" required value="${carId ? esc("Systemic fix for: " + carTitle) : ""}"></label>
      <label>Description <textarea name="description"></textarea></label>
      <div class="row">
        <label>RCCA method <select name="rcca_method">
          ${["5-Why", "Fishbone", "8D", "Fault Tree", "Other"].map(x => `<option>${x}</option>`).join("")}
        </select></label>
        <label>Root cause category <select name="root_cause_category" id="rc-cat">
          <option value="">— TBD —</option>
          ${["Process", "Design", "Supplier", "Training", "Equipment", "Documentation", "Material", "Other"]
            .map(x => `<option>${x}</option>`).join("")}
        </select></label>
      </div>
      <div class="row">
        <label>Due date <input type="date" name="due_date"></label>
        <label>Owner <select name="owner_id" id="owner-sel">${ownerOptions()}</select></label>
      </div>
      <div id="assign-sug" style="margin-bottom:12px"></div>
      <div class="form-actions">
        <button type="button" class="secondary" id="suggest">Suggest owner</button>
        <button type="button" class="secondary" data-close>Cancel</button>
        <button class="primary">Create</button>
      </div>
    </form>`, wrap => {
    wrap.querySelector("[data-close]").onclick = () => wrap.remove();
    wrap.querySelector("#suggest").onclick = async () => {
      const cat = wrap.querySelector("#rc-cat").value;
      const sugs = await api(`/api/capas/assignment-suggestions?root_cause_category=${encodeURIComponent(cat)}`);
      wrap.querySelector("#assign-sug").innerHTML = sugs.length ? sugs.map(s => `
        <div class="rec"><span class="score">score ${s.score}</span>
          <a class="link" data-pick="${s.user_id}">${esc(s.name)}</a> — ${esc(s.department)}
          &middot; ${s.effective_capas_closed} effective CAPA(s) closed${cat ? " in " + esc(cat) : ""},
          ${s.open_capa_load} open now</div>`).join("")
        : '<div class="empty">No users yet</div>';
      wrap.querySelectorAll("[data-pick]").forEach(a =>
        a.onclick = () => { wrap.querySelector("#owner-sel").value = a.dataset.pick; });
    };
    wrap.querySelector("#f").onsubmit = async e => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      fd.owner_id = fd.owner_id ? +fd.owner_id : null;
      fd.due_date = fd.due_date || null;
      if (carId) fd.car_id = carId;
      try {
        const rec = await api("/api/capas", { method: "POST", body: JSON.stringify(fd) });
        wrap.remove(); toast(`${rec.ref} created`);
        navigate("capas"); capaDetail(rec.id);
      } catch (err) { toast(err.message, true); }
    };
  });
}

async function capaDetail(id) {
  const r = await api(`/api/capas/${id}`);
  const transitions = {
    Open: ["RCCA In Progress"], "RCCA In Progress": ["Actions In Progress"],
    "Actions In Progress": ["Effectiveness Verification"],
    "Effectiveness Verification": ["Actions In Progress"],
  }[r.status] || [];
  $main.innerHTML = `
    <div class="back"><a class="link" id="back">&larr; All CAPAs</a></div>
    <div class="panel">
      <h3>${esc(r.ref)} — ${esc(r.title)} &nbsp; ${statusBadge(r.status)} ${overdueBadge(r)}
        ${r.effective === null ? "" : r.effective ? '<span class="badge green">Verified effective</span>' : '<span class="badge red">Not effective</span>'}</h3>
      <div class="detail-grid">
        ${field("Source CAR", r.car_ref ? `<a class="link" id="goto-car">${esc(r.car_ref)}</a>` : "")}
        ${field("RCCA method", esc(r.rcca_method))}
        ${field("Root cause category", esc(r.root_cause_category))}
        ${field("Owner", esc(r.owner_name))}
        ${field("Due", esc(r.due_date))}
        ${field("Verified by", esc(r.verified_by_name))}
        ${field("Verified at", esc(r.verified_at))}
        ${field("Closed", esc(r.closed_at))}
      </div>
      <div class="field"><div class="k">Description</div></div>
      <div class="longtext">${esc(r.description) || "—"}</div>
      <div class="field"><div class="k">Root cause</div></div>
      <div class="longtext">${esc(r.root_cause) || "— not yet determined —"}</div>
      <div class="field"><div class="k">Corrective action</div></div>
      <div class="longtext">${esc(r.corrective_action) || "—"}</div>
      <div class="field"><div class="k">Preventive action</div></div>
      <div class="longtext">${esc(r.preventive_action) || "—"}</div>
      ${r.effectiveness_result ? `<div class="field"><div class="k">Effectiveness verification result</div></div>
        <div class="longtext">${esc(r.effectiveness_result)}</div>` : ""}
      <div class="actions">
        ${canWrite() ? transitions.map(t => `<button class="secondary" data-status="${t}">Move to ${t}</button>`).join("") : ""}
        ${canWrite() && r.status === "Effectiveness Verification" ? '<button class="primary" id="a-verify">Record effectiveness verification</button>' : ""}
        ${canWrite() ? '<button class="secondary" id="edit">Edit RCCA / actions</button>' : ""}
        <button class="secondary" id="a-sug">RCCA suggestions from effective CAPAs</button>
      </div>
      <div id="sug"></div>
    </div>
    <div class="panel"><h3>History</h3>${historyHtml(r.history)}</div>`;

  document.getElementById("back").onclick = () => navigate("capas");
  const goCar = document.getElementById("goto-car");
  if (goCar) goCar.onclick = () => { navigate("cars"); carDetail(r.car_id); };
  document.querySelectorAll("[data-status]").forEach(b => b.onclick = async () => {
    try {
      await api(`/api/capas/${id}/status`, { method: "POST", body: JSON.stringify({ status: b.dataset.status }) });
      capaDetail(id);
    } catch (e) { toast(e.message, true); }
  });

  const editBtn = document.getElementById("edit");
  if (editBtn) editBtn.onclick = () => modal(`Edit ${r.ref}`, `
    <form id="f">
      <div class="row">
        <label>RCCA method <select name="rcca_method">
          ${["5-Why", "Fishbone", "8D", "Fault Tree", "Other"].map(x =>
            `<option ${x === r.rcca_method ? "selected" : ""}>${x}</option>`).join("")}
        </select></label>
        <label>Root cause category <select name="root_cause_category">
          <option value="">— TBD —</option>
          ${["Process", "Design", "Supplier", "Training", "Equipment", "Documentation", "Material", "Other"]
            .map(x => `<option ${x === r.root_cause_category ? "selected" : ""}>${x}</option>`).join("")}
        </select></label>
      </div>
      <label>Root cause <textarea name="root_cause">${esc(r.root_cause)}</textarea></label>
      <label>Corrective action <textarea name="corrective_action">${esc(r.corrective_action)}</textarea></label>
      <label>Preventive action <textarea name="preventive_action">${esc(r.preventive_action)}</textarea></label>
      <div class="row">
        <label>Due date <input type="date" name="due_date" value="${esc(r.due_date || "")}"></label>
        <label>Owner <select name="owner_id">${ownerOptions(r.owner_id)}</select></label>
      </div>
      <div class="form-actions"><button class="primary">Save</button></div>
    </form>`, wrap => {
    wrap.querySelector("#f").onsubmit = async e => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      fd.owner_id = fd.owner_id ? +fd.owner_id : null;
      if (!fd.due_date) delete fd.due_date;
      try {
        await api(`/api/capas/${id}`, { method: "PATCH", body: JSON.stringify(fd) });
        wrap.remove(); capaDetail(id);
      } catch (err) { toast(err.message, true); }
    };
  });

  const verifyBtn = document.getElementById("a-verify");
  if (verifyBtn) verifyBtn.onclick = () => modal(`Effectiveness verification for ${r.ref}`, `
    <form id="f">
      <label>Verifier (auditor) <select name="verified_by">${ownerOptions()}</select></label>
      <label>Findings <textarea name="effectiveness_result" required placeholder="Objective evidence: recurrence data, audit results, metrics"></textarea></label>
      <div class="form-actions">
        <button type="button" class="danger" id="not-eff">Not effective — rework</button>
        <button class="primary">Effective — close CAPA</button>
      </div>
    </form>`, wrap => {
    const submit = async effective => {
      const fd = Object.fromEntries(new FormData(wrap.querySelector("#f")));
      fd.verified_by = fd.verified_by ? +fd.verified_by : null;
      fd.effective = effective;
      await api(`/api/capas/${id}/verify`, { method: "POST", body: JSON.stringify(fd) });
      wrap.remove(); capaDetail(id);
    };
    wrap.querySelector("#f").onsubmit = e => { e.preventDefault(); submit(true).catch(err => toast(err.message, true)); };
    wrap.querySelector("#not-eff").onclick = () => submit(false).catch(err => toast(err.message, true));
  });

  document.getElementById("a-sug").onclick = async () => {
    const sugs = await api(`/api/capas/${id}/rcca-suggestions`);
    document.getElementById("sug").innerHTML = `
      <div class="panel"><h3>Root causes &amp; actions from similar historically effective CAPAs</h3>
      ${sugs.length ? sugs.map(x => `
        <div class="rec"><span class="score">similarity ${x.score}</span>
          <strong>${esc(x.capa_ref)}</strong> ${esc(x.capa_title)}
          ${x.root_cause_category ? `<span class="badge gray">${esc(x.root_cause_category)}</span>` : ""}
          <div style="margin-top:8px"><em>Root cause:</em> ${esc(x.root_cause)}</div>
          <div><em>Corrective:</em> ${esc(x.corrective_action)}</div>
          <div><em>Preventive:</em> ${esc(x.preventive_action)}</div>
        </div>`).join("")
      : '<div class="empty">No similar effective CAPAs yet — suggestions improve as verified history builds</div>'}
      </div>`;
  };
}

/* ------------------------------------------------------------- analytics */

const VIZ = {
  c1: "#2a78d6", c2: "#eb6834", c3: "#1baf7a",
  grid: "#e1e0d9", axis: "#c3c2b7", muted: "#898781", ink: "#1c2733",
};

function vizTooltipEl() {
  let el = document.querySelector(".viz-tooltip");
  if (!el) {
    el = document.createElement("div");
    el.className = "viz-tooltip";
    document.body.appendChild(el);
  }
  return el;
}

function attachVizHover(container) {
  const tip = vizTooltipEl();
  container.querySelectorAll("[data-tip]").forEach(t => {
    t.addEventListener("mousemove", e => {
      tip.textContent = t.dataset.tip;
      tip.style.display = "block";
      tip.style.left = Math.min(e.clientX + 12, window.innerWidth - 180) + "px";
      tip.style.top = (e.clientY - 34) + "px";
    });
    t.addEventListener("mouseleave", () => { tip.style.display = "none"; });
  });
}

// Rounded-top bar path (4px data-end radius, flat baseline).
function barPath(x, y, w, h, r) {
  r = Math.min(r, w / 2, h);
  if (h <= 0) return "";
  return `M${x},${y + h} v${-(h - r)} a${r},${r} 0 0 1 ${r},${-r} h${w - 2 * r} ` +
         `a${r},${r} 0 0 1 ${r},${r} v${h - r} z`;
}

function gridLines(maxV, x0, x1, yScale, y0) {
  const step = maxV <= 5 ? 1 : Math.ceil(maxV / 4);
  let out = "";
  for (let v = step; v <= maxV; v += step) {
    const y = y0 - v * yScale;
    out += `<line x1="${x0}" y1="${y}" x2="${x1}" y2="${y}" stroke="${VIZ.grid}" stroke-width="1"/>` +
           `<text x="${x0 - 6}" y="${y + 3}" text-anchor="end" font-size="10" fill="${VIZ.muted}">${v}</text>`;
  }
  return out;
}

// Vertical bar chart, single series.
function vBarChart(labels, values, { color = VIZ.c1, tipFmt = (l, v) => `${l}: ${v}`, W = 360 } = {}) {
  const H = 200, padL = 30, padB = 26, padT = 10;
  const y0 = H - padB;
  const maxV = Math.max(1, ...values);
  const yScale = (y0 - padT) / maxV;
  const n = labels.length || 1;
  const slot = (W - padL - 8) / n;
  const bw = Math.min(48, slot - 8);
  let bars = "", xlabels = "";
  labels.forEach((l, i) => {
    const x = padL + 8 + i * slot + (slot - bw) / 2;
    const h = values[i] * yScale;
    bars += `<path d="${barPath(x, y0 - h, bw, h, 4)}" fill="${color}" data-tip="${esc(tipFmt(l, values[i]))}"/>`;
    const short = String(l).length > 9 ? String(l).slice(0, 8) + "…" : l;
    xlabels += `<text x="${x + bw / 2}" y="${y0 + 14}" text-anchor="middle" font-size="10" fill="${VIZ.muted}">${esc(short)}</text>`;
  });
  return `<div class="chart-wrap"><svg viewBox="0 0 ${W} ${H}" role="img">
    ${gridLines(maxV, padL, W - 4, yScale, y0)}
    <line x1="${padL}" y1="${y0}" x2="${W - 4}" y2="${y0}" stroke="${VIZ.axis}" stroke-width="1"/>
    ${bars}${xlabels}</svg></div>`;
}

// Horizontal bar chart (top-N lists).
function hBarChart(items, { color = VIZ.c1, tipFmt = (l, v) => `${l}: ${v}`, W = 360 } = {}) {
  if (!items.length) return '<div class="empty">No data yet</div>';
  const rowH = 30, padL = 110, padT = 4;
  const H = padT + items.length * rowH + 4;
  const maxV = Math.max(1, ...items.map(d => d.count));
  const scale = (W - padL - 46) / maxV;
  let rows = "";
  items.forEach((d, i) => {
    const y = padT + i * rowH + 5;
    const w = Math.max(2, d.count * scale);
    const label = d.label.length > 18 ? d.label.slice(0, 17) + "…" : d.label;
    rows += `<text x="${padL - 8}" y="${y + 13}" text-anchor="end" font-size="11" fill="${VIZ.ink}">${esc(label)}</text>` +
      `<path d="M${padL},${y} h${w - 4} a4,4 0 0 1 4,4 v${rowH - 18} a4,4 0 0 1 -4,4 h${-(w - 4)} z" fill="${color}" data-tip="${esc(tipFmt(d.label, d.count))}"/>` +
      `<text x="${padL + w + 6}" y="${y + 13}" font-size="11" fill="${VIZ.muted}">${d.count}</text>`;
  });
  return `<div class="chart-wrap"><svg viewBox="0 0 ${W} ${H}" role="img">${rows}</svg></div>`;
}

// Two-series line chart over months with column hover.
function lineChart(months, seriesA, seriesB, nameA, nameB) {
  const W = 720, H = 220, padL = 30, padB = 24, padT = 10;
  const y0 = H - padB;
  const maxV = Math.max(1, ...seriesA, ...seriesB);
  const yScale = (y0 - padT) / maxV;
  const n = months.length;
  const xStep = (W - padL - 16) / Math.max(1, n - 1);
  const x = i => padL + 8 + i * xStep;
  const y = v => y0 - v * yScale;
  const pts = s => s.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const dots = (s, color) => s.map((v, i) =>
    `<circle cx="${x(i)}" cy="${y(v)}" r="3" fill="${color}"/>`).join("");
  let hover = "", xlabels = "";
  const monthName = m => new Date(m + "-15").toLocaleString("en", { month: "short" });
  months.forEach((m, i) => {
    hover += `<rect x="${x(i) - xStep / 2}" y="${padT}" width="${xStep}" height="${y0 - padT}" fill="transparent" data-tip="${esc(`${monthName(m)} ${m.slice(0, 4)} — ${nameA} ${seriesA[i]}, ${nameB} ${seriesB[i]}`)}"/>`;
    if (i % 2 === 0 || n <= 6)
      xlabels += `<text x="${x(i)}" y="${y0 + 14}" text-anchor="middle" font-size="10" fill="${VIZ.muted}">${monthName(m)}</text>`;
  });
  return `
    <div class="viz-legend">
      <span class="key"><span class="swatch" style="background:${VIZ.c1}"></span>${esc(nameA)}</span>
      <span class="key"><span class="swatch" style="background:${VIZ.c2}"></span>${esc(nameB)}</span>
    </div>
    <div class="chart-wrap"><svg viewBox="0 0 ${W} ${H}" role="img">
      ${gridLines(maxV, padL, W - 4, yScale, y0)}
      <line x1="${padL}" y1="${y0}" x2="${W - 4}" y2="${y0}" stroke="${VIZ.axis}" stroke-width="1"/>
      <polyline points="${pts(seriesA)}" fill="none" stroke="${VIZ.c1}" stroke-width="2"/>
      <polyline points="${pts(seriesB)}" fill="none" stroke="${VIZ.c2}" stroke-width="2"/>
      ${dots(seriesA, VIZ.c1)}${dots(seriesB, VIZ.c2)}
      ${hover}${xlabels}</svg></div>`;
}

// Grouped bars: aging buckets x 3 record types. Aqua is low-contrast on white,
// so every bar carries a visible value label (the palette's relief rule).
function agingChart(a) {
  const series = [
    { name: "Escapes", vals: a.escapes, color: VIZ.c1 },
    { name: "CARs", vals: a.cars, color: VIZ.c2 },
    { name: "CAPAs", vals: a.capas, color: VIZ.c3 },
  ];
  const W = 720, H = 210, padL = 30, padB = 26, padT = 16;
  const y0 = H - padB;
  const maxV = Math.max(1, ...series.flatMap(s => s.vals));
  const yScale = (y0 - padT) / maxV;
  const groupW = (W - padL - 16) / a.buckets.length;
  const bw = Math.min(34, (groupW - 24) / 3);
  let bars = "", xlabels = "";
  a.buckets.forEach((b, gi) => {
    const gx = padL + 8 + gi * groupW + (groupW - bw * 3 - 4) / 2;
    series.forEach((s, si) => {
      const v = s.vals[gi];
      const h = v * yScale;
      const x = gx + si * (bw + 2);
      if (h > 0) bars += `<path d="${barPath(x, y0 - h, bw, h, 4)}" fill="${s.color}" data-tip="${esc(`${s.name} open ${b} days: ${v}`)}"/>`;
      bars += `<text x="${x + bw / 2}" y="${y0 - h - 4}" text-anchor="middle" font-size="10" fill="${VIZ.ink}">${v}</text>`;
    });
    xlabels += `<text x="${gx + bw * 1.5}" y="${y0 + 15}" text-anchor="middle" font-size="10" fill="${VIZ.muted}">${b} days</text>`;
  });
  return `
    <div class="viz-legend">${series.map(s =>
      `<span class="key"><span class="swatch" style="background:${s.color}"></span>${s.name}</span>`).join("")}
    </div>
    <div class="chart-wrap"><svg viewBox="0 0 ${W} ${H}" role="img">
      ${gridLines(maxV, padL, W - 4, yScale, y0)}
      <line x1="${padL}" y1="${y0}" x2="${W - 4}" y2="${y0}" stroke="${VIZ.axis}" stroke-width="1"/>
      ${bars}${xlabels}</svg></div>`;
}

views.analytics = async function () {
  const a = await api("/api/analytics");
  const ct = a.cycle_time_days;
  const tile = (num, label, note) => `
    <div class="card"><div class="num">${num}</div><div class="label">${label}</div>
    ${note ? `<div class="stat-note">${note}</div>` : ""}</div>`;
  $main.innerHTML = `
    <div class="cards">
      ${tile(ct.escapes ?? "—", "Avg days to close escape")}
      ${tile(ct.cars ?? "—", "Avg days to close CAR")}
      ${tile(ct.capas ?? "—", "Avg days to close CAPA")}
      ${tile(a.car_first_pass_acceptance !== null ? a.car_first_pass_acceptance + "%" : "—",
             "CAR first-pass acceptance", "responses accepted without a rejection round")}
      ${tile(a.capa_effectiveness_rate !== null ? a.capa_effectiveness_rate + "%" : "—",
             "CAPA effectiveness", "of verified CAPAs confirmed effective")}
    </div>
    <div class="chart-grid">
      <div class="panel wide"><h3>Created vs closed — all concern records, last 12 months</h3>
        ${lineChart(a.months, a.monthly_created, a.monthly_closed, "Created", "Closed")}</div>
      <div class="panel wide"><h3>Open record aging</h3>${agingChart(a.aging)}</div>
      <div class="panel"><h3>Escapes by customer</h3>
        ${hBarChart(a.escapes_by_customer, { tipFmt: (l, v) => `${l}: ${v} escape(s)` })}</div>
      <div class="panel"><h3>CARs by supplier</h3>
        ${hBarChart(a.cars_by_supplier, { color: VIZ.c1, tipFmt: (l, v) => `${l}: ${v} CAR(s)` })}</div>
      <div class="panel"><h3>Root cause Pareto (CAPAs)</h3>
        ${a.root_cause_pareto.length
          ? vBarChart(a.root_cause_pareto.map(d => d.label), a.root_cause_pareto.map(d => d.count),
                      { tipFmt: (l, v) => `${l}: ${v} CAPA(s)` })
          : '<div class="empty">No categorized CAPAs yet</div>'}</div>
      <div class="panel"><h3>Open records by escalation level</h3>
        ${vBarChart(a.escalation_distribution.labels, a.escalation_distribution.counts,
                    { tipFmt: (l, v) => `${l}: ${v} open record(s)` })}</div>
    </div>`;
  attachVizHover($main);
};

/* ------------------------------------------------------------- bulletins */

views.bulletins = async function () {
  const rows = await api("/api/bulletins");
  $main.innerHTML = `
    <div class="toolbar"><div class="spacer"></div>
      ${canWrite() ? '<button class="primary" id="new">+ New bulletin</button>' : ""}</div>
    ${rows.length ? rows.map(b => `
      <div class="panel">
        <h3>${esc(b.ref)} — ${esc(b.title)}</h3>
        <div class="longtext">${esc(b.body)}</div>
        <div class="when" style="color:var(--muted);font-size:12px">
          Audience: <strong>${esc(b.audience)}</strong> &middot; issued ${esc(b.issued_at)}</div>
      </div>`).join("")
    : '<div class="empty">No bulletins issued yet. Bulletins can also be raised from a CAR detail page.</div>'}`;
  const newBul = document.getElementById("new");
  if (newBul) newBul.onclick = () => modal("New quality alert bulletin", `
    <form id="f">
      <label>Title <input name="title" required></label>
      <label>Body <textarea name="body" required></textarea></label>
      <div class="row">
        <label>Target audience <input name="audience" value="All Quality"></label>
        <label>Issued by <select name="issued_by">${ownerOptions()}</select></label>
      </div>
      <div class="form-actions"><button class="primary">Issue</button></div>
    </form>`, wrap => {
    wrap.querySelector("#f").onsubmit = async e => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      fd.issued_by = fd.issued_by ? +fd.issued_by : null;
      await api("/api/bulletins", { method: "POST", body: JSON.stringify(fd) });
      wrap.remove(); views.bulletins();
    };
  });
};

/* ---------------------------------------------------------------- import */

views.import = async function () {
  $main.innerHTML = `
    <div class="panel">
      <h3>Migrate from spreadsheets</h3>
      <p>Export your current tracking spreadsheet as CSV (with a header row) and upload it here.
         Column names are matched case-insensitively; unrecognized columns are ignored.</p>
      <form id="f">
        <div class="row">
          <label>Record type <select name="entity" id="entity">
            <option value="escapes">Escapes</option>
            <option value="cars">CARs</option>
            <option value="capas">CAPAs</option>
          </select></label>
          <label>CSV file <input type="file" name="file" accept=".csv" required></label>
        </div>
        <div id="cols" class="longtext"></div>
        <div class="form-actions"><button class="primary">Import</button></div>
      </form>
      <div id="result"></div>
    </div>`;
  const showCols = async () => {
    const entity = document.getElementById("entity").value;
    const t = await api(`/api/import/template/${entity}`);
    document.getElementById("cols").textContent =
      "Recognized columns: " + t.columns.join(", ");
  };
  showCols();
  document.getElementById("entity").addEventListener("change", showCols);
  document.getElementById("f").onsubmit = async e => {
    e.preventDefault();
    const entity = document.getElementById("entity").value;
    const fd = new FormData(e.target);
    fd.delete("entity");
    try {
      const r = await api(`/api/import/${entity}`, { method: "POST", body: fd });
      document.getElementById("result").innerHTML = `
        <div class="rec"><strong>${r.imported}</strong> record(s) imported.
        ${r.errors.length ? `<div style="margin-top:8px;color:var(--red)">${r.errors.map(esc).join("<br>")}</div>` : ""}</div>`;
    } catch (err) { toast(err.message, true); }
  };
};

/* ----------------------------------------------------------------- users */

views.users = async function () {
  const list = await api("/api/users");
  $main.innerHTML = `
    <div class="toolbar"><div class="spacer"></div>
      ${isAdmin() ? '<button class="primary" id="new">+ Add user</button>' : ""}</div>
    <table><thead><tr><th>Name</th><th>Email</th><th>Department</th><th>Role</th>
      <th>Supplier</th><th>Active</th>${isAdmin() ? "<th></th>" : ""}</tr></thead>
    <tbody>${list.map(u => `
      <tr><td>${esc(u.name)}</td><td>${esc(u.email)}</td><td>${esc(u.department)}</td>
        <td><span class="badge ${u.role === "admin" ? "red" : u.role === "supplier" ? "amber" : u.role === "viewer" ? "gray" : "blue"}">${esc(u.role)}</span></td>
        <td>${esc(u.supplier_name)}</td>
        <td>${u.active ? "Yes" : '<span class="badge gray">Deactivated</span>'}</td>
        ${isAdmin() ? `<td>${u.id === me.id ? "" : `<a class="link" data-toggle="${u.id}" data-active="${u.active}">${u.active ? "Deactivate" : "Reactivate"}</a>`}</td>` : ""}
      </tr>`).join("")}</tbody></table>`;
  if (isAdmin()) {
    document.querySelectorAll("[data-toggle]").forEach(a => a.onclick = async () => {
      await api(`/api/users/${a.dataset.toggle}`, {
        method: "PATCH", body: JSON.stringify({ active: a.dataset.active !== "1" }) });
      views.users();
    });
    const newBtn = document.getElementById("new");
    if (newBtn) newBtn.onclick = () => modal("Add user", `
      <form id="f">
        <div class="row">
          <label>Name <input name="name" required></label>
          <label>Email <input name="email" type="email" required></label>
        </div>
        <div class="row">
          <label>Department <input name="department"></label>
          <label>Role <select name="role" id="role-sel">
            <option value="quality">Quality (read/write)</option>
            <option value="viewer">Viewer (read-only)</option>
            <option value="supplier">Supplier (own CARs only)</option>
            <option value="admin">Admin</option>
          </select></label>
        </div>
        <div class="row">
          <label>Initial password <input name="password" required minlength="8"></label>
          <label>Supplier name (supplier role) <input name="supplier_name"></label>
        </div>
        <div class="form-actions"><button class="primary">Create</button></div>
      </form>`, wrap => {
      wrap.querySelector("#f").onsubmit = async e => {
        e.preventDefault();
        try {
          await api("/api/users", {
            method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(e.target))) });
          wrap.remove(); toast("User created");
          users = await api("/api/users"); views.users();
        } catch (err) { toast(err.message, true); }
      };
    });
  }
};

/* ------------------------------------------------------------------ init */

function applyRoleUI() {
  document.getElementById("nav").hidden = false;
  document.getElementById("whoami").textContent = `${me.name} · ${me.role}`;
  const logoutBtn = document.getElementById("logout");
  logoutBtn.hidden = false;
  logoutBtn.onclick = async () => {
    try { await api("/api/auth/logout", { method: "POST" }); } catch (_) {}
    location.reload();
  };
  document.querySelectorAll("#nav button").forEach(b => {
    const v = b.dataset.view;
    if (me.role === "supplier") b.hidden = v !== "cars";
    else if (v === "import") b.hidden = !canWrite();
    else if (v === "users") b.hidden = false;   // list visible to internal roles
  });
  if (me.role === "supplier") {
    document.querySelectorAll("#nav button").forEach(b =>
      b.classList.toggle("active", b.dataset.view === "cars"));
  }
}

function renderLogin() {
  document.getElementById("nav").hidden = true;
  $main.innerHTML = `
    <div class="login-wrap"><div class="panel">
      <h2>Sign in</h2>
      <div class="login-error" id="err"></div>
      <form id="f">
        <label>Email <input name="email" type="email" required autofocus></label>
        <label>Password <input name="password" type="password" required></label>
        <button class="primary" style="width:100%">Sign in</button>
      </form>
    </div></div>`;
  document.getElementById("f").onsubmit = async e => {
    e.preventDefault();
    try {
      await api("/api/auth/login", {
        method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(e.target))) });
      location.reload();
    } catch (err) {
      document.getElementById("err").textContent = err.message;
    }
  };
}

(async function init() {
  try {
    me = await api("/api/auth/me");
  } catch (_) {
    renderLogin();
    return;
  }
  applyRoleUI();
  if (me.role !== "supplier") {
    try { users = await api("/api/users"); } catch (_) { users = []; }
    navigate("dashboard");
  } else {
    navigate("cars");
  }
})();
