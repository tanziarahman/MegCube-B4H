'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, Database, Moon, RefreshCw, Users } from 'lucide-react';
import {
  CountingError, DEFAULT_FILTERS, GRANULARITY_MAX_DAYS, PRESET_LABELS, autoGranularity, fetchCountingCameras,
  fetchCountingHeatmap, fetchCountingSeries, fetchCountingSummary, rangeDays,
  type CountingCamera, type CountingFilters, type CountingSummary, type FaceEstimate, type Granularity, type Heatmap,
  type Preset, type SeriesPoint,
} from '@/lib/counting';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { ErrorNote, Field, btnCls, formatTime, inputCls } from '@/components/alarms/shared';
import { BusyTimes, SeriesChart, type ChartMetric } from './charts';
import CameraSettings from './CameraSettings';
import SightingsList from './SightingsList';

const REFRESH_MS = 60_000;
const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const GRANULARITY_LABELS: Record<Granularity, string> = { '15m': '15 min', hour: 'Hour', day: 'Day' };
const number = (n: number) => n.toLocaleString();

interface Data { summary: CountingSummary; series: SeriesPoint[]; heatmap: Heatmap; granularity: Granularity }

function Section({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-line bg-white">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
        <h2 className="text-[15px] font-semibold text-slate-800">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Tile({ label, value, detail, tag }: { label: string; value: string; detail: string; tag?: string }) {
  return (
    <div className="rounded-xl border border-line bg-white px-4 py-4">
      <div className="flex items-center gap-2">
        <p className="text-[12px] font-semibold uppercase tracking-[0.08em] text-mute">{label}</p>
        {tag && <span className="rounded-full bg-warn-bg px-1.5 py-0.5 text-[11px] font-medium text-warn">{tag}</span>}
      </div>
      <p className="mt-2 text-[26px] font-semibold text-slate-800">{value}</p>
      <p className="mt-1 text-[12.5px] text-mute">{detail}</p>
    </div>
  );
}

/** A face estimate worth showing: at least one face compared, and the period wasn't too big. */
const usable = (e: FaceEstimate | null): e is FaceEstimate & { people: number; low: number; high: number } =>
  e !== null && e.people !== null && e.low !== null && e.high !== null && e.fingerprinted > 0;

/** One line under the tiles: how "different people" was worked out, and what it leaves out. */
function PeopleNote({ summary }: { summary: CountingSummary }) {
  const e = summary.totals.faceEstimate;
  const pending = e?.pending ? ` ${number(e.pending)} walk-past${e.pending === 1 ? ' is' : 's are'} still being processed.` : '';
  let text: string;
  if (e?.tooMany) {
    text = 'This period has too many walk-pasts to compare: pick a shorter period to see different people.';
  } else if (usable(e)) {
    text = `Different people are told apart by comparing faces and clothing, so it’s an estimate; the range shows how far off it could be.`
      + (e.unusable ? ` ${number(e.unusable)} walk-past${e.unusable === 1 ? '' : 's'} had no usable picture and ${e.unusable === 1 ? 'isn’t' : 'aren’t'} included.` : '')
      + pending;
  } else if (summary.faceMatching.available && e?.pending) {
    text = `Pictures are still being compared; different people appears once they’re done.${pending}`;
  } else if (!summary.identityAvailable) {
    text = 'People can’t be told apart yet, so different people is the same as walk-pasts for now'
      + (summary.faceMatching.reason ? ` (${summary.faceMatching.reason}).` : '.');
  } else {
    return null;
  }
  return <p className="mt-2 text-[13px] text-mute">{text}</p>;
}

function CameraPicker({ cameras, value, onChange }: {
  cameras: CountingCamera[]; value: number[]; onChange: (ids: number[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);
  const choices = cameras.filter((c) => !c.deleted);
  const label = value.length === 0 ? 'All counted cameras'
    : value.length === 1 ? (choices.find((c) => c.id === value[0])?.name ?? '1 camera') : `${value.length} cameras`;
  const toggle = (id: number) => onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id].sort((a, b) => a - b));

  return (
    <div ref={ref} className="relative">
      <button type="button" aria-label="Cameras" aria-expanded={open} onClick={() => setOpen((o) => !o)}
        className={`${inputCls} flex w-52 items-center justify-between gap-2 text-left`}>
        <span className="truncate">{label}</span><ChevronDown size={15} className="shrink-0 text-mute" />
      </button>
      {open && (
        <div className="absolute z-20 mt-1 w-64 rounded-lg border border-line bg-white p-2 shadow-lg">
          {choices.map((c) => (
            <label key={c.id} className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-[14px] hover:bg-ground">
              <input type="checkbox" checked={value.includes(c.id)} onChange={() => toggle(c.id)} />
              <span className="flex-1 truncate">{c.name}</span>
              {!c.countEnabled && <span className="text-[11.5px] text-mute">not counted</span>}
            </label>
          ))}
          {!choices.length && <p className="px-2 py-1.5 text-[13px] text-mute">No cameras yet</p>}
          {value.length > 0 && (
            <button type="button" onClick={() => onChange([])} className="mt-1 w-full rounded-md px-2 py-1.5 text-left text-[13px] text-pri hover:bg-ground">
              Use all counted cameras
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function hourOptions() {
  return Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{String(h).padStart(2, '0')}:00</option>);
}

export default function CountingView() {
  const [filters, setFilters] = useLocalStorage<CountingFilters>('counting.filters', DEFAULT_FILTERS);
  const f = { ...DEFAULT_FILTERS, ...filters };            // older saved filters may lack new fields
  const [cameras, setCameras] = useState<CountingCamera[]>([]);
  const [chosenGranularity, setChosenGranularity] = useState<Granularity | null>(null);
  const [chosenMetric, setChosenMetric] = useState<ChartMetric | null>(null);
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [noDatabase, setNoDatabase] = useState<string | null>(null);
  const [version, setVersion] = useState(0);            // bumps on refresh, so the sightings reload too

  const days = rangeDays(f);
  const allowed = (Object.keys(GRANULARITY_MAX_DAYS) as Granularity[]).filter((g) => days <= GRANULARITY_MAX_DAYS[g]);
  const granularity = chosenGranularity && allowed.includes(chosenGranularity) ? chosenGranularity : autoGranularity(days);
  const filterKey = JSON.stringify(f);

  const fail = (e: unknown, what: string) => {
    if (e instanceof CountingError && e.status === 503) setNoDatabase(e.message);
    else setError(e instanceof Error ? e.message : what);
  };

  const loadCameras = useCallback(async () => {
    try {
      setCameras(await fetchCountingCameras());
    } catch (e) {
      fail(e, 'Could not load cameras');
    }
  }, []);

  const load = useCallback(async (quiet = false) => {
    const current: CountingFilters = JSON.parse(filterKey);
    if (!quiet) setLoading(true);
    setError(null);
    try {
      const [summary, series, heatmap] = await Promise.all([
        fetchCountingSummary(current), fetchCountingSeries(current, granularity), fetchCountingHeatmap(current),
      ]);
      setNoDatabase(null);
      setData({ summary, series, heatmap, granularity });
    } catch (e) {
      fail(e, 'Could not load the counts');
    } finally {
      setLoading(false);
    }
  }, [filterKey, granularity]);

  useEffect(() => { loadCameras(); }, [loadCameras]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (f.preset !== 'today') return;
    const timer = setInterval(() => { load(true); setVersion((v) => v + 1); }, REFRESH_MS);
    return () => clearInterval(timer);
  }, [f.preset, load]);

  const update = (change: Partial<CountingFilters>) => { setFilters({ ...f, ...change }); setChosenGranularity(null); };
  const refresh = () => { load(); loadCameras(); setVersion((v) => v + 1); };
  const filtered = JSON.stringify(f) !== JSON.stringify(DEFAULT_FILTERS);
  const hoursActive = f.hourFrom !== null && f.hourTo !== null;

  const totals = data?.summary.totals;
  const identity = data?.summary.identityAvailable ?? false;
  const empty = data !== null && totals?.walkPasts === 0;
  // New people (each person once, when they first appear) when faces can be compared, else walk-pasts.
  const canShowNew = Boolean(data?.series.some((p) => p.newPeople !== null) && usable(data?.summary.totals.faceEstimate ?? null));
  const metric: ChartMetric = canShowNew ? chosenMetric ?? 'newPeople' : 'walkPasts';
  const peak = useMemo(() => {
    if (!data?.series.length) return null;
    const value = (p: SeriesPoint) => (metric === 'newPeople' ? p.newPeople ?? 0 : p.walkPasts);
    return Math.max(...data.series.map(value));
  }, [data, metric]);

  if (noDatabase) {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-line bg-white p-5 text-[14.5px] text-slate-700">
        <Database size={22} className="mt-0.5 shrink-0 text-pri" />
        <div>
          <p className="font-semibold text-slate-800">People counting needs the portal database</p>
          <p className="mt-1 text-mute">
            Set <code className="rounded bg-ground px-1">DATABASE_URL</code> in <code className="rounded bg-ground px-1">fastapi-app/.env</code> to your
            Neon connection string, run <code className="rounded bg-ground px-1">uv run alembic upgrade head</code>, then restart the backend.
          </p>
          <p className="mt-2 text-[13px] text-mute">The backend said: {noDatabase}</p>
          <button onClick={() => { setNoDatabase(null); refresh(); }} className={`${btnCls} mt-3`}>Try again</button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-white p-3.5">
        <Field label="Cameras">
          <CameraPicker cameras={cameras} value={f.cameraIds} onChange={(cameraIds) => update({ cameraIds })} />
        </Field>
        <Field label="Period">
          <select aria-label="Period" value={f.preset} onChange={(e) => update({ preset: e.target.value as Preset })} className={`${inputCls} w-40`}>
            {(Object.keys(PRESET_LABELS) as Preset[]).map((p) => <option key={p} value={p}>{PRESET_LABELS[p]}</option>)}
          </select>
        </Field>
        {f.preset === 'custom' && (
          <>
            <Field label="From">
              <div className="flex gap-1.5">
                <input type="date" aria-label="From date" value={f.fromDate} onChange={(e) => update({ fromDate: e.target.value })} className={inputCls} />
                <input type="time" aria-label="From time" value={f.fromTime} onChange={(e) => update({ fromTime: e.target.value })} className={`${inputCls} w-28`} />
              </div>
            </Field>
            <Field label="To">
              <div className="flex gap-1.5">
                <input type="date" aria-label="To date" value={f.toDate} onChange={(e) => update({ toDate: e.target.value })} className={inputCls} />
                <input type="time" aria-label="To time" value={f.toTime} onChange={(e) => update({ toTime: e.target.value })} className={`${inputCls} w-28`} />
              </div>
            </Field>
          </>
        )}
        <Field label="Hours">
          <div className="flex items-center gap-1.5">
            <select aria-label="From hour" value={f.hourFrom ?? ''} className={`${inputCls} w-24`}
              onChange={(e) => {
                const v = e.target.value === '' ? null : Number(e.target.value);
                update({ hourFrom: v, hourTo: v === null ? null : f.hourTo ?? 23 });
              }}>
              <option value="">Any</option>{hourOptions()}
            </select>
            <span className="text-mute">to</span>
            <select aria-label="To hour" value={f.hourTo ?? ''} className={`${inputCls} w-24`}
              onChange={(e) => {
                const v = e.target.value === '' ? null : Number(e.target.value);
                update({ hourTo: v, hourFrom: v === null ? null : f.hourFrom ?? 0 });
              }}>
              <option value="">Any</option>{hourOptions()}
            </select>
            {hoursActive && f.hourTo! < f.hourFrom! && (
              <span className="flex items-center gap-1 text-[12.5px] text-mute"><Moon size={13} /> past midnight</span>
            )}
          </div>
        </Field>
        <Field label="Weekdays">
          <div className="flex gap-1">
            {DAY_NAMES.map((name, i) => {
              const d = i + 1;
              const on = f.days.includes(d);
              return (
                <button key={name} type="button" aria-pressed={on} aria-label={name}
                  onClick={() => update({ days: on ? f.days.filter((x) => x !== d) : [...f.days, d].sort() })}
                  className={`w-10 rounded-md border py-2 text-[12.5px] font-medium ${on ? 'border-pri bg-pri-bg text-pri' : 'border-line text-mute'}`}>
                  {name}
                </button>
              );
            })}
          </div>
        </Field>
        <div className="ml-auto flex items-center gap-2">
          {filtered && <button onClick={() => { setFilters(DEFAULT_FILTERS); setChosenGranularity(null); }} className={btnCls}>Reset</button>}
          <button onClick={refresh} disabled={loading} className={btnCls}>
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {error && <ErrorNote message={`Couldn’t load the counts: ${error}`} onRetry={refresh} />}

      {/* Number tiles */}
      {!data ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((i) => <div key={i} className="h-[118px] animate-pulse rounded-xl border border-line bg-white" />)}
        </div>
      ) : (
        <div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Tile label="Walk-pasts" value={number(totals!.walkPasts)}
              detail={`${number(totals!.paired)} face + body · ${number(totals!.faceOnly)} face only · ${number(totals!.bodyOnly)} body only`} />
            {usable(totals!.faceEstimate) ? (
              <Tile label="Different people" value={`≈ ${number(totals!.faceEstimate.people)}`} tag="estimate"
                detail={`Likely ${number(totals!.faceEstimate.low)}–${number(totals!.faceEstimate.high)} · from ${number(totals!.faceEstimate.fingerprinted)} of ${number(totals!.walkPasts)} walk-pasts`} />
            ) : (
              <Tile label="Different people" value={number(totals!.uniquePeople)} tag={identity ? undefined : 'estimate'}
                detail={identity ? `Exact for recognised people · ${number(totals!.visits)} visits` : `At most this many · ${number(totals!.visits)} visits`} />
            )}
            <Tile label="Recognised people" value={number(totals!.knownPeople)} detail="Different face-library people" />
            <Tile label="Strangers (walk-pasts)" value={number(totals!.strangerWalkPasts)}
              detail="Walk-pasts with no face-library match; not different people" />
          </div>
          <PeopleNote summary={data.summary} />
        </div>
      )}

      {empty && !loading && (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-line bg-white py-10 text-[14.5px] text-mute">
          <Users size={24} className="text-slate-300" />
          No one walked past in this period.
          {data?.summary.lastSightingAt && <span className="text-[12.5px]">Last walk-past: {formatTime(data.summary.lastSightingAt)}</span>}
        </div>
      )}

      {data && !empty && (
        <>
          <Section title="Over time" action={
            <div className="flex flex-wrap items-center gap-3">
              {peak !== null && peak > 0 && <span className="text-[12px] text-mute">Peak {peak} {metric === 'newPeople' ? 'new people' : 'walk-pasts'}</span>}
              {canShowNew && (
                <div role="group" aria-label="Chart shows" className="flex rounded-lg border border-line p-0.5">
                  {(['newPeople', 'walkPasts'] as ChartMetric[]).map((m) => (
                    <button key={m} type="button" aria-pressed={metric === m} onClick={() => setChosenMetric(m)}
                      className={`rounded-md px-2.5 py-1 text-[12.5px] font-medium ${metric === m ? 'bg-pri-bg text-pri' : 'text-mute hover:text-slate-700'}`}>
                      {m === 'newPeople' ? 'New people' : 'Walk-pasts'}
                    </button>
                  ))}
                </div>
              )}
              <div role="group" aria-label="Bar size" className="flex rounded-lg border border-line p-0.5">
                {allowed.map((g) => (
                  <button key={g} type="button" aria-pressed={granularity === g} onClick={() => setChosenGranularity(g)}
                    className={`rounded-md px-2.5 py-1 text-[12.5px] font-medium ${granularity === g ? 'bg-pri-bg text-pri' : 'text-mute hover:text-slate-700'}`}>
                    {GRANULARITY_LABELS[g]}
                  </button>
                ))}
              </div>
            </div>
          }>
            <div className="px-4 pb-3 pt-4">
              <SeriesChart points={data.series} granularity={data.granularity} metric={metric} />
              <p className="mt-1 text-[12px] text-mute">
                {metric === 'newPeople'
                  ? `People seen for the first time in this period, per ${data.granularity === '15m' ? '15 minutes' : data.granularity}: someone who comes back isn’t counted again.`
                  : `Every walk-past per ${data.granularity === '15m' ? '15 minutes' : data.granularity}, including people coming back.`} Hover a bar for its number.
              </p>
            </div>
          </Section>

          <Section title="Busy times" action={<span className="text-[12px] text-mute">Average per day, by weekday and hour ({data.summary.timezone || 'box time'})</span>}>
            <div className="px-4 py-4"><BusyTimes data={data.heatmap} /></div>
          </Section>

          <Section title="By camera">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[14px]">
                <thead>
                  <tr className="border-b border-line bg-slate-50/70 text-[12px] uppercase tracking-wide text-mute">
                    <th className="px-4 py-2.5 font-medium">Camera</th>
                    <th className="px-4 py-2.5 text-right font-medium">Walk-pasts</th>
                    <th className="px-4 py-2.5 text-right font-medium">Visits</th>
                    <th className="px-4 py-2.5 text-right font-medium">Different people (est.)</th>
                    <th className="px-4 py-2.5 text-right font-medium">Face + body</th>
                    <th className="px-4 py-2.5 text-right font-medium">Face only</th>
                    <th className="px-4 py-2.5 text-right font-medium">Body only</th>
                  </tr>
                </thead>
                <tbody>
                  {data.summary.byCamera.map((c) => (
                    <tr key={c.cameraId} className="border-b border-line last:border-0">
                      <td className="px-4 py-2.5 font-medium text-slate-800">{c.name}</td>
                      <td className="px-4 py-2.5 text-right font-mono">{number(c.walkPasts)}</td>
                      <td className="px-4 py-2.5 text-right font-mono">{number(c.visits)}</td>
                      <td className="px-4 py-2.5 text-right font-mono">
                        {usable(c.faceEstimate)
                          ? <span title={`Likely ${c.faceEstimate.low}–${c.faceEstimate.high}, from ${c.faceEstimate.fingerprinted} walk-pasts`}>≈ {number(c.faceEstimate.people)}</span>
                          : <span title="At most this many">{number(c.uniquePeople)}</span>}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono">{number(c.paired)}</td>
                      <td className="px-4 py-2.5 text-right font-mono">{number(c.faceOnly)}</td>
                      <td className="px-4 py-2.5 text-right font-mono">{number(c.bodyOnly)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        </>
      )}

      {data && <SightingsList filters={f} reloadKey={`${filterKey}:${version}`} />}

      <CameraSettings cameras={cameras} onChanged={(c) => { setCameras((cs) => cs.map((x) => (x.id === c.id ? c : x))); load(true); }} />
    </div>
  );
}
