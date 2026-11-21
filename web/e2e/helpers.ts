import { expect, Page } from "@playwright/test";
import path from "node:path";

export const FIXTURE = path.join(__dirname, ".fixtures", "math101.pdf");

export async function signInDemo(page: Page) {
  await page.goto("/welcome");
  await page.getByLabel("Email").fill("demo@thinkfirst.local");
  await page.getByLabel("Password").fill("demo-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/today/);
}

export async function signUpFresh(page: Page) {
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  await page.goto("/welcome");
  await page.getByRole("button", { name: "Create an account instead" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("e2e-password-123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/onboarding/);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/subjects$/);
  return email;
}

/** Start wizard (C01): exam -> topic -> my course files -> start from scratch -> build. Ends on C02. */
export async function wizardWithCourse(page: Page, addFiles: () => Promise<void>, topic = "MATH 101") {
  await expect(page.locator("[data-screen=C01]")).toBeVisible();
  await page.getByRole("button", { name: "I'm preparing for an exam" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("Topic", { exact: true }).fill(topic);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Yes — use my course" }).click();
  await addFiles();
  await page.getByLabel(/I may use these materials/).check();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "No — start from scratch" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Build my learning path" }).click();
  await expect(page.locator("[data-screen=C02]")).toBeVisible();
}

/** C01 wizard -> C02 -> confirm -> J01 (my path) -> W01 with the fixture PDF; returns subject URL base. */
export async function createSubjectFromFixture(page: Page) {
  await page.goto("/subjects/new");
  await wizardWithCourse(page, () => page.locator("#files").setInputFiles(FIXTURE));
  await page.getByRole("button", { name: "Confirm scope" }).click();
  await expect(page).toHaveURL(/\/start$/);
  const base = page.url().replace(/\/start$/, "");
  await page.goto(`${base}/roadmap`);
  return base;
}

/** From W01: start the distributive-property session and reach the given stage. */
export async function startDistributive(page: Page) {
  await page.getByRole("link", { name: /1\.2 The distributive property/ }).click();
  await page.getByRole("button", { name: "Learn this concept" }).click();
  await expect(page).toHaveURL(/\/setup$/);
  await page.getByLabel("Text").check();
  await page.getByRole("button", { name: "Start session" }).click();
  await expect(page.locator("[data-screen=S02]")).toBeVisible();
}

export async function passPractice(page: Page) {
  await page.getByRole("button", { name: "Continue" }).click(); // recall
  await page.getByRole("button", { name: "Continue to practice" }).click(); // learn
  await page.getByLabel("Your answer").fill("2x + 6");
  await page.getByRole("button", { name: "Check my reasoning" }).click();
  await page.getByRole("button", { name: "Continue to explain-back" }).click();
}

export async function typedExplanation(page: Page, text: string) {
  await page.getByRole("tab", { name: "Text" }).click();
  await page.getByLabel("Your explanation").fill(text);
  await page.getByRole("button", { name: "Review text" }).click();
  await page.getByRole("button", { name: "Confirm and assess" }).click();
  await expect(page.locator("[data-phase=explanation-feedback]")).toBeVisible();
}
