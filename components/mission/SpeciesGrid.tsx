"use client";

import { useState } from "react";
import { LinkButton } from "@/components/base/buttons/link-button";
import { useListener } from "@/lib/pod/listener";
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

// who made the recordings and the photos; the phone's sound page shows the same lines
export function SpeciesSources() {
  return (
    <div className="flex flex-col gap-1">
      <Note>
        Recordings: HumBugDB test set (Kiskin et al. 2021, CC BY 4.0), never used in training; each is the test recording of its
        species the model gets right most often, as recorded and through a simulated speaker. On
        all test recordings it names the species {pct(results.species.recording_balanced_accuracy)} of the time, and{" "}
        {pct(results.species.through_the_air.recording_balanced_accuracy)} through a simulated speaker and room (docs/METHODS.md).
      </Note>
      {SPECIES.filter((s, i) => SPECIES.findIndex((t) => t.photo.file === s.photo.file) === i).map((s) => (
        <Note key={s.photo.file}>
          Photo of {s.photo.shows}: {s.photo.credit}.
        </Note>
      ))}
    </div>
  );
}

// The eight species the model knows; the one heard last is outlined. The cards make no sound:
// the recordings play from a phone (/sounds/) and reach the model through the microphone.
export function SpeciesGrid() {
  const listened = useListener((s) => s.heard);
  const fromPod = usePod((s) => s.latest.mosquito);
  // a pod that names the species itself counts too
  const podHeard =
    fromPod?.label && fromPod.quality !== null
      ? { label: fromPod.label, confidence: fromPod.quality, at: fromPod.at, genus: undefined, genusConfidence: undefined }
      : null;
  // the listener also stores its own detections as pod readings a moment later, so only a clearly newer one counts
  const heard = podHeard && (!listened || Date.parse(podHeard.at) - Date.parse(listened.at) > 1000) ? podHeard : listened;
  const [credits, setCredits] = useState(false);

  return (
    <section aria-label="Mosquitoes" className="flex min-w-0 flex-col gap-2">
      <ModelScore />
      <div className="flex items-baseline justify-between gap-4">
        <FieldLabel>Play a mosquito sound from a phone near the microphone</FieldLabel>
        <span className="flex items-baseline gap-4">
          <LinkButton size="small" href="/sounds/" target="_blank">
            Phone sounds
          </LinkButton>
          <LinkButton size="small" aria-expanded={credits} onClick={() => setCredits(!credits)}>
            {credits ? "Hide sources" : "Sources"}
          </LinkButton>
        </span>
      </div>
      <ul className="grid grid-cols-4 gap-2">
        {SPECIES.map((s) => {
          const isHeard = heard?.label === s.label;
          return (
            <li
              key={s.label}
              data-heard={isHeard || undefined}
              className={cx(
                "flex flex-col overflow-hidden rounded-xl border bg-background-primary-default transition-colors duration-150 ease-out motion-reduce:transition-none",
                isHeard ? "border-text-primary ring-1 ring-text-primary" : "border-border-button-default",
              )}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/species/${s.photo.file}`} alt={s.photo.shows} className="aspect-[3/2] w-full object-cover" loading="lazy" />
              <span className="flex min-w-0 flex-col px-2 py-1.5">
                <span className="truncate text-caption-1-semibold text-text-primary">{s.label}</span>
                {isHeard ? (
                  <span className="truncate text-caption-1-regular text-text-secondary tabular-nums">
                    heard {hhmm(heard.at)}, {heard.genus ?? s.label} {Math.round((heard.genusConfidence ?? heard.confidence) * 100)}%
                  </span>
                ) : null}
              </span>
            </li>
          );
        })}
      </ul>
      {credits ? <SpeciesSources /> : null}
    </section>
  );
}
