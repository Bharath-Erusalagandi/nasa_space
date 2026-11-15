import { RiAddLine, RiFocus3Line, RiFullscreenExitLine, RiSubtractLine } from "@remixicon/react";
import type { ComponentType } from "react";
import { MAX_ZOOM, MIN_ZOOM } from "@/lib/map/projection";

type Props = { k: number; onZoom: (factor: number) => void; onReset: () => void; onLocate?: () => void; locateLabel?: string };

type Icon = ComponentType<{ className?: string; "aria-hidden"?: boolean | "true" | "false" }>;

function Key({ icon: Glyph, label, disabled, onClick }: { icon: Icon; label: string; disabled?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="flex size-8 items-center justify-center text-text-primary outline-none transition-colors duration-150 ease-out hover:bg-background-secondary-hover focus-visible:ring-2 focus-visible:ring-border-focus-ring focus-visible:ring-inset disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:bg-transparent motion-reduce:transition-none"
    >
      <Glyph className="size-4" aria-hidden />
    </button>
  );
}

// one joined control, like a map's own zoom buttons
export function ZoomControls({ k, onZoom, onReset, onLocate, locateLabel }: Props) {
  return (
    <div className="absolute end-3 top-3 flex flex-col divide-y divide-separator-border overflow-hidden rounded-xl border border-border-button-default bg-background-primary-default shadow-md" data-zoom-controls>
      <Key icon={RiAddLine} label="Zoom in" disabled={k >= MAX_ZOOM} onClick={() => onZoom(1.5)} />
      <Key icon={RiSubtractLine} label="Zoom out" disabled={k <= MIN_ZOOM} onClick={() => onZoom(1 / 1.5)} />
      <Key icon={RiFullscreenExitLine} label="Reset zoom" disabled={k <= MIN_ZOOM} onClick={onReset} />
      {onLocate ? <Key icon={RiFocus3Line} label={locateLabel ?? "Zoom to the selected place"} onClick={onLocate} /> : null}
    </div>
  );
}
