import { expect, test } from "@playwright/test";

test("dashboard creates a content workflow item", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Good morning, Nadia/i })).toBeVisible();

  await page.getByRole("button", { name: /New content/i }).click();
  await page.getByLabel("Content topic").fill("Playwright content workflow smoke test");
  await page.getByRole("button", { name: /Create content/i }).click();

  await expect(page.getByRole("table").getByText("Playwright content workflow smoke test", { exact: true })).toBeVisible();
  await expect(page.getByText("Content item created", { exact: true })).toBeVisible();
});

test("approved content exposes scheduling controls", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("table").getByText("The quiet cost of publishing without an approval workflow", { exact: true }).click();
  await expect(page.getByText("Publishing readiness", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Publish approved content/i })).toBeVisible();
  await expect(page.getByText("Schedule publishing", { exact: true })).toBeVisible();
});

test("workspace projects and team screens load", async ({ page }) => {
  await page.goto("/projects");
  await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
  await expect(page.getByText("AXIS Consulting", { exact: true })).toBeVisible();

  await page.goto("/team");
  await expect(page.getByRole("heading", { name: "Team" })).toBeVisible();
  await expect(page.getByText("Nadia Rahman", { exact: true })).toBeVisible();
});

test("admin can edit and archive a project in local mode", async ({ page }) => {
  await page.goto("/projects");
  await page.getByLabel("Project name").fill("Lifecycle test project");
  await page.getByRole("button", { name: /Create project/i }).click();
  await expect(page.getByText("Lifecycle test project", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: /Edit Lifecycle test project/i }).click();
  await page.getByLabel("Edit name for Lifecycle test project").fill("Archived lifecycle project");
  await page.getByRole("button", { name: "Save project" }).click();
  await expect(page.getByText("Archived lifecycle project", { exact: true })).toBeVisible();
  const projectRow = page.locator(".management-row").filter({ hasText: "Archived lifecycle project" });
  await projectRow.getByText("Archive", { exact: true }).click();
  await expect(projectRow.getByText("ARCHIVED", { exact: true })).toBeVisible();
});

test("invitation acceptance screen loads from a workspace link", async ({ page }) => {
  await page.goto("/invite/accept?workspace_id=ws_demo");
  await expect(page.getByRole("heading", { name: "Join your workspace" })).toBeVisible();
  await expect(page.getByLabel("Workspace ID")).toHaveValue("ws_demo");
});

test("team admin can preview an invite and soft-disable a member", async ({ page }) => {
  await page.goto("/team");
  await page.getByLabel("Invite email").fill("preview.member@axis.local");
  await page.getByRole("button", { name: /Preview email/i }).click();
  await expect(page.getByText("You have been invited to AXIS OS", { exact: true })).toBeVisible();

  const memberRow = page.locator(".management-row").filter({ hasText: "Samira Islam" });
  await memberRow.getByText("Deactivate", { exact: true }).click();
  await expect(memberRow.getByText("DISABLED", { exact: true })).toBeVisible();
  await memberRow.getByText("Reactivate", { exact: true }).click();
  await expect(memberRow.getByText("ACTIVE", { exact: true })).toBeVisible();
});

test("notifications screen shows delivery tracking", async ({ page }) => {
  await page.goto("/notifications");
  await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
  await expect(page.getByText("Copy is ready for review", { exact: true })).toBeVisible();
  await expect(page.getByText("FAILED", { exact: true })).toBeVisible();
});

test("operations screen shows provider health and response times", async ({ page }) => {
  await page.goto("/operations");
  await expect(page.getByRole("heading", { name: "System health" })).toBeVisible();
  await expect(page.getByText("Connection status and latency", { exact: true })).toBeVisible();
  await expect(page.getByText("openai", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Average response", { exact: true })).toBeVisible();
});
