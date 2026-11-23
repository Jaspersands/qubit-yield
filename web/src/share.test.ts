import { describe, expect, it } from "vitest";
import { readShareState, shareHash, viewIds } from "./share";
describe("precomputed share links", () => {
  it("round-trips all five views and a whitelisted scenario", () => {
    for (const view of viewIds)
      expect(
        readShareState(shareHash(view, "same_work_savings"), [
          "same_work_savings",
        ]),
      ).toEqual({ view, scenario: "same_work_savings" });
  });
  it("ignores unknown states, arbitrary URLs and oversized hashes", () => {
    expect(readShareState("#view=evil&scenario=https://evil.test", [])).toEqual(
      { view: "decision" },
    );
    expect(readShareState("#" + "x".repeat(501), [])).toEqual({
      view: "decision",
    });
  });
});
