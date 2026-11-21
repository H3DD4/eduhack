import { expect, test } from "@playwright/test";
import { signInDemo, wizardWithCourse } from "./helpers";

/* The 8-state hackathon storyboard (blueprint "Build order and acceptance criteria"), on the seeded demo account,
   with REAL browser capture (Chromium fake microphone) and labeled demo transcription/assessment. */
test("demo storyboard: 2(x+3) misconception -> explain-back (voice) -> follow-up -> no-help transfer -> S03", async ({ page }) => {
  // 1. G01 empty -> one clear starting CTA
  await signInDemo(page);
  await expect(page.locator("[data-screen=G01]")).toBeVisible();
  await page.getByRole("link", { name: /Add a subject/ }).click();

  // 2. C01 start wizard: exam -> topic -> demo course PDF (limits + rights visible) -> start from scratch
  await wizardWithCourse(page, async () => {
    await expect(page.getByText(/up to 20 MB per file/)).toBeVisible();
    await page.getByRole("button", { name: "Use the demo course file" }).click();
    await expect(page.getByRole("list", { name: "Selected files" })).toContainText("MATH101");
  });

  // 3. C02: processing -> confirm scope with cited pages
  await expect(page.getByText(/Heuristic extraction/)).toBeVisible();
  await page.getByRole("button", { name: "See cited page 2" }).first().click();
  await page.getByRole("button", { name: "Confirm scope" }).click();

  // 3b. J01 my path: roadmap done, level = beginner (from scratch), summary of every page written for that level
  await expect(page.locator("[data-screen=J01]")).toBeVisible();
  await expect(page.locator("[data-step=level]")).toHaveAttribute("data-state", "done");
  await expect(page.getByTestId("level-label")).toHaveText("Beginner");
  await expect(page.locator("[data-step=summary]")).toHaveAttribute("data-state", "done");
  await page.getByRole("button", { name: "Read summary" }).click();
  await expect(page.locator("[data-screen=R01]")).toBeVisible();
  await expect(page.locator("p", { hasText: "Coverage:" })).toContainText(/(\d+)\/\1 pages/);
  await page.getByRole("link", { name: "Open roadmap" }).click();

  // 4. W01 + W06: vertical path, optional foundation, start concept
  await expect(page.locator("[data-screen=W01]")).toBeVisible();
  await expect(page.getByRole("link", { name: /Optional foundation: Order of operations/ })).toBeVisible();
  await page.getByRole("link", { name: /1\.2 The distributive property/ }).click();
  await expect(page.locator("[data-screen=W06]")).toBeVisible();
  await page.getByRole("button", { name: "Learn this concept" }).click();
  await page.getByLabel("Voice").check();
  await page.getByRole("button", { name: "Start session" }).click();

  // 5. S02 guided learn/practice: recall, cited chunk, attempt 2x + 3, misconception + one targeted question, early hint
  await expect(page.locator("[data-stage=recall]")).toBeVisible();
  await page.getByRole("button", { name: "I don't know" }).click();
  await expect(page.getByText(/Orientation:/)).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText(/multiplies every term inside the brackets/).first()).toBeVisible();
  await expect(page.getByRole("link", { name: /page 2/ })).toBeVisible();
  await page.getByRole("button", { name: "Continue to practice" }).click();
  await expect(page.getByText("Unverified source")).toBeVisible();
  await page.getByLabel("Your answer").fill("2x + 3");
  await page.getByRole("button", { name: "Check my reasoning" }).click();
  await expect(page.getByText(/Possible distribution misconception/)).toBeVisible();
  await expect(page.getByText(/What is 2 × 3\?/)).toBeVisible();
  await page.getByRole("button", { name: "Get help" }).click();
  await page.getByRole("button", { name: "I don't know where to start" }).click();
  await expect(page.getByText(/Step 1: Clarify the task/)).toBeVisible();
  await page.getByRole("button", { name: "Close help and return to task" }).click();
  await page.getByLabel("Your answer").fill("2x + 6");
  await page.getByRole("button", { name: "Check my reasoning" }).click();
  await expect(page.getByText(/equivalent and fully expanded/)).toBeVisible();
  await page.getByRole("button", { name: "Continue to explain-back" }).click();

  // 6. Explanation by voice: disclosure -> record -> playback -> upload -> demo transcript -> confirm -> cited feedback
  await expect(page.getByText("We assess your ideas, not your voice", { exact: false }).first()).toBeVisible();
  await expect(page.getByText(/Demo: no speech recognition is configured/)).toBeVisible();
  await page.getByRole("button", { name: "Enable microphone" }).click();
  await expect(page.getByText("Microphone connected. Recording has not started.").first()).toBeVisible();
  await page.getByRole("button", { name: "Start recording" }).click();
  await expect(page.getByText("Recording. Take your time.").first()).toBeVisible();
  await page.waitForTimeout(1500);
  await page.getByRole("button", { name: "Pause" }).click();
  await expect(page.getByText(/audio is not being added/).first()).toBeVisible();
  await page.getByRole("button", { name: "Resume" }).click();
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "Finish recording" }).click();
  await expect(page.getByRole("button", { name: "Use recording" })).toBeVisible();
  await page.getByRole("button", { name: "Use recording" }).click();
  await expect(page.locator("[data-phase=transcript-confirmation]")).toBeVisible();
  await expect(page.getByText(/Demo transcription \(simulated\)/).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirm and assess" })).toBeDisabled(); // unclear word unresolved
  await page.getByLabel(/“brackets” is what I meant/).check();
  await page.getByRole("button", { name: "Confirm and assess" }).click();
  await expect(page.locator("[data-phase=explanation-feedback]")).toBeVisible();
  await expect(page.getByText(/Simulated assessment/).first()).toBeVisible();
  await expect(page.locator("[data-criterion=correctness][data-status=demonstrated] blockquote").first()).toContainText("every term");
  const missing = page.locator("[data-criterion=example_application]");
  await expect(missing).toContainText("Not demonstrated");
  await expect(missing.locator("blockquote")).toHaveCount(0); // never an invented quote for a missing idea
  await expect(missing.getByRole("link", { name: "course page 2" })).toBeVisible();
  await expect(page.getByText("Audio deleted; transcript history remains.").first()).toBeVisible();
  await page.getByRole("button", { name: "Answer one follow-up" }).click();

  // one follow-up (text)
  await expect(page.getByText("One more question about that idea.")).toBeVisible();
  await page.getByRole("tab", { name: "Text" }).click();
  await page.getByLabel("Your explanation").fill("For example, 4(y + 2) = 4y + 8 because the 4 multiplies both terms.");
  await page.getByRole("button", { name: "Review text" }).click();
  await page.getByRole("button", { name: "Confirm and assess" }).click();
  await expect(page.locator("[data-phase=explanation-feedback]")).toBeVisible();
  await page.getByRole("button", { name: "Try new application" }).click();

  // 7. No-help transfer with a NEW expression and context
  await expect(page.locator("[data-phase=transfer-introduction]")).toBeVisible();
  await expect(page.getByText(/Lessons and hints stay unavailable/)).toBeVisible();
  await page.getByRole("button", { name: "Start without in-app help" }).click();
  const prompt = page.locator("#st-h");
  await expect(prompt).toContainText("3 packs of (x + 4) pens");
  await expect(prompt).not.toContainText("2(x + 3)");
  await expect(page.getByText("Independent application: no in-app lesson or hint access")).toBeVisible();
  // deep link to a source page in another tab is denied while locked
  const other = await page.context().newPage();
  const src = await page.evaluate(async () => (await (await fetch(location.pathname.replace(/\/subjects\/([^/]+).*/, "/api/subjects/$1/resources"))).json()).sources[0].id);
  const subjectBase = page.url().replace(/\/sessions\/.*/, "");
  await other.goto(`${subjectBase}/resources/${src}?page=2`);
  await expect(other.getByText("Hidden during independent application")).toBeVisible();
  await other.close();
  await page.getByLabel(/Your answer \(write both forms\)/).fill("3(x + 4) and 3x + 12");
  await page.getByRole("button", { name: "Check my answer" }).click();
  await expect(page.getByText("● Completed without in-app help")).toBeVisible();
  await page.getByRole("button", { name: "Reflect" }).click();

  // 8. S03: separate application/retention, reflection, review booking, return Today
  await expect(page.locator("[data-screen=S03]")).toBeVisible();
  await expect(page.getByText("Applied independently (no in-app help)").first()).toBeVisible();
  await expect(page.getByText(/Retention not checked yet/)).toBeVisible();
  await page.getByLabel(/What would you try next time/).fill("Draw the groups before expanding.");
  await page.getByRole("button", { name: "Save reflection" }).click();
  await expect(page.getByText("“Draw the groups before expanding.”")).toBeVisible();
  const due = await page.getByLabel("Review date").inputValue();
  expect(due).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  await page.getByRole("button", { name: "Finish and save review date" }).click();
  await expect(page).toHaveURL(/\/today/);
  await expect(page.getByText(/Review on/)).toBeVisible();
  await page.goto("/planner");
  await expect(page.getByText(/Review on/)).toBeVisible();
});
