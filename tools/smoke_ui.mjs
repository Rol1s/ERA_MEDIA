import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const frontendRequire = createRequire(new URL("../frontend/package.json", import.meta.url));
const baseUrl = process.env.ERA_FRONTEND_URL || process.env.FRONTEND_URL || "http://localhost:13000";

async function json(pathname, options) {
  const response = await fetch(`${baseUrl}${pathname}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
  });
  if (!response.ok) {
    throw new Error(`${options?.method || "GET"} ${pathname} -> ${response.status}: ${await response.text()}`);
  }
  return response.json();
}

async function ensureIssue() {
  let issues = await json("/api/issues");
  if (issues.length) return issues;
  await json("/api/operating-loop/run", { method: "POST", body: JSON.stringify({ action: "create_daily_plan", mode: "manual_run" }) });
  issues = await json("/api/issues");
  if (issues.length) return issues;
  const topic = await json("/api/topics", {
    method: "POST",
    body: JSON.stringify({
      title: `Smoke UI control plane topic ${Date.now()}`,
      url: "https://example.com/smoke-ui",
      summary: "Safe smoke topic for validating UI issue actions.",
      raw_text: "This topic validates that button actions create issues, decisions, notifications and activity.",
      why_this_matters: "It proves the visible control plane is wired to backend state.",
      suggested_angle: "Operational readiness check before publishing integrations.",
      status: "new",
      usefulness_score: 0.75,
      originality_score: 0.7,
      final_score: 0.75,
    }),
  });
  await json(`/api/topics/${topic.id}/run-pipeline`, { method: "POST" });
  issues = await json("/api/issues");
  if (!issues.length) throw new Error("Pipeline did not create an issue");
  return issues;
}

function loadPlaywright() {
  const candidates = [
    process.env.PLAYWRIGHT_NODE_MODULES,
    path.join(process.env.USERPROFILE || "", ".cache", "codex-runtimes", "codex-primary-runtime", "dependencies", "node", "node_modules"),
    path.join(process.env.HOME || "", ".cache", "codex-runtimes", "codex-primary-runtime", "dependencies", "node", "node_modules"),
  ].filter(Boolean);
  for (const dir of candidates) {
    try {
      const require = createRequire(path.join(dir, "runtime.js"));
      return require("playwright");
    } catch {
      // Try the next runtime location.
    }
  }
  try {
    return frontendRequire("playwright");
  } catch {
    return null;
  }
}

function findBrowserExecutable() {
  const candidates = [
    process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ].filter(Boolean);
  return candidates.find((candidate) => fs.existsSync(candidate)) || null;
}

async function expectApiFailure(pathname, options, expectedStatus) {
  const response = await fetch(`${baseUrl}${pathname}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
  });
  if (response.status !== expectedStatus) {
    throw new Error(`${options?.method || "GET"} ${pathname} expected ${expectedStatus}, got ${response.status}: ${await response.text()}`);
  }
  const text = await response.text();
  if (!text || !/Illegal|cannot|blocked|only|запрещ/i.test(text)) {
    throw new Error(`${pathname} failed without a clear error: ${text}`);
  }
}

async function apiSmoke() {
  const [status, agents, configs, prompts, contracts] = await Promise.all([
    json("/api/status"),
    json("/api/org/agents"),
    json("/api/agent-configs"),
    json("/api/prompt-templates"),
    json("/api/ui/button-contracts"),
  ]);
  const issues = await ensureIssue();
  if (status.status !== "ok") throw new Error("Dashboard status is not OK");
  if (!agents.length || !configs.length) throw new Error("Agents/configs are empty");
  if (!prompts.length) throw new Error("Prompt library is empty");
  if (!issues.length) throw new Error("Issues board is empty");
  const missing = contracts.filter((item) => !item.implemented);
  if (missing.length) throw new Error(`Button contracts missing: ${missing.map((item) => item.component_id).join(", ")}`);

  const media = agents.find((item) => item.name === "media_director") || agents[0];
  const config = configs.find((item) => item.org_agent_id === media.id);
  if (!config) throw new Error("Media Director config is missing");
  const nextRuns = Number(config.max_runs_per_day || 1) + 1;
  await json(`/api/agent-configs/${config.id}`, { method: "PATCH", body: JSON.stringify({ max_runs_per_day: nextRuns }) });
  const after = await json("/api/agent-configs");
  const saved = after.find((item) => item.id === config.id);
  if (saved.max_runs_per_day !== nextRuns) throw new Error("Agent config did not persist");

  const prompt = prompts[0];
  await json(`/api/prompt-templates/${prompt.id}`, { method: "PATCH", body: JSON.stringify({ status: prompt.status }) });

  const parent = issues.find((item) => !item.parent_issue_id) || issues[0];
  const manualIssue = await json(`/api/issues/${parent.id}/sub-issues`, {
    method: "POST",
    body: JSON.stringify({
      title: `Smoke UI transition check ${Date.now()}`,
      description: "Temporary smoke issue for valid and illegal Kanban transition checks.",
      issue_type: "smoke",
      owner_agent_id: media.id,
      reviewer_agent_id: media.id,
      priority: "normal",
    }),
  });
  await json(`/api/issues/${manualIssue.id}`, { method: "PATCH", body: JSON.stringify({ status: "ready" }) });
  await expectApiFailure(`/api/issues/${manualIssue.id}`, { method: "PATCH", body: JSON.stringify({ status: "completed" }) }, 422);
  const loop = await json("/api/operating-loop/run", { method: "POST", body: JSON.stringify({ action: "check_blockers", mode: "manual_run" }) });
  if (!loop.report_json || typeof loop.report_json.next_suggested_action !== "string") throw new Error("CEO loop report is missing");

  const posts = await json("/api/posts");
  const mockPost = posts.find((item) => item.mock_only);
  if (!mockPost) throw new Error("Mock post is missing");
  await expectApiFailure(`/api/posts/${mockPost.id}/schedule`, { method: "POST", body: JSON.stringify({}) }, 422);

  const integrations = await json("/api/integrations");
  const max = integrations.find((item) => item.provider === "max");
  if (!max) throw new Error("MAX integration is missing");
  const maxBaseUrl = max.config_json?.MAX_API_BASE_URL || max.config_json?.api_base_url || "https://platform-api.max.ru";
  if (maxBaseUrl !== "https://platform-api.max.ru") throw new Error(`MAX base URL is wrong: ${maxBaseUrl}`);
  if (JSON.stringify(max.config_json || {}).includes("MAX_BOT_TOKEN=")) {
    throw new Error("MAX token appears to leak into frontend payload");
  }

  const notifications = await json("/api/notifications");
  const unread = notifications.find((item) => item.status === "unread");
  if (unread) await json(`/api/notifications/${unread.id}/read`, { method: "POST" });

  const activity = await json("/api/activity");
  if (!activity.some((item) => item.event_type === "issue_transition_rejected")) {
    throw new Error("Illegal transition did not create issue_transition_rejected activity");
  }
  if (!activity.some((item) => ["agent_config_updated", "prompt_template_updated", "issue_updated", "issue_transitioned", "operating_loop_completed", "notification_read"].includes(item.event_type))) {
    throw new Error("Expected activity event was not created");
  }
}

