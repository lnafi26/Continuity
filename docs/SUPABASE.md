Current repository locations:
`frontend/index.html` — page structure
`frontend/assets/css/styles.css` — visual design
`frontend/assets/js/dashboard.js` — dashboard rendering and interactions
`frontend/assets/js/auth.js` — authentication and user profiles
`backend/database/supabase_connections.py` — titled database-query runner
`backend/database/supabase_queries.json` — schema, index, and RLS queries
`backend/.env` — private server-side credentials (ignored by Git)
The cleanest setup is:
Supabase PostgreSQL
↓
Supabase JavaScript client
↓
script.js loads data
↓
Existing render functions update index.html
The browser may safely contain a Supabase publishable key, but never a secret key or legacy service_role key. Supabase’s publishable key has limited privileges, while Row Level Security determines which records each signed-in user can access. Supabase API-key documentation

# Note: Call URL and the key - Define SUPABASE_URL, SUPABASE_KEY

# Commented out const db = supabase.createClient(SUPABASE_URL, SUPABASE_KEY)

Step 1: Create your Supabase account and project
Go to Supabase.

Select Start your project.

Sign in with GitHub or email.

Select New project.

Choose or create an organization.

Enter:
Project name: ThreadLinePMA
Database password: generate and securely save a strong password
Region: choose the region closest to your users

Select Create new project.
Wait for the database to finish provisioning.
Do not put the database password anywhere in your HTML or JavaScript.

Step 2: Create the database tables
Open:
Supabase Dashboard → SQL Editor → New query

Paste and run this schema. It is intentionally limited to the MVP described in the Four-Phase Planning Guide: uploaded files, Gmail and Google Calendar as the two live integrations, semantic project grouping, source-linked timelines, extracted actions, and user review. It does not copy an entire mailbox, store Gmail attachments in PostgreSQL, or mirror every event from every calendar.

