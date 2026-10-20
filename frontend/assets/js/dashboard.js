let currentUserDisplayName = "You";
let currentUserInitials = "ME";

let projects = [
  {
    id: "website",
    name: "Website Redesign",
    symbol: "W",
    summary: "Customer-facing website refresh and CMS migration",
    deadline: "Tomorrow",
    days: 1,
    progress: 78,
    risk: "At risk",
    color: "#4263eb",
    soft: "#eef2ff",
    members: ["ME", "AK", "SL"],
    sources: ["gmail", "slack", "drive"],
    events: [
      {
        id: 1,
        date: "Today, 11:24 AM",
        type: "Slack",
        title: "Mobile navigation fix is ready for review",
        body: "Alex shared the updated build and asked you to approve it before deployment.",
        person: "Alex Kim",
        color: "#7950c8",
      },
      {
        id: 2,
        date: "Yesterday, 3:10 PM",
        type: "Decision",
        title: "Launch moved to Friday at 4:00 PM",
        body: "The team agreed to allow one additional QA cycle. This supersedes the Wednesday launch plan.",
        person: "Current user + 4 teammates",
        color: "#4263eb",
      },
      {
        id: 3,
        date: "Aug 3, 9:30 AM",
        type: "Meeting",
        title: "Final content review",
        body: "Marketing approved the homepage copy. Legal requested one footer disclosure change.",
        person: "Google Calendar",
        color: "#17865c",
      },
    ],
    files: [
      ["Homepage-copy-final.docx", "Google Drive · yesterday"],
      ["Mobile-QA-results.pdf", "Gmail · 2 days ago"],
      ["Launch-checklist.csv", "Google Drive · Aug 2"],
    ],
  },
  {
    id: "vendor",
    name: "Vendor Migration",
    symbol: "V",
    summary: "Move payment processing to the new enterprise vendor",
    deadline: "Friday",
    days: 2,
    progress: 62,
    risk: "",
    color: "#7950c8",
    soft: "#f3efff",
    members: ["ME", "TN", "RC"],
    sources: ["gmail", "calendar", "drive"],
    events: [
      {
        id: 1,
        date: "Today, 9:05 AM",
        type: "Email",
        title: "Security review approved with conditions",
        body: "Risk requested confirmation of the vendor data-retention setting before production access.",
        person: "Priya Shah",
        color: "#d6584c",
      },
      {
        id: 2,
        date: "Aug 4, 2:00 PM",
        type: "Meeting",
        title: "Migration rehearsal completed",
        body: "All test transactions reconciled. The rollback runbook needs one owner update.",
        person: "Google Meet",
        color: "#17865c",
      },
    ],
    files: [
      ["Migration-runbook-v4.pdf", "Google Drive · today"],
      ["Vendor-risk-review.docx", "Gmail · Aug 4"],
    ],
  },
  {
    id: "campaign",
    name: "Fall Campaign",
    symbol: "F",
    summary: "Cross-channel campaign planning for the fall product launch",
    deadline: "Aug 21",
    days: 15,
    progress: 45,
    risk: "",
    color: "#d76c2c",
    soft: "#fff1e7",
    members: ["ME", "MB", "KW"],
    sources: ["slack", "drive", "calendar"],
    events: [
      {
        id: 1,
        date: "Yesterday, 4:42 PM",
        type: "Slack",
        title: "Creative direction selected",
        body: "The team selected concept B after reviewing research and production cost.",
        person: "Marketing channel",
        color: "#7950c8",
      },
      {
        id: 2,
        date: "Aug 1, 10:00 AM",
        type: "File",
        title: "Audience research added",
        body: "The updated deck was associated with this project at 94% confidence.",
        person: "Google Drive",
        color: "#2c966d",
      },
    ],
    files: [
      ["Fall-campaign-brief.pdf", "Google Drive · yesterday"],
      ["Audience-research.pptx", "Google Drive · Aug 1"],
    ],
  },
  {
    id: "onboarding",
    name: "Client Onboarding",
    symbol: "C",
    summary: "Implementation and training plan for Northstar Health",
    deadline: "Sep 4",
    days: 29,
    progress: 31,
    risk: "Needs input",
    color: "#17865c",
    soft: "#e8f7f0",
    members: ["ME", "ET", "NP"],
    sources: ["gmail", "calendar", "slack"],
    events: [
      {
        id: 1,
        date: "Today, 8:17 AM",
        type: "Email",
        title: "Client requested another training session",
        body: "Northstar asked for a reporting workshop for its operations team.",
        person: "Erin Torres",
        color: "#d6584c",
      },
      {
        id: 2,
        date: "Aug 2, 1:00 PM",
        type: "Meeting",
        title: "Technical kickoff completed",
        body: "SSO and data export responsibilities were assigned.",
        person: "Google Calendar",
        color: "#17865c",
      },
    ],
    files: [["Northstar-onboarding-plan.docx", "Gmail · today"]],
  },
  {
    id: "quarterly",
    name: "Quarterly Planning",
    symbol: "Q",
    summary: "Q4 goals, staffing model, and operating plan",
    deadline: "Oct 2",
    days: 57,
    progress: 18,
    risk: "",
    color: "#2e8aa6",
    soft: "#e8f7fa",
    members: ["ME", "DL", "PS"],
    sources: ["drive", "calendar", "gmail"],
    events: [
      {
        id: 1,
        date: "Aug 4, 11:00 AM",
        type: "Meeting",
        title: "Initial priorities collected",
        body: "Department leads submitted preliminary priorities and staffing constraints.",
        person: "Planning workshop",
        color: "#17865c",
      },
    ],
    files: [["Q4-planning-template.xlsx", "Google Drive · Aug 4"]],
  },
];
let actions = [
  {
    id: 1,
    title: "Approve mobile navigation before deployment",
    project: "Website Redesign",
    projectId: "website",
    due: "Overdue",
    overdue: true,
    color: "#4263eb",
  },
  {
    id: 2,
    title: "Confirm vendor data-retention setting",
    project: "Vendor Migration",
    projectId: "vendor",
    due: "Today",
    color: "#7950c8",
  },
  {
    id: 3,
    title: "Review campaign budget assumptions",
    project: "Fall Campaign",
    projectId: "campaign",
    due: "Tomorrow",
    color: "#d76c2c",
  },
  {
    id: 4,
    title: "Schedule client reporting workshop",
    project: "Client Onboarding",
    projectId: "onboarding",
    due: "Aug 10",
    color: "#17865c",
  },
];
let activity = [
  {
    icon: "M",
    text: "<b>Priya Shah</b> sent “Security review approved”",
    meta: "Vendor Migration · Gmail",
    time: "12 min",
    color: "#d6584c",
    soft: "#fff0ef",
  },
  {
    icon: "S",
    text: "<b>Alex Kim</b> shared a mobile navigation update",
    meta: "Website Redesign · Slack",
    time: "32 min",
    color: "#7950c8",
    soft: "#f3efff",
  },
  {
    icon: "D",
    text: "<b>Fall-campaign-brief.pdf</b> was updated",
    meta: "Fall Campaign · Google Drive",
    time: "1 hr",
    color: "#17865c",
    soft: "#e8f7f0",
  },
  {
    icon: "✦",
    text: "AI connected <b>4 related items</b> to Client Onboarding",
    meta: "Confidence: 91%",
    time: "2 hrs",
    color: "#4263eb",
    soft: "#eef2ff",
  },
];
const connectors = [
  { id: "gmail", name: "Gmail", description: "Import selected messages, threads, and attachment metadata", icon: "M", connected: false },
  { id: "google_calendar", name: "Google Calendar", description: "Import meetings, attendees, dates, and descriptions", icon: "31", connected: false },
  { id: "slack", name: "Slack", description: "Planned after Gmail and Calendar", icon: "S", connected: false, comingSoon: true },
];
const $ = (s, r = document) => r.querySelector(s),
  $$ = (s, r = document) => [...r.querySelectorAll(s)];

