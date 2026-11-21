import * as THREE from "three";

// Procedural cartoon scientists for ThinkFirst (Newton, Einstein, Marie Curie, al-Khwarizmi), built from three.js
// primitives: no model files. Toon shading + ink outlines to match the UI, colours read from the theme variables.
// The rig supports facial expressions, mouth shapes (visemes), gestures and a falling-apple physics demo.

export type PersonaId = "newton" | "einstein" | "curie" | "khwarizmi";
export type EmotionName = "neutral" | "happy" | "thinking" | "surprised" | "encouraging" | "proud";
export type GestureName = "wave" | "point" | "think" | "shrug" | "celebrate" | "nod" | "apple" | "poke" | "bow";
export type VisemeName = "rest" | "A" | "E" | "O" | "M";

export interface PersonaConfig {
  name: string;
  field: string;
  lang: string;
  hair: "wig" | "wild" | "bun" | "turban";
  facial: "none" | "mustache" | "beard";
  long: boolean;
  prop: "apple" | "chalk" | "flask" | "scroll";
}

export const PERSONAS: Record<PersonaId, PersonaConfig> = {
  newton: { name: "Newton", field: "Physics and motion", lang: "en-GB", hair: "wig", facial: "none", long: false, prop: "apple" },
  einstein: { name: "Einstein", field: "Energy, light and relativity", lang: "en-GB", hair: "wild", facial: "mustache", long: false, prop: "chalk" },
  curie: { name: "Marie Curie", field: "Chemistry and atoms", lang: "fr-FR", hair: "bun", facial: "none", long: true, prop: "flask" },
  khwarizmi: { name: "Al-Khwarizmi", field: "Algebra and algorithms", lang: "ar", hair: "turban", facial: "beard", long: true, prop: "scroll" },
};

/** Pick a persona from a subject or concept title. */
export function personaFor(hint = ""): PersonaId {
  const h = hint.toLowerCase();
  if (/relativ|energy|light|photon|quantum|einstein|e\s*=\s*mc/.test(h)) return "einstein";
  if (/chem|atom|radio|element|molecul|reaction|curie|biolog/.test(h)) return "curie";
  if (/algebra|equation|algorithm|math|fraction|number|bracket|expand|khwarizmi|linear|matri|calcul|derivativ|probab|term|variable|operation/.test(h))
    return "khwarizmi";
  return "newton";
}

export interface Palette {
  coat: string;
  vest: string;
  accent: string;
  ink: string;
  skin: string;
  skinShade: string;
  cloth: string;
  mouth: string;
}

export function readPalette(): Palette {
  const cs = typeof window !== "undefined" ? getComputedStyle(document.documentElement) : null;
  const v = (name: string, fallback: string) => {
    const raw = cs?.getPropertyValue(name).trim();
    return raw && !raw.startsWith("var(") ? raw : fallback;
  };
  return {
    coat: v("--tf-slate", "#334155"),
    vest: v("--tf-strong", "#128C7E"),
    accent: v("--tf-hl", "#25D366"),
    ink: v("--tf-ink", "#0F172A"),
    skin: "#F6CDA8",
    skinShade: "#E9A982",
    cloth: "#FFFFFF",
    mouth: "#7A2331",
  };
}

interface EmotionPose {
  smile: number;
  browY: number;
  browTilt: number;
  squint: number;
  wide: number;
  tilt: number;
}

const EMOTIONS: Record<EmotionName, EmotionPose> = {
  neutral: { smile: 0.35, browY: 0, browTilt: 0, squint: 0, wide: 0, tilt: 0 },
  happy: { smile: 1, browY: 0.02, browTilt: 0.1, squint: 0.18, wide: 0, tilt: 0.05 },
  thinking: { smile: 0, browY: 0.01, browTilt: -0.25, squint: 0.1, wide: 0, tilt: -0.12 },
  surprised: { smile: 0, browY: 0.07, browTilt: 0.25, squint: 0, wide: 0.18, tilt: 0 },
  encouraging: { smile: 0.8, browY: 0.035, browTilt: 0.2, squint: 0.08, wide: 0, tilt: 0.08 },
  proud: { smile: 1, browY: 0.03, browTilt: 0, squint: 0.3, wide: 0, tilt: -0.05 },
};