```sql
-- Store one dashboard project or workstream owned by a user.
create table public.projects (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid()
    references auth.users(id) on delete cascade,
  name text not null,
  symbol text not null default 'P',
  summary text not null default '',
  deadline date,
  progress smallint not null default 0
    check (progress between 0 and 100),
  risk text not null default '',
  color text not null default '#4263eb',
  soft_color text not null default '#eef2ff',
  members text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Store non-secret metadata for a user's Gmail or Google Calendar connection and its incremental sync state. OAuth access and refresh tokens must stay in a protected backend or Supabase Vault, never in this public table.
create table public.source_connections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid()
    references auth.users(id) on delete cascade,
  provider text not null
    check (provider in ('gmail', 'google_calendar')),
  provider_account_id text not null,
  account_email text not null,
  status text not null default 'active'
    check (status in ('active', 'expired', 'error', 'disconnected')),
  sync_cursor text,
  last_synced_at timestamptz,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, provider, provider_account_id)
);

-- Store normalized input from an upload, selected Gmail message, or relevant Google Calendar event. Keep only useful text and metadata; actual uploaded files belong in Supabase Storage.
create table public.source_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid()
    references auth.users(id) on delete cascade,
  connection_id uuid
    references public.source_connections(id) on delete cascade,
  source_type text not null
    check (source_type in ('upload', 'gmail', 'google_calendar')),
  external_id text,
  external_thread_id text,
  title text not null default '',
  text_excerpt text not null default ''
    check (char_length(text_excerpt) <= 2000),
  extracted_text text,
  sender text,
  participants text[] not null default '{}',
  mime_type text,
  file_name text,
  storage_path text,
  source_url text,
  occurred_at timestamptz,
  ends_at timestamptz,
  location text,
  processing_status text not null default 'pending'
    check (processing_status in ('pending', 'processing', 'processed', 'failed')),
  processing_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (
    (source_type in ('gmail', 'google_calendar') and connection_id is not null and external_id is not null)
    or source_type = 'upload'
  ),
  unique (connection_id, external_id)
);

-- Connect a source item to one or more projects and preserve the AI match confidence and explanation for user review.
create table public.project_source_links (
  id bigint generated by default as identity primary key,
  user_id uuid not null default auth.uid()
    references auth.users(id) on delete cascade,
  project_id uuid not null
    references public.projects(id) on delete cascade,
  source_item_id uuid not null
    references public.source_items(id) on delete cascade,
  match_method text not null default 'ai'
    check (match_method in ('manual', 'rule', 'ai')),
  confidence numeric(5,4)
    check (confidence between 0 and 1),
  explanation text,
  review_status text not null default 'pending'
    check (review_status in ('pending', 'confirmed', 'rejected')),
  created_at timestamptz not null default now(),
  unique (project_id, source_item_id)
);

-- Store chronological meetings, discussions, decisions, deadlines, and status changes extracted from a source or added manually.
create table public.project_events (
  id bigint generated by default as identity primary key,
  user_id uuid not null default auth.uid()
    references auth.users(id) on delete cascade,
  project_id uuid not null
    references public.projects(id) on delete cascade,
  source_item_id uuid
    references public.source_items(id) on delete set null,
  event_type text not null
    check (event_type in ('email', 'file', 'meeting', 'decision', 'deadline', 'status', 'note')),
  title text not null,
  body text not null default '',
  person text not null default '',
  event_date timestamptz not null default now(),
  confidence numeric(5,4)
    check (confidence between 0 and 1),
  user_edited boolean not null default false,
  color text not null default '#4263eb',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Store the latest action items extracted from source material or entered manually and shown in "Needs your attention."
create table public.project_actions (
  id bigint generated by default as identity primary key,
  user_id uuid not null default auth.uid()
    references auth.users(id) on delete cascade,
  project_id uuid not null
    references public.projects(id) on delete cascade,
  source_item_id uuid
    references public.source_items(id) on delete set null,
  title text not null,
  assignee text,
  due_date date,
  completed boolean not null default false,
  confidence numeric(5,4)
    check (confidence between 0 and 1),
  user_edited boolean not null default false,
  color text not null default '#4263eb',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Store a small audit trail of user confirmations and corrections so AI grouping quality can be evaluated without retaining duplicate source content.
create table public.user_corrections (
  id bigint generated by default as identity primary key,
  user_id uuid not null default auth.uid()
    references auth.users(id) on delete cascade,
  source_item_id uuid
    references public.source_items(id) on delete set null,
  project_id uuid
    references public.projects(id) on delete set null,
  correction_type text not null
    check (correction_type in ('confirm_match', 'reject_match', 'move_project', 'edit_event', 'edit_action')),
  previous_value jsonb,
  corrected_value jsonb,
  created_at timestamptz not null default now()
);

-- Add indexes for user-scoped dashboard queries, project timelines, pending processing, and incremental source lookup.
create index projects_user_id_idx
  on public.projects(user_id);
create index source_connections_user_id_idx
  on public.source_connections(user_id);
create index source_items_user_status_idx
  on public.source_items(user_id, processing_status);
create index source_items_occurred_at_idx
  on public.source_items(user_id, occurred_at desc);
create index project_source_links_project_id_idx
  on public.project_source_links(project_id);
create index project_source_links_source_item_id_idx
  on public.project_source_links(source_item_id);
create index project_events_project_date_idx
  on public.project_events(project_id, event_date desc);
create index project_actions_project_due_idx
  on public.project_actions(project_id, due_date);
create index user_corrections_user_id_idx
  on public.user_corrections(user_id);
```

This MVP uses seven application tables. `source_items` replaces separate upload, Gmail-message, and Calendar-event tables by storing their shared searchable fields in one normalized format. `ends_at` and `location` support calendar meetings, while email-only fields such as `sender` and `external_thread_id` remain nullable. A source can be linked to multiple projects through `project_source_links`, which satisfies the planning requirement that information may appear in more than one project. Recent activity can be derived from the `created_at` and `updated_at` values instead of duplicating it in an `activities` table.

