"use client";

import { RiArrowRightLine } from "@remixicon/react";
import { useEffect, useRef } from "react";
import { Button } from "@/components/base/buttons/button";
import { ScrollFade, useScrollFade } from "@/components/foundations/scroll-fade/scroll-fade";
import { missionStore, useMission } from "@/lib/mission/state";
import { showStep, useShownStep, type Step } from "@/lib/mission/view";
import { ActionPanel } from "./ActionPanel";
import { GroundPanel } from "./GroundPanel";
import { MissionMap } from "./MissionMap";
import { Note } from "./primitives";
import { SkyPanel } from "./SkyPanel";
import { StoryLine } from "./StoryLine";
import { TopBar } from "./TopBar";

function inTextField(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  return target.matches("input, textarea, select, [role='combobox']");
}

function useStoryKeys() {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const s = missionStore.getState();
      if (!s.story || event.defaultPrevented || event.altKey || event.metaKey || event.ctrlKey) return;
      if (inTextField(event.target)) return;
      if (event.key === "ArrowRight") s.nextStep();
      else if (event.key === "ArrowLeft") s.prevStep();
      else return;
      event.preventDefault();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}

// one step on screen at a time; the other two stay mounted so the pod link and the session keep running
function PanelColumn() {
  const fade = useScrollFade();
  const shown = useShownStep();
  const story = useMission((s) => s.story);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scroller.current) scroller.current.scrollTop = 0;
  }, [shown]);

  const step = (name: Step) => (shown === name ? "flex min-h-full flex-col" : "hidden");
  return (
    <div className="relative min-h-0 min-w-0">
      <div ref={scroller} onScroll={fade.onScroll} className="h-full overflow-y-auto">
        <div className="mx-auto h-full w-full max-w-3xl">
          <div className={step("sky")}>
            <SkyPanel />
            {story ? null : (
              <div className="flex justify-end px-6 pb-6">
                <Button variant="primary" size="small" trailingIcon={RiArrowRightLine} onClick={() => showStep("ground")}>
                  Check on the ground
                </Button>
              </div>
            )}
          </div>
          <div className={step("ground")}>
            <GroundPanel />
          </div>
          <div className={step("action")}>
            <ActionPanel />
          </div>
        </div>
      </div>
      <ScrollFade progress={fade.progress} surfaceClassName="from-background-full" />
    </div>
  );
}

export function MissionShell() {
  const story = useMission((s) => s.story);
  const indexError = useMission((s) => s.indexError);

  useEffect(() => {
    void missionStore.getState().init();
  }, []);
  useStoryKeys();

  return (
    <div className="flex h-dvh min-w-[1280px] flex-col overflow-hidden bg-background-full text-text-primary">
      <TopBar />
      {story ? <StoryLine /> : null}
      {indexError ? (
        <Note className="border-b border-separator-border px-6 py-2">
          The trend index could not be loaded ({indexError}). Rebuild the trends and reload the page.
        </Note>
      ) : null}
      <main className="grid min-h-0 flex-1 grid-cols-2 grid-rows-1">
        {/* one map of the province; its layer switches choose between the climate trend and the terrain */}
        <div className="min-h-0 min-w-0 border-e border-separator-border">
          <MissionMap />
        </div>
        <PanelColumn />
      </main>
    </div>
  );
}
