import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

// Fresh E2E database + demo account; also writes the fixture PDF for non-demo uploads.
export default function globalSetup() {
  const apiDir = path.resolve(__dirname, "../../api");
  const py = process.env.E2E_PYTHON || (process.platform === "win32" ? path.join(apiDir, ".venv", "Scripts", "python.exe") : path.join(apiDir, ".venv", "bin", "python"));
  const db = path.join(apiDir, "e2e.db");
  // Delete e2e.db (+ the Agentic Tutor database attached next to it) when possible. The API web server may already
  // hold it open (create_app() runs ensure_schema() on SQLite); then `seed --reset` below clears the data instead.
  for (const f of [db, `${db}.tutor_tracks.sqlite`, `${db}-journal`]) {
    try { fs.rmSync(f, { force: true, maxRetries: 3, retryDelay: 300 }); } catch { /* in use: reset below */ }
  }
  const env = { ...process.env, DATABASE_URL: `sqlite:///${db.replace(/\\/g, "/")}`, LOCAL_STORAGE_DIR: path.join(apiDir, ".storage-e2e"),
    LLM_PROVIDER: "demo", STT_PROVIDER: "demo", JOB_MODE: "inline", GEMINI_API_KEY: "", GROQ_API_KEY: "", RESOURCE_DISCOVERY: "false", EMBEDDING_PROVIDER: "demo" };
  execFileSync(py, ["-m", "thinkfirst.seed", "--reset"], { cwd: apiDir, env, stdio: "inherit" });
  const out = path.join(__dirname, ".fixtures");
  fs.mkdirSync(out, { recursive: true });
  execFileSync(py, ["-c", `from thinkfirst.fixtures import demo_course_pdf; open(r"${path.join(out, "math101.pdf")}", "wb").write(demo_course_pdf())`], { cwd: apiDir, env });
}