To remain comfortable under the Free tier, sync only selected Gmail content and selected calendars within a recent 30–60 day window, keep `text_excerpt` short, delete `extracted_text` after processing when it is no longer needed, store files in Supabase Storage rather than PostgreSQL, and do not copy Gmail attachments automatically. Use the Google Calendar incremental sync token in `source_connections.sync_cursor` so unchanged events are not downloaded repeatedly.

Step 3: Enable database security
Run the following SQL:

```sql
alter table public.projects enable row level security;
alter table public.source_connections enable row level security;
alter table public.source_items enable row level security;
alter table public.project_source_links enable row level security;
alter table public.project_events enable row level security;
alter table public.project_actions enable row level security;
alter table public.user_corrections enable row level security;
```

Create policies that restrict every record to its owner:

```sql
create policy "Users manage their projects"
on public.projects
for all
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy "Users manage their source connections"
on public.source_connections
for all
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy "Users manage their source items"
on public.source_items
for all
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy "Users manage their project source links"
on public.project_source_links
for all
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy "Users manage their events"
on public.project_events
for all
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy "Users manage their actions"
on public.project_actions
for all
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy "Users manage their corrections"
on public.user_corrections
for all
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);
```

Supabase recommends enabling RLS on every table exposed through the browser. Supabase RLS documentation

Step 4: Configure email authentication
In Supabase, open:
Authentication → Providers → Email
Enable the email provider.
Then open:
Authentication → URL Configuration
For local development, enter:
Site URL:
http://localhost:8000

Redirect URLs:
http://localhost:8000/**
After deployment, add the production URL, for example:
https://your-site.example.com/**

Step 5: Get the browser credentials
Open your project’s Connect dialog, or go to:
Project Settings → API Keys
Copy:
Project URL, such as https://abcxyz.supabase.co
Publishable key, beginning with sb*publishable*
Use the publishable key in the browser. Never use:
sb*secret*...
service_role
Your database password
Supabase now recommends publishable keys for client-side applications. Supabase key guidance

Step 6: Update index.html
Edit [index.html](/Users/cxu/PycharmProjects/AI_Projects/ai_project_management_tool/index.html).
Immediately before the existing script.js tag, add the Supabase browser SDK:

<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
<script src="script.js"></script>

The end of the file should therefore look like:

  <div class="toasts" id="toasts" aria-live="polite"></div>

  <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
  <script src="script.js"></script>
</body>
</html>
Add a small login dialog before those scripts:
<dialog id="loginDialog">
  <form id="loginForm">
    <header>
      <div>
        <p class="eyebrow">SIGN IN</p>
        <h2>Connect your workspace</h2>
      </div>
    </header>

    <p class="help">
      Enter your email. Supabase will send you a secure sign-in link.
    </p>

    <label class="field">
      Email
      <input
        id="loginEmail"
        type="email"
        autocomplete="email"
        required
        placeholder="you@example.com"
      >
    </label>

    <footer>
      <button class="button primary" type="submit">
        Send sign-in link
      </button>
    </footer>

  </form>
</dialog>

Step 7: Update styles.css
Your existing form and dialog styles should handle most of the login dialog. Add this to [styles.css](/Users/cxu/PycharmProjects/AI_Projects/ai_project_management_tool/styles.css):
.loading-message,
.error-message {
padding: 2rem;
text-align: center;
color: #667085;
}

.error-message {
color: #b42318;
}

#loginDialog::backdrop {
background: rgba(15, 23, 42, 0.55);
}

#loginDialog {
width: min(460px, calc(100% - 2rem));
}
No other database-specific CSS changes are required.

Step 8: Initialize Supabase in script.js
Edit [script.js](/Users/cxu/PycharmProjects/AI_Projects/ai_project_management_tool/script.js).
At the top, add:
const SUPABASE_URL = "https://YOUR_PROJECT_ID.supabase.co";
const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_YOUR_KEY";