// Top-level views: Overview (catch-up, read-only), Actions (board + upcoming),
// Projects (the one place you verify/fix/check things off).
const VIEW_IDS = ["overview", "actions", "projects"];
function showView(target) {
  $$(".nav[data-target]").forEach((n) => n.classList.toggle("active", n.dataset.target === target));
  VIEW_IDS.forEach((id) => {
    const el = $("#" + id);
    if (el) el.hidden = id !== target;
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}
// Within Projects: grid of everything, or one project's full-page detail --
// never a partial-width overlay with the grid still visible behind it.
function showProjectsGrid() {
  const grid = $("#projectsGridView");
  const detail = $("#projectDetailView");
  if (grid) grid.hidden = false;
  if (detail) detail.hidden = true;
}
function showProjectDetailView() {
  const grid = $("#projectsGridView");
  const detail = $("#projectDetailView");
  if (grid) grid.hidden = true;
  if (detail) detail.hidden = false;
}
// Overview cards navigate here instead of opening an editable drawer inline.
function goToProject(projectId) {
  showView("projects");
  openProjectPage(projectId);
}

function renderProjects(filter = "all") {
  return; // Stage 7: the project grid is replaced by the chronological timeline.
  // eslint-disable-next-line no-unreachable
  const shown = projects.filter(
    (p) =>
      filter === "all" ||
      (filter === "urgent" && p.days <= 7) ||
      (filter === "risk" && p.risk),
  );
  $("#projectGrid").innerHTML =
    shown
      .map(
        (p) =>
          `<article class="project-card" tabindex="0" data-id="${p.id}" style="--color:${p.color};--soft:${p.soft}"><div><div class="card-top"><span class="project-symbol">${p.symbol}</span><button class="more" aria-label="More options">•••</button></div><h3>${p.name}</h3><p class="summary">${p.summary}</p></div><div><div class="meta"><span class="${p.days <= 2 ? "urgent" : ""}">◷ Due ${p.deadline}</span>${p.risk ? `<span class="risk">${p.risk}</span>` : ""}</div><div class="track"><i style="width:${p.progress}%"></i></div><div class="progress"><span>Progress</span><b>${p.progress}%</b></div></div><div class="card-foot"><span class="avatars">${p.members.map((m) => `<i>${m}</i>`).join("")}</span><span class="chips">${p.sources.map((s) => `<i class="${s}">${s === "calendar" ? "31" : s[0].toUpperCase()}</i>`).join("")}</span><button class="open-project">→</button></div></article>`,
      )
      .join("") || '<p class="empty">No projects match this filter.</p>';
  $$(".project-card").forEach((c) => {
    c.onclick = (e) => !e.target.closest(".more") && openProject(c.dataset.id);
    c.onkeydown = (e) => e.key === "Enter" && openProject(c.dataset.id);
  });
}
let activeProject = null,
  activeTab = "timeline";
function openProject(id) {
  activeProject = projects.find((p) => p.id === id);
  activeTab = "timeline";
  $("#drawerTitle").textContent = activeProject.name;
  $$(".tabs button").forEach((b) =>
    b.classList.toggle("active", b.dataset.tab === "timeline"),
  );
  renderDrawer();
  $("#drawer").classList.add("open");
  $("#backdrop").classList.add("open");
  $("#drawer").setAttribute("aria-hidden", "false");
}
function closeDrawer() {
  $("#drawer").classList.remove("open");
  $("#backdrop").classList.remove("open");
  $("#drawer").setAttribute("aria-hidden", "true");
}
function renderDrawer() {
  if (activeTab === "timeline")
    $("#drawerBody").innerHTML =
      `<div class="timeline">${activeProject.events.map((e) => `<article class="event" data-event="${e.id}" style="--event:${e.color}"><time>${e.date} · ${e.type}</time><h3>${e.title}</h3><p>${e.body}</p><footer>${e.person}<span><button class="edit">Edit</button><button class="delete">Delete</button></span></footer></article>`).join("")}</div>`;
  if (activeTab === "actions") {
    const a = actions.filter((x) => x.projectId === activeProject.id);
    $("#drawerBody").innerHTML = a.length
      ? a
        .map(
          (x) =>
            `<div class="action"><input type="checkbox" ${x.done ? "checked" : ""}><div><strong>${x.title}</strong><small>${x.project}</small></div><span class="due">${x.due}</span></div>`,
        )
        .join("")
      : '<p class="empty">No open actions for this project.</p>';
  }
  if (activeTab === "files")
    $("#drawerBody").innerHTML = activeProject.files
      .map(
        (f) =>
          `<div class="file-row"><i>${f[0].split(".").pop().toUpperCase()}</i><div><strong>${f[0]}</strong><small>${f[1]}</small></div><button class="link-btn">Open ↗</button></div>`,
      )
      .join("");
  $$(".delete").forEach(
    (b) =>
    (b.onclick = () => {
      activeProject.events = activeProject.events.filter(
        (e) => e.id != b.closest(".event").dataset.event,
      );
      renderDrawer();
      toast("Timeline item deleted", "The project memory was updated.");
    }),
  );
  $$(".edit").forEach(
    (b) =>
    (b.onclick = () => {
      const e = activeProject.events.find(
        (e) => e.id == b.closest(".event").dataset.event,
      ),
        v = prompt("Edit timeline title:", e.title);
      if (v?.trim()) {
        e.title = v.trim();
        renderDrawer();
        toast("Timeline item updated", e.title);
      }
    }),
  );
}
function renderConnectors() {
  $("#connectorList").innerHTML = connectors
    .map(
      (c) =>
        `<div class="connector"><i class="source ${c.id}">${c.icon}</i><div><strong>${c.name}</strong><small>${c.description}</small></div><button type="button" data-connector="${c.id}" class="${c.connected ? "connected" : ""}" ${c.comingSoon ? "disabled" : ""}>${c.comingSoon ? "Coming soon" : c.connected ? "Connected" : "Connect"}</button></div>`,
    )
    .join("");
  $$('[data-connector]:not([disabled])').forEach((button) => {
    button.onclick = () => connectSource(button.dataset.connector);
  });
}

async function connectSource(provider) {
  const connector = connectors.find((item) => item.id === provider);
  if (!connector) return;
  if (connector.connected) {
    $("#sourcesDialog").showModal();
    return;
  }
  if (!window.startSourceConnection) {
    toast("Integration setup required", "Deploy the Google OAuth Edge Function before connecting this source.");
    return;
  }
  try {
    await window.startSourceConnection(provider);
  } catch (error) {
    toast(`Could not connect ${connector.name}`, error.message);
  }
}

window.setSourceConnections = (rows = []) => {
  connectors.forEach((connector) => {
    connector.connected = rows.some((row) => row.provider === connector.id && row.status === "active");
  });
  const connected = connectors.filter((connector) => connector.connected);
  document.body.classList.toggle("has-integrations", connected.length > 0);

  // Minimal, disappearing onboarding prompt -- shown only until the first
  // source is connected, replacing the old permanent Integration Hub card.
  const prompt = $("#connectPrompt");
  if (prompt) prompt.hidden = connected.length > 0;

  if (connected.length) {
    $("#syncTitle").textContent = "Apps connected";
    $("#syncStatus").textContent = "Automatic imports are not enabled";
    $("#scanBtn").textContent = "Manage apps";
  } else {
    $("#syncTitle").textContent = "Waiting for a connection";
    $("#syncStatus").textContent = "No automatic imports yet";
    $("#scanBtn").textContent = "Connect apps";
  }
  renderConnectors();
  $$("#sidebarSources li").forEach((row, index) => {
    const connector = connectors[index];
    const state = row.querySelector(".source-state");
    if (connector && state) state.textContent = connector.connected ? "Connected" : "Not connected";
    row.classList.toggle("is-connected", Boolean(connector?.connected));
  });
};
function toast(title, detail) {
  const t = document.createElement("div");
  t.className = "toast";
  t.innerHTML = `<i>✓</i><div><strong>${title}</strong><small>${detail}</small></div>`;
  $("#toasts").append(t);
  setTimeout(() => t.remove(), 3300);
}
window.showToast = toast;

// Stage 7: auth.js loads the real projects/events/actions from Supabase and
// hands them here to replace whatever is currently rendered.
function renderUpcoming(list = []) {
  const host = $("#upcomingList");
  if (!host) return;
  host.innerHTML = list.length
    ? list
      .map(
        (u) =>
          `<div class="up-row clickable" data-item="${u.id || ""}"><span class="up-when">${escHtml(u.when)}</span><span class="up-title">${escHtml(u.title)}</span></div>`,
      )
      .join("")
    : '<p class="empty">Nothing upcoming.</p>';
  $$("#upcomingList .up-row").forEach((r) => {
    if (r.dataset.item) r.onclick = () => openItem(r.dataset.item);
  });
}

window.setDashboardData = ({ upcoming = [] } = {}) => {
  renderUpcoming(upcoming);
};

// ---- Stage 7: catch-up hero + digest ----
let catchupGroups = [];

function tagPill(label, kind) {
  return `<span class="digest-tag tag-${kind}">${escHtml(label)}</span>`;
}

function renderCatchupDigest() {
  const host = $("#catchupList");
  if (!host) return;
  host.style.maxHeight = "";
  host.style.overflowY = "";
  if (!catchupGroups.length) {
    host.innerHTML = '<p class="empty">Nothing new since then — you’re fully caught up.</p>';
    return;
  }
  // One summary card per project (not per item): a brief "what happened"
  // headline + count, not the full item list. Clicking opens the complete
  // message/thread history via the existing project drawer.
  host.innerHTML = catchupGroups
    .map((g) => {
      const top = g.items[0];
      const more = g.items.length - 1;
      const people = [...new Set(g.items.map((it) => it.person).filter(Boolean))];
      const peopleLabel = people.slice(0, 3).join(", ") + (people.length > 3 ? ` +${people.length - 3} more` : "");
      const needsReply = g.items.some((it) => it.requires_response);
      // Prefer the precomputed Haiku sentence (backend/digest); fall back to
      // a plain headline only if it hasn't been generated for this project yet.
      const summary = g.summary
        ? escHtml(g.summary)
        : more > 0
          ? `${escHtml(top.title)} — and ${more} more update${more > 1 ? "s" : ""}`
          : escHtml(top.title);

      // Tag row: urgency (always) + up to 2 content tags from the shared
      // Task/Meeting/Decision/Issue-Blocker/Update-Change taxonomy -- the
      // same one the board will use -- picked by priority so the cap of 3
      // stays even when a project's missed items span several kinds.
      const types = new Set(g.items.map((it) => it.type));
      const contentCandidates = [
        { test: types.has("Issue"), label: "Issue/Blockers", kind: "issue" },
        { test: types.has("Decision"), label: "Decisions", kind: "decision" },
        { test: g.hasTask, label: "Tasks", kind: "task" },
        { test: types.has("Meeting"), label: "Meetings", kind: "meeting" },
        {
          test: ["Email", "File", "Deadline", "Status", "Note"].some((t) => types.has(t)),
          label: "Update / Change", kind: "update",
        },
      ];
      const tags = [
        // Urgency -- always exactly one: do I need to respond?
        needsReply ? tagPill("Needs Your Reply", "reply") : tagPill("For Your Info", "fyi"),
      ];
      for (const c of contentCandidates) {
        if (tags.length >= 3) break;
        if (c.test) tags.push(tagPill(c.label, c.kind));
      }

      return `<div class="digest-item clickable" data-project="${g.id}" style="--color:${g.color}">
        <div class="digest-time">${escHtml(g.when || "")}</div>
        <div class="digest-rail"><span class="digest-line"></span><span class="digest-dot"></span></div>
        <div class="digest-card">
          <div class="digest-body">
            <div class="digest-top">
              <strong>${escHtml(g.project)}</strong>
              <span class="digest-count">${g.items.length} update${g.items.length > 1 ? "s" : ""}</span>
            </div>
            <p class="digest-sentence">${summary}</p>
            <div class="digest-tags">${tags.join("")}</div>
            ${peopleLabel ? `<div class="digest-meta"><span class="digest-people">${escHtml(peopleLabel)}</span></div>` : ""}
          </div>
        </div>
      </div>`;
    })
    .join("");

  // Overview is glance-and-navigate only -- no editing here. Clicking a card
  // takes you to that project's page (Projects view), which is the one place
  // you verify/fix/check things off.
  $$("#catchupList .digest-item").forEach((row) => {
    row.onclick = () => goToProject(row.dataset.project);
  });

  // "What users can do": show ~5 project cards at a time; scroll for the
  // rest rather than dropping data. Each project is one uniform-height row now.
  const rows = $$("#catchupList .digest-item");
  if (rows.length > 5) {
    host.style.maxHeight = `${rows[5].offsetTop}px`;
    host.style.overflowY = "auto";
  }
}

// Shared with the project page, so "Since your last catch-up" there uses the
// exact same window as the digest that brought the user here -- both ends,
// not just the lower bound (a bare ">= cutoff" would leak in everything
// after an OOO range's "to" date too).
let catchupCheckpointMs = null;
let catchupCheckpointToMs = null;

window.setCatchupData = ({ checkpointLabel = "", checkpointISO = null, checkpointToISO = null, groups = [] } = {}) => {
  const since = $("#catchupSince");
  if (since) since.textContent = checkpointLabel || "your last visit";
  catchupCheckpointMs = checkpointISO ? new Date(checkpointISO).getTime() : null;
  catchupCheckpointToMs = checkpointToISO ? new Date(checkpointToISO).getTime() : null;
  catchupGroups = groups;
  renderCatchupDigest();
};

// ---- Stage 7: AI-inferred action board (drag = Stage 8 correction) ----
// Three real states -- In Progress / Completed / Backlog. No separate "Not
// Started" column; Stage 6's default status folds into In Progress since
// the board doesn't distinguish "not started yet" from "in progress".
let boardState = { in_progress: [], completed: [], backlog: [] };
const BOARD_COLS = ["in_progress", "completed", "backlog"];

// Board filters: which project(s) to show (empty set = all projects) and an
// optional due-date range. Module-level so they survive a re-render and a
// drag/drop, and so a project page can drive them via showProjectOnBoard().
// A checkbox dropdown rather than one chip per project -- scales as more
// projects get added instead of the filter bar growing with them -- and
// rather than a native <select multiple>, which needs a modifier key to
// pick more than one option and has no real "closed" state.
let boardProjectFilter = new Set();
let boardDueFrom = null;
let boardDueTo = null;

function _cardMatchesBoardFilters(c) {
  if (boardProjectFilter.size && !boardProjectFilter.has(String(c.projectId))) return false;
  if (boardDueFrom || boardDueTo) {
    if (!c.dueDate) return false;
    if (boardDueFrom && c.dueDate < boardDueFrom) return false;
    if (boardDueTo && c.dueDate > boardDueTo) return false;
  }
  return true;
}

function _boardProjectFilterLabel(list) {
  if (!boardProjectFilter.size) return "All projects";
  if (boardProjectFilter.size === 1) {
    const p = list.find((x) => boardProjectFilter.has(x.id));
    return p ? p.name : "1 project";
  }
  return `${boardProjectFilter.size} projects`;
}

// The checkbox list is built from whatever projects actually have cards on
// the board right now, so the menu never offers one with nothing to show.
// If a selected project drops off the board (e.g. its last action item was
// completed/removed elsewhere), it's dropped from the filter too.
function renderBoardProjectOptions() {
  const btn = $("#boardProjectFilterBtn");
  const menu = $("#boardProjectFilterMenu");
  if (!btn || !menu) return;
  const byProject = {};
  for (const col of BOARD_COLS) {
    for (const c of boardState[col] || []) {
      if (c.projectId) byProject[c.projectId] = { id: String(c.projectId), name: c.project };
    }
  }
  const list = Object.values(byProject).sort((a, b) => a.name.localeCompare(b.name));
  for (const id of [...boardProjectFilter]) {
    if (!list.some((p) => p.id === id)) boardProjectFilter.delete(id);
  }
  btn.textContent = `${_boardProjectFilterLabel(list)} ▾`;
  menu.innerHTML = list.length
    ? list
      .map(
        (p) =>
          `<label><input type="checkbox" value="${p.id}"${boardProjectFilter.has(p.id) ? " checked" : ""}> ${escHtml(p.name)}</label>`,
      )
      .join("")
    : '<p class="board-filter-dd-empty">No projects yet.</p>';
  $$("#boardProjectFilterMenu input[type=checkbox]").forEach((cb) => {
    cb.onchange = () => {
      if (cb.checked) boardProjectFilter.add(cb.value);
      else boardProjectFilter.delete(cb.value);
      renderBoard();
    };
  });
}

// Jumps from a project page to the Task Board, scoped to just that
// project's action items -- "See action items by due dates" in
// _projectBlocks. Due-date range is left open so every due date shows.
function showProjectOnBoard(projectId) {
  boardProjectFilter = new Set([String(projectId)]);
  boardDueFrom = null;
  boardDueTo = null;
  if ($("#boardDueFrom")) $("#boardDueFrom").value = "";
  if ($("#boardDueTo")) $("#boardDueTo").value = "";
  renderBoard();
  showView("actions");
}

function renderBoard() {
  renderBoardProjectOptions();
  for (const col of BOARD_COLS) {
    const host = document.querySelector(`.board-list[data-col="${col}"]`);
    if (!host) continue;
    const cards = (boardState[col] || []).filter(_cardMatchesBoardFilters);
    host.innerHTML = cards.length
      ? cards
        .map((c) => {
          // Same tag-chip idea as the project page and catch-up digest --
          // which project this belongs to, and its due date if it has one
          // (backlog items and some AI-suggested actions won't).
          const chips = [`<span class="board-chip board-chip-project" style="--color:${c.color}">${escHtml(c.project)}</span>`];
          if (c.due) chips.push(`<span class="board-chip board-chip-due${c.overdue ? " board-chip-overdue" : ""}">${escHtml(c.due)}</span>`);
          return `<div class="board-card clickable" draggable="true" data-action="${c.id}" data-project="${c.projectId || ""}" style="--color:${c.color}"><strong>${escHtml(c.title)}</strong><div class="board-card-tags">${chips.join("")}</div></div>`;
        })
        .join("")
      : (boardState[col] || []).length
        ? '<p class="empty small">No items match the current filters.</p>'
        : '<p class="empty small">No items.</p>';
  }
  $$(".board-card").forEach((card) => {
    card.ondragstart = (e) => {
      e.dataTransfer.setData("text/plain", card.dataset.action);
      e.dataTransfer.effectAllowed = "move";
    };
    // A click (as opposed to a drag) takes you to the project it belongs to
    // -- the board stays the place to triage status, the project page stays
    // the one place to see full context and correct the item itself.
    card.onclick = () => {
      if (card.dataset.project) goToProject(card.dataset.project);
    };
  });
  $$(".board-list").forEach((list) => {
    list.ondragover = (e) => e.preventDefault();
    list.ondragenter = () => list.classList.add("drag-over");
    list.ondragleave = () => list.classList.remove("drag-over");
    list.ondrop = async (e) => {
      e.preventDefault();
      list.classList.remove("drag-over");
      const actionId = e.dataTransfer.getData("text/plain");
      const col = list.dataset.col;
      if (!actionId || !col) return;
      let moved = null;
      for (const c of BOARD_COLS) {
        const idx = (boardState[c] || []).findIndex((x) => String(x.id) === actionId);
        if (idx > -1) {
          moved = boardState[c][idx];
          boardState[c].splice(idx, 1);
          break;
        }
      }
      if (!moved) return;
      // Only two underlying statuses now (Backlog is a flag, not a status):
      // dropping into Backlog keeps the action "in progress" underneath,
      // just flagged low-priority; In Progress/Completed set status directly.
      const status = col === "backlog" ? "in_progress" : col;
      const backlog = col === "backlog";
      moved.status = status;
      moved.backlog = backlog;
      boardState[col].push(moved);
      renderBoard();
      const ok = await window.updateActionStatus?.(actionId, status, backlog, moved.projectId);
      if (!ok) {
        toast("Update failed", moved.title);
        return;
      }
      // Keep the project page in sync in real time too -- the same
      // correction, just made from the board instead of from the project
      // page's own status control.
      const project = moved.projectId ? projectIndex[moved.projectId] : null;
      const action = project?.actions?.find((a) => String(a.id) === String(actionId));
      if (action) {
        action.status = status;
        action.backlog = backlog;
        action.done = status === "completed";
      }
      if (_drawerContext && String(_drawerContext.projectId) === String(moved.projectId)) {
        _refreshDrawer();
      }
      toast("Board updated", moved.title);
    };
  });
}

window.setBoardData = (data = {}) => {
  boardState = {
    in_progress: data.in_progress || [],
    completed: data.completed || [],
    backlog: data.backlog || [],
  };
  renderBoard();
};

// Keeps the Task Board in sync in real time when an action item is changed
// from somewhere else (the project page's checkbox, its edit dialog, or a
// reject) instead of only picking up the change on the next full reload.
// `patch` merges onto the card and re-files it into the right column if
// `status`/`backlog` changed; `patch === null` removes the card entirely
// (a reject).
function _syncBoardCard(actionId, patch) {
  let card = null, fromCol = null;
  for (const col of BOARD_COLS) {
    const idx = (boardState[col] || []).findIndex((x) => String(x.id) === String(actionId));
    if (idx > -1) {
      card = boardState[col][idx];
      fromCol = col;
      if (patch === null) boardState[col].splice(idx, 1);
      break;
    }
  }
  if (!card) return;
  if (patch === null) {
    renderBoard();
    return;
  }
  Object.assign(card, patch);
  const targetCol = card.backlog ? "backlog" : card.status || "in_progress";
  if (targetCol !== fromCol) {
    boardState[fromCol] = boardState[fromCol].filter((x) => String(x.id) !== String(actionId));
    (boardState[targetCol] ||= []).push(card);
  }
  renderBoard();
}

// ---- Stage 7: source items + thread drawer (feeds the digest's click-through) ----
let allItems = [];
let projectIndex = {};

function escHtml(value = "") {
  const el = document.createElement("div");
  el.textContent = value;
  return el.innerHTML;
}

// Mirrors auth.js's dayLabel() so an edited due date shows the right
// "Overdue" / "Today" / "Tomorrow" / short-date label immediately, without
// waiting on the next full reload from Supabase.
function formatDueLabel(dateStr) {
  if (!dateStr) return "No date";
  const d = new Date(`${dateStr}T00:00:00`);
  const days = Math.ceil((d - new Date()) / 86400000);
  if (days < 0) return "Overdue";
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
// Mirrors auth.js's board-card `overdue` computation, for the same reason.
function computeOverdue(dateStr, done) {
  return !!(dateStr && !done && new Date(`${dateStr}T23:59:59`) < new Date());
}
// The Task Board's three real states, from an action's raw status/backlog --
// shared by the project page's status select so both surfaces agree on what
// "the status" means for a given action.
function actionStatusCol(a) {
  if (a.backlog) return "backlog";
  return a.status === "completed" ? "completed" : "in_progress";
}

// Event type -> tag color, sharing the same taxonomy as the digest/board.
const EVENT_TAG_KIND = { Decision: "decision", Meeting: "meeting", Issue: "issue" };

// Same local calendar day? Used to decide whether an event's AI-interpreted
// date is worth flagging as different from its source message's real date --
// small formatting/timezone differences shouldn't trigger a false alarm.
function _sameLocalDay(msA, msB) {
  if (msA == null || msB == null) return true;
  const a = new Date(msA), b = new Date(msB);
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

// Consecutive items (already date-sorted) that landed on the same local day
// get one shared header instead of each repeating its own time + type tag.
function _clusterEventsByDay(events) {
  const groups = [];
  for (const e of events) {
    const last = groups[groups.length - 1];
    if (last && _sameLocalDay(last[0].dateMs, e.dateMs)) {
      last.push(e);
    } else {
      groups.push([e]);
    }
  }
  return groups;
}

// One item's title/body/verify row -- no time or type tag here anymore;
// those live once on the cluster's shared header.
function _dpEventItemRow(e) {
  const diverges = e.sourceWhenMs != null && !_sameLocalDay(e.dateMs, e.sourceWhenMs);
  // Every item still carries its own verify controls -- this is the one
  // place items get confirmed or corrected (Stage 8), even when grouped.
  return `<div class="dp-event" data-event="${e.id}" data-src="${e.source_item_id || ""}" data-title="${escHtml(e.title)}">
    <div class="dp-event-main${e.source_item_id ? " clickable" : ""}">
      <strong>${escHtml(e.title)}</strong>
      ${e.body ? `<p>${escHtml(e.body)}</p>` : ""}
      ${diverges ? `<small class="dp-ai-note">Message itself is dated ${escHtml(e.sourceWhen)} — verify if this looks off</small>` : ""}
    </div>
    <div class="digest-verify">
      <button type="button" class="verify-ok" title="Looks right">✓</button>
      <button type="button" class="verify-fix" title="Fix">✎</button>
    </div>
  </div>`;
}

// A day's worth of events: one time + the union of their type tags up top,
// each item still its own row underneath -- easier to scan than a wall of
// near-duplicate cards that all happened "around the same time".
function _dpEventCluster(items) {
  const types = [...new Set(items.map((e) => e.type))];
  const tags = types.map((t) => tagPill(t, EVENT_TAG_KIND[t] || "update")).join("");
  const anyDiverges = items.some((e) => e.sourceWhenMs != null && !_sameLocalDay(e.dateMs, e.sourceWhenMs));
  return `<div class="dp-event-group">
    <div class="dp-event-group-head">
      <time>${escHtml(items[0].date)}</time>
      ${tags}
      ${items.length > 1 ? `<span class="dp-cluster-count">${items.length} items</span>` : ""}
      ${anyDiverges ? `<span class="dp-ai-flag" title="AI-interpreted date from the message text">✦ AI-dated</span>` : ""}
    </div>
    ${items.map(_dpEventItemRow).join("")}
  </div>`;
}

function _dpEventList(events) {
  return _clusterEventsByDay(events).map(_dpEventCluster).join("");
}

// Which statuses the currently-viewed project's action list shows -- default
// mirrors the old "open actions only" behavior (Completed hidden unless the
// user opts in). Reset per-project (see _ensureActionFilterFor) so switching
// projects doesn't carry over a filter that no longer makes sense there.
let actionStatusFilter = new Set(["in_progress", "backlog"]);
let _actionFilterProjectId = null;
function _ensureActionFilterFor(projectId) {
  if (_actionFilterProjectId !== projectId) {
    actionStatusFilter = new Set(["in_progress", "backlog"]);
    _actionFilterProjectId = projectId;
  }
}

// One action item row -- the status select is the same three states as the
// Task Board's columns, so changing it here is the identical correction
// (edit_action) as dragging a card there. The verify controls answer a
// different question: not "what state is this in" but "is this actually a
// real, correctly-described action" -- confirm it, fix its title/due date,
// or say it isn't needed at all (reject_match, removes it).
function _dpActionRow(a, project) {
  const col = actionStatusCol(a);
  return `<div class="dp-action" data-action="${a.id}" data-project="${project.id}" data-title="${escHtml(a.title)}" data-due="${escHtml(a.dueDate || "")}">
    <div class="dp-action-top">
      <strong>${escHtml(a.title)}</strong>
      <div class="digest-verify dp-action-verify">
        <button type="button" class="action-verify-ok" title="Looks right — this is needed">✓</button>
        <button type="button" class="action-verify-fix" title="Edit">✎</button>
        <button type="button" class="action-verify-reject" title="Not needed — remove">✕</button>
      </div>
    </div>
    <div class="dp-action-meta">
      <select class="dp-action-status" data-action="${a.id}" data-project="${project.id}">
        <option value="in_progress"${col === "in_progress" ? " selected" : ""}>In Progress</option>
        <option value="completed"${col === "completed" ? " selected" : ""}>Completed</option>
        <option value="backlog"${col === "backlog" ? " selected" : ""}>Backlog</option>
      </select>
      ${a.due ? `<em>${escHtml(a.due)}</em>` : ""}
    </div>
  </div>`;
}

function _projectBlocks(project) {
  if (!project) return "";
  // Project summary (Stage 5, LLM-generated) gets the same verify-in-place
  // treatment as timeline events: "✓ looks right" / "✎ fix" inline, instead
  // of being the one AI-generated piece of text nobody can correct.
  const summaryBlock = project.summary
    ? `<div class="dp-summary" data-project="${project.id}">
        <p>${escHtml(project.summary)}</p>
        <div class="digest-verify dp-summary-verify">
          <button type="button" class="summary-verify-ok" title="Summary looks right">✓</button>
          <button type="button" class="summary-verify-fix" title="Edit summary">✎</button>
        </div>
      </div>`
    : "";
  let html = `<div class="dp-head"><span class="dp-symbol" style="--color:${project.color || "#4263eb"}">${escHtml(project.symbol || "P")}</span><div class="dp-head-body"><strong>${escHtml(project.name)}</strong>${summaryBlock}</div></div>`;
  const allActs = project.actions || [];
  if (allActs.length) {
    const filterChip = (status, label) =>
      `<button type="button" class="board-filter-chip${actionStatusFilter.has(status) ? " active" : ""}" data-status="${status}">${label}</button>`;
    const filtered = allActs.filter((a) => actionStatusFilter.has(actionStatusCol(a)));
    html += `<div class="dp-block">
      <div class="dp-actions-head">
        <h4>Action items</h4>
        <button type="button" class="link-btn dp-due-link" data-project="${project.id}">See action items by due dates →</button>
      </div>
      <div class="dp-action-filter">
        ${filterChip("in_progress", "In Progress")}
        ${filterChip("completed", "Completed")}
        ${filterChip("backlog", "Backlog")}
      </div>
      ${filtered.length
        ? filtered.map((a) => _dpActionRow(a, project)).join("")
        : '<p class="empty small">No action items match this filter.</p>'}
    </div>`;
  }

  // Split on the same window the catch-up digest uses, so "recent" here
  // means exactly what brought this project onto the Overview digest --
  // bounded on both ends, so an OOO range's "to" date is actually respected.
  const events = (project.events || []).slice().sort((a, b) => (b.dateMs || 0) - (a.dateMs || 0));
  const cutoff = catchupCheckpointMs;
  const cutoffTo = catchupCheckpointToMs;
  const recent = cutoff != null
    ? events.filter((e) => e.dateMs != null && e.dateMs >= cutoff && (cutoffTo == null || e.dateMs <= cutoffTo))
    : events;
  const anyDiverges = events.some((e) => e.sourceWhenMs != null && !_sameLocalDay(e.dateMs, e.sourceWhenMs));

  // html += `<p class="dp-legend">Dates below are when the AI thinks each thing actually happens, based on the message text — not always the same as when the message arrived. ${anyDiverges ? 'Items marked <span class="dp-ai-flag">✦ AI-dated</span> differ from their source message — worth a quick check.' : ""}</p>`;

  html += `<div class="dp-block dp-recent">
    <h4>Since your last catch-up</h4>
    ${recent.length ? _dpEventList(recent) : '<p class="empty">Nothing new here since you last checked.</p>'}
  </div>`;

  // Genuinely complete -- every event, including the recent ones above, so
  // nothing you already saw "since your last catch-up" looks like it went
  // missing once you look at the full record.
  if (events.length) {
    const historyId = `dp-history-${project.id}`;
    html += `<div class="dp-history">
      <button type="button" class="link-btn dp-history-toggle" data-target="${historyId}">Show complete history (${events.length} total) ▸</button>
      <div class="dp-history-body" id="${historyId}" hidden>
        ${_dpEventList(events)}
      </div>
    </div>`;
  }

  return html;
}

// Tracks how the drawer was opened so an edit can re-render it from the
// (now-updated) cached data instead of leaving stale text on screen.
let _drawerContext = null;

// A real edit dialog for Stage 8 "✎ fix" corrections -- multi-line, visible
// on screen, cancelable -- instead of a bare window.prompt(). One shared
// dialog, built from a list of fields (e.g. title + generated summary, or
// title + recommended due date) so a single correction can touch more than
// one column at once; `onSave` receives `{ fieldId: value }` and returns
// true/false so the dialog only closes on success. `type: "date"` renders a
// real date input instead of a textarea; anything else defaults to textarea.
let _editDialogOnSave = null;
function openEditDialog({ title, help, fields, onSave }) {
  const dialog = $("#editItemDialog");
  if (!dialog) return;
  $("#editItemTitle").textContent = title;
  $("#editItemHelp").textContent = help || "";
  const host = $("#editItemFields");
  host.innerHTML = fields
    .map((f) => {
      const required = f.required === false ? "" : " required";
      const control =
        f.type === "date"
          ? `<input type="date" data-field="${f.id}" value="${escHtml(f.value || "")}"${required}>`
          : `<textarea data-field="${f.id}" rows="${f.rows || 4}"${required}>${escHtml(f.value || "")}</textarea>`;
      return `<label class="full"><span>${escHtml(f.label)}</span>${control}</label>`;
    })
    .join("");
  _editDialogOnSave = onSave;
  dialog.showModal();
  const first = host.querySelector("textarea, input");
  if (first) {
    first.focus();
    if (first.select) first.select();
  }
}
if ($("#editItemForm")) {
  $("#editItemForm").onsubmit = async (e) => {
    e.preventDefault();
    const values = {};
    let valid = true;
    $$("#editItemFields [data-field]").forEach((el) => {
      const v = el.value.trim();
      if (el.hasAttribute("required") && !v) valid = false;
      values[el.dataset.field] = v;
    });
    if (!valid || !_editDialogOnSave) return;
    const submitBtn = e.submitter;
    if (submitBtn) submitBtn.disabled = true;
    const ok = await _editDialogOnSave(values);
    if (submitBtn) submitBtn.disabled = false;
    if (ok) $("#editItemDialog").close();
  };
}

// Events are cached per-project (not in one flat list), and a fix's click
// target doesn't carry its project id -- look the event up by id across the
// cached projects, same way the post-save refresh already does.
function _findCachedEvent(eventId) {
  for (const project of Object.values(projectIndex)) {
    const ev = project.events?.find((x) => String(x.id) === String(eventId));
    if (ev) return ev;
  }
  return null;
}

// Wire the interactive bits inside a freshly-rendered drawer or project page
// (whichever is currently showing): change an action's status (same
// correction the board's drag makes), verify/fix a timeline event, or open
// its original message/event. Selectors are unscoped since only one
// container is ever populated at a time.
function _wireDrawerInteractions() {
  $$(".dp-action-status").forEach((sel) => {
    const prev = sel.value;
    sel.onchange = async (e) => {
      e.stopPropagation();
      const actionId = sel.dataset.action;
      const projectId = sel.dataset.project || null;
      if (!actionId) return;
      const value = sel.value; // "in_progress" | "completed" | "backlog"
      const status = value === "completed" ? "completed" : "in_progress";
      const backlog = value === "backlog";
      const ok = await window.updateActionStatus?.(actionId, status, backlog, projectId);
      if (!ok) {
        sel.value = prev;
        toast("Could not update", "Please try again.");
        return;
      }
      const project = projectId ? projectIndex[projectId] : null;
      const action = project?.actions?.find((a) => String(a.id) === String(actionId));
      if (action) {
        action.status = status;
        action.backlog = backlog;
        action.done = status === "completed";
      }
      _syncBoardCard(actionId, { status, backlog });
      toast("Updated", "Status changed.");
      _refreshDrawer();
    };
  });
  $$(".dp-event-main.clickable").forEach((row) => {
    row.onclick = () => {
      const src = row.closest(".dp-event")?.dataset.src;
      if (src) openItem(src);
    };
  });
  $$(".dp-history-toggle").forEach((btn) => {
    btn.onclick = () => {
      const body = document.getElementById(btn.dataset.target);
      if (!body) return;
      if (body.hasAttribute("hidden")) {
        body.removeAttribute("hidden");
        btn.textContent = btn.textContent.replace("▸", "▾").replace("Show", "Hide");
      } else {
        body.setAttribute("hidden", "");
        btn.textContent = btn.textContent.replace("▾", "▸").replace("Hide", "Show");
      }
    };
  });
  $$(".verify-ok").forEach((b) => {
    b.onclick = async (e) => {
      e.stopPropagation();
      const row = b.closest(".dp-event");
      const ok = await window.confirmDigestItem?.(row?.dataset.src || null, _drawerContext?.projectId || null);
      toast(ok ? "Confirmed" : "Could not confirm", ok ? "Thanks — marked as correct." : "Please try again.");
    };
  });
  $$(".verify-fix").forEach((b) => {
    b.onclick = async (e) => {
      e.stopPropagation();
      const row = b.closest(".dp-event");
      const eventId = row?.dataset.event;
      if (!eventId) return;
      const cached = _findCachedEvent(eventId);
      openEditDialog({
        title: "Edit timeline event",
        help: "Fix the title and/or the AI-generated summary for this event. Saved corrections are used to improve future extraction.",
        fields: [
          { id: "title", label: "Title", value: cached?.title ?? row?.dataset.title ?? "", rows: 2 },
          { id: "body", label: "Summary", value: cached?.body ?? "", rows: 5, required: false },
        ],
        onSave: async (values) => {
          const ok = await window.editDigestEvent?.(eventId, { title: values.title, body: values.body });
          if (!ok) {
            toast("Could not save fix", "Please try again.");
            return false;
          }
          const ev = _findCachedEvent(eventId);
          if (ev) {
            ev.title = values.title;
            ev.body = values.body;
          }
          toast("Updated", "Timeline item corrected.");
          _refreshDrawer();
          return true;
        },
      });
    };
  });

  // Stage 8: verify-in-place for the project's own summary (Stage 5,
  // LLM-generated) -- confirm it reads correctly, or fix it in place.
  $$(".summary-verify-ok").forEach((b) => {
    b.onclick = async (e) => {
      e.stopPropagation();
      const projectId = b.closest(".dp-summary")?.dataset.project || _drawerContext?.projectId || null;
      if (!projectId) return;
      const ok = await window.confirmProjectSummary?.(projectId);
      toast(ok ? "Confirmed" : "Could not confirm", ok ? "Thanks — summary marked as correct." : "Please try again.");
    };
  });
  $$(".summary-verify-fix").forEach((b) => {
    b.onclick = async (e) => {
      e.stopPropagation();
      const projectId = b.closest(".dp-summary")?.dataset.project || _drawerContext?.projectId || null;
      if (!projectId) return;
      openEditDialog({
        title: "Edit project summary",
        help: "Rewrite the AI-generated summary for this project. Saved corrections are used to improve future extraction.",
        fields: [{ id: "summary", label: "Summary", value: projectIndex[projectId]?.summary || "", rows: 5 }],
        onSave: async (values) => {
          const ok = await window.editProjectSummary?.(projectId, values.summary);
          if (!ok) {
            toast("Could not save summary", "Please try again.");
            return false;
          }
          if (projectIndex[projectId]) projectIndex[projectId].summary = values.summary;
          toast("Updated", "Project summary corrected.");
          _refreshDrawer();
          return true;
        },
      });
    };
  });

  // Stage 8: verify-in-place for action items -- confirm it's actually
  // needed, fix its title, or reject it (removes it -- for AI-suggested
  // items, especially backlog ones, that missed the mark entirely).
  $$(".action-verify-ok").forEach((b) => {
    b.onclick = async (e) => {
      e.stopPropagation();
      const row = b.closest(".dp-action");
      const actionId = row?.dataset.action;
      const projectId = row?.dataset.project || null;
      if (!actionId) return;
      const ok = await window.confirmAction?.(actionId, projectId);
      toast(ok ? "Confirmed" : "Could not confirm", ok ? "Thanks — marked as needed." : "Please try again.");
    };
  });
  $$(".action-verify-fix").forEach((b) => {
    b.onclick = async (e) => {
      e.stopPropagation();
      const row = b.closest(".dp-action");
      const actionId = row?.dataset.action;
      const projectId = row?.dataset.project || null;
      if (!actionId) return;
      openEditDialog({
        title: "Edit action item",
        help: "Fix the title and/or the AI-recommended due date for this action. Saved corrections are used to improve future extraction.",
        fields: [
          { id: "title", label: "Title", value: row?.dataset.title || "", rows: 2 },
          { id: "due_date", label: "Due date", value: row?.dataset.due || "", type: "date", required: false },
        ],
        onSave: async (values) => {
          const ok = await window.editActionTitle?.(actionId, { title: values.title, due_date: values.due_date });
          if (!ok) {
            toast("Could not save fix", "Please try again.");
            return false;
          }
          const project = projectId ? projectIndex[projectId] : null;
          const action = project?.actions?.find((a) => String(a.id) === String(actionId));
          if (action) {
            action.title = values.title;
            action.dueDate = values.due_date;
            action.due = formatDueLabel(values.due_date);
          }
          _syncBoardCard(actionId, {
            title: values.title,
            due: formatDueLabel(values.due_date),
            dueDate: values.due_date,
            overdue: computeOverdue(values.due_date, action?.done),
          });
          toast("Updated", "Action item corrected.");
          _refreshDrawer();
          return true;
        },
      });
    };
  });
  $$(".action-verify-reject").forEach((b) => {
    b.onclick = async (e) => {
      e.stopPropagation();
      const row = b.closest(".dp-action");
      const actionId = row?.dataset.action;
      const projectId = row?.dataset.project || null;
      if (!actionId) return;
      if (!confirm("Remove this action item? It wasn't actually needed.")) return;
      const ok = await window.rejectAction?.(actionId, projectId);
      if (!ok) {
        toast("Could not remove", "Please try again.");
        return;
      }
      const project = projectId ? projectIndex[projectId] : null;
      if (project) project.actions = (project.actions || []).filter((a) => String(a.id) !== String(actionId));
      _syncBoardCard(actionId, null);
      toast("Removed", "Marked as not needed.");
      _refreshDrawer();
    };
  });

  // Status filter for this project's action items -- toggles which of the
  // three states (matching the Task Board's columns) are shown.
  $$(".dp-action-filter .board-filter-chip").forEach((btn) => {
    btn.onclick = () => {
      const status = btn.dataset.status;
      if (actionStatusFilter.has(status)) actionStatusFilter.delete(status);
      else actionStatusFilter.add(status);
      _refreshDrawer();
    };
  });
  // "See action items by due dates" -- jumps to the Task Board pre-filtered
  // to just this project, where the due-date filter actually lives.
  $$(".dp-due-link").forEach((btn) => {
    btn.onclick = () => {
      if (btn.dataset.project) showProjectOnBoard(btn.dataset.project);
    };
  });
}

// Re-render from (now-updated) cached data after an edit, so a correction
// shows up immediately instead of only on next login.
function _refreshDrawer() {
  if (!_drawerContext) return;
  if (_drawerContext.kind === "item") openItem(_drawerContext.itemId);
  else if (_drawerContext.kind === "project") openProjectPage(_drawerContext.projectId);
}

function _threadBlock(items, heading) {
  return `<div class="dp-block"><h4>${escHtml(heading)}</h4><div class="thread">${items
    .map(
      (m) =>
        `<article class="thread-msg"><header><strong>${escHtml(m.sender || "Unknown")}</strong><time>${escHtml(m.when || "")}</time></header>${m.title ? `<div class="tm-subject">${escHtml(m.title)}</div>` : ""}<p>${escHtml(m.snippet || "")}</p>${m.source_url ? `<a class="link-btn" href="${m.source_url}" target="_blank" rel="noopener">Open original ↗</a>` : ""}</article>`,
    )
    .join("")}</div></div>`;
}

// Fallback-only: a real message with no project to attach to (rare -- most
// items resolve to a project and use the full-page view below instead).
function _openDrawer(title, eyebrow, bodyHtml) {
  const eb = $("#drawer .eyebrow");
  if (eb) eb.textContent = eyebrow;
  const tabs = $(".tabs");
  if (tabs) tabs.style.display = "none";
  $("#drawerTitle").textContent = title;
  $("#drawerBody").innerHTML = bodyHtml;
  $("#drawer").classList.add("open");
  $("#backdrop").classList.add("open");
  $("#drawer").setAttribute("aria-hidden", "false");
  _wireDrawerInteractions();
}

// The one full-page project view -- never a partial-width overlay with the
// grid still visible behind it.
function _openProjectPage(bodyHtml) {
  showView("projects");
  showProjectDetailView();
  const host = $("#projectDetailBody");
  if (host) host.innerHTML = bodyHtml;
  _wireDrawerInteractions();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// Click an item (Upcoming row, a timeline event's source link): if it has a
// project, show that project's full page with this specific thread; a rare
// project-less item falls back to the lightweight overlay.
function openItem(itemId) {
  const item = allItems.find((i) => String(i.id) === String(itemId));
  if (!item) return;
  const project = item.project_id ? projectIndex[item.project_id] : null;
  const thread = item.external_thread_id
    ? allItems.filter((i) => i.external_thread_id === item.external_thread_id)
    : [item];
  thread.sort((a, b) => new Date(a.occurred_at || 0) - new Date(b.occurred_at || 0));
  _drawerContext = { kind: "item", itemId, projectId: project?.id || null };
  if (project) {
    _ensureActionFilterFor(project.id);
    _openProjectPage(_projectBlocks(project) + _threadBlock(thread, "Conversation"));
  } else {
    _openDrawer(item.title || "(no subject)", "THREAD", _threadBlock(thread, "Conversation"));
  }
}

// Click a project: its full page -- verify/fix events, check off actions,
// browse the complete history.
function openProjectPage(projectId) {
  const project = projectIndex[projectId];
  if (!project) return;
  _ensureActionFilterFor(projectId);
  _drawerContext = { kind: "project", projectId };
  const items = allItems
    .filter((i) => i.project_id === projectId)
    .sort((a, b) => new Date(b.occurred_at || 0) - new Date(a.occurred_at || 0));
  _openProjectPage(_projectBlocks(project) + _threadBlock(items, "Related messages"));
}

// "Projects" nav view: every project, not just ones with recent activity --
// distinct from Overview (catch-up, time-scoped) and My actions (task-scoped).
function renderProjectsList() {
  const host = $("#projectsList");
  if (!host) return;
  const list = Object.values(projectIndex);
  if (!list.length) {
    host.innerHTML = '<p class="empty">No projects yet. Connect a source and catch up to build your first one.</p>';
    return;
  }
  host.innerHTML = list
    .map((p) => {
      const open = (p.actions || []).filter((a) => !a.done).length;
      const events = (p.events || []).length;
      return `<article class="project-tile clickable" data-project="${p.id}" style="--color:${p.color}">
        <div class="pt-symbol">${escHtml(p.symbol || "P")}</div>
        <div class="pt-body">
          <strong>${escHtml(p.name)}</strong>
          ${p.summary ? `<p>${escHtml(p.summary)}</p>` : ""}
          <small>${events} update${events === 1 ? "" : "s"} · ${open} open action${open === 1 ? "" : "s"}</small>
        </div>
      </article>`;
    })
    .join("");
  $$("#projectsList .project-tile").forEach((el) => {
    el.onclick = () => openProjectPage(el.dataset.project);
  });
}

window.setTimelineData = ({ all = [], projects = {} } = {}) => {
  allItems = all;
  projectIndex = projects || {};
  renderProjectsList();
};

// Populate the summary tiles + sidebar counts from real data.
window.setMetrics = (m = {}) => {
  const set = (id, val) => {
    const el = $("#" + id);
    if (el) el.textContent = val ?? 0;
  };
  set("statProjects", m.activeProjects);
  set("statDueWeek", m.dueThisWeek);
  set("statAttention", m.needAttention);
  set("statWaiting", m.waiting);
  set("statWeek", m.thisWeek);
  set("navProjectCount", m.activeProjects);
  set("navActionCount", m.openActions);
};

window.updateCurrentUserUI = (displayName) => {
  currentUserDisplayName = displayName || "You";
  currentUserInitials = currentUserDisplayName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase() || "ME";

  const welcomeName = document.querySelector("#welcomeUserName");
  if (welcomeName) welcomeName.textContent = currentUserDisplayName;

  projects.forEach((project) => {
    if (project.members.length) project.members[0] = currentUserInitials;
    project.events.forEach((event) => {
      if (event.person === "Current user + 4 teammates" || event.person.endsWith(" + 4 teammates")) {
        event.person = `${currentUserDisplayName} + 4 teammates`;
      }
    });
  });

  renderProjects($("#projectFilter")?.value || "all");
  if (activeProject) {
    activeProject = projects.find((project) => project.id === activeProject.id);
    renderDrawer();
  }
};

// Remove the previous account's in-memory and rendered dashboard data.
// Called by auth.js when a session ends or the account changes.
window.clearAccountData = () => {
  window.showOooRange = undefined;
  window.markCaughtUp = undefined;
  projects = [];
  actions = [];
  activity = [];
  activeProject = null;
  activeTab = "timeline";

  allItems = [];
  projectIndex = {};
  catchupGroups = [];
  catchupCheckpointMs = null;
  catchupCheckpointToMs = null;

  boardState = { in_progress: [], completed: [], backlog: [] };
  boardProjectFilter = new Set();
  boardDueFrom = null;
  boardDueTo = null;
  actionStatusFilter = new Set(["in_progress", "backlog"]);
  _actionFilterProjectId = null;
  _drawerContext = null;
  _editDialogOnSave = null;

  closeDrawer();

  for (const id of ["sourcesDialog", "editItemDialog"]) {
    const dialog = $("#" + id);
    if (dialog?.open) dialog.close();
  }

  for (const id of [
    "drawerBody", "projectDetailBody", "editItemFields",
    "projectGrid", "toasts"
  ]) {
    $("#" + id)?.replaceChildren();
  }

  for (const id of ["oooFrom", "oooTo", "boardDueFrom", "boardDueTo"]) {
    const input = $("#" + id);
    if (input) input.value = "";
  }

  window.setTimelineData({});
  window.setBoardData({});
  window.setDashboardData({});
  window.setCatchupData({});
  window.setMetrics({});
  window.setSourceConnections([]);
  window.updateCurrentUserUI("You");

  const defaults = {
    profileName: "Account",
    profileInitials: "--",
    profileTitle: "Sign in required",
    accountEmail: "",
    profileDisplayName: "",
    profileJobTitle: "",
  };

  for (const [id, value] of Object.entries(defaults)) {
    const node = $("#" + id);
    if (!node) continue;
    if ("value" in node) node.value = value;
    else node.textContent = value;
  }

  showProjectsGrid();
  showView("overview");
};

// Stage 7: start empty so no fabricated content shows; auth.js fills the
// dashboard from Supabase after sign-in via window.setDashboardData.
projects = [];
actions = [];
activity = [];
renderConnectors();
if ($("#connectPromptBtn"))
  $("#connectPromptBtn").onclick = () => $("#sourcesDialog").showModal();
$("#closeDrawer").onclick = $("#backdrop").onclick = closeDrawer;
if ($("#backToProjectsBtn")) $("#backToProjectsBtn").onclick = () => showProjectsGrid();
if ($("#catchMeUpBtn"))
  $("#catchMeUpBtn").onclick = () => window.markCaughtUp?.();
if ($("#oooShowBtn"))
  $("#oooShowBtn").onclick = () => {
    const from = $("#oooFrom")?.value;
    const to = $("#oooTo")?.value;
    if (!from || !to) {
      toast("Pick both dates", "Choose a from and to date to catch up on a specific range.");
      return;
    }
    window.showOooRange?.(from, to);
  };
$$(".tabs button").forEach(
  (b) =>
  (b.onclick = () => {
    $$(".tabs button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    activeTab = b.dataset.tab;
    renderDrawer();
  }),
);
if ($("#boardProjectFilterBtn"))
  $("#boardProjectFilterBtn").onclick = (e) => {
    e.stopPropagation();
    const menu = $("#boardProjectFilterMenu");
    if (!menu) return;
    const opening = menu.hidden;
    menu.hidden = !opening;
    $("#boardProjectFilterBtn").setAttribute("aria-expanded", String(opening));
  };
// Outside click closes the menu; a click inside it (a checkbox/label) does
// not, so multiple projects can be toggled without the menu snapping shut.
document.addEventListener("click", (e) => {
  const menu = $("#boardProjectFilterMenu");
  const dropdown = $("#boardProjectFilterDropdown");
  if (menu && !menu.hidden && dropdown && !dropdown.contains(e.target)) {
    menu.hidden = true;
    $("#boardProjectFilterBtn")?.setAttribute("aria-expanded", "false");
  }
});
if ($("#boardDueFrom"))
  $("#boardDueFrom").onchange = (e) => {
    boardDueFrom = e.target.value || null;
    renderBoard();
  };
if ($("#boardDueTo"))
  $("#boardDueTo").onchange = (e) => {
    boardDueTo = e.target.value || null;
    renderBoard();
  };
if ($("#boardFilterClear"))
  $("#boardFilterClear").onclick = () => {
    boardProjectFilter = new Set();
    boardDueFrom = null;
    boardDueTo = null;
    if ($("#boardDueFrom")) $("#boardDueFrom").value = "";
    if ($("#boardDueTo")) $("#boardDueTo").value = "";
    renderBoard();
  };
$("#connectAppsBtn").onclick = () => $("#sourcesDialog").showModal();
$("#manageSources").onclick = $("#sourcesNav").onclick = () =>
  $("#sourcesDialog").showModal();
$$(".close-dialog").forEach(
  (b) => (b.onclick = () => b.closest("dialog").close()),
);
$("#scanBtn").onclick = () => {
  $("#sourcesDialog").showModal();
};
document.onkeydown = (e) => {
  if (e.key === "Escape") closeDrawer();
};
$("#menuBtn").onclick = () => $("#sidebar").classList.toggle("open");

// Real view-switching (Overview = catch-up, Actions = board + upcoming,
// Projects = browse + edit), not scroll-to-anchor -- Overview stays
// laser-focused on "what changed" instead of every section living on one
// long page.
$$(".nav[data-target]").forEach(
  (b) =>
  (b.onclick = () => {
    const target = b.dataset.target;
    if (VIEW_IDS.includes(target)) {
      showView(target);
      // Always land on the grid from the nav, never resume wherever a
      // previous project page was left.
      if (target === "projects") showProjectsGrid();
    } else {
      $$(".nav").forEach((n) => n.classList.remove("active"));
      b.classList.add("active");
      $("#" + target)?.scrollIntoView({ behavior: "smooth" });
    }
    if (innerWidth < 800) $("#sidebar").classList.remove("open");
  }),
);
