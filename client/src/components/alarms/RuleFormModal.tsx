'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Moon, Plus, Trash2 } from 'lucide-react';
import {
  DAY_NAMES, EVENT_KIND_LABELS, MATCH_MODE_LABELS,
  type AlarmCamera, type AlarmRule, type Contact, type DedupeScope, type EventKind, type MatchMode,
  type RuleInput, type RuleTarget, type RuleWindow, type Severity,
} from '@/lib/alarms';
import { fetchPersonnelGroups, type PersonnelGroup } from '@/lib/personnel';
import { fetchPeople, type Person } from '@/lib/recognition';
import { Dialog, ErrorNote, btnCls, inputCls, priBtnCls } from './shared';

/** One schedule line in the form: the same hours on several days. The backend stores one window per day. */
interface ScheduleRow { days: number[]; start: string; end: string }

export function windowsToRows(windows: RuleWindow[]): ScheduleRow[] {
  const byHours = new Map<string, ScheduleRow>();
  for (const w of windows) {
    const key = `${w.start}-${w.end}`;
    const row = byHours.get(key) ?? { days: [], start: w.start, end: w.end };
    row.days.push(w.isoDow);
    byHours.set(key, row);
  }
  return [...byHours.values()].map((r) => ({ ...r, days: [...r.days].sort() }));
}

export function rowsToWindows(rows: ScheduleRow[]): RuleWindow[] {
  return rows.flatMap((r) => r.days.map((d) => ({ isoDow: d, start: r.start, end: r.end })));
}

const ALL_DAYS = [1, 2, 3, 4, 5, 6, 7];
const DEFAULT_KINDS: Record<MatchMode, EventKind[]> = {
  anyone: ['stranger', 'matched'],
  strangers: ['stranger'],
  known: ['matched'],
  targets: ['matched'],
};
/** Which event kinds make sense for each "who" choice. */
const ALLOWED_KINDS: Record<MatchMode, EventKind[]> = {
  anyone: ['stranger', 'matched', 'face_capture', 'body_capture'],
  strangers: ['stranger'],
  known: ['matched'],
  targets: ['matched'],
};

const label = 'text-[13px] font-medium text-mute';
const section = 'space-y-3 border-b border-line px-6 py-4 last:border-0';

function Check({ checked, onChange, children, disabled }: {
  checked: boolean; onChange: (v: boolean) => void; children: React.ReactNode; disabled?: boolean;
}) {
  return (
    <label className={`flex items-center gap-2 text-[14px] ${disabled ? 'text-mute' : 'text-slate-700'}`}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4 accent-pri" />
      {children}
    </label>
  );
}

const toggle = <T,>(list: T[], value: T, on: boolean) => (on ? [...new Set([...list, value])] : list.filter((v) => v !== value));

