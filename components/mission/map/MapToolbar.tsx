"use client";

import { RiStackLine } from "@remixicon/react";
import { Button } from "@/components/base/buttons/button";
import { Popover, PopoverTrigger } from "@/components/base/popover/popover";
import { SegmentedControl, SegmentedControlItem } from "@/components/base/segmented-control/segmented-control";
import { Switch } from "@/components/base/switch/switch";
import { GROUNDS, OVERLAYS, reliefLock, shownCount, withGround, withOverlay, type Ground, type LayerState } from "@/lib/map/layers";

type Props = { layers: LayerState; onChange: (next: LayerState) => void };

// the map's controls in one row: what colours the ground, and a menu of the overlays, so the map itself stays clear
export function MapToolbar({ layers, onChange }: Props) {
  return (
    <div className="absolute start-3 top-3 flex items-center gap-2" data-map-toolbar>
      <div className="rounded-xl border border-border-button-default bg-background-primary-default shadow-md">
        <SegmentedControl
          aria-label="Colour the map by"
          selectedKeys={[layers.ground]}
          onSelectionChange={(keys) => {
            const [next] = [...keys] as Ground[];
            if (next) onChange(withGround(layers, next));
          }}
        >
          {GROUNDS.map((g) => (
            <SegmentedControlItem key={g.id} id={g.id} data-ground={g.id}>
              {g.label}
            </SegmentedControlItem>
          ))}
        </SegmentedControl>
      </div>
      <PopoverTrigger>
        <Button variant="secondary" size="small" leadingIcon={RiStackLine} className="shadow-md" data-layers-button>
          <span>Layers</span>
          <span className="ps-1 text-text-secondary tabular-nums">
            {shownCount(layers)}/{OVERLAYS.length}
          </span>
        </Button>
        <Popover placement="bottom start" aria-label="Map layers" className="w-64">
          <ul className="flex flex-col gap-2.5">
            {OVERLAYS.map((o) => {
              // some grounds carry their own relief, so the switch is locked there
              const lock = o.id === "relief" ? reliefLock(layers.ground) : null;
              return (
                <li key={o.id} className="flex flex-col">
                  <Switch size="sm" data-overlay={o.id} isSelected={lock ? lock.on : layers.overlays[o.id]} isDisabled={lock !== null} onChange={(on) => onChange(withOverlay(layers, o.id, on))}>
                    <span className="text-body-2-medium text-text-primary">{o.label}</span>
                  </Switch>
                  <span className="ps-9 text-caption-2-regular text-text-secondary">{lock ? lock.words : o.source}</span>
                </li>
              );
            })}
          </ul>
        </Popover>
      </PopoverTrigger>
    </div>
  );
}
