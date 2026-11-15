import { useEffect, useMemo, useState } from "react";
import type { GeoProjection } from "d3-geo";
import { linePath } from "@/lib/map/paths";
import { project, type View } from "@/lib/map/projection";
import type { Delivery } from "@/lib/mission/orders";
import { cx } from "@/utils/cx";
import { HALO } from "./PlaceLayer";

const reducedMotion = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// an animation-frame clock while the vehicle is on the road; once a second under reduced motion
function useClock(delivery: Delivery | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!delivery) return;
    let frame = 0;
    let timer: ReturnType<typeof setInterval> | undefined;
    const tick = () => {
      const t = Date.now();
      setNow(t);
      if (delivery.progress(t) >= 1) {
        cancelAnimationFrame(frame);
        clearInterval(timer);
        return false;
      }
      return true;
    };
    if (reducedMotion()) {
      tick();
      timer = setInterval(tick, 1000);
    } else {
      const loop = () => {
        if (tick()) frame = requestAnimationFrame(loop);
      };
      frame = requestAnimationFrame(loop);
    }
    return () => {
      cancelAnimationFrame(frame);
      clearInterval(timer);
    };
  }, [delivery]);
  return now;
}

const line = "fill-none [vector-effect:non-scaling-stroke] [stroke-linejoin:round] [stroke-linecap:round]";

export function DeliveryLayer({ delivery, projection, view }: { delivery: Delivery | null; projection: GeoProjection; view: View }) {
  const now = useClock(delivery);
  const d = useMemo(() => (delivery ? linePath(projection, delivery.route.line) : ""), [delivery, projection]);
  if (!delivery) return null;

  const [lon, lat] = delivery.position(now);
  const [x, y] = project(projection, view, lon, lat);

  return (
    <g data-layer="delivery" className="pointer-events-none">
      <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`} aria-hidden>
        <path d={d} className={cx(line, "stroke-background-primary-default [stroke-width:5px]")} />
        <path d={d} data-route className={cx(line, "stroke-text-primary [stroke-width:2px]")} />
      </g>
      <g data-vehicle role="img" aria-label={delivery.label(now)}>
        <circle cx={x} cy={y} r={5.5} className="fill-text-primary stroke-background-primary-default [stroke-width:2px]" />
        {/* right of the dot and below it: town names and the pod id sit to the left and above */}
        <text x={x + 10} y={y + 14} dy="0.35em" textAnchor="start" className={cx("fill-text-secondary text-caption-1-medium", HALO)}>
          simulated vehicle
        </text>
      </g>
    </g>
  );
}
