import assert from "node:assert/strict";
import test from "node:test";

import { CLIENT, INTENTS, SCHEMA_VERSION, capText } from "../protocol";

test("schema version is the M1 wire version", () => {
  assert.equal(SCHEMA_VERSION, "1");
});

test("intents match the documented commands", () => {
  assert.deepEqual(INTENTS, ["share_selection", "share_file_diagnostics", "ask"]);
});

test("client identity is stable for the bridge", () => {
  assert.equal(CLIENT.name, "ide-pair-agent-extension");
  assert.equal(CLIENT.version, "0.1.0");
});

test("capText leaves short strings alone", () => {
  assert.deepEqual(capText("abc", 10), { text: "abc", truncated: false });
});

test("capText marks overflow", () => {
  const result = capText("abcdefghij", 4);
  assert.equal(result.truncated, true);
  assert.match(result.text, /truncated/);
  assert.ok(result.text.startsWith("abcd"));
});
