(() => {
  "use strict";

  const status = document.getElementById("recoveryStatus");
  const form = document.getElementById("resetPasswordForm");
  const button = document.getElementById("resetPasswordButton");

  const setStatus = (message) => {
    status.textContent = message;
  };

  const cleanUrl = () => {
    window.history.replaceState(
      null,
      "",
      window.location.pathname
    );
  };

  const config = window.SUPABASE_CONFIG;

  if (!config?.url || !config?.publishableKey ||
      !window.supabase) {
    setStatus("Password recovery is unavailable.");
    return;
  }

  const query = new URLSearchParams(window.location.search);
  const fragment = new URLSearchParams(
    window.location.hash.substring(1)
  );

  // Recovery errors may be returned in the query string or URL fragment.
  const errorParameters = ["error", "error_code", "error_description"];
  const callbackHasError = [query, fragment].some((parameters) =>
    errorParameters.some((key) => parameters.has(key))
  );

  if (callbackHasError) {
    cleanUrl();
    setStatus("This recovery link is invalid or expired. Please request a new one.");
    return;
  }

  const hasCallback =
    query.has("code") ||
    fragment.has("access_token");

  if (!hasCallback) {
    setStatus("Open the password-reset link from your email to continue.");
    return;
  }

  const db = window.supabase.createClient(
    config.url,
    config.publishableKey,
    {
      auth: {
        persistSession: false,
        autoRefreshToken: false,
        detectSessionInUrl: true
      }
    }
  );

  let recoveryAuthorized = false;
  let submitting = false;
  let verificationPending = true;

  db.auth.onAuthStateChange((event, session) => {
    if (event !== "PASSWORD_RECOVERY" ||
        !session?.access_token) {
      return;
    }

    recoveryAuthorized = true;
    verificationPending = false;
    form.hidden = false;
    setStatus("Recovery link verified. Choose a new password.");
    cleanUrl();
  });

  // A slow response does not establish that a recovery link is invalid.
  window.setTimeout(() => {
    if (verificationPending) {
      setStatus(
        "Verification is taking longer than expected. Keep this page open, or request a new recovery link."
      );
    }
  }, 8000);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!recoveryAuthorized || submitting) return;

    const password = document.getElementById("newPassword").value;
    const confirmation = document.getElementById("confirmPassword").value;

    if (password.length < 15) {
      setStatus("Use a password of at least 15 characters.");
      return;
    }

    if (password !== confirmation) {
      setStatus("The passwords do not match.");
      return;
    }

    submitting = true;
    button.disabled = true;
    setStatus("Updating your password…");

    try {
      const { error } = await db.auth.updateUser({
        password
      });

      if (error) {
        form.reset();
        setStatus(
          "Unable to update your password. Please retry or request a new recovery link."
        );
        return;
      }

      recoveryAuthorized = false;
      verificationPending = false;
      form.reset();
      form.hidden = true;

      // Password update has succeeded. Track session cleanup separately.
      let sessionEnded = false;

      try {
        const { error: signOutError } =
          await db.auth.signOut({ scope: "local" });
        sessionEnded = !signOutError;
      } catch {
        // Do not misreport a successful password update as a failure.
      }

      setStatus(
        sessionEnded
          ? "Password updated successfully. You can now return to sign in."
          : "Password updated successfully, but session cleanup could not be confirmed. Close this tab before signing in again."
      );
    } catch {
      form.reset();
      setStatus(
        "Could not confirm whether your password was updated. Try signing in before requesting another reset."
      );
    } finally {
      submitting = false;
      button.disabled = false;
    }
  });
})();
