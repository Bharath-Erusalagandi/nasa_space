export function senLine(trend: { intercept: number; slope_per_year: number }, seasons: number[]): number[] {
  return seasons.map((season) => trend.intercept + trend.slope_per_year * season);
}
