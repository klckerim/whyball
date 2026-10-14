// T1 source scan (UI_SPEC §7): no number may be written into JSX by hand; it must come from data
// through <Fact>. Parses TSX with the bundler's own parser (vite → rolldown/oxc), so it reads JSX,
// not text patterns.
import { parseAst } from "vite";

export interface Finding {
  file: string;
  line: number;
  snippet: string; // the offending source text
  rule: "jsx-text" | "jsx-expression" | "text-attribute";
}

/** Attributes whose value is read or heard by the viewer. */
const TEXT_ATTRIBUTES = new Set(["title", "alt", "placeholder", "aria-label", "aria-valuetext", "aria-description"]);
const DIGIT = /\d/;

type Node = { type: string; start: number; end: number; [key: string]: unknown };

function isNode(v: unknown): v is Node {
  return typeof v === "object" && v !== null && typeof (v as Node).type === "string";
}

function children(node: Node): Node[] {
  const out: Node[] = [];
  for (const [key, value] of Object.entries(node)) {
    if (key === "start" || key === "end" || key === "type") continue;
    for (const v of Array.isArray(value) ? value : [value]) if (isNode(v)) out.push(v);
  }
  return out;
}

/** Literals with a digit inside an expression; nested JSX is scanned on its own. */
function digitLiterals(node: Node, out: Node[]): Node[] {
  if (node.type === "JSXElement" || node.type === "JSXFragment") return out;
  if (node.type === "Literal" && (typeof node.value === "number" || (typeof node.value === "string" && DIGIT.test(node.value)))) {
    out.push(node);
  } else if (node.type === "TemplateElement" && DIGIT.test(String((node.value as { raw: string }).raw))) {
    out.push(node);
  }
  for (const c of children(node)) digitLiterals(c, out);
  return out;
}

export function scanJsx(file: string, source: string): Finding[] {
  const findings: Finding[] = [];
  const line = (pos: number) => source.slice(0, pos).split("\n").length;
  const add = (node: Node, rule: Finding["rule"]) => {
    const text = node.type === "TemplateElement" ? (node.value as { raw: string }).raw : source.slice(node.start, node.end);
    findings.push({ file, line: line(node.start), snippet: text.trim(), rule });
  };

  const visit = (node: Node, parent: Node | null) => {
    if (node.type === "JSXText" && DIGIT.test(String(node.value))) add(node, "jsx-text");
    if (node.type === "JSXExpressionContainer" && parent?.type !== "JSXAttribute") {
      for (const lit of digitLiterals(node.expression as Node, [])) add(lit, "jsx-expression");
    }
    if (node.type === "JSXAttribute") {
      const name = (node.name as { name?: unknown }).name;
      const value = node.value as Node | null;
      if (typeof name === "string" && TEXT_ATTRIBUTES.has(name) && value) {
        const lits = value.type === "Literal" ? (DIGIT.test(String(value.value)) ? [value] : []) : digitLiterals(value, []);
        for (const lit of lits) add(lit, "text-attribute");
      }
    }
    for (const c of children(node)) visit(c, node);
  };
  visit(parseAst(source, { lang: "tsx" }) as unknown as Node, null);
  return findings;
}
