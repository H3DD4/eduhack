"use client";
import React, { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, newKey } from "@/lib/api";
import { personaFor, PersonaId, PERSONAS } from "./rig";
import { TeacherAvatar } from "./TeacherAvatar";
import { AccessibilityProfile, isAccessibilityActive } from "@/lib/accessibility/profile";
import { parseVoiceGuideIntent, voiceGuidePagePrompt } from "@/lib/accessibility/voiceGuide";

const VOICE_GUIDE_STORAGE_KEY = "tf_voice_guide_enabled";

function elementLabel(element: HTMLElement): string {
  const labels = element.id
    ? Array.from(document.querySelectorAll<HTMLLabelElement>("label")).filter((label) => label.htmlFor === element.id)
    : [];
  return [
    element.getAttribute("aria-label"),
    element.getAttribute("name"),
    element.getAttribute("placeholder"),
    ...labels.map((label) => label.innerText),
    element.innerText,
  ].filter(Boolean).join(" ").toLowerCase();
}

function setInputValue(element: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement, value: string) {
  const prototype = element instanceof HTMLInputElement
    ? HTMLInputElement.prototype
    : element instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLSelectElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
  setter?.call(element, value);
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
}

interface AvatarSpeakerState {
  open: boolean;
  text: string;
  title: string;
  hint: string;
  subjectId?: string;
  taskId?: string;
  persona?: PersonaId;
}

interface AvatarSpeakerContextValue {
  /** Transcribe and speak any system-generated text in the 3D Speaking Avatar dock. */
  speakWithAvatar: (
    text: string,
    opts?: { title?: string; hint?: string; subjectId?: string; taskId?: string; persona?: PersonaId }
  ) => void;
  closeAvatar: () => void;
  openAvatarStudio: (opts?: { hint?: string; subjectId?: string }) => void;
  startVoiceGuide: () => void;
  voiceGuideEnabled: boolean;
  profile?: AccessibilityProfile | null;
}

const AvatarSpeakerCtx = createContext<AvatarSpeakerContextValue>({
  speakWithAvatar: () => {},
  closeAvatar: () => {},
  openAvatarStudio: () => {},
  startVoiceGuide: () => {},
  voiceGuideEnabled: false,
});

export const useAvatarSpeaker = () => useContext(AvatarSpeakerCtx);

/** Reusable button that transcribes any system-generated text into the 3D Speaking Avatar. */
export function SpeakButton({
  text,
  title,
  hint,
  subjectId,
  taskId,
  label = "Speak with Avatar",
  className = "",
}: {
  text?: string | null;
  title?: string;
  hint?: string;
  subjectId?: string;
  taskId?: string;
  label?: string;
  className?: string;
}) {
  const { speakWithAvatar, profile } = useAvatarSpeaker();
  if (isAccessibilityActive(profile) && profile?.tts_enabled === false) return null;
  if (!text || !text.trim()) return null;
  const p = personaFor(hint || title || text);
  return (
    <button
      type="button"
      onClick={() => speakWithAvatar(text, { title, hint: hint || title || text, subjectId, taskId, persona: p })}
      className={`btn-secondary !min-h-[36px] !px-3 text-meta ${className}`}
      title={`Have ${PERSONAS[p].name} speak and act out this text`}
    >
      <span aria-hidden>🔊</span> {label}
    </button>
  );
}

export function VoiceGuideButton() {
  const { startVoiceGuide, voiceGuideEnabled } = useAvatarSpeaker();
  return (
    <button
      type="button"
      onClick={startVoiceGuide}
      aria-pressed={voiceGuideEnabled}
      aria-label={voiceGuideEnabled ? "Open voice guide" : "Start voice guide"}
      className="btn-secondary fixed bottom-20 right-4 z-40 !min-h-[44px] shadow-hard"
    >
      Voice guide
    </button>
  );
}

