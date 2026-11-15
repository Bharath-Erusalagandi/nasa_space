import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { geoContains } from "d3-geo";
import type { IndicatorKey, TrendIndex } from "../lib/trends/types";

const index = JSON.parse(readFileSync(join(__dirname, "../public/trends/index.json"), "utf8")) as TrendIndex;

function watch(page: Page) {
  const errors: string[] = [];
  const foreign: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (url.protocol.startsWith("http") && !["localhost", "127.0.0.1"].includes(url.hostname)) foreign.push(req.url());
  });
  return { errors, foreign };
}

function expectedOutlines(key: IndicatorKey) {
  const live = index.cells.filter((c) => !c.error);
  return {
    solid: live.filter((c) => c.indicators?.[key]?.significant_fdr).length,
    dashed: live.filter((c) => c.indicators?.[key]?.significant && !c.indicators?.[key]?.significant_fdr).length,
  };
}

const map = (page: Page) => page.locator("[data-map-ready]");
const legend = (page: Page) => page.locator("[data-legend]");

async function outlineCounts(page: Page) {
  return {
    solid: await map(page).locator('[data-outline-for][data-style="solid"]').count(),
    dashed: await map(page).locator('[data-outline-for][data-style="dashed"]').count(),
  };
}

test.use({ viewport: { width: 1920, height: 1080 } });

test("every cell in the index is drawn, and October temperature outlines match the index", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/mission/");
  await expect(map(page).locator("[data-cell]")).toHaveCount(index.cells.length);
  await expect(legend(page)).toContainText("October");
  expect(await outlineCounts(page)).toEqual(expectedOutlines("october_temp_c"));
  await page.waitForLoadState("networkidle");
  expect(seen.errors).toEqual([]);
  expect(seen.foreign).toEqual([]);
});

test("wet-season rainfall outlines match the index and the legend follows the indicator", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/mission/?story=1");
  await expect(map(page).locator("[data-cell]")).toHaveCount(index.cells.length);
  await expect(legend(page)).toContainText("wet-season rain");
  expect(await outlineCounts(page)).toEqual(expectedOutlines("wet_season_rain_mm"));
  const rainText = await legend(page).innerText();

  await page.locator("body").click({ position: { x: 1300, y: 1060 } });
  await page.keyboard.press("ArrowRight");
  await expect(legend(page)).toContainText("October");
  expect(await legend(page).innerText()).not.toEqual(rainText);
  expect(await outlineCounts(page)).toEqual(expectedOutlines("october_temp_c"));
  expect(seen.errors).toEqual([]);
  expect(seen.foreign).toEqual([]);
});

const placeInUrl = (page: Page) => new URL(page.url()).searchParams.get("place");

test("choosing a cell selects a place inside it and the SKY panel follows", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/mission/");
  await expect(map(page).locator("[data-cell]")).toHaveCount(index.cells.length);
  await expect(page).toHaveURL(/place=katete/);
  const katete = index.places.find((p) => p.id === "katete")!;

  const named = new Set(index.places.filter((p) => p.kind !== "cell").map((p) => p.cell));
  const targets = index.cells.filter((c) => c.id !== katete.cell && named.has(c.id)).slice(0, 2);
  expect(targets).toHaveLength(2);

  for (const [i, cell] of targets.entries()) {
    const target = map(page).locator(`[data-cell="${cell.id}"]`);
    if (i === 0) {
      await target.focus();
      await page.keyboard.press("Enter");
    } else {
      await target.dispatchEvent("click");
    }
    await expect.poll(() => placeInUrl(page)).not.toBe(i === 0 ? "katete" : null);
    await expect.poll(() => index.places.find((p) => p.id === placeInUrl(page))?.cell).toBe(cell.id);
    const place = index.places.find((p) => p.id === placeInUrl(page))!;
    await expect(map(page).locator("[data-selected-cell]")).toHaveAttribute("data-selected-cell", cell.id);
    await expect(map(page).locator("[data-selected-place]")).toHaveAttribute("data-selected-place", place.id);
    await expect(page.getByRole("region", { name: "SKY" })).toContainText(`${place.name}, NASA`);
  }
  expect(seen.errors).toEqual([]);
  expect(seen.foreign).toEqual([]);
});

test("clicking a town selects it", async ({ page }) => {
  await page.goto("/mission/");
  await expect(page).toHaveURL(/place=katete/);
  await map(page).locator('[data-place="chipata"]').dispatchEvent("click");
  await expect(page).toHaveURL(/place=chipata/);
  await expect(page.getByRole("region", { name: "SKY" })).toContainText("Chipata, NASA");
});

