// nasa power grid: 0.5 deg latitude by 0.625 deg longitude
const LAT_STEP = 0.5;
const LON_STEP = 0.625;

// matches python's round(), which sends ties to the even neighbour
function roundHalfEven(x: number): number {
  const floor = Math.floor(x);
  const diff = x - floor;
  if (diff < 0.5) return floor;
  if (diff > 0.5) return floor + 1;
  return floor % 2 === 0 ? floor : floor + 1;
}

const snap = (x: number, step: number) => roundHalfEven(x / step) * step || 0;

export function powerCell(lat: number, lon: number): [number, number] {
  return [snap(lat, LAT_STEP), snap(lon, LON_STEP)];
}

export function cellId(cell: [number, number]): string {
  return `${cell[0].toFixed(3)}_${cell[1].toFixed(3)}`;
}
