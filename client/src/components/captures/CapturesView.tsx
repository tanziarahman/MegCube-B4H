'use client';

import { useEffect, useMemo, useState } from 'react';
import { fetchCaptures, humanizeKey, type CaptureRow, type Device, type TargetType } from '@/lib/captures';
import {
  IconGrid,
  IconList,
  IconChevronLeft,
  IconChevronRight,
  IconClose,
  IconFace,
  IconBody,
  IconRefresh,
  IconImageOff,
} from './icons';

const PAGE_SIZES = [10, 20, 30] as const; // box refuses more than 30/page

function todayStr() {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export default function CapturesView() {
  const [dateFrom, setDateFrom] = useState(todayStr());
  const [dateTo, setDateTo] = useState(todayStr());
  const [targetType, setTargetType] = useState<TargetType>('all');
  const [deviceFilter, setDeviceFilter] = useState<string>('all');
  const [trackFilter, setTrackFilter] = useState('');
  const [view, setView] = useState<'grid' | 'list'>('grid');
  const [page, setPage] = useState(1);
  const [size, setSize] = useState<number>(10);

  const [rows, setRows] = useState<CaptureRow[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<CaptureRow | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchCaptures({
      start: `${dateFrom} 00:00:00`,
      end: `${dateTo} 23:59:59`,
      targetType,
      page,
      size,
    })
      .then(({ rows, total, devices }:any) => {
        if (cancelled) return;
        setRows(rows);
        setTotal(total);
        setDevices(devices);
      })
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateFrom, dateTo, targetType, page, size]);

  // Device + track-id filtering happen client-side on the current page only:
  // the box's alarm_history endpoint doesn't support a device filter, and a
  // track-id search would otherwise need to scan every page.
  const visible = useMemo(
    () =>
      rows.filter(
        (r) =>
          (deviceFilter === 'all' || r.deviceId === deviceFilter) &&
          (!trackFilter.trim() || r.trackId.includes(trackFilter.trim())),
      ),
    [rows, deviceFilter, trackFilter],
  );

  const totalPages = Math.max(1, Math.ceil(total / size));
  const isPageFiltered = deviceFilter !== 'all' || trackFilter.trim() !== '';

  function resetFilters() {
    setDateFrom(todayStr());
    setDateTo(todayStr());
    setTargetType('all');
    setDeviceFilter('all');
    setTrackFilter('');
    setPage(1);
  }

  return (
    <div className="flex flex-col gap-4">
      <Toolbar
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFrom={(v) => (setPage(1), setDateFrom(v))}
        onDateTo={(v) => (setPage(1), setDateTo(v))}
        targetType={targetType}
        onTargetType={(v) => (setPage(1), setTargetType(v))}
        deviceFilter={deviceFilter}
        onDeviceFilter={setDeviceFilter}
        devices={devices}
        trackFilter={trackFilter}
        onTrackFilter={setTrackFilter}
        view={view}
        onView={setView}
        onReset={resetFilters}
        onRefresh={() => (setPage(1), setDateFrom((d) => d))}
        loading={loading}
      />

      {isPageFiltered && (
        <p className="text-[12px] text-mute">
          Device / track-ID filters apply to the {rows.length} records on this page only — they don&apos;t narrow
          the server query.
        </p>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">{error}</div>
      )}

      {loading ? (
        <SkeletonGrid view={view} />
      ) : visible.length === 0 ? (
        <EmptyState />
      ) : view === 'grid' ? (
        <GridView rows={visible} onOpen={setActive} />
      ) : (
        <ListView rows={visible} onOpen={setActive} />
      )}

      <Pagination
        page={page}
        totalPages={totalPages}
        total={total}
        size={size}
        onPage={setPage}
        onSize={(s) => (setSize(s), setPage(1))}
      />

      {active && <Lightbox row={active} onClose={() => setActive(null)} />}
    </div>
  );
}

// ---------- toolbar ----------

