import { createStore, useStore } from "zustand";
import { useMission } from "./state";

export type Step = "sky" | "ground" | "action";

// the one step on screen; in story mode the story picks it instead
export const viewStore = createStore<{ step: Step }>()(() => ({ step: "sky" }));

export const showStep = (step: Step) => viewStore.setState({ step });

export function useShownStep(): Step {
  const own = useStore(viewStore, (s) => s.step);
  const story = useMission((s) => s.story);
  const panel = useMission((s) => s.panel);
  if (!story) return own;
  return panel === "ground" || panel === "action" ? panel : "sky";
}
