/* Tutor module client: types mirror backend/tutor/schemas.py, calls go through the shared api() helper
   (same-origin /api, CSRF header, retries). */
import { api } from "@/lib/api";

export type Valley = "revision" | "skills";
export type Level = "beginner" | "intermediate" | "advanced";
export type TrackStatus = "created" | "ingesting" | "awaiting_level" | "probing" | "levelled" | "building" | "ready" | "failed";

export interface Citation { chunk_id: string; quote?: string; page?: number | null; source?: string; origin?: "course" | "web"; url?: string | null }
export interface QCMOption { text: string; correct?: boolean; why?: string }
export interface QCMItem { kind: "qcm"; id: string; concept_key: string; stem: string; options: QCMOption[]; multiple: boolean; explanation?: string; difficulty?: number; likeness?: number; citations?: Citation[]; points?: number }
export interface QuizItem { kind: "quiz"; id: string; concept_key: string; question: string; answer_type: "text" | "number" | "expression" | "true_false" | "choice"; answer?: string; explanation?: string; likeness?: number; citations?: Citation[]; points?: number }
export interface ExercisePart { label: string; prompt: string; answer_type: string; points: number; answer?: string; solution_steps?: string[] }
export interface ExerciseItem { kind: "exercise"; id: string; concept_keys: string[]; title: string; statement: string; parts: ExercisePart[]; likeness?: number; citations?: Citation[]; points?: number }
export interface Fiche { kind: "fiche"; id: string; concept_key: string; fiche_type: string; front: string; back: string; citations?: Citation[] }
export type Item = QCMItem | QuizItem | ExerciseItem;

export interface Concept { key: string; title: string; chapter: string; exam_weight: number; coverage: number; prerequisites: string[] }
export interface TutorDocument { id: string; filename: string; doc_type: string; status: string; pages: number; error?: string | null; ocr_pages: number }
export interface Run { id: string; flow: string; status: "queued" | "running" | "waiting" | "succeeded" | "failed"; node: string | null; error: string | null; steps: { node: string; label: string; status: string; ms: number; result?: any; error?: string }[] }
export interface Track {
  id: string; valley: Valley; title: string; subject: string; goal: string; language: string; exam_date: string | null;
  chapters: string[]; allow_web: boolean; status: TrackStatus; declared_level: Level | null; measured_level: Level | null;
  level_verdict: string | null; level_by_chapter: Record<string, Level>; stats: any; updated_at: string;
  documents?: TutorDocument[]; concepts?: Concept[]; last_run?: Run | null; fingerprint?: any; web_sources?: any[];
}
export interface ArtifactSummary { id: string; type: string; title: string; chapter: string; likeness: number | null; status: string; count: number; concept_keys: string[] }
export interface Artifact extends ArtifactSummary { track_id: string; content: any; likeness_detail: Record<string, number>; verification: any }
export interface TutorialNode { id: string; slug: string; title: string; chapter: string; ord: number; kind: "chapter" | "page" | "quiz" | "project" | "checkpoint"; parent_slug: string | null; status: "locked" | "open" | "done" | "skippable"; mastery: number; artifact_id: string | null }
export interface LevelResult { declared: Level; measured: Level; verdict: "confirmed" | "higher" | "lower" | "unverified"; theta: number; level_by_chapter: Record<string, Level>; items_scored: number; rapid_guesses: number }
export interface AttemptResult { correct: boolean | null; score: number; feedback: string; error_tags: string[]; solution: any; mastery?: { concept_key: string; p_mastery: number; elo: number; mastered: boolean; next_review: string } }
export interface HelpResult { level: number; message: string; citations: Citation[]; autonomy_cost: number }

