'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle, CalendarClock, Check, ChevronDown, Clock3, Plus, RefreshCw, Save, Search, Trash2,
} from 'lucide-react';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import {
  blankTimePlan, createTimePlan, deleteTimePlan, fetchTimeContext, fetchTimePlans, updateTimePlan, type PlanKind, type TimePlan,
} from '@/lib/timeplans';

const DAYS = [
  ['1', 'Monday'], ['2', 'Tuesday'], ['3', 'Wednesday'], ['4', 'Thursday'],
  ['5', 'Friday'], ['6', 'Saturday'], ['7', 'Sunday'],
] as const;

const inputClass = 'h-9 rounded-md border border-line bg-white px-2.5 text-[13px] text-ink outline-none transition focus:border-pri focus:ring-2 focus:ring-pri/10';

function intervalParts(interval: string) {
  const [start = '00:00:00', end = '23:59:00'] = interval.split('-');
  return { start: start.slice(0, 5), end: end.slice(0, 5) };
}

function intervalValue(start: string, end: string) {
  return `${start || '00:00'}:00-${end || '23:59'}:00`;
}

function planWith(plan: TimePlan, day: string, intervals: string[]): TimePlan {
  return { ...plan, weekSchedule: { ...plan.weekSchedule, [day]: intervals } };
}