export default function RuleFormModal({ rule, cameras, contacts, timezone, maxRecipients, onClose, onSubmit }: {
  rule: AlarmRule | null;                  // null = new rule
  cameras: AlarmCamera[];
  contacts: Contact[];
  timezone: string;
  maxRecipients: number;
  onClose: () => void;
  onSubmit: (input: RuleInput) => Promise<void>;
}) {
  const [name, setName] = useState(rule?.name ?? '');
  const [description, setDescription] = useState(rule?.description ?? '');
  const [isEnabled, setIsEnabled] = useState(rule?.isEnabled ?? true);
  const [severity, setSeverity] = useState<Severity>(rule?.severity ?? 'warning');
  const [cameraIds, setCameraIds] = useState<number[]>(rule?.cameraIds ?? []);
  const [matchMode, setMatchMode] = useState<MatchMode>(rule?.matchMode ?? 'anyone');
  const [eventKinds, setEventKinds] = useState<EventKind[]>(rule?.eventKinds ?? DEFAULT_KINDS.anyone);
  const [targets, setTargets] = useState<RuleTarget[]>(rule?.targets ?? []);
  const [always, setAlways] = useState(rule ? rule.windows.length === 0 : false);
  const [rows, setRows] = useState<ScheduleRow[]>(
    rule?.windows.length ? windowsToRows(rule.windows) : [{ days: ALL_DAYS, start: '22:00', end: '06:00' }],
  );
  const [cooldownMin, setCooldownMin] = useState(String(Math.round((rule?.cooldownSeconds ?? 300) / 60)));
  const [dedupeScope, setDedupeScope] = useState<DedupeScope>(rule?.dedupeScope ?? 'camera');
  const [minScore, setMinScore] = useState(rule?.minMatchScore != null ? String(rule.minMatchScore) : '');
  const [minLiveness, setMinLiveness] = useState(rule?.minLiveness != null ? String(rule.minLiveness) : '');
  const [maxDelayMin, setMaxDelayMin] = useState(String(Math.round((rule?.maxDelaySeconds ?? 300) / 60)));
  const [emailDelayed, setEmailDelayed] = useState(rule?.emailDelayed ?? false);
  const [attachSnapshot, setAttachSnapshot] = useState(rule?.attachSnapshot ?? true);
  const [recipientIds, setRecipientIds] = useState<number[]>(rule?.recipientIds ?? []);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // People and groups come from the box; only needed for "specific people or groups".
  const [people, setPeople] = useState<Person[] | null>(null);
  const [groups, setGroups] = useState<PersonnelGroup[] | null>(null);
  const [libraryError, setLibraryError] = useState<string | null>(null);
  const [personSearch, setPersonSearch] = useState('');
  useEffect(() => {
    if (matchMode !== 'targets' || people) return;
    Promise.all([fetchPeople(), fetchPersonnelGroups()])
      .then(([p, g]) => { setPeople(p); setGroups(g); })
      .catch((e) => setLibraryError(e instanceof Error ? e.message : 'Could not load the face library'));
  }, [matchMode, people]);

  const changeMatchMode = (mode: MatchMode) => {
    setMatchMode(mode);
    setEventKinds(DEFAULT_KINDS[mode]);
  };
  const isTarget = (type: RuleTarget['type'], value: string) => targets.some((t) => t.type === type && t.value === value);
  const setTarget = (type: RuleTarget['type'], value: string, targetLabel: string, on: boolean) =>
    setTargets((list) => on ? [...list.filter((t) => !(t.type === type && t.value === value)), { type, value, label: targetLabel }]
      : list.filter((t) => !(t.type === type && t.value === value)));

  const shownPeople = useMemo(() => (people ?? [])
    .filter((p) => !personSearch || p.name.toLowerCase().includes(personSearch.toLowerCase()))
    .slice(0, 200), [people, personSearch]);
  const liveCameras = cameras.filter((c) => !c.deleted || cameraIds.includes(c.id));

  const problem = (): string | null => {
    if (!name.trim()) return 'Give the rule a name.';
    if (!cameraIds.length) return 'Pick at least one camera.';
    if (!eventKinds.length) return 'Pick at least one kind of detection.';
    if (matchMode === 'targets' && !targets.length) return 'Pick at least one person or group.';
    if (!always) {
      if (!rows.length) return 'Add a time window, or choose “Always”.';
      if (rows.some((r) => !r.days.length)) return 'Every time window needs at least one day.';
      if (rows.some((r) => !r.start || !r.end || r.start === r.end)) return 'A time window can’t start and end at the same time.';
    }
    if (recipientIds.length > maxRecipients) return `At most ${maxRecipients} recipients per rule.`;
    return null;
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const issue = problem();
    if (issue) { setError(issue); return; }
    const score = (v: string) => (v.trim() === '' ? null : Math.max(0, Math.min(100, Number(v))));
    setSaving(true);
    setError(null);
    try {
      await onSubmit({
        name, description, isEnabled, severity, eventKinds, matchMode,
        minMatchScore: score(minScore), minLiveness: score(minLiveness),
        timezone: rule?.timezone || timezone,
        cooldownSeconds: Math.max(0, Math.round(Number(cooldownMin) || 0)) * 60,
        dedupeScope,
        maxDelaySeconds: Math.max(0, Math.round(Number(maxDelayMin) || 0)) * 60,
        emailDelayed, attachSnapshot, cameraIds,
        windows: always ? [] : rowsToWindows(rows),
        targets: matchMode === 'targets' ? targets : [],
        recipientIds,
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the rule');
      setSaving(false);
    }
  };

  return (
    <Dialog eyebrow={rule ? 'Edit rule' : 'New rule'} title={rule ? rule.name : 'New alarm rule'} onClose={onClose} busy={saving} wide>
      <form onSubmit={submit} noValidate className="flex min-h-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto">
          {/* What */}
          <div className={section}>
            <div className="grid gap-3 sm:grid-cols-[1fr_160px]">
              <label className={label}>Rule name
                <input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} placeholder="e.g. After-hours on D3"
                  className={`${inputCls} mt-1 w-full`} required />
              </label>
              <label className={label}>Severity
                <select value={severity} onChange={(e) => setSeverity(e.target.value as Severity)} className={`${inputCls} mt-1 w-full`}>
                  <option value="info">Info</option>
                  <option value="warning">Warning</option>
                  <option value="critical">Critical</option>
                </select>
              </label>
            </div>
            <label className={`${label} block`}>Description (optional)
              <input value={description} onChange={(e) => setDescription(e.target.value)} maxLength={2000} className={`${inputCls} mt-1 w-full`} />
            </label>
            <Check checked={isEnabled} onChange={setIsEnabled}>Rule is on</Check>
          </div>

          {/* Where */}
          <div className={section}>
            <p className={label}>Cameras</p>
            {liveCameras.length === 0 ? (
              <p className="text-[14px] text-mute">No cameras yet. They are copied from the box; check that the box is reachable.</p>
            ) : (
              <div className="grid gap-1.5 sm:grid-cols-3">
                {liveCameras.map((c) => (
                  <Check key={c.id} checked={cameraIds.includes(c.id)} onChange={(on) => setCameraIds((l) => toggle(l, c.id, on))}>
                    {c.name}{c.deleted && <span className="text-[12px] text-crit"> (removed)</span>}
                  </Check>
                ))}
              </div>
            )}
          </div>

          {/* Who */}
          <div className={section}>
            <label className={`${label} block`}>Who triggers it
              <select aria-label="Who triggers it" value={matchMode} onChange={(e) => changeMatchMode(e.target.value as MatchMode)} className={`${inputCls} mt-1 w-full sm:w-72`}>
                {(Object.keys(MATCH_MODE_LABELS) as MatchMode[]).map((m) => <option key={m} value={m}>{MATCH_MODE_LABELS[m]}</option>)}
              </select>
            </label>
            <div>
              <p className={label}>Detections that count</p>
              <div className="mt-1 flex flex-wrap gap-x-5 gap-y-1.5">
                {ALLOWED_KINDS[matchMode].map((k) => (
                  <Check key={k} checked={eventKinds.includes(k)} onChange={(on) => setEventKinds((l) => toggle(l, k, on))}>
                    {EVENT_KIND_LABELS[k]}
                  </Check>
                ))}
              </div>
              {matchMode === 'anyone' && (
                <p className="mt-1 text-[12.5px] text-mute">Add body captures to catch people whose face isn’t visible.</p>
              )}
            </div>
            {matchMode === 'targets' && (
              <div className="grid gap-3 sm:grid-cols-2">
                {libraryError && <div className="sm:col-span-2"><ErrorNote message={`Couldn’t load the face library: ${libraryError}`} /></div>}
                <div>
                  <p className={label}>Groups</p>
                  <div className="mt-1 max-h-40 space-y-1 overflow-y-auto rounded-lg border border-line p-2">
                    {groups === null ? <p className="text-[13px] text-mute">Loading…</p> : groups.length === 0 ? <p className="text-[13px] text-mute">No groups</p>
                      : groups.map((g) => (
                        <Check key={g.group_id} checked={isTarget('group', g.group_id)} onChange={(on) => setTarget('group', g.group_id, g.group_name, on)}>
                          {g.group_name}
                        </Check>
                      ))}
                  </div>
                </div>
                <div>
                  <p className={label}>People</p>
                  <input value={personSearch} onChange={(e) => setPersonSearch(e.target.value)} placeholder="Search people" aria-label="Search people" className={`${inputCls} mt-1 w-full`} />
                  <div className="mt-1 max-h-40 space-y-1 overflow-y-auto rounded-lg border border-line p-2">
                    {people === null ? <p className="text-[13px] text-mute">Loading…</p> : shownPeople.length === 0 ? <p className="text-[13px] text-mute">Nobody found</p>
                      : shownPeople.map((p) => (
                        <Check key={p.id} checked={isTarget('person', p.id)} onChange={(on) => setTarget('person', p.id, p.name, on)}>
                          {p.name}
                        </Check>
                      ))}
                  </div>
                </div>
                {targets.length > 0 && (
                  <p className="text-[12.5px] text-mute sm:col-span-2">Watching: {targets.map((t) => t.label || t.value).join(', ')}</p>
                )}
              </div>
            )}
            <div className="grid gap-3 sm:grid-cols-2">
              {matchMode !== 'strangers' && (
                <label className={label}>Minimum match score (0–100, optional)
                  <input type="number" min={0} max={100} value={minScore} onChange={(e) => setMinScore(e.target.value)} placeholder="Any" className={`${inputCls} mt-1 w-full`} />
                </label>
              )}
              <label className={label}>Minimum liveness (0–100, optional)
                <input type="number" min={0} max={100} value={minLiveness} onChange={(e) => setMinLiveness(e.target.value)} placeholder="Any" className={`${inputCls} mt-1 w-full`} />
              </label>
            </div>
          </div>

          {/* When */}
          <div className={section}>
            <div className="flex items-center justify-between">
              <p className={label}>When it’s active <span className="normal-case">(box time, {rule?.timezone || timezone})</span></p>
              <div className="flex rounded-lg border border-line p-0.5 text-[13px]">
                <button type="button" onClick={() => setAlways(true)} className={`rounded-md px-2.5 py-1 ${always ? 'bg-slate-900 text-white' : 'text-slate-600'}`}>Always</button>
                <button type="button" onClick={() => setAlways(false)} className={`rounded-md px-2.5 py-1 ${!always ? 'bg-slate-900 text-white' : 'text-slate-600'}`}>Set times</button>
              </div>
            </div>
            {!always && (
              <div className="space-y-2">
                {rows.map((row, index) => (
                  <div key={index} className="flex flex-wrap items-center gap-2 rounded-lg border border-line p-2.5">
                    <div className="flex gap-1">
                      {ALL_DAYS.map((d) => (
                        <button key={d} type="button" aria-pressed={row.days.includes(d)} aria-label={`${DAY_NAMES[d - 1]} for window ${index + 1}`}
                          onClick={() => setRows((rs) => rs.map((r, i) => i === index ? { ...r, days: toggle(r.days, d, !r.days.includes(d)).sort() } : r))}
                          className={`w-10 rounded-md border py-1 text-[12.5px] font-medium ${row.days.includes(d) ? 'border-pri bg-pri-bg text-pri' : 'border-line text-mute'}`}>
                          {DAY_NAMES[d - 1]}
                        </button>
                      ))}
                    </div>
                    <input type="time" aria-label={`Start of window ${index + 1}`} value={row.start}
                      onChange={(e) => setRows((rs) => rs.map((r, i) => i === index ? { ...r, start: e.target.value } : r))} className={inputCls} />
                    <span className="text-mute">to</span>
                    <input type="time" aria-label={`End of window ${index + 1}`} value={row.end}
                      onChange={(e) => setRows((rs) => rs.map((r, i) => i === index ? { ...r, end: e.target.value } : r))} className={inputCls} />
                    {row.end && row.start && row.end < row.start && (
                      <span className="flex items-center gap-1 text-[12.5px] text-mute"><Moon size={13} /> until next day</span>
                    )}
                    <button type="button" onClick={() => setRows((rs) => rs.filter((_, i) => i !== index))} aria-label={`Remove window ${index + 1}`}
                      className="ml-auto rounded-md p-1.5 text-crit hover:bg-crit-bg"><Trash2 size={15} /></button>
                  </div>
                ))}
                <button type="button" onClick={() => setRows((rs) => [...rs, { days: [1, 2, 3, 4, 5], start: '18:00', end: '08:00' }])} className={btnCls}>
                  <Plus size={15} /> Add time window
                </button>
              </div>
            )}
          </div>

          {/* How often */}
          <div className={section}>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className={label}>Quiet period after an alarm (minutes)
                <input type="number" min={0} max={1440} value={cooldownMin} onChange={(e) => setCooldownMin(e.target.value)} className={`${inputCls} mt-1 w-full`} />
              </label>
              <label className={label}>Group detections
                <select value={dedupeScope} onChange={(e) => setDedupeScope(e.target.value as DedupeScope)} className={`${inputCls} mt-1 w-full`}>
                  <option value="camera">One alarm per camera during the quiet period</option>
                  <option value="track">One alarm per person walking by</option>
                </select>
              </label>
              <label className={label}>Count as late after (minutes)
                <input type="number" min={0} max={1440} value={maxDelayMin} onChange={(e) => setMaxDelayMin(e.target.value)} className={`${inputCls} mt-1 w-full`} />
              </label>
              <div className="flex items-end pb-2">
                <Check checked={emailDelayed} onChange={setEmailDelayed}>Still email late alarms</Check>
              </div>
            </div>
            <p className="text-[12.5px] text-mute">Detections during the quiet period are added to the open alarm instead of sending more emails. Late alarms happen when the portal catches up after being offline.</p>
          </div>

          {/* Email */}
          <div className={section}>
            <p className={label}>Email these people ({recipientIds.length}/{maxRecipients})</p>
            {contacts.length === 0 ? (
              <p className="text-[14px] text-mute">No recipients yet. Add them on the Recipients tab. The rule still records alarms without them.</p>
            ) : (
              <div className="grid gap-1.5 sm:grid-cols-2">
                {contacts.map((c) => (
                  <Check key={c.id} checked={recipientIds.includes(c.id)} onChange={(on) => setRecipientIds((l) => toggle(l, c.id, on))}
                    disabled={!recipientIds.includes(c.id) && recipientIds.length >= maxRecipients}>
                    {c.name} <span className="text-mute">{c.email}</span>{!c.isActive && <span className="text-[12px] text-warn"> (paused)</span>}
                  </Check>
                ))}
              </div>
            )}
            <Check checked={attachSnapshot} onChange={setAttachSnapshot}>Attach the snapshot to the email</Check>
          </div>
        </div>

        <div className="flex items-center gap-3 border-t border-line px-6 py-4">
          {error && <div className="min-w-0 flex-1"><ErrorNote message={error} /></div>}
          <div className="ml-auto flex shrink-0 gap-2">
            <button type="button" onClick={onClose} disabled={saving} className={btnCls}>Cancel</button>
            <button type="submit" disabled={saving} className={priBtnCls}>{saving ? 'Saving…' : rule ? 'Save rule' : 'Create rule'}</button>
          </div>
        </div>
      </form>
    </Dialog>
  );
}
