const assert = require("node:assert/strict");

const { build } = require(
  "../assets/js/night-observatory-branching-demo.js"
);
const relationships = require(
  "../assets/js/night-observatory-relationships.js"
);
const semantics = require(
  "../assets/js/night-observatory-junction-semantics.js"
);
const inspection = require(
  "../assets/js/night-observatory-junction-inspection.js"
);
const inspector = require(
  "../assets/js/night-observatory-junction-inspector.js"
);

const source = build();
const prepared = inspection.prepare(
  source, relationships, semantics
);

const divergence = prepared.find({
  kind: "junction",
  id: "j-div"
});

const convergence = prepared.find({
  kind: "junction",
  id: "j-con"
});

const shared = prepared.find({
  kind: "junction",
  id: "j-shared"
});

const divergenceView = inspector.describe(divergence);

assert.equal(divergenceView.title, "Documented divergence");
assert.equal(divergenceView.synthetic, true);

assert.deepEqual(
  divergenceView.sections.map(item => item.heading),
  [
    "Historical anchor",
    "Involved workstreams",
    "Historical branches",
    "Validated relationships",
    "Accepted supporting evidence"
  ]
);

assert.equal(
  divergenceView.sections.find(section =>
    section.heading === "Historical branches"
  ).lines.length,
  2
);

assert.equal(
  inspector.describe(convergence).title,
  "Documented convergence"
);

assert.equal(
  inspector.describe(shared).title,
  "Shared historical milestone"
);

assert.equal(
  inspector.describe(shared).sections.some(section =>
    section.heading === "Historical branches"
  ),
  false
);

assert.equal(
  inspector.describe(shared).sections.at(-1).lines.length,
  1
);

// Withheld junctions cannot be rendered.
const pending = build();

pending.evidence.find(item =>
  item.id === "e-j-div"
).reviewState = "pending";

const pendingPrepared = inspection.prepare(
  pending, relationships, semantics
);

assert.equal(
  pendingPrepared.find({
    kind: "junction", id: "j-div"
  }),
  null
);

assert.throws(
  () => inspector.describe(null),
  /validated junction/
);

// DOM rendering uses textContent, never HTML injection.
function fakeNode(tag) {
  return {
    tag,
    children: [],
    textContent: "",
    className: "",
    attributes: {},
    append(...nodes) {
      this.children.push(...nodes);
    },
    setAttribute(key, value) {
      this.attributes[key] = value;
    }
  };
}

const doc = {
  createElement: fakeNode
};

const host = fakeNode("div");
host.ownerDocument = doc;

const malicious = {
  ...divergence,
  statement: "<script>alert('test')</script>"
};

const panel = inspector.render(host, malicious);

assert.equal(panel.tag, "article");
assert.equal(
  panel.attributes["data-no-junction-inspection"],
  "j-div"
);
assert.equal(host.children.length, 0);
assert.ok(
  panel.children.some(child =>
    child.textContent === malicious.statement
  )
);

console.log(
  "First-class junction Inspector presentation checks passed."
);
