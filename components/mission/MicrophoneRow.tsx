"use client";

import { useEffect, useState } from "react";
import { LinkButton } from "@/components/base/buttons/link-button";
import { ProgressTrack } from "@/components/base/progress/progress";
import { Select, SelectItem } from "@/components/base/select/select";
import { chooseMicrophone, saveHeard, useListener } from "@/lib/pod/listener";
import { recordingRequested } from "@/lib/pod/recorder";
import { Note } from "./primitives";

// Shown while listening: which microphone the browser gave, how loud it is and how mosquito-like the
// newest sound is. A computer's default microphone can be a headset that hears nothing, so it can be changed here.
export function MicrophoneRow() {
  const microphone = useListener((l) => l.microphone);
  const microphones = useListener((l) => l.microphones);
  const level = useListener((l) => l.level);
  const silent = useListener((l) => l.silent);
  const score = useListener((l) => l.score);
  // with ?record=1 the sound itself can be saved, to score a real test again later
  const [recording, setRecording] = useState(false);
  useEffect(() => setRecording(recordingRequested(window.location.search)), []);

  return (
    <div className="flex min-w-0 flex-col gap-2">
      <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2">
        {microphones.length ? (
          <Select
            aria-label="Microphone"
            size="sm"
            className="min-w-0"
            selectedKey={microphone}
            onSelectionChange={(id) => id !== null && id !== microphone && chooseMicrophone(String(id))}
          >
            {microphones.map((m) => (
              <SelectItem key={m.id} id={m.id}>
                {m.label}
              </SelectItem>
            ))}
          </Select>
        ) : null}
        <div
          role="meter"
          aria-label="Microphone level"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(level * 100)}
          className="w-28 shrink-0"
        >
          <ProgressTrack percentage={level * 100} size="sm" className="text-text-primary" />
        </div>
        {score !== null && !silent ? (
          <p className="text-caption-1-regular text-text-secondary tabular-nums">Sounds like a mosquito: {Math.round(score * 100)}%</p>
        ) : null}
        {recording ? (
          <LinkButton size="small" onClick={saveHeard}>
            Save the last 20 s
          </LinkButton>
        ) : null}
      </div>
      {silent ? (
        <Note className="text-text-error-primary">This microphone is sending no sound. Choose another one.</Note>
      ) : (
        <Note>A mosquito shows on its card below.</Note>
      )}
    </div>
  );
}
