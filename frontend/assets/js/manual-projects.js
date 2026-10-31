/* Continuity manual project records: explicit user actions only.
 * This uses existing projects/project_events/project_actions tables.
 * It is NOT the B4 versioned-memory persistence implementation.
 */
(function () {
  "use strict";

  function bounded(value, label, max, required = true) {
    const text = typeof value === "string" ? value.trim() : "";
    if ((required && !text) || text.length > max) {
      throw new Error(`${label} must be ${required ? `1–${max}` : `at most ${max}`} characters.`);
    }
    return text;
  }

  function requiredId(value, label) {
    return bounded(value, label, 80);
  }

  function dateOnly(value) {
    if (!value) return null;
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      throw new Error("Use a valid YYYY-MM-DD due date.");
    }
    const [year, month, day] = value.split("-").map(Number);
    const parsed = new Date(Date.UTC(year, month - 1, day));
    if (parsed.getUTCFullYear() !== year || parsed.getUTCMonth() !== month - 1 || parsed.getUTCDate() !== day) {
      throw new Error("Invalid calendar date.");
    }
    return value;
  }

  async function createProject(db, userId, fields) {
    requiredId(userId, "User");
    const name = bounded(fields.name, "Project name", 120);
    const summary = bounded(fields.summary, "Summary", 2000, false);
    const { data, error } = await db.from("projects").insert({
      user_id: userId,
      name,
      summary,
      symbol: name.slice(0, 1).toUpperCase(),
      origin: "user",
      category: "project",
    }).select("id").single();
    if (error || !data?.id) throw new Error(error?.message || "Project could not be saved.");
    return data.id;
  }

  async function assertOwnedProject(db, userId, projectId) {
    requiredId(userId, "User");
    requiredId(projectId, "Project");
    const { data, error } = await db.from("projects")
      .select("id").eq("id", projectId).eq("user_id", userId).maybeSingle();
    if (error || !data?.id) throw new Error("Project unavailable or not owned by this account.");
  }

  async function addDecision(db, userId, projectId, fields) {
    const title = bounded(fields.title, "Decision title", 200);
    const body = bounded(fields.body, "Decision details", 5000, false);
    await assertOwnedProject(db, userId, projectId);
    const { error } = await db.from("project_events").insert({
      user_id: userId,
      project_id: projectId,
      event_type: "decision",
      title,
      body,
      person: "You",
      user_edited: true,
    });
    if (error) throw new Error(error.message || "Decision could not be saved.");
  }

  async function addTask(db, userId, projectId, fields) {
    const title = bounded(fields.title, "Task title", 200);
    const due_date = dateOnly(fields.due_date || "");
    await assertOwnedProject(db, userId, projectId);
    const { error } = await db.from("project_actions").insert({
      user_id: userId,
      project_id: projectId,
      title,
      due_date,
      status: "not_started",
      completed: false,
      user_edited: true,
    });
    if (error) throw new Error(error.message || "Task could not be saved.");
  }

  const api = { createProject, addDecision, addTask, dateOnly };
  if (typeof module !== "undefined" && module.exports) module.exports = api;

  if (typeof window === "undefined" || typeof document === "undefined") return;
  window.ContinuityManualProjects = api;

  function install() {
    const form = document.getElementById("manualEntryForm");
    const dialog = document.getElementById("manualEntryDialog");
    const newProject = document.getElementById("manualNewProject");
    if (!form || !dialog || !newProject) return;
    const input = (id) => document.getElementById(id);
    let mode = "project";
    let projectId = null;
    let saving = false;

    function open(nextMode, id = null) {
      if (saving || dialog.open) return;
      mode = nextMode;
      projectId = id;
      form.reset();
      input("manualEntryStatus").textContent = "";
      input("manualEntryHeading").textContent = {
        project: "New project",
        decision: "Record a decision",
        task: "Add a task",
      }[mode];
      input("manualProjectFields").hidden = mode !== "project";
      input("manualRecordFields").hidden = mode === "project";
      input("manualDecisionFields").hidden = mode !== "decision";
      input("manualTaskFields").hidden = mode !== "task";
      input("manualEntryHelp").textContent =
        "Saving writes to your signed-in Supabase account. These are manual records, not B4 versioned revisions.";
      dialog.showModal();
      input(mode === "project" ? "manualProjectName" : "manualRecordTitle").focus();
    }

    newProject.addEventListener("click", () => open("project"));
    input("manualEntryCancel").addEventListener("click", () => {
      if (!saving) dialog.close();
    });
    dialog.addEventListener("cancel", (event) => {
      if (saving) event.preventDefault();
    });

    document.addEventListener("continuity:project-detail", (event) => {
      const id = event.detail?.projectId;
      const host = document.getElementById("projectDetailBody");
      if (!id || !host) return;
      const toolbar = document.createElement("div");
      toolbar.className = "manual-entry-toolbar";
      toolbar.style.cssText = "display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px";
      for (const [label, kind] of [["+ Decision", "decision"], ["+ Task", "task"]]) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "button secondary";
        button.textContent = label;
        button.addEventListener("click", () => open(kind, id));
        toolbar.append(button);
      }
      host.prepend(toolbar);
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (saving) return;
      const status = input("manualEntryStatus");
      const submit = input("manualEntrySubmit");
      const db = window.supabaseDb;
      if (!db) {
        status.textContent = "Sign in to save a record.";
        return;
      }
      saving = true;
      submit.disabled = true;
      status.textContent = "Saving…";
      try {
        const { data, error } = await db.auth.getUser();
        if (error || !data?.user?.id) throw new Error("Your session is unavailable. Sign in again.");
        const userId = data.user.id;
        let targetProject = projectId;
        if (mode === "project") {
          targetProject = await createProject(db, userId, {
            name: input("manualProjectName").value,
            summary: input("manualProjectSummary").value,
          });
        } else if (mode === "decision") {
          await addDecision(db, userId, projectId, {
            title: input("manualRecordTitle").value,
            body: input("manualDecisionBody").value,
          });
        } else {
          await addTask(db, userId, projectId, {
            title: input("manualRecordTitle").value,
            due_date: input("manualTaskDue").value,
          });
        }
        dialog.close();
        window.showToast?.("Saved to Supabase", "Your project record is stored in your account.");
        try {
          if (typeof window.refreshProjectData !== "function") throw new Error("Dashboard refresh unavailable.");
          await window.refreshProjectData();
          window.openProjectById?.(targetProject);
        } catch (refreshError) {
          console.error("Saved, but unable to refresh dashboard", refreshError);
          window.showToast?.("Saved, but view not refreshed", "Reload to see your saved change.");
        }
      } catch (error) {
        status.textContent = error?.message || "Save failed. Please try again.";
      } finally {
        saving = false;
        submit.disabled = false;
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install, { once: true });
  } else {
    install();
  }
})();
