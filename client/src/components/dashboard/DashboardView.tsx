'use client';

import { useEffect, useState } from 'react';
import {
  Activity, AlertTriangle, ArrowUpRight, Camera, CheckCircle2, Clock3, RefreshCw, ScanFace, ShieldAlert, Video,
} from 'lucide-react';
import Link from 'next/link';
import { PATHS } from '@/lib/paths';
import { fetchDashboardSummary, type DashboardEvent, type DashboardSummary } from '@/lib/dashboard';

const REFRESH_MS = 45_000;

function number(value: number) {
  return new Intl.NumberFormat().format(value);
}

function percentChange(value: number, previous: number) {
  if (previous === 0) return value ? 'New' : 'No change';
  const change = ((value - previous) / previous) * 100;
  return `${change > 0 ? '+' : ''}${change.toFixed(0)}%`;
}

function timeLabel(value?: number | null) {
  if (!value) return 'Unknown time';
  return new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(value);
}

function StatCard({ label, value, detail, tone = 'blue', icon: Icon }: {
  label: string; value: string; detail: string; tone?: 'blue' | 'red' | 'green' | 'amber'; icon: typeof Activity;
}) {
  const tones = {
    blue: 'bg-pri-bg text-pri', red: 'bg-crit-bg text-crit', green: 'bg-ok-bg text-ok', amber: 'bg-warn-bg text-warn',
  };
  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-[0_1px_2px_rgba(15,22,33,0.03)]">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-mute">{label}</p>
        <span className={`flex h-8 w-8 items-center justify-center rounded-md ${tones[tone]}`}><Icon size={16} /></span>
      </div>
      <p className="mt-3 text-[25px] font-semibold tracking-tight text-ink">{value}</p>
      <p className="mt-1 text-[12px] text-mute">{detail}</p>
    </section>
  );
}

