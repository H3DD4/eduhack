import katex from "katex";

export type RichSegment =
  | { kind: "text"; value: string }
  | { kind: "code-block"; value: string }
  | { kind: "code-inline"; value: string }
  | { kind: "math"; value: string; display: boolean };

const LATEX_CMD_NAMES = [
  "begin", "end", "text", "textbf", "textit", "textrm", "mathrm", "mathbf", "boldsymbol",
  "mathbb", "mathcal", "mathfrak", "operatorname", "displaystyle", "textstyle",
  "max", "min", "arg", "sup", "inf", "lim", "log", "ln", "exp",
  "sin", "cos", "tan", "cot", "sec", "csc", "det", "dim", "ker", "gcd", "mod", "bmod", "pmod",
  "frac", "tfrac", "dfrac", "binom", "sqrt", "sum", "prod", "int", "iint", "oint",
  "bigcup", "bigcap", "partial", "nabla", "infty",
  "le", "ge", "leq", "geq", "neq", "ne", "approx", "equiv", "sim", "simeq", "cong", "propto", "ll", "gg",
  "pm", "mp", "times", "cdot", "div", "circ", "bullet", "oplus", "otimes", "odot", "setminus",
  "in", "notin", "ni", "subset", "subseteq", "supset", "supseteq", "cup", "cap", "emptyset", "varnothing",
  "forall", "exists", "neg", "lnot", "land", "lor", "implies", "iff",
  "to", "gets", "rightarrow", "leftarrow", "Rightarrow", "Leftarrow", "leftrightarrow", "Leftrightarrow",
  "mapsto", "longmapsto", "uparrow", "downarrow", "top", "bot", "perp", "parallel", "dagger", "star", "ast",
  "langle", "rangle", "lfloor", "rfloor", "lceil", "rceil", "left", "right", "bigl", "bigr", "Big", "Bigl", "Bigr",
  "dots", "ldots", "cdots", "vdots", "ddots", "bar", "hat", "tilde", "vec", "overline", "underline",
  "underbrace", "overbrace", "quad", "qquad",
  "alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta", "eta", "theta", "vartheta",
  "iota", "kappa", "lambda", "mu", "nu", "xi", "pi", "rho", "sigma", "tau", "upsilon",
  "phi", "varphi", "chi", "psi", "omega",
  "Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma", "Upsilon", "Phi", "Psi", "Omega",
];

// Word commands require no trailing ASCII letter (so \Users, \new, \test stay plain text);
// spacing commands (\, \; \: \!) may sit next to any character.
const LATEX_CMD_SRC = `(?:\\\\(?:${LATEX_CMD_NAMES.join("|")})(?![A-Za-z])|\\\\[,;:!])`;
const LATEX_CMD_RE = new RegExp(LATEX_CMD_SRC);
const LATEX_STRIP_RE = new RegExp(`\\\\text(?:bf|it|rm)?\\{[^}]*\\}|${LATEX_CMD_SRC}`, "g");
const ENV_NAMES = "aligned|align\\*?|pmatrix|bmatrix|vmatrix|matrix|cases|array|gather\\*?|equation\\*?";

// Primary tokenizer: fenced code, inline code, $$...$$, $\begin...\end$, \[...\] / \\[...\\], $...$, \(...\) / \\(...\\), bare envs.
const RICH_RE = new RegExp(
  [
    "```\\w*[ \\t]*\\n?(?<block>[\\s\\S]*?)```",
    "`(?<inline>[^`\\n]+)`",
    "\\$\\$(?<displayDollar>[\\s\\S]+?)\\$\\$",
    `\\$\\s*(?<dollarEnv>\\\\begin\\{(?<dollarEnvName>${ENV_NAMES})\\}[\\s\\S]+?\\\\end\\{\\k<dollarEnvName>\\})\\s*\\$`,
    "\\\\{1,2}\\[(?<bracketMath>[\\s\\S]+?)\\\\{1,2}\\]",
    "\\$(?:(?=[^\\s$])|[ \\t]+(?=[A-Za-z\\\\(\\-|]))(?<inlineDollar>[^$\\n]{0,400}?\\S)\\$(?!\\d)",
    "\\\\{1,2}\\((?<parenMath>[\\s\\S]+?)\\\\{1,2}\\)",
    `(?<bareEnv>\\\\begin\\{(?<bareEnvName>${ENV_NAMES})\\}[\\s\\S]+?\\\\end\\{\\k<bareEnvName>\\})`,
  ].join("|"),
  "gi",
);

