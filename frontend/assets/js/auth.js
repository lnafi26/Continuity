// User Authentication Logic stays in the file
(() => {
  const config = window.SUPABASE_CONFIG;
  if (!config || config.url.includes("YOUR_PROJECT") || config.publishableKey.includes("REPLACE_ME")) {
    document.body.classList.remove("auth-pending");
    console.error("Complete supabase-config.js before using authentication.");
    return;
  }

  const db = window.supabase.createClient(config.url, config.publishableKey);
  window.supabaseDb = db;

  const element = (id) => document.getElementById(id);
  const loginDialog = element("loginDialog");
  const signupDialog = element("signupDialog");
  const accountDialog = element("accountDialog");
  let creatingAccount = false;

  function showMessage(message, isError = false) {
    const output = element("authMessage");
    output.textContent = message;
    output.classList.toggle("error-message", isError);
  }

  function clearSensitiveFields() {
    [
      "authPassword",
      "signupPassword",
      "signupPasswordConfirm",
      "currentPassword",
      "newPassword",
      "confirmNewPassword", "passwordReauthCode"
    ]
      .forEach((id) => {
        const input = element(id);
        if (input) input.value = "";
      });
    const loginPassword = element("authPassword");
    if (loginPassword) loginPassword.type = "password";
    const toggle = element("togglePassword");
    if (toggle) {
      toggle.textContent = "Show";
      toggle.setAttribute("aria-label", "Show password");
    }
  }

  function initials(name) {
    return (name || "User")
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase();
  }

  function authDisplayName(user) {
    const metadataName =
      user.user_metadata?.display_name ||
      user.user_metadata?.full_name ||
      user.user_metadata?.name;

    if (metadataName?.trim()) return metadataName.trim();

    const emailName = user.email?.split("@")[0] || "User";
    return emailName
      .replace(/[._-]+/g, " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  async function loadProfile(user) {
    // Update the UI immediately, even if the profile row is missing or unavailable.
    const fallbackName = authDisplayName(user);
    window.updateCurrentUserUI?.(fallbackName);
    element("profileInitials").textContent = initials(fallbackName);
    element("profileName").textContent = fallbackName;
    element("profileTitle").textContent = "Project manager";
    element("accountEmail").textContent = user.email || "";

    const { data, error } = await db
      .from("profiles")
      .select("display_name, job_title")
      .eq("id", user.id)
      .maybeSingle();

    if (error) {
      console.error("Unable to load profile; using Supabase Auth name instead.", error);
      return;
    }

    const displayName = data?.display_name?.trim() || fallbackName;
    const jobTitle = data?.job_title || "Project manager";
    element("profileInitials").textContent = initials(displayName);
    element("profileName").textContent = displayName;
    element("profileTitle").textContent = jobTitle;
    element("profileDisplayName").value = data?.display_name || fallbackName;
    element("profileJobTitle").value = data?.job_title || "";
    element("accountEmail").textContent = user.email;
    window.updateCurrentUserUI?.(displayName);
  }

  async function showAuthenticatedUser(session) {
    if (!session?.user) {
      clearSensitiveFields();
      if (!loginDialog.open) loginDialog.showModal();
      document.body.classList.remove("auth-pending");
      return;
    }

    if (loginDialog.open) loginDialog.close();
    document.body.classList.remove("auth-pending");
    await loadProfile(session.user);
    await loadSourceConnections(session.user);
    await loadProjectData(session.user);
  }

  async function loadSourceConnections(user) {
    const { data, error } = await db
      .from("source_connections")
      .select("provider, status, account_email, last_synced_at")
      .eq("user_id", user.id);
    if (error) {
      console.error("Unable to load source connections.", error);
      return;
    }
    window.setSourceConnections?.(data);
  }

  // Stage 7: load the user's real projects, timeline events, and actions from
  // Supabase and hand them to the dashboard renderer (window.setDashboardData).
  async function loadProjectData(user) {
    const esc = (value = "") => {
      const el = document.createElement("div");
      el.textContent = value;
      return el.innerHTML;
    };
    const cap = (s = "") => (s ? s[0].toUpperCase() + s.slice(1) : "");
    const fmtShort = (d) =>
      d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    const fmtDateTime = (ts) =>
      ts
        ? new Date(ts).toLocaleString(undefined, {
            month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
          })
        : "";
    const dayLabel = (dateStr) => {
      if (!dateStr) return { label: "No date", days: 9999 };
      const d = new Date(`${dateStr}T00:00:00`);
      const days = Math.ceil((d - new Date()) / 86400000);
      if (days < 0) return { label: "Overdue", days };
      if (days === 0) return { label: "Today", days };
      if (days === 1) return { label: "Tomorrow", days };
      return { label: fmtShort(d), days };
    };
    const relTime = (ts) => {
      const s = Math.max(1, Math.floor((Date.now() - new Date(ts).getTime()) / 1000));
      if (s < 60) return `${s} sec`;
      if (s < 3600) return `${Math.floor(s / 60)} min`;
      if (s < 86400) return `${Math.floor(s / 3600)} hr`;
      return `${Math.floor(s / 86400)} days`;
    };

    try {
      const [projRes, evRes, acRes, linkRes, itemRes, profileRes] = await Promise.all([
        db.from("projects").select("*").eq("user_id", user.id).order("updated_at", { ascending: false }),
        db.from("project_events").select("*").eq("user_id", user.id).order("event_date", { ascending: false }),
        db.from("project_actions").select("*").eq("user_id", user.id).order("due_date", { ascending: true, nullsFirst: false }),
        db.from("project_source_links").select("project_id, source_item_id, source_items(source_type)").eq("user_id", user.id),
        db.from("source_items").select("id, source_type, sender, title, occurred_at, external_thread_id, source_url, text_excerpt, include_in_grouping").eq("user_id", user.id).order("occurred_at", { ascending: false, nullsFirst: false }),
        db.from("profiles").select("last_catchup_at").eq("id", user.id).maybeSingle(),
      ]);
      const failed = [projRes, evRes, acRes, linkRes, itemRes].find((r) => r.error);
      if (failed) {
        console.error("Unable to load dashboard data.", failed.error);
        return;
      }
      if (profileRes.error) {
        console.error("Unable to load catch-up checkpoint; defaulting to a 7-day window.", profileRes.error);
      }

      const projectRows = projRes.data || [];
      const events = evRes.data || [];
      const actionRows = acRes.data || [];

      const sourcesByProject = {};
      for (const link of linkRes.data || []) {
        const type = link.source_items?.source_type;
        if (!type) continue;
        const chip = type === "google_calendar" ? "calendar" : type;
        (sourcesByProject[link.project_id] ||= new Set()).add(chip);
      }

      const nameById = {};
      const projects = projectRows.map((p) => {
        nameById[p.id] = p.name;
        const { label: deadline, days } = dayLabel(p.deadline);
        return {
          id: p.id,
          name: p.name,
          symbol: p.symbol || "P",
          summary: p.summary || "",
          deadline,
          days,
          progress: p.progress || 0,
          risk: p.risk || "",
          color: p.color || "#4263eb",
          soft: p.soft_color || "#eef2ff",
          members: p.members || [],
          sources: [...(sourcesByProject[p.id] || [])],
          events: events
            .filter((e) => e.project_id === p.id)
            .map((e) => ({
              id: e.id,
              date: fmtDateTime(e.event_date),
              type: cap(e.event_type),
              title: e.title,
              body: e.body || "",
              person: e.person || "",
              color: e.color || p.color,
            })),
          files: [],
        };
      });

      const actions = actionRows.map((a) => {
        const overdue =
          a.due_date && !a.completed &&
          new Date(`${a.due_date}T23:59:59`) < new Date();
        return {
          id: a.id,
          title: a.title,
          project: nameById[a.project_id] || "Project",
          projectId: a.project_id,
          due: dayLabel(a.due_date).label,
          overdue: !!overdue,
          done: !!a.completed,
          color: a.color || "#4263eb",
        };
      });

      const activity = events.slice(0, 8).map((e) => ({
        icon: e.event_type === "meeting" ? "31" : "M",
        text: `<b>${esc(e.person || "Someone")}</b> ${esc((e.title || "").slice(0, 120))}`,
        meta: `${esc(nameById[e.project_id] || "Project")} · ${cap(e.event_type)}`,
        time: relTime(e.event_date),
        color: e.color || "#4263eb",
        soft: "#eef2ff",
      }));

      // Per-project detail index (summary + events + actions) for the drawer.
      const projectsById = {};
      for (const p of projectRows) {
        projectsById[p.id] = {
          id: p.id,
          name: p.name,
          symbol: p.symbol || "P",
          summary: p.summary || "",
          color: p.color || "#4263eb",
          events: [],
          actions: [],
        };
      }
      // Lets the UI show, right next to an event, when its AI-interpreted
      // date diverges from the real timestamp of the message it came from --
      // instead of leaving that only discoverable by cross-referencing
      // "Related messages" by hand.
      const itemById = {};
      for (const it of itemRes.data || []) itemById[it.id] = it;

      for (const e of events) {
        const p = projectsById[e.project_id];
        if (!p) continue;
        const sourceItem = e.source_item_id ? itemById[e.source_item_id] : null;
        p.events.push({
          id: e.id,
          date: fmtDateTime(e.event_date),
          dateMs: e.event_date ? new Date(e.event_date).getTime() : null,
          type: cap(e.event_type),
          title: e.title,
          body: e.body || "",
          person: e.person || "",
          source_item_id: e.source_item_id || null,
          sourceWhen: sourceItem?.occurred_at ? fmtDateTime(sourceItem.occurred_at) : null,
          sourceWhenMs: sourceItem?.occurred_at ? new Date(sourceItem.occurred_at).getTime() : null,
        });
      }
      for (const a of actionRows) {
        const p = projectsById[a.project_id];
        if (!p) continue;
        const rawStatus = a.status || (a.completed ? "completed" : "not_started");
        p.actions.push({
          id: a.id,
          title: a.title,
          due: dayLabel(a.due_date).label,
          dueDate: a.due_date || "",
          done: !!a.completed,
          status: rawStatus === "completed" ? "completed" : "in_progress",
          backlog: !!a.backlog,
          assignee: a.assignee || "",
        });
      }

      // Build the timeline items (all = for full threads, feed = kept items).
      const itemProjectId = {};
      for (const link of linkRes.data || []) {
        if (link.source_item_id && !itemProjectId[link.source_item_id]) {
          itemProjectId[link.source_item_id] = link.project_id;
        }
      }
      const all = (itemRes.data || []).map((it) => {
        const pid = itemProjectId[it.id] || null;
        return {
          id: it.id,
          source_type: it.source_type,
          sender: it.sender || "Unknown",
          title: it.title || "",
          occurred_at: it.occurred_at,
          external_thread_id: it.external_thread_id,
          source_url: it.source_url,
          when: fmtDateTime(it.occurred_at),
          snippet: (it.text_excerpt || "").slice(0, 240),
          project_id: pid,
          project: (pid && nameById[pid]) || "",
          include: it.include_in_grouping,
        };
      });
      const feed = all.filter((it) => it.include);
      window.setTimelineData?.({ feed, all, projects: projectsById });

      // Day helpers.
      const nowMs = Date.now();
      const startOfDay = (d) => {
        const x = new Date(d);
        x.setHours(0, 0, 0, 0);
        return x.getTime();
      };
      const todayK = startOfDay(new Date());
      const pastDayLabel = (k) => {
        const diff = (todayK - k) / 86400000;
        if (diff === 0) return "Today";
        if (diff === 1) return "Yesterday";
        return new Date(k).toLocaleDateString(undefined, { month: "short", day: "numeric" }).toUpperCase();
      };
      const futureDayLabel = (d) => {
        const diff = (startOfDay(d) - todayK) / 86400000;
        if (diff === 0) return "Today";
        if (diff === 1) return "Tomorrow";
        return new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric" });
      };

      // Needs your attention: projects that have open actions.
      const openByProject = {};
      for (const a of actionRows) {
        if (!a.completed && a.project_id) (openByProject[a.project_id] ||= []).push(a);
      }
      const latestEvent = {};
      for (const e of events) {
        if (e.project_id && !latestEvent[e.project_id]) latestEvent[e.project_id] = e;
      }
      const attention = Object.keys(openByProject)
        .map((pid) => {
          const acts = openByProject[pid]
            .slice()
            .sort((a, b) => ((a.due_date || "9999") < (b.due_date || "9999") ? -1 : 1));
          const overdue = acts.filter(
            (a) => a.due_date && new Date(`${a.due_date}T23:59:59`) < new Date(),
          ).length;
          const top = acts[0];
          const ev = latestEvent[pid];
          const status = overdue
            ? `${overdue} overdue action${overdue > 1 ? "s" : ""}`
            : acts.length > 1
              ? `${acts.length} unresolved actions`
              : ev ? ev.title : "Open follow-up";
          const suggested = top
            ? `${top.title}${top.due_date ? " · " + dayLabel(top.due_date).label : ""}`
            : "";
          const proj = projectRows.find((p) => p.id === pid);
          return {
            id: pid,
            project: (proj && proj.name) || "Project",
            status,
            suggested,
            color: (proj && proj.color) || "#4263eb",
            sort: overdue ? 0 : 1,
          };
        })
        .sort((a, b) => a.sort - b.sort)
        .slice(0, 6);

      // Recent project activity: kept items grouped by day, newest first.
      const groups = [];
      const seenDay = {};
      for (const it of feed) {
        if (!it.occurred_at) continue;
        const k = startOfDay(it.occurred_at);
        let g = seenDay[k];
        if (!g) {
          g = { label: pastDayLabel(k), items: [] };
          seenDay[k] = g;
          groups.push(g);
        }
        if (g.items.length < 6) {
          g.items.push({
            id: it.id,
            project: it.project || "Unsorted",
            title: it.title || "(no subject)",
            source_type: it.source_type,
          });
        }
      }
      const activityDays = groups.slice(0, 6);

      // Recent / Upcoming: future-dated items (mostly calendar), soonest first.
      const upcoming = all
        .filter((it) => it.occurred_at && new Date(it.occurred_at).getTime() >= nowMs)
        .sort((a, b) => new Date(a.occurred_at) - new Date(b.occurred_at))
        .slice(0, 6)
        .map((it) => ({
          id: it.id,
          when: futureDayLabel(it.occurred_at),
          title: it.title || "(no subject)",
          source_type: it.source_type,
        }));

      window.setDashboardData?.({
        attention,
        activityDays,
        upcoming,
      });

      // ---- Stage 7: catch-up digest (checkpoint-anchored) ----
      // Decisions/differing-opinion events rank first, then deadlines/meetings,
      // then everything else, per project -- no new extraction, a filtered read
      // over events Stage 6 already produced.
      const rankScore = (e) =>
        e.event_type === "decision" ? 0
          : (e.event_type === "deadline" || e.event_type === "meeting") ? 1
          : 2;
      function buildDigest(fromMs, toMs) {
        const missed = events.filter(
          (e) => e.project_id && e.event_date &&
            new Date(e.event_date).getTime() >= fromMs &&
            new Date(e.event_date).getTime() <= toMs,
        );
        const byProject = {};
        for (const e of missed) (byProject[e.project_id] ||= []).push(e);
        return Object.keys(byProject)
          .map((pid) => {
            // Every missed item is kept -- no truncation. The 5-at-a-time cap
            // from "What users can do" applies to project groups, not items;
            // the panel scrolls (dashboard.js) rather than dropping data.
            const raw = byProject[pid]
              .slice()
              .sort((a, b) => rankScore(a) - rankScore(b) || new Date(b.event_date) - new Date(a.event_date));
            const proj = projectRows.find((p) => p.id === pid);
            const mostRecentMs = Math.max(...raw.map((e) => new Date(e.event_date).getTime()));
            return {
              id: pid,
              project: nameById[pid] || "Project",
              color: (proj && proj.color) || "#4263eb",
              mostRecentMs,
              // The actual time of the most recent decision/meeting/message in
              // this project -- shown on the timeline rail, and what drives the
              // most-recent-to-least-recent card order below.
              when: fmtDateTime(mostRecentMs),
              // Stage 7: precomputed by backend/digest (Haiku 4.5), never
              // generated live here. Null until the backend job has run for
              // this project -- dashboard.js falls back to a plain headline.
              summary: proj?.catchup_summary || null,
              // Tag signal (Tasks): a NEW open action item since the
              // checkpoint -- scoped to the digest window, not "any open
              // action ever" (which fires on almost every project and isn't
              // actually "what changed"). Shared taxonomy with the board:
              // Tasks / Meetings / Decisions / Issue-Blockers / Update-Change.
              hasTask: actionRows.some(
                (a) => a.project_id === pid && !a.completed && a.created_at &&
                  new Date(a.created_at).getTime() >= fromMs &&
                  new Date(a.created_at).getTime() <= toMs,
              ),
              items: raw.map((e) => ({
                id: e.id,
                title: e.title,
                body: e.body || "",
                person: e.person || "",
                type: cap(e.event_type),
                when: fmtDateTime(e.event_date),
                requires_response: e.requires_response,
                source_item_id: e.source_item_id,
              })),
            };
          })
          // Project groups most-recent-activity-first, per "list from most
          // recent to less recent" in "What users can do".
          .sort((a, b) => b.mostRecentMs - a.mostRecentMs);
      }

      // Checkpoint: stored profiles.last_catchup_at, or a 7-day window on first
      // use (Supabase does not expose a reliable "previous" sign-in timestamp
      // client-side, so a bounded default window stands in for it).
      const storedCheckpoint = profileRes.data?.last_catchup_at || null;
      const checkpoint = storedCheckpoint || new Date(nowMs - 7 * 86400000).toISOString();
      window.setCatchupData?.({
        checkpointLabel: fmtDateTime(checkpoint),
        checkpointISO: checkpoint,
        // Upper bound = now for the default digest -- there's nothing beyond
        // "now" to show anyway, so this mostly matters for the OOO override
        // below, but every call sets both ends for consistency.
        checkpointToISO: new Date(nowMs).toISOString(),
        groups: buildDigest(new Date(checkpoint).getTime(), nowMs),
      });

      // OOO override: re-filter already-loaded data client-side; does not move
      // the stored checkpoint (only "Catch Me Up" / markCaughtUp does that).
      window.showOooRange = (fromIso, toIso) => {
        if (!fromIso || !toIso) return;
        const fromMs = new Date(`${fromIso}T00:00:00`).getTime();
        const toMs = new Date(`${toIso}T23:59:59`).getTime();
        window.setCatchupData?.({
          checkpointLabel: `${fromIso} to ${toIso}`,
          // A real range (not the stored checkpoint) -- the project page's
          // "since your last catch-up" split uses whichever window is
          // currently active, override or not, with BOTH ends respected
          // (a bare lower bound would leak in everything after "to" too).
          checkpointISO: new Date(fromMs).toISOString(),
          checkpointToISO: new Date(toMs).toISOString(),
          groups: buildDigest(fromMs, toMs),
        });
      };

      // Stage 8 mark_caught_up: advances the checkpoint to now, clearing the
      // digest (nothing "missed" as of the moment it's viewed).
      window.markCaughtUp = async () => {
        const nowIso = new Date().toISOString();
        const { error } = await db.from("profiles").upsert({
          id: user.id, last_catchup_at: nowIso, updated_at: nowIso,
        });
        if (error) {
          console.error("Failed to advance catch-up checkpoint.", error);
          window.toast?.("Could not update checkpoint", error.message);
          return;
        }
        window.setCatchupData?.({
          checkpointLabel: fmtDateTime(nowIso), checkpointISO: nowIso,
          checkpointToISO: nowIso, groups: [],
        });
        window.toast?.("You're all caught up", "We'll show what's new since now next time.");
      };

      // ---- Stage 7: AI-inferred action board (In Progress / Completed /
      // Backlog) -- a pure read grouping over Stage 6 output. No dedicated
      // "not started" column: Stage 6's default status folds into In
      // Progress here since the board no longer distinguishes the two.
      const board = { in_progress: [], completed: [], backlog: [] };
      for (const a of actionRows) {
        const rawStatus = a.status || (a.completed ? "completed" : "not_started");
        const status = rawStatus === "completed" ? "completed" : "in_progress";
        const card = {
          id: a.id,
          title: a.title,
          project: nameById[a.project_id] || "Project",
          projectId: a.project_id,
          due: dayLabel(a.due_date).label,
          dueDate: a.due_date || "",
          overdue: !!(a.due_date && !a.completed && new Date(`${a.due_date}T23:59:59`) < new Date()),
          color: a.color || "#4263eb",
          status,
          backlog: !!a.backlog,
        };
        (card.backlog ? board.backlog : board[status]).push(card);
      }
      window.setBoardData?.(board);

      // Summary metrics for the tiles.
      const linkedProjectIds = new Set(
        (linkRes.data || []).map((l) => l.project_id).filter(Boolean),
      );
      const activeProjects = linkedProjectIds.size || projectRows.length;
      const needAttention = Object.keys(openByProject).length;
      const openActions = actionRows.filter((a) => !a.completed).length;
      // Real signal now that Stage 6 tags requires_response, replacing the old
      // activeProjects-minus-needAttention placeholder.
      const waiting = events.filter((e) => e.requires_response === true).length;
      const weekAgo = nowMs - 7 * 86400000;
      const thisWeek = all.filter(
        (it) => it.occurred_at && new Date(it.occurred_at).getTime() >= weekAgo,
      ).length;
      const dueThisWeek = actionRows.filter(
        (a) =>
          !a.completed && a.due_date &&
          new Date(`${a.due_date}T23:59:59`) >= new Date() &&
          new Date(`${a.due_date}T00:00:00`).getTime() <= nowMs + 7 * 86400000,
      ).length;
      window.setMetrics?.({ activeProjects, dueThisWeek, needAttention, waiting, thisWeek, openActions });
    } catch (err) {
      console.error("Failed to load project data.", err);
    }
  }

  // Stage 8: board drag-and-drop is a correction (edit_action), not the
  // primary interaction -- it overrides the AI-inferred status/backlog and
  // logs to user_corrections for evaluation, same as any other edit.
  window.updateActionStatus = async (actionId, status, backlog, projectId) => {
    const { data: { user } } = await db.auth.getUser();
    if (!user) return false;
    const { data: prevRows } = await db
      .from("project_actions")
      .select("status, backlog, completed")
      .eq("id", actionId)
      .limit(1);
    const prev = prevRows && prevRows[0];
    const completed = status === "completed";
    const { error } = await db
      .from("project_actions")
      .update({ status, backlog: !!backlog, completed, user_edited: true, updated_at: new Date().toISOString() })
      .eq("id", actionId);
    if (error) {
      console.error("Failed to update action status.", error);
      return false;
    }
    await db.from("user_corrections").insert({
      user_id: user.id,
      project_id: projectId || null,
      correction_type: "edit_action",
      previous_value: prev ? { status: prev.status, backlog: prev.backlog, completed: prev.completed } : null,
      corrected_value: { status, backlog: !!backlog, completed },
    });
    return true;
  };

  // Stage 8: verify-in-place "✓ looks right" -- confirm_match against the
  // source item, presented inline in the digest instead of a review screen.
  window.confirmDigestItem = async (sourceItemId, projectId) => {
    const { data: { user } } = await db.auth.getUser();
    if (!user) return false;
    const { error } = await db.from("user_corrections").insert({
      user_id: user.id,
      source_item_id: sourceItemId || null,
      project_id: projectId || null,
      correction_type: "confirm_match",
    });
    if (error) {
      console.error("Failed to record confirmation.", error);
      return false;
    }
    return true;
  };

  // Stage 8: verify-in-place "✎ fix" -- edit_event, sets user_edited so
  // re-extraction will not silently overwrite the correction. Covers both
  // the title and the AI-generated summary (body) shown under it -- either
  // can be omitted (undefined) to leave that column untouched.
  window.editDigestEvent = async (eventId, { title, body } = {}) => {
    const { data: { user } } = await db.auth.getUser();
    if (!user) return false;
    const { data: prevRows } = await db
      .from("project_events")
      .select("title, body")
      .eq("id", eventId)
      .limit(1);
    const prev = prevRows && prevRows[0];
    const updates = { user_edited: true, updated_at: new Date().toISOString() };
    if (title != null) updates.title = title;
    if (body != null) updates.body = body;
    const { error } = await db
      .from("project_events")
      .update(updates)
      .eq("id", eventId);
    if (error) {
      console.error("Failed to edit event.", error);
      return false;
    }
    await db.from("user_corrections").insert({
      user_id: user.id,
      correction_type: "edit_event",
      previous_value: prev ? { title: prev.title, body: prev.body } : null,
      corrected_value: { title, body },
    });
    return true;
  };

  // Stage 8: verify-in-place for action items -- "✓ looks right" / "✎ fix
  // the title", alongside the existing checkbox (which only ever meant
  // "done or not", never "is this task actually described correctly").
  window.confirmAction = async (actionId, projectId) => {
    const { data: { user } } = await db.auth.getUser();
    if (!user) return false;
    const { error } = await db.from("user_corrections").insert({
      user_id: user.id,
      project_id: projectId || null,
      correction_type: "confirm_match",
      corrected_value: { action_id: actionId },
    });
    if (error) {
      console.error("Failed to record confirmation.", error);
      return false;
    }
    return true;
  };

  // Edits the title and/or the recommended due date the AI assigned to an
  // action item -- either can be omitted (undefined) to leave that column
  // untouched. An empty string for due_date clears it (no date recommended).
  window.editActionTitle = async (actionId, { title, due_date } = {}) => {
    const { data: { user } } = await db.auth.getUser();
    if (!user) return false;
    const { data: prevRows } = await db
      .from("project_actions")
      .select("title, due_date")
      .eq("id", actionId)
      .limit(1);
    const prev = prevRows && prevRows[0];
    const updates = { user_edited: true, updated_at: new Date().toISOString() };
    if (title != null) updates.title = title;
    if (due_date != null) updates.due_date = due_date || null;
    const { error } = await db
      .from("project_actions")
      .update(updates)
      .eq("id", actionId);
    if (error) {
      console.error("Failed to edit action.", error);
      return false;
    }
    await db.from("user_corrections").insert({
      user_id: user.id,
      correction_type: "edit_action",
      previous_value: prev ? { title: prev.title, due_date: prev.due_date } : null,
      corrected_value: { title, due_date },
    });
    return true;
  };

  // Stage 8: verify-in-place for the project's own summary (Stage 5,
  // Sonnet-generated) -- nothing covered this before; only individual
  // events/actions were correctable, not the project description itself.
  // Stage 8: reject_match on an action item -- answers "is this actually
  // needed", not "is it done yet" (that's the checkbox / updateActionStatus).
  // No `dismissed` column exists on project_actions, so a reject removes the
  // row outright; the full prior row is captured on the correction first so
  // nothing the model produced is silently lost from the evaluation record.
  window.rejectAction = async (actionId, projectId) => {
    const { data: { user } } = await db.auth.getUser();
    if (!user) return false;
    const { data: prevRows } = await db
      .from("project_actions")
      .select("title, assignee, due_date, status, backlog, completed")
      .eq("id", actionId)
      .limit(1);
    const prev = prevRows && prevRows[0];
    const { error } = await db.from("project_actions").delete().eq("id", actionId);
    if (error) {
      console.error("Failed to reject action.", error);
      return false;
    }
    await db.from("user_corrections").insert({
      user_id: user.id,
      project_id: projectId || null,
      correction_type: "reject_match",
      previous_value: prev || null,
    });
    return true;
  };

  window.confirmProjectSummary = async (projectId) => {
    const { data: { user } } = await db.auth.getUser();
    if (!user) return false;
    const { error } = await db.from("user_corrections").insert({
      user_id: user.id,
      project_id: projectId,
      correction_type: "confirm_match",
    });
    if (error) {
      console.error("Failed to record confirmation.", error);
      return false;
    }
    return true;
  };

  window.editProjectSummary = async (projectId, newSummary) => {
    const { data: { user } } = await db.auth.getUser();
    if (!user) return false;
    const { data: prevRows } = await db
      .from("projects")
      .select("summary")
      .eq("id", projectId)
      .limit(1);
    const prev = prevRows && prevRows[0];
    const { error } = await db
      .from("projects")
      .update({ summary: newSummary, updated_at: new Date().toISOString() })
      .eq("id", projectId);
    if (error) {
      console.error("Failed to edit project summary.", error);
      return false;
    }
    await db.from("user_corrections").insert({
      user_id: user.id,
      project_id: projectId,
      correction_type: "edit_project",
      previous_value: prev ? { summary: prev.summary } : null,
      corrected_value: { summary: newSummary },
    });
    return true;
  };

  window.startSourceConnection = async (provider) => {
    const { data: { session } } = await db.auth.getSession();
    if (!session) throw new Error("Sign in before connecting a source.");

    const oauthBaseUrl = config.oauthBaseUrl;
    if (!oauthBaseUrl) {
      throw new Error("Set oauthBaseUrl in supabase-config.js to the Stage 0 OAuth server.");
    }

    // Authenticated POST binds Google OAuth state to the verified Supabase user.
    // Never put bearer tokens or user IDs into OAuth initiation URLs.
    const response = await fetch(new URL("/auth/google/start", oauthBaseUrl), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${session.access_token}`,
      },
      body: JSON.stringify({
        providers: provider,
        return_to: `${window.location.origin}/`,
      }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.authorization_url) {
      throw new Error(result.error || "Unable to begin Google authorization.");
    }
    window.location.assign(result.authorization_url);
  };



  // "Scan for updates" -- runs the real Stages 1-7 pipeline (sync through
  // digest summarize) for the signed-in user on the same local Stage 0
  // server, then reloads the dashboard from Supabase so the result shows up
  // without a page refresh. Synchronous: the request blocks for as long as
  // the pipeline takes (LLM calls included), same tradeoff as running it
  // from the terminal, just from one button instead of eight commands.
  window.runPipelineScan = async () => {
    const { data: { session } } = await db.auth.getSession();
    if (!session) throw new Error("Sign in before scanning for updates.");

    const oauthBaseUrl = config.oauthBaseUrl;
    if (!oauthBaseUrl) {
      throw new Error("Set oauthBaseUrl in supabase-config.js to the Stage 0 OAuth server.");
    }

    const res = await fetch(new URL("/pipeline/run", oauthBaseUrl), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${session.access_token}`,
      },
      body: JSON.stringify({}),
    });
    const result = await res.json().catch(() => ({ ok: false, steps: [], error: "Bad response from pipeline server." }));

    // Refresh regardless of per-stage failures -- earlier stages (e.g. a
    // stale connection) failing doesn't mean nothing new is worth showing;
    // later stages report their own real state either way.
    await loadProjectData(session.user);
    return result;
  };

  element("loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = element("authEmail").value.trim();
    const password = element("authPassword").value;
    showMessage("Working…");

    const result = await db.auth.signInWithPassword({ email, password });
    clearSensitiveFields();

    if (result.error) {
      showMessage(result.error.message, true);
      return;
    }

    showMessage("");
    await showAuthenticatedUser(result.data.session);
  });

  function openLogin() {
    clearSensitiveFields();
    if (signupDialog.open) signupDialog.close();
    element("signupFormView").hidden = false;
    element("signupSuccess").hidden = true;
    element("signupForm").reset();
    element("signupMessage").textContent = "";
    if (!loginDialog.open) loginDialog.showModal();
  }

  element("openSignup").addEventListener("click", () => {
    loginDialog.close();
    signupDialog.showModal();
    element("signupName").focus();
  });
  element("backToLogin").addEventListener("click", openLogin);
  element("returnToLogin").addEventListener("click", openLogin);

  element("signupForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = element("signupName").value.trim();
    const email = element("signupEmail").value.trim();
    const password = element("signupPassword").value;
    const confirmation = element("signupPasswordConfirm").value;
    const message = element("signupMessage");

    if (password.length < 15) {
      message.textContent = "Use a password of at least 15 characters.";
      message.classList.add("error-message");
      return;
    }

    if (password !== confirmation) {
      message.textContent = "Passwords do not match.";
      message.classList.add("error-message");
      return;
    }

    creatingAccount = true;
    message.classList.remove("error-message");
    message.textContent = "Creating your account…";
    const { data, error } = await db.auth.signUp({
      email,
      password,
      options: { data: { display_name: name } },
    });
    clearSensitiveFields();

    if (error) {
      creatingAccount = false;
      message.textContent = error.message;
      message.classList.add("error-message");
      return;
    }

    if (data.session) await db.auth.signOut();
    creatingAccount = false;
    element("signupFormView").hidden = true;
    element("signupSuccess").hidden = false;
    element("signupSuccessText").textContent = data.session
      ? "You will be redirected back to the sign-in page…"
      : "Check your email to verify the account. You will be redirected back to sign in…";
    setTimeout(openLogin, 3500);
  });

  element("profileForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const { data: { user } } = await db.auth.getUser();
    if (!user) return;

    const { error } = await db.from("profiles").upsert({
      id: user.id,
      display_name: element("profileDisplayName").value.trim(),
      job_title: element("profileJobTitle").value.trim(),
      updated_at: new Date().toISOString(),
    });

    if (error) return alert(error.message);
    await loadProfile(user);
    accountDialog.close();
  });


  const passwordReauthField = element("passwordReauthField");
  const passwordReauthCode = element("passwordReauthCode");
  const sendPasswordReauth = element("sendPasswordReauth");

  let passwordReauthSent = false;

  function passwordFeedback(message, isError = false) {
    const output = element("passwordMessage");
    output.textContent = message;
    output.classList.toggle("error-message", isError);
  }

  sendPasswordReauth.addEventListener("click", async () => {
    if (sendPasswordReauth.disabled) return;

    sendPasswordReauth.disabled = true;
    passwordFeedback("Sending verification code…");

    try {
      const { error } = await db.auth.reauthenticate();

      if (error) {
        passwordFeedback(
          "Unable to send verification code. Please wait before retrying.",
          true
        );
        return;
      }

      passwordReauthSent = true;
      passwordReauthCode.value = "";
      passwordReauthField.hidden = false;

      passwordFeedback(
        "Verification code sent. Check your email, then enter the code."
      );
    } catch {
      passwordFeedback(
        "Unable to contact the authentication service.",
        true
      );
    } finally {
      sendPasswordReauth.disabled = false;
    }
  });

  element("passwordForm").addEventListener("submit", async (event) => {
    event.preventDefault();

    const form = element("passwordForm");
    const button = form.querySelector('button[type="submit"]');

    if (button.disabled) return;

    const currentPassword = element("currentPassword").value;
    const newPassword = element("newPassword").value;
    const confirmation = element("confirmNewPassword").value;
    const code = passwordReauthCode.value.trim();

    if (!currentPassword) {
      passwordFeedback("Enter your current password.", true);
      return;
    }

    if (newPassword.length < 15) {
      passwordFeedback(
        "Use a new password of at least 15 characters.",
        true
      );
      return;
    }

    if (newPassword !== confirmation) {
      passwordFeedback("The new passwords do not match.", true);
      return;
    }

    if (newPassword === currentPassword) {
      passwordFeedback(
        "Choose a password different from your current one.",
        true
      );
      return;
    }

    if (passwordReauthSent && !/^\d{6,10}$/.test(code)) {
      passwordFeedback("Enter a valid email verification code.", true);
      return;
    }

    const attributes = {
      password: newPassword,
      current_password: currentPassword
    };

    if (passwordReauthSent) {
      attributes.nonce = code;
    }

    button.disabled = true;
    passwordFeedback("Updating your password…");

    try {
      const { error } = await db.auth.updateUser(attributes);

      if (error) {
        if (error.code === "reauthentication_needed") {
          passwordReauthSent = false;
          passwordReauthField.hidden = true;
          sendPasswordReauth.hidden = false;

          passwordFeedback(
            "Additional verification is required. Select Send verification code.",
            true
          );
        } else if (error.code === "reauthentication_not_valid") {
          sendPasswordReauth.hidden = false;

          passwordFeedback(
            "The verification code is invalid or expired. Try again or request another code.",
            true
          );
        } else {
          passwordFeedback(
            "Password change unsuccessful. Check your current password and try again.",
            true
          );
        }
        return;
      }

      passwordReauthSent = false;
      passwordReauthField.hidden = true;
      sendPasswordReauth.hidden = true;

      passwordFeedback("Password updated successfully.");
    } catch {
      passwordFeedback(
        "Unable to update your password. Please try again.",
        true
      );
    } finally {
      clearSensitiveFields();
      button.disabled = false;
    }
  });

  element("togglePassword").addEventListener("click", () => {
    const input = element("authPassword");
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    element("togglePassword").textContent = show ? "Hide" : "Show";
    element("togglePassword").setAttribute("aria-label", `${show ? "Hide" : "Show"} password`);
  });

  element("forgotPassword").addEventListener("click", async () => {
    const email = element("authEmail").value.trim();
    if (!email) {
      showMessage("Enter your email address first, then select Forgot your password.", true);
      element("authEmail").focus();
      return;
    }
    showMessage("Sending password reset email…");
    const { error } = await db.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password.html`,
    });
    showMessage(error ? error.message : "Password reset email sent. Check your inbox.", Boolean(error));
  });

  element("profileButton").addEventListener("click", () => accountDialog.showModal());
  element("closeAccount").addEventListener("click", () => accountDialog.close());

  // Clear credentials and temporary verification state whenever
  // account settings closes, including via the Escape key.
  accountDialog.addEventListener("close", () => {
    clearSensitiveFields();

    passwordReauthSent = false;
    passwordReauthField.hidden = true;
    sendPasswordReauth.hidden = true;
    sendPasswordReauth.disabled = false;

    passwordFeedback("");
  });

  element("signOutButton").addEventListener("click", async () => {
    clearSensitiveFields();
    await db.auth.signOut();
    accountDialog.close();
    loginDialog.showModal();
  });

  db.auth.onAuthStateChange((_event, session) => {
    if (creatingAccount) return;
    setTimeout(() => showAuthenticatedUser(session).catch(console.error), 0);
  });

  db.auth.getSession().then(({ data }) => showAuthenticatedUser(data.session)).catch(console.error);

  // When the Stage 0 OAuth server redirects back with ?connected=<providers>,
  // confirm it and clean the URL. loadSourceConnections (run on session load)
  // refreshes the "Connected" state from the source_connections table.
  const connectedParam = new URLSearchParams(window.location.search).get("connected");
  if (connectedParam) {
    const names = connectedParam.replace(/_/g, " ");
    window.toast?.("Source connected", `${names} is now importing (read-only).`);
    const cleanUrl = window.location.origin + window.location.pathname;
    window.history.replaceState({}, document.title, cleanUrl);
  }
})();
