import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

test.use({ viewport: { width: 1920, height: 1080 } });

// a granted port whose bytes the test writes with window.__pushLine; what the page writes to it lands in window.__sent
const FAKE_SERIAL = () => {
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();
  const sent: string[] = [];
  let controller: ReadableStreamDefaultController<Uint8Array> | undefined;
  const readable = new ReadableStream<Uint8Array>({ start: (c) => void (controller = c) });
  const writable = new WritableStream<Uint8Array>({ write: (chunk) => void sent.push(decoder.decode(chunk)) });
  const port = { readable, writable, open: async () => {}, close: async () => {}, setSignals: async () => {} };
  (window as unknown as { __sent: string[] }).__sent = sent;
  Object.defineProperty(navigator, "serial", {
    value: {
      requestPort: async () => port,
      getPorts: async () => [port],
      addEventListener() {},
      removeEventListener() {},
    },
  });
  (window as unknown as { __pushLine: (line: string) => void }).__pushLine = (line) => controller?.enqueue(encoder.encode(`${line}\n`));
};

const NO_SERIAL = () => {
  Object.defineProperty(navigator, "serial", { value: undefined });
};

const REPLAY = [
  { kind: "heart_rate", value: 91, label: null, unit: "bpm", quality: 0.9, t: 0 },
  { kind: "spo2", value: 95, label: null, unit: "%", quality: 0.9, t: 200 },
  { kind: "heart_rate", value: 92, label: null, unit: "bpm", quality: 0.9, t: 1200 },
  { kind: "heart_rate", value: 93, label: null, unit: "bpm", quality: 0.9, t: 20000 },
];

const RESULTS = { heart_rate: { n: 48, bias: 1, sd: 2.45, loa_low: -3.8, loa_high: 5.8, mae: 2.1, within_tolerance: 0.94, people: 6 } };

const HR_LABEL = "tested on 48 pairs: 95% of readings within \u22123.8 to +5.8 bpm of the reference";

function foreignRequests(page: Page) {
  const foreign: string[] = [];
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (url.protocol.startsWith("http") && !["localhost", "127.0.0.1"].includes(url.hostname)) foreign.push(req.url());
  });
  return foreign;
}

// the build lists the optional files it found; add one so the page asks for the routed copy
async function listFile(page: Page, file: string) {
  await page.route(/\/mission\/(\?.*)?$/, async (route) => {
    const response = await route.fetch();
    const body = (await response.text()).replace(/(<meta name="orbit-files" content=")([^"]*)/, `$1$2 ${file}`);
    await route.fulfill({ response, body });
  });
}

const push = (page: Page, line: string) => page.evaluate((l) => (window as unknown as { __pushLine: (l: string) => void }).__pushLine(l), line);
const reading = (page: Page, name: string) => page.getByRole("group", { name, exact: true });
const ground = (page: Page) => page.getByRole("region", { name: "GROUND" });
// GROUND is the Verify step; one step is on screen at a time
const verify = (page: Page) => page.getByRole("banner").getByRole("button", { name: "Verify" }).click();
const conversation = (page: Page) => ground(page).getByRole("group", { name: "Conversation" });
async function chat(page: Page, answers: string[]) {
  for (const answer of answers) await conversation(page).getByRole("button", { name: answer, exact: true }).click();
}
const seeOrder = (page: Page) => conversation(page).getByRole("button", { name: "See the order" }).click();
const startOver = (page: Page) => conversation(page).getByRole("button", { name: "Start over" }).click();
async function type(page: Page, text: string) {
  await conversation(page).getByLabel("Type the answer").fill(text);
  await conversation(page).getByRole("button", { name: "Send", exact: true }).click();
}
const badge = (page: Page, text: string) => page.getByRole("banner").getByText(text, { exact: true });

async function pressR(page: Page) {
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  await page.keyboard.press("r");
}

