import { expect, test } from "@playwright/test";
import { createSubjectFromFixture, FIXTURE, passPractice, signUpFresh, startDistributive, typedExplanation } from "./helpers";

/* Acceptance tests from audio_accessibility_and_states.md that apply to M0–M2. */

test("transfer: hint request locked; cancel conversion keeps work; confirm converts to guided (assisted)", async ({ page }) => {
  await signUpFresh(page);
  await createSubjectFromFixture(page);
  await startDistributive(page);
  await passPractice(page);
  await typedExplanation(page, "The 2 multiplies each term in the brackets, so 2(x + 3) = 2x + 6.");
  await page.getByRole("button", { name: "Answer one follow-up" }).click();
  await typedExplanation(page, "It does not work over a product: 2(x · 3) is 6x, not 2x · 6.");
  await page.getByRole("button", { name: "Try new application" }).click();
  await page.getByRole("button", { name: "Start without in-app help" }).click();
  await page.getByLabel(/Your answer \(write both forms\)/).fill("3(x + 4)");
  await page.getByRole("button", { name: "Use guided help" }).click();
  await expect(page.getByRole("dialog", { name: "Keep your work and switch to guided practice?" })).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByLabel(/Your answer \(write both forms\)/)).toHaveValue("3(x + 4)");
  await expect(page.getByText("Independent application: no in-app lesson or hint access")).toBeVisible();
  await page.getByRole("button", { name: "Use guided help" }).click();
  await page.getByRole("button", { name: "Switch to guided practice" }).click();
  await expect(page.getByText("Guided practice (assisted)")).toBeVisible();
  await expect(page.getByLabel(/Your answer \(write both forms\)/)).toHaveValue("3(x + 4)");
  await page.getByRole("button", { name: "Get help" }).click();
  await page.getByRole("button", { name: "I don't know where to start" }).click();
  await expect(page.getByText("Step 1: Clarify the task")).toBeVisible(); // the avatar also reads it aloud (live region)
});

test("microphone denied: cause-specific copy and text path remains usable", async ({ page }) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException("denied", "NotAllowedError"));
  });
  await signUpFresh(page);
  await createSubjectFromFixture(page);
  await startDistributive(page);
  await passPractice(page);
  await page.getByRole("tab", { name: "Voice" }).click();
  await page.getByRole("button", { name: "Enable microphone" }).click();
  await expect(page.getByText(/Microphone access is blocked here/).first()).toBeVisible();
  await page.getByRole("button", { name: "Use text" }).click();
  await expect(page.getByLabel("Your explanation")).toBeVisible();
  await expect(page.getByRole("button", { name: "Review text" })).toBeDisabled();
  await expect(page.getByText("Add text to review it.")).toBeVisible();
});

test("unsupported recording context disables retry", async ({ page }) => {
  await page.addInitScript(() => { (window as any).MediaRecorder = undefined; });
  await signUpFresh(page);
  await createSubjectFromFixture(page);
  await startDistributive(page);
  await passPractice(page);
  await page.getByRole("tab", { name: "Voice" }).click();
  await page.getByRole("button", { name: "Enable microphone" }).click();
  await expect(page.getByText(/Recording is unavailable in this browser or page/).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Try microphone again" })).toHaveCount(0);
});

test("reload during recording: explicit review of the captured part, no automatic restart", async ({ page }) => {
  await signUpFresh(page);
  await createSubjectFromFixture(page);
  await startDistributive(page);
  await passPractice(page);
  await page.getByRole("tab", { name: "Voice" }).click();
  await page.getByRole("button", { name: "Enable microphone" }).click();
  await page.getByRole("button", { name: "Start recording" }).click();
  await expect(page.getByText("Recording. Take your time.").first()).toBeVisible();
  await page.waitForTimeout(3500); // >= 3 chunks persisted to IndexedDB
  await page.reload();
  await page.getByRole("tab", { name: "Voice" }).click();
  await expect(page.getByText(/We found a recording saved on this device/).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Use recording" })).toBeVisible();
  await expect(page.getByText("Recording. Take your time.")).toHaveCount(0);
});

test("save and pause from F01 returns to Today with Resume; resume restores the draft", async ({ page }) => {
  await signUpFresh(page);
  await createSubjectFromFixture(page);
  await startDistributive(page);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Continue to practice" }).click();
  await page.getByLabel("Your answer").fill("2x + 6");
  await expect(page.locator("[data-save-state=synced]")).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "Focus" }).click();
  await page.getByRole("button", { name: "Save and pause" }).click();
  await expect(page).toHaveURL(/\/today/);
  await page.getByRole("link", { name: /Resume session/ }).click(); // Today hero CTA
  await page.getByRole("button", { name: "Resume" }).click();
  await expect(page.getByLabel("Your answer")).toHaveValue("2x + 6");
});

