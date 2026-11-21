import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

// E2E runs the real API (SQLite + inline jobs + labeled demo adapters, so results are deterministic and no
// external AI service is called) and a production Next.js build (rewrites baked with API_URL). Chromium's fake microphone exercises real capture.
const apiDir = path.resolve(__dirname, "../api");
const py = process.env.E2E_PYTHON || (process.platform === "win32" ? path.join(apiDir, ".venv", "Scripts", "python.exe") : path.join(apiDir, ".venv", "bin", "python"));
const apiEnv = {
  DATABASE_URL: `sqlite:///${path.join(apiDir, "e2e.db").replace(/\\/g, "/")}`,
  LOCAL_STORAGE_DIR: path.join(apiDir, ".storage-e2e"),
  LLM_PROVIDER: "demo", STT_PROVIDER: "demo", GEMINI_API_KEY: "", GROQ_API_KEY: "", ANTHROPIC_API_KEY: "",
  JOB_MODE: "inline", DEMO_MODE: "true", RESOURCE_DISCOVERY: "false",
};

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  expect: { timeout: 20_000 },
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: "http://localhost:3100",
    trace: "retain-on-failure",
    launchOptions: { args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], channel: "chromium", permissions: ["microphone"] } }],
  webServer: [
    {
      command: `"${py}" -m uvicorn thinkfirst.main:app --port 8100`,
      cwd: apiDir,
      url: "http://127.0.0.1:8100/api/health",
      env: apiEnv,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npx next build && npx next start -p 3100",
      url: "http://localhost:3100/welcome",
      env: { API_URL: "http://127.0.0.1:8100", NEXT_TELEMETRY_DISABLED: "1" },
      reuseExistingServer: false,
      timeout: 600_000,
    },
  ],
});
