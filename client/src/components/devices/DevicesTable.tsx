'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { LayoutGrid, List, RefreshCw, Video, Wifi, WifiOff } from 'lucide-react';
import { fetchDeviceDetails, type DeviceDetail } from '@/lib/devices';

const inputCls =
  'rounded-lg border border-line bg-white px-3 py-2.5 text-[14.5px] text-slate-700 outline-none transition focus:border-slate-400';

/** rtsp://user:****@192.168.90.24:554/ISAPI/Streaming/channels/201 -> host "192.168.90.24:554", path "/ISAPI/…/201" */
function splitAddress(address: string): { host: string; path: string } {
  try {
    const u = new URL(address.replace(/^rtsp:/i, 'http:'));   // URL() doesn't parse rtsp:, http: has the same shape
    return { host: u.port ? `${u.hostname}:${u.port}` : u.hostname, path: u.pathname };
  } catch {
    return { host: address || '—', path: '' };
  }
}

// ---------- small pieces ----------

function StatusPill({ d }: { d: DeviceDetail }) {
  return d.online ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-ok-bg px-2 py-0.5 text-[12.5px] font-medium text-ok">
      <span className="h-1.5 w-1.5 rounded-full bg-ok" /> Online
    </span>
  ) : (
    <span
      className="inline-flex items-center gap-1.5 rounded-full bg-crit-bg px-2 py-0.5 text-[12.5px] font-medium text-crit"
      title={d.stateCode != null ? `Box state code ${d.stateCode}` : undefined}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-crit" /> Offline
    </span>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: 'ok' | 'crit' }) {
  const color = tone === 'ok' ? 'text-ok' : tone === 'crit' ? 'text-crit' : 'text-slate-800';
  return (
    <div className="rounded-xl border border-line bg-white px-4 py-3.5">
      <p className="text-[12.5px] font-medium uppercase tracking-wide text-mute">{label}</p>
      <p className={`mt-1 text-[28px] font-semibold leading-none ${color}`}>{value}</p>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[12.5px] font-medium uppercase tracking-wide text-mute">{label}</span>
      {children}
    </label>
  );
}

// Edit / Delete need the box's own requests for changing and removing a camera (not captured yet),
// so they stay disabled until those are wired in. Styles match the Recognition page's buttons.
const ACTIONS_READY = false;
const NOT_READY_HINT = 'Not available yet: needs the box\'s edit/delete request';

function DeviceActions({ d }: { d: DeviceDetail }) {
  return (
    <div className="flex items-center gap-2 whitespace-nowrap">
      <button
        disabled={!ACTIONS_READY}
        title={ACTIONS_READY ? `Edit ${d.name}` : NOT_READY_HINT}
        className="h-8 rounded-md border border-line bg-white px-3.5 text-[13.5px] font-medium hover:bg-ground disabled:cursor-not-allowed disabled:opacity-40"
      >
        Edit
      </button>
      <button
        disabled={!ACTIONS_READY}
        title={ACTIONS_READY ? `Delete ${d.name}` : NOT_READY_HINT}
        className="h-8 rounded-md border border-[#F3C1C1] bg-white px-3.5 text-[13.5px] font-medium text-crit hover:bg-[#FDECEC] disabled:cursor-not-allowed disabled:opacity-40"
      >
        Delete
      </button>
    </div>
  );
}

// ---------- views ----------

function DeviceCard({ d }: { d: DeviceDetail }) {
  const { host, path } = splitAddress(d.address);
  return (
    <div className="rounded-xl border border-line bg-white p-4 transition hover:shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-lg ${d.online ? 'bg-pri-bg text-pri' : 'bg-slate-100 text-slate-400'}`}>
            <Video size={22} />
          </div>
          <div className="min-w-0">
            <p className="truncate text-[16px] font-semibold text-slate-800">{d.name}</p>
            <p className="text-[13px] text-mute">Device #{d.id}</p>
          </div>
        </div>
        <StatusPill d={d} />
      </div>

      <dl className="mt-4 space-y-2 text-[14px]">
        <div className="flex justify-between gap-3">
          <dt className="text-mute">Host</dt>
          <dd className="truncate font-mono text-slate-700">{host}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-mute">Stream</dt>
          <dd className="truncate font-mono text-slate-700" title={d.address}>{path || '—'}</dd>
        </div>
      </dl>

      <div className="mt-4 flex flex-wrap items-center gap-1.5 border-t border-line pt-3">
        <span className="rounded-md bg-ground px-2 py-0.5 text-[12.5px] text-slate-600">{d.type}</span>
        <span className="rounded-md bg-ground px-2 py-0.5 text-[12.5px] uppercase text-slate-600">{d.protocol}</span>
        {d.online && (
          <span className={`rounded-md px-2 py-0.5 text-[12.5px] ${d.pullingStream ? 'bg-ok-bg text-ok' : 'bg-warn-bg text-warn'}`}>
            {d.pullingStream ? 'Streaming' : 'Not streaming'}
          </span>
        )}
        <div className="ml-auto"><DeviceActions d={d} /></div>
      </div>
    </div>
  );
}

