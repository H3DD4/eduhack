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

/** C01 -> C02 -> confirm -> W01 with the fixture PDF; returns subject URL base. */
export async function createSubjectFromFixture(page: Page) {
  await page.goto("/subjects/new");
  await page.locator("#files").setInputFiles(FIXTURE);
  await page.getByLabel("Subject name").fill("MATH 101");
  await page.getByLabel(/I may use these materials/).check();
  await page.getByRole("button", { name: "Create subject" }).click();
  await expect(page.getByRole("button", { name: "Confirm scope" })).toBeVisible();
  await page.getByRole("button", { name: "Confirm scope" }).click();
  await expect(page).toHaveURL(/\/roadmap$/);
  return page.url().replace(/\/roadmap$/, "");
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