export default function TimeplansView() {
  const [kind, setKind] = useState<PlanKind>('regular');
  const [plans, setPlans] = useLocalStorage<TimePlan[]>('timeplan-drafts-v1', []);
  const [serverPlans, setServerPlans] = useState<TimePlan[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [search, setSearch] = useState('');
  const [context, setContext] = useState<{ time?: string; zone?: string; source?: 'box' | 'backend_fallback' } | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = async (showSpinner = true) => {
    if (showSpinner) setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const [remote, time] = await Promise.all([fetchTimePlans(kind), fetchTimeContext()]);
      setServerPlans(remote);
      setContext({ time: time.current_time?.time, zone: time.system_time?.time_zone, source: time.clock_source });
      setSelectedId((current) => current || remote[0]?.id || '');
      return remote;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load time plans');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { load(); }, [kind]);

  const visiblePlans = useMemo(() => {
    const remoteIds = new Set(serverPlans.map((plan) => plan.id));
    const merged = [
      ...serverPlans,
      ...plans.filter((plan) => plan.type === (kind === 'regular' ? 1 : 2) && (!remoteIds.has(plan.id) || plan.local)),
    ];
    return merged.filter((plan) => plan.name.toLowerCase().includes(search.toLowerCase()));
  }, [kind, plans, search, serverPlans]);

  const selected = plans.find((plan) => plan.id === selectedId)
    ?? serverPlans.find((plan) => plan.id === selectedId)
    ?? visiblePlans[0];

  useEffect(() => {
    if (selected && selected.id !== selectedId) setSelectedId(selected.id);
  }, [selected, selectedId]);

  const updatePlan = (next: TimePlan) => {
    setPlans((current) => [...current.filter((plan) => plan.id !== next.id), next]);
    setNotice(null);
  };

  const createPlan = () => {
    const next = blankTimePlan(kind, plans.length + 1);
    setPlans((current) => [...current, next]);
    setSelectedId(next.id);
    setSearch('');
    setNotice('Draft created. It will stay in this browser until the box write API is connected.');
  };

  const removePlan = async () => {
    if (!selected || !window.confirm(`Delete “${selected.name}” from the box? This cannot be undone.`)) return;
    setSaving(true);
    setError(null);
    try {
      if (selected.local) {
        setPlans((current) => current.filter((plan) => plan.id !== selected.id));
        setSelectedId(visiblePlans.find((plan) => plan.id !== selected.id)?.id ?? '');
        setNotice('Local draft removed.');
      } else {
        await deleteTimePlan(selected);
        setPlans((current) => current.filter((plan) => plan.id !== selected.id));
        const remote = await load(false);
        setSelectedId(remote?.find((plan) => plan.id !== selected.id)?.id ?? '');
        setNotice(`“${selected.name}” deleted from the box.`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete the time plan');
    } finally {
      setSaving(false);
    }
  };

  const savePlan = async () => {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      if (selected.local) {
        const name = selected.name.trim();
        await createTimePlan(selected);
        setPlans((current) => current.filter((plan) => plan.id !== selected.id));
        const remote = await load(false);
        setSelectedId(remote?.find((plan) => plan.name === name)?.id ?? '');
        setNotice(`“${name}” created on the box.`);
      } else {
        await updateTimePlan(selected);
        setPlans((current) => current.filter((plan) => plan.id !== selected.id));
        await load(false);
        setNotice(`“${selected.name}” saved to the box.`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save the time plan');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4 pb-8">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-white px-4 py-3 shadow-[0_1px_2px_rgba(15,22,33,0.03)]">
        <div className="flex items-center gap-1 rounded-md bg-ground p-1">
          {(['regular', 'festival'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => { setKind(tab); setSelectedId(''); }}
              className={`rounded px-3 py-1.5 text-[13px] font-medium transition ${kind === tab ? 'bg-white text-pri shadow-sm' : 'text-mute hover:text-ink'}`}
            >
              {tab === 'regular' ? 'Regular plans' : 'Festival plans'}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3 text-[12px] text-mute">
          <span className="flex items-center gap-1.5"><span className={`h-2 w-2 rounded-full ${context?.source === 'box' ? 'bg-ok' : 'bg-warn'}`} /> {context?.source === 'box' ? 'Box clock' : 'Portal clock'}</span>
          <span className="hidden text-line sm:inline">|</span>
          <span className="font-mono">{context?.time ?? 'Reading clock...'}</span>
          <button onClick={() => load(false)} disabled={refreshing} aria-label="Refresh time plans" title="Refresh time plans" className="rounded p-1.5 text-mute hover:bg-ground hover:text-ink disabled:opacity-50">
            <RefreshCw size={15} className={refreshing ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {error && <div className="flex items-center gap-2 rounded-md border border-crit/20 bg-crit-bg px-3 py-2 text-[13px] text-crit"><AlertCircle size={16} /> {error}</div>}
      {notice && <div className="flex items-center justify-between gap-3 rounded-md border border-pri/20 bg-pri-bg px-3 py-2 text-[13px] text-pri"><span className="flex items-center gap-2"><Check size={16} /> {notice}</span><button onClick={() => setNotice(null)} className="text-[12px] hover:underline">Dismiss</button></div>}

      <div className="grid gap-4 xl:grid-cols-[250px_minmax(0,1fr)_220px]">
        <aside className="rounded-lg border border-line bg-white shadow-[0_1px_2px_rgba(15,22,33,0.03)]">
          <div className="border-b border-line p-3">
            <div className="relative">
              <Search size={15} className="absolute left-2.5 top-2.5 text-mute" />
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Find a plan" className={`${inputClass} w-full pl-8`} />
            </div>
            <button onClick={createPlan} className="mt-3 flex h-9 w-full items-center justify-center gap-1.5 rounded-md border border-pri bg-pri-bg text-[13px] font-medium text-pri hover:bg-[#DDE7FC]"><Plus size={15} /> New time plan</button>
          </div>
          <div className="p-2">
            {loading ? <div className="space-y-2 p-2"><div className="h-10 animate-pulse rounded bg-ground" /><div className="h-10 animate-pulse rounded bg-ground" /></div> : visiblePlans.length === 0 ? <div className="p-4 text-center text-[12px] text-mute">No plans found</div> : visiblePlans.map((plan) => (
              <button key={plan.id} onClick={() => setSelectedId(plan.id)} className={`mb-1 flex w-full items-center justify-between rounded-md px-3 py-2.5 text-left transition ${selected?.id === plan.id ? 'bg-pri-bg text-pri' : 'text-ink hover:bg-ground'}`}>
                <span className="min-w-0"><span className="block truncate text-[13px] font-medium">{plan.name}</span><span className="mt-0.5 block text-[11px] text-mute">{plan.local ? 'Local draft' : plan.isDefault ? 'Default plan' : 'Box plan'}</span></span>
                {plan.isDefault && <span className="ml-2 h-2 w-2 shrink-0 rounded-full bg-ok" />}
              </button>
            ))}
          </div>
        </aside>

        {selected ? <PlanEditor plan={selected} saving={saving} onChange={updatePlan} onSave={savePlan} onRemove={removePlan} /> : <div className="flex min-h-[420px] items-center justify-center rounded-lg border border-dashed border-line bg-white text-center text-[13px] text-mute"><div><CalendarClock size={28} className="mx-auto mb-2 text-pri" /><p>Select a plan or create a new draft.</p></div></div>}

        <aside className="space-y-4">
          <section className="rounded-lg border border-line bg-[#111A27] p-4 text-white shadow-[0_8px_24px_rgba(15,22,33,0.12)]">
            <div className="flex items-center justify-between"><span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#8F9DB0]">Box clock</span><Clock3 size={16} className="text-[#9BB8F8]" /></div>
            <p className="mt-4 font-mono text-[24px] tracking-tight">{context?.time?.slice(11) ?? '--:--:--'}</p>
            <p className="mt-1 text-[12px] text-[#AAB6C5]">{context?.time?.slice(0, 10) ?? 'Waiting for time'} · {context?.zone ?? 'Unknown zone'}</p>
            <div className="mt-4 border-t border-white/10 pt-3 text-[11.5px] text-[#AAB6C5]">{context ? 'Clock is synchronized with the recorder.' : 'Reading the recorder clock...'}</div>
          </section>
          <section className="rounded-lg border border-line bg-white p-4">
            <div className="flex items-center gap-2 text-[13px] font-semibold"><CalendarClock size={16} className="text-pri" /> Plan summary</div>
            <dl className="mt-4 space-y-3 text-[12px]"><div className="flex justify-between gap-3"><dt className="text-mute">Plan type</dt><dd className="font-medium">{kind === 'regular' ? 'Regular' : 'Festival'}</dd></div><div className="flex justify-between gap-3"><dt className="text-mute">Total plans</dt><dd className="font-mono">{visiblePlans.length}</dd></div><div className="flex justify-between gap-3"><dt className="text-mute">Active days</dt><dd className="font-mono">{selected ? Object.values(selected.weekSchedule).filter((items) => items.length).length : 0} / 7</dd></div></dl>
          </section>
        </aside>
      </div>
    </div>
  );
}

function PlanEditor({ plan, saving, onChange, onSave, onRemove }: { plan: TimePlan; saving: boolean; onChange: (plan: TimePlan) => void; onSave: () => void; onRemove: () => void }) {
  const setName = (name: string) => onChange({ ...plan, name });
  const addInterval = (day: string) => onChange(planWith(plan, day, [...(plan.weekSchedule[day] ?? []), '09:00:00-17:00:00']));
  const removeInterval = (day: string, index: number) => onChange(planWith(plan, day, (plan.weekSchedule[day] ?? []).filter((_, i) => i !== index)));
  const changeInterval = (day: string, index: number, key: 'start' | 'end', value: string) => {
    const next = (plan.weekSchedule[day] ?? []).map((item, i) => {
      if (i !== index) return item;
      const parts = intervalParts(item);
      return intervalValue(key === 'start' ? value : parts.start, key === 'end' ? value : parts.end);
    });
    onChange(planWith(plan, day, next));
  };

  return (
    <section className="min-w-0 rounded-lg border border-line bg-white shadow-[0_1px_2px_rgba(15,22,33,0.03)]">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
        <div className="min-w-0"><div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-pri"><CalendarClock size={14} /> {plan.local ? 'Local draft' : 'Box plan'}</div><input aria-label="Plan name" value={plan.name} onChange={(event) => setName(event.target.value)} className="w-full max-w-[360px] border-0 p-0 text-[19px] font-semibold tracking-tight outline-none focus:ring-0" /><p className="mt-1 text-[12px] text-mute">Set the windows when this plan should run.</p></div>
        <div className="flex items-center gap-2"><button onClick={onRemove} disabled={saving} aria-label="Delete plan" title="Delete plan" className="rounded-md border border-line p-2 text-mute hover:border-crit/30 hover:bg-crit-bg hover:text-crit disabled:opacity-40"><Trash2 size={16} /></button><button onClick={onSave} disabled={saving} className="flex h-9 items-center gap-1.5 rounded-md bg-pri px-3.5 text-[13px] font-medium text-white hover:bg-[#1A43A0] disabled:opacity-60"><Save size={15} /> {saving ? 'Saving...' : plan.local ? 'Save draft' : 'Save to box'}</button></div>
      </header>
      <div className="border-b border-line bg-[#FBFCFD] px-5 py-3 text-[12px] text-mute"><span className="mr-2 inline-flex items-center gap-1.5 rounded-full bg-ok-bg px-2 py-1 font-medium text-ok"><span className="h-1.5 w-1.5 rounded-full bg-ok" /> Weekly schedule</span>Times use the recorder&apos;s local timezone.</div>
      <div className="overflow-x-auto p-5"><div className="min-w-[650px]">
        <div className="mb-2 grid grid-cols-[88px_minmax(0,1fr)_116px] items-center gap-3 px-2 text-[10px] font-semibold uppercase tracking-wider text-mute"><span>Day</span><div className="flex justify-between font-mono font-normal normal-case tracking-normal"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div><span className="text-right">Windows</span></div>
        <div className="space-y-2">{DAYS.map(([day, label]) => <div key={day} className="grid grid-cols-[88px_minmax(0,1fr)_116px] items-center gap-3 rounded-md border border-line/70 px-2 py-2"><span className="text-[12.5px] font-medium">{label}</span><div className="relative h-9 overflow-hidden rounded border border-line bg-ground"><div className="absolute inset-0 bg-[linear-gradient(90deg,transparent_24.8%,#DCE0E5_25%,transparent_25.2%,transparent_49.8%,#DCE0E5_50%,transparent_50.2%,transparent_74.8%,#DCE0E5_75%,transparent_75.2%)]" />{(plan.weekSchedule[day] ?? []).map((item, index) => { const parts = intervalParts(item); const start = (Number(parts.start.slice(0, 2)) * 60 + Number(parts.start.slice(3))) / 1440 * 100; const end = (Number(parts.end.slice(0, 2)) * 60 + Number(parts.end.slice(3))) / 1440 * 100; return <div key={`${item}-${index}`} className="absolute inset-y-1 rounded bg-pri/80 shadow-sm" style={{ left: `${start}%`, width: `${Math.max(end - start, 1)}%` }} />; })}</div><div className="flex justify-end gap-1"><span className="rounded-full bg-ground px-2 py-1 font-mono text-[10.5px] text-mute">{(plan.weekSchedule[day] ?? []).length} {`window${(plan.weekSchedule[day] ?? []).length === 1 ? '' : 's'}`}</span><button onClick={() => addInterval(day)} aria-label={`Add window for ${label}`} title="Add window" className="rounded p-1 text-pri hover:bg-pri-bg"><Plus size={14} /></button></div></div>)}</div>
      </div></div>
      <div className="border-t border-line px-5 py-4"><div className="mb-3 flex items-center justify-between"><div><h3 className="text-[13px] font-semibold">Daily windows</h3><p className="mt-0.5 text-[11.5px] text-mute">Add more than one interval when a day has a split schedule.</p></div><ChevronDown size={16} className="text-mute" /></div><div className="space-y-2">{DAYS.map(([day, label]) => <div key={day} className="grid gap-2 sm:grid-cols-[100px_1fr] sm:items-center"><span className="text-[12px] font-medium text-mute">{label}</span><div className="space-y-2">{(plan.weekSchedule[day] ?? []).length ? (plan.weekSchedule[day] ?? []).map((item, index) => { const parts = intervalParts(item); return <div key={`${day}-${index}`} className="flex flex-wrap items-center gap-2"><input type="time" value={parts.start} onChange={(event) => changeInterval(day, index, 'start', event.target.value)} className={inputClass} /><span className="text-[12px] text-mute">to</span><input type="time" value={parts.end} onChange={(event) => changeInterval(day, index, 'end', event.target.value)} className={inputClass} /><button onClick={() => removeInterval(day, index)} aria-label={`Remove ${label} window`} title="Remove window" className="rounded p-2 text-mute hover:bg-crit-bg hover:text-crit"><Trash2 size={14} /></button></div>; }) : <button onClick={() => addInterval(day)} className="flex items-center gap-1 text-[12px] text-pri hover:underline"><Plus size={14} /> Add a window</button>}</div></div>)}</div></div>
    </section>
  );
}