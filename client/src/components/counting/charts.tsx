'use client';

import type { Granularity, Heatmap, SeriesPoint } from '@/lib/counting';

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const pad = (n: number) => String(n).padStart(2, '0');

/** Slot start -> short label in this browser's time zone (like every other page). */
export function slotLabel(iso: string, granularity: Granularity): string {
  const d = new Date(iso);
  if (granularity === 'day') return `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function slotTitle(iso: string, granularity: Granularity): string {
  const d = new Date(iso);
  const day = `${DAY_NAMES[(d.getDay() + 6) % 7]} ${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  return granularity === 'day' ? day : `${day} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** A round top for the axis: 1, 2, 5 x 10^n. */
function niceMax(value: number): number {
  if (value <= 4) return 4;
  const step = 10 ** Math.floor(Math.log10(value));
  return [1, 2, 5, 10].map((m) => m * step).find((m) => m >= value) ?? value;
}

const W = 800;
const H = 220;
const LEFT = 36;
const BOTTOM = 24;
const TOP = 8;

/** Bars with a rounded top, anchored to the baseline. */
function barPath(x: number, y: number, w: number, h: number): string {
  const r = Math.min(3, w / 2, h);
  return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
}

export type ChartMetric = 'newPeople' | 'walkPasts';
const METRIC_UNITS: Record<ChartMetric, [string, string]> = {
  newPeople: ['new person', 'new people'],
  walkPasts: ['walk-past', 'walk-pasts'],
};

/** New people or walk-pasts over time: one series, one scale. Each bar has a hover title. */
export function SeriesChart({ points, granularity, metric = 'walkPasts' }: {
  points: SeriesPoint[]; granularity: Granularity; metric?: ChartMetric;
}) {
  const value = (p: SeriesPoint) => (metric === 'newPeople' ? p.newPeople ?? 0 : p.walkPasts);
  const [one, many] = METRIC_UNITS[metric];
  const max = niceMax(Math.max(0, ...points.map(value)));
  const plotW = W - LEFT;
  const plotH = H - TOP - BOTTOM;
  const slot = plotW / Math.max(points.length, 1);
  const gap = Math.min(2, slot * 0.2);
  const barW = Math.max(1, Math.min(slot - gap, 28));
  const labelEvery = Math.max(1, Math.ceil(points.length / 12));
  const ticks = [0, max / 2, max];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img"
      aria-label={`${many[0].toUpperCase()}${many.slice(1)} per ${granularity === '15m' ? '15 minutes' : granularity}, ${points.length} bars`}>
      {ticks.map((t) => {
        const y = TOP + plotH - (t / max) * plotH;
        return (
          <g key={t}>
            <line x1={LEFT} x2={W} y1={y} y2={y} stroke="#DCE0E5" strokeWidth={t === 0 ? 1 : 0.6}
              strokeDasharray={t === 0 ? undefined : '3 3'} />
            <text x={LEFT - 6} y={y + 4} textAnchor="end" fontSize="11" fill="#58616C">{Number.isInteger(t) ? t : t.toFixed(1)}</text>
          </g>
        );
      })}
      {points.map((p, i) => {
        const x = LEFT + i * slot + (slot - barW) / 2;
        const v = value(p);
        const h = (v / max) * plotH;
        const title = `${slotTitle(p.start, granularity)} · ${v} ${v === 1 ? one : many}`;
        return (
          <g key={p.start}>
            <title>{title}</title>
            {/* Hit area larger than the bar. */}
            <rect x={LEFT + i * slot} y={TOP} width={slot} height={plotH} fill="transparent" />
            {v > 0 && <path d={barPath(x, TOP + plotH - h, barW, h)} fill="#1F4FB5" />}
            {i % labelEvery === 0 && (
              <text x={LEFT + i * slot + slot / 2} y={H - 6} textAnchor="middle" fontSize="11" fill="#58616C">
                {slotLabel(p.start, granularity)}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

/** Weekday x hour grid, shaded by the average walk-pasts per day (one hue, light to dark). */
export function BusyTimes({ data }: { data: Heatmap }) {
  const values = new Map(data.cells.map((c) => [`${c.isoDow}-${c.hour}`, c]));
  const max = Math.max(0, ...data.cells.map((c) => c.avgWalkPasts));
  const shade = (v: number) => (v <= 0 || max <= 0 ? 0 : 0.15 + 0.85 * (v / max));

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[640px]">
        <div className="grid grid-cols-[40px_repeat(24,minmax(0,1fr))] gap-[2px] text-[11px] text-mute">
          <span />
          {Array.from({ length: 24 }, (_, h) => (
            <span key={h} className="text-center">{h % 3 === 0 ? pad(h) : ''}</span>
          ))}
          {DAY_NAMES.map((name, i) => {
            const dow = i + 1;
            const inRange = (data.daysInRange[dow] ?? 0) > 0;
            return [
              <span key={name} className="flex items-center">{name}</span>,
              ...Array.from({ length: 24 }, (_, h) => {
                const cell = values.get(`${dow}-${h}`);
                const avg = cell?.avgWalkPasts ?? 0;
                const title = inRange
                  ? `${name} ${pad(h)}:00 · ${avg} on average per day${cell ? ` (${cell.walkPasts} in total)` : ''}`
                  : `${name}: not in the chosen period`;
                return (
                  <div key={`${dow}-${h}`} title={title} data-testid={`cell-${dow}-${h}`}
                    className={`h-6 rounded-[3px] ${inRange ? 'bg-ground' : 'bg-[repeating-linear-gradient(45deg,#F3F4F6,#F3F4F6_3px,#fff_3px,#fff_6px)]'}`}>
                    {avg > 0 && <div className="h-full w-full rounded-[3px] bg-pri" style={{ opacity: shade(avg) }} />}
                  </div>
                );
              }),
            ];
          })}
        </div>
        <div className="mt-3 flex items-center gap-2 text-[12px] text-mute">
          <span>Average walk-pasts per day:</span>
          <span>0</span>
          <span className="h-2.5 w-28 rounded-full bg-gradient-to-r from-[#1F4FB526] to-pri" />
          <span>{max ? max.toFixed(max < 10 ? 1 : 0) : '0'}</span>
          <span className="ml-3 inline-block h-2.5 w-4 rounded-sm bg-[repeating-linear-gradient(45deg,#F3F4F6,#F3F4F6_3px,#fff_3px,#fff_6px)] ring-1 ring-line" />
          <span>Day not in the period</span>
        </div>
      </div>
    </div>
  );
}