function DeviceList({ rows }: { rows: DeviceDetail[] }) {
  return (
    <div className="overflow-hidden rounded-xl border border-line bg-white">
      <table className="w-full text-left text-[14.5px]">
        <thead>
          <tr className="border-b border-line bg-slate-50/70 text-[12.5px] uppercase tracking-wide text-mute">
            <th className="px-4 py-2.5 font-medium">Device</th>
            <th className="px-4 py-2.5 font-medium">Type</th>
            <th className="px-4 py-2.5 font-medium">Protocol</th>
            <th className="px-4 py-2.5 font-medium">Host</th>
            <th className="px-4 py-2.5 font-medium">Stream</th>
            <th className="px-4 py-2.5 font-medium">Status</th>
            <th className="px-4 py-2.5 font-medium"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((d) => {
            const { host, path } = splitAddress(d.address);
            return (
              <tr key={d.id} className="border-b border-line last:border-0 hover:bg-slate-50/60">
                <td className="px-4 py-3.5">
                  <p className="font-medium text-slate-800">{d.name}</p>
                  <p className="text-[13px] text-mute">#{d.id}</p>
                </td>
                <td className="px-4 py-3.5 text-slate-700">{d.type}</td>
                <td className="px-4 py-3.5 text-[13.5px] uppercase text-slate-600">{d.protocol}</td>
                <td className="px-4 py-3.5 font-mono text-[13.5px] text-slate-700">{host}</td>
                <td className="max-w-[320px] truncate px-4 py-3.5 font-mono text-[13.5px] text-slate-500" title={d.address}>{path || '—'}</td>
                <td className="px-4 py-3.5"><StatusPill d={d} /></td>
                <td className="px-4 py-3.5"><div className="flex justify-end"><DeviceActions d={d} /></div></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------- page ----------

export default function DevicesTable() {
  const [devices, setDevices] = useState<DeviceDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<'grid' | 'list'>('list');

  // filters apply as you type (the box only has a handful of cameras)
  const [name, setName] = useState('');
  const [status, setStatus] = useState<'' | 'online' | 'offline'>('');
  const [address, setAddress] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDevices(await fetchDeviceDetails());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load devices');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const visible = useMemo(() => devices.filter((d) =>
    (!name || d.name.toLowerCase().includes(name.toLowerCase())) &&
    (!status || (status === 'online') === d.online) &&
    (!address || d.address.toLowerCase().includes(address.toLowerCase())),
  ), [devices, name, status, address]);

  const online = devices.filter((d) => d.online).length;
  const filtered = !!(name || status || address);
  const reset = () => { setName(''); setStatus(''); setAddress(''); };

  return (
    <div className="flex flex-col gap-4">
      {/* Summary */}
      <div className="grid grid-cols-3 gap-3 sm:max-w-lg">
        <Stat label="Cameras" value={devices.length} />
        <Stat label="Online" value={online} tone="ok" />
        <Stat label="Offline" value={devices.length - online} tone={devices.length - online ? 'crit' : undefined} />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-white p-3.5">
        <Field label="Device name">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Hikvision" className={`${inputCls} w-44`} />
        </Field>
        <Field label="Status">
          <select value={status} onChange={(e) => setStatus(e.target.value as typeof status)} className={`${inputCls} w-32`}>
            <option value="">All</option>
            <option value="online">Online</option>
            <option value="offline">Offline</option>
          </select>
        </Field>
        <Field label="Address">
          <input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="e.g. 192.168.90.24" className={`${inputCls} w-52`} />
        </Field>

        <div className="ml-auto flex items-center gap-2">
          {filtered && (
            <button onClick={reset} className="rounded-lg border border-line px-3 py-2 text-[14.5px] font-medium text-slate-600 transition hover:bg-slate-50">
              Reset
            </button>
          )}
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-[14.5px] font-medium text-slate-600 transition hover:bg-slate-50 disabled:opacity-50"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
          <div className="flex items-center rounded-lg border border-line p-0.5">
            <button
              onClick={() => setView('grid')}
              aria-label="Grid view"
              className={`rounded-md p-1.5 transition ${view === 'grid' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-50'}`}
            >
              <LayoutGrid size={18} />
            </button>
            <button
              onClick={() => setView('list')}
              aria-label="List view"
              className={`rounded-md p-1.5 transition ${view === 'list' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-50'}`}
            >
              <List size={18} />
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      {error ? (
        <div className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-4 py-3.5 text-[14.5px] text-red-700">
          <span className="flex items-center gap-2"><WifiOff size={17} /> Couldn’t load devices: {error}</span>
          <button onClick={load} className="font-medium hover:underline">Try again</button>
        </div>
      ) : loading && devices.length === 0 ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((i) => <div key={i} className="h-44 animate-pulse rounded-xl border border-line bg-white" />)}
        </div>
      ) : visible.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-line bg-white py-12 text-[14.5px] text-mute">
          <Wifi size={24} className="text-slate-300" />
          {devices.length ? 'No cameras match these filters.' : 'No cameras are configured on the box.'}
        </div>
      ) : view === 'grid' ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((d) => <DeviceCard key={d.id} d={d} />)}
        </div>
      ) : (
        <DeviceList rows={visible} />
      )}

      {filtered && !error && (
        <p className="text-[13.5px] text-mute">Showing {visible.length} of {devices.length} cameras</p>
      )}
    </div>
  );
}