import { describe, expect, it } from "vitest";
import { highlight } from "./highlight";

describe("highlight", () => {
  it("marks the quote inside the passage", () => {
    expect(highlight("Total assets: 412,600\nNet income: 3,260", "Net income: 3,260")).toEqual([
      { text: "Total assets: 412,600\n", mark: false },
      { text: "Net income: 3,260", mark: true },
    ]);
  });

  it("matches across line breaks, extra spaces and case", () => {
    const parts = highlight("The provision increased because\ndelinquent   auto loans rose.", "because delinquent AUTO loans");
    expect(parts.find((p) => p.mark)?.text).toBe("because\ndelinquent   auto loans");
  });

  it("matches text where the PDF split words or spaced out letters", () => {
    expect(highlight("The budget deficit de creased by $41.4 b illion.", "deficit decreased by $41.4 billion").find((p) => p.mark)?.text)
      .toBe("deficit de creased by $41.4 b illion");
    expect(highlight("The DIF reserve ratio, w h i c h i s t h e r a t i o", "which is the ratio").some((p) => p.mark)).toBe(true);
  });

  it("matches curly and straight apostrophes", () => {
    expect(highlight("The Fund’s balance rose.", "Fund's balance").some((p) => p.mark)).toBe(true);
  });

  it("marks several quotes in one passage and merges overlaps", () => {
    const parts = highlight("Interest income: 21,870\nProvision: 1,940\nNet income: 3,260", ["Net income: 3,260", "Provision: 1,940", "1,940"]);
    expect(parts.filter((p) => p.mark).map((p) => p.text)).toEqual(["Provision: 1,940", "Net income: 3,260"]);
  });

  it("returns the passage unmarked when the quote is not there", () => {
    expect(highlight("Net income: 3,260", "Net income: 9,999")).toEqual([{ text: "Net income: 3,260", mark: false }]);
  });
});
