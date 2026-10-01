'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Database, MailWarning } from 'lucide-react';
import {
  fetchAlarmCameras, fetchAlarmStatus, fetchContacts, fetchRules,
  type AlarmCamera, type AlarmRule, type AlarmStatus, type Contact,
} from '@/lib/alarms';
import IncidentsPanel from './IncidentsPanel';
import RecipientsPanel from './RecipientsPanel';
import RulesPanel from './RulesPanel';
import { ErrorNote } from './shared';

type Tab = 'incidents' | 'rules' | 'recipients';

function HealthBanner({ status }: { status: AlarmStatus }) {
  const notes: { icon: React.ReactNode; text: string; tone: 'warn' | 'crit' }[] = [];
  if (status.ingestError) {
    notes.push({ icon: <AlertTriangle size={16} />, tone: 'crit',
      text: `The portal can’t read new detections from the box right now (${status.ingestError}). Alarms resume when it reconnects.` });
  }
  if (!status.smtpConfigured) {
    notes.push({ icon: <MailWarning size={16} />, tone: 'warn',
      text: `Email isn’t set up, so alarms are recorded but not emailed${status.pendingEmails ? ` (${status.pendingEmails} waiting)` : ''}. See the Recipients tab.` });
  } else if (status.failedEmails) {
    notes.push({ icon: <MailWarning size={16} />, tone: 'warn',
      text: `${status.failedEmails} alarm email${status.failedEmails === 1 ? '' : 's'} could not be delivered. Open an alarm to see why.` });
  }
  if (!notes.length) return null;
  return (
    <div className="space-y-2">
      {notes.map((n) => (
        <div key={n.text} className={`flex items-start gap-2 rounded-lg border px-4 py-3 text-[14px] ${
          n.tone === 'crit' ? 'border-red-200 bg-red-50 text-red-700' : 'border-[#F1D9A6] bg-warn-bg text-warn'}`}>
          <span className="mt-0.5 shrink-0">{n.icon}</span>{n.text}
        </div>
      ))}
    </div>
  );
}

export default function AlarmsView() {
  const [tab, setTab] = useState<Tab>('incidents');
  const [status, setStatus] = useState<AlarmStatus | null>(null);
  const [rules, setRules] = useState<AlarmRule[]>([]);
  const [cameras, setCameras] = useState<AlarmCamera[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await fetchAlarmStatus());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reach the backend');
    }
  }, []);

  const loadSetup = useCallback(async () => {
    setError(null);
    try {
      const [r, c, p] = await Promise.all([fetchRules(), fetchAlarmCameras(), fetchContacts()]);
      setRules(r);
      setCameras(c);
      setContacts(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load alarm settings');
    }
  }, []);

  useEffect(() => { refreshStatus(); }, [refreshStatus]);
  useEffect(() => { if (status?.database) loadSetup(); }, [status?.database, loadSetup]);

  const reloadAll = useCallback(async () => { await Promise.all([loadSetup(), refreshStatus()]); }, [loadSetup, refreshStatus]);

  if (status && !status.database) {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-line bg-white p-5 text-[14.5px] text-slate-700">
        <Database size={22} className="mt-0.5 shrink-0 text-pri" />
        <div>
          <p className="font-semibold text-slate-800">Alarms need the portal database</p>
          <p className="mt-1 text-mute">
            Set <code className="rounded bg-ground px-1">DATABASE_URL</code> in <code className="rounded bg-ground px-1">fastapi-app/.env</code> to your
            Neon connection string, run <code className="rounded bg-ground px-1">uv run alembic upgrade head</code>, then restart the backend.
          </p>
        </div>
      </div>
    );
  }

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: 'incidents', label: 'Alarms', count: status?.openIncidents || undefined },
    { id: 'rules', label: 'Rules', count: rules.length || undefined },
    { id: 'recipients', label: 'Recipients', count: contacts.length || undefined },
  ];

  return (
    <div className="flex flex-col gap-4">
      {status && <HealthBanner status={status} />}
      {error && <ErrorNote message={error} onRetry={reloadAll} />}

      <div role="tablist" className="flex gap-1 border-b border-line">
        {tabs.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
            className={`-mb-px flex items-center gap-2 border-b-2 px-3.5 py-2.5 text-[14.5px] font-medium transition ${
              tab === t.id ? 'border-pri text-pri' : 'border-transparent text-mute hover:text-slate-700'}`}>
            {t.label}
            {t.count !== undefined && (
              <span className={`rounded-full px-1.5 text-[12px] ${t.id === 'incidents' ? 'bg-crit text-white' : 'bg-ground text-slate-600'}`}>{t.count}</span>
            )}
          </button>
        ))}
      </div>

      {!status ? (
        <div className="h-40 animate-pulse rounded-xl border border-line bg-white" />
      ) : tab === 'incidents' ? (
        <IncidentsPanel rules={rules} cameras={cameras} onChanged={refreshStatus} />
      ) : tab === 'rules' ? (
        <RulesPanel rules={rules} cameras={cameras} contacts={contacts} timezone={status.timezone}
          maxRecipients={status.maxRecipients} onChanged={reloadAll} />
      ) : (
        <RecipientsPanel contacts={contacts} smtpConfigured={status.smtpConfigured} smtpSender={status.smtpSender} onChanged={reloadAll} />
      )}
    </div>
  );
}
