import { RiAddLine, RiFullscreenExitLine, RiSubtractLine } from "@remixicon/react";
import { IconButton } from "@/components/base/buttons/icon-button";
import { MAX_ZOOM, MIN_ZOOM } from "@/lib/map/projection";

type Props = { k: number; onZoom: (factor: number) => void; onReset: () => void };

export function ZoomControls({ k, onZoom, onReset }: Props) {
  return (
    <div className="absolute end-4 top-4 flex flex-col gap-2">
      <IconButton size="small" icon={RiAddLine} aria-label="Zoom in" disabled={k >= MAX_ZOOM} onClick={() => onZoom(1.5)} />
      <IconButton size="small" icon={RiSubtractLine} aria-label="Zoom out" disabled={k <= MIN_ZOOM} onClick={() => onZoom(1 / 1.5)} />
      <IconButton size="small" icon={RiFullscreenExitLine} aria-label="Reset zoom" disabled={k <= MIN_ZOOM} onClick={onReset} />
    </div>
  );
}
