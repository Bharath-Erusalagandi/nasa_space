"use client";

import { RiPlayFill, RiStopFill } from "@remixicon/react";
import { useEffect, useRef, useState } from "react";
import { LinkButton } from "@/components/base/buttons/link-button";
import { SpeciesSources } from "@/components/mission/SpeciesGrid";
import { Note } from "@/components/mission/primitives";
import { SPECIES } from "@/lib/pod/species";
import { cx } from "@/utils/cx";

// The phone's half of the demo. Each photo plays that species' held-out recording on a loop;
// the Mission page on the laptop hears it through its microphone and names the mosquito.
export function SoundBoard() {
  const audio = useRef<HTMLAudioElement | null>(null);
  const loaded = useRef<Record<string, string>>({});
  const [playing, setPlaying] = useState<string | null>(null);
  const [credits, setCredits] = useState(false);

  // Every clip is fetched up front and played from memory: a phone browser refuses to play
  // a sound file from a plain static server that cannot send it in byte ranges.
  useEffect(() => {
    const urls = loaded.current;
    let gone = false;
    for (const s of SPECIES) {
      fetch(s.clip)
        .then((r) => (r.ok ? r.blob() : Promise.reject(new Error(r.statusText))))
        .then((blob) => {
          if (!gone) urls[s.clip] = URL.createObjectURL(blob);
        })
        .catch(() => {});
    }
    return () => {
      gone = true;
      audio.current?.pause();
      for (const url of Object.values(urls)) URL.revokeObjectURL(url);
    };
  }, []);

  function toggle(clip: string) {
    audio.current?.pause();
    audio.current = null;
    if (playing === clip) return setPlaying(null);
    const next = new Audio(loaded.current[clip] ?? clip);
    next.loop = true;
    audio.current = next;
    setPlaying(clip);
    // a refused play leaves the card idle; a play cut short by the next tap is not a failure
    next.play().catch(() => {
      if (audio.current === next) setPlaying(null);
    });
  }

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-4 px-4 py-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-title-3-semibold text-text-primary">Mosquito sounds</h1>
        <p className="text-body-regular text-text-secondary">Tap one, volume up, and hold the phone by the laptop microphone.</p>
      </header>
      <ul className="grid grid-cols-2 gap-3">
        {SPECIES.map((s) => {
          const isPlaying = playing === s.clip;
          const Icon = isPlaying ? RiStopFill : RiPlayFill;
          return (
            <li key={s.label}>
              <button
                type="button"
                aria-label={isPlaying ? `Stop ${s.name}` : `Play ${s.name}`}
                aria-pressed={isPlaying}
                onClick={() => toggle(s.clip)}
                className={cx(
                  "relative flex w-full flex-col overflow-hidden rounded-xl border bg-background-primary-default text-start outline-none transition-colors duration-150 ease-out focus-visible:ring-2 focus-visible:ring-border-focus-ring motion-reduce:transition-none",
                  isPlaying ? "border-text-primary ring-1 ring-text-primary" : "border-border-button-default",
                )}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`/species/${s.photo.file}`} alt={s.photo.shows} className="aspect-[3/2] w-full object-cover" />
                <span className="absolute end-2 top-2 flex size-8 items-center justify-center rounded-full bg-background-primary-default/90 text-foreground-icon-primary">
                  <Icon className="size-4" aria-hidden />
                </span>
                <span className="flex min-w-0 flex-col px-3 py-2">
                  <span className="truncate text-body-medium text-text-primary">{s.label}</span>
                  <span className="text-caption-1-regular text-text-secondary">{isPlaying ? "Playing, tap to stop" : s.role}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      <div className="flex flex-col gap-2">
        <Note>Six-second recordings on a loop. The laptop needs about four seconds to name one.</Note>
        <LinkButton size="small" className="self-start" aria-expanded={credits} onClick={() => setCredits(!credits)}>
          {credits ? "Hide sources" : "Sources"}
        </LinkButton>
        {credits ? <SpeciesSources /> : null}
      </div>
    </main>
  );
}
