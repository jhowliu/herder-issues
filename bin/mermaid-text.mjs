#!/usr/bin/env node
// Draws mermaid diagrams as box-drawing text for herdr-issues.
// stdin:  JSON list of mermaid sources.
// stdout: JSON list, one entry per source: candidate drawings, roomiest first,
//         or null when the diagram can't be drawn (unsupported type, parse error).
// The panel picks the first candidate that fits its width.
import { readFileSync } from "node:fs";
import { renderMermaidASCII } from "beautiful-mermaid";

const SPACING = [
  {}, // library defaults
  { paddingX: 2, paddingY: 1, boxBorderPadding: 0 }, // compact
];
const SIDEWAYS = /^(\s*(?:graph|flowchart)\s+)(LR|RL)\b/m;

function draw(src) {
  // A left-to-right flowchart is usually too wide for a side panel; offer it top-down too.
  const sources = SIDEWAYS.test(src) ? [src, src.replace(SIDEWAYS, "$1TD")] : [src];
  const out = [];
  for (const s of sources) {
    for (const opts of SPACING) {
      try {
        const text = renderMermaidASCII(s, { colorMode: "none", ...opts })
          .replace(/[ \t]+$/gm, "")
          .replace(/^\n+|\n+$/g, "");
        if (text && !out.includes(text)) out.push(text);
      } catch {
        // this variant failed; try the next
      }
    }
  }
  return out.length ? out : null;
}

const sources = JSON.parse(readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(sources.map(draw)));
