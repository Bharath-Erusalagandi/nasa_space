"use client";

import { RiPlayFill, RiStopFill } from "@remixicon/react";
import { useEffect, useState } from "react";
import { LinkButton } from "@/components/base/buttons/link-button";
import { useShownStep } from "@/lib/mission/view";
import { playClip, stopClip, useListener } from "@/lib/pod/listener";
import { SPECIES } from "@/lib/pod/species";
import results from "@/models/mosquito/results.json";
import { usePod } from "@/lib/pod/store";
import { cx } from "@/utils/cx";
import { FieldLabel, Note } from "./primitives";

const hhmm = (at: string) => new Date(at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });

const pct = (x: number) => `${Math.round(x * 100)}%`;

// the model's held-out test results, written by models/mosquito/train.py
function ModelScore() {
  const items = [
    { value: pct(results.detector.recall), words: "of mosquitoes found" },
    { value: pct(results.detector.false_alarm_rate), words: "false alarms" },
    { value: pct(results.malaria_vector.recall), words: "of malaria mosquitoes named" },
  ];
  return (
    <div role="group" aria-label="Model test results" className="flex flex-col gap-1">
      <div className="flex flex-wrap gap-x-8 gap-y-2">
        {items.map((i) => (
          <p key={i.words} className="flex items-baseline gap-1.5">
            <span className="text-title-2-medium text-text-primary tabular-nums">{i.value}</span>
            <span className="text-body-regular text-text-secondary">{i.words}</span>
          </p>
        ))}
      </div>
      <Note>
        On {results.detector.test_recordings} recordings the model never trained on (HumBugDB lab recordings). Not yet tested on a live mosquito.
      </Note>
    </div>
  );
}

// the eight species the model knows; the one heard last is outlined, and each card plays a held-out recording
export function SpeciesGrid() {
  const listened = useListener((s) => s.heard);
  const fromPod = usePod((s) => s.latest.mosquito);
  // a pod that names the species itself counts too
  const podHeard =
    fromPod?.label && fromPod.quality !== null
      ? { label: fromPod.label, confidence: fromPod.quality, via: "microphone" as const, at: fromPod.at, genus: undefined, genusConfidence: undefined }
      : null;
  // the listener also stores its own detections as pod readings a moment later, so only a clearly newer one counts
  const heard = podHeard && (!listened || Date.parse(podHeard.at) - Date.parse(listened.at) > 1000) ? podHeard : listened;
  const playing = useListener((s) => s.playing);
  const note = useListener((s) => s.note);
  const [credits, setCredits] = useState(false);
  const shown = useShownStep();

  // a clip never keeps playing once its step is off screen
  useEffect(() => {
    if (shown !== "ground") stopClip();
  }, [shown]);

  return (
    <section aria-label="Mosquitoes" className="flex min-w-0 flex-col gap-2">
      <ModelScore />
      <div className="flex items-baseline justify-between gap-4">
        <FieldLabel>Tap a mosquito to play a recording of its wingbeat</FieldLabel>
        <LinkButton size="small" aria-expanded={credits} onClick={() => setCredits(!credits)}>
          {credits ? "Hide sources" : "Sources"}
        </LinkButton>
      </div>
      <ul className="grid grid-cols-4 gap-2">
        {SPECIES.map((s) => {
          const isHeard = heard?.label === s.label;
          const isPlaying = playing === s.clip;
          const Icon = isPlaying ? RiStopFill : RiPlayFill;
          return (
            <li key={s.label}>
              <button
                type="button"
                aria-label={isPlaying ? `Stop the recording of ${s.name}` : `Play a recording of ${s.name}`}
                aria-pressed={isPlaying}
                data-heard={isHeard || undefined}
                onClick={() => void playClip(s.clip)}
                className={cx(
                  "group relative flex w-full flex-col overflow-hidden rounded-xl border bg-background-primary-default text-start outline-none transition-colors duration-150 ease-out focus-visible:ring-2 focus-visible:ring-border-focus-ring motion-reduce:transition-none",
                  isHeard ? "border-text-primary ring-1 ring-text-primary" : "border-border-button-default hover:border-border-button-hover",
                )}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`/species/${s.photo.file}`} alt={s.photo.shows} className="aspect-[3/2] w-full object-cover" loading="lazy" />
                <span className="absolute end-1.5 top-1.5 flex size-6 items-center justify-center rounded-full bg-background-primary-default/90 text-foreground-icon-primary">
                  <Icon className="size-3.5" aria-hidden />
                </span>
                <span className="flex min-w-0 flex-col px-2 py-1.5">
                  <span className="truncate text-caption-1-semibold text-text-primary">{s.label}</span>
                  {isHeard ? (
                    <span className="truncate text-caption-1-regular text-text-secondary tabular-nums">
                      {heard.via === "microphone" ? "heard" : "recording"} {hhmm(heard.at)}, {heard.genus ?? s.label}{" "}
                      {Math.round((heard.genusConfidence ?? heard.confidence) * 100)}%
                    </span>
                  ) : isPlaying ? (
                    <span className="truncate text-caption-1-regular text-text-tertiary">playing, tap to stop</span>
                  ) : null}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      {note ? <Note>{note}</Note> : null}
      {credits ? (
        <div className="flex flex-col gap-1">
          <Note>
            Recordings: HumBugDB test set (Kiskin et al. 2021, CC BY 4.0), never used in training; each is the longest test recording
            of its species the model gets right (none for Ma. africanus). On all test recordings it names the species 55% of the time
            and the genus 76% (docs/METHODS.md).
          </Note>
          {SPECIES.filter((s, i) => SPECIES.findIndex((t) => t.photo.file === s.photo.file) === i).map((s) => (
            <Note key={s.photo.file}>
              Photo of {s.photo.shows}: {s.photo.credit}.
            </Note>
          ))}
        </div>
      ) : null}
    </section>
  );
}
