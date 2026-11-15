"use client";

import { Fragment } from "react";
import { ThemeToggle } from "@/components/application/theme/theme-toggle";
import { Badge } from "@/components/base/badges/badge";
import { PRODUCT_NAME } from "@/lib/brand";
import { useMission } from "@/lib/mission/state";
import { stepLabel } from "@/lib/mission/story";
import { showStep, useShownStep, type Step } from "@/lib/mission/view";
import { usePod, type PodSource } from "@/lib/pod/store";
import { cx } from "@/utils/cx";
import { PlacePicker } from "./PlacePicker";

const LOOP = [
  { word: "Detect", step: "sky" },
  { word: "Verify", step: "ground" },
  { word: "Act", step: "action" },
] as const satisfies readonly { word: string; step: Step }[];

const SOURCE_BADGE: Partial<Record<PodSource, string>> = { replay: "REPLAY", simulation: "SIMULATION" };

// the three steps, one on screen at a time; the story drives them while it runs
function Loop() {
  const story = useMission((s) => s.story);
  const shown = useShownStep();
  const at = LOOP.findIndex((l) => l.step === shown);
  return (
    <nav className="flex items-center gap-3" aria-label="Detect, then verify, then act">
      {LOOP.map((l, i) => (
        <Fragment key={l.word}>
          {i > 0 ? <span aria-hidden className={cx("h-px w-8", i <= at ? "bg-text-secondary" : "bg-separator-border")} /> : null}
          <button
            type="button"
            disabled={story}
            aria-current={l.step === shown ? "step" : undefined}
            onClick={() => showStep(l.step)}
            className={cx(
              "group flex items-center gap-2 rounded-md px-1 py-1 text-body-medium outline-none transition-colors duration-150 ease-out focus-visible:ring-2 focus-visible:ring-border-focus-ring motion-reduce:transition-none",
              l.step === shown ? "text-text-primary" : "text-text-tertiary",
              !story && l.step !== shown && "hover:text-text-secondary",
            )}
          >
            {/* the number is drawn by CSS so the step's text stays its word */}
            <span
              aria-hidden
              data-n={i + 1}
              className={cx(
                "flex size-5 items-center justify-center rounded-full text-caption-2-semibold tabular-nums transition-colors duration-150 ease-out before:content-[attr(data-n)] motion-reduce:transition-none",
                l.step === shown ? "bg-text-primary text-background-primary-default" : "border border-border-button-default",
              )}
            />
            {l.word}
          </button>
        </Fragment>
      ))}
    </nav>
  );
}

export function TopBar() {
  const story = useMission((s) => s.story);
  const step = useMission((s) => s.step);
  const source = usePod((s) => s.source);
  const badge = SOURCE_BADGE[source];

  return (
    <header className="grid h-14 shrink-0 grid-cols-[1fr_auto_1fr] items-center gap-6 border-b border-separator-border px-6">
      <div className="flex min-w-0 items-center gap-6">
        <h1 className="shrink-0 text-headline-semibold text-text-primary">{PRODUCT_NAME}</h1>
        <PlacePicker />
      </div>
      <Loop />
      <div className="flex items-center justify-end gap-4">
        {badge ? (
          <Badge className="border border-border-button-default bg-transparent text-text-secondary">{badge}</Badge>
        ) : null}
        {story ? (
          <span className="text-body-medium text-text-secondary tabular-nums" aria-label={`Story step ${stepLabel(step)}`}>
            {stepLabel(step)}
          </span>
        ) : null}
        <ThemeToggle appearance="segmented" size="small" />
      </div>
    </header>
  );
}
