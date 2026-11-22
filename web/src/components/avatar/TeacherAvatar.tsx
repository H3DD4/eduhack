"use client";
import React, { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { SCRIPTS, Segment, toSegments } from "./director";
import {
  buildCharacter,
  CharacterRig,
  PERSONAS,
  personaFor,
  PersonaId,
  readPalette,
  visemeFor,
} from "./rig";
import { browserSTTProvider, browserTTSProvider } from "@/lib/accessibility/profile";

export interface TeacherAvatarProps {
  /** Any system-generated text or directed script to transcribe into the speaking 3D avatar. */
  text?: string;
  /** Optional subject/concept hint to automatically select the matching scientist (Newton, Einstein, Curie, Al-Khwarizmi). */
  hint?: string;
  /** Explicit initial persona override. */
  initialPersona?: PersonaId;
  /** Start in compact bust view (default false = full body, true = bust). */
  compact?: boolean;
  /** Automatically start speaking whenever `text` changes. */
  autoPlay?: boolean;
  /** Show persona switcher chips above the stage. */
  showPersonaPicker?: boolean;
  /** Optional callback when the student asks the avatar a question. Returns the Professor's answer text. */
  onAsk?: (question: string, persona: PersonaId) => Promise<string | void>;
  /** Optional header title or badge. */
  title?: string;
  /** Stage height in CSS pixels. */
  stageHeight?: number;
  speechLanguage?: string;
  speechRate?: number;
  speechInputEnabled?: boolean;
  strictSpeechLanguage?: boolean;
  speechGuideMode?: boolean;
}

const CANNED_ANSWERS: [RegExp, string][] = [
  [
    /apple|fall|gravit/i,
    "Everything with mass pulls on everything else. [think] The Earth is so massive that it pulls the apple down. [apple] [board: F = G m₁ m₂ / r²] [point]",
  ],
  [
    /mass|weight/i,
    "Mass is how much stuff something has. [nod] Weight is the force of gravity on that mass. [board: W = m × g] [point]",
  ],
  [
    /algebra|equation|solve|bracket|expand|distribut/i,
    "Keep the balance! [shrug] Multiply every term inside the brackets, and whatever you do to one side of an equation, do to the other. [board: a(b + c) = ab + ac] [point] [encouraging]",
  ],
  [
    /.*/,
    "Good question! [think] Try it first in your own words, then I will help step by step. [encouraging] [nod]",
  ],
];

export function TeacherAvatar({
  text,
  hint = "",
  initialPersona,
  compact = false,
  autoPlay = false,
  showPersonaPicker = true,
  onAsk,
  title,
  stageHeight,
  speechLanguage = "en-GB",
  speechRate = 1,
  speechInputEnabled = true,
  strictSpeechLanguage = false,
  speechGuideMode = false,
}: TeacherAvatarProps) {
  const defaultPersona = useMemo<PersonaId>(
    () => initialPersona || (hint ? personaFor(hint) : "khwarizmi"),
    [initialPersona, hint]
  );
  const [persona, setPersona] = useState<PersonaId>(defaultPersona);
  const [bust, setBust] = useState<boolean>(compact);
  const [customScript, setCustomScript] = useState<string | null>(null);
  const [idx, setIdx] = useState<number>(0);
  const [playing, setPlaying] = useState<boolean>(false);
  const [rate, setRate] = useState<number>(speechRate);
  const [voiceOn, setVoiceOn] = useState<boolean>(true);
  const [showTranscript, setShowTranscript] = useState<boolean>(false);
  const [board, setBoard] = useState<string | null>(null);
  const [wordAt, setWordAt] = useState<number | null>(null);
  const [question, setQuestion] = useState<string>("");
  const [asking, setAsking] = useState<boolean>(false);
  const [listening, setListening] = useState<boolean>(false);
  const [hasSpeechRec, setHasSpeechRec] = useState<boolean>(false);
  const [speechMessage, setSpeechMessage] = useState("");
  const [webglOk, setWebglOk] = useState<boolean>(true);

  useEffect(() => {
    if (initialPersona) setPersona(initialPersona);
    else if (hint) setPersona(personaFor(hint));
  }, [initialPersona, hint]);

  useEffect(() => {
    setCustomScript(null);
  }, [text]);

  const activeScript = useMemo(() => {
    if (customScript) return customScript;
    if (text && text.trim()) return text;
    return SCRIPTS[persona];
  }, [customScript, text, persona]);

  const queue = useMemo<Segment[]>(
    () => toSegments(activeScript, persona, { greet: !text }),
    [activeScript, persona, text]
  );

  // Refs shared with the Three.js animation loop & speech synthesizer
  const stageRef = useRef<HTMLDivElement | null>(null);
  const rigRef = useRef<CharacterRig | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const speakingRef = useRef<boolean>(false);
  const openRef = useRef<number>(0);
  const boardOnRef = useRef<boolean>(false);
  const bustRef = useRef<boolean>(compact);
  const rateRef = useRef<number>(1);
  const voiceOnRef = useRef<boolean>(true);
  const lookRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const hoverRef = useRef<boolean>(false);
  const wordRef = useRef<{ text: string; at: number }>({ text: "", at: 0 });
  const segRef = useRef<{ text: string; at: number; last: number }>({ text: "", at: 0, last: 0 });
  const tokenRef = useRef<number>(0);

  useEffect(() => {
    bustRef.current = bust;
    const cam = cameraRef.current;
    if (cam) {
      const t = bust ? new THREE.Vector3(0, 2.25, 0) : new THREE.Vector3(0, 1.55, 0);
      cam.position.set(0, t.y + 0.15, bust ? 3.4 : 6.8);
      cam.lookAt(t);
    }
  }, [bust]);

  useEffect(() => {
    rateRef.current = rate;
  }, [rate]);
  useEffect(() => {
    setRate(speechRate);
  }, [speechRate]);

  useEffect(() => {
    voiceOnRef.current = voiceOn;
  }, [voiceOn]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const w = window as any;
      setHasSpeechRec(speechInputEnabled && Boolean(w.SpeechRecognition || w.webkitSpeechRecognition));
    }
  }, [speechInputEnabled]);

  // Mount Three.js scene
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setWebglOk(false);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.style.display = "block";
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    stage.prepend(renderer.domElement);

    const scene = new THREE.Scene();
    sceneRef.current = scene;
    scene.add(new THREE.HemisphereLight(0xffffff, 0x3a4252, 1.4));
    const sun = new THREE.DirectionalLight(0xffffff, 2.2);
    sun.position.set(2.5, 5, 4);
    scene.add(sun);

    const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 50);
    cameraRef.current = camera;
    const target = bustRef.current ? new THREE.Vector3(0, 2.25, 0) : new THREE.Vector3(0, 1.55, 0);
    camera.position.set(0, target.y + 0.15, bustRef.current ? 3.4 : 6.8);
    camera.lookAt(target);

    const resize = () => {
      if (!stage) return;
      const w = Math.max(1, stage.clientWidth);
      const h = Math.max(1, stage.clientHeight);
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(stage);

    const onPointerMove = (e: PointerEvent) => {
      const r = stage.getBoundingClientRect();
      lookRef.current.x = Math.max(-1, Math.min(1, (e.clientX - (r.left + r.width / 2)) / (window.innerWidth / 2)));
      lookRef.current.y = Math.max(-1, Math.min(1, (r.top + r.height * 0.3 - e.clientY) / (window.innerHeight / 2)));
    };
    window.addEventListener("pointermove", onPointerMove, { passive: true });

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    const clock = new THREE.Clock();

    renderer.setAnimationLoop(() => {
      const rig = rigRef.current;
      if (!rig) return;
      const dt = Math.min(clock.getDelta(), 0.05);
      const t = clock.elapsedTime;
      const now = performance.now();
      let vis = visemeFor(" ");
      if (speakingRef.current) {
        const useWord = now - segRef.current.last < 600 && wordRef.current.text;
        const src = useWord ? wordRef.current.text : segRef.current.text;
        const st = useWord ? wordRef.current.at : segRef.current.at;
        const i = Math.floor(((now - st) / 1000) * 14 * rateRef.current);
        vis =
          i >= src.length && useWord
            ? "M"
            : visemeFor(src.charAt(Math.min(src.length - 1, Math.max(0, i))) || " ");
        openRef.current = 0.55 + 0.45 * Math.abs(Math.sin(t * 11));
      } else {
        openRef.current = Math.max(0, openRef.current - dt * 6);
      }
      const off = boardOnRef.current ? (bustRef.current ? -0.55 : -0.85) : 0;
      rig.root.position.x += (off - rig.root.position.x) * Math.min(1, dt * 4);
      rig.update(dt, t, {
        speaking: speakingRef.current,
        open: openRef.current,
        viseme: vis,
        look: lookRef.current,
        hover: hoverRef.current,
        reduced: reduced.matches || document.documentElement.dataset.motion === "reduce",
      });
      renderer.render(scene, camera);
    });

    return () => {
      tokenRef.current++;
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        browserTTSProvider.cancel();
      }
      renderer.setAnimationLoop(null);
      window.removeEventListener("pointermove", onPointerMove);
      ro.disconnect();
      if (rigRef.current) {
        scene.remove(rigRef.current.root);
        rigRef.current.dispose();
        rigRef.current = null;
      }
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  // Swap character rig when persona changes
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    if (rigRef.current) {
      scene.remove(rigRef.current.root);
      rigRef.current.dispose();
    }
    const rig = buildCharacter(persona, readPalette());
    rigRef.current = rig;
    scene.add(rig.root);
  }, [persona]);

  const pickVoice = useCallback(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return null;
    const voices = window.speechSynthesis.getVoices();
    const language = speechLanguage.split("-")[0].toLowerCase();
    const matching = voices.filter((v) => v.lang.toLowerCase().startsWith(language));
    if (!strictSpeechLanguage) {
      const english = voices.filter((v) => v.lang.startsWith("en"));
      return english.find((x) => /male|daniel|george|arthur|thomas|ryan|guy/i.test(x.name)) ||
        english.find((x) => x.lang === "en-GB") || english[0] || voices[0] || null;
    }
    return (
      matching.find((x) => x.lang.toLowerCase() === speechLanguage.toLowerCase()) ||
      matching[0] ||
      null
    );
  }, [speechLanguage, strictSpeechLanguage]);

  const pause = useCallback(() => {
    tokenRef.current++;
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      browserTTSProvider.cancel();
    }
    speakingRef.current = false;
    setPlaying(false);
    setWordAt(null);
  }, []);

  const runSegments = useCallback(
    (list: Segment[], i: number, chain: boolean) => {
      const my = ++tokenRef.current;
      const canSpeak = typeof window !== "undefined" && "speechSynthesis" in window;
      if (canSpeak) browserTTSProvider.cancel();
      const rig = rigRef.current;

      if (i >= list.length || list.length === 0) {
        speakingRef.current = false;
        setPlaying(false);
        setWordAt(null);
        setIdx(0);
        rig?.setEmotion("neutral");
        return;
      }

      const s = list[i];
      setIdx(i);
      setWordAt(null);
      if (s.emotion) rig?.setEmotion(s.emotion);
      s.gestures.forEach((g, n) => {
        setTimeout(() => {
          if (tokenRef.current === my) rigRef.current?.play(g);
        }, n * 900);
      });
      if (s.board !== undefined) {
        boardOnRef.current = Boolean(s.board);
        setBoard(s.board ? s.board.replace(/\$/g, "") : null);
      }

      const next = () => {
        if (tokenRef.current !== my) return;
        speakingRef.current = false;
        setWordAt(null);
        if (chain) {
          setTimeout(() => {
            if (tokenRef.current === my) runSegments(list, i + 1, true);
          }, s.pause);
        } else {
          setPlaying(false);
        }
      };

      if (!s.text) {
        setTimeout(next, 300);
        return;
      }

      segRef.current = { text: s.text, at: performance.now(), last: 0 };
      if (voiceOnRef.current && canSpeak) {
        if (strictSpeechLanguage && !browserTTSProvider.hasVoice(speechLanguage)) {
          setSpeechMessage(`No ${speechLanguage} voice is available on this device. The text remains visible to read.`);
          next();
          return;
        }
        setSpeechMessage("");
        try {
          const u = new SpeechSynthesisUtterance(s.text);
          u.lang = speechLanguage;
          const v = pickVoice();
          if (v) u.voice = v;
          u.rate = 0.96 * rateRef.current;
          u.pitch = persona === "curie" ? 1.15 : 0.9;
          u.onstart = () => {
            if (tokenRef.current === my) {
              speakingRef.current = true;
              segRef.current.at = performance.now();
            }
          };
          u.onboundary = (e) => {
            if (tokenRef.current !== my || (e.name && e.name !== "word")) return;
            wordRef.current = {
              text: s.text.slice(e.charIndex).split(/\s/)[0] || "",
              at: performance.now(),
            };
            segRef.current.last = performance.now();
            setWordAt(e.charIndex);
          };
          u.onend = next;
          u.onerror = () => {
            if (strictSpeechLanguage) {
              setSpeechMessage(`The ${speechLanguage} voice could not read this text. The text remains visible to read.`);
            }
            next();
          };
          speakingRef.current = true;
          browserTTSProvider.speak(u);
          return;
        } catch {
          // Fall through to silent word ticker if speechSynthesis throws
        }
      }

      // Captions-only or fallback word ticker (drives mouth visemes, gestures & word highlight)
      speakingRef.current = true;
      const ws = s.text.split(/(\s+)/);
      let pos = 0;
      let n = 0;
      const ms = 60000 / (170 * rateRef.current);
      const tick = () => {
        if (tokenRef.current !== my) return;
        while (n < ws.length && /^\s+$/.test(ws[n])) {
          pos += ws[n].length;
          n++;
        }
        if (n >= ws.length) {
          next();
          return;
        }
        wordRef.current = { text: ws[n], at: performance.now() };
        segRef.current.last = performance.now();
        setWordAt(pos);
        pos += ws[n].length;
        n++;
        setTimeout(tick, ms + ws[n - 1].length * 12);
      };
      tick();
    },
    [persona, pickVoice, speechLanguage, strictSpeechLanguage]
  );

  const play = useCallback(() => {
    if (!queue.length) return;
    setPlaying(true);
    runSegments(queue, idx >= queue.length ? 0 : idx, true);
  }, [queue, idx, runSegments]);

  const jump = useCallback(
    (targetIdx: number) => {
      if (!queue.length) return;
      const clamped = Math.max(0, Math.min(queue.length - 1, targetIdx));
      if (playing) {
        runSegments(queue, clamped, true);
      } else {
        pause();
        setPlaying(true);
        runSegments(queue, clamped, false);
      }
    },
    [queue, playing, runSegments, pause]
  );

  const sayOnce = useCallback(
    (line: string) => {
      const segs = toSegments(line, persona);
      if (!segs.length) return;
      setCustomScript(line);
      setPlaying(true);
      runSegments(segs, 0, true);
    },
    [persona, runSegments]
  );

  // Auto-play when `text` changes and `autoPlay` is enabled
  useEffect(() => {
    pause();
    setIdx(0);
    setBoard(null);
    boardOnRef.current = false;
    if (autoPlay && queue.length > 0) {
      const timer = setTimeout(() => {
        setPlaying(true);
        runSegments(queue, 0, true);
      }, 150);
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeScript, persona, autoPlay]);

  const onStageClick = () => {
    if (playing) return;
    rigRef.current?.play("poke");
    const lines = [
      "Careful! I was thinking. [surprised]",
      "Yes? Press play and I will explain. [happy]",
      "Eureka! [celebrate]",
      "Hello there! [wave]",
    ];
    if (persona === "newton") lines.push("Did you know my apple story? [apple] Watch it fall.");
    setTimeout(() => sayOnce(lines[Math.floor(Math.random() * lines.length)]), 320);
  };

  const onStageKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === " " || e.key === "k") {
      e.preventDefault();
      playing ? pause() : play();
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      jump(idx + 1);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      jump(idx - 1);
    } else if (e.key === "r") {
      e.preventDefault();
      jump(idx);
    }
  };

  const submitQuestion = async (e: FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (!q || asking) return;
    pause();
    rigRef.current?.play("think");
    setQuestion("");
    if (onAsk) {
      setAsking(true);
      try {
        const reply = await onAsk(q, persona);
        if (reply && reply.trim()) {
          sayOnce(reply);
          return;
        }
      } finally {
        setAsking(false);
      }
    }
    const found = CANNED_ANSWERS.find(([re]) => re.test(q));
    const reply = found ? found[1] : CANNED_ANSWERS[CANNED_ANSWERS.length - 1][1];
    setTimeout(() => sayOnce(reply), 700);
  };

  const startMic = () => {
    const r = browserSTTProvider.create();
    if (!r) {
      setSpeechMessage("Dictation is not available in this browser. You can type your question.");
      return;
    }
    r.lang = speechLanguage;
    r.interimResults = true;
    if (!strictSpeechLanguage) setListening(true);
    r.onstart = () => {
      setListening(true);
      if (strictSpeechLanguage) setSpeechMessage("Listening. Review and edit the transcript before asking.");
    };
    r.onresult = (event) => {
      const transcript = Array.from(event.results).map((result) => result[0]?.transcript || "").join("");
      if (transcript) setQuestion(transcript);
    };
    r.onend = () => setListening(false);
    r.onerror = () => {
      setListening(false);
      if (strictSpeechLanguage) setSpeechMessage("Dictation stopped. You can type or edit your question.");
    };
    try {
      r.start();
    } catch {
      setListening(false);
      setSpeechMessage("Dictation could not start. You can type your question.");
    }
  };

  const currentSeg = queue[Math.min(idx, Math.max(0, queue.length - 1))];
  const progressPct = queue.length ? ((idx + (playing ? 0.5 : 0)) / queue.length) * 100 : 0;
  const resolvedHeight = stageHeight ?? (bust ? 260 : 390);

  // Word-by-word karaoke caption tokens
  const captionWords = useMemo(() => {
    const raw = currentSeg?.text || "";
    let pos = 0;
    return raw.split(/(\s+)/).map((w, i) => {
      const st = pos;
      pos += w.length;
      const active = wordAt !== null && !/^\s+$/.test(w) && wordAt >= st && wordAt < pos;
      return { w, active, key: i };
    });
  }, [currentSeg?.text, wordAt]);

  return (
    <div className="space-y-3" data-component="teacher-avatar">
      {showPersonaPicker && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Choose your 3D teacher">
            {(Object.keys(PERSONAS) as PersonaId[]).map((pid) => (
              <button
                key={pid}
                type="button"
                aria-pressed={persona === pid}
                onClick={() => {
                  pause();
                  setPersona(pid);
                  setCustomScript(null);
                }}
                className="chip !min-h-[36px] !px-3 text-meta"
              >
                {PERSONAS[pid].name}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setBust((b) => !b)}
            className="btn-secondary !min-h-[36px] !px-3 text-meta"
          >
            {bust ? "Full body" : "Bust view"}
          </button>
        </div>
      )}

      <div className="card !overflow-hidden !p-0">
        <div
          ref={stageRef}
          tabIndex={speechGuideMode ? -1 : 0}
          role={speechGuideMode ? undefined : "application"}
          aria-hidden={speechGuideMode || undefined}
          aria-label={`3D Teacher ${PERSONAS[persona].name}. Space to play or pause, arrow keys for sentences, R to replay.`}
          onClick={onStageClick}
          onKeyDown={onStageKeyDown}
          onPointerEnter={() => {
            hoverRef.current = true;
          }}
          onPointerLeave={() => {
            hoverRef.current = false;
          }}
          style={{ height: resolvedHeight }}
          className="relative w-full cursor-pointer bg-soft outline-none focus-visible:ring-4 focus-visible:ring-ink"
        >
          {!webglOk && (
            <div className="grid h-full place-items-center p-4 text-center">
              <p className="font-semibold">
                {PERSONAS[persona].name} · {PERSONAS[persona].field}
              </p>
            </div>
          )}

          <span className="badge pointer-events-none absolute left-3 top-3 bg-surface">
            {title ? `${title} · ` : ""}
            {PERSONAS[persona].name} · {PERSONAS[persona].field}
          </span>

          {playing && (
            <span className="badge pointer-events-none absolute right-3 top-3 bg-hl text-ink">
              {voiceOn ? "🔊 Speaking" : "💬 Captions only"}
            </span>
          )}

          {board && (
            <div className="fade-in pointer-events-none absolute right-3 top-14 max-w-[52%] rounded-card border-2 border-ink bg-surface px-4 py-3 font-mono text-problem shadow-hard">
              <small className="block font-sans text-meta text-ink-muted">Board</small>
              <span>{board}</span>
            </div>
          )}

          <div className="absolute inset-x-0 bottom-0 h-1.5 bg-[rgba(15,23,42,0.12)]">
            <i
              className="block h-full bg-strong transition-[width] duration-300"
              style={{ width: `${Math.min(100, Math.round(progressPct))}%` }}
            />
          </div>
        </div>

        <p
          aria-live="polite"
          className="min-h-[72px] border-t-2 border-ink px-4 py-3 text-problem leading-relaxed"
        >
          {captionWords.map((t) =>
            t.active ? (
              <mark key={t.key} className="rounded bg-hl px-1 text-ink">
                {t.w}
              </mark>
            ) : (
              <React.Fragment key={t.key}>{t.w}</React.Fragment>
            )
          )}
        </p>
        {speechMessage && <p className="px-4 text-meta text-ink-muted" role="status" aria-live="polite">{speechMessage}</p>}

        <div className="flex flex-wrap items-center gap-2 px-4 pb-3">
          <button
            type="button"
            className="btn-primary !min-h-[40px] !px-4"
            onClick={() => (playing ? pause() : play())}
          >
            {playing ? "Pause" : idx > 0 ? "Resume" : "▶ Speak"}
          </button>
          <button
            type="button"
            className="btn-secondary !min-h-[40px] !px-3"
            onClick={() => jump(idx - 1)}
            disabled={idx === 0}
            aria-label="Previous sentence"
          >
            ◀
          </button>
          <button
            type="button"
            className="btn-secondary !min-h-[40px] !px-3"
            onClick={() => jump(idx)}
            aria-label="Replay sentence"
          >
            ↻
          </button>
          <button
            type="button"
            className="btn-secondary !min-h-[40px] !px-3"
            onClick={() => jump(idx + 1)}
            disabled={idx >= queue.length - 1}
            aria-label="Next sentence"
          >
            ▶
          </button>
          <button
            type="button"
            className="btn-secondary !min-h-[40px] !px-3 text-meta"
            onClick={() => {
              const rates = [0.85, 1, 1.2];
              setRate(rates[(rates.indexOf(rate) + 1) % rates.length]);
            }}
          >
            {rate}×
          </button>
          <button
            type="button"
            className={`btn-secondary !min-h-[40px] !px-3 text-meta ${!voiceOn ? "!bg-hl" : ""}`}
            onClick={() => {
              setVoiceOn((v) => !v);
              if (playing) pause();
            }}
          >
            {voiceOn ? "Voice on" : "Captions only"}
          </button>
          <button
            type="button"
            className="btn-secondary !min-h-[40px] !px-3 text-meta"
            onClick={() => setShowTranscript((s) => !s)}
          >
            Transcript
          </button>
          <span className="ml-auto text-meta text-ink-muted">
            {queue.length ? `${Math.min(idx + 1, queue.length)} / ${queue.length}` : "0 / 0"}
          </span>
        </div>

        {showTranscript && (
          <ol className="mx-4 mb-3 max-h-48 list-none overflow-y-auto rounded-control border-2 border-border p-1.5">
            {queue.map((q, i) => (
              <li key={i}>
                <button
                  type="button"
                  onClick={() => jump(i)}
                  className={`w-full rounded-detail px-3 py-1.5 text-left text-meta ${
                    i === idx ? "bg-hl font-semibold text-ink" : "hover:bg-soft"
                  }`}
                >
                  {i + 1}. {q.text || "…"}
                </button>
              </li>
            ))}
          </ol>
        )}

        <form onSubmit={submitQuestion} className="flex flex-wrap items-center gap-2 border-t border-border px-4 py-3">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={`Ask ${PERSONAS[persona].name} a question or paste any text to speak…`}
            aria-label={`Ask ${PERSONAS[persona].name}`}
            className="field !min-h-[40px] flex-1"
          />
          {hasSpeechRec && (
            <button
              type="button"
              onClick={startMic}
              aria-label="Ask by voice"
              className={`btn-secondary !min-h-[40px] !px-3 text-meta ${listening ? "!bg-hl" : ""}`}
            >
              {listening ? "Listening…" : "Mic"}
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              if (question.trim()) {
                sayOnce(question.trim());
                setQuestion("");
              }
            }}
            disabled={!question.trim() || asking}
            className="btn-secondary !min-h-[40px] !px-3 text-meta"
            title="Have the avatar read your typed text aloud verbatim"
          >
            Read aloud
          </button>
          <button type="submit" disabled={!question.trim() || asking} className="btn-primary !min-h-[40px] !px-4">
            {asking ? "Thinking…" : "Ask"}
          </button>
        </form>
      </div>
    </div>
  );
}