const MATH_RUN_RE = /(\d*\s*\([a-z0-9+\-−·*× ]+\)(?:\s*[+\-−]\s*\d*[a-z]?)*|\b\d+[a-z](?:\s*[+\-−]\s*\d+[a-z]?)+)/gi;
const EXPLICIT_DELIM_RE = /`|\$|\\{1,2}[(\[]/;
const PROSE_WORD_RE = /\b[A-Za-z\u00C0-\u024F]{3,}\b/g;

// Disjoint token scanner for linear-time bare-inline math extraction.
const TOKEN_RE = new RegExp(
  `${LATEX_CMD_SRC}|\\{(?:[^{}\\n]|\\{[^{}\\n]*\\})*\\}|[A-Za-z0-9]+(?:[_^](?:\\{[^{}\\n]*\\}|[A-Za-z0-9]+))+|[A-Za-z0-9]+(?:\\.[0-9]+)?|\\s+|[=+\\-*/<>^_|≤≥×·→,()\\[\\]&!?:;"'\\u2018-\\u201F]|.`,
  "g",
);
const BINARY_OP_RE = /^[=+\-*/<>^_|≤≥×·→]$/;
const SCRIPT_TOKEN_RE = /[_^]/;
const STOPWORDS = new Set([
  "a", "an", "as", "at", "be", "by", "do", "for", "if", "in", "is", "it",
  "no", "of", "on", "or", "so", "to", "we",
]);

function balanceTrailingBraces(tex: string): string {
  let depth = 0;
  for (let i = 0; i < tex.length; i += 1) {
    if (tex[i] === "\\") {
      i += 1;
      continue;
    }
    if (tex[i] === "{") depth += 1;
    else if (tex[i] === "}" && depth > 0) depth -= 1;
  }
  return depth > 0 && depth <= 3 ? tex + "}".repeat(depth) : tex;
}

/** Normalize LLM escape quirks and Unicode math symbols inside TeX before passing to KaTeX. */
export function cleanTex(tex: string): string {
  const normalized = tex
    .replace(/\\\\n(?![A-Za-z])/g, "\\\\\n")
    .replace(/(?<!\\)\\n(?![A-Za-z])/g, "\n")
    .replace(/[\u2212\u2011−]/g, "-")
    .replace(/≤/g, "\\le ")
    .replace(/≥/g, "\\ge ")
    .replace(/×/g, "\\times ")
    .replace(/·/g, "\\cdot ")
    .replace(/→/g, "\\to ")
    .replace(/[\u202f\u00a0]/g, " ");
  return balanceTrailingBraces(normalized);
}

/** True when a string contains at least one allowlisted LaTeX math command. */
export function hasLatexCommand(text: string): boolean {
  return LATEX_CMD_RE.test(text);
}

/** Render TeX with KaTeX in HTML+MathML mode, tolerating unknown macros without throwing. */
export function renderKatex(tex: string, displayMode: boolean): string {
  try {
    return katex.renderToString(cleanTex(tex), {
      throwOnError: false,
      strict: false,
      output: "htmlAndMathml",
      displayMode,
    });
  } catch {
    return "";
  }
}

function isCurrencyFalsePositive(dollarInner: string): boolean {
  return /^\d[\d,.]*(?:\s+[a-z]{2,}|\s*$)/i.test(dollarInner) && !/[=+\-*/^_<>\\()]/.test(dollarInner);
}

function emitAlgebraRuns(text: string, out: RichSegment[]): void {
  let last = 0;
  for (const m of text.matchAll(MATH_RUN_RE)) {
    const i = m.index ?? 0;
    const run = m[0];
    const inner = run.match(/\(([^)]*)\)/)?.[1];
    // "main(args)" and "(a note)" are text; "2(x + 3)" and "30S + 50D" are math
    if (/[A-Za-z_]{2,}$/.test(text.slice(0, i)) || (inner !== undefined && inner.trim().length > 2 && !/[0-9+\-−·*×]/.test(inner))) {
      continue;
    }
    if (i > last) out.push({ kind: "text", value: text.slice(last, i) });
    out.push({ kind: "math", value: cleanTex(run).replace(/\*/g, "\\cdot "), display: false });
    last = i + run.length;
  }
  if (last < text.length) out.push({ kind: "text", value: text.slice(last) });
}

type Tok = { text: string; start: number; end: number };

