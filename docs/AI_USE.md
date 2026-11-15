# Use of AI

| Tool | What it did | Files |
|---|---|---|
| Claude (Anthropic), through Claude Code, with subagents | Wrote the code, tests, firmware, CAD scripts and documentation under the team's direction on 14 November 2026. The team chose the product, reviewed the work and ran the demo. | Everything under `app/`, `components/mission/`, `lib/`, `e2e/`, `trend/`, `validation/` (the `.py` files), `mapdata/`, `scripts/`, `firmware/`, `hardware/cad/`, `docs/` and `README.md`. The BoardUI components in `components/base/` and `components/application/` come from the BoardUI CLI. |
| Claude (Anthropic), through Claude Code, on 15 November 2026 | Drafted the slide decks (including the architecture slides) from this repository's numbers, recorded the app walkthrough with Playwright, and cleaned up dead code. The screenshots and video are screen captures of the real app, not generated images. | Slides (Claude artifacts), `docs/media/` |
| Blender 4.4 (`bpy`), run by `hardware/cad/render.py` and `hardware/render/render_k01.py` | Rendered the enclosure previews from the CAD meshes. These are renders of the CAD model, not AI images. | `hardware/out/renders/` |

The app makes no AI model calls when it runs. Every number on screen comes from JSON files under `public/` written by scripts in this repository.

No AI tool wrote the data. The NASA POWER, ERA5, map and facility files are downloaded by the scripts named in `docs/METHODS.md` and `mapdata/README.md`. The validation CSV files in `validation/` are for people to fill in with real readings.

TODO (team): add a row for any other tool you use for the final slides (for example PowerPoint or Canva), the video or the voice-over, with what it did. If any image or video is AI-generated, give it a visible watermark and say so here.
