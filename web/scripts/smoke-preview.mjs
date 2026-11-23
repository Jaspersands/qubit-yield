/** Executes the actual built standalone module in a DOM. This is not visual QA. */
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { JSDOM, VirtualConsole } from "jsdom";

const html = readFileSync(
  new URL("../preview/index.html", import.meta.url),
  "utf8",
);
const catalog = JSON.parse(
  readFileSync(
    new URL("../../artifacts/scenarios.json", import.meta.url),
    "utf8",
  ),
);
const errors = [];
let requests = 0;
const vc = new VirtualConsole();
vc.on("jsdomError", (error) => errors.push(error.message));
vc.on("error", (message) => errors.push(String(message)));
const dom = new JSDOM(html, {
  url: "https://preview.example.test/",
  runScripts: "outside-only",
  pretendToBeVisual: true,
  virtualConsole: vc,
  beforeParse(window) {
    window.fetch = async () => {
      requests++;
      throw new Error("Preview must not require network");
    };
    window.scrollTo = () => {};
    window.TextEncoder = TextEncoder;
    window.ResizeObserver = class {
      constructor(callback) {
        this.callback = callback;
      }
      observe(target) {
        this.callback([{ target, contentRect: { width: 640, height: 240 } }]);
      }
      unobserve() {}
      disconnect() {}
    };
  },
});
const { window } = dom;
const document = window.document;
const wait = async () => new Promise((resolve) => setTimeout(resolve, 60));
const button = (text) =>
  [...document.querySelectorAll("button")].find(
    (node) => node.textContent.trim() === text,
  );
const click = async (text) => {
  const node = button(text);
  assert.ok(node, `Missing button: ${text}`);
  node.click();
  await wait();
};
const change = async (node, value) => {
  assert.ok(node, "Missing form input");
  const proto =
    node.tagName === "TEXTAREA"
      ? window.HTMLTextAreaElement.prototype
      : node.tagName === "SELECT"
        ? window.HTMLSelectElement.prototype
        : window.HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value").set.call(node, value);
  node.dispatchEvent(
    new window.Event(node.tagName === "SELECT" ? "change" : "input", {
      bubbles: true,
    }),
  );
  node.dispatchEvent(new window.Event("change", { bubbles: true }));
  await wait();
};
for (const script of document.querySelectorAll('script[type="module"]'))
  window.eval(script.textContent);
await new Promise((resolve) => setTimeout(resolve, 300));
assert.match(document.body.textContent, /Saved experiment/);
const select = document.querySelector("#saved-scenario-select");
assert.equal(select.options.length, 8);
for (const option of [...select.options]) {
  await change(select, option.value);
  await click("Save scenario");
  const stored = JSON.parse(
    window.localStorage.getItem("qubityield-scenarios-v1"),
  );
  assert.deepEqual(
    stored[0].data,
    catalog[option.value],
    `Exact evidence mismatch for ${option.value}`,
  );
}
await change(select, "same_work_savings");
assert.equal(
  document.querySelector("#value-mode").value,
  "fixed_output_savings",
);
await change(document.querySelector("#input-value-per-productive-hour"), "400");
assert.match(
  document.body.textContent,
  /Draft edits are not recalculated offline/,
);
await click("Restore saved inputs");
assert.equal(
  Number(document.querySelector("#input-value-per-productive-hour").value),
  catalog.same_work_savings.scenario.value_per_productive_hour,
);
await click("Strategy tools");
assert.match(document.body.textContent, /Coverage, not probability/);
assert.match(document.body.textContent, /125 GRID CELLS/);
assert.equal(button("Run stress grid").disabled, true);
await click("Pricing feasibility");
assert.match(document.body.textContent, /Minimum vendor value share/);
assert.equal(button("Evaluate pricing").disabled, true);
await click("History");
assert.match(document.body.textContent, /History lives with your local engine/);
await click("Experiment lab");
assert.equal(button("Rerun experiment").disabled, true);
await click("Import");
const textarea = document.querySelector("textarea");
assert.equal(document.activeElement, textarea);
await change(textarea, '{"value_per_productive_hour":300}');
await click("Validate and import");
assert.equal(document.querySelector('[role="dialog"]'), null);
assert.equal(
  Number(document.querySelector("#input-value-per-productive-hour").value),
  300,
);
assert.match(
  document.body.textContent,
  /Draft edits are not recalculated offline/,
);
window.location.hash = "#view=decision&scenario=case_default";
await wait();
assert.match(document.body.textContent, /Prioritize pulse optimization/);
assert.equal(
  document.querySelector("#saved-scenario-select").value,
  "case_default",
);
await click("Compare scenarios3");
assert.ok(document.querySelector('[role="dialog"]'));
document.dispatchEvent(
  new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
);
await wait();
assert.equal(document.querySelector('[role="dialog"]'), null);
const external = [
  ...document.querySelectorAll("script[src],link[href],img[src],iframe[src]"),
].filter(
  (node) =>
    !String(node.getAttribute("src") || node.getAttribute("href")).startsWith(
      "data:",
    ),
);
assert.deepEqual(
  external,
  [],
  "Standalone preview contains external asset references",
);
assert.equal(requests, 0);
assert.deepEqual(errors, []);
console.log(
  JSON.stringify({
    status: "passed",
    catalog_scenarios: 8,
    screens: 5,
    import: true,
    hash_navigation: true,
    modal: true,
    network_requests: requests,
    runtime_errors: errors.length,
    html_bytes: Buffer.byteLength(html),
  }),
);
dom.window.close();