const db = window.supabase.createClient(
SUPABASE_URL,
SUPABASE_PUBLISHABLE_KEY,
);

let projects = [];
let actions = [];
let activity = [];
Replace the placeholders with the values copied from Supabase.
Remove or comment out the current hard-coded declarations:
const projects = [/* hard-coded data */];
let actions = [/* hard-coded data */];
const activity = [/* hard-coded data */];
Do not declare the same variables twice.
Supabase initializes the browser client with the project URL and publishable key. JavaScript client initialization

Step 9: Add the authentication functions
Add these functions after the $ and $$ helpers:
async function getCurrentUser() {
const {
data: { user },
error,
} = await db.auth.getUser();

if (error) {
console.error("Unable to read user session:", error);
}

return user;
}

async function requireUser() {
const user = await getCurrentUser();

if (!user) {
$("#loginDialog").showModal();
return null;
}

return user;
}

$("#loginForm").onsubmit = async (event) => {
event.preventDefault();

const email = $("#loginEmail").value.trim();
const submitButton = event.submitter;

submitButton.disabled = true;
submitButton.textContent = "Sending…";

const { error } = await db.auth.signInWithOtp({
email,
options: {
emailRedirectTo: window.location.origin,
},
});

submitButton.disabled = false;
submitButton.textContent = "Send sign-in link";

if (error) {
console.error(error);
toast("Sign-in failed", error.message);
return;
}

toast("Check your email", "Supabase sent you a secure sign-in link.");
};

Step 10: Load projects and related information
Add this function to script.js:
async function loadDashboardData() {
const user = await requireUser();
if (!user) return;

$("#projectGrid").innerHTML =
'<p class="loading-message">Loading projects…</p>';

const [
projectsResult,
eventsResult,
actionsResult,
filesResult,
activityResult,
] = await Promise.all([
db
.from("projects")
.select("\*")
.eq("user_id", user.id)
.order("created_at"),

    db
      .from("project_events")
      .select("*")
      .eq("user_id", user.id)
      .order("event_date", { ascending: false }),

    db
      .from("project_actions")
      .select("*")
      .eq("user_id", user.id)
      .order("due_date"),

    db
      .from("project_files")
      .select("*")
      .eq("user_id", user.id)
      .order("created_at", { ascending: false }),

    db
      .from("activities")
      .select("*")
      .eq("user_id", user.id)
      .order("created_at", { ascending: false })
      .limit(20),

]);

const error = [
projectsResult,
eventsResult,
actionsResult,
filesResult,
activityResult,
].find((result) => result.error)?.error;

if (error) {
console.error("Supabase loading error:", error);
$("#projectGrid").innerHTML =
      `<p class="error-message">${escapeHtml(error.message)}</p>`;
return;
}

const eventRows = eventsResult.data;
const actionRows = actionsResult.data;
const fileRows = filesResult.data;

projects = projectsResult.data.map((project) => {
const deadline = project.deadline
? new Date(`${project.deadline}T00:00:00`)
: null;

    const days = deadline
      ? Math.ceil((deadline - new Date()) / 86400000)
      : 9999;

    return {
      id: project.id,
      name: project.name,
      symbol: project.symbol,
      summary: project.summary,
      deadline: deadline
        ? deadline.toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
          })
        : "No date",
      days,
      progress: project.progress,
      risk: project.risk || "",
      color: project.color,
      soft: project.soft_color,
      members: project.members || [],
      sources: project.sources || [],

      events: eventRows
        .filter((event) => event.project_id === project.id)
        .map((event) => ({
          id: event.id,
          date: new Date(event.event_date).toLocaleString(),
          type: event.event_type,
          title: event.title,
          body: event.body,
          person: event.person,
          color: event.color || project.color,
        })),

      files: fileRows
        .filter((file) => file.project_id === project.id)
        .map((file) => [
          file.file_name,
          `${file.source_name} · ${new Date(
            file.created_at,
          ).toLocaleDateString()}`,
        ]),
    };

});

