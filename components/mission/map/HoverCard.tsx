import type { HoverCard as Card } from "@/lib/map/hover";
import type { Size } from "@/lib/map/projection";

const WIDTH = 248;

// a small card beside the pointer; it never takes the pointer, so the thing under it stays clickable
export function HoverCard({ card, at, size }: { card: Card; at: { x: number; y: number }; size: Size }) {
  const left = at.x + 16 + WIDTH > size.width ? at.x - 16 - WIDTH : at.x + 16;
  const below = at.y < size.height / 2;
  return (
    <div
      role="status"
      data-hover-card
      className="pointer-events-none absolute z-10 flex flex-col gap-1 rounded-xl border border-border-button-default bg-background-primary-default px-3 py-2 shadow-lg"
      style={{ left: Math.max(4, left), width: WIDTH, ...(below ? { top: at.y + 12 } : { bottom: size.height - at.y + 12 }) }}
    >
      <p className="text-body-2-semibold text-text-primary">{card.title}</p>
      {card.lines.map((line) => (
        <p key={line} className="text-caption-1-regular text-text-secondary tabular-nums">
          {line}
        </p>
      ))}
    </div>
  );
}
