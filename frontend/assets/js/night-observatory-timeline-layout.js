/* Continuity C2.1c — Historical strand layout planner. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  if (root) root.ContinuityTimelineLayout = api;
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  const LEFT = 180;
  const SPAN = 620;
  const FIRST_Y = 150;
  const LANE_GAP = 175;
  const NODE_GAP = 160;

  function timestamp(value) {
    if (value == null || value === "") return null;

    if (
      typeof value !== "string" ||
      !/^\d{4}-\d{2}-\d{2}$/.test(value)
    ) {
      throw new Error("Historical dates must use YYYY-MM-DD.");
    }

    const parsed = Date.parse(value + "T00:00:00Z");

    if (
      !Number.isFinite(parsed) ||
      new Date(parsed).toISOString().slice(0, 10) !== value
    ) {
      throw new Error("Invalid historical date: " + value);
    }

    return parsed;
  }

  function plan(model) {
    if (
      !model ||
      !Array.isArray(model.events) ||
      !Array.isArray(model.strands)
    ) {
      throw new Error("Timeline requires event and strand arrays.");
    }

    const byId = new Map();

    for (const event of model.events) {
      if (
        !event ||
        typeof event.id !== "string" ||
        !event.id ||
        byId.has(event.id)
      ) {
        throw new Error("Each event requires a unique, nonempty ID.");
      }

      byId.set(event.id, event);
    }

    const historical = [];
    const used = new Set();
    const strandIds = new Set();
    let excluded = 0;

    for (const strand of model.strands) {
      if (
        !strand ||
        typeof strand.id !== "string" ||
        !strand.id ||
        strandIds.has(strand.id) ||
        !Array.isArray(strand.eventIds)
      ) {
        throw new Error("Invalid or duplicate strand definition.");
      }

      strandIds.add(strand.id);

      // Future possibilities never become historical Canvas nodes.
      if (["proposal", "alternative"].includes(strand.kind)) {
        excluded++;
        continue;
      }

      if (strand.kind !== "historical") {
        throw new Error("Unsupported strand kind: " + strand.kind);
      }

      const entries = strand.eventIds.map(id => {
        const event = byId.get(id);

        if (!event) {
          throw new Error("Unknown historical event: " + id);
        }

        if (used.has(id)) {
          throw new Error("Repeated historical event: " + id);
        }

        if (
          ["proposal", "planned", "hypothetical"]
            .includes(event.temporalClass)
        ) {
          throw new Error(
            "Proposed event placed in historical strand: " + id
          );
        }

        used.add(id);
        return { event, time: timestamp(event.occurredAt) };
      });

      historical.push({
        id: strand.id,
        label: strand.label || strand.id,
        entries
      });
    }

    const times = historical.flatMap(strand =>
      strand.entries
        .filter(entry => entry.time !== null)
        .map(entry => entry.time)
    );

    const earliest = times.length ? Math.min(...times) : 0;
    const span = times.length
      ? Math.max(1, Math.max(...times) - earliest)
      : 1;

    const undated = [];
    let farthestX = 0;

    const strands = historical.map((strand, lane) => {
      const dated = strand.entries.filter(entry => {
        if (entry.time !== null) return true;

        // Unknown dates remain unknown, rather than invented.
        undated.push({
          eventId: entry.event.id,
          strandId: strand.id
        });
        return false;
      }).sort((a, b) =>
        a.time - b.time ||
        a.event.id.localeCompare(b.event.id)
      );

      let lastX = -Infinity;

      const nodes = dated.map(({ event, time }) => {
        const target = LEFT +
          ((time - earliest) / span) * SPAN;

        // Prevent adjacent event labels from colliding.
        const x = Math.max(target, lastX + NODE_GAP);
        lastX = x;
        farthestX = Math.max(farthestX, x);

        return {
          eventId: event.id,
          strandId: strand.id,
          x,
          y: FIRST_Y + lane * LANE_GAP
        };
      });

      let path = null;

      if (nodes.length > 1) {
        path = `M ${nodes[0].x} ${nodes[0].y}`;

        for (let index = 1; index < nodes.length; index++) {
          const a = nodes[index - 1];
          const b = nodes[index];
          const middle = (a.x + b.x) / 2;

          path +=
            ` C ${middle} ${a.y}` +
            ` ${middle} ${b.y}` +
            ` ${b.x} ${b.y}`;
        }
      }

      return {
        id: strand.id,
        label: strand.label,
        nodes,
        path
      };
    });

    return {
      width: Math.max(1000, Math.ceil(farthestX + 190)),
      height: Math.max(
        280,
        FIRST_Y + (historical.length - 1) * LANE_GAP + 130
      ),
      strands,
      undated,
      excludedProposalStrands: excluded
    };
  }

  return Object.freeze({ plan });
});