test("(d) pod lines reach GROUND within a second; bad lines change nothing", async ({ page }) => {
  await page.addInitScript(FAKE_SERIAL);
  const foreign = foreignRequests(page);
  await page.goto("/mission/");
  await verify(page);
  await expect(ground(page).getByRole("status", { name: "pod K-01, not connected" })).toBeVisible();
  await expect(ground(page).getByText("Not yet tested against a reference")).toHaveCount(0);
  await expect(reading(page, "Heart rate")).toHaveCount(0);
  await expect(ground(page).getByRole("button", { name: "Connect pod" })).toHaveCount(0);

  await push(page, '{"k":"hr","v":72,"q":0.93}');
  await push(page, '{"k":"spo2","v":98,"q":0.9}');
  await push(page, '{"k":"temp","v":24.1}');
  await push(page, '{"k":"rh","v":41}');
  await push(page, '{"k":"mosq","label":"An. arabiensis","conf":0.84}');
  await expect(reading(page, "Heart rate")).toContainText("72", { timeout: 1000 });
  await expect(reading(page, "SpO2")).toContainText("98", { timeout: 1000 });
  await expect(reading(page, "Temperature")).toContainText("24.1", { timeout: 1000 });
  await expect(reading(page, "Humidity")).toContainText("41", { timeout: 1000 });
  await expect(ground(page).locator("[data-heard]")).toContainText("An. arabiensis", { timeout: 1000 });
  await expect(ground(page).locator("[data-heard]")).toContainText("84%");
  await expect(ground(page).getByText("live", { exact: true })).toBeVisible();
  await expect(badge(page, "REPLAY")).toHaveCount(0);

  await push(page, '{"k":"hr","v":7');
  await push(page, '{"k":"hr","v":0}');
  await push(page, '{"k":"spo2","v":104}');
  await page.waitForTimeout(500);
  await expect(reading(page, "Heart rate")).toContainText("72");
  await expect(reading(page, "SpO2")).toContainText("98");
  expect(foreign).toEqual([]);
});

test("(e) silence shows the pod as not connected; R replays under the REPLAY badge and R again stops", async ({ page }) => {
  await page.addInitScript(FAKE_SERIAL);
  await listFile(page, "pod/replay.json");
  await page.route("**/pod/replay.json", (route) => route.fulfill({ json: REPLAY }));
  const foreign = foreignRequests(page);
  await page.goto("/mission/");
  await verify(page);
  await push(page, '{"k":"hr","v":72,"q":0.93}');
  await expect(ground(page).getByText("live", { exact: true })).toBeVisible();

  await expect(ground(page).getByRole("status", { name: "pod K-01, not connected" })).toBeVisible({ timeout: 6000 });
  await expect(reading(page, "Heart rate")).toContainText(/at \d\d:\d\d:\d\d/);

  await pressR(page);
  await expect(reading(page, "Heart rate")).toContainText("91", { timeout: 2000 });
  await expect(badge(page, "REPLAY")).toBeVisible();
  await expect(ground(page).getByText("replay", { exact: true })).toBeVisible();
  await expect(reading(page, "Heart rate")).toContainText("92", { timeout: 2500 });

  // a live line during the replay is held back, never shown under REPLAY
  await push(page, '{"k":"hr","v":75,"q":0.9}');
  await page.waitForTimeout(300);
  await expect(reading(page, "Heart rate")).toContainText("92");
  await expect(reading(page, "Heart rate")).not.toContainText("75");

  await pressR(page);
  await expect(badge(page, "REPLAY")).toHaveCount(0);
  await expect(reading(page, "Heart rate")).toHaveCount(0);
  await expect(reading(page, "SpO2")).toHaveCount(0);
  await expect(ground(page).getByRole("status", { name: "pod K-01, not connected" })).toBeVisible();

  await push(page, '{"k":"hr","v":76,"q":0.9}');
  await expect(reading(page, "Heart rate")).toContainText("76", { timeout: 1000 });
  await expect(ground(page).getByText("live", { exact: true })).toBeVisible();
  await expect(badge(page, "REPLAY")).toHaveCount(0);
  expect(foreign).toEqual([]);
});

test("a replay that runs to its end leaves no replayed reading on screen", async ({ page }) => {
  await page.addInitScript(FAKE_SERIAL);
  await listFile(page, "pod/replay.json");
  const short = [...REPLAY.slice(0, 3), { kind: "spo2", value: 96, label: null, unit: "%", quality: 0.9, t: 2600 }];
  await page.route("**/pod/replay.json", (route) => route.fulfill({ json: short }));
  await page.goto("/mission/");
  await verify(page);
  await push(page, '{"k":"hr","v":72,"q":0.93}');
  await expect(reading(page, "Heart rate")).toContainText("72");

  await pressR(page);
  await expect(reading(page, "Heart rate")).toContainText("91", { timeout: 2000 });
  await expect(badge(page, "REPLAY")).toBeVisible();
  await expect(reading(page, "Heart rate")).toContainText("92", { timeout: 2500 });
  await expect(badge(page, "REPLAY")).toHaveCount(0, { timeout: 3000 });
  await expect(reading(page, "Heart rate")).toHaveCount(0);
  await expect(reading(page, "SpO2")).toHaveCount(0);
  await expect(ground(page).getByRole("status", { name: "pod K-01, not connected" })).toBeVisible();
});

