export type AccessibilityProfile = {
  enabled: boolean | null;
  font: string | null;
  font_size: number | null;
  line_spacing: number | null;
  letter_spacing: number | null;
  word_spacing: number | null;
  theme: string | null;
  line_width: number | null;
  focus_mode: string | null;
  tts_enabled: boolean | null;
  tts_speed: number | null;
  speech_language: string | null;
  stt_enabled: boolean | null;
  extra_time_factor: number | null;
  hide_timer: boolean | null;
  arabic_diacritics: boolean | null;
  spelling_suggestions: boolean | null;
  word_prediction: boolean | null;
  language_subject_ids: string[] | null;
  consent_given_at: string | null;
};

export type AccessibilityResponse = { profile: AccessibilityProfile | null };

export const isAccessibilityActive = (profile: AccessibilityProfile | null | undefined) =>
  Boolean(profile?.enabled && profile.consent_given_at);

export type SpeechRecognitionResultEvent = {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
};

export type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionResultEvent) => void) | null;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  start: () => void;
  stop: () => void;
};

export type STTProvider = {
  available: () => boolean;
  create: () => SpeechRecognitionLike | null;
};

export type TTSProvider = {
  hasVoice: (language: string) => boolean;
  speak: (utterance: SpeechSynthesisUtterance) => void;
  cancel: () => void;
};

type SpeechWindow = Window & {
  SpeechRecognition?: new () => SpeechRecognitionLike;
  webkitSpeechRecognition?: new () => SpeechRecognitionLike;
};

export const browserSTTProvider: STTProvider = {
  available: () => {
    if (typeof window === "undefined") return false;
    const w = window as SpeechWindow;
    return Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
  },
  create: () => {
    if (typeof window === "undefined") return null;
    const w = window as SpeechWindow;
    const Constructor = w.SpeechRecognition || w.webkitSpeechRecognition;
    return Constructor ? new Constructor() : null;
  },
};

export const browserTTSProvider: TTSProvider = {
  hasVoice: (language) =>
    typeof window !== "undefined" &&
    "speechSynthesis" in window &&
    window.speechSynthesis.getVoices().some((voice) =>
      voice.lang.toLowerCase().startsWith(language.split("-")[0].toLowerCase())),
  speak: (utterance) => window.speechSynthesis.speak(utterance),
  cancel: () => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
  },
};
