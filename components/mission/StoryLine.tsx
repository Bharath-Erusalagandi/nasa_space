"use client";

import { Kbd } from "@/components/base/kbd/kbd";
import { getPlace, useMission } from "@/lib/mission/state";
import { STORY } from "@/lib/mission/story";

function Hint({ keys, children }: { keys: string[]; children: string }) {
  return (
    <span className="flex items-center gap-1 text-caption-1-regular text-text-tertiary">
      {keys.map((k) => (
        <Kbd key={k} className="min-w-5">
          {k}
        </Kbd>
      ))}
      {children}
    </span>
  );
}

export function StoryLine() {
  const step = useMission((s) => s.step);
  const place = useMission(getPlace);
  const cell = useMission((s) => s.cell);
  const index = useMission((s) => s.index);
  const s = STORY[step];
  const sentence = place ? s.sentence({ placeName: place.name, cell: cell ?? undefined, index: index ?? undefined }) : null;

  return (
    <div className="flex shrink-0 items-center gap-6 border-b border-separator-border px-6 py-3">
      <p key={step} className="min-w-0 flex-1 text-title-3-regular text-text-secondary motion-safe:animate-label-in" aria-live="polite">
        <span className="text-title-3-semibold text-text-primary">{s.question}</span> {sentence}
      </p>
      <div className="flex shrink-0 items-center gap-4">
        <Hint keys={["←", "→"]}>step</Hint>
        <Hint keys={["R"]}>replay</Hint>
      </div>
    </div>
  );
}