test("keyboard-only sign-in with skip link and visible focus; 320px reflow without horizontal scroll", async ({ page }) => {
  await page.goto("/welcome");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Email")).toBeFocused();
  await page.keyboard.type("demo@thinkfirst.local");
  await page.keyboard.press("Tab");
  await page.keyboard.type("demo-password");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/today/);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await page.setViewportSize({ width: 320, height: 720 });
  for (const url of ["/today", "/subjects", "/subjects/new", "/settings?section=privacy"]) {
    await page.goto(url);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, url).toBeLessThanOrEqual(0);
  }
  await expect(page.getByRole("navigation", { name: "Main" }).last()).toBeVisible(); // mobile bottom bar
});

test("start wizard 'test my level': test first -> roadmap built on the level -> my path -> summary; back works", async ({ page }) => {
  await signUpFresh(page);
  await page.goto("/subjects/new");
  await expect(page.locator("[data-screen=C01]")).toBeVisible();
  await page.getByRole("button", { name: "I want to learn something new" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("Topic", { exact: true }).fill("Algebra");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Back to the previous question" }).click(); // wizard back keeps the answers
  await expect(page.getByLabel("Topic", { exact: true })).toHaveValue("Algebra");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Yes — use my course" }).click();
  await page.locator("#files").setInputFiles(FIXTURE);
  await page.getByLabel(/I may use these materials/).check();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Yes — test my level" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText("Level test first, then everything adapts to your level")).toBeVisible();
  await page.getByRole("button", { name: "Build my learning path" }).click();
  await page.getByRole("button", { name: "Confirm scope" }).click();

  // the level test comes right after the roadmap is confirmed
  await expect(page).toHaveURL(/\/diagnostic$/);
  // the roadmap stays locked until the test is done; Back returns to the test
  await page.getByRole("link", { name: "Roadmap", exact: true }).click();
  await expect(page.locator("[data-screen=W01-locked]")).toBeVisible();
  await page.getByRole("button", { name: "Back to the previous page" }).click();
  await expect(page).toHaveURL(/\/diagnostic$/);

  await page.getByRole("button", { name: /Start the level test/ }).click();
  const question = page.locator("[data-phase=diagnostic-question]");
  const result = page.locator("[data-phase=diagnostic-result]");
  await expect(question.or(result).first()).toBeVisible();
  for (let i = 0; i < 14 && !(await result.isVisible()); i++) {
    await Promise.all([page.waitForResponse((r) => r.url().includes("/diagnostic/answer")),
      page.getByRole("button", { name: "I don't know yet" }).click()]);
    await expect(question.or(result).first()).toBeVisible();
  }
  await expect(page.getByTestId("level-label")).toHaveText("Beginner");
  await expect(page.getByText(/Level score/)).toBeVisible();

  // the roadmap now shows, built on the measured level
  await page.getByRole("button", { name: "See my roadmap (built on your level)" }).click();
  await expect(page.locator("[data-screen=W01]")).toBeVisible();
  await expect(page.getByTestId("roadmap-level")).toContainText("Beginner");

  await page.getByRole("link", { name: "My path", exact: true }).click();
  await expect(page.locator("[data-step=level]")).toHaveAttribute("data-state", "done");
  await expect(page.locator("[data-step=summary]")).toHaveAttribute("data-state", "done");
  await page.getByRole("button", { name: "Read summary" }).click();
  await expect(page.locator("[data-screen=R01]")).toBeVisible();
});
