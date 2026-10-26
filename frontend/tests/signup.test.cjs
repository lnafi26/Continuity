const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(
  path.resolve(__dirname, "../assets/js/auth.js"),
  "utf8"
);

function createAuthPage({ signUp } = {}) {
  const elements = new Map();
  const handlers = new Map();
  const signupCalls = [];

  const signupButton = { disabled: false };

  function getElement(id) {
    if (!elements.has(id)) {
      const classes = new Set();

      elements.set(id, {
        value: "",
        textContent: "",
        hidden: false,
        disabled: false,
        open: false,
        type: "text",
        classList: {
          add(name) { classes.add(name); },
          remove(name) { classes.delete(name); },
          toggle(name, enabled) {
            if (enabled) classes.add(name);
            else classes.delete(name);
          },
          contains(name) { return classes.has(name); }
        },
        addEventListener(name, callback) {
          handlers.set(`${id}:${name}`, callback);
        },
        querySelector(selector) {
          if (selector === 'button[type="submit"]') {
            return signupButton;
          }
          return null;
        },
        setAttribute() {},
        focus() {},
        reset() {},
        showModal() { this.open = true; },
        close() { this.open = false; }
      });
    }

    return elements.get(id);
  }

  const auth = {
    onAuthStateChange() {},

    // Keep dashboard bootstrap inactive during these isolated tests.
    getSession() {
      return new Promise(() => {});
    },

    async signUp(attributes) {
      signupCalls.push(attributes);

      if (signUp) return signUp(attributes);

      return {
        data: { user: { id: "mock-user" }, session: null },
        error: null
      };
    }
  };

  const window = {
    SUPABASE_CONFIG: {
      url: "https://example.supabase.co",
      publishableKey: "sb_publishable_mock"
    },
    supabase: {
      createClient() {
        return { auth };
      }
    },
    location: {
      origin: "http://localhost:8000",
      pathname: "/",
      search: ""
    }
  };

  vm.runInNewContext(source, {
    window,
    document: {
      getElementById: getElement
    },
    URLSearchParams,
    console,
    setTimeout() {}
  }, { filename: "auth.js" });

  return {
    element: getElement,
    signupButton,
    signupCalls,
    submit: handlers.get("signupForm:submit")
  };
}

test("short signup password is rejected before Supabase", async () => {
  const page = createAuthPage();

  page.element("signupPassword").value = "short";
  page.element("signupPasswordConfirm").value = "short";

  await page.submit({ preventDefault() {} });

  assert.equal(page.signupCalls.length, 0);
  assert.equal(page.signupButton.disabled, false);
  assert.match(
    page.element("signupMessage").textContent,
    /at least 15 characters/i
  );
});

test("mismatched signup passwords are rejected", async () => {
  const page = createAuthPage();

  page.element("signupPassword").value = "ValidPasswordForTests2026!";
  page.element("signupPasswordConfirm").value =
    "DifferentPasswordForTests2026!";

  await page.submit({ preventDefault() {} });

  assert.equal(page.signupCalls.length, 0);
  assert.equal(page.signupButton.disabled, false);
  assert.match(
    page.element("signupMessage").textContent,
    /passwords do not match/i
  );
});

test("overlapping signup requests are prevented", async () => {
  let finishSignup;

  const pendingSignup = new Promise((resolve) => {
    finishSignup = resolve;
  });

  const page = createAuthPage({
    signUp: () => pendingSignup
  });

  page.element("signupName").value = "Test User";
  page.element("signupEmail").value = "test@example.com";
  page.element("signupPassword").value = "ValidPasswordForTests2026!";
  page.element("signupPasswordConfirm").value =
    "ValidPasswordForTests2026!";

  const firstSubmission = page.submit({ preventDefault() {} });

  assert.equal(page.signupCalls.length, 1);
  assert.equal(page.signupButton.disabled, true);

  await page.submit({ preventDefault() {} });

  // A second submission must not reach Supabase.
  assert.equal(page.signupCalls.length, 1);

  finishSignup({
    data: { user: { id: "mock-user" }, session: null },
    error: null
  });

  await firstSubmission;

  assert.equal(page.signupButton.disabled, false);
  assert.equal(page.element("signupSuccess").hidden, false);
  assert.equal(page.element("signupFormView").hidden, true);
  assert.equal(page.element("signupPassword").value, "");
  assert.equal(page.element("signupPasswordConfirm").value, "");
});

test("failed signup restores the interface", async () => {
  const page = createAuthPage({
    signUp: async () => ({
      data: null,
      error: new Error("Mock signup rejected")
    })
  });

  page.element("signupName").value = "Test User";
  page.element("signupEmail").value = "test@example.com";
  page.element("signupPassword").value = "ValidPasswordForTests2026!";
  page.element("signupPasswordConfirm").value =
    "ValidPasswordForTests2026!";

  await page.submit({ preventDefault() {} });

  assert.equal(page.signupCalls.length, 1);
  assert.equal(page.signupButton.disabled, false);
  assert.equal(page.element("signupFormView").hidden, false);
  assert.equal(page.element("signupSuccess").hidden, false);
  assert.match(
    page.element("signupMessage").textContent,
    /mock signup rejected/i
  );
  assert.equal(page.element("signupPassword").value, "");
  assert.equal(page.element("signupPasswordConfirm").value, "");
});