test("the simulator holds back a live line, and SIMULATION stays on the readings it shows", async ({ page }) => {
  await page.addInitScript(FAKE_SERIAL);
  await page.goto("/mission/?sim=1");
  await verify(page);
  await expect(reading(page, "Heart rate")).toBeVisible();
  await push(page, '{"k":"hr","v":200,"q":0.9}');
  for (let i = 0; i < 6; i++) {
    await page.waitForTimeout(250);
    await expect(reading(page, "Heart rate")).not.toContainText("200");
    await expect(badge(page, "SIMULATION")).toBeVisible();
    await expect(ground(page).getByText("simulation", { exact: true })).toBeVisible();
  }
  await expect(ground(page).getByText("live", { exact: true })).toHaveCount(0);
});

test("?record=1 records live pod lines and Download session gives the replay.json shape", async ({ page }) => {
  await page.addInitScript(FAKE_SERIAL);
  await page.goto("/mission/?record=1");
  await verify(page);
  await push(page, '{"k":"hr","v":72,"q":0.93}');
  await push(page, "garbage");
  await push(page, '{"k":"spo2","v":98,"q":0.9}');
  await push(page, '{"k":"mosq","label":"An. arabiensis","conf":0.84}');
  await expect(ground(page).locator("[data-heard]")).toContainText("An. arabiensis");

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    ground(page).getByRole("button", { name: "Download session" }).click(),
  ]);
  expect(download.suggestedFilename()).toBe("replay.json");
  const body = JSON.parse(readFileSync((await download.path())!, "utf8")) as Record<string, unknown>[];
  for (const event of body) expect(typeof event.t).toBe("number");
  expect(body.map((event) => ({ ...event, t: undefined }))).toEqual([
    { kind: "heart_rate", value: 72, label: null, unit: "bpm", quality: 0.93 },
    { kind: "spo2", value: 98, label: null, unit: "%", quality: 0.9 },
    { kind: "mosquito", value: null, label: "An. arabiensis", unit: null, quality: 0.84 },
  ]);
  const times = body.map((e) => e.t as number);
  expect(times).toEqual([...times].sort((a, b) => a - b));
  for (const event of body) expect(Object.keys(event).sort()).toEqual(["kind", "label", "quality", "t", "unit", "value"]);
});

test("(e) R with no replay file shows a toast", async ({ page }) => {
  await page.addInitScript(FAKE_SERIAL);
  await page.goto("/mission/");
  await verify(page);
  await expect(ground(page).getByRole("status", { name: "pod K-01, not connected" })).toBeVisible();
  await pressR(page);
  await expect(page.getByText("No replay recorded yet")).toBeVisible();
  await expect(badge(page, "REPLAY")).toHaveCount(0);
});

test("(f) simulation stays badged, error labels come from the results file, triage drives the order and delivery", async ({ page }) => {
  await page.addInitScript(FAKE_SERIAL);
  await listFile(page, "validation/results.json");
  await page.route("**/validation/results.json", (route) => route.fulfill({ json: RESULTS }));
  const foreign = foreignRequests(page);
  await page.goto("/mission/?sim=1");
  await verify(page);

  const hr = reading(page, "Heart rate");
  await expect(hr).toBeVisible();
  let changes = 0;
  let before = await hr.innerText();
  for (let i = 0; i < 12; i++) {
    await page.waitForTimeout(250);
    const now = await hr.innerText();
    if (now !== before) {
      changes++;
      await expect(badge(page, "SIMULATION")).toBeVisible();
      await expect(ground(page).getByText("simulation", { exact: true })).toBeVisible();
    }
    before = now;
  }
  expect(changes).toBeGreaterThan(0);

  await expect(ground(page).getByText(HR_LABEL)).toBeVisible();
  await expect(ground(page).getByText(/^Not yet tested against a reference: .*SpO2/)).toBeVisible();

  const action = page.getByRole("region", { name: "ACTION" });
  await chat(page, ["No", "none of these"]);
  await expect(conversation(page).getByTestId("advice").first()).toHaveText("No fever and no danger sign, so no test is needed now.");
  await seeOrder(page);
  await expect(action.getByText(/^No fever, no danger sign\. SpO2 is \d+% \(simulation\)\./)).toBeVisible();

  await verify(page);
  await startOver(page);
  await chat(page, ["Yes", "very sleepy or hard to wake"]);
  await seeOrder(page);
  await expect(action.getByText("Urgent referral")).toBeVisible();
  await expect(action.getByText("Danger sign reported: very sleepy or hard to wake.")).toBeVisible();
  await expect(action.getByRole("group", { name: "Order" })).toContainText("Referral transport to the nearest hospital");
  await expect(action.getByRole("group", { name: "Delivery" })).toContainText("simulated vehicle");
  await expect(action.getByText("Decision support, not a diagnosis.")).toBeVisible();
  await expect(action.getByText("Start of the rains (stand-in for road closure)")).toBeVisible();

  await page.waitForLoadState("networkidle");
  expect(foreign).toEqual([]);
});

