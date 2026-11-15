import { resolve } from "node:path";
import { expect, test, type Page } from "@playwright/test";

const ground = (page: Page) => page.getByRole("region", { name: "GROUND" });

// the held-out An. arabiensis recording, fed to Chrome as its microphone
test.use({
  permissions: ["microphone"],
  launchOptions: {
    args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", `--use-file-for-fake-audio-capture=${resolve("public/clips/an-arabiensis.wav")}`],
  },
});

test("a mosquito recording at the microphone is heard live and opens the conversation", async ({ page }) => {
  await page.goto("/mission/");
  await page.getByRole("banner").getByRole("button", { name: "Verify" }).click();
  await ground(page).getByRole("button", { name: "Listen for mosquitoes" }).click();
  const heard = ground(page).locator("[data-heard]");
  await expect(heard).toHaveCount(1, { timeout: 30_000 });
  await expect(heard).toContainText(/heard \d\d:\d\d, [A-Z][a-z]+ \d+%/);
  await expect(ground(page).getByRole("group", { name: "Conversation" })).toContainText("I just heard a mosquito near the pod");
  await expect(ground(page).getByRole("status", { name: "pod K-01, not connected" })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("mic.png") });
});
