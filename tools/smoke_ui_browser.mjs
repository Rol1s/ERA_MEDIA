import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const frontendRequire = createRequire(new URL("../frontend/package.json", import.meta.url));
const baseUrl = process.env.ERA_FRONTEND_URL || process.env.FRONTEND_URL || "http://localhost:13000";

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
    } catch {}
  }
  try {
    return frontendRequire("playwright");
  } catch {
    return null;
  }
}

function browserExecutable() {
  const candidates = [
    process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
  ].filter(Boolean);
  return candidates.find((item) => fs.existsSync(item)) || null;
}

async function api(pathname, options) {
  const response = await fetch(`${baseUrl}${pathname}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
  });
  if (!response.ok) throw new Error(`${options?.method || "GET"} ${pathname} -> ${response.status}: ${await response.text()}`);
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

async function waitForToast(page) {
  await page.locator(".toast").first().waitFor({ state: "visible", timeout: 15000 });
}

async function ensureDryRunReady() {
  const [secrets, integrations] = await Promise.all([api("/api/secrets/status"), api("/api/integrations")]);
  const openai = secrets.providers.find((item) => item.provider === "openai");
  if (openai?.status !== "configured") throw new Error("OpenAI secret is not configured; browser smoke cannot run real dry-run.");
  await api("/api/settings", {
    method: "PATCH",
    body: JSON.stringify({
      system_mode: "dry_run",
      global_agents_enabled: true,
      global_publishing_enabled: false,
      global_routines_enabled: false,
      global_daily_budget_usd: 100,
      global_daily_token_limit: 5000000,
    }),
  });
  const model = integrations.find((item) => item.provider === "openai")?.config_json?.model || "gpt-4.1-mini";
  await api("/api/agent-configs/content-agents/openai", { method: "POST", body: JSON.stringify({ model }) });
  const channels = await api("/api/channels");
  const eraAi = channels.find((channel) => channel.slug === "era-ai") || channels[0];
  return api("/api/topics", {
    method: "POST",
    body: JSON.stringify({
      title: `OpenAI model selection for editorial agents ${Date.now()}`,
      url: "https://developers.openai.com/api/docs/models",
      summary: "OpenAI model documentation lists current GPT models, structured output support, and model choices that matter for agentic editorial workflows.",
      raw_text: "Source-backed editorial topic: explain how an AI newsroom should choose an OpenAI model for research, factcheck, editor and chief editor agents. Keep it practical, cautious, and require human review before publication.",
      why_this_matters: "ERA AI readers need a practical model-selection note for agentic workflows, not a raw documentation rewrite.",
      suggested_angle: "A decision guide for choosing a model by cost, latency and structured output reliability.",
      assigned_channel_ids: eraAi ? [eraAi.id] : [],
      status: "new",
      usefulness_score: 0.75,
      originality_score: 0.7,
      final_score: 0.75,
    }),
  });
}

const playwright = loadPlaywright();
if (!playwright) {
  throw new Error("Playwright runtime not found. On server run: npm --prefix frontend install playwright && npx playwright install chromium");
}
const executablePath = browserExecutable();
const browser = await playwright.chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
const page = await browser.newPage();
const consoleErrors = [];
const networkErrors = [];
let previousSettings = null;

page.on("console", (message) => {
  if (message.type() === "error" && !message.text().includes("favicon")) consoleErrors.push(message.text());
});
page.on("pageerror", (error) => consoleErrors.push(error.message));
page.on("response", (response) => {
  if (response.status() >= 500 || response.status() === 422) networkErrors.push(`${response.status()} ${response.url()}`);
});
page.on("requestfailed", (request) => {
  const url = request.url();
  const failure = request.failure()?.errorText || "";
  if (!url.includes("/api/events/stream") && !url.includes("_rsc=") && !failure.includes("ERR_ABORTED")) networkErrors.push(`${url} ${failure}`);
});

try {
  previousSettings = await api("/api/settings").catch(() => null);

  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: /Панель|оператора|Dashboard/i }).waitFor({ state: "visible" });
  await page.getByText(/Готовность системы|Что делать дальше/).first().waitFor({ state: "visible" });
  await page.getByRole("link", { name: /Интеграции|Открыть интеграции/ }).first().click();
  await page.waitForURL(/\/integrations/);

  await page.getByText(/OpenAI/).first().waitFor({ state: "visible" });
  await page.locator("select").first().waitFor({ state: "visible" });
  await page.getByRole("button", { name: /Применить OpenAI|content agents/i }).first().click();
  await waitForToast(page);

  await page.goto(`${baseUrl}/agents`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: /агентами|Agents/i }).waitFor({ state: "visible" });
  await page.getByRole("button", { name: /^Настроить$/ }).first().click();
  await page.locator("[data-testid='agent-max-runs']").first().fill("1000");
  await page.locator("[data-testid='agent-save-config']").first().click();
  await waitForToast(page);

  await page.goto(`${baseUrl}/channels`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: /Каналы/ }).waitFor({ state: "visible" });
  await page.getByRole("button", { name: /Сохранить правила/ }).click();
  await waitForToast(page);
  await page.getByRole("button", { name: /Проверить связь/ }).click();
  await waitForToast(page);

  await page.goto(`${baseUrl}/sources`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: /Источники/ }).waitFor({ state: "visible" });
  await page.waitForTimeout(1200);
  await page.getByPlaceholder("Название").first().fill(`Browser audit source ${Date.now()}`);
  await page.getByPlaceholder(/RSS|URL/).first().fill("https://example.com/browser-audit-rss");
  await page.locator("form button").first().waitFor({ state: "visible" });
  await page.waitForTimeout(300);
  const sourceFormState = await page.evaluate(() => ({
    values: Array.from(document.querySelectorAll("form input")).map((input) => input.value),
    disabled: document.querySelector("form button")?.disabled,
  }));
  if (sourceFormState.disabled) throw new Error(`Source form did not enable after fill: ${JSON.stringify(sourceFormState)}`);
  await page.locator("form button").first().click();
  await waitForToast(page);
  await page.getByRole("button", { name: /Проверить/ }).first().click();
  await waitForToast(page);

  await page.goto(`${baseUrl}/topics`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: /Темы/ }).waitFor({ state: "visible" });
  const topic = await ensureDryRunReady();
  await page.goto(`${baseUrl}/topics`, { waitUntil: "domcontentloaded" });
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByText(topic.title).locator("xpath=ancestor::article").getByRole("button", { name: /Run real dry-run|dry-run/i }).click();
  let dryRunPost = null;
  for (let i = 0; i < 90; i += 1) {
    const posts = await api("/api/posts");
    dryRunPost = posts.find((post) => post.topic_id === topic.id && post.generation_mode === "dry_run");
    if (dryRunPost) break;
    await page.waitForTimeout(2000);
  }
  if (!dryRunPost) throw new Error("Dry-run post was not created from topic card");

  await page.goto(`${baseUrl}/posts`, { waitUntil: "domcontentloaded" });
  await page.getByText(/DRY RUN|ТРЕБУЕТ ПРОВЕРКИ/).first().waitFor({ state: "visible" });
  await page.getByText(/нельзя публиковать|Публичная публикация MAX/).first().waitFor({ state: "visible" });
  await page.getByRole("button", { name: /Сохранить правки/ }).first().click();
  await waitForToast(page);
  await page.getByRole("button", { name: /Копировать/ }).first().click();
  await waitForToast(page);

  await page.goto(`${baseUrl}/issues`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: /Kanban/ }).waitFor({ state: "visible" });
  await page.getByRole("button", { name: /Открыть/ }).first().click();
  await page.getByText(/Допустимые переходы|Дерево задач/).first().waitFor({ state: "visible" });
  const issues = await api("/api/issues");
  const movable = issues.find((issue) => ["backlog", "ready", "in_progress", "review", "waiting_human"].includes(issue.status));
  if (movable) {
    const next = movable.status === "backlog" ? "ready" : movable.status === "ready" ? "in_progress" : movable.status === "in_progress" ? "review" : "waiting_human";
    await api(`/api/issues/${movable.id}`, { method: "PATCH", body: JSON.stringify({ status: next }) });
    const illegal = await fetch(`${baseUrl}/api/issues/${movable.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: "backlog" }) });
    if (illegal.status !== 422) throw new Error(`Illegal issue transition expected 422, got ${illegal.status}`);
  }

  await page.goto(`${baseUrl}/notifications`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: /Уведомления/ }).waitFor({ state: "visible" });
  const readButton = page.getByRole("button", { name: /Прочитано/ }).first();
  if (await readButton.count()) {
    await readButton.click();
    await waitForToast(page);
  }

  await page.goto(`${baseUrl}/routines`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: /Регламенты/ }).waitFor({ state: "visible" });
  await page.getByRole("button", { name: /Dry run/ }).first().click();
  await waitForToast(page);

  await page.goto(`${baseUrl}/prompts`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: /Промпты/ }).waitFor({ state: "visible" });
  await page.locator("[data-testid^='prompt-save-']").first().click();
  await waitForToast(page);

  await page.goto(`${baseUrl}/activity`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: /Активность/ }).waitFor({ state: "visible" });
  await page.getByRole("button", { name: /Применить/ }).click();
  await waitForToast(page);
  const activity = await api("/api/activity");
  for (const required of ["content_agents_openai_configured", "channel_updated", "source_created", "agent_run_completed"]) {
    if (!activity.some((item) => item.event_type === required)) throw new Error(`Missing activity event: ${required}`);
  }

  await page.goto(`${baseUrl}/logs`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: /Логи/ }).waitFor({ state: "visible" });

  const meaningfulNetworkErrors = networkErrors.filter((item) => !item.includes("/api/issues/"));
  if (meaningfulNetworkErrors.length) throw new Error(`Network errors: ${meaningfulNetworkErrors.slice(0, 8).join(" | ")}`);
  if (consoleErrors.length) throw new Error(`Console errors: ${consoleErrors.slice(0, 8).join(" | ")}`);
  console.log("SMOKE UI BROWSER PASSED");
} finally {
  const safeSettings = previousSettings
    ? { ...previousSettings, system_mode: "mock", global_agents_enabled: false, global_publishing_enabled: false, global_routines_enabled: false }
    : { system_mode: "mock", global_agents_enabled: false, global_publishing_enabled: false, global_routines_enabled: false };
  await api("/api/settings", { method: "PATCH", body: JSON.stringify(safeSettings) }).catch(() => {});
  await browser.close();
}
