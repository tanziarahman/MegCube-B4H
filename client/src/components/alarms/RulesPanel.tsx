'use client';

import { useState } from 'react';
import { Mail, Pencil, Plus, ShieldAlert, Trash2 } from 'lucide-react';
import {
  DAY_NAMES, MATCH_MODE_LABELS, createRule, deleteRule, setRuleEnabled, updateRule,
  type AlarmCamera, type AlarmRule, type Contact, type RuleInput,
} from '@/lib/alarms';
import RuleFormModal, { windowsToRows } from './RuleFormModal';
import { ConfirmDialog, ErrorNote, SeverityPill, formatTime, priBtnCls } from './shared';

function dayList(days: number[]): string {
  const key = days.join(',');
  if (key === '1,2,3,4,5,6,7') return 'Every day';
  if (key === '1,2,3,4,5') return 'Mon–Fri';
  if (key === '6,7') return 'Weekends';
  return days.map((d) => DAY_NAMES[d - 1]).join(', ');
}

export function scheduleSummary(rule: AlarmRule): string {
  if (!rule.windows.length) return 'Always';
  return windowsToRows(rule.windows).map((r) => `${dayList(r.days)} ${r.start}–${r.end}`).join('; ');
}

function whoSummary(rule: AlarmRule): string {
  if (rule.matchMode !== 'targets') return MATCH_MODE_LABELS[rule.matchMode];
  const names = rule.targets.map((t) => t.label || t.value);
  return names.length <= 3 ? names.join(', ') : `${names.slice(0, 3).join(', ')} +${names.length - 3}`;
}

export default function RulesPanel({ rules, cameras, contacts, timezone, maxRecipients, onChanged }: {
  rules: AlarmRule[]; cameras: AlarmCamera[]; contacts: Contact[]; timezone: string; maxRecipients: number;
  onChanged: () => Promise<void>;
}) {
  const [form, setForm] = useState<'new' | AlarmRule | null>(null);
  const [deleting, setDeleting] = useState<AlarmRule | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const cameraName = (id: number) => cameras.find((c) => c.id === id)?.name ?? `Camera ${id}`;

  const save = async (input: RuleInput) => {
    if (form && form !== 'new') {
      await updateRule(form.id, form.version, input);
      setNotice(`Saved “${input.name}”.`);
    } else {
      await createRule(input);
      setNotice(`Created “${input.name}”.`);
    }
    await onChanged();
  };

  const toggle = async (rule: AlarmRule) => {
    setError(null);
    try {
      await setRuleEnabled(rule.id, !rule.isEnabled);
      await onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not change the rule');
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[14px] text-mute">Rules are checked against every detection from the box, a few seconds after it happens.</p>
        <button onClick={() => setForm('new')} className={priBtnCls}><Plus size={16} /> New rule</button>
      </div>

      {notice && (
        <div className="flex items-center justify-between rounded-lg border border-[#BFE3CC] bg-ok-bg px-4 py-3 text-[14px] text-ok">
          <span>{notice}</span>
          <button onClick={() => setNotice(null)} className="font-medium hover:underline">Dismiss</button>
        </div>
      )}
      {error && <ErrorNote message={error} />}

      {rules.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-line bg-white py-12 text-[14.5px] text-mute">
          <ShieldAlert size={24} className="text-slate-300" />
          No rules yet. Create one, e.g. “anyone on D3 between 22:00 and 06:00”.
        </div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {rules.map((rule) => (
            <div key={rule.id} className={`rounded-xl border border-line bg-white p-4 ${rule.isEnabled ? '' : 'opacity-70'}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-[16px] font-semibold text-slate-800">{rule.name}</p>
                  {rule.description && <p className="truncate text-[13px] text-mute">{rule.description}</p>}
                </div>
                <label className="flex shrink-0 cursor-pointer items-center gap-2 text-[13px] text-mute">
                  {rule.isEnabled ? 'On' : 'Off'}
                  <input type="checkbox" role="switch" aria-label={`${rule.name} on`} checked={rule.isEnabled}
                    onChange={() => toggle(rule)} className="h-4 w-4 accent-pri" />
                </label>
              </div>
              <dl className="mt-3 space-y-1.5 text-[14px]">
                <div className="flex gap-3"><dt className="w-20 shrink-0 text-mute">Cameras</dt><dd className="text-slate-700">{rule.cameraIds.map(cameraName).join(', ')}</dd></div>
                <div className="flex gap-3"><dt className="w-20 shrink-0 text-mute">Who</dt><dd className="text-slate-700">{whoSummary(rule)}</dd></div>
                <div className="flex gap-3"><dt className="w-20 shrink-0 text-mute">When</dt><dd className="text-slate-700">{scheduleSummary(rule)}</dd></div>
                <div className="flex gap-3"><dt className="w-20 shrink-0 text-mute">Last alarm</dt><dd className="text-slate-700">{rule.lastFiredAt ? formatTime(rule.lastFiredAt) : 'Never'}</dd></div>
              </dl>
              <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
                <SeverityPill severity={rule.severity} />
                <span className="flex items-center gap-1 rounded-md bg-ground px-2 py-0.5 text-[12.5px] text-slate-600">
                  <Mail size={13} /> {rule.recipientIds.length || 'No'} recipient{rule.recipientIds.length === 1 ? '' : 's'}
                </span>
                <div className="ml-auto flex gap-1">
                  <button onClick={() => setForm(rule)} className="flex h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-xs font-medium hover:bg-ground">
                    <Pencil size={14} /> Edit
                  </button>
                  <button onClick={() => setDeleting(rule)} aria-label={`Delete ${rule.name}`} className="flex h-8 w-8 items-center justify-center rounded-md text-crit hover:bg-crit-bg">
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {form && (
        <RuleFormModal rule={form === 'new' ? null : form} cameras={cameras} contacts={contacts} timezone={timezone}
          maxRecipients={maxRecipients} onClose={() => setForm(null)} onSubmit={save} />
      )}
      {deleting && (
        <ConfirmDialog title={`Delete “${deleting.name}”?`} confirmLabel="Delete rule"
          message="No new alarms will be raised by this rule. Alarms it already raised are kept."
          onCancel={() => setDeleting(null)}
          onConfirm={async () => { await deleteRule(deleting.id); setNotice(`Deleted “${deleting.name}”.`); await onChanged(); }} />
      )}
    </div>
  );
}
