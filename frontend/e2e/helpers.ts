import { expect, type Page } from "@playwright/test";

export const forbiddenPatterns = [
  /\bCASE-\d+/i, /\bCQ-\d+/i, /\bMNP-ELIG-\d+/i, /\bREG-MNP-CLAUSE-\d+/i,
  /\bEXEC-[A-Z0-9-]+/i, /\bELIGIBLE\b/, /\bBLOCKED\b/, /\bMANUAL_REVIEW\b/,
  /\bPASS\b/, /\bFAIL\b/, /\bVALID\b/, /\bFastAPI\b/, /\bJSON Schema\b/,
  /\bRDF Builder\b/, /\bOWL-RL\b/, /\bSPARQL\b/,
];

export async function expectChineseUi(page: Page) {
  const text = await page.locator("body").innerText();
  for (const pattern of forbiddenPatterns) expect(text).not.toMatch(pattern);
}

export async function openCase(page: Page, chineseCase: string) {
  await page.goto("/overview");
  await page.getByText(chineseCase, { exact: true }).first().click();
  await expect(page).toHaveURL(/\/assessments\/[^/]+$/);
}
