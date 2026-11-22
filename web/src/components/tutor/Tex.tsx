"use client";
/* $…$ / $$…$$ LaTeX via KaTeX, plus a small, safe markdown subset for generated material
   (paragraphs, "- " lists, **bold**, `code`, ``` code blocks). No raw HTML from the model is ever injected. */
import katex from "katex";
import { Fragment, type ReactNode } from "react";

function tex(src: string, display: boolean, key: string | number): ReactNode {
  try {
    const html = katex.renderToString(src, { throwOnError: false, displayMode: display, output: "htmlAndMathml" });
    return <span key={key} className={display ? "math-scroll my-2 block" : "math-scroll inline-block align-middle"} dangerouslySetInnerHTML={{ __html: html }} />;
  } catch {
    return <code key={key}>{src}</code>;
  }
}

function inline(text: string, keyBase = "i"): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\$\$[^$]+\$\$|\$[^$\n]+\$|\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let n = 0;
  for (const m of text.matchAll(re)) {
    const i = m.index ?? 0;
    if (i > last) out.push(text.slice(last, i));
    const tok = m[0];
    const k = `${keyBase}-${n++}`;
    if (tok.startsWith("$$")) out.push(tex(tok.slice(2, -2), true, k));
    else if (tok.startsWith("$")) out.push(tex(tok.slice(1, -1), false, k));
    else if (tok.startsWith("**")) out.push(<strong key={k}>{tok.slice(2, -2)}</strong>);
    else out.push(<code key={k} className="rounded bg-soft px-1 font-mono text-[0.92em]">{tok.slice(1, -1)}</code>);
    last = i + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function Tex({ text, className = "" }: { text: string; className?: string }) {
  return <span className={className}>{inline(text || "")}</span>;
}

export function Md({ text, className = "" }: { text: string; className?: string }) {
  const blocks: ReactNode[] = [];
  const parts = (text || "").split(/```(\w+)?\n?([\s\S]*?)```/g);
  // split() with 2 groups yields [text, lang, code, text, lang, code, ...]
  for (let i = 0; i < parts.length; i += 3) {
    const chunk = parts[i] || "";
    chunk.split(/\n{2,}/).forEach((para, pi) => {
      const lines = para.split("\n").filter((l) => l.trim());
      if (!lines.length) return;
      const key = `${i}-${pi}`;
      if (lines.every((l) => /^\s*[-•*]\s+/.test(l))) {
        blocks.push(<ul key={key} className="my-2 list-disc space-y-1 pl-6">{lines.map((l, li) => <li key={li}>{inline(l.replace(/^\s*[-•*]\s+/, ""), `${key}-${li}`)}</li>)}</ul>);
      } else {
        blocks.push(<p key={key} className="my-2">{lines.map((l, li) => <Fragment key={li}>{li > 0 && <br />}{inline(l, `${key}-${li}`)}</Fragment>)}</p>);
      }
    });
    if (i + 2 < parts.length && parts[i + 2] !== undefined) {
      blocks.push(<CodeBlock key={`code-${i}`} code={parts[i + 2]} language={parts[i + 1]} />);
    }
  }
  return <div className={className}>{blocks}</div>;
}

export function CodeBlock({ code, language }: { code: string; language?: string | null }) {
  return (
    <div className="my-3 overflow-hidden rounded-control border-2 border-ink">
      <div className="flex items-center justify-between bg-ink px-3 py-1 text-meta text-white">
        <span>{language || "code"}</span>
        <button type="button" className="underline-offset-2 hover:underline" onClick={() => navigator.clipboard?.writeText(code)}>Copy</button>
      </div>
      <pre className="overflow-x-auto bg-surface p-3 font-mono text-[0.92rem] leading-6"><code>{code}</code></pre>
    </div>
  );
}
