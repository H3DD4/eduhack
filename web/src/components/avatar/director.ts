import { EmotionName, GestureName, PersonaId } from "./rig";

export interface Segment {
  text: string;
  gestures: GestureName[];
  pause: number;
  emotion?: EmotionName;
  board?: string | null;
}

const EMOTION_TAGS: EmotionName[] = ["happy", "thinking", "surprised", "encouraging", "proud", "neutral"];
const GESTURE_TAGS: GestureName[] = ["wave", "point", "think", "shrug", "celebrate", "nod", "apple", "bow"];
const TAG = /\[([a-z]+)(?::\s*([^\]]*))?\]/gi;

/** Make text speakable: drop markdown and LaTeX markup while keeping math readable out loud. */
export function speakable(t: string): string {
  return (t || "")
    .replace(/\$\$?([^$]+)\$\$?/g, "$1")
    .replace(/\\frac\{([^}]*)\}\{([^}]*)\}/g, "$1 over $2")
    .replace(/\\cdot|\\times|×|·/g, " times ")
    .replace(/\\div|÷/g, " divided by ")
    .replace(/√/g, " square root of ")
    .replace(/\^2\b|²/g, " squared")
    .replace(/\^3\b|³/g, " cubed")
    .replace(/\^\{?([^}\s]+)\}?/g, " to the power $1")
    .replace(/_\{?([^}\s]+)\}?/g, " $1")
    .replace(/\\[a-zA-Z]+/g, " ")
    .replace(/[*_#`{}]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function hasDirections(script: string): boolean {
  return /\[(?:[a-z]+)(?::[^\]]*)?\]/i.test(script);
}

export function parseScript(script: string): Segment[] {
  const chunks = (script || "")
    .replace(/\s+/g, " ")
    .trim()
    .split(/(?<=[.!?…](?:\s*\[[^\]]*\])*)\s+(?=[^\s[])/);
  return chunks
    .map((chunk) => {
      const seg: Segment = { text: "", gestures: [], pause: 250 };
      const plain = chunk.replace(TAG, (_m, name: string, arg?: string) => {
        const n = name.toLowerCase();
        if (EMOTION_TAGS.includes(n as EmotionName)) seg.emotion = n as EmotionName;
        else if (GESTURE_TAGS.includes(n as GestureName)) seg.gestures.push(n as GestureName);
        else if (n === "board") seg.board = arg && arg.trim() ? arg.trim() : null;
        else if (n === "pause") seg.pause += 700;
        return " ";
      });
      seg.text = speakable(plain);
      if (!seg.text) seg.pause += 600;
      return seg;
    })
    .filter((s) => s.text || s.gestures.length || s.emotion || s.board !== undefined);
}

/** Add stage directions to any system-generated plain text (lessons, hints, feedback, diagnostics) so the avatar feels alive. */
export function autoDirect(text: string, persona: PersonaId, opts: { greet?: boolean } = {}): Segment[] {
  const clean = (text || "").replace(/\s+/g, " ").trim();
  if (!clean) return [];
  const raw = clean.split(/(?<=[.!?…])\s+(?=\S)/);
  let appleUsed = false;
  const segs: Segment[] = raw.map((sentence, i) => {
    const seg: Segment = { text: speakable(sentence), gestures: [], pause: 250 };
    const math =
      sentence.match(/\$([^$]+)\$/) ||
      sentence.match(/([A-Za-z0-9()\s+\-*/×·−]+\s*=\s*[A-Za-z0-9()\s+\-*/×·−^²³]+)/) ||
      sentence.match(/(\b\d+\s*\([a-z0-9+\-−·*× ]+\))/i);
    if (math) {
      seg.board = math[0].trim().slice(0, 48);
      seg.gestures.push("point");
    }
    if (i === 0 && (opts.greet || /^(hello|hi|hey|bonjour|salut|peace|welcome)\b/i.test(sentence))) {
      seg.gestures.push("wave");
    }
    if (/\?\s*$/.test(sentence)) {
      seg.gestures.push("think");
      seg.emotion = "thinking";
    }
    if (persona === "newton" && !appleUsed && /gravit|fall|apple|weight|drop/i.test(sentence)) {
      seg.gestures.push("apple");
      appleUsed = true;
    }
    if (/\b(great|well done|good job|you can|you've got|correct|solid|demonstrated|equivalent)\b/i.test(sentence)) {
      seg.emotion = "encouraging";
    }
    if (/\b(surpris|amazing|imagine|notice|careful|check)\b/i.test(sentence)) {
      seg.emotion = seg.emotion ?? "surprised";
    }
    if (i > 0 && i % 3 === 0 && !seg.gestures.length) seg.gestures.push("nod");
    return seg;
  });
  if (segs.length) {
    const last = segs[segs.length - 1];
    last.emotion = last.emotion ?? "encouraging";
  }
  return segs;
}

export function toSegments(script: string, persona: PersonaId, opts: { greet?: boolean } = {}): Segment[] {
  if (!script || !script.trim()) return [];
  return hasDirections(script) ? parseScript(script) : autoDirect(script, persona, opts);
}

export const SCRIPTS: Record<PersonaId, string> = {
  newton:
    "Hello, I am Isaac Newton! [wave] [happy] Today: my three laws of motion. First, an object keeps doing what it is doing unless a force acts on it. [nod] Second, force equals mass times acceleration. [board: F = m × a] [point] Push a trolley, then a car, with the same force: the car barely moves. [shrug] Third, every action has an equal and opposite reaction. [board: F₁ = −F₂] [point] And gravity? Watch my apple. [apple] [board:] It falls because the Earth pulls on it. [surprised] Now try one yourself. [encouraging] [nod]",
  einstein:
    "Hello, I am Albert Einstein! [wave] Energy and mass are two faces of the same thing. [board: E = m c²] [point] Because the speed of light is huge, a tiny mass holds a huge amount of energy. [surprised] Imagine riding next to a beam of light. [think] Curious? Ask me a question. [encouraging]",
  curie:
    "Bonjour, I am Marie Curie! [wave] [happy] Everything around you is made of atoms. [nod] Some atoms are unstable and give off energy: that is radioactivity. [board: Radium, Ra] [point] I discovered two elements, polonium and radium. [proud] Science needs patience. [encouraging] [bow]",
  khwarizmi:
    "Peace be upon you, I am al-Khwarizmi. [bow] The word algebra comes from my book. [proud] An equation is a balance: what you do to one side, do to the other. [board: 3x + 5 = 20] [point] Take away 5 from both sides. [board: 3x = 15] Now divide by 3. [board: x = 5] [celebrate] You just solved it, step by step. [encouraging]",
};