function Toolbar(props: {
  dateFrom: string;
  dateTo: string;
  onDateFrom: (v: string) => void;
  onDateTo: (v: string) => void;
  targetType: TargetType;
  onTargetType: (v: TargetType) => void;
  deviceFilter: string;
  onDeviceFilter: (v: string) => void;
  devices: Device[];
  trackFilter: string;
  onTrackFilter: (v: string) => void;
  view: 'grid' | 'list';
  onView: (v: 'grid' | 'list') => void;
  onReset: () => void;
  onRefresh: () => void;
  loading: boolean;
}) {
  const {
    dateFrom, dateTo, onDateFrom, onDateTo, targetType, onTargetType,
    deviceFilter, onDeviceFilter, devices, trackFilter, onTrackFilter,
    view, onView, onReset, onRefresh, loading,
  } = props;

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-white p-3.5">
      <Field label="From">
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => onDateFrom(e.target.value)}
          className="rounded-lg border border-line bg-white px-2.5 py-2 text-[13px] text-slate-700 outline-none transition focus:border-slate-400"
        />
      </Field>
      <Field label="To">
        <input type="date" value={dateTo} onChange={(e) => onDateTo(e.target.value)} className="rounded-lg border border-line bg-white px-2.5 py-2 text-[13px] text-slate-700 outline-none transition focus:border-slate-400" />
      </Field>
      <Field label="Target type">
        <select
          value={targetType}
          onChange={(e) => onTargetType(e.target.value as TargetType)}
          className="rounded-lg border border-line bg-white px-2.5 py-2 text-[13px] text-slate-700 outline-none transition focus:border-slate-400"
        >
          <option value="all">All types</option>
          <option value="face">Face</option>
          <option value="body">Body</option>
        </select>
      </Field>
      <Field label="Device">
        <select value={deviceFilter} onChange={(e) => onDeviceFilter(e.target.value)} className="rounded-lg border border-line bg-white px-2.5 py-2 text-[13px] text-slate-700 outline-none transition focus:border-slate-400">
          <option value="all">All devices</option>
          {devices.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Track ID">
        <input
          type="text"
          value={trackFilter}
          onChange={(e) => onTrackFilter(e.target.value)}
          placeholder="e.g. 5610081"
          className="rounded-lg border border-line bg-white px-2.5 py-2 text-[13px] text-slate-700 outline-none transition focus:border-slate-400 w-36"
        />
      </Field>

      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          onClick={onReset}
          className="rounded-lg border border-line px-3 py-2 text-[13px] font-medium text-slate-600 transition hover:bg-slate-50"
        >
          Reset
        </button>
        <button
          type="button"
          onClick={onRefresh}
          className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-[13px] font-medium text-slate-600 transition hover:bg-slate-50"
        >
          <IconRefresh className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
        <div className="flex items-center rounded-lg border border-line p-0.5">
          <button
            type="button"
            onClick={() => onView('grid')}
            aria-label="Grid view"
            className={`rounded-md p-1.5 transition ${view === 'grid' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-50'}`}
          >
            <IconGrid className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => onView('list')}
            aria-label="List view"
            className={`rounded-md p-1.5 transition ${view === 'list' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-50'}`}
          >
            <IconList className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] font-medium uppercase tracking-wide text-mute">{label}</span>
      {children}
    </label>
  );
}

// ---------- badges / shared bits ----------

