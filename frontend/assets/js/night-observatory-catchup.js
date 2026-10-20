/*
 * Project Continuity — Night Observatory Catch-up
 * C2.1b: Local demonstration interactions only.
 * No persistent status updates, ingestion, or network requests.
 */
(() => {
  "use strict";

  const filters = [
    ...document.querySelectorAll("#noCatchupFilters .no-filter")
  ];
  const updates = [
    ...document.querySelectorAll("#noUpdateList .no-update")
  ];
  const count = document.getElementById("noCatchupCount");
  const goToContinuities = document.getElementById("noGoToContinuities");

  for (const filter of filters) {
    filter.addEventListener("click", () => {
      const selected = filter.dataset.filter;
      let visible = 0;

      for (const update of updates) {
        const matches =
          selected === "all" || update.dataset.kind === selected;

        update.hidden = !matches;
        if (matches) visible += 1;
      }

      for (const button of filters) {
        button.setAttribute(
          "aria-pressed",
          String(button === filter)
        );
      }

      count.textContent =
        `Showing ${visible} ${visible === 1 ? "update" : "updates"}`;
    });
  }

  goToContinuities?.addEventListener("click", () => {
    document.querySelector(
      '.no-navigation [data-view="atlas"]'
    )?.click();
  });
})();
