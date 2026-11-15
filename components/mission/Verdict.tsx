import { AUTOCORRELATION_NOTE, NOT_ENOUGH_SEASONS, qValue, rate, significance } from "@/lib/trends/format";
import type { Indicator, Trend, WindowChoice } from "@/lib/trends/types";
import { FieldValue, Figure, Note } from "./primitives";
import { cx } from "@/utils/cx";

const secondary = "text-body-regular text-text-secondary";

type Props = {
  indicator: Indicator;
  trend: Trend | null | undefined;
  window: WindowChoice;
  q: number | null | undefined;
};

// the answer only: how much, and whether it is significant; what and where are in How we know
export function Verdict({ indicator, trend, window, q }: Props) {
  const r = trend ? rate(trend, indicator.unit) : null;
  return (
    <div role="group" aria-label="Verdict" className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-2">
        {r ? (
          <p className="flex flex-wrap items-baseline gap-x-2" data-testid="how-much">
            <Figure hero value={r.figure} unit={r.unit} />
            <span className={cx(secondary, "tabular-nums")}>{r.range}</span>
          </p>
        ) : (
          <FieldValue as="p">{NOT_ENOUGH_SEASONS}</FieldValue>
        )}
        {trend ? (
          <p className="flex flex-col items-end text-end" data-testid="significant">
            <span className="text-body-medium text-text-primary tabular-nums">{significance(trend)}</span>
            {window === "all" && q !== null && q !== undefined ? (
              <span className="text-caption-1-regular text-text-tertiary tabular-nums">{`${qValue(q, trend.alpha)} across all cells`}</span>
            ) : null}
          </p>
        ) : (
          <FieldValue as="p">Not tested</FieldValue>
        )}
      </div>
      {trend?.autocorrelation_warning ? <Note>{AUTOCORRELATION_NOTE}</Note> : null}
    </div>
  );
}