test("a cell with an error is drawn hatched", async ({ page }) => {
  const broken = index.cells[0].id;
  await page.route("**/trends/index.json", async (route) => {
    const response = await route.fetch();
    const body = (await response.json()) as TrendIndex;
    body.cells = body.cells.map((c) => (c.id === broken ? { ...c, error: "download failed (test)" } : c));
    await route.fulfill({ response, json: body });
  });
  await page.goto("/mission/");
  const cell = map(page).locator(`[data-cell="${broken}"]`);
  await expect(cell).toHaveAttribute("data-error", "true");
  await expect(cell.locator("[data-fill]")).toHaveAttribute("fill", /url\(#map-hatch\)/);
  await expect(map(page).locator(`[data-outline-for="${broken}"]`)).toHaveCount(0);
  await expect(map(page).locator("[data-error]")).toHaveCount(1);
});

test("zoom is clamped and reset returns to the full province", async ({ page }) => {
  await page.goto("/mission/");
  const zoomIn = page.getByRole("button", { name: "Zoom in" });
  const reset = page.getByRole("button", { name: "Reset zoom" });
  await expect(reset).toBeDisabled();
  for (let i = 0; i < 8; i++) if (await zoomIn.isEnabled()) await zoomIn.click();
  await expect(zoomIn).toBeDisabled();
  await reset.click();
  await expect(reset).toBeDisabled();
  await expect(page.getByRole("button", { name: "Zoom out" })).toBeDisabled();
});

const province = JSON.parse(readFileSync(join(__dirname, "../public/map/province.json"), "utf8")) as Parameters<typeof geoContains>[0];

type Rect = { x: number; y: number; width: number; height: number };
// half a pixel of slack for anti-aliased edges
const meets = (a: Rect, b: Rect, e = 0.5) => a.x + e < b.x + b.width && b.x + e < a.x + a.width && a.y + e < b.y + b.height && b.y + e < a.y + a.height;

// median colour of a small square of the rendered page, decoded in the page itself
async function sample(page: Page, x: number, y: number, r = 10): Promise<number[]> {
  const png = await page.screenshot({ clip: { x: x - r, y: y - r, width: 2 * r + 1, height: 2 * r + 1 } });
  return page.evaluate(async (b64) => {
    const img = new Image();
    img.src = `data:image/png;base64,${b64}`;
    await img.decode();
    const canvas = document.createElement("canvas");
    [canvas.width, canvas.height] = [img.width, img.height];
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(img, 0, 0);
    const d = ctx.getImageData(0, 0, img.width, img.height).data;
    return [0, 1, 2].map((c) => {
      const v: number[] = [];
      for (let i = c; i < d.length; i += 4) v.push(d[i]);
      return v.sort((a, b) => a - b)[v.length >> 1];
    });
  }, png.toString("base64"));
}

for (const theme of ["light", "dark"] as const) {
  test(`relief does not change how a class reads (${theme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: theme });
    let pairs = 0;
    for (const url of ["/mission/", "/mission/?story=1"]) {
      await page.goto(url);
      await expect(map(page).locator("[data-cell]")).toHaveCount(index.cells.length);
      await page.waitForLoadState("networkidle");
      // this checks the hillshade raster; the contour lines are a drawn layer like the roads, so they are hidden here
      await map(page).locator("[data-contours]").evaluateAll((els) => els.forEach((e) => ((e as SVGElement).style.display = "none")));
      await page.waitForTimeout(400);
      const busy: Rect[] = await map(page)
        .locator("[data-place], text, [data-pod-marker], [data-selected-cell]")
        .evaluateAll((els) => els.map((e) => e.getBoundingClientRect().toJSON()));
      const cells = await map(page)
        .locator("[data-cell][data-class]")
        .evaluateAll((els) =>
          els.map((e) => {
            const b = e.querySelector("[data-fill]")!.getBoundingClientRect();
            return { id: e.getAttribute("data-cell")!, cls: e.getAttribute("data-class")!, x: b.x + b.width / 2, y: b.y + b.height / 2 };
          }),
        );
      const clear = cells.filter((c) => !busy.some((b) => meets(b, { x: c.x - 10, y: c.y - 10, width: 21, height: 21 })));
      const centre = (id: string) => {
        const b = index.cells.find((c) => c.id === id)!.bounds;
        return [(b.west + b.east) / 2, (b.south + b.north) / 2] as [number, number];
      };
      const onRelief = (id: string) => geoContains(province, centre(id));
      for (const cls of new Set(clear.map((c) => c.cls))) {
        const over = clear.find((c) => c.cls === cls && onRelief(c.id));
        const off = clear.find((c) => c.cls === cls && !onRelief(c.id));
        if (!over || !off) continue;
        const [a, b] = [await sample(page, over.x, over.y), await sample(page, off.x, off.y)];
        const diff = Math.max(...a.map((v, i) => Math.abs(v - b[i])));
        expect(diff, `class ${cls}: ${over.id} ${a} vs ${off.id} ${b}`).toBeLessThanOrEqual(8);
        pairs++;
      }
    }
    expect(pairs).toBeGreaterThan(0);
  });
}

test("outlines are thin ink lines and the selected cell keeps full-ink brackets", async ({ page }) => {
  await page.goto("/mission/");
  await expect(map(page).locator("[data-cell]")).toHaveCount(index.cells.length);
  const outline = map(page).locator("[data-outline-for]").first();
  await expect(outline).toHaveCSS("stroke-width", "1.25px");
  await expect(outline).toHaveCSS("opacity", "0.55");
  await expect(map(page).locator("[data-selected-cell]")).toHaveCSS("opacity", "1");
});

test("the pod marker, the selected name and town labels stay clear of each other and of dots", async ({ page }) => {
  await page.goto("/mission/?sim=1");
  await expect(map(page).locator("[data-pod-marker]")).toBeVisible();
  const box = (sel: string) => map(page).locator(sel).evaluateAll((els) => els.map((e) => e.getBoundingClientRect().toJSON() as Rect));
  const [pod] = await box("[data-pod-marker] text, [data-pod-marker] rect");
  const [name] = await box("[data-selected-label]");
  const ring = (await box("[data-selected-place] circle"))[0];
  expect(meets(pod, name)).toBe(false);
  expect(meets(pod, ring)).toBe(false);
  expect(meets(name, ring)).toBe(false);
  const labels = await box("[data-town-label]");
  const dots = await box('[data-layer="facilities"] circle[r="2.5"], [data-layer="towns"] circle[r="3.5"]');
  for (const label of [...labels, name]) for (const dot of dots) expect(meets(label, dot), JSON.stringify({ label, dot })).toBe(false);
});

for (const [width, height] of [
  [1440, 900],
  [1280, 800],
]) {
  for (const theme of ["light", "dark"] as const) {
    test(`nothing in the map column overlaps or clips at ${width} x ${height} (${theme})`, async ({ page }) => {
      await page.setViewportSize({ width, height });
      await page.emulateMedia({ colorScheme: theme });
      await page.goto("/mission/?sim=1");
      await expect(map(page).locator("[data-cell]")).toHaveCount(index.cells.length);
      const column = await page.locator('section[aria-label="Map"]').evaluate((e) => e.getBoundingClientRect().toJSON() as Rect);
      const parts = await page.locator('section[aria-label="Map"]').evaluate((section) =>
        [...section.querySelectorAll("footer, footer *, [data-map-ready], [data-map-ready] button")].map((e) => ({
          tag: e.tagName,
          rect: e.getBoundingClientRect().toJSON(),
          clipped: e instanceof HTMLElement && (e.scrollWidth > e.clientWidth + 1 || e.scrollHeight > e.clientHeight + 1) && getComputedStyle(e).overflow !== "visible",
        })),
      );
      for (const p of parts) {
        if (!p.rect.width && !p.rect.height) continue;
        expect(p.rect.x >= column.x - 0.5 && p.rect.x + p.rect.width <= column.x + column.width + 0.5, `${p.tag} inside the column`).toBe(true);
        expect(p.rect.y >= column.y - 0.5 && p.rect.y + p.rect.height <= column.y + column.height + 0.5, `${p.tag} inside the column`).toBe(true);
        expect(p.clipped, `${p.tag} not clipped`).toBe(false);
      }
      const svg = await map(page).boundingBox();
      const footer = await page.locator('footer[aria-label="Map legend"]').boundingBox();
      expect(svg!.y + svg!.height).toBeLessThanOrEqual(footer!.y + 0.5);
      // the climate map shares the column with the terrain map below it
      expect(svg!.height).toBeGreaterThan(height * 0.3);
      const name = await map(page).locator("[data-selected-label]").boundingBox();
      expect(name!.x >= svg!.x && name!.x + name!.width <= svg!.x + svg!.width).toBe(true);
    });
  }
}
