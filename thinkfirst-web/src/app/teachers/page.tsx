"use client";
import React, { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { TeacherAvatar } from "@/components/avatar/TeacherAvatar";
import { api, newKey } from "@/lib/api";
import { useApi } from "@/lib/hooks";

export default function TeachersPage() {
  const subjects = useApi<any>("/subjects");
  const [selectedSubjectId, setSelectedSubjectId] = useState<string>("");
  const [customText, setCustomText] = useState<string>("");
  const [activeScript, setActiveScript] = useState<string | undefined>(undefined);

  const list = subjects.data?.subjects || [];
  const activeSubId = selectedSubjectId || list[0]?.id || "";
  const activeSubName = list.find((s: any) => s.id === activeSubId)?.name || "";

  const handleAskProfessor = async (question: string) => {
    if (!activeSubId) return;
    try {
      const r = await api("/professor/ask", {
        method: "POST",
        json: { subject_id: activeSubId, question, idempotency_key: newKey() },
      });
      if (r?.message) return r.message as string;
    } catch {
      // Built-in fallback handled by TeacherAvatar
    }
  };

  return (
    <AppShell crumbs={[{ label: "3D Teachers" }]}>
      <div className="space-y-6" data-screen="T01">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-page-compact md:text-page">
              Meet your <span className="hl">3D teachers</span>
            </h1>
            <p className="mt-1 text-meta text-ink-muted">
              Move the mouse: they follow you. Hover: they wave. Click them: they react. Paste or generate any text in
              ThinkFirst to have them teach it out loud with chalkboard formulas and gestures.
            </p>
          </div>
          {list.length > 0 && (
            <div>
              <label htmlFor="teacher-sub" className="label !mb-1 text-meta">
                Ground answers in subject
              </label>
              <select
                id="teacher-sub"
                className="field !min-h-[42px] !w-auto"
                value={activeSubId}
                onChange={(e) => setSelectedSubjectId(e.target.value)}
              >
                {list.map((s: any) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <TeacherAvatar
          text={activeScript}
          hint={activeSubName}
          compact={false}
          autoPlay={Boolean(activeScript)}
          stageHeight={450}
          onAsk={handleAskProfessor}
        />

        <section className="game-card space-y-3 p-5">
          <h2 className="text-section">Transcribe any text into a speaking teacher</h2>
          <p className="text-meta text-ink-muted">
            Paste any course excerpt, lesson, formula, or explanation. You can also use stage tags like{" "}
            <code>[wave]</code>, <code>[think]</code>, <code>[board: 2(x + 3) = 2x + 6]</code>, <code>[point]</code>,{" "}
            <code>[celebrate]</code>, or <code>[apple]</code> — or just plain text and the director will add gestures
            and chalkboard equations automatically.
          </p>
          <textarea
            className="field !min-h-[96px]"
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            placeholder="Type or paste any text here (e.g. Expand 2(x + 3) = 2x + 6 because the factor outside multiplies every term inside the brackets)..."
          />
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className="btn-primary"
              disabled={!customText.trim()}
              onClick={() => setActiveScript(customText.trim())}
            >
              🔊 Speak &amp; animate text
            </button>
            {activeScript && (
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setActiveScript(undefined);
                  setCustomText("");
                }}
              >
                Reset to teacher intro
              </button>
            )}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
