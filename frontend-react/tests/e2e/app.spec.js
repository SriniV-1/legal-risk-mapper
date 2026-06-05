// @ts-check
import { test, expect } from "@playwright/test";

// ─── Sample contract text long enough to pass the 10-char minimum ────────────
const SAMPLE_CONTRACT = [
  "SERVICE AGREEMENT",
  "",
  "This Service Agreement is entered into between Acme Software Inc.",
  '("Company") and the customer ("Client").',
  "",
  "1. LIABILITY",
  "IN NO EVENT SHALL COMPANY BE LIABLE FOR CONSEQUENTIAL, INCIDENTAL,",
  "OR PUNITIVE DAMAGES. Company's aggregate liability shall not exceed",
  "$100 regardless of the nature of the claim.",
  "",
  "2. MODIFICATIONS",
  "Company reserves the right to modify these terms at its sole",
  "discretion at any time without notice.",
].join("\n");

// ─────────────────────────────────────────────────────────────────────────────
// 1. Landing page
// ─────────────────────────────────────────────────────────────────────────────
test.describe("Landing page", () => {
  test("renders with expected heading and CTA button", async ({ page }) => {
    await page.goto("/");

    // The landing page has an h1 containing "Know the risk"
    await expect(page.locator("h1")).toContainText("Know the risk");

    // The nav bar shows the ALRM brand
    await expect(page.locator(".nav-logo")).toHaveText("ALRM");

    // Primary CTA — "Launch App" in the navbar
    const navCta = page.locator(".nav-cta");
    await expect(navCta).toBeVisible();
    await expect(navCta).toContainText("Launch App");

    // Hero CTA — "Analyze a Contract"
    const heroCta = page.locator(".btn-hero").first();
    await expect(heroCta).toBeVisible();
    await expect(heroCta).toContainText("Analyze a Contract");
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 2. Navigation
// ─────────────────────────────────────────────────────────────────────────────
test.describe("Navigation", () => {
  test("clicking Launch App navigates to the app page", async ({ page }) => {
    await page.goto("/");

    await page.locator(".nav-cta").click();
    await expect(page).toHaveURL(/\/app$/);

    // App page header should contain "Analysis"
    await expect(page.locator(".header-title")).toHaveText("Analysis");

    // The back link should say ALRM
    await expect(page.locator(".back-link")).toContainText("ALRM");
  });

  test("clicking ALRM back-link returns to landing page", async ({ page }) => {
    await page.goto("/app");
    await page.locator(".back-link").click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.locator("h1")).toContainText("Know the risk");
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 3. Text analysis flow
// ─────────────────────────────────────────────────────────────────────────────
test.describe("Text analysis flow", () => {
  test("paste contract text, click Analyze, risk cards appear", async ({ page }) => {
    await page.goto("/app");

    // The textarea should be visible (Paste Text tab is default)
    const textarea = page.locator(".clause-textarea");
    await expect(textarea).toBeVisible();

    // Type sample contract text
    await textarea.fill(SAMPLE_CONTRACT);

    // Character count updates
    await expect(page.locator(".char-count")).toContainText(
      `${SAMPLE_CONTRACT.length} characters`
    );

    // Click Analyze Risk
    await page.locator("button.btn-primary", { hasText: "Analyze Risk" }).click();

    // Wait for the risk analysis view to load (loader may appear first)
    await expect(page.locator(".card-title", { hasText: "Risk Analysis" })).toBeVisible({
      timeout: 30_000,
    });

    // Overall risk level badge should be visible
    await expect(page.locator(".risk-level-badge")).toBeVisible();

    // At least one severity badge should appear in the results
    const sevBadges = page.locator(".sev-badge");
    await expect(sevBadges.first()).toBeVisible({ timeout: 5_000 });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 4. Error handling — empty text
// ─────────────────────────────────────────────────────────────────────────────
test.describe("Error handling", () => {
  test("submitting empty text shows an error message", async ({ page }) => {
    await page.goto("/app");

    // Ensure textarea is empty
    const textarea = page.locator(".clause-textarea");
    await textarea.fill("");

    // Click Analyze Risk with no text
    await page.locator("button.btn-primary", { hasText: "Analyze Risk" }).click();

    // Error box should appear with the minimum-characters message
    const errorBox = page.locator(".error-box");
    await expect(errorBox).toBeVisible();
    await expect(errorBox).toContainText("at least 10 characters");
  });

  test("submitting very short text shows an error message", async ({ page }) => {
    await page.goto("/app");

    await page.locator(".clause-textarea").fill("short");
    await page.locator("button.btn-primary", { hasText: "Analyze Risk" }).click();

    await expect(page.locator(".error-box")).toBeVisible();
    await expect(page.locator(".error-box")).toContainText("at least 10 characters");
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 5. Sample text loading
// ─────────────────────────────────────────────────────────────────────────────
test.describe("Sample text", () => {
  test("clicking a sample button loads text into the textarea", async ({ page }) => {
    await page.goto("/app");

    // There should be sample buttons in the sidebar
    const sampleButtons = page.locator(".sample-btn");
    await expect(sampleButtons.first()).toBeVisible();

    // Click the first sample (SaaS Service Agreement)
    await sampleButtons.first().click();

    // Textarea should now have content (the sample text)
    const textarea = page.locator(".clause-textarea");
    await expect(textarea).not.toHaveValue("");

    // The sample text should contain "SERVICE AGREEMENT" or similar content
    const value = await textarea.inputValue();
    expect(value.length).toBeGreaterThan(100);
  });

  test("loading a sample and analyzing produces results", async ({ page }) => {
    await page.goto("/app");

    // Click a sample button to load text
    await page.locator(".sample-btn").first().click();

    // Click Analyze Risk
    await page.locator("button.btn-primary", { hasText: "Analyze Risk" }).click();

    // Wait for results
    await expect(page.locator(".card-title", { hasText: "Risk Analysis" })).toBeVisible({
      timeout: 30_000,
    });

    // Risk data should show total risks
    await expect(page.locator(".risk-subtitle")).toBeVisible();
    await expect(page.locator(".risk-subtitle")).toContainText(/\d+ risks? detected/);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 6. Results structure
// ─────────────────────────────────────────────────────────────────────────────
test.describe("Results structure", () => {
  test("risk cards have title, severity badge, and description", async ({ page }) => {
    await page.goto("/app");

    // Load sample and analyze
    await page.locator(".sample-btn").first().click();
    await page.locator("button.btn-primary", { hasText: "Analyze Risk" }).click();

    // Wait for risk analysis to appear
    await expect(page.locator(".card-title", { hasText: "Risk Analysis" })).toBeVisible({
      timeout: 30_000,
    });

    // Overall risk level badge (High / Medium / Low)
    const riskBadge = page.locator(".risk-level-badge");
    await expect(riskBadge).toBeVisible();
    const badgeText = await riskBadge.textContent();
    expect(["HIGH", "MEDIUM", "LOW", "NONE"]).toContain(badgeText?.trim());

    // Stats row should show counts for Total, High, Medium, Low
    const statChips = page.locator(".stat-chip");
    await expect(statChips).toHaveCount(4);

    // Total risks count should be >= 1
    const totalChip = statChips.first();
    const totalNum = await totalChip.locator(".stat-chip-num").textContent();
    expect(parseInt(totalNum || "0", 10)).toBeGreaterThanOrEqual(1);

    // Contract text section should be visible
    await expect(page.locator(".cr-body-title", { hasText: "Contract Text" })).toBeVisible();

    // Severity filter chips should be present
    const filterChips = page.locator(".filter-chip");
    await expect(filterChips).toHaveCount(4); // All, High, Medium, Low

    // Clicking a risk dot should expand the risk detail panel
    const riskDots = page.locator(".cr-dot");
    const dotCount = await riskDots.count();
    if (dotCount > 0) {
      await riskDots.first().click();

      // Expanded risk panel should show
      const expandedRisk = page.locator(".cr-expanded-risk");
      await expect(expandedRisk).toBeVisible();

      // It should contain a severity badge
      await expect(expandedRisk.locator(".sev-badge")).toBeVisible();

      // It should contain a risk type label
      await expect(expandedRisk.locator(".risk-type")).toBeVisible();
      const riskType = await expandedRisk.locator(".risk-type").textContent();
      expect(riskType?.trim().length).toBeGreaterThan(0);

      // It should contain an explanation
      const explanation = expandedRisk.locator(".cr-exp-explanation");
      if ((await explanation.count()) > 0) {
        await expect(explanation).toBeVisible();
      }

      // It should contain a confidence score
      await expect(expandedRisk.locator(".cr-exp-conf")).toBeVisible();
    }
  });

  test("analysis notes section is displayed", async ({ page }) => {
    await page.goto("/app");

    await page.locator(".sample-btn").first().click();
    await page.locator("button.btn-primary", { hasText: "Analyze Risk" }).click();

    await expect(page.locator(".card-title", { hasText: "Risk Analysis" })).toBeVisible({
      timeout: 30_000,
    });

    // Analysis notes should be present
    const notes = page.locator(".notes-section");
    await expect(notes).toBeVisible();
    const notesText = await notes.textContent();
    expect(notesText?.trim().length).toBeGreaterThan(0);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 7. App page — initial state
// ─────────────────────────────────────────────────────────────────────────────
test.describe("App page initial state", () => {
  test("shows get-started placeholder before any analysis", async ({ page }) => {
    await page.goto("/app");

    // The placeholder card should show "Get Started"
    await expect(page.locator(".card-title", { hasText: "Get Started" })).toBeVisible();

    // Guide steps should be visible
    const guideSteps = page.locator(".guide-step");
    await expect(guideSteps).toHaveCount(3);

    // Quick-analyze sample links should be present
    const guideLinks = page.locator(".guide-link");
    await expect(guideLinks).toHaveCount(2);
    await expect(guideLinks.first()).toContainText("SaaS Agreement");
    await expect(guideLinks.last()).toContainText("Privacy Policy");
  });

  test("tab switching works between Paste Text and Upload File", async ({ page }) => {
    await page.goto("/app");

    // Paste Text tab should be active by default
    const pasteTab = page.locator(".tab-btn", { hasText: "Paste Text" });
    const uploadTab = page.locator(".tab-btn", { hasText: "Upload File" });

    await expect(pasteTab).toHaveClass(/active/);
    await expect(page.locator("#tab-text")).toHaveClass(/active/);

    // Switch to Upload File tab
    await uploadTab.click();
    await expect(uploadTab).toHaveClass(/active/);
    await expect(page.locator("#tab-file")).toHaveClass(/active/);

    // Dropzone should be visible
    await expect(page.locator(".dropzone")).toBeVisible();

    // Switch back to Paste Text
    await pasteTab.click();
    await expect(pasteTab).toHaveClass(/active/);
    await expect(page.locator(".clause-textarea")).toBeVisible();
  });
});
