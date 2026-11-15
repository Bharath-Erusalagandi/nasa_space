// shared parts for every mission panel: PanelFrame, ColumnTitle, FieldLabel, FieldValue, Figure, Note, EmptyState, Columns
import type { ReactNode } from "react";
import { cx } from "@/utils/cx";

export type Emphasis = "active" | "quiet" | undefined;

type PanelFrameProps = {
  title?: ReactNode;
  descriptor?: ReactNode;
  right?: ReactNode;
  emphasis?: Emphasis;
  label?: string;
  className?: string;
  children?: ReactNode;
};

export function PanelFrame({ title, descriptor, right, emphasis, label, className, children }: PanelFrameProps) {
  return (
    <section
      aria-label={label}
      data-emphasis={emphasis}
      className={cx(
        "relative flex min-h-0 min-w-0 flex-col gap-3 px-6 py-4",
        "before:absolute before:inset-y-0 before:start-0 before:w-0.5 before:bg-text-primary before:opacity-0 before:transition-opacity before:duration-150 before:ease-out motion-reduce:before:transition-none",
        emphasis === "active" && "before:opacity-100",
        className,
      )}
    >
      {title || right ? (
        <header className="flex min-h-8 items-center gap-4">
          <div className="flex min-w-0 flex-1 items-baseline gap-3">
            {title ? (
              <h2 className={cx("shrink-0 text-caption-1-semibold tracking-wide", emphasis === "active" ? "text-text-primary" : "text-text-tertiary")}>
                {title}
              </h2>
            ) : null}
            {descriptor ? <p className="min-w-0 truncate text-caption-1-regular text-text-tertiary">{descriptor}</p> : null}
          </div>
          {right ? <div className="flex shrink-0 items-center gap-3">{right}</div> : null}
        </header>
      ) : null}
      {children}
    </section>
  );
}

type TextProps = { children: ReactNode; className?: string };

export function ColumnTitle({ children, aside }: { children: string; aside?: ReactNode }) {
  return (
    <div className="flex min-w-0 items-baseline justify-between gap-3">
      <h3 className="text-body-medium text-text-secondary">{children}</h3>
      {aside ? <p className="shrink-0 text-caption-1-regular text-text-tertiary tabular-nums">{aside}</p> : null}
    </div>
  );
}

export function FieldLabel({ children, className, as: Tag = "span" }: TextProps & { as?: "span" | "dt" | "p" }) {
  return <Tag className={cx("text-caption-1-medium text-text-tertiary", className)}>{children}</Tag>;
}

export function FieldValue({ children, className, as: Tag = "span" }: TextProps & { as?: "span" | "dd" | "p" }) {
  return <Tag className={cx("text-body-medium text-text-primary tabular-nums", className)}>{children}</Tag>;
}

// tabular figures set a sign as wide as a digit; keep the sign proportional
function signApart(value: ReactNode): ReactNode {
  if (typeof value !== "string" || !/^[+-]\d/.test(value)) return value;
  return (
    <>
      <span className="normal-nums">{value[0]}</span>
      {value.slice(1)}
    </>
  );
}

type FigureProps = { value: ReactNode; unit?: ReactNode; muted?: boolean; hero?: boolean; className?: string };

export function Figure({ value, unit, muted, hero, className }: FigureProps) {
  return (
    <span className={cx("inline-flex items-baseline gap-1", className)}>
      <span className={cx(hero ? "text-large-title-medium" : "text-title-1-medium", "tabular-nums", muted ? "text-text-tertiary" : "text-text-primary")}>
        {signApart(value)}
      </span>
      {unit ? <span className="text-body-regular text-text-secondary">{unit}</span> : null}
    </span>
  );
}

export function Note({ children, className }: TextProps) {
  return <p className={cx("text-caption-1-regular text-text-tertiary", className)}>{children}</p>;
}

export function EmptyState({ children = "No reading yet", className }: Partial<TextProps>) {
  return <p className={cx("text-body-regular text-text-tertiary", className)}>{children}</p>;
}

export function Columns({ children, className }: Partial<TextProps>) {
  return (
    <div
      className={cx(
        "grid min-h-0 auto-cols-fr grid-flow-col divide-x divide-separator-border",
        "*:flex *:min-w-0 *:flex-col *:gap-2 *:px-4 *:first:ps-0 *:last:pe-0",
        className,
      )}
    >
      {children}
    </div>
  );
}