function isShortOperand(t: string): boolean {
  if (SCRIPT_TOKEN_RE.test(t) && /^[A-Za-z0-9]/.test(t)) return true;
  if (/^\d+(?:\.\d+)?[A-Za-z]?$/.test(t)) return true;
  if (/^[A-Za-z0-9]$/.test(t)) return true;
  if (/^[A-Z][A-Za-z0-9]$/.test(t)) return true;
  return /^[a-z]\d$/.test(t);
}

function nextNonSpace(toks: Tok[], idx: number): number {
  let j = idx + 1;
  while (j < toks.length && /^\s+$/.test(toks[j].text)) j += 1;
  return j;
}

function prevNonSpace(toks: Tok[], idx: number): number {
  let j = idx - 1;
  while (j >= 0 && /^\s+$/.test(toks[j].text)) j -= 1;
  return j;
}

function canExtendLeft(toks: Tok[], boundaryIdx: number): boolean {
  const prevIdx = prevNonSpace(toks, boundaryIdx);
  if (prevIdx < 0) return false;
  const pt = toks[prevIdx].text;
  const curText = toks[boundaryIdx].text;
  const tight = prevIdx === boundaryIdx - 1;

  if (LATEX_CMD_RE.test(pt) || BINARY_OP_RE.test(pt) || pt === "(" || pt === "[" || pt === "{") return true;
  if (pt.startsWith("{") && tight) return true;
  if (pt === "," || pt === "|") {
    const before = prevNonSpace(toks, prevIdx);
    return before >= 0 && (isShortOperand(toks[before].text) || LATEX_CMD_RE.test(toks[before].text) || toks[before].text.startsWith("{"));
  }
  if (SCRIPT_TOKEN_RE.test(pt) && /^[A-Za-z0-9]/.test(pt)) {
    return BINARY_OP_RE.test(curText) || LATEX_CMD_RE.test(curText) || isShortOperand(curText);
  }
  if (/^[A-Za-z0-9]+$/.test(pt)) {
    const feedsMath = BINARY_OP_RE.test(curText) || LATEX_CMD_RE.test(curText) || SCRIPT_TOKEN_RE.test(curText);
    if (feedsMath && pt.length <= 2 && !STOPWORDS.has(pt.toLowerCase())) return true;
    const before = prevNonSpace(toks, prevIdx);
    if (pt.length === 1 && feedsMath) return true;
    return before >= 0 && (BINARY_OP_RE.test(toks[before].text) || LATEX_CMD_RE.test(toks[before].text) || SCRIPT_TOKEN_RE.test(toks[before].text));
  }
  return false;
}

function canExtendRight(toks: Tok[], boundaryIdx: number): boolean {
  const nextIdx = nextNonSpace(toks, boundaryIdx);
  if (nextIdx >= toks.length) return false;
  const nt = toks[nextIdx].text;
  const curText = toks[boundaryIdx].text;
  const tight = nextIdx === boundaryIdx + 1;

  if (tight && (nt.startsWith("{") || nt === "(" || nt === "[")) return true;
  if (LATEX_CMD_RE.test(nt) || BINARY_OP_RE.test(nt) || nt === "|" || nt === "]") return true;
  if (nt === ",") {
    const after = nextNonSpace(toks, nextIdx);
    if (after >= toks.length) return false;
    const at = toks[after].text;
    return LATEX_CMD_RE.test(at) || isShortOperand(at);
  }
  if (isShortOperand(nt) && !STOPWORDS.has(nt.toLowerCase())) {
    if (BINARY_OP_RE.test(curText) || LATEX_CMD_RE.test(curText) || curText.startsWith("{") || curText === "(" || curText === ",") {
      return true;
    }
    if ((nt.length === 1 || SCRIPT_TOKEN_RE.test(nt)) && (SCRIPT_TOKEN_RE.test(curText) || /^[A-Za-z0-9{}]+$/.test(curText))) {
      return true;
    }
  }
  return false;
}

