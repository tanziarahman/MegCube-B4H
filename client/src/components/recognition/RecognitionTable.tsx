'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertCircle, Eye, Loader2, RotateCcw, Search, Trash2 } from 'lucide-react';
import { fetchDevices, fetchRecognition, deleteRecognition, type Device, type RecognitionRow } from '@/lib/recognition';
import RecognitionDrawer from './RecognitionDrawer';

const PAGE_SIZE = 10;
const RESULTS = [
  { label: 'Matched', minor: 'face_comparison_successful' },
  { label: 'Stranger', minor: 'stranger' },
];

// <input type="datetime-local"> value <-> backend format "YYYY-MM-DD HH:mm:ss"
const today = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const toBackend = (v: string, secs: string) => `${v.replace('T', ' ')}${secs}`;

function Thumb({ src, alt, wide }: { src?: string; alt: string; wide?: boolean }) {
  const [failed, setFailed] = useState(false);
  const size = wide ? 'h-[46px] w-[64px]' : 'h-[56px] w-[44px]';
  if (!src || failed) {
    return <div className={`${size} rounded bg-ground`} aria-label={`${alt} not available`} />;
  }
  return (
    <a href={src} target="_blank" rel="noreferrer">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={alt} loading="lazy" onError={() => setFailed(true)} className={`${size} rounded object-cover`} />
    </a>
  );
}