function TypeBadge({ type }: { type: 'face' | 'body' }) {
  const isFace = type === 'face';
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${
        isFace ? 'bg-indigo-50 text-indigo-700' : 'bg-emerald-50 text-emerald-700'
      }`}
    >
      {isFace ? <IconFace className="h-3 w-3" /> : <IconBody className="h-3 w-3" />}
      {isFace ? 'Face' : 'Body'}
    </span>
  );
}

function Thumb({ src, alt, className }: { src?: string; alt: string; className?: string }) {
  const [errored, setErrored] = useState(false);
  if (!src || errored) {
    return (
      <div className={`flex items-center justify-center bg-slate-100 text-slate-300 ${className ?? ''}`}>
        <IconImageOff className="h-6 w-6" />
      </div>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt={alt} onError={() => setErrored(true)} className={`object-cover ${className ?? ''}`} />;
}

// ---------- grid view ----------

function GridView({ rows, onOpen }: { rows: CaptureRow[]; onOpen: (r: CaptureRow) => void }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
      {rows.map((r) => (
        <button
          key={r.id}
          type="button"
          onClick={() => onOpen(r)}
          className="group relative overflow-hidden rounded-xl border border-line bg-white text-left transition hover:-translate-y-0.5 hover:shadow-md"
        >
          <div className="relative aspect-square w-full overflow-hidden bg-slate-100">
            <Thumb
              src={r.targetImage}
              alt={`${r.targetType} capture ${r.trackId}`}
              className="h-full w-full transition duration-300 group-hover:scale-105"
            />
            <div className="absolute left-2 top-2">
              <TypeBadge type={r.targetType} />
            </div>
            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent px-2.5 pb-2 pt-6">
              <p className="truncate text-[11px] font-medium text-white">{r.device}</p>
              <p className="truncate text-[10.5px] text-white/75">{r.time}</p>
            </div>
          </div>
          <div className="flex items-center justify-between px-2.5 py-1.5">
            <span className="text-[11px] text-mute">Track</span>
            <span className="font-mono text-[11px] text-slate-700">{r.trackId}</span>
          </div>
        </button>
      ))}
    </div>
  );
}

// ---------- list view ----------

function ListView({ rows, onOpen }: { rows: CaptureRow[]; onOpen: (r: CaptureRow) => void }) {
  return (
    <div className="overflow-hidden rounded-xl border border-line bg-white">
      <table className="w-full text-left text-[13px]">
        <thead>
          <tr className="border-b border-line bg-slate-50/70 text-[11px] uppercase tracking-wide text-mute">
            <th className="px-3 py-2.5 font-medium">Capture</th>
            <th className="px-3 py-2.5 font-medium">Type</th>
            <th className="px-3 py-2.5 font-medium">Device</th>
            <th className="px-3 py-2.5 font-medium">Time</th>
            <th className="px-3 py-2.5 font-medium">Track ID</th>
            <th className="px-3 py-2.5 font-medium" />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-b border-line last:border-0 hover:bg-slate-50/60">
              <td className="px-3 py-2">
                <Thumb src={r.targetImage} alt={r.trackId} className="h-11 w-11 rounded-lg" />
              </td>
              <td className="px-3 py-2">
                <TypeBadge type={r.targetType} />
              </td>
              <td className="px-3 py-2 text-slate-700">{r.device}</td>
              <td className="px-3 py-2 text-slate-500">{r.time}</td>
              <td className="px-3 py-2 font-mono text-slate-600">{r.trackId}</td>
              <td className="px-3 py-2 text-right">
                <button
                  type="button"
                  onClick={() => onOpen(r)}
                  className="rounded-md border border-line px-2.5 py-1 text-[12px] font-medium text-slate-600 transition hover:bg-white"
                >
                  Details
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------- lightbox ----------

function Lightbox({ row, onClose }: { row: CaptureRow; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const attrs = Object.entries(row.attributes);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="flex max-h-[85vh] w-full max-w-3xl overflow-hidden rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="hidden w-2/5 shrink-0 bg-slate-100 sm:block">
          <Thumb src={row.panoramicImage ?? row.targetImage} alt="panoramic" className="h-full w-full" />
        </div>
        <div className="flex flex-1 flex-col overflow-y-auto">
          <div className="flex items-start justify-between border-b border-line px-5 py-4">
            <div>
              <div className="mb-1 flex items-center gap-2">
                <TypeBadge type={row.targetType} />
                <span className="text-[13px] font-semibold text-slate-800">Track {row.trackId}</span>
              </div>
              <p className="text-[12.5px] text-mute">
                {row.device} · {row.time}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="rounded-full p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            >
              <IconClose className="h-4 w-4" />
            </button>
          </div>

          <div className="p-5 sm:hidden">
            <Thumb src={row.targetImage} alt="target" className="h-48 w-full rounded-lg" />
          </div>

          <div className="flex-1 px-5 py-4">
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-mute">
              Attributes <span className="normal-case text-slate-400">(raw box codes — no legend yet)</span>
            </p>
            {attrs.length === 0 ? (
              <p className="text-[13px] text-mute">No attributes on this record.</p>
            ) : (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {attrs.map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between rounded-lg border border-line px-2.5 py-1.5">
                    <span className="text-[12px] text-slate-600">{humanizeKey(k)}</span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-700">{v}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------- pagination ----------

function Pagination(props: {
  page: number;
  totalPages: number;
  total: number;
  size: number;
  onPage: (p: number) => void;
  onSize: (s: number) => void;
}) {
  const { page, totalPages, total, size, onPage, onSize } = props;
  const from = total === 0 ? 0 : (page - 1) * size + 1;
  const to = Math.min(page * size, total);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-white px-4 py-3">
      <p className="text-[12.5px] text-mute">
        {total === 0 ? 'No records' : `Showing ${from}–${to} of ${total}`}
      </p>
      <div className="flex items-center gap-3">
        <select
          value={size}
          onChange={(e) => onSize(Number(e.target.value))}
          className="rounded-lg border border-line bg-white px-2.5 py-2 text-[13px] text-slate-700 outline-none transition focus:border-slate-400 py-1.5 text-[12.5px]"
        >
          {PAGE_SIZES.map((s) => (
            <option key={s} value={s}>
              {s} / page
            </option>
          ))}
        </select>
        <div className="flex items-center gap-1">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => onPage(page - 1)}
            className="rounded-md border border-line p-1.5 text-slate-500 transition hover:bg-slate-50 disabled:opacity-40"
          >
            <IconChevronLeft className="h-4 w-4" />
          </button>
          <span className="min-w-[70px] text-center text-[12.5px] text-slate-600">
            Page {page} / {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => onPage(page + 1)}
            className="rounded-md border border-line p-1.5 text-slate-500 transition hover:bg-slate-50 disabled:opacity-40"
          >
            <IconChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------- states ----------

function SkeletonGrid({ view }: { view: 'grid' | 'list' }) {
  if (view === 'list') {
    return (
      <div className="overflow-hidden rounded-xl border border-line bg-white">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 border-b border-line px-3 py-2.5 last:border-0">
            <div className="h-11 w-11 animate-pulse rounded-lg bg-slate-100" />
            <div className="h-3 w-16 animate-pulse rounded bg-slate-100" />
            <div className="h-3 w-24 animate-pulse rounded bg-slate-100" />
            <div className="h-3 w-32 animate-pulse rounded bg-slate-100" />
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
      {Array.from({ length: 12 }).map((_, i) => (
        <div key={i} className="overflow-hidden rounded-xl border border-line bg-white">
          <div className="aspect-square w-full animate-pulse bg-slate-100" />
          <div className="px-2.5 py-2">
            <div className="h-2.5 w-2/3 animate-pulse rounded bg-slate-100" />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-64 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-line bg-white text-mute">
      <IconImageOff className="h-8 w-8 text-slate-300" />
      <p className="text-[13px]">No captures match these filters.</p>
    </div>
  );
}