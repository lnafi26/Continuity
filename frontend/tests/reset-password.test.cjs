const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(
  path.resolve(__dirname, "../assets/js/reset-password.js"),
  "utf8"
);

function createRecoveryPage(
  hash,
  { search = "", initializationError = null, updateError = null } = {}
) {
  let authCallback = null;
  let cleanedUrl = null;
  let submitHandler = null;
  let signOutCalls = 0;
  const updateCalls = [];

  const newPassword = { value: "" };
  const confirmPassword = { value: "" };
  const status = { textContent: "" };
  const form = {
    hidden: true,
    addEventListener(name, callback) {
      if (name === "submit") submitHandler = callback;
    },
    reset() {
      newPassword.value = "";
      confirmPassword.value = "";
    }
  };
  const button = { disabled: false };

  const elements = {
    recoveryStatus: status,
    resetPasswordForm: form,
    resetPasswordButton: button,
    newPassword,
    confirmPassword
  };

  const auth = {
    onAuthStateChange(callback) {
      authCallback = callback;
    },
    initialize: async () => ({ error: initializationError }),
    updateUser: async (attributes) => {
      updateCalls.push(attributes);
      return { error: updateError };
    },
    signOut: async () => {
      signOutCalls++;
      return { error: null };
    }
  };

  const window = {
    SUPABASE_CONFIG: {
      url: "https://example.supabase.co",
      publishableKey: "sb_publishable_mock"
    },
    location: {
      pathname: "/reset-password.html",
      search,
      hash
    },
    history: {
      replaceState(_state, _title, url) {
        cleanedUrl = url;
      }
    },
    supabase: {
      createClient() {
        return { auth };
      }
    },
    setTimeout() {}
  };

  vm.runInNewContext(source, {
    window,
    URLSearchParams,
    document: {
      getElementById(id) {
        if (!elements[id]) {
          throw new Error(`Unexpected element: ${id}`);
        }
        return elements[id];
      }
    }
  }, { filename: "reset-password.js" });

  return {
    status,
    form,
    button,
    newPassword,
    confirmPassword,
    updateCalls,
    get submitHandler() { return submitHandler; },
    get signOutCalls() { return signOutCalls; },
    get authCallback() { return authCallback; },
    get cleanedUrl() { return cleanedUrl; }
  };
}

test("explicitly expired recovery link is rejected", () => {
  const page = createRecoveryPage("#error_code=otp_expired");

  assert.match(page.status.textContent, /invalid or expired/i);
  assert.equal(page.form.hidden, true);
  assert.equal(page.cleanedUrl, "/reset-password.html");
});

test("ordinary sign-in cannot authorize password recovery", () => {
  const page = createRecoveryPage(
    "#access_token=mock-token&type=recovery"
  );

  page.authCallback("SIGNED_IN", {
    access_token: "mock-token"
  });

  assert.equal(page.form.hidden, true);
  assert.notEqual(
    page.status.textContent,
    "Recovery link verified. Choose a new password."
  );
});

test("recovery event without access token is rejected", () => {
  const page = createRecoveryPage(
    "#access_token=mock-token&type=recovery"
  );

  page.authCallback("PASSWORD_RECOVERY", null);

  assert.equal(page.form.hidden, true);
});

test("standalone PKCE code is rejected in implicit recovery flow", () => {
  const page = createRecoveryPage("", {
    search: "?code=mock-invalid-code"
  });

  assert.match(page.status.textContent, /could not be verified/i);
  assert.equal(page.form.hidden, true);
  assert.equal(page.cleanedUrl, "/reset-password.html");
});

test("initialization failure leaves the recovery form locked", async () => {
  const page = createRecoveryPage(
    "#access_token=mock-token&type=recovery",
    { initializationError: new Error("Invalid recovery token") }
  );

  await new Promise((resolve) => setImmediate(resolve));

  assert.match(page.status.textContent, /could not be verified/i);
  assert.equal(page.form.hidden, true);
  assert.equal(page.cleanedUrl, "/reset-password.html");
});

test("valid recovery event unlocks password form", () => {
  const page = createRecoveryPage(
    "#access_token=mock-token&type=recovery"
  );

  page.authCallback("PASSWORD_RECOVERY", {
    access_token: "mock-token"
  });

  assert.equal(page.form.hidden, false);
  assert.equal(
    page.status.textContent,
    "Recovery link verified. Choose a new password."
  );
  assert.equal(page.cleanedUrl, "/reset-password.html");
});

test("unauthorized submission cannot update password", async () => {
  const page = createRecoveryPage(
    "#access_token=mock-token&type=recovery"
  );

  page.newPassword.value = "NewPasswordForTesting2026!";
  page.confirmPassword.value = "NewPasswordForTesting2026!";

  await page.submitHandler({ preventDefault() {} });

  assert.equal(page.form.hidden, true);
  assert.equal(page.updateCalls.length, 0);
  assert.equal(page.signOutCalls, 0);
});

test("successful password update locks form and ends session", async () => {
  const page = createRecoveryPage(
    "#access_token=mock-token&type=recovery"
  );

  page.authCallback("PASSWORD_RECOVERY", {
    access_token: "mock-token"
  });

  page.newPassword.value = "NewPasswordForTesting2026!";
  page.confirmPassword.value = "NewPasswordForTesting2026!";

  await page.submitHandler({ preventDefault() {} });

  assert.equal(page.updateCalls.length, 1);
  assert.equal(
    page.updateCalls[0].password,
    "NewPasswordForTesting2026!"
  );
  assert.equal(page.signOutCalls, 1);
  assert.equal(page.form.hidden, true);
  assert.equal(page.newPassword.value, "");
  assert.match(page.status.textContent, /updated successfully/i);
});

test("failed password update does not report success", async () => {
  const page = createRecoveryPage(
    "#access_token=mock-token&type=recovery",
    { updateError: new Error("Mock update failure") }
  );

  page.authCallback("PASSWORD_RECOVERY", {
    access_token: "mock-token"
  });

  page.newPassword.value = "NewPasswordForTesting2026!";
  page.confirmPassword.value = "NewPasswordForTesting2026!";

  await page.submitHandler({ preventDefault() {} });

  assert.equal(page.updateCalls.length, 1);
  assert.equal(page.signOutCalls, 0);
  assert.equal(page.form.hidden, false);
  assert.equal(page.newPassword.value, "");
  assert.equal(page.button.disabled, false);
  assert.match(page.status.textContent, /unable to update/i);
});