/** Small centered "are you sure?" dialog for deleting a record. */
function ConfirmDelete({ row, busy, onCancel, onConfirm }: {
  row: RecognitionRow;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    cancelRef.current?.focus();   // safe default: Enter cancels, not deletes
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && !busy && onCancel();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [busy, onCancel]);

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" role="alertdialog" aria-modal="true" aria-labelledby="del-title">
      <button aria-label="Cancel" onClick={() => !busy && onCancel()} className="absolute inset-0 cursor-default bg-black/40" />
      <div className="relative w-full max-w-[400px] rounded-lg bg-white p-5 shadow-xl">
        <div className="flex gap-3">
          <AlertCircle size={22} className="mt-0.5 shrink-0 text-[#F59E0B]" />
          <div>
            <h2 id="del-title" className="text-[15px] font-medium">Are you sure you want to delete this record?</h2>
            <p className="mt-1 text-[12.5px] text-mute">
              {row.name} · <span className="font-mono">{row.time}</span>. This can&apos;t be undone.
            </p>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            ref={cancelRef}
            onClick={onCancel}
            disabled={busy}
            className="h-8 rounded-md border border-line bg-white px-4 text-[13px] hover:bg-ground disabled:opacity-40"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={busy}
            className="h-8 rounded-md bg-[#E5484D] px-4 text-[13px] font-medium text-white hover:bg-[#D13A3F] disabled:opacity-60"
          >
            {busy ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function RecognitionTable() {
  // filter inputs
  const [start, setStart] = useState(`${today()}T00:00`);
  const [end, setEnd] = useState(`${today()}T23:59`);
  const [minor, setMinor] = useState(RESULTS[0].minor);
  const [deviceName, setDeviceName] = useState('');
  // data
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState<RecognitionRow[]>([]);
  const [total, setTotal] = useState(0);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<RecognitionRow | null>(null);   // row shown in the details panel
  const closeDetails = useCallback(() => setSelected(null), []);
  const [deletingId, setDeletingId] = useState<string | null>(null);       // row whose delete is in flight
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(
    async (p: number) => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetchRecognition({
          start: toBackend(start, ':00'), end: toBackend(end, ':59'), page: p, size: PAGE_SIZE, minor,
        });
        setRows(res.rows);
        setTotal(res.total);
        setPage(p);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Could not load records');
      } finally {
        setLoading(false);
      }
    },
    [start, end, minor],
  );

  // first load
  useEffect(() => {
    fetchDevices().then(setDevices);
    load(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const reset = () => {
    setStart(`${today()}T00:00`);
    setEnd(`${today()}T23:59`);
    setMinor(RESULTS[0].minor);
    setDeviceName('');
  };

  // Records only carry a numeric device id; look its name up in the device list.
  const deviceOf = (r: RecognitionRow) => devices.find((d) => d.id === r.deviceId)?.name ?? r.device;
  // The backend has no device filter yet, so filter the loaded page by device name.
  const visible = deviceName ? rows.filter((r) => deviceOf(r) === deviceName) : rows;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Delete flow: the row button opens the dialog; the dialog's Delete button does the work.
  const [confirming, setConfirming] = useState<RecognitionRow | null>(null);
  const closeConfirm = useCallback(() => setConfirming(null), []);   // stable, so the dialog doesn't re-focus on every render

  const confirmDelete = async () => {
    const r = confirming;
    if (!r || r.alarmId == null) return;
    setDeletingId(r.id);
    setActionError(null);
    try {
      await deleteRecognition(r.alarmId);
      setConfirming(null);
      if (selected?.id === r.id) setSelected(null);
      // reload; step back a page if this was the last row on it
      await load(rows.length === 1 && page > 1 ? page - 1 : page);
    } catch (e) {
      setConfirming(null);
      setActionError(e instanceof Error ? e.message : 'Could not delete the record');
    } finally {
      setDeletingId(null);
    }
  };

  const inputCls = 'h-9 rounded-md border border-line bg-white px-2.5 text-[13px] outline-none focus:border-pri';

  return (
    <div className="rounded-lg border border-line bg-white">
      {/* Filters */}
      <form
        onSubmit={(e) => { e.preventDefault(); load(1); }}
        className="flex flex-wrap items-end gap-3 border-b border-line p-4"
      >
        <label className="text-[12px] font-medium text-mute">
          Capture device
          <select value={deviceName} onChange={(e) => setDeviceName(e.target.value)} className={`${inputCls} mt-1 block w-44`}>
            <option value="">All</option>
            {devices.map((d) => <option key={d.id} value={d.name}>{d.name}</option>)}
          </select>
        </label>
        <label className="text-[12px] font-medium text-mute">
          Recognition result
          <select value={minor} onChange={(e) => setMinor(e.target.value)} className={`${inputCls} mt-1 block w-36`}>
            {RESULTS.map((r) => <option key={r.minor} value={r.minor}>{r.label}</option>)}
          </select>
        </label>
        <label className="text-[12px] font-medium text-mute">
          From
          <input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} className={`${inputCls} mt-1 block`} />
        </label>
        <label className="text-[12px] font-medium text-mute">
          To
          <input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} className={`${inputCls} mt-1 block`} />
        </label>
        <div className="ml-auto flex gap-2">
          <button type="submit" className="flex h-9 items-center gap-1.5 rounded-md bg-pri px-4 text-[13px] font-medium text-white hover:bg-[#1A43A0]">
            <Search size={15} /> Search
          </button>
          <button type="button" onClick={reset} className="flex h-9 items-center gap-1.5 rounded-md border border-line px-4 text-[13px] hover:bg-ground">
            <RotateCcw size={15} /> Reset
          </button>
        </div>
      </form>

      {/* Table */}
      {actionError && (
        <div className="flex items-center justify-between border-b border-line bg-[#FDECEC] px-4 py-2 text-[13px] text-crit">
          <span>{actionError}</span>
          <button onClick={() => setActionError(null)} className="hover:underline">Dismiss</button>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead className="bg-[#F7F8FA] text-left text-[12px] text-mute">
            <tr>
              <th className="px-4 py-2.5 font-medium">Face</th>
              <th className="px-4 py-2.5 font-medium">Panoramic</th>
              <th className="px-4 py-2.5 font-medium">Capture device</th>
              <th className="px-4 py-2.5 font-medium">Capture time</th>
              <th className="px-4 py-2.5 font-medium">Living fraction</th>
              <th className="px-4 py-2.5 font-medium">Base image</th>
              <th className="px-4 py-2.5 font-medium">Name</th>
              <th className="px-4 py-2.5 font-medium">Group</th>
              <th className="px-4 py-2.5 font-medium">Similarity</th>
              <th className="px-4 py-2.5 font-medium"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={10} className="px-4 py-10 text-center text-mute">Loading…</td></tr>
            )}
            {!loading && error && (
              <tr><td colSpan={10} className="px-4 py-10 text-center">
                <p className="text-crit">Couldn’t load records: {error}</p>
                <button onClick={() => load(page)} className="mt-2 text-pri hover:underline">Try again</button>
              </td></tr>
            )}
            {!loading && !error && visible.length === 0 && (
              <tr><td colSpan={10} className="px-4 py-10 text-center text-mute">No records for these filters.</td></tr>
            )}
            {!loading && !error && visible.map((r) => (
                <tr key={r.id} className={`border-t border-line align-middle ${selected?.id === r.id ? 'bg-[#F2F6FF]' : ''}`}>
                  <td className="px-4 py-2.5"><Thumb src={r.faceImg} alt="Face" /></td>
                  <td className="px-4 py-2.5"><Thumb src={r.panoramaImg} alt="Panoramic" wide /></td>
                  <td className="px-4 py-2.5">{deviceOf(r)}</td>
                  <td className="px-4 py-2.5 font-mono text-[12.5px]">{r.time}</td>
                  <td className="px-4 py-2.5 font-mono">{r.living}</td>
                  <td className="px-4 py-2.5"><Thumb src={r.baseImg} alt="Base image" /></td>
                  <td className="px-4 py-2.5 font-medium">{r.name}</td>
                  <td className="max-w-[180px] truncate px-4 py-2.5" title={r.groups}>{r.groups}</td>
                  <td className="px-4 py-2.5 font-mono">{r.similarity}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex justify-end gap-1">
                      <button
                        type="button"
                        onClick={() => setSelected(r)}
                        title="View details"
                        className="flex h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-xs font-medium hover:bg-ground"
                      >
                        <Eye size={14} /> Details
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirming(r)}
                        disabled={r.alarmId == null || deletingId !== null}
                        title="Delete record"
                        aria-label={`Delete the recognition of ${r.name} at ${r.time}`}
                        className="flex h-8 w-8 items-center justify-center rounded-md text-crit hover:bg-crit-bg disabled:opacity-40"
                      >
                        {deletingId === r.id ? <Loader2 size={15} className="animate-spin" /> : <Trash2 size={15} />}
                      </button>
                    </div>
                  </td>
                </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between border-t border-line px-4 py-3 text-[13px]">
        <span className="text-mute">
          Total {total} items{deviceName && ` · showing ${visible.length} from ${deviceName} on this page`}
        </span>
        <div className="flex items-center gap-2">
          <button disabled={page <= 1 || loading} onClick={() => load(page - 1)}
            className="h-8 rounded-md border border-line px-3 disabled:opacity-40">Previous</button>
          <span className="font-mono">{page} / {pages}</span>
          <button disabled={page >= pages || loading} onClick={() => load(page + 1)}
            className="h-8 rounded-md border border-line px-3 disabled:opacity-40">Next</button>
        </div>
      </div>

      <RecognitionDrawer row={selected} deviceName={selected ? deviceOf(selected) : ''} onClose={closeDetails} />

      {confirming && (
        <ConfirmDelete
          row={confirming}
          busy={deletingId === confirming.id}
          onCancel={closeConfirm}
          onConfirm={confirmDelete}
        />
      )}
    </div>
  );
}