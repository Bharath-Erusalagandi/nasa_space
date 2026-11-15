import { expect, test } from "@playwright/test";

test.use({ viewport: { width: 390, height: 844 } });

type Players = { __audio: HTMLAudioElement[] };

// which recordings are sounding now, found by comparing what each player holds with the files on the server
const playingClips = async () => {
  const bytes = async (url: string) => Array.from(new Uint8Array(await (await fetch(url)).arrayBuffer())).join();
  const files = await Promise.all(["an-arabiensis", "ae-aegypti"].map(async (name) => ({ name, bytes: await bytes(`/clips/${name}.wav`) })));
  const names: string[] = [];
  for (const audio of (window as unknown as Players).__audio.filter((a) => !a.paused)) {
    const held = await bytes(audio.src);
    names.push(files.find((f) => f.bytes === held)?.name ?? "unknown");
  }
  return names;
};

test("the phone page plays one looping recording per photo, and a second tap stops it", async ({ page }) => {
  await page.addInitScript(() => {
    const made: HTMLAudioElement[] = [];
    const Real = window.Audio;
    window.Audio = function (src?: string) {
      const audio = new Real(src);
      made.push(audio);
      return audio;
    } as unknown as typeof Audio;
    (window as unknown as Players).__audio = made;
  });
  await page.goto("/sounds/", { waitUntil: "networkidle" });
  await expect(page.getByRole("button")).toHaveCount(9);
  for (const photo of await page.getByRole("img").all()) await expect(photo).toHaveJSProperty("complete", true);

  await page.getByRole("button", { name: "Play Anopheles arabiensis" }).click();
  await expect(page.getByRole("button", { name: "Stop Anopheles arabiensis" })).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => page.evaluate(playingClips)).toEqual(["an-arabiensis"]);
  // played from memory and on a loop
  const first = await page.evaluate(() => {
    const audio = (window as unknown as Players).__audio[0];
    return { loop: audio.loop, src: audio.src.slice(0, 5) };
  });
  expect(first).toEqual({ loop: true, src: "blob:" });

  await page.getByRole("button", { name: "Play Aedes aegypti" }).click();
  await expect.poll(() => page.evaluate(playingClips)).toEqual(["ae-aegypti"]);
  await expect(page.getByRole("button", { name: "Play Anopheles arabiensis" })).toHaveAttribute("aria-pressed", "false");

  await page.getByRole("button", { name: "Stop Aedes aegypti" }).click();
  await expect.poll(() => page.evaluate(playingClips)).toEqual([]);
  await page.screenshot({ path: test.info().outputPath("sounds.png"), fullPage: true });
});

test("the laptop's species cards are pictures, not players", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 745 });
  await page.goto("/mission/");
  await page.getByRole("banner").getByRole("button", { name: "Verify" }).click();
  const cards = page.getByRole("region", { name: "Mosquitoes" });
  await expect(cards.getByRole("img")).toHaveCount(8);
  await expect(cards.getByRole("button", { name: /Play|Stop/ })).toHaveCount(0);
  await expect(cards.getByRole("link", { name: "Phone sounds" })).toHaveAttribute("href", "/sounds/");
});
