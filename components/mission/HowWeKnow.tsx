"use client";

import type { ReactNode } from "react";
import { LinkButton } from "@/components/base/buttons/link-button";
import { Drawer, DrawerBody, DrawerHeader, DrawerTrigger } from "@/components/base/drawer/drawer";
import {
  agreement,
  AUTOCORRELATION_NOTE,
  NOT_ENOUGH_SEASONS,
  pValue,
  qValue,
  rateText,
  rateUnit,
  recordLimit,
  signed,
} from "@/lib/trends/format";
import { cellSizeLabel } from "@/lib/trends/geo";
import { displayUnit, type CellFile, type IndicatorKey, type Trend, type WindowChoice } from "@/lib/trends/types";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-1">
      <h3 className="text-body-medium text-text-primary">{title}</h3>
      {children}
    </section>
  );
}

const text = "text-body-regular text-text-secondary";

type Props = {
  cell: CellFile;
  indicatorKey: IndicatorKey;
  placeName: string;
  trend: Trend | null | undefined;
  window: WindowChoice;
  q: number | null | undefined;
  cellCount: number;
  generated: string | undefined;
};

export function HowWeKnow({ cell, indicatorKey, placeName, trend, window, q, cellCount, generated }: Props) {
  const indicator = cell.indicators[indicatorKey];
  const series = indicator.series;
  const first = series[0];
  const last = series.at(-1);
  const level = trend ? Math.round((1 - trend.alpha) * 100) : null;
  const used = window === "all" ? `all ${series.length} seasons` : `the last ${window} seasons`;
  const second = indicator.second_source;
  const agree = second ? agreement(indicator.trend, second.trend) : null;
  const record = recordLimit(indicator);
  const onset = cell.indicators.rain_onset_day;
  const source = displayUnit(cell.source);

  return (
    <DrawerTrigger>
      <LinkButton size="small">How we know</LinkButton>
      <Drawer placement="end" size="lg">
        <DrawerHeader title="How we know" description={`${indicator.label} for the NASA cell around ${placeName}`} />
        <DrawerBody className="flex flex-col gap-5 pb-6">
          <Section title="Source and dates">
            <p className={text}>
              {source}. Seasons {cell.period}
              {generated ? `, trends built on ${generated}` : ""}.
            </p>
          </Section>

          <Section title="Seasons">
            <p className={text}>
              {first && last
                ? `Each season is labelled by the two years it spans, from ${first.label} to ${last.label}, one value per season. `
                : null}
              {indicator.label}: {indicator.definition}
            </p>
          </Section>

          <Section title="Method">
            <p className={text}>
              Sen&apos;s slope is the median of the slopes between every pair of seasons, so one unusual season cannot pull it
              far{level !== null ? `; the range in brackets is its ${level}% range` : ""}. The Mann-Kendall test asks whether later
              seasons are higher, or lower, than earlier ones more often than chance would give
              {trend ? `, and a two-sided p below ${trend.alpha} counts as significant` : ""}.
            </p>
          </Section>

          <Section title={`This verdict, ${used}`}>
            {trend ? (
              <ul className="flex flex-col gap-1">
                <li className={text}>
                  Sen&apos;s slope: {rateText(trend, indicator.unit)}, Mann-Kendall {pValue(trend.mk_p, trend.alpha)}.
                </li>
                <li className={text}>
                  For comparison, the least-squares slope: {signed(trend.ols_slope_per_decade)} {rateUnit(indicator.unit)}, t-test{" "}
                  {pValue(trend.ols_p, trend.alpha)}.
                </li>
                <li className={text}>
                  {q !== null && q !== undefined
                    ? `${qValue(q, trend.alpha)} for the all-season trend after a false-discovery correction (Benjamini-Hochberg) across ${cellCount} cells.`
                    : "No q-value for this cell."}
                  {window !== "all" ? " The correction is run on the all-season trends only." : ""}
                </li>
                {trend.lag1_autocorrelation !== null ? (
                  <li className={text}>
                    Lag-1 autocorrelation {signed(trend.lag1_autocorrelation)}.
                    {trend.autocorrelation_warning ? ` ${AUTOCORRELATION_NOTE}` : ""}
                  </li>
                ) : null}
              </ul>
            ) : (
              <p className={text}>{NOT_ENOUGH_SEASONS}.</p>
            )}
          </Section>

          {second ? (
            <Section title="Second source">
              <p className={text}>
                {second.trend
                  ? `${second.name}, all seasons: ${rateText(second.trend, indicator.unit)}, Mann-Kendall ${pValue(second.trend.mk_p, second.trend.alpha)}.`
                  : `${second.name}: not enough seasons to compare.`}
                {agree ? ` ${agree}` : ""}
              </p>
            </Section>
          ) : null}

          <Section title="Limits">
            <ul className="flex list-disc flex-col gap-1 ps-5">
              <li className={text}>
                One dataset: {source}. Reanalysis trends can be affected by changes in the observations fed into it
                {second ? `; ${second.name} is the cross-check above` : ""}.
              </li>
              {record ? <li className={text}>{record}</li> : null}
              <li className={text}>
                Cell values are averages over {cellSizeLabel(cell.cell.bounds)}, not village measurements. That gap is the reason
                the pod exists.
              </li>
              {onset ? (
                <li className={text}>
                  The start of the rains is a rule chosen for this tool, not an official date. {onset.label}: {onset.definition}
                </li>
              ) : null}
            </ul>
          </Section>
        </DrawerBody>
      </Drawer>
    </DrawerTrigger>
  );
}