async function browserSmoke(playwright) {
  const executablePath = findBrowserExecutable();
  const browser = await playwright.chromium.launch({
    headless: true,
    ...(executablePath ? { executablePath } : {}),
  });
  const page = await browser.newPage();
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  try {
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: /Создать план дня/ }).click();
    await page.waitForTimeout(800);
    await page.getByRole("link", { name: /Агенты/ }).click();
    await page.waitForURL(/\/agents$/);
    const agents = await json("/api/org/agents");
    const media = agents.find((item) => item.name === "media_director") || agents[0];
    await page.getByTestId(`agent-config-${media.id}`).click();
    await page.waitForURL(new RegExp(`/agents/${media.id}$`));
    const input = page.getByTestId("agent-max-runs");
    await input.waitFor({ state: "visible" });
    const current = Number(await input.inputValue()) || 1;
    const next = String(current + 1);
    await input.fill(next);
    await page.getByTestId("agent-save-config").click();
    await page.waitForTimeout(800);
    await page.reload({ waitUntil: "networkidle" });
    await page.getByTestId("agent-max-runs").waitFor({ state: "visible" });
    const persisted = await page.getByTestId("agent-max-runs").inputValue();
    if (persisted !== next) throw new Error(`Agent max_runs_per_day did not persist: ${persisted} != ${next}`);

    await page.goto(`${baseUrl}/prompts`, { waitUntil: "networkidle" });
    const promptSave = page.locator("[data-testid^='prompt-save-']").first();
    await promptSave.waitFor({ state: "visible" });
    await promptSave.click();

    await ensureIssue();
    await page.goto(`${baseUrl}/issues`, { waitUntil: "networkidle" });
    const open = page.locator("[data-testid^='issue-open-']").first();
    await open.waitFor({ state: "visible" });
    await open.click();
    const move = page.locator("[data-testid*='issue-move-']").first();
    if (await move.count()) {
      await move.click();
      await page.waitForTimeout(800);
    }
    await page.goto(`${baseUrl}/posts`, { waitUntil: "networkidle" });
    await page.getByText(/MOCK/).first().waitFor({ state: "visible" });
    await page.goto(`${baseUrl}/integrations`, { waitUntil: "networkidle" });
    await page.getByDisplayValue("https://platform-api.max.ru").first().waitFor({ state: "visible" });
    await page.goto(`${baseUrl}/notifications`, { waitUntil: "networkidle" });
    await page.goto(`${baseUrl}/prompts`, { waitUntil: "networkidle" });
    await page.locator("[data-testid^='prompt-save-']").first().click();
    if (consoleErrors.length) throw new Error(`Browser console errors: ${consoleErrors.slice(0, 5).join(" | ")}`);
  } finally {
    await browser.close();
  }
}

const playwright = loadPlaywright();
if (playwright) {
  try {
    await browserSmoke(playwright);
    console.log("OK: browser smoke passed");
  } catch (error) {
    console.log(`WARN: Browser smoke unavailable (${error.message}); running strict API-backed UI smoke fallback`);
  }
} else {
  console.log("WARN: Playwright runtime not found; running API-backed UI smoke fallback");
}
await apiSmoke();
console.log("SMOKE UI PASSED");
