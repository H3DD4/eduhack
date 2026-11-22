"use client";
import React, { createContext, ReactNode, useCallback, useContext, useState } from "react";
import { api, newKey } from "@/lib/api";
import { personaFor, PersonaId, PERSONAS } from "./rig";
import { TeacherAvatar } from "./TeacherAvatar";
import { AccessibilityProfile, isAccessibilityActive } from "@/lib/accessibility/profile";

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
  profile?: AccessibilityProfile | null;
}

const AvatarSpeakerCtx = createContext<AvatarSpeakerContextValue>({
  speakWithAvatar: () => {},
  closeAvatar: () => {},
  openAvatarStudio: () => {},
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

export function AvatarSpeakerProvider({ children, profile = null }: { children: ReactNode; profile?: AccessibilityProfile | null }) {
  const [state, setState] = useState<AvatarSpeakerState>({
    open: false,
    text: "",
    title: "",
    hint: "",
  });
  const [expanded, setExpanded] = useState<boolean>(false);

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

  const handleAsk = useCallback(
    async (question: string) => {
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
          // Fall back to built-in teacher response if quota/lock blocks Professor call
        }
      }
    },
    [state.subjectId, state.taskId]
  );

  return (
    <AvatarSpeakerCtx.Provider value={{ speakWithAvatar, closeAvatar, openAvatarStudio, profile }}>
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
            speechLanguage={profile?.speech_language || "en-GB"}
            speechRate={profile?.tts_speed || 1}
            strictSpeechLanguage={isAccessibilityActive(profile)}
            speechInputEnabled={!isAccessibilityActive(profile) || Boolean(profile?.stt_enabled)}
            stageHeight={expanded ? 380 : 225}
            onAsk={handleAsk}
          />
        </aside>
      )}
    </AvatarSpeakerCtx.Provider>
  );
}
