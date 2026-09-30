import { createElement, Fragment, type ReactNode } from "react";

/** The model returns e.g. "C — strong on X, weak on Y" in one field; split
 * it into the letter (shown big) and the qualifier (shown as a sentence). */
export function splitGrade(grade: string): { letter: string; note: string } {
  const m = /^\s*([A-F][+-]?)(?=[\s—–:-]|$)\s*[—–:-]?\s*([\s\S]*)$/.exec(grade ?? "");
  if (!m) return { letter: grade?.trim() || "—", note: "" };
  return { letter: m[1], note: m[2].trim() };
}

export interface Rewrite {
  before: string;
  after: string;
  why: string;
}

/** Best-effort split of "Instead of 'X', say: 'Y' *Why:* Z"; anything that
 * doesn't fit falls back to the raw text as `after`. */
export function parseRewrite(item: string): Rewrite {
  const [main, why = ""] = item.trim().split(/\s*\*Why:?\*:?\s*/i, 2);
  const m = /^Instead of\s+([\s\S]+?)[,\s]+(?:say|open with)[^:]*:\s*([\s\S]+)$/i.exec(main.trim());
  const strip = (t: string, extra = "") =>
    t.replace(new RegExp(`^[\\s'"‘’“”${extra}]+|[\\s'"‘’“”${extra}]+$`, "g"), "");
  if (m) return { before: strip(m[1], ","), after: strip(m[2]), why: why.trim() };
  return { before: "", after: main.trim(), why: why.trim() };
}

/** Render the **bold** / *italic* the models like to emit, as React nodes
 * (no innerHTML, so nothing needs escaping). */
export function renderInline(text: string): ReactNode {
  const parts = text.split(/(\*\*[\s\S]+?\*\*|(?<![\w*])\*(?!\s)[\s\S]+?(?<!\s)\*(?![\w*]))/g);
  return createElement(
    Fragment,
    null,
    ...parts.map((p, i) => {
      if (p.startsWith("**") && p.endsWith("**") && p.length > 4)
        return createElement("strong", { key: i }, p.slice(2, -2));
      if (p.startsWith("*") && p.endsWith("*") && p.length > 2)
        return createElement("em", { key: i }, p.slice(1, -1));
      return p;
    })
  );
}

export function dimensionLabel(key: string): string {
  return key.replace(/_/g, " ").trim().replace(/\b\w/g, (c) => c.toUpperCase());
}
