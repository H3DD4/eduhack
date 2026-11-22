import { describe, expect, it } from "vitest";
import { parseRichMath, renderKatex } from "./math";

describe("parseRichMath & renderKatex", () => {
  const LP_FORMULAS = [
    String.raw`\max \; P = 30S + 50D`,
    String.raw`\text{s.t.}\; 2S + D \le 40`,
    String.raw`\;\;\; S + 2D \le 30`,
    String.raw`\;\;\; S \ge 0,\; D \ge 0`,
  ];

  it("renders the user's bare LP formula blocks as display KaTeX without errors or raw commands", () => {
    for (const f of LP_FORMULAS) {
      const segs = parseRichMath(f, { formula: true });
      expect(segs).toEqual([{ kind: "math", value: f, display: true }]);
      const seg = segs[0];
      expect(seg.kind).toBe("math");
      if (seg.kind !== "math") continue;
      const html = renderKatex(seg.value, seg.display);
      expect(html).not.toContain("katex-error");
      expect(html).toContain('class="katex-display"');
      const visualHtml = html.slice(html.indexOf('class="katex-html"'));
      expect(visualHtml).not.toContain("\\max");
      expect(visualHtml).not.toContain("\\le");
      expect(visualHtml).not.toContain("\\ge");
      expect(visualHtml).not.toContain("\\;");
    }
  });

  it("renders bare LP formula lines even without formula=true", () => {
    for (const f of LP_FORMULAS) {
      const segs = parseRichMath(f);
      expect(segs).toHaveLength(1);
      expect(segs[0].kind).toBe("math");
      const html = renderKatex(segs[0].value, false);
      expect(html).not.toContain("katex-error");
    }
  });

  it("renders multi-line bare matrices, cases, and calligraphic formulas", () => {
    const samples = [
      String.raw`X = \begin{pmatrix}0 & 1\\ 1 & 0\end{pmatrix},\quad H = \frac{1}{\sqrt2}\begin{pmatrix}1 & 1\\ 1 & -1\end{pmatrix}`,
      "max   \\; \\sum_{j:(s,j)\\in E} f_{sj} \\\\\nsubject\\;to\\; \\; 0\\le f_{ij}\\le c_{ij} \\;\\;\\forall (i,j)\\in E \\\\\n\\quad\\; \\sum_{i:(i,k)\\in E} f_{ik}=\\sum_{j:(k,j)\\in E} f_{kj} \\;\\;\\forall k\\in V\\setminus\\{s,t\\}",
      "max \\; f_{s1}+f_{s2} \\\\\n\\text{s.t.}\\;\\;\\begin{cases}\n0\\le f_{s1}\\le4,\\\\\n0\\le f_{s2}\\le2\n\\end{cases}",
      String.raw`\mathcal{E}(\rho)= (1-p)\,\rho + p\,X\rho X^{\dagger}`,
      String.raw`c^{\top}x \le b^{\top}y`,
    ];
    for (const s of samples) {
      const segs = parseRichMath(s, { formula: true });
      expect(segs).toHaveLength(1);
      expect(segs[0]).toMatchObject({ kind: "math", display: true });
      const html = renderKatex(segs[0].value, true);
      expect(html).not.toContain("katex-error");
    }
  });

  it("supports \\[...\\] and double-escaped \\\\[...\\\\] with literal \\n / \\\\n", () => {
    const aligned = "Maximise $Z = 3x + 2y$ subject to\n\\[\\begin{aligned}\nx + y &\\le 4 \\\\\nx &\\le 2\n\\end{aligned}\\]\nDone.";
    const aSegs = parseRichMath(aligned);
    expect(aSegs.filter((x) => x.kind === "math")).toHaveLength(2);
    const displaySeg = aSegs.find((x) => x.kind === "math" && x.display);
    expect(displaySeg).toBeTruthy();
    expect(renderKatex(displaySeg!.value, true)).not.toContain("katex-error");

    const ilp =
      String.raw`An **Integer Linear Program** is a problem of the form\n\\[\n\max \; c^{\top}x\\n\text{s.t.}\; Ax \le b,\; x \ge 0\n\\]where \(c\) is a vector.`;
    const segs = parseRichMath(ilp);
    expect(segs.some((s) => s.kind === "text" && s.value.includes("is a problem of the form\n"))).toBe(true);
    const block = segs.find((s) => s.kind === "math" && s.display);
    expect(block).toBeTruthy();
    expect(block!.value).not.toContain("\\n");
    const html = renderKatex(block!.value, true);
    expect(html).not.toContain("katex-error");
    expect(segs.some((s) => s.kind === "math" && !s.display && s.value === "c")).toBe(true);
  });

  it("preserves prose around delimited math inside formula blocks", () => {
    const segs1 = parseRichMath(String.raw`Standard form:  minimise   $c^{\top}x$   subject to   $Ax = b$,   $x \ge 0$.`, { formula: true });
    expect(segs1[0]).toEqual({ kind: "text", value: "Standard form:  minimise   " });
    expect(segs1.filter((s) => s.kind === "math")).toHaveLength(3);

    const segs2 = parseRichMath(String.raw`For any integers \(a,b\): \(a + b = c\) and \(a - b = a + (-b)\).`, { formula: true });
    expect(segs2[0]).toEqual({ kind: "text", value: "For any integers " });
    expect(segs2.filter((s) => s.kind === "math")).toHaveLength(3);
  });

  it("extracts bare inline LaTeX fragments inside prose without swallowing surrounding words", () => {
    const quote = parseRichMath(String.raw`A canonical form LP has constraints written as "\le" inequalities.`);
    expect(quote).toEqual([
      { kind: "text", value: 'A canonical form LP has constraints written as "' },
      { kind: "math", value: "\\le", display: false },
      { kind: "text", value: '" inequalities.' },
    ]);

    const lpDef = parseRichMath(String.raw`Linear Program (LP): maximise c^T x subject to Ax \le b, x \ge 0.`);
    const mathSegs = lpDef.filter((s) => s.kind === "math");
    expect(mathSegs).toHaveLength(1);
    expect(mathSegs[0].value).toBe(String.raw`Ax \le b, x \ge 0`);
    expect(lpDef[0]).toEqual({ kind: "text", value: "Linear Program (LP): maximise c^T x subject to " });
    expect(lpDef[lpDef.length - 1]).toEqual({ kind: "text", value: "." });

    const cTop = parseRichMath(String.raw`Maximise c^\top x \le b.`);
    const cSeg = cTop.find((s) => s.kind === "math");
    expect(cSeg?.value).toBe(String.raw`c^\top x \le b`);

    const leadingSpaceDollar = parseRichMath(String.raw` $ x_1 + 3x_2 \ge 30$`);
    const lsMath = leadingSpaceDollar.find((s) => s.kind === "math");
    expect(lsMath).toEqual({ kind: "math", value: String.raw`x_1 + 3x_2 \ge 30`, display: false });
    expect(renderKatex(lsMath!.value, false)).not.toContain("katex-error");

    const truncatedBrace = parseRichMath(String.raw`\textbf{Dual} \text{ are dual.`, { formula: true });
    expect(renderKatex(truncatedBrace[0].value, true)).not.toContain("katex-error");
  });

  it("does not misclassify currency, code blocks, Windows paths, or ordinary function calls as math", () => {
    const currency = parseRichMath("Each chair yields a profit of $30, each deluxe $50. Two weights.");
    expect(currency.every((s) => s.kind === "text")).toBe(true);

    const code = parseRichMath("Use `C:\\Users\\new\\max` and ```py\nx = 2(x + 3)\n``` and main(args) or (a note) with 2(x + 3).");
    expect(code.filter((s) => s.kind === "code-inline")).toEqual([{ kind: "code-inline", value: "C:\\Users\\new\\max" }]);
    expect(code.filter((s) => s.kind === "code-block")).toHaveLength(1);
    expect(code.filter((s) => s.kind === "math")).toEqual([{ kind: "math", value: "2(x + 3)", display: false }]);
  });
});