const VISEMES: Record<VisemeName, { w: number; h: number }> = {
  rest: { w: 1, h: 0 },
  A: { w: 1, h: 1 },
  E: { w: 1.3, h: 0.4 },
  O: { w: 0.6, h: 0.85 },
  M: { w: 1.05, h: 0.02 },
};

/** Map a letter to a mouth shape. */
export function visemeFor(ch: string): VisemeName {
  const c = ch.toLowerCase();
  if ("aáàâä".includes(c)) return "A";
  if ("oóôöuúùwq".includes(c)) return "O";
  if ("eéèêiíyjsztcdgknxh".includes(c)) return "E";
  if ("mbpfv".includes(c)) return "M";
  return "rest";
}

const GESTURE_TIME: Record<GestureName, number> = {
  wave: 1.6,
  point: 2.2,
  think: 2.6,
  shrug: 1.4,
  celebrate: 1.7,
  nod: 0.9,
  apple: 3.2,
  poke: 0.8,
  bow: 1.6,
};

function toonRamp(): THREE.DataTexture {
  const data = new Uint8Array([110, 110, 110, 255, 200, 200, 200, 255, 255, 255, 255, 255]);
  const tex = new THREE.DataTexture(data, 3, 1, THREE.RGBAFormat);
  tex.minFilter = THREE.NearestFilter;
  tex.magFilter = THREE.NearestFilter;
  tex.generateMipmaps = false;
  tex.needsUpdate = true;
  return tex;
}

export interface RigUpdateState {
  speaking: boolean;
  open: number;
  viseme: VisemeName;
  look: { x: number; y: number };
  hover: boolean;
  reduced: boolean;
}

export interface CharacterRig {
  root: THREE.Group;
  persona: PersonaId;
  update: (dt: number, t: number, s: RigUpdateState) => void;
  setEmotion: (e: EmotionName) => void;
  play: (name: GestureName) => void;
  dispose: () => void;
}

interface PartOpts {
  pos?: [number, number, number];
  scale?: [number, number, number];
  rot?: [number, number, number];
  outline?: number | false;
}

