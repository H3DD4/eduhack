import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

// Fresh E2E database + demo account; also writes the fixture PDF for non-demo uploads.
export default function globalSetup() {
  const apiDir = path.resolve(__dirname, "../../api");
  const py = process.env.E2E_PYTHON || (process.platform === "win32" ? path.join(apiDir, ".venv", "Scripts", "python.exe") : path.join(apiDir, ".venv", "bin", "python"));
  const db = path.join(apiDir, "e2e.db");
  if (fs.existsSync(db)) fs.rmSync(db);
  const env = { ...process.env, DATABASE_URL: `sqlite:///${db.replace(/\\/g, "/")}`, LOCAL_STORAGE_DIR: path.join(apiDir, ".storage-e2e"),
    LLM_PROVIDER: "demo", STT_PROVIDER: "demo", JOB_MODE: "inline", GEMINI_API_KEY: "", GROQ_API_KEY: "", RESOURCE_DISCOVERY: "false" };
  execFileSync(py, ["-m", "thinkfirst.seed", "--reset"], { cwd: apiDir, env, stdio: "inherit" });
  const out = path.join(__dirname, ".fixtures");
  fs.mkdirSync(out, { recursive: true });
  execFileSync(py, ["-c", `from thinkfirst.fixtures import demo_course_pdf; open(r"${path.join(out, "math101.pdf")}", "wb").write(demo_course_pdf())`], { cwd: apiDir, env });
}
