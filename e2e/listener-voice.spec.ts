import { expect, test, type Page } from "@playwright/test";
import { microphonePlaying } from "./tone";

const ground = (page: Page) => page.getByRole("region", { name: "GROUND" });

// a steady 150 Hz tone with six harmonics, where a spoken voice sits
test.use(microphonePlaying(150, [0.2, 0.18, 0.16, 0.12, 0.08, 0.06]));

test("a voice-range tone at the microphone is not reported as a mosquito", async ({ page }) => {
  await page.goto("/mission/");
  await page.getByRole("banner").getByRole("button", { name: "Verify" }).click();
  await ground(page).getByRole("button", { name: "Listen for mosquitoes" }).click();
  await expect(ground(page).getByText("Listening through the microphone. A mosquito shows on its card below.")).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(6000);
  await expect(ground(page).locator("[data-heard]")).toHaveCount(0);
  await expect(ground(page).getByTestId("question")).toHaveText("Has the patient had a fever in the last two days?");
});
