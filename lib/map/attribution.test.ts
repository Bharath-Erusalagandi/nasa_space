import { describe, expect, it } from "vitest";
import { attribution, climateCredit } from "./attribution";

const source = (name: string, group: string, text: string) => ({ name, licence: "", url: "", fetched: "2026-11-14", used_for: "", credit: { group, text } });

const climate = "NASA POWER daily point API (MERRA-2 reanalysis): PRECTOTCORR (rain, mm/day) and T2M";

describe("attribution", () => {
  it("builds one line of short credits grouped by what they are used for", () => {
    const text = attribution(
      [
        source("geoBoundaries ADM1", "Boundaries", "geoBoundaries"),
        source("geoBoundaries ADM2", "Boundaries", "geoBoundaries"),
        source("Natural Earth lines", "Boundaries", "Natural Earth"),
        source("Natural Earth countries", "Boundaries", "Natural Earth"),
        source("Maina", "Facilities", "Maina et al. 2019"),
        source("OSM", "Roads and rivers", "© OpenStreetMap contributors"),
        source("Copernicus", "Relief", "Copernicus DEM"),
      ],
      climate,
    );
    expect(text).toBe(
      "Trends: NASA POWER (MERRA-2). Boundaries: geoBoundaries, Natural Earth. Roads and rivers: © OpenStreetMap contributors. Facilities: Maina et al. 2019. Relief: Copernicus DEM.",
    );
  });

  it("falls back to the dataset name for a source without a credit", () => {
    const bare = { name: "Some layer (extra words)", licence: "", url: "", fetched: "", used_for: "" };
    expect(attribution([bare], climate)).toBe("Trends: NASA POWER (MERRA-2). Sources: Some layer.");
  });

  it("shortens the climate source", () => {
    expect(climateCredit(climate)).toBe("NASA POWER (MERRA-2)");
    expect(climateCredit("")).toBe("NASA POWER");
  });
});