actions = actionRows.map((action) => {
const project = projects.find(
(item) => item.id === action.project_id,
);

    return {
      id: action.id,
      title: action.title,
      project: project?.name || "Unknown project",
      projectId: action.project_id,
      due: action.due_date
        ? new Date(`${action.due_date}T00:00:00`).toLocaleDateString(
            undefined,
            { month: "short", day: "numeric" },
          )
        : "No date",
      overdue:
        action.due_date &&
        new Date(`${action.due_date}T23:59:59`) < new Date() &&
        !action.completed,
      done: action.completed,
      color: action.color || project?.color || "#4263eb",
    };

});

activity = activityResult.data.map((item) => ({
icon: item.icon,
text: escapeHtml(item.activity_text),
meta: escapeHtml(item.metadata),
time: relativeTime(item.created_at),
color: item.color,
soft: item.soft_color,
}));

renderProjects();
renderActions();
renderActivity();
populateProjectOptions();
}
Add the supporting helpers:
function escapeHtml(value = "") {
const element = document.createElement("div");
element.textContent = value;
return element.innerHTML;
}

function relativeTime(dateString) {
const seconds = Math.max(
1,
Math.floor((Date.now() - new Date(dateString).getTime()) / 1000),
);

if (seconds < 60) return `${seconds} sec`;
if (seconds < 3600) return `${Math.floor(seconds / 60)} min`;
if (seconds < 86400) return `${Math.floor(seconds / 3600)} hr`;

return `${Math.floor(seconds / 86400)} days`;
}

function populateProjectOptions() {
const options = projects
.map(
(project) =>
`<option value="${project.id}">${escapeHtml(project.name)}</option>`,
)
.join("");

$("#updateProject").innerHTML = options;

$("#uploadProject").innerHTML =
'<option value="auto">Let AI detect the project</option>' + options;
}
Explicit .eq("user_id", user.id) filters help database performance even though RLS also restricts the records. Supabase RLS performance guidance

Step 11: Replace the current page initialization
Find this block:
renderProjects();
renderActions();
renderActivity();
renderConnectors();

const opts = projects
.map((p) => `<option value="${p.id}">${p.name}</option>`)
.join("");

$("#updateProject").innerHTML = opts;
$("#uploadProject").insertAdjacentHTML("beforeend", opts);
Replace it with:
renderConnectors();

async function initializeApp() {
const user = await requireUser();

if (user) {
await loadDashboardData();
}
}

db.auth.onAuthStateChange((event, session) => {
if (session?.user) {
$("#loginDialog").close();
loadDashboardData();
}
});

initializeApp();
Now the page waits for Supabase before rendering its cards.

Step 12: Save a new timeline update to Supabase
Replace the existing updateForm.onsubmit handler with:
$("#updateForm").onsubmit = async (event) => {
event.preventDefault();

const user = await requireUser();
if (!user) return;

const project = projects.find(
(item) => item.id === $("#updateProject").value,
);

const { error } = await db
.from("project_events")
.insert({
project_id: project.id,
user_id: user.id,
event_type: $("#updateType").value,
title: $("#updateTitle").value.trim(),
body: $("#updateDetails").value.trim(),
person: user.email,
color: project.color,
});

if (error) {
console.error(error);
toast("Update not saved", error.message);
return;
}

event.target.reset();
$("#updateDialog").close();

await loadDashboardData();
toast("Update added", `Added to ${project.name}.`);
};