function Section({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-white shadow-[0_1px_2px_rgba(15,22,33,0.03)]">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <h2 className="text-[13px] font-semibold text-ink">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function EventRow({ event }: { event: DashboardEvent }) {
  const stranger = event.type === 'stranger';
  return (
    <div className="flex items-center gap-3 border-b border-line px-4 py-3 last:border-0">
      <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${stranger ? 'bg-crit-bg text-crit' : 'bg-pri-bg text-pri'}`}>
        {stranger ? <ShieldAlert size={15} /> : <ScanFace size={15} />}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-medium">{stranger ? 'Stranger detected' : event.person || 'Matched face'}</p>
        <p className="mt-0.5 truncate text-[11.5px] text-mute">{event.device} · {timeLabel(event.time_ms)}</p>
      </div>
      {event.score != null && <span className="font-mono text-[12px] text-mute">{event.score.toFixed(0)}%</span>}
    </div>
  );
}

export default function DashboardView() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshedAt, setRefreshedAt] = useState<Date | null>(null);

  const load = async (initial = false, fresh = false) => {
    if (initial) setLoading(true); else setRefreshing(true);
    setError(null);
    try {
      setData(await fetchDashboardSummary(undefined, { fresh }));
      setRefreshedAt(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load dashboard');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    load(true);
    const timer = window.setInterval(() => load(), REFRESH_MS);
    return () => window.clearInterval(timer);
  }, []);

  if (loading && !data) return <div className="grid gap-4 md:grid-cols-4"><div className="h-32 animate-pulse rounded-lg bg-white" /><div className="h-32 animate-pulse rounded-lg bg-white" /><div className="h-32 animate-pulse rounded-lg bg-white" /><div className="h-32 animate-pulse rounded-lg bg-white" /></div>;
  if (!data) return <div className="rounded-lg border border-crit/20 bg-crit-bg px-4 py-3 text-[13px] text-crit">{error ?? 'Dashboard unavailable'}</div>;

  const strangerRate = data.activity.matched + data.activity.strangers
    ? Math.round((data.activity.strangers / (data.activity.matched + data.activity.strangers)) * 100)
    : 0;
  const peak = data.insights.peak_hour == null ? 'No activity' : `${String(data.insights.peak_hour).padStart(2, '0')}:00`;
  const maxHour = Math.max(1, ...data.insights.hourly_activity.map((item) => item.count));

  return (
    <div className="space-y-4 pb-8">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-white px-4 py-3">
        <div className="flex items-center gap-3 text-[12px] text-mute">
          <span className={`h-2 w-2 rounded-full ${data.health.clock.source === 'box' ? 'bg-ok' : 'bg-warn'}`} />
          <span>{data.health.clock.source === 'box' ? 'Box clock connected' : 'Box clock unavailable'}</span>
          <span className="hidden text-line sm:inline">|</span>
          <span>{data.date} · refreshes every 45 seconds{data.meta ? ` · from ${data.meta.source === 'database' ? 'portal database' : 'box'}` : ''}</span>
        </div>
        <button onClick={() => load(false, true)} disabled={refreshing} title="Refresh dashboard" className="flex h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-[12px] font-medium hover:bg-ground disabled:opacity-50">
          <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {error && <div className="flex items-center gap-2 rounded-md border border-crit/20 bg-crit-bg px-3 py-2 text-[13px] text-crit"><AlertTriangle size={15} /> {error} <span className="ml-auto text-[11px]">Showing last successful snapshot</span></div>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Recognitions" value={number(data.activity.matched)} detail={`${percentChange(data.activity.matched, data.activity.previous_matched)} vs yesterday`} icon={ScanFace} />
        <StatCard label="Strangers" value={number(data.activity.strangers)} detail={`${strangerRate}% of face matches`} tone={data.activity.strangers ? 'red' : 'green'} icon={ShieldAlert} />
        <StatCard label="Cameras" value={`${data.health.devices_online}/${data.health.devices_total}`} detail={`${data.health.streams_pulling} streams pulling`} tone={data.health.devices_offline ? 'amber' : 'green'} icon={Video} />
        <StatCard label="Captures" value={number(data.activity.captures)} detail={`${data.activity.face_captures} face · ${data.activity.body_captures} body${data.activity.capture_breakdown_limited ? ' scanned' : ''}`} icon={Camera} />
      </div>

      <Section title="People flow" action={<span className="text-[11px] text-mute">Today · camera track analysis</span>}>
        <div className="grid divide-y divide-line sm:grid-cols-2 sm:divide-x sm:divide-y-0 xl:grid-cols-4">
          <div className="px-4 py-4"><p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-mute">Tracked encounters</p><p className="mt-2 text-[23px] font-semibold">{number(data.insights.tracked_encounters)}</p><p className="mt-1 text-[11.5px] text-mute">{data.insights.face_encounters} face · {data.insights.body_encounters} body</p></div>
          <div className="px-4 py-4"><p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-mute">Unique recognized people</p><p className="mt-2 text-[23px] font-semibold">{number(data.insights.unique_recognized_people)}</p><p className="mt-1 text-[11.5px] text-mute">Distinct face-library identities</p></div>
          <div className="px-4 py-4"><p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-mute">Recognized encounters</p><p className="mt-2 text-[23px] font-semibold">{number(data.insights.recognized_encounters)}</p><p className="mt-1 text-[11.5px] text-mute">{data.insights.recognition_coverage_percent == null ? 'No face tracks to compare' : `${data.insights.recognition_coverage_percent}% of face tracks`}</p></div>
          <div className="px-4 py-4"><p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-mute">Stranger encounters</p><p className="mt-2 text-[23px] font-semibold text-crit">{number(data.insights.stranger_encounters)}</p><p className="mt-1 text-[11.5px] text-mute">Tracked strangers, not unique identities</p></div>
        </div>
        <p className="border-t border-line px-4 py-3 text-[11px] leading-relaxed text-mute">Tracked encounters are deduplicated by camera and track ID. The box can identify recognized people by face-library ID, but it cannot prove that two stranger tracks are the same person across cameras.</p>
      </Section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(300px,0.75fr)]">
        <Section title="Security activity by hour" action={<span className="text-[11px] text-mute">Peak {peak}</span>}>
          <div className="px-4 pb-4 pt-5">
            <div className="flex h-36 items-end gap-1.5 border-b border-line">
              {data.insights.hourly_activity.map((item) => <div key={item.hour} className="group flex min-w-0 flex-1 flex-col items-center justify-end gap-1" title={`${String(item.hour).padStart(2, '0')}:00 · ${item.count} events`}>
                <div className={`w-full max-w-5 rounded-t-sm ${item.count ? 'bg-pri' : 'bg-ground'}`} style={{ height: `${Math.max(item.count ? 5 : 2, (item.count / maxHour) * 100)}%` }} />
              </div>)}
            </div>
            <div className="mt-2 flex justify-between text-[10px] text-mute"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>23:00</span></div>
            {data.insights.analysis_limited && <p className="mt-3 text-[11px] text-mute">Trend metrics use the latest {number(data.insights.analysis_sampled)} recognition records; totals are complete.</p>}
          </div>
        </Section>

        <Section title="Signals worth checking">
          <div className="divide-y divide-line">
            <div className="flex items-center justify-between px-4 py-3 text-[12px]"><span className="text-mute">Average match score</span><strong>{data.insights.average_match_score == null ? '—' : `${data.insights.average_match_score}%`}</strong></div>
            <div className="flex items-center justify-between px-4 py-3 text-[12px]"><span className="text-mute">Low-confidence matches</span><strong className={data.insights.low_confidence_count ? 'text-warn' : 'text-ok'}>{data.insights.low_confidence_count}</strong></div>
            <div className="flex items-center justify-between px-4 py-3 text-[12px]"><span className="text-mute">Low-liveness matches</span><strong className={data.insights.low_liveness_count ? 'text-crit' : 'text-ok'}>{data.insights.low_liveness_count}</strong></div>
            <div className="flex items-center justify-between px-4 py-3 text-[12px]"><span className="text-mute">Busiest camera</span><strong className="max-w-[150px] truncate">{data.insights.busiest_device || '—'}</strong></div>
          </div>
        </Section>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(280px,0.8fr)]">
        <Section title="Camera readiness" action={<Link href={PATHS.devices} className="flex items-center gap-1 text-[11px] font-medium text-pri hover:underline">Manage devices <ArrowUpRight size={13} /></Link>}>
          <div className="divide-y divide-line">
            {data.devices.map((device) => <div key={device.id} className="flex items-center gap-3 px-4 py-3 text-[12px]">
              <span className={`h-2 w-2 shrink-0 rounded-full ${device.online && device.pulling_stream ? 'bg-ok' : device.online ? 'bg-warn' : 'bg-crit'}`} />
              <span className="min-w-0 flex-1 truncate font-medium">{device.name}</span>
              <span className="hidden text-mute sm:inline">{device.task || 'No task'}</span>
              <span className={device.online ? 'text-ok' : 'text-crit'}>{device.online ? (device.pulling_stream ? 'Ready' : 'Stream issue') : 'Offline'}</span>
            </div>)}
            {!data.devices.length && <p className="px-4 py-8 text-center text-[12px] text-mute">No cameras configured.</p>}
          </div>
        </Section>

        <Section title="Attention queue">
          <div className="divide-y divide-line">
            {data.attention.slice(0, 5).map((item, index) => <div key={`${item.type}-${item.device_id ?? index}`} className="flex gap-3 px-4 py-3 text-[12px]">
              <AlertTriangle size={15} className={`mt-0.5 shrink-0 ${item.severity === 'critical' ? 'text-crit' : 'text-warn'}`} />
              <span>{item.message}</span>
            </div>)}
            {!data.attention.length && <div className="flex items-center gap-2 px-4 py-8 text-[12px] text-ok"><CheckCircle2 size={16} /> No device issues detected.</div>}
          </div>
        </Section>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(260px,0.65fr)]">
        <Section title="Recent recognition activity" action={<Link href={PATHS.recognition} className="flex items-center gap-1 text-[11px] font-medium text-pri hover:underline">View records <ArrowUpRight size={13} /></Link>}>
          {data.insights.events.length ? data.insights.events.map((event) => <EventRow key={event.id} event={event} />) : <p className="px-4 py-8 text-center text-[12px] text-mute">No recognition activity today.</p>}
        </Section>
        <Section title="Most recognized today">
          <div className="divide-y divide-line">
            {data.insights.top_people.map((person, index) => <div key={person.name} className="flex items-center gap-3 px-4 py-3 text-[12px]"><span className="w-5 font-mono text-mute">{index + 1}</span><span className="min-w-0 flex-1 truncate font-medium">{person.name}</span><span className="font-mono text-mute">{person.count}</span></div>)}
            {!data.insights.top_people.length && <p className="px-4 py-8 text-center text-[12px] text-mute">No matched people today.</p>}
          </div>
        </Section>
      </div>

      <p className="flex items-center justify-end gap-1 text-[11px] text-mute"><Clock3 size={13} /> Last refreshed {refreshedAt?.toLocaleTimeString() ?? '—'} · {data.health.clock.time_zone || 'Box timezone unavailable'}</p>
    </div>
  );
}