function emitBareInlineMath(line: string, out: RichSegment[]): void {
  const toks: Tok[] = [];
  for (const m of line.matchAll(TOKEN_RE)) {
    toks.push({ text: m[0], start: m.index ?? 0, end: (m.index ?? 0) + m[0].length });
  }
  const cmdIndices: number[] = [];
  toks.forEach((tok, idx) => {
    if (LATEX_CMD_RE.test(tok.text)) cmdIndices.push(idx);
  });

  let pos = 0;
  let k = 0;
  while (k < cmdIndices.length) {
    const anchor = cmdIndices[k];
    if (toks[anchor].start < pos) {
      k += 1;
      continue;
    }
    let left = anchor;
    while (canExtendLeft(toks, left)) {
      const p = prevNonSpace(toks, left);
      if (toks[p].start < pos) break;
      left = p;
    }
    let right = anchor;
    let parenDepth = 0;
    for (let j = left; j <= right; j += 1) {
      if (toks[j].text === "(") parenDepth += 1;
      else if (toks[j].text === ")") parenDepth -= 1;
    }
    while (true) {
      const n = nextNonSpace(toks, right);
      if (n < toks.length && toks[n].text === ")" && parenDepth > 0) {
        parenDepth -= 1;
        right = n;
        continue;
      }
      if (!canExtendRight(toks, right)) break;
      if (toks[n].text === "(") parenDepth += 1;
      right = n;
    }
    while (k + 1 < cmdIndices.length && cmdIndices[k + 1] <= right) {
      k += 1;
    }
    k += 1;

    while (left < right && toks[left].text === "(" && parenDepth > 0) {
      parenDepth -= 1;
      left = nextNonSpace(toks, left);
    }

    const startChar = toks[left].start;
    const endChar = toks[right].end;
    const frag = line.slice(startChar, endChar).trim();
    if (!frag || !hasLatexCommand(frag)) continue;
    if (startChar > pos) emitAlgebraRuns(line.slice(pos, startChar), out);
    out.push({ kind: "math", value: cleanTex(frag), display: false });
    pos = endChar;
  }
  if (pos < line.length) emitAlgebraRuns(line.slice(pos), out);
}

function emitPlainSegment(raw: string, out: RichSegment[]): void {
  const text = raw.replace(/(?<!\\)\\n(?![A-Za-z])/g, "\n");
  if (!hasLatexCommand(text)) {
    emitAlgebraRuns(text, out);
    return;
  }

  const lines = text.split("\n");
  lines.forEach((line, idx) => {
    if (idx > 0) out.push({ kind: "text", value: "\n" });
    if (!line) return;
    if (!hasLatexCommand(line)) {
      emitAlgebraRuns(line, out);
      return;
    }
    const nonLatex = line.replace(LATEX_STRIP_RE, " ");
    const hasSurroundingProse =
      (nonLatex.match(PROSE_WORD_RE) || []).length >= 3 || /^[A-Z][a-z\u00C0-\u024F]{3,}\s/.test(nonLatex.trim());
    if (!hasSurroundingProse) {
      out.push({ kind: "math", value: cleanTex(line.trim()), display: false });
      return;
    }
    emitBareInlineMath(line, out);
  });
}

function pushTextMerged(out: RichSegment[], seg: RichSegment): void {
  const prev = out[out.length - 1];
  if (seg.kind === "text" && prev?.kind === "text") {
    prev.value += seg.value;
    return;
  }
  out.push(seg);
}

/** Parse code blocks, inline code, explicit TeX delimiters, bare LaTeX blocks/lines, and algebra runs. */
export function parseRichMath(text: string, opts?: { formula?: boolean }): RichSegment[] {
  if (!text) return [];
  if (opts?.formula && !EXPLICIT_DELIM_RE.test(text) && hasLatexCommand(text)) {
    return [{ kind: "math", value: cleanTex(text.trim()), display: true }];
  }

  const out: RichSegment[] = [];
  const push = (seg: RichSegment) => pushTextMerged(out, seg);
  let last = 0;

  for (const m of text.matchAll(RICH_RE)) {
    const i = m.index ?? 0;
    const g = m.groups || {};
    if (g.inlineDollar !== undefined && isCurrencyFalsePositive(g.inlineDollar)) {
      continue;
    }
    if (i > last) {
      const gap: RichSegment[] = [];
      emitPlainSegment(text.slice(last, i), gap);
      gap.forEach(push);
    }
    last = i + m[0].length;

    if (g.block !== undefined) {
      push({ kind: "code-block", value: g.block.replace(/\s+$/, "") });
    } else if (g.inline !== undefined) {
      push({ kind: "code-inline", value: g.inline });
    } else if (g.displayDollar !== undefined || g.bracketMath !== undefined || g.bareEnv !== undefined || g.dollarEnv !== undefined) {
      const rawMath = g.displayDollar ?? g.bracketMath ?? g.bareEnv ?? g.dollarEnv ?? "";
      push({ kind: "math", value: cleanTex(rawMath.trim()), display: true });
    } else {
      push({ kind: "math", value: cleanTex((g.inlineDollar ?? g.parenMath ?? "").trim()), display: false });
    }
  }

  if (last < text.length) {
    const tail: RichSegment[] = [];
    emitPlainSegment(text.slice(last), tail);
    tail.forEach(push);
  }
  return out;
}
