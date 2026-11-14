// Engagement colour scale: 0 = cold ink, 10 = hot amber (shared by every heat cell).
export const heat = (v: number): string => {
  const t = Math.max(0, Math.min(10, v)) / 10
  const r = Math.round(38 + t * (245 - 38))
  const g = Math.round(43 + t * (184 - 43))
  const b = Math.round(52 + t * (74 - 52))
  return `rgb(${r},${g},${b})`
}
