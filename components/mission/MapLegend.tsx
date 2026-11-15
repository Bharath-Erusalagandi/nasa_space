import { useId, useState } from "react";
import { LinkButton } from "@/components/base/buttons/link-button";
import type { Legend, Outline } from "@/lib/trends/cellLayer";
import { rampColors } from "@/lib/trends/colors";
import { cx } from "@/utils/cx";
import { FILL_OPACITY, HatchPattern, OUTLINE_CLASS, OUTLINE_DASH } from "./map/CellLayer";
import { Note } from "./primitives";

export type ElevationRamp = { m: number; colour: string }[];

type Props = {
  // the trend colours; null when the map is not coloured by the trend
  legend: Legend | null;
  // the elevation colours, when the map is coloured by height
  elevation?: ElevationRamp | null;
  title: string;
  scale: { km: number; px: number } | null;
  attribution: string;
};

function OutlineSample({ style, hatchId }: { style: Outline | "error"; hatchId: string }) {
  return (
    <svg width="24" height="14" aria-hidden className="mt-px shrink-0">
      <rect x="0" y="0" width="24" height="14" className="fill-background-primary-default" />
      {style === "error" ? (
        <rect x="0.75" y="0.75" width="22.5" height="12.5" fill={`url(#${hatchId})`} />
      ) : (
        <>
          <rect x="0.75" y="0.75" width="22.5" height="12.5" className="fill-data-none" />
          {style === "none" ? null : <rect x="1.5" y="1.5" width="21" height="11" strokeDasharray={OUTLINE_DASH[style]} className={OUTLINE_CLASS} />}
        </>
      )}
    </svg>
  );
}

function KeyLine({ className }: { className: string }) {
  return (
    <svg width="20" height="10" aria-hidden className="shrink-0">
      <line x1="1" y1="5" x2="19" y2="5" className={cx("[stroke-linecap:round]", className)} />
    </svg>
  );
}

function KeyDot({ r, className }: { r: number; className: string }) {
  return (
    <svg width="10" height="10" aria-hidden className="shrink-0">
      <circle cx="5" cy="5" r={r} className={className} />
    </svg>
  );
}

export function ScaleBar({ km, px }: { km: number; px: number }) {
  const w = Math.round(px);
  return (
    <div className="flex items-center gap-2" data-scale-km={km}>
      <svg width={w + 2} height="8" aria-hidden>
        <path d={`M1,1V7H${w + 1}V1`} className="fill-none stroke-text-secondary [stroke-width:1.5px]" />
      </svg>
      <span className="whitespace-nowrap text-caption-1-medium text-text-secondary tabular-nums">{km} km</span>
    </div>
  );
}

// layerLegend's outline sentences, shortened to fit the map column
const OUTLINE_WORDS: Record<Outline | "error", string> = {
  solid: "Solid outline: significant after correction (q < 0.05)",
  dashed: "Dashed outline: significant in this cell only (p < 0.05)",
  none: "No outline: not statistically significant",
  error: "Grey hatching: no NASA data for this cell",
};

const perDecade = (s: string) => s.replace(/ per decade$/, "");

const SYMBOLS = [
  { key: "town", words: "Town", mark: <KeyDot r={3.5} className="fill-text-primary" /> },
  { key: "facility", words: "Health facility", mark: <KeyDot r={2.5} className="fill-text-secondary" /> },
  { key: "main", words: "Main road", mark: <KeyLine className="stroke-foreground-icon-secondary [stroke-width:1.5px]" /> },
  { key: "minor", words: "Minor road or river", mark: <KeyLine className="stroke-foreground-icon-tertiary [stroke-width:1px]" /> },
  { key: "province", words: "Province boundary", mark: <KeyLine className="stroke-text-secondary [stroke-width:1.5px]" /> },
  { key: "contour", words: "Contour, every 100 m (500 m bolder)", mark: <KeyLine className="stroke-text-secondary opacity-60 [stroke-width:0.8px]" /> },
];

const metres = (m: number) => `${m.toLocaleString("en-GB")} m`;

function ElevationBar({ ramp }: { ramp: ElevationRamp }) {
  const low = ramp[0].m;
  const high = ramp[ramp.length - 1].m;
  const stops = ramp.map((r) => `${r.colour} ${(((r.m - low) / (high - low)) * 100).toFixed(1)}%`).join(", ");
  return (
    <div data-elevation-legend className="flex flex-col gap-1.5">
      <div className="h-2.5 rounded-full" style={{ background: `linear-gradient(to right, ${stops})` }} aria-hidden />
      <div className="flex justify-between gap-4 text-caption-1-regular text-text-secondary tabular-nums">
        <span>{metres(low)}</span>
        <span className="text-end">{metres(high)}</span>
      </div>
    </div>
  );
}

export function MapLegend({ legend, elevation, title, scale, attribution }: Props) {
  const hatchId = `legend-hatch-${useId().replace(/[^a-zA-Z0-9-]/g, "")}`;
  const keyId = useId();
  const [open, setOpen] = useState(false);
  const colors = legend ? rampColors(legend.ramp, legend.reversed) : [];

  return (
    <footer className="flex flex-col gap-2" aria-label="Map legend">
      <svg width="0" height="0" className="absolute" aria-hidden>
        <defs>
          <HatchPattern id={hatchId} />
        </defs>
      </svg>
      <div className="flex flex-col gap-1.5" data-legend>
        <div className="flex items-end justify-between gap-4">
          <p className="min-w-0 text-body-2-medium text-text-primary">{title}</p>
          {scale ? <ScaleBar {...scale} /> : null}
        </div>
        {legend ? (
          <>
            <div className="flex h-2.5 gap-px overflow-hidden rounded-full" aria-hidden>
              {colors.map((color) => (
                <span key={color} className="flex-1 bg-background-primary-default">
                  <span className="block size-full" style={{ backgroundColor: color, opacity: FILL_OPACITY }} />
                </span>
              ))}
            </div>
            <div className="flex justify-between gap-4 text-caption-1-regular text-text-secondary">
              <span>{perDecade(legend.low)}</span>
              <span className="text-end">{perDecade(legend.high)}</span>
            </div>
          </>
        ) : elevation ? (
          <ElevationBar ramp={elevation} />
        ) : null}
        <div className="flex items-center justify-between gap-4 pt-1">
          <Note>Roads and rivers © OpenStreetMap contributors</Note>
          <LinkButton size="small" aria-expanded={open} aria-controls={keyId} onClick={() => setOpen(!open)}>
            {open ? "Hide key and sources" : "Key and sources"}
          </LinkButton>
        </div>
        <div id={keyId} hidden={!open} className={cx(open && "grid", "grid-cols-[minmax(0,1fr)_auto] gap-x-6 text-caption-1-regular text-text-secondary")}>
          <ul className="flex flex-col gap-1">
            {(legend?.outlines ?? []).map((o) => (
              <li key={o.style} className="flex items-start gap-2">
                <OutlineSample style={o.style} hatchId={hatchId} />
                <span>{OUTLINE_WORDS[o.style]}</span>
              </li>
            ))}
          </ul>
          <ul className="flex flex-col gap-1">
            {SYMBOLS.map((s) => (
              <li key={s.key} className="flex items-center gap-1.5 whitespace-nowrap">
                {s.mark}
                {s.words}
              </li>
            ))}
          </ul>
        </div>
      </div>
      {open ? <Note>{attribution}</Note> : null}
    </footer>
  );
}