export function buildCharacter(persona: PersonaId = "newton", p: Palette = readPalette()): CharacterRig {
  const cfg = PERSONAS[persona];
  const hairColor = persona === "curie" ? "#5B3A29" : persona === "khwarizmi" ? "#2F2A28" : "#EEF0F4";
  const ramp = toonRamp();
  const geoms: THREE.BufferGeometry[] = [];
  const mats: THREE.Material[] = [];
  const outlineMat = new THREE.MeshBasicMaterial({ color: p.ink, side: THREE.BackSide });
  mats.push(outlineMat);
  const cache = new Map<string, THREE.MeshToonMaterial>();
  const toon = (color: string) => {
    let m = cache.get(color);
    if (!m) {
      m = new THREE.MeshToonMaterial({ color, gradientMap: ramp });
      cache.set(color, m);
      mats.push(m);
    }
    return m;
  };
  const basic = (color: string, opacity = 1) => {
    const m = new THREE.MeshBasicMaterial({ color, transparent: opacity < 1, opacity });
    mats.push(m);
    return m;
  };
  const g = <T extends THREE.BufferGeometry>(geo: T): T => {
    geoms.push(geo);
    return geo;
  };
  const part = (geo: THREE.BufferGeometry, color: string, o: PartOpts = {}) => {
    const mesh = new THREE.Mesh(g(geo), toon(color));
    if (o.pos) mesh.position.set(...o.pos);
    if (o.scale) mesh.scale.set(...o.scale);
    if (o.rot) mesh.rotation.set(...o.rot);
    if (o.outline !== false) {
      const out = new THREE.Mesh(geo, outlineMat);
      out.scale.setScalar(typeof o.outline === "number" ? o.outline : 1.06);
      mesh.add(out);
    }
    return mesh;
  };
  const sphere = (r: number, seg = 28) => new THREE.SphereGeometry(r, seg, Math.round(seg * 0.75));
  const capsule = (r: number, len: number) => new THREE.CapsuleGeometry(r, len, 6, 16);

  let seed = 7;
  const rand = () => {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  };
  const root = new THREE.Group();
  const body = new THREE.Group();
  root.add(body);
  const shadow = new THREE.Mesh(g(new THREE.CircleGeometry(0.85, 40)), basic(p.ink, 0.16));
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.set(0.12, 0.005, 0.1);
  shadow.scale.set(1, 0.7, 1);
  root.add(shadow);

  // ---------- legs or long garment ----------
  if (cfg.long) {
    const robe = persona === "curie" ? "#3B2F3A" : p.cloth;
    body.add(part(new THREE.CylinderGeometry(0.6, 0.76, 0.72, 32, 1, true), robe, { pos: [0, 0.36, 0], outline: 1.03 }));
    body.add(part(new THREE.CircleGeometry(0.76, 32), robe, { pos: [0, 0.005, 0], rot: [Math.PI / 2, 0, 0], outline: false }));
    for (const sx of [-1, 1]) body.add(part(sphere(0.13), "#1B1F2A", { pos: [sx * 0.2, 0.06, 0.68], scale: [1, 0.5, 1.4] }));
  } else {
    for (const sx of [-1, 1]) {
      body.add(part(capsule(0.12, 0.28), persona === "einstein" ? "#4B5563" : p.cloth, { pos: [sx * 0.17, 0.3, 0] }));
      body.add(part(capsule(0.14, 0.22), p.ink, { pos: [sx * 0.17, 0.6, 0], outline: 1.04 }));
      const shoe = part(sphere(0.15), "#1B1F2A", { pos: [sx * 0.18, 0.08, 0.07], scale: [1, 0.55, 1.45] });
      if (persona === "newton") shoe.add(part(new THREE.BoxGeometry(0.11, 0.05, 0.04), p.accent, { pos: [0, 0.12, 0.12], outline: 1.15 }));
      body.add(shoe);
    }
  }

  // ---------- torso ----------
  const torso = new THREE.Group();
  torso.position.y = 0.72;
  body.add(torso);
  const coat = persona === "khwarizmi" ? p.cloth : persona === "curie" ? "#3B2F3A" : p.coat;
  torso.add(part(new THREE.CylinderGeometry(0.44, 0.62, 0.95, 32), coat, { pos: [0, 0.42, 0], outline: 1.04 }));
  torso.add(part(sphere(0.45), coat, { pos: [0, 0.86, 0], scale: [1.05, 0.55, 0.9], outline: 1.04 }));
  if (persona === "newton") {
    torso.add(part(sphere(0.3), p.vest, { pos: [0, 0.5, 0.36], scale: [0.9, 1.45, 0.42], outline: 1.05 }));
    for (let i = 0; i < 3; i++) torso.add(part(sphere(0.035, 12), p.accent, { pos: [0, 0.68 - i * 0.16, 0.49], outline: 1.3 }));
    torso.add(part(sphere(0.18), p.cloth, { pos: [0, 0.98, 0.25], scale: [1.15, 0.65, 0.7] }));
    torso.add(part(new THREE.ConeGeometry(0.13, 0.26, 16), p.cloth, { pos: [0, 0.8, 0.33], rot: [Math.PI + 0.25, 0, 0], outline: 1.08 }));
  } else if (persona === "einstein") {
    torso.add(part(sphere(0.3), p.cloth, { pos: [0, 0.62, 0.34], scale: [0.75, 1.05, 0.42], outline: 1.05 }));
    torso.add(part(new THREE.ConeGeometry(0.07, 0.42, 4), p.vest, { pos: [0, 0.6, 0.47], rot: [Math.PI, 0, 0], outline: 1.1 }));
  } else if (persona === "curie") {
    torso.add(part(sphere(0.16), p.cloth, { pos: [0, 0.98, 0.22], scale: [1.4, 0.45, 0.8] }));
    torso.add(part(sphere(0.05, 12), p.accent, { pos: [0, 0.92, 0.36], outline: 1.2 }));
  } else {
    torso.add(part(new THREE.BoxGeometry(0.14, 0.9, 0.05), p.vest, { pos: [0.16, 0.45, 0.47], rot: [0.12, 0, 0], outline: 1.05 }));
    torso.add(part(new THREE.TorusGeometry(0.47, 0.06, 10, 40), p.accent, { pos: [0, 0.35, 0], rot: [Math.PI / 2, 0, 0], outline: 1.08 }));
  }
  const pin = part(new THREE.OctahedronGeometry(0.06), p.accent, { pos: [0.27, 0.72, 0.42], rot: [0, 0, Math.PI / 4], outline: 1.25 });
  if (persona !== "khwarizmi") torso.add(pin);

  // ---------- arms ----------
  const arm = (side: number) => {
    const pivot = new THREE.Group();
    pivot.position.set(side * 0.5, 0.86, 0);
    pivot.add(part(capsule(0.12, 0.42), coat, { pos: [0, -0.3, 0], outline: 1.06 }));
    pivot.add(part(new THREE.CylinderGeometry(0.155, 0.155, 0.13, 20), persona === "khwarizmi" ? p.accent : p.cloth, { pos: [0, -0.6, 0], outline: 1.06 }));
    pivot.add(part(sphere(0.12), p.skin, { pos: [0, -0.72, 0.02] }));
    pivot.rotation.z = side * 0.18;
    torso.add(pivot);
    return pivot;
  };
  const left = arm(-1);
  const right = arm(1);

  const prop = new THREE.Group();
  prop.position.set(0, -0.76, 0.16);
  if (cfg.prop === "apple") {
    prop.add(part(sphere(0.14), "#E5484D", { scale: [1.05, 0.95, 1.05] }));
    prop.add(part(new THREE.CylinderGeometry(0.012, 0.012, 0.09, 6), "#6B4226", { pos: [0, 0.16, 0], outline: 1.4 }));
    prop.add(part(sphere(0.05, 12), "#2BB673", { pos: [0.06, 0.18, 0], scale: [1.4, 0.4, 0.8], rot: [0, 0, -0.5], outline: 1.2 }));
  } else if (cfg.prop === "chalk") {
    prop.add(part(new THREE.CylinderGeometry(0.035, 0.035, 0.22, 10), "#FFFFFF", { rot: [0.6, 0, 0.4], outline: 1.2 }));
  } else if (cfg.prop === "flask") {
    prop.add(part(sphere(0.13), p.accent, { pos: [0, -0.02, 0], outline: 1.08 }));
    prop.add(part(new THREE.CylinderGeometry(0.045, 0.045, 0.16, 12), "#DDE7F0", { pos: [0, 0.16, 0], outline: 1.15 }));
  } else {
    prop.add(part(new THREE.CylinderGeometry(0.06, 0.06, 0.34, 14), "#F3E5C0", { rot: [0, 0, Math.PI / 2], outline: 1.1 }));
    for (const sx of [-1, 1])
      prop.add(part(new THREE.CylinderGeometry(0.075, 0.075, 0.03, 14), "#8B5E34", { pos: [sx * 0.18, 0, 0], rot: [0, 0, Math.PI / 2], outline: 1.1 }));
  }
  right.add(prop);
  const propHome = prop.position.clone();

  // ---------- head ----------
  const head = new THREE.Group();
  head.position.y = 1.0;
  torso.add(head);
  head.add(part(sphere(0.5, 36), p.skin, { pos: [0, 0.5, 0], outline: 1.035 }));
  if (cfg.hair === "wig") {
    head.add(part(sphere(0.52, 32), hairColor, { pos: [0, 0.87, -0.06], scale: [1.02, 0.55, 1.0], outline: 1.04 }));
    head.add(part(sphere(0.55, 32), hairColor, { pos: [0, 0.48, -0.2], scale: [1.0, 1.05, 0.8], outline: 1.04 }));
    for (const sx of [-1, 1])
      (
        [
          [0.56, 0.5, -0.02],
          [0.6, 0.24, -0.06],
          [0.58, -0.02, -0.1],
          [0.5, -0.24, -0.14],
        ] as [number, number, number][]
      ).forEach(([x, y, z], i) => head.add(part(sphere(0.19 - i * 0.012, 20), hairColor, { pos: [sx * x, y, z], outline: 1.07 })));
    (
      [
        [-0.22, -0.18],
        [0.22, -0.18],
        [0, -0.26],
      ] as [number, number][]
    ).forEach(([x, y]) => head.add(part(sphere(0.2, 20), hairColor, { pos: [x, y, -0.42], outline: 1.07 })));
  } else if (cfg.hair === "wild") {
    head.add(part(sphere(0.5, 28), hairColor, { pos: [0, 0.7, -0.12], scale: [1.08, 0.75, 0.95], outline: 1.04 }));
    for (let i = 0; i < 22; i++) {
      const a = (i / 22) * Math.PI * 2;
      const r = 0.55 + rand() * 0.12;
      const y = 0.55 + Math.sin(a) * 0.38;
      const x = Math.cos(a) * r;
      if (y < 0.35 && Math.abs(x) < 0.3) continue;
      head.add(part(sphere(0.13 + rand() * 0.07, 14), hairColor, { pos: [x, y, -0.15 - rand() * 0.15], outline: 1.08 }));
    }
  } else if (cfg.hair === "bun") {
    head.add(part(sphere(0.53, 32), hairColor, { pos: [0, 0.72, -0.08], scale: [1.02, 0.7, 0.98], outline: 1.04 }));
    head.add(part(sphere(0.24, 24), hairColor, { pos: [0, 1.02, -0.32], outline: 1.06 }));
    for (const sx of [-1, 1]) head.add(part(sphere(0.18, 18), hairColor, { pos: [sx * 0.46, 0.5, -0.05], outline: 1.07 }));
  } else {
    head.add(part(new THREE.TorusGeometry(0.42, 0.16, 16, 40), p.cloth, { pos: [0, 0.86, -0.04], rot: [Math.PI / 2 - 0.12, 0, 0], outline: 1.05 }));
    head.add(part(sphere(0.43, 28), p.cloth, { pos: [0, 0.98, -0.06], scale: [1, 0.6, 1], outline: 1.04 }));
    head.add(part(sphere(0.06, 12), p.accent, { pos: [0, 0.88, 0.6], outline: 1.2 }));
  }
  if (cfg.facial === "beard") {
    head.add(part(sphere(0.36, 28), hairColor, { pos: [0, 0.08, 0.18], scale: [1.05, 0.8, 0.85], outline: 1.04 }));
  }

  const eyes: THREE.Group[] = [];
  const pupils: THREE.Mesh[] = [];
  for (const sx of [-1, 1]) {
    const eye = new THREE.Group();
    eye.position.set(sx * 0.17, 0.54, 0.47);
    eye.add(part(sphere(0.115, 24), "#FFFFFF", { scale: [1, 1.12, 0.55], outline: 1.1 }));
    const pupil = new THREE.Mesh(g(sphere(0.06, 16)), basic(p.ink));
    pupil.position.set(0, -0.01, 0.055);
    pupil.scale.set(1, 1.15, 0.5);
    const shine = new THREE.Mesh(g(sphere(0.02, 10)), basic("#FFFFFF"));
    shine.position.set(0.022, 0.03, 0.03);
    pupil.add(shine);
    eye.add(pupil);
    head.add(eye);
    eyes.push(eye);
    pupils.push(pupil);
  }
  const browColor = persona === "curie" || persona === "khwarizmi" ? hairColor : p.ink;
  const brows = [-1, 1].map((sx) => {
    const b = part(capsule(0.028, 0.13), browColor, { pos: [sx * 0.18, 0.7, 0.47], rot: [0, 0, Math.PI / 2], outline: false });
    head.add(b);
    return { mesh: b, side: sx };
  });
  head.add(part(sphere(0.075, 18), p.skinShade, { pos: [0, 0.44, 0.5], scale: [1, 0.9, 0.9], outline: 1.1 }));
  if (cfg.facial === "mustache") {
    for (const sx of [-1, 1])
      head.add(part(sphere(0.1, 16), hairColor, { pos: [sx * 0.08, 0.35, 0.47], scale: [1.3, 0.55, 0.6], rot: [0, 0, sx * -0.25], outline: 1.08 }));
  }
  for (const sx of [-1, 1]) {
    const blush = new THREE.Mesh(g(sphere(0.07, 14)), basic("#F28B82", 0.45));
    blush.position.set(sx * 0.28, 0.37, 0.47);
    blush.scale.set(1.2, 0.7, 0.4);
    head.add(blush);
  }
  const mouthY = cfg.facial === "mustache" ? 0.24 : 0.27;
  const mouth = part(sphere(0.1, 20), p.mouth, { pos: [0, mouthY, 0.465], scale: [1.2, 0.18, 0.4], outline: 1.12 });
  head.add(mouth);
  const smile = new THREE.Mesh(g(new THREE.TorusGeometry(0.11, 0.018, 8, 24, Math.PI)), basic(p.ink));
  smile.position.set(0, mouthY + 0.03, 0.49);
  smile.rotation.z = Math.PI;
  head.add(smile);

  const bubble = new THREE.Group();
  bubble.position.set(0.7, 1.15, 0.1);
  bubble.add(part(sphere(0.07, 12), "#FFFFFF", { pos: [-0.25, -0.25, 0], outline: 1.15 }));
  bubble.add(part(sphere(0.11, 14), "#FFFFFF", { pos: [-0.12, -0.1, 0], outline: 1.12 }));
  bubble.add(part(sphere(0.22, 20), "#FFFFFF", { pos: [0.12, 0.12, 0], scale: [1.3, 1, 0.6], outline: 1.06 }));
  bubble.add(part(sphere(0.05, 10), p.accent, { pos: [0.12, 0.13, 0.13], outline: 1.2 }));
  bubble.visible = false;
  head.add(bubble);

  let emotion: EmotionName = "neutral";
  const em: EmotionPose = { ...EMOTIONS.neutral };
  let gesture: { name: GestureName; t: number } | null = null;
  let blinkIn = 2 + Math.random() * 3;
  let blink = 0;
  let idleIn = 6 + Math.random() * 4;
  let idleLook = { x: 0, y: 0, t: 0 };
  const apple = { y: 0, vy: 0, z: 0, active: false };
  const lerp = (a: number, b: number, k: number) => a + (b - a) * k;
  const setEmotion = (e: EmotionName) => {
    emotion = e;
  };
  const play = (name: GestureName) => {
    gesture = { name, t: 0 };
    if (name === "apple") {
      apple.active = true;
      apple.y = 0;
      apple.vy = 0;
      apple.z = 0;
    }
    if (name === "poke") emotion = "surprised";
    if (name === "celebrate") emotion = "happy";
    if (name === "think") emotion = "thinking";
  };

  const update = (dt: number, t: number, s: RigUpdateState) => {
    const calm = s.reduced ? 0 : 1;
    const k = Math.min(1, dt * 9);
    const target = EMOTIONS[emotion] || EMOTIONS.neutral;
    (Object.keys(em) as (keyof EmotionPose)[]).forEach((key) => {
      em[key] = lerp(em[key], target[key], Math.min(1, dt * 6));
    });
    let gName: GestureName | null = null;
    let gp = 0;
    if (gesture) {
      gesture.t += dt;
      gp = gesture.t / GESTURE_TIME[gesture.name];
      gName = gesture.name;
      if (gp >= 1) {
        if (gesture.name === "poke" || gesture.name === "think") emotion = "neutral";
        gesture = null;
        gName = null;
      }
    }
    const bell = gName ? Math.sin(Math.min(1, gp) * Math.PI) : 0;
    const hold = gName ? Math.min(1, Math.min(gp, 1 - gp) * 5) : 0;

    idleIn -= dt;
    if (idleIn <= 0 && !s.speaking && !gName) {
      idleIn = 6 + Math.random() * 6;
      idleLook = { x: (Math.random() - 0.5) * 1.4, y: (Math.random() - 0.6) * 0.8, t: 1.4 };
    }
    idleLook.t = Math.max(0, idleLook.t - dt);
    const lx = idleLook.t > 0 ? idleLook.x : s.look.x;
    const ly = idleLook.t > 0 ? idleLook.y : s.look.y;

    torso.scale.y = 1 + 0.015 * Math.sin(t * 2.1) * calm;
    let jump = 0;
    let squash = 1;
    if (gName === "celebrate" && calm) jump = Math.max(0, Math.sin(gp * Math.PI * 2)) * 0.35;
    if (gName === "poke") squash = 1 - 0.12 * Math.sin(gp * Math.PI * 3) * (1 - gp);
    if (gName === "bow") torso.rotation.x = lerp(torso.rotation.x, 0.45 * bell, k);
    else torso.rotation.x = lerp(torso.rotation.x, 0, k);
    body.position.y = jump + 0.025 * Math.sin(t * 2.1) * calm;
    body.scale.set(2 - squash, squash, 2 - squash);
    shadow.scale.set(1 - jump * 0.8, 0.7 - jump * 0.5, 1);

    let nod = 0;
    if (gName === "nod") nod = Math.sin(gp * Math.PI * 4) * 0.18 * calm;
    if (s.speaking) nod += 0.04 * Math.sin(t * 6) * calm;
    const lookDownAtApple = gName === "apple" ? Math.min(1, gp * 3) : 0;
    head.rotation.y = lerp(head.rotation.y, (lx * 0.45 + (gName === "point" ? 0.35 * hold : 0)) * (s.reduced ? 0.4 : 1), k);
    head.rotation.x = lerp(head.rotation.x, -ly * 0.18 + nod + lookDownAtApple * 0.35 + (gName === "think" ? -0.15 * hold : 0), k);
    head.rotation.z = lerp(head.rotation.z, em.tilt + 0.04 * Math.sin(t * 1.3) * calm + (gName === "shrug" ? 0.15 * bell : 0), k);
    pupils.forEach((pu) => {
      const px = gName === "think" ? 0.03 : gName === "point" ? 0.035 : lx * 0.03;
      const py = gName === "think" ? 0.035 : gName === "apple" ? -0.03 : -0.01 + ly * 0.025;
      pu.position.x = lerp(pu.position.x, px, k);
      pu.position.y = lerp(pu.position.y, py, k);
    });

    blinkIn -= dt;
    if (blinkIn <= 0) {
      blink = 1;
      blinkIn = 2.2 + Math.random() * 3.5;
    }
    blink = Math.max(0, blink - dt * 7);
    const open = (1 - Math.sin(Math.min(1, blink) * Math.PI) * 0.92) * (1 - em.squint) * (1 + em.wide);
    eyes.forEach((e) => {
      e.scale.y = open;
      e.scale.x = 1 + em.wide * 0.5;
    });

    brows.forEach(({ mesh, side }) => {
      const y = 0.7 + em.browY + (s.speaking ? 0.02 + 0.015 * Math.sin(t * 3) : 0) + (gName === "shrug" ? 0.05 * bell : 0);
      mesh.position.y = lerp(mesh.position.y, y, k);
      const asym = emotion === "thinking" ? (side < 0 ? 0.25 : -0.15) : 0;
      mesh.rotation.z = lerp(mesh.rotation.z, Math.PI / 2 + side * -em.browTilt + asym, k);
    });

    const vis = s.speaking ? VISEMES[s.viseme] : VISEMES.rest;
    const openAmt = s.speaking ? Math.max(0.1, s.open) * vis.h : emotion === "surprised" ? 0.55 : 0;
    const mw = s.speaking ? vis.w : emotion === "surprised" ? 0.6 : 1;
    mouth.scale.y = lerp(mouth.scale.y, 0.1 + openAmt * 0.9, Math.min(1, dt * 20));
    mouth.scale.x = lerp(mouth.scale.x, 1.15 * mw, Math.min(1, dt * 20));
    const showSmile = !s.speaking && emotion !== "surprised" && em.smile > 0.2;
    smile.visible = showSmile;
    mouth.visible = !showSmile || openAmt > 0.05;
    smile.scale.set(0.8 + em.smile * 0.5, 0.4 + em.smile * 0.9, 1);

    const L = { x: 0.04 * Math.sin(t * 1.6) * calm, z: -0.18 };
    const R = { x: -0.3 + 0.04 * Math.sin(t * 1.6 + 1) * calm, z: 0.18 };
    if (s.speaking && !gName && calm) {
      L.x = -0.9 - 0.25 * Math.sin(t * 2.4);
      L.z = -0.35 - 0.1 * Math.sin(t * 1.7);
      R.x = -0.5;
    }
    if (s.hover && !s.speaking && !gName && calm) {
      L.x = -0.2;
      L.z = -2.5 + 0.28 * Math.sin(t * 11);
    }
    switch (gName) {
      case "wave":
        L.x = -0.2;
        L.z = -2.5 + 0.3 * Math.sin(t * 12) * calm;
        break;
      case "point":
        R.x = -1.35 * hold;
        R.z = 0.18 + 0.55 * hold;
        break;
      case "think":
        L.x = -2.1 * hold;
        L.z = 0.55 * hold - 0.18 * (1 - hold);
        break;
      case "shrug":
        L.z = -0.18 - 0.7 * bell;
        R.z = 0.18 + 0.7 * bell;
        L.x = R.x = -0.4 * bell;
        break;
      case "celebrate":
        L.z = -0.18 - 2.4 * hold;
        R.z = 0.18 + 2.4 * hold;
        break;
      case "bow":
        L.x = -0.3 * bell;
        R.x = -0.5 * bell;
        break;
      case "apple":
        R.x = 0;
        R.z = 0.18;
        break;
      case "poke":
        L.z = -0.18 - 0.5 * bell;
        R.z = 0.18 + 0.5 * bell;
        break;
      default:
        break;
    }
    left.rotation.x = lerp(left.rotation.x, L.x, k);
    left.rotation.z = lerp(left.rotation.z, L.z, k);
    right.rotation.x = lerp(right.rotation.x, R.x, k);
    right.rotation.z = lerp(right.rotation.z, R.z, k);

    if (apple.active) {
      const ground = -1.44 - propHome.y;
      if (gp < 0.72) {
        apple.vy -= 9.8 * 0.55 * dt;
        apple.y += apple.vy * dt;
        apple.z = Math.min(0.35, apple.z + dt * 0.5);
        if (apple.y < ground) {
          apple.y = ground;
          apple.vy = -apple.vy * 0.45;
          if (Math.abs(apple.vy) > 0.4) emotion = "surprised";
        }
      } else {
        apple.y = lerp(apple.y, 0, Math.min(1, dt * 6));
        apple.z = lerp(apple.z, 0, Math.min(1, dt * 6));
        if (gp > 0.8) emotion = "happy";
      }
      if (!gName) {
        apple.active = false;
        apple.y = 0;
        apple.z = 0;
        emotion = "neutral";
      }
      prop.position.set(propHome.x, propHome.y + apple.y, propHome.z + apple.z);
    } else {
      prop.position.lerp(propHome, Math.min(1, dt * 8));
    }
    prop.rotation.y += dt * 0.6 * calm;
    bubble.visible = gName === "think";
    if (bubble.visible) bubble.position.y = 1.15 + 0.03 * Math.sin(t * 3);
  };

  const dispose = () => {
    geoms.forEach((x) => x.dispose());
    mats.forEach((x) => x.dispose());
    ramp.dispose();
  };
  return { root, persona, update, setEmotion, play, dispose };
}