const T = "/tutor";
export const tutor = {
  capabilities: () => api<any>(`${T}/capabilities`),
  tracks: () => api<{ tracks: Track[] }>(`${T}/tracks`),
  track: (id: string) => api<Track>(`${T}/tracks/${id}`),
  create: (body: Partial<Track> & { valley: Valley; title: string }) => api<Track>(`${T}/tracks`, { method: "POST", json: body }),
  patch: (id: string, body: Partial<Track>) => api<Track>(`${T}/tracks/${id}`, { method: "PATCH", json: body }),
  remove: (id: string) => api(`${T}/tracks/${id}`, { method: "DELETE" }),
  upload: (id: string, files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return api<{ documents: TutorDocument[] }>(`${T}/tracks/${id}/documents`, { method: "POST", body: fd, retries: 1 });
  },
  removeDocument: (id: string, docId: string) => api(`${T}/tracks/${id}/documents/${docId}`, { method: "DELETE" }),
  prepare: (id: string) => api<Run>(`${T}/tracks/${id}/prepare`, { method: "POST" }),
  build: (id: string) => api<Run>(`${T}/tracks/${id}/build`, { method: "POST" }),
  run: (runId: string) => api<Run>(`${T}/runs/${runId}`),
  resume: (runId: string) => api<Run>(`${T}/runs/${runId}/resume`, { method: "POST" }),
  declare: (id: string, level: Level, skip_probe = false, per_chapter: Record<string, Level> = {}) =>
    api<{ item?: any; result?: LevelResult }>(`${T}/tracks/${id}/level`, { method: "POST", json: { level, skip_probe, per_chapter } }),
  probeAnswer: (id: string, item_id: string, choice: number | number[], ms: number) =>
    api<{ done: boolean; item?: any; result?: LevelResult; progress: { answered: number; max: number } }>(`${T}/tracks/${id}/probe/answer`, { method: "POST", json: { item_id, choice, ms } }),
  probeFinish: (id: string) => api<LevelResult>(`${T}/tracks/${id}/probe/finish`, { method: "POST" }),
  plan: (id: string) => api<any>(`${T}/tracks/${id}/plan`),
  artifacts: (id: string, type?: string) => api<{ artifacts: ArtifactSummary[] }>(`${T}/tracks/${id}/artifacts${type ? `?type=${type}` : ""}`),
  artifact: (artifactId: string) => api<Artifact>(`${T}/artifacts/${artifactId}`),
  regenerate: (artifactId: string) => api<Artifact>(`${T}/artifacts/${artifactId}/regenerate`, { method: "POST" }),
  newMock: (id: string) => api<Artifact>(`${T}/tracks/${id}/mock-exams`, { method: "POST" }),
  submitMock: (artifactId: string, answers: Record<string, any>, elapsed_s: number) =>
    api<any>(`${T}/mock-exams/${artifactId}/submit`, { method: "POST", json: { answers, elapsed_s } }),
  attempt: (id: string, itemId: string, answer: any, ms: number, help_level: number) =>
    api<AttemptResult>(`${T}/tracks/${id}/items/${itemId}/attempt`, { method: "POST", json: { answer, ms, help_level } }),
  help: (id: string, itemId: string, level: number) => api<HelpResult>(`${T}/tracks/${id}/items/${itemId}/help`, { method: "POST", json: { level } }),
  ask: (id: string, question: string, mode: "study" | "practice" = "study", item_id?: string) =>
    api<{ answer: string; citations: Citation[]; grounded: boolean; simulated: boolean }>(`${T}/tracks/${id}/ask`, { method: "POST", json: { question, mode, item_id } }),
  tutorial: (id: string) => api<{ nodes: TutorialNode[] }>(`${T}/tracks/${id}/tutorial`),
  lesson: (id: string, slug: string) => api<{ node: TutorialNode; artifact: Artifact }>(`${T}/tracks/${id}/lessons/${slug}`),
  complete: (id: string, slug: string) => api<{ next: TutorialNode | null; skill?: any }>(`${T}/tracks/${id}/lessons/${slug}/complete`, { method: "POST" }),
  report: (id: string) => api<any>(`${T}/tracks/${id}/report`),
  bySubject: (subjectId: string) => api<{ tracks: Track[] }>(`${T}/by-subject/${subjectId}`),
  fromSubject: (subjectId: string, body: { valley: Valley; exam_date?: string | null; allow_web?: boolean; language?: string }) =>
    api<Track>(`${T}/from-subject/${subjectId}`, { method: "POST", json: body }),
};

/** Poll a flow run until it ends; onTick receives each snapshot. */
export async function waitRun(runId: string, onTick?: (r: Run) => void, maxMs = 15 * 60_000): Promise<Run> {
  const start = Date.now();
  for (;;) {
    const r = await tutor.run(runId);
    onTick?.(r);
    if (r.status === "succeeded" || r.status === "failed") return r;
    if (Date.now() - start > maxMs) return r;
    await new Promise((res) => setTimeout(res, 1200));
  }
}

export const ARTIFACT_LABEL: Record<string, string> = {
  resume: "Résumé", fiches: "Fiches", qcm: "QCM", quiz: "Quiz", exercises: "Exercises", mock_exam: "Mock exam", lesson: "Lesson",
};
export const LEVEL_LABEL: Record<Level, string> = { beginner: "Beginner", intermediate: "Intermediate", advanced: "Advanced" };
