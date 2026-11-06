export interface Segment {
  text: string;
  mark: boolean;
}

const fold = (ch: string) =>
  ch.replace(/[‘’]/g, "'").replace(/[“”]/g, '"').replace(/ /g, " ").toLowerCase();

/** Map a passage to its normalised form (no whitespace), remembering where each character came from. */
function normalise(passage: string) {
  const norm: string[] = [];
  const origin: number[] = [];
  for (let i = 0; i < passage.length; i++) {
    const ch = fold(passage[i]);
    if (!/\s/.test(ch)) {
      norm.push(ch);
      origin.push(i);
    }
  }
  return { text: norm.join(""), origin };
}

/**
 * Split a passage so that every quote in it can be highlighted.
 * Matching ignores case, curly quotes and all whitespace, the same way the server verifies
 * quotes, because PDF text extraction often adds or drops spaces inside words. Overlapping quotes are merged.
 */
export function highlight(passage: string, quotes: string | string[]): Segment[] {
  const { text, origin } = normalise(passage);
  const ranges: [number, number][] = [];
  for (const quote of Array.isArray(quotes) ? quotes : [quotes]) {
    const target = fold(quote).replace(/\s+/g, "");
    const at = target ? text.indexOf(target) : -1;
    if (at >= 0) ranges.push([origin[at], origin[at + target.length - 1] + 1]);
  }
  if (!ranges.length) return [{ text: passage, mark: false }];
  ranges.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([...r]);
  }
  const out: Segment[] = [];
  let pos = 0;
  for (const [start, end] of merged) {
    if (start > pos) out.push({ text: passage.slice(pos, start), mark: false });
    out.push({ text: passage.slice(start, end), mark: true });
    pos = end;
  }
  if (pos < passage.length) out.push({ text: passage.slice(pos), mark: false });
  return out;
}
