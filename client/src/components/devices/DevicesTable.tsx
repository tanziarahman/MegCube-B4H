'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshCw, RotateCcw, Search } from 'lucide-react';
import { fetchDeviceDetails, type DeviceDetail } from '@/lib/devices';

const inputCls = 'h-9 rounded-md border border-line bg-white px-2.5 text-[13px] outline-none focus:border-pri';

function StatusBadge({ d }: { d: DeviceDetail }) {
  return d.online ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-[#E8F7EE] px-2 py-0.5 text-[12px] font-medium text-[#1A7F45]">
      <span className="h-1.5 w-1.5 rounded-full bg-[#1FA35A]" /> Online
    </span>
  ) : (
    <span
      className="inline-flex items-center gap-1.5 rounded-full bg-[#FDECEC] px-2 py-0.5 text-[12px] font-medium text-crit"
      title={d.stateCode != null ? `Box state code ${d.stateCode}` : undefined}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-crit" /> Offline
    </span>
  );
}

export default function DevicesTable() {
  const [devices, setDevices] = useState<DeviceDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // filter inputs, applied when Search is pressed
  const [name, setName] = useState('');
  const [type, setType] = useState('');
  const [address, setAddress] = useState('');
  const [applied, setApplied] = useState({ name: '', type: '', address: '' });

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

  const types = useMemo(() => Array.from(new Set(devices.map((d) => d.type))).filter(Boolean), [devices]);

  // the box only has a handful of cameras, so filtering happens here
  const visible = devices.filter((d) =>
    (!applied.name || d.name.toLowerCase().includes(applied.name.toLowerCase())) &&
    (!applied.type || d.type === applied.type) &&
    (!applied.address || d.address.toLowerCase().includes(applied.address.toLowerCase())),
  );
  const onlineCount = devices.filter((d) => d.online).length;

  const reset = () => {
    setName(''); setType(''); setAddress('');
    setApplied({ name: '', type: '', address: '' });
  };

  return (
    <div className="rounded-lg border border-line bg-white">
      {/* Filters */}
      <form
        onSubmit={(e) => { e.preventDefault(); setApplied({ name, type, address }); }}
        className="flex flex-wrap items-end gap-3 border-b border-line p-4"
      >
        <label className="text-[12px] font-medium text-mute">
          Device name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Hikvision" className={`${inputCls} mt-1 block w-44`} />
        </label>
        <label className="text-[12px] font-medium text-mute">
          Device type
          <select value={type} onChange={(e) => setType(e.target.value)} className={`${inputCls} mt-1 block w-36`}>
            <option value="">All</option>
            {types.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label className="text-[12px] font-medium text-mute">
          Device address
          <input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="e.g. 192.168.90.24" className={`${inputCls} mt-1 block w-56`} />
        </label>
        <div className="ml-auto flex gap-2">
          <button type="submit" className="flex h-9 items-center gap-1.5 rounded-md bg-pri px-4 text-[13px] font-medium text-white hover:bg-[#1A43A0]">
            <Search size={15} /> Search
          </button>
          <button type="button" onClick={reset} className="flex h-9 items-center gap-1.5 rounded-md border border-line px-4 text-[13px] hover:bg-ground">
            <RotateCcw size={15} /> Reset
          </button>
          <button type="button" onClick={load} disabled={loading} className="flex h-9 items-center gap-1.5 rounded-md border border-line px-4 text-[13px] hover:bg-ground disabled:opacity-50">
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </form>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead className="bg-[#F7F8FA] text-left text-[12px] text-mute">
            <tr>
              <th className="px-4 py-2.5 font-medium">Device ID</th>
              <th className="px-4 py-2.5 font-medium">Device name</th>
              <th className="px-4 py-2.5 font-medium">Device type</th>
              <th className="px-4 py-2.5 font-medium">Protocol</th>
              <th className="px-4 py-2.5 font-medium">Device address</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {loading && devices.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-mute">Loading…</td></tr>
            )}
            {!loading && error && (
              <tr><td colSpan={6} className="px-4 py-10 text-center">
                <p className="text-crit">Couldn’t load devices: {error}</p>
                <button onClick={load} className="mt-2 text-pri hover:underline">Try again</button>
              </td></tr>
            )}
            {!error && !loading && visible.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-mute">
                {devices.length ? 'No devices match these filters.' : 'No devices configured on the box.'}
              </td></tr>
            )}
            {!error && visible.map((d) => (
              <tr key={d.id} className="border-t border-line align-middle">
                <td className="px-4 py-3 font-mono">{d.id}</td>
                <td className="px-4 py-3 font-medium">{d.name}</td>
                <td className="px-4 py-3">{d.type}</td>
                <td className="px-4 py-3 uppercase text-[12px] tracking-wide">{d.protocol}</td>
                <td className="max-w-[420px] truncate px-4 py-3 font-mono text-[12px]" title={d.address}>{d.address || '—'}</td>
                <td className="px-4 py-3"><StatusBadge d={d} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="border-t border-line px-4 py-3 text-[13px] text-mute">
        {devices.length} devices · {onlineCount} online
        {visible.length !== devices.length && ` · showing ${visible.length}`}
      </div>
    </div>
  );
}
