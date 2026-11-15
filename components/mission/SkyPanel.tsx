"use client";

import { useId, useRef } from "react";
import { SegmentedControl, SegmentedControlItem } from "@/components/base/segmented-control/segmented-control";
import { Select, SelectItem } from "@/components/base/select/select";
import {
  getCellFile,
  getCellSummary,
  getPlace,
  getTrend,
  missionStore,
  usePanelEmphasis,
  useMission,
} from "@/lib/mission/state";
import { descriptor } from "@/lib/trends/format";
import { INDICATOR_KEYS, type CellFile, type IndicatorKey, type WindowChoice } from "@/lib/trends/types";
import { HowWeKnow } from "./HowWeKnow";
import { EmptyState, FieldLabel, PanelFrame } from "./primitives";
import { ChartKey, TrendChart } from "./TrendChart";
import { Verdict } from "./Verdict";

const isIndicator = (key: unknown): key is IndicatorKey => INDICATOR_KEYS.includes(key as IndicatorKey);

function windowChoices(cell: CellFile | null, key: IndicatorKey): WindowChoice[] {
  const windows = cell?.indicators[key]?.windows;
  const sizes = windows ? Object.keys(windows).sort((a, b) => Number(a) - Number(b)) : [];
  return [...(sizes as WindowChoice[]), "all"];
}

function Controls({ cell }: { cell: CellFile | null }) {
  const indicatorKey = useMission((s) => s.indicator);
  const window = useMission((s) => s.window);
  const labelId = useId();
  const options = INDICATOR_KEYS.flatMap((key) => {
    const indicator = cell?.indicators[key];
    return indicator ? [{ key, label: indicator.label, definition: indicator.definition }] : [];
  });

  return (
    <>
      <Select
        aria-label="Indicator"
        size="sm"
        isDisabled={!options.length}
        selectedKey={indicatorKey}
        onSelectionChange={(key) => isIndicator(key) && missionStore.getState().setIndicator(key)}
        popoverClassName="max-w-[360px]"
        renderValue={({ selectedText }) => selectedText}
      >
        {options.map(({ key, label, definition }) => (
          <SelectItem key={key} id={key} textValue={label}>
            <span className="flex min-w-0 flex-col">
              <span className="text-body-2-medium text-text-primary">{label}</span>
              <span className="text-caption-1-regular text-text-tertiary">{definition}</span>
            </span>
          </SelectItem>
        ))}
      </Select>
      <div className="flex items-center gap-2">
        <FieldLabel>
          <span id={labelId}>Seasons</span>
        </FieldLabel>
        <SegmentedControl
          aria-labelledby={labelId}
          selectedKeys={[window]}
          onSelectionChange={(keys) => {
            const [next] = [...keys] as WindowChoice[];
            if (next) missionStore.getState().setWindow(next);
          }}
        >
          {windowChoices(cell, indicatorKey).map((w) => (
            <SegmentedControlItem key={w} id={w} className="tabular-nums">
              {w === "all" ? "All" : w}
            </SegmentedControlItem>
          ))}
        </SegmentedControl>
      </div>
    </>
  );
}

export function SkyPanel() {
  const emphasis = usePanelEmphasis("sky");
  const place = useMission(getPlace);
  const summary = useMission(getCellSummary);
  const cell = useMission(getCellFile);
  const cellError = useMission((s) => s.cellError);
  const indicatorKey = useMission((s) => s.indicator);
  const window = useMission((s) => s.window);
  const trend = useMission(getTrend);
  const index = useMission((s) => s.index);

  // while the next cell loads the previous one stays on screen, named after its own place
  const shownPlace = useRef(place);
  if (place && cell && place.cell === cell.cell.id) shownPlace.current = place;
  const placeName = shownPlace.current?.name ?? place?.name ?? "";

  const indicator = cell?.indicators[indicatorKey];
  const q = index?.cells.find((c) => c.id === cell?.cell.id)?.indicators?.[indicatorKey]?.q;
  const cellCount = index?.cells.filter((c) => !c.error).length ?? 0;
  const level = trend ? Math.round((1 - trend.alpha) * 100) : null;
  const failed = summary?.error;

  let body;
  if (failed) {
    body = <EmptyState>NASA data for this cell could not be downloaded when the trends were built.</EmptyState>;
  } else if (!cell || !indicator) {
    body = cellError ? (
      <EmptyState>The trend file for this cell could not be loaded.</EmptyState>
    ) : (
      <EmptyState>{place ? `Loading the trend for ${place.name}` : "Loading the trend"}</EmptyState>
    );
  } else {
    body = (
      <div className="flex min-h-0 flex-1 flex-col gap-4">
        <Verdict indicator={indicator} trend={trend} window={window} q={q} />
        <div className="flex min-h-64 min-w-0 flex-1 flex-col gap-3">
          <TrendChart layerKey={`${cell.cell.id}-${indicatorKey}`} indicator={indicator} trend={trend} window={window} />
          <div className="flex items-end justify-between gap-4">
            <ChartKey window={window} level={level} />
            <div className="shrink-0">
              <HowWeKnow
                cell={cell}
                indicatorKey={indicatorKey}
                placeName={placeName}
                trend={trend}
                window={window}
                q={q}
                cellCount={cellCount}
                generated={index?.generated}
              />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <PanelFrame
      className="min-h-auto flex-1"
      title="SKY"
      label="SKY"
      emphasis={emphasis}
      descriptor={!failed && cell && indicator ? `${placeName}, ${descriptor(cell, indicatorKey)}` : undefined}
      right={failed ? undefined : <Controls cell={cell} />}
    >
      {body}
    </PanelFrame>
  );
}