Step 13: Persist completed actions
Inside the existing checkbox handler, change it to an asynchronous handler:
x.onchange = async () => {
const action = actions.find(
(item) => item.id == x.closest(".action").dataset.id,
);

const previousValue = action.done;
action.done = x.checked;
renderActions();

const { error } = await db
.from("project_actions")
.update({ completed: action.done })
.eq("id", action.id);

if (error) {
console.error(error);
action.done = previousValue;
renderActions();
toast("Action not updated", error.message);
return;
}

$("#actionCount").textContent =
actions.filter((item) => !item.done).length;

toast(
action.done ? "Action completed" : "Action reopened",
action.title,
);
};
Supabase supports browser-side select, insert, and update operations, with authorization enforced by RLS. Supabase JavaScript select documentation

Step 14: Persist event deletion
Replace the current in-memory delete operation with:
b.onclick = async () => {
const eventId = Number(b.closest(".event").dataset.event);

const { error } = await db
.from("project_events")
.delete()
.eq("id", eventId);

if (error) {
console.error(error);
toast("Timeline item not deleted", error.message);
return;
}

await loadDashboardData();

activeProject = projects.find(
(project) => project.id === activeProject.id,
);

renderDrawer();
toast("Timeline item deleted", "The project memory was updated.");
};
Use the same pattern for editing: call .update(...), then reload the database information.

Step 15: Add your first user and sample project
Open the website locally.
Enter your email in the login dialog.
Open the magic link from your email.
In Supabase, go to Authentication → Users.
Copy your user UUID.
Open SQL Editor and insert sample data, replacing `YOUR_USER_UUID`. The query generates the project's UUID and reuses it for the related event and action:

```sql
with new_project as (
insert into public.projects (
  user_id,
  name,
  symbol,
  summary,
  deadline,
  progress,
  risk,
  color,
  soft_color,
  members
)
values (
  'YOUR_USER_UUID',
  'Website Redesign',
  'W',
  'Customer-facing website refresh and CMS migration',
  current_date + 1,
  78,
  'At risk',
  '#4263eb',
  '#eef2ff',
  array['JM', 'AK', 'SL']
)
returning id
)

insert into public.project_events (
  project_id,
  user_id,
  event_type,
  title,
  body,
  person,
  color
)
values (
  (select id from new_project),
  'YOUR_USER_UUID',
  'decision',
  'Launch moved to Friday at 4:00 PM',
  'The team agreed to allow one additional QA cycle.',
  'Jordan and team',
  '#4263eb'
)
returning project_id;

-- Copy the returned project_id from the preceding query and replace YOUR_PROJECT_UUID below.

insert into public.project_actions (
  project_id,
  user_id,
  title,
  due_date,
  color
)
values (
  'YOUR_PROJECT_UUID',
  'YOUR_USER_UUID',
  'Approve mobile navigation before deployment',
  current_date + 1,
  '#4263eb'
);
```

Reload the UI. The Website Redesign project should now appear automatically.

Step 16: Run the website through a local server
Do not double-click index.html and use a file:// URL. Authentication redirects work more reliably through HTTP.
From the project directory, run:
cd /Users/cxu/PycharmProjects/AI_Projects/ai_project_management_tool
python3 -m http.server 8000
Open:
http://localhost:8000
Test this sequence:
Sign in through the email link.
Confirm projects load.
Add a project update.
Reload the browser.
Confirm the update remains.
Complete an action.
Reload again.
Confirm the completed state remains.
Sign in with another user.
Confirm that user cannot see the first user’s records.

Step 17: Understand what Supabase does not automate
This database connection automatically retrieves records already stored in Supabase. It does not automatically import Gmail or Google Calendar information.
Those connector buttons are currently simulated. Real external connections require:
OAuth authorization for each provider
A secure backend or Supabase Edge Function
Provider access and refresh tokens
Scheduled synchronization or webhooks
Transformation of external records into your Supabase tables
OAuth client secrets and provider refresh tokens must never be placed in script.js. They belong in protected server-side environment variables or Supabase Edge Function secrets.
Similarly, the existing Upload button only simulates file handling. Actual uploads should use Supabase Storage, while a backend process extracts and classifies their contents.

10:42 AM

Ask for approval

5.6 SolLight

Work locallyLocal