export function AvatarSpeakerProvider({ children, profile = null }: { children: ReactNode; profile?: AccessibilityProfile | null }) {
  const router = useRouter();
  const pathname = usePathname();
  const [state, setState] = useState<AvatarSpeakerState>({
    open: false,
    text: "",
    title: "",
    hint: "",
  });
  const [expanded, setExpanded] = useState<boolean>(false);
  const [voiceGuideEnabled, setVoiceGuideEnabled] = useState(false);
  const initialized = useRef(false);
  const lastPath = useRef(pathname);
  const awaitingVoiceConsent = useRef(false);
  const pendingAction = useRef<(() => void) | null>(null);
  const voiceTarget = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const initialPath = lastPath.current;
    let enabled = false;
    try {
      enabled = window.localStorage.getItem(VOICE_GUIDE_STORAGE_KEY) === "true";
    } catch {
      enabled = false;
    }
    initialized.current = true;
    setVoiceGuideEnabled(enabled);
    if (enabled && initialPath !== "/onboarding") {
      setState({
        open: true,
        text: voiceGuidePagePrompt(initialPath, window.location.search),
        title: "Voice guide",
        hint: "voice navigation",
      });
    }
  }, []);

  useEffect(() => {
    if (!initialized.current || pathname === lastPath.current) return;
    lastPath.current = pathname;
    pendingAction.current = null;
    voiceTarget.current = null;
    if (voiceGuideEnabled && pathname !== "/onboarding") {
      setState({
        open: true,
        text: voiceGuidePagePrompt(pathname, window.location.search),
        title: "Voice guide",
        hint: "voice navigation",
      });
    }
  }, [pathname, voiceGuideEnabled]);

  const speakWithAvatar = useCallback(
    (
      text: string,
      opts: { title?: string; hint?: string; subjectId?: string; taskId?: string; persona?: PersonaId } = {}
    ) => {
      if (!text || !text.trim()) return;
      setState({
        open: true,
        text: text.trim(),
        title: opts.title || "3D Teacher",
        hint: opts.hint || opts.title || text,
        subjectId: opts.subjectId,
        taskId: opts.taskId,
        persona: opts.persona,
      });
    },
    []
  );

  const openAvatarStudio = useCallback((opts: { hint?: string; subjectId?: string } = {}) => {
    setState((prev) => ({
      ...prev,
      open: true,
      hint: opts.hint || prev.hint || "algebra",
      subjectId: opts.subjectId || prev.subjectId,
    }));
  }, []);

  const closeAvatar = useCallback(() => {
    setState((prev) => ({ ...prev, open: false }));
  }, []);

  const startVoiceGuide = useCallback(() => {
    if (voiceGuideEnabled) {
      setState({
        open: true,
        text: voiceGuidePagePrompt(pathname, typeof window === "undefined" ? "" : window.location.search),
        title: "Voice guide",
        hint: "voice navigation",
      });
      return;
    }
    awaitingVoiceConsent.current = true;
    setState({
      open: true,
      text: "Would spoken guidance and voice navigation help you use ThinkFirst? Say yes to turn it on for this device, or no to leave it off. The microphone stays off until you press Ask by voice; your browser may process speech.",
      title: "Voice guide",
      hint: "voice navigation",
    });
  }, [pathname, voiceGuideEnabled]);

  const handleAsk = useCallback(
    async (question: string) => {
      const intent = parseVoiceGuideIntent(question);

      if (intent.type === "stop") {
        closeAvatar();
        return "Speech stopped.";
      }

      if (intent.type === "disable") {
        try {
          window.localStorage.removeItem(VOICE_GUIDE_STORAGE_KEY);
          setVoiceGuideEnabled(false);
          return "Voice guidance is off. You can turn it on again with the Voice guide button.";
        } catch {
          setVoiceGuideEnabled(false);
          return "Voice guidance is off for this visit, but I could not save that preference on this device.";
        }
      }

      if (intent.type === "cancel") {
        pendingAction.current = null;
        awaitingVoiceConsent.current = false;
        return "Cancelled. Nothing was submitted.";
      }

      if (intent.type === "affirmative" && pendingAction.current) {
        const action = pendingAction.current;
        pendingAction.current = null;
        action();
        return "Confirmed. I am doing that now.";
      }

      if (intent.type === "affirmative" && awaitingVoiceConsent.current) {
        awaitingVoiceConsent.current = false;
        try {
          window.localStorage.setItem(VOICE_GUIDE_STORAGE_KEY, "true");
          setVoiceGuideEnabled(true);
          return "Voice guidance is on for this device. The microphone is not always listening. Say help to hear commands.";
        } catch {
          setVoiceGuideEnabled(true);
          return "Voice guidance is on for this visit, but I could not save the preference on this device. The microphone is not always listening. Say help for commands.";
        }
      }

      if (intent.type === "negative" && awaitingVoiceConsent.current) {
        awaitingVoiceConsent.current = false;
        return "No problem. Voice guidance stays off. Close this avatar when you are finished.";
      }

      if (intent.type === "help" || intent.type === "repeat") {
        return voiceGuidePagePrompt(pathname, typeof window === "undefined" ? "" : window.location.search);
      }

      if (intent.type === "navigate") {
        if (pathname === "/welcome" && intent.href === "/welcome") {
          document.querySelector<HTMLButtonElement>('[data-voice-action="sign-in"]')?.click();
          const email = document.getElementById("email");
          email?.focus();
          voiceTarget.current = email;
          return "The email field is focused. For safety, type your password or use a password manager; do not speak it aloud.";
        }
        if (pathname === "/welcome" && intent.href.includes("mode=create")) {
          const button = document.querySelector<HTMLButtonElement>('[data-voice-action="create-account"]');
          button?.click();
          const email = document.getElementById("email");
          email?.focus();
          voiceTarget.current = email;
          return "The create-account form is ready. Enter your email and type your password or use a password manager.";
        }
        if (pathname === "/welcome" && !intent.href.startsWith("/welcome")) {
          return "Please sign in or create an account first. Say sign in or create account.";
        }
        if (intent.href === pathname) {
          return voiceGuidePagePrompt(pathname, typeof window === "undefined" ? "" : window.location.search);
        }
        router.push(intent.href);
        return `Opening ${intent.label}.`;
      }

      if (intent.type === "learn") {
        if (pathname === "/welcome") return "Please sign in or create an account first. Say sign in or create account.";
        router.push(`/subjects/new?topic=${encodeURIComponent(intent.topic)}`);
        return `Opening the topic form for ${intent.topic}.`;
      }

      if (intent.type === "select") {
        const option = Array.from(document.querySelectorAll<HTMLElement>('[role="radio"], [role="switch"], label'))
          .find((element) => element.innerText.toLowerCase().includes(intent.option));
        if (option) {
          option.click();
          voiceTarget.current = null;
          return `${intent.option} selected. Say next to continue.`;
        }
        return `I could not find an option matching ${intent.option}. Say help to hear the choices on this page.`;
      }

      if (intent.type === "focus") {
        const field = Array.from(document.querySelectorAll<HTMLElement>(
          "input:not([type=hidden]):not([type=file]), textarea, select, button"
        )).find((element) => elementLabel(element).includes(intent.field));
        if (!field) return `I could not find a field called ${intent.field}. Say help for this page.`;
        field.focus();
        voiceTarget.current = field;
        return `${intent.field} is focused. Say type followed by the text you want to enter. Passwords must be typed or filled by your password manager, not spoken.`;
      }

      if (intent.type === "type") {
        const target = voiceTarget.current;
        if (target instanceof HTMLInputElement && target.type === "password") {
          return "For your security, I cannot enter passwords from speech. Type it or use your password manager.";
        }
        if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) ||
          target.disabled || ("readOnly" in target && target.readOnly)) {
          return "Focus a text field first by saying focus followed by its label.";
        }
        let value = intent.value;
        if (target instanceof HTMLInputElement && target.type === "email") {
          value = value.replace(/\s+at\s+/gi, "@").replace(/\s+dot\s+/gi, ".");
        }
        const maxLength = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement ? target.maxLength : -1;
        setInputValue(target, maxLength > 0 ? value.slice(0, maxLength) : value);
        return "Text entered. You can say read this page, next, or submit.";
      }

      if (intent.type === "click") {
        const control = Array.from(document.querySelectorAll<HTMLElement>("button, a, [role='button']"))
          .find((element) => elementLabel(element).includes(intent.control));
        if (!control) return `I could not find a control called ${intent.control}. Say help for this page.`;
        pendingAction.current = () => control.click();
        return `I found ${elementLabel(control)}. Say confirm to activate it, or cancel.`;
      }

      if (intent.type === "next") {
        if (pathname === "/onboarding") {
          const form = document.querySelector<HTMLFormElement>("main form");
          const submit = form?.querySelector<HTMLButtonElement>('button[type="submit"]');
          if (form && submit?.innerText.trim().toLowerCase() === "save and start") {
            pendingAction.current = () => form.requestSubmit();
            return "This saves your setup and starts the app. Say confirm to continue, or cancel.";
          }
          voiceTarget.current = null;
          submit?.click();
          return "Moving to the next setup question.";
        }
        return "There is no setup question to advance here. Say help for the actions on this page.";
      }

      if (intent.type === "back") {
        const button = document.querySelector<HTMLButtonElement>('button[aria-label="Back"]');
        if (button && !button.disabled) {
          voiceTarget.current = null;
          button.click();
          return "Going back one step.";
        }
        router.back();
        return "Going back.";
      }

      if (intent.type === "start_topic") {
        const form = document.querySelector<HTMLFormElement>('form[aria-label="Learn a topic"]');
        const topic = document.getElementById("topic") as HTMLInputElement | null;
        if (form && topic && !topic.value.trim()) {
          topic.focus();
          voiceTarget.current = topic;
          return "Tell me the topic you want to learn, then say start learning.";
        }
        if (form && topic) {
          pendingAction.current = () => form.requestSubmit();
          return `I heard ${topic.value.trim()}. Say confirm to create its learning plan, or cancel.`;
        }
        const action = Array.from(document.querySelectorAll<HTMLButtonElement>("main button"))
          .find((button) => /^(start learning|confirm scope)$/i.test(button.innerText.trim()));
        if (action) {
          pendingAction.current = () => action.click();
          return `${action.innerText.trim()} will continue this subject. Say confirm to continue, or cancel.`;
        }
        return "Open the new subject page first by saying add a subject.";
      }

      if (intent.type === "submit") {
        if (pathname === "/welcome") {
          const form = document.querySelector<HTMLFormElement>('[data-voice-form="auth"]');
          if (!form) return "The sign-in form is not available on this page.";
          pendingAction.current = () => form.requestSubmit();
          return "This will submit the sign-in or account-creation form. Say confirm to continue, or cancel.";
        }
        const topicForm = document.querySelector<HTMLFormElement>('form[aria-label="Learn a topic"]');
        const topicInput = document.getElementById("topic") as HTMLInputElement | null;
        if (topicForm && topicInput?.value.trim()) {
          pendingAction.current = () => topicForm.requestSubmit();
          return `This will create a learning plan for ${topicInput.value.trim()}. Say confirm to continue, or cancel.`;
        }
        const form = document.querySelector<HTMLFormElement>("main form");
        if (form) {
          pendingAction.current = () => form.requestSubmit();
          return "This will submit the current form. Say confirm to continue, or cancel.";
        }
        const action = Array.from(document.querySelectorAll<HTMLButtonElement>("main button"))
          .find((button) => /^(confirm scope|start learning|start session)(?:\s*→)?$/i.test(button.innerText.trim()));
        if (action) {
          pendingAction.current = () => action.click();
          return `${action.innerText.trim()} will continue. Say confirm to proceed, or cancel.`;
        }
        return "There is no form or primary action to submit on this page.";
      }

      if (state.subjectId) {
        try {
          const r = await api("/professor/ask", {
            method: "POST",
            json: {
              subject_id: state.subjectId,
              task_id: state.taskId || null,
              question,
              idempotency_key: newKey(),
            },
          });
          if (r?.message) return r.message as string;
        } catch {
          return "I could not reach your professor right now. Please try again.";
        }
      }
      if (intent.type === "unknown") {
        return "I did not understand that command. Say help, add a subject, today, subjects, planner, progress, settings, or sign in.";
      }
    },
    [closeAvatar, pathname, router, state.subjectId, state.taskId]
  );

  return (
    <AvatarSpeakerCtx.Provider value={{ speakWithAvatar, closeAvatar, openAvatarStudio, startVoiceGuide, voiceGuideEnabled, profile }}>
      {children}
      {state.open && (
        <aside
          aria-label="3D Speaking Teacher Avatar"
          data-component="floating-avatar-dock"
          className={`fade-in fixed bottom-4 right-4 z-50 rounded-card border-2 border-ink bg-surface p-3 shadow-hard-lg ${
            expanded ? "inset-x-4 bottom-4 max-w-3xl md:left-auto md:w-[680px]" : "w-[360px] max-w-[calc(100vw-2rem)] sm:w-[430px]"
          }`}
        >
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="font-semibold">
              🎓 {state.title || "Learn with 3D Teacher"}
            </span>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setExpanded((e) => !e)}
                className="btn-secondary !min-h-[32px] !px-2.5 text-meta"
                aria-label={expanded ? "Compact avatar player" : "Expand avatar player"}
              >
                {expanded ? "Compact" : "Expand"}
              </button>
              <button
                type="button"
                onClick={closeAvatar}
                className="btn-secondary !min-h-[32px] !px-2.5 text-meta"
                aria-label="Close 3D teacher avatar"
              >
                ✕
              </button>
            </div>
          </div>
          <TeacherAvatar
            text={state.text || undefined}
            hint={state.hint}
            initialPersona={state.persona}
            compact={!expanded}
            autoPlay={Boolean(state.text)}
            showPersonaPicker={state.title !== "Voice guide"}
            speechLanguage={state.title === "Voice guide" ? "en-GB" : profile?.speech_language || "en-GB"}
            speechRate={profile?.tts_speed || 1}
            strictSpeechLanguage={state.title === "Voice guide" ? false : isAccessibilityActive(profile)}
            speechInputEnabled={state.title === "Voice guide" || !isAccessibilityActive(profile) || Boolean(profile?.stt_enabled)}
            speechGuideMode={state.title === "Voice guide"}
            stageHeight={expanded ? 380 : 225}
            onAsk={handleAsk}
          />
        </aside>
      )}
    </AvatarSpeakerCtx.Provider>
  );
}
