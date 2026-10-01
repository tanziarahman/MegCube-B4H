'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, CheckCircle2, Clock, Mail, RotateCcw, XCircle } from 'lucide-react';
import {
  EVENT_KIND_LABELS, fetchIncident, imageUrl, updateIncident, whoLabel,
  type IncidentDetail as Detail, type IncidentStatus,
} from '@/lib/alarms';
import { PATHS } from '@/lib/paths';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { BoxImage, ErrorNote, SeverityPill, StatusPill, btnCls, formatTime, inputCls, priBtnCls } from './shared';

const EMAIL_STATUS: Record<string, string> = {
  pending: 'Waiting to send', sending: 'Sending', sent: 'Sent', failed: 'Failed', cancelled: 'Cancelled',
};

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-line bg-white">
      <h3 className="border-b border-line px-4 py-2.5 text-[12.5px] font-semibold uppercase tracking-wide text-mute">{title}</h3>
      <div className="p-4">{children}</div>
    </section>
  );
}

export default function IncidentDetail({ incidentRef }: { incidentRef: string }) {
  const [incident, setIncident] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [note, setNote] = useState('');
  const [me, setMe] = useLocalStorage('alarms.ackName', '');

  const load = useCallback(async () => {
    setError(null);
    try {
      const d = await fetchIncident(incidentRef);
      setIncident(d);
      setNote(d.note ?? '');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load the alarm');
    }
  }, [incidentRef]);

  useEffect(() => { load(); }, [load]);

  const change = async (status?: IncidentStatus) => {
    if (!incident) return;
    setBusy(true);
    setActionError(null);
    try {
      await updateIncident(incident.id, { status, note, by: me.trim() || undefined });
      await load();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Could not update the alarm');
    } finally {
      setBusy(false);
    }
  };

  if (error) return <ErrorNote message={`Couldn’t load this alarm: ${error}`} onRetry={load} />;
  if (!incident) return <div className="h-64 animate-pulse rounded-xl border border-line bg-white" />;

  const panorama = incident.events.find((e) => e.panoramaPath)?.panoramaPath;
  const facts: [string, React.ReactNode][] = [
    ['Rule', incident.ruleId ? incident.ruleName : <>{incident.ruleName} <span className="text-mute">(deleted)</span></>],
    ['Camera', incident.cameraName],
    ['Who', whoLabel(incident)],
    ['Seen at', formatTime(incident.occurredAt)],
    ['Detections', `${incident.eventCount}${incident.eventCount > 1 ? `, last at ${formatTime(incident.lastEventAt)}` : ''}`],
    ['Track ID', incident.trackId ?? '—'],
  ];
  if (incident.isDelayed) facts.push(['Note', `Reported ${Math.round(incident.delaySeconds / 60)} min late`]);
  if (incident.acknowledgedAt) facts.push(['Handled by', `${incident.acknowledgedBy ?? '—'} at ${formatTime(incident.acknowledgedAt)}`]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <Link href={PATHS.alarms} className="flex items-center gap-1 text-[14px] font-medium text-pri hover:underline"><ArrowLeft size={16} /> All alarms</Link>
        <div className="ml-auto flex items-center gap-2"><SeverityPill severity={incident.severity} /><StatusPill status={incident.status} /></div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex flex-col gap-4">
          <Card title="Snapshot">
            <div className="flex flex-wrap gap-3">
              <BoxImage src={imageUrl(incident.snapshotPath)} alt="Detected person" className="h-56 w-44 rounded-lg" />
              {panorama && <BoxImage src={imageUrl(panorama)} alt="Full camera view" className="h-56 min-w-0 flex-1 rounded-lg" />}
            </div>
            <p className="mt-2 text-[12.5px] text-mute">Images are kept on the box and disappear when it overwrites old records.</p>
          </Card>

          <Card title={`Detections (${incident.events.length})`}>
            {incident.events.length === 0 ? <p className="text-[14px] text-mute">The detections have been cleaned up.</p> : (
              <table className="w-full text-left text-[14px]">
                <thead><tr className="text-[12.5px] uppercase tracking-wide text-mute">
                  <th className="pb-2 font-medium">Image</th><th className="pb-2 font-medium">Time</th>
                  <th className="pb-2 font-medium">Type</th><th className="pb-2 font-medium">Track</th><th className="pb-2 font-medium">Person</th>
                </tr></thead>
                <tbody>
                  {incident.events.map((e) => (
                    <tr key={e.id} className="border-t border-line">
                      <td className="py-2"><BoxImage src={imageUrl(e.imagePath)} alt={`Detection ${e.id}`} className="h-10 w-10 rounded-md" /></td>
                      <td className="py-2 font-mono text-[13px]">{formatTime(e.occurredAt)}</td>
                      <td className="py-2">{EVENT_KIND_LABELS[e.kind] ?? e.kind}</td>
                      <td className="py-2 font-mono text-[13px]">{e.trackId ?? '—'}</td>
                      <td className="py-2">{e.personName ?? '—'}{e.matchScore != null && e.personName ? ` (${Math.round(e.matchScore)}%)` : ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </div>

        <div className="flex flex-col gap-4">
          <Card title="Alarm">
            <dl className="space-y-2 text-[14px]">
              {facts.map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3"><dt className="text-mute">{k}</dt><dd className="text-right text-slate-800">{v}</dd></div>
              ))}
            </dl>
          </Card>

          <Card title="Handle it">
            <div className="space-y-3">
              <label className="block text-[13px] font-medium text-mute">Your name
                <input value={me} onChange={(e) => setMe(e.target.value)} placeholder="Shown as who handled it" className={`${inputCls} mt-1 w-full`} />
              </label>
              <label className="block text-[13px] font-medium text-mute">Note
                <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} maxLength={2000} className={`${inputCls} mt-1 w-full`} />
              </label>
              {actionError && <ErrorNote message={actionError} />}
              <div className="flex flex-wrap gap-2">
                {incident.status === 'open' && (
                  <button onClick={() => change('acknowledged')} disabled={busy} className={priBtnCls}><CheckCircle2 size={16} /> Acknowledge</button>
                )}
                {incident.status !== 'resolved' && (
                  <button onClick={() => change('resolved')} disabled={busy} className={btnCls}><CheckCircle2 size={16} /> Resolve</button>
                )}
                {incident.status !== 'false_alarm' && (
                  <button onClick={() => change('false_alarm')} disabled={busy} className={btnCls}><XCircle size={16} /> False alarm</button>
                )}
                {incident.status !== 'open' && (
                  <button onClick={() => change('open')} disabled={busy} className={btnCls}><RotateCcw size={16} /> Reopen</button>
                )}
                <button onClick={() => change()} disabled={busy || note === (incident.note ?? '')} className={btnCls}>Save note</button>
              </div>
            </div>
          </Card>

          <Card title="Emails">
            {incident.notifications.length === 0 ? (
              <p className="text-[14px] text-mute">{incident.isDelayed ? 'Not emailed: the alarm was reported late.' : 'Nobody was emailed for this alarm.'}</p>
            ) : (
              <ul className="space-y-2 text-[14px]">
                {incident.notifications.map((n) => (
                  <li key={n.id} className="flex items-start gap-2">
                    {n.status === 'sent' ? <Mail size={15} className="mt-0.5 text-ok" /> : n.status === 'failed' ? <XCircle size={15} className="mt-0.5 text-crit" /> : <Clock size={15} className="mt-0.5 text-warn" />}
                    <div className="min-w-0">
                      <p className="truncate text-slate-800">{n.toAddress}</p>
                      <p className="text-[12.5px] text-mute">
                        {EMAIL_STATUS[n.status] ?? n.status}{n.sentAt ? ` · ${formatTime(n.sentAt)}` : ''}{n.attempts > 1 ? ` · ${n.attempts} tries` : ''}
                      </p>
                      {n.lastError && n.status !== 'sent' && <p className="text-[12.5px] text-crit">{n.lastError}</p>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
