'use client';

import { useCallback, useEffect, useState } from 'react';
import { fetchSightings, imageUrl, type CountingFilters, type Sighting } from '@/lib/counting';
import { BoxImage, ErrorNote, btnCls, formatTime } from '@/components/alarms/shared';

const PAGE_SIZE = 20;

function identity(s: Sighting): string | null {
  if (s.personSource === 'recognized') return s.personName ?? 'Recognised person';
  if (s.recognitionResult === 'stranger') return 'Stranger';
  return null;
}

/** New person (counted) or came back (not counted again), within the chosen period. */
function Who({ s }: { s: Sighting }) {
  const name = identity(s);
  if (s.personNo === null) {
    return <span className="text-mute" title="No usable face or body picture, so this walk-past can’t be matched to a person">{name ?? 'Can’t tell'}</span>;
  }
  return (
    <div className="flex flex-col gap-0.5">
      <span className="flex items-center gap-1.5">
        {s.newPerson
          ? <span className="rounded-full bg-ok-bg px-2 py-0.5 text-[12px] font-medium text-ok">New person</span>
          : <span className="rounded-full bg-ground px-2 py-0.5 text-[12px] font-medium text-slate-600">Came back</span>}
        <span className="text-slate-700">{name ?? `Person ${s.personNo}`}</span>
      </span>
      {!s.newPerson && s.personFirstSeenAt && (
        <span className="text-[12px] text-mute">First seen {formatTime(s.personFirstSeenAt)}</span>
      )}
    </div>
  );
}

function duration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)} s`;
  return `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60)} s`;
}

/** The walk-pasts behind the numbers, with the box's face and body pictures. */
export default function SightingsList({ filters, reloadKey }: { filters: CountingFilters; reloadKey: string }) {
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<Sighting[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setPage(1), [reloadKey]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchSightings(filters, page, PAGE_SIZE);
      setItems(result.items);
      setTotal(result.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load the walk-pasts');
    } finally {
      setLoading(false);
    }
    // filters are covered by reloadKey
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadKey, page]);

  useEffect(() => { load(); }, [load]);

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className="rounded-xl border border-line bg-white">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <h2 className="text-[15px] font-semibold text-slate-800">Walk-pasts</h2>
        <span className="text-[12px] text-mute">{total.toLocaleString()} in this period · newest first</span>
      </div>
      {error ? (
        <div className="p-4"><ErrorNote message={`Couldn’t load the walk-pasts: ${error}`} onRetry={load} /></div>
      ) : loading && items.length === 0 ? (
        <div className="space-y-2 p-4">{[0, 1, 2].map((i) => <div key={i} className="h-14 animate-pulse rounded-lg bg-ground" />)}</div>
      ) : items.length === 0 ? (
        <p className="px-4 py-8 text-center text-[14px] text-mute">No walk-pasts in this period.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[14px]">
            <thead>
              <tr className="border-b border-line bg-slate-50/70 text-[12px] uppercase tracking-wide text-mute">
                <th className="px-4 py-2.5 font-medium">Face</th>
                <th className="px-4 py-2.5 font-medium">Body</th>
                <th className="px-4 py-2.5 font-medium">Time</th>
                <th className="px-4 py-2.5 font-medium">Camera</th>
                <th className="px-4 py-2.5 font-medium">In view</th>
                <th className="px-4 py-2.5 font-medium">Who</th>
                <th className="px-4 py-2.5 font-medium">Records</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <tr key={s.id} className="border-b border-line last:border-0 hover:bg-slate-50/60">
                  <td className="px-4 py-2"><BoxImage src={imageUrl(s.faceImagePath)} alt={`Face, walk-past ${s.id}`} className="h-12 w-12 rounded-lg" /></td>
                  <td className="px-4 py-2"><BoxImage src={imageUrl(s.bodyImagePath)} alt={`Body, walk-past ${s.id}`} className="h-12 w-9 rounded-lg" /></td>
                  <td className="px-4 py-2 font-mono text-[13.5px] text-slate-700">{formatTime(s.firstSeenAt)}</td>
                  <td className="px-4 py-2 text-slate-700">{s.cameraName}</td>
                  <td className="px-4 py-2 text-slate-700">{duration(s.durationSeconds)}</td>
                  <td className="px-4 py-2"><Who s={s} /></td>
                  <td className="px-4 py-2 text-mute" title={`Face track ${s.faceTrackId ?? '—'} · body track ${s.bodyTrackId ?? '—'}`}>{s.eventCount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {pages > 1 && (
        <div className="flex items-center justify-end gap-2 border-t border-line px-4 py-3 text-[13.5px] text-mute">
          <span>Page {page} of {pages}</span>
          <button onClick={() => setPage((p) => p - 1)} disabled={page <= 1 || loading} className={btnCls}>Previous</button>
          <button onClick={() => setPage((p) => p + 1)} disabled={page >= pages || loading} className={btnCls}>Next</button>
        </div>
      )}
    </section>
  );
}