test("(f) without a results file every reading is not yet tested; a typed answer triages", async ({ page }) => {
  await page.addInitScript(FAKE_SERIAL);
  await page.goto("/mission/");
  await verify(page);
  const patient = page.getByRole("region", { name: "GROUND" });
  await expect(patient.getByText(HR_LABEL)).toHaveCount(0);
  await expect(patient.getByText(/^Not yet tested against a reference/)).toHaveCount(0);
  for (const line of ['{"k":"hr","v":72}', '{"k":"temp","v":24.1}', '{"k":"rh","v":41}', '{"k":"dist","v":23.4}']) await push(page, line);
  await expect(patient.getByText("Not yet tested against a reference: temperature, humidity, heart rate, distance to surface.")).toBeVisible();

  await type(page, "yes, since last night");
  await type(page, "he cannot drink anything");
  await seeOrder(page);
  const action = page.getByRole("region", { name: "ACTION" });
  await expect(action.getByText("Urgent referral")).toBeVisible();
  await expect(action.getByText("Answer mentions: cannot drink. Confirm with the carer.")).toBeVisible();

  await verify(page);
  await startOver(page);
  await type(page, "maybe");
  await expect(conversation(page).getByText("Sorry, I did not catch that. Please answer yes or no.")).toBeVisible();
  await type(page, "no");
  await type(page, "no fits, not sleepy, vomited once yesterday");
  await seeOrder(page);
  await expect(action.getByText("No danger sign found", { exact: true })).toBeVisible();
  await expect(action.getByText(/SpO2 not measured\./)).toBeVisible();
});

test("car kit prototype: distance and light show in GROUND, a planned delivery sends dispatch, the acknowledgement shows", async ({ page }) => {
  await page.addInitScript(FAKE_SERIAL);
  await page.goto("/mission/");
  await verify(page);
  await expect(ground(page).getByText("Not yet tested against a reference")).toHaveCount(0);
  await expect(reading(page, "Heart rate")).toHaveCount(0);
  await expect(reading(page, "Distance to surface")).toHaveCount(0);
  await expect(reading(page, "Light on panel")).toHaveCount(0);

  await push(page, "pod K-01 early prototype (Uno car kit) ready");
  await push(page, '{"k":"dist","v":23.4}');
  await push(page, '{"k":"light","v":62}');
  await expect(reading(page, "Distance to surface")).toContainText("23.4", { timeout: 1000 });
  await expect(reading(page, "Light on panel")).toContainText("62", { timeout: 1000 });
  await expect(ground(page).getByText("Not yet tested against a reference: distance to surface, light on panel (uncalibrated).")).toBeVisible();
  await expect(ground(page).getByText("live", { exact: true })).toBeVisible();

  const action = page.getByRole("region", { name: "ACTION" });
  const sent = () => page.evaluate(() => (window as unknown as { __sent: string[] }).__sent);
  await chat(page, ["No", "none of these"]);
  await seeOrder(page);
  await expect(action.getByRole("group", { name: "Order" })).toContainText("No order: no danger sign found.");
  expect(await sent()).toEqual([]);

  await verify(page);
  await startOver(page);
  await chat(page, ["Yes", "very sleepy or hard to wake"]);
  await seeOrder(page);
  const delivery = action.getByRole("group", { name: "Delivery" });
  await expect(delivery).toContainText("simulated vehicle");
  await expect.poll(sent).toEqual(["dispatch\n"]);
  await expect(delivery).not.toContainText("Car kit acknowledged");

  await push(page, '{"ack":"dispatch"}');
  await expect(delivery).toContainText(/Car kit acknowledged the dispatch command at \d\d:\d\d:\d\d\./);
  await page.screenshot({ path: test.info().outputPath("car-kit.png") });
});

test("a browser without Web Serial says so", async ({ page }) => {
  await page.addInitScript(NO_SERIAL);
  await page.goto("/mission/");
  await verify(page);
  await expect(page.getByText("This browser cannot read the pod. Open the page in Chrome or Edge.")).toBeVisible();
});

test("no serial port granted shows Connect pod", async ({ page }) => {
  await page.goto("/mission/");
  await verify(page);
  const supported = await page.evaluate(() => "serial" in navigator);
  test.skip(!supported, "this browser has no Web Serial");
  await expect(ground(page).getByRole("button", { name: "Connect pod" })).toBeVisible();
});
