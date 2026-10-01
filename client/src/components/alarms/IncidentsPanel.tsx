'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { BellOff, Check, RefreshCw } from 'lucide-react';
import {
  STATUS_LABELS, fetchIncidents, imageUrl, updateIncident, whoLabel,
  type AlarmCamera, type AlarmRule, type Incident, type IncidentStatus,
} from '@/lib/alarms';
import { PATHS } from '@/lib/paths';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { BoxImage, ErrorNote, Field, SeverityPill, StatusPill, btnCls, formatTime, inputCls } from './shared';

const PAGE_SIZE = 20;
const REFRESH_MS = 30_000;

export default function IncidentsPanel({ rules, cameras, onChanged }: {
  rules: AlarmRule[]; cameras: AlarmCamera[]; onChanged: () => void;
}) {
  const [status, setStatus] = useState<IncidentStatus | ''>('open');
  const [ruleId, setRuleId] = useState<number | ''>('');
  const [cameraId, setCameraId] = useState<number | ''>('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<Incident[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [me] = useLocalStorage('alarms.ackName', '');

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    setError(null);
    try {
      const result = await fetchIncidents({ status, ruleId, cameraId, from, to, page, size: PAGE_SIZE });
      setItems(result.items);
      setTotal(result.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load alarms');
    } finally {
      setLoading(false);
    }
  }, [status, ruleId, cameraId, from, to, page]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const timer = setInterval(() => load(true), REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  const changeFilter = <T,>(set: (v: T) => void) => (v: T) => { set(v); setPage(1); };
  const filtered = status !== 'open' || ruleId !== '' || cameraId !== '' || from || to;
  const reset = () => { setStatus('open'); setRuleId(''); setCameraId(''); setFrom(''); setTo(''); setPage(1); };

  const acknowledge = async (incident: Incident) => {
    try {
      await updateIncident(incident.id, { status: 'acknowledged', by: me || undefined });
      await load(true);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not acknowledge the alarm');
    }
  };

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-white p-3.5">
        <Field label="Status">
          <select aria-label="Status" value={status} onChange={(e) => changeFilter(setStatus)(e.target.value as IncidentStatus | '')} className={`${inputCls} w-40`}>
            <option value="">All</option>
            {(Object.keys(STATUS_LABELS) as IncidentStatus[]).map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
          </select>
        </Field>
        <Field label="Rule">
          <select aria-label="Rule" value={ruleId} onChange={(e) => changeFilter(setRuleId)(e.target.value ? Number(e.target.value) : '')} className={`${inputCls} w-48`}>
            <option value="">All rules</option>
            {rules.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
        </Field>
        <Field label="Camera">
          <select aria-label="Camera" value={cameraId} onChange={(e) => changeFilter(setCameraId)(e.target.value ? Number(e.target.value) : '')} className={`${inputCls} w-44`}>
            <option value="">All cameras</option>
            {cameras.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </Field>
        <Field label="From">
          <input type="date" aria-label="From" value={from} onChange={(e) => changeFilter(setFrom)(e.target.value)} className={inputCls} />
        </Field>
        <Field label="To">
          <input type="date" aria-label="To" value={to} onChange={(e) => changeFilter(setTo)(e.target.value)} className={inputCls} />
        </Field>
        <div className="ml-auto flex items-center gap-2">
          {filtered && <button onClick={reset} className={btnCls}>Reset</button>}
          <button onClick={() => load()} disabled={loading} className={btnCls}>
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {error ? (
        <ErrorNote message={`Couldn’t load alarms: ${error}`} onRetry={() => load()} />
      ) : loading && items.length === 0 ? (
        <div className="space-y-2">{[0, 1, 2].map((i) => <div key={i} className="h-16 animate-pulse rounded-xl border border-line bg-white" />)}</div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-line bg-white py-12 text-[14.5px] text-mute">
          <BellOff size={24} className="text-slate-300" />
          {status === 'open' && !filtered ? 'No open alarms. All quiet.' : 'No alarms match these filters.'}
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-line bg-white">
          <table className="w-full text-left text-[14.5px]">
            <thead>
              <tr className="border-b border-line bg-slate-50/70 text-[12.5px] uppercase tracking-wide text-mute">
                <th className="px-4 py-2.5 font-medium">Snapshot</th>
                <th className="px-4 py-2.5 font-medium">Time</th>
                <th className="px-4 py-2.5 font-medium">Rule</th>
                <th className="px-4 py-2.5 font-medium">Camera</th>
                <th className="px-4 py-2.5 font-medium">Who</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id} className="border-b border-line last:border-0 hover:bg-slate-50/60">
                  <td className="px-4 py-2.5">
                    <BoxImage src={imageUrl(i.snapshotPath)} alt={`Alarm ${i.id}`} className="h-12 w-12 rounded-lg" />
                  </td>
                  <td className="px-4 py-2.5">
                    <p className="font-mono text-[13.5px] text-slate-700">{formatTime(i.occurredAt)}</p>
                    {i.isDelayed && <p className="text-[12.5px] text-warn">Reported {Math.round(i.delaySeconds / 60)} min late</p>}
                  </td>
                  <td className="px-4 py-2.5">
                    <Link href={PATHS.alarmDetail(String(i.id))} className="font-medium text-slate-800 hover:text-pri hover:underline">{i.ruleName}</Link>
                    <div className="mt-0.5"><SeverityPill severity={i.severity} /></div>
                  </td>
                  <td className="px-4 py-2.5 text-slate-700">{i.cameraName}</td>
                  <td className="px-4 py-2.5">
                    <p className="text-slate-700">{whoLabel(i)}</p>
                    {i.eventCount > 1 && <p className="text-[12.5px] text-mute">{i.eventCount} detections</p>}
                  </td>
                  <td className="px-4 py-2.5"><StatusPill status={i.status} /></td>
                  <td className="px-4 py-2.5">
                    <div className="flex justify-end gap-1">
                      {i.status === 'open' && (
                        <button onClick={() => acknowledge(i)} aria-label={`Acknowledge alarm ${i.id}`}
                          className="flex h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-xs font-medium hover:bg-ground">
                          <Check size={14} /> Acknowledge
                        </button>
                      )}
                      <Link href={PATHS.alarmDetail(String(i.id))} className="flex h-8 items-center rounded-md px-2.5 text-xs font-medium text-pri hover:bg-pri-bg">
                        Details
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!error && total > 0 && (
        <div className="flex items-center justify-between text-[13.5px] text-mute">
          <span>{total} alarm{total === 1 ? '' : 's'}</span>
          {pages > 1 && (
            <div className="flex items-center gap-2">
              <button onClick={() => setPage((p) => p - 1)} disabled={page <= 1} className={btnCls}>Previous</button>
              <span>Page {page} of {pages}</span>
              <button onClick={() => setPage((p) => p + 1)} disabled={page >= pages} className={btnCls}>Next</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
