import { useEffect } from "react";
import { createStore, useStore } from "zustand";
import { loadReplay } from "@/lib/trends/load";
import { createRecorder, downloadJSON, recordFrom, recordingRequested, type RecordedEvent } from "./recorder";
import { replay } from "./replay";
import { autoOpen, requestAndOpen } from "./serial";
import { simulationRequested, startSimulator } from "./simulator";
import { podStore, type PodStore } from "./store";

export const NO_REPLAY = "No replay recorded yet";

export type ControlsState = { replaying: boolean; simulating: boolean; recording: boolean };

function abortableSleep(signal: AbortSignal) {
  return (ms: number) =>
    new Promise<void>((resolve, reject) => {
      const id = setTimeout(resolve, ms);
      signal.addEventListener(
        "abort",
        () => {
          clearTimeout(id);
          reject(signal.reason);
        },
        { once: true },
      );
    });
}

type Options = {
  pod?: PodStore;
  load?: () => Promise<RecordedEvent[] | undefined>;
  simulate?: () => () => void;
  notify?: (message: string) => void;
};

export function createPodControls({ pod = podStore, load = loadReplay, simulate = () => startSimulator(), notify = () => {} }: Options = {}) {
  const state = createStore<ControlsState>()(() => ({ replaying: false, simulating: false, recording: false }));
  let abort: AbortController | null = null;
  let stopSim: (() => void) | null = null;
  let resumeSim = false;
  let recorder: ReturnType<typeof createRecorder> | null = null;

  function startSimulation() {
    if (stopSim) return;
    if (abort) stopReplay();
    pod.getState().claim("simulation");
    stopSim = simulate();
    state.setState({ simulating: true });
  }

  function stopSimulation() {
    stopSim?.();
    stopSim = null;
    pod.getState().release("simulation");
    state.setState({ simulating: false });
  }

  // a replay's readings leave the screen when it ends or stops; nothing earlier comes back
  function finishReplay(controller: AbortController) {
    if (abort !== controller) return;
    abort = null;
    pod.getState().release("replay");
    state.setState({ replaying: false });
    if (resumeSim) startSimulation();
    resumeSim = false;
  }

  async function startReplay() {
    if (abort) return;
    const controller = new AbortController();
    abort = controller;
    state.setState({ replaying: true });
    const events = await load().catch(() => undefined);
    if (controller.signal.aborted) return;
    if (!events?.length) {
      abort = null;
      state.setState({ replaying: false });
      notify(NO_REPLAY);
      return;
    }
    resumeSim = stopSim !== null;
    if (stopSim) stopSimulation();
    pod.getState().claim("replay");
    try {
      await replay(
        events,
        (event) => {
          if (!controller.signal.aborted) pod.getState().ingestEvent(event, "replay");
        },
        1,
        abortableSleep(controller.signal),
      );
    } catch {
      // stopped part way
    }
    finishReplay(controller);
  }

  function stopReplay() {
    if (!abort) return;
    const controller = abort;
    controller.abort();
    finishReplay(controller);
  }

  function startRecording() {
    if (recorder) return () => {};
    recorder = createRecorder();
    recorder.start();
    const stop = recordFrom(pod, recorder);
    state.setState({ recording: true });
    return () => {
      stop();
      recorder?.stop();
      recorder = null;
      state.setState({ recording: false });
    };
  }

  return {
    state,
    toggleReplay: () => (abort ? stopReplay() : void startReplay()),
    startReplay,
    stopReplay,
    startSimulation,
    stopSimulation,
    startRecording,
    download: () => recorder && downloadJSON(recorder.toJSON()),
  };
}

export type PodControls = ReturnType<typeof createPodControls>;

let shared: PodControls | undefined;
let notifier: (message: string) => void = () => {};

const controls = () => (shared ??= createPodControls({ notify: (message) => notifier(message) }));

function inTextField(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || target.matches("input, textarea, select, [role='combobox']");
}

// the GROUND panel mounts this once: serial reconnect, the R key, ?sim=1 and ?record=1
export function usePodControls(notify: (message: string) => void) {
  const c = controls();
  const status = useStore(c.state);

  useEffect(() => {
    notifier = notify;
  }, [notify]);

  useEffect(() => {
    const search = window.location.search;
    const stopSerial = autoOpen();
    const stopRecording = recordingRequested(search) ? c.startRecording() : () => {};
    if (simulationRequested(search)) c.startSimulation();

    function onKey(event: KeyboardEvent) {
      if (event.key !== "r" && event.key !== "R") return;
      if (event.defaultPrevented || event.repeat || event.altKey || event.metaKey || event.ctrlKey) return;
      if (inTextField(event.target)) return;
      event.preventDefault();
      c.toggleReplay();
    }
    window.addEventListener("keydown", onKey);

    return () => {
      window.removeEventListener("keydown", onKey);
      stopSerial();
      stopRecording();
      c.stopReplay();
      c.stopSimulation();
    };
  }, [c]);

  return { ...status, connect: requestAndOpen, download: c.download };
}
