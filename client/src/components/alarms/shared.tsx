'use client';

import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { STATUS_LABELS, type IncidentStatus, type Severity } from '@/lib/alarms';

export const inputCls =
  'rounded-lg border border-line bg-white px-3 py-2 text-[14.5px] text-slate-700 outline-none transition focus:border-pri disabled:bg-ground disabled:text-mute';
export const btnCls =
  'flex items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-[14.5px] font-medium text-slate-600 transition hover:bg-slate-50 disabled:opacity-50';
export const priBtnCls =
  'flex items-center gap-1.5 rounded-lg bg-pri px-3.5 py-2 text-[14.5px] font-medium text-white transition hover:bg-[#1A43A0] disabled:opacity-50';

/** ISO timestamp -> "YYYY-MM-DD HH:mm:ss" in this browser's time zone (like the other pages). */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[12.5px] font-medium uppercase tracking-wide text-mute">{label}</span>
      {children}
      {hint && <span className="text-[12.5px] text-mute">{hint}</span>}
    </label>
  );
}

const SEVERITY_STYLE: Record<Severity, string> = {
  critical: 'bg-crit-bg text-crit',
  warning: 'bg-warn-bg text-warn',
  info: 'bg-pri-bg text-pri',
};

export function SeverityPill({ severity }: { severity: Severity }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[12.5px] font-medium capitalize ${SEVERITY_STYLE[severity] ?? 'bg-ground'}`}>
      {severity}
    </span>
  );
}

const STATUS_STYLE: Record<IncidentStatus, string> = {
  open: 'bg-crit-bg text-crit',
  acknowledged: 'bg-warn-bg text-warn',
  resolved: 'bg-ok-bg text-ok',
  false_alarm: 'bg-ground text-slate-600',
};

export function StatusPill({ status }: { status: IncidentStatus }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[12.5px] font-medium ${STATUS_STYLE[status] ?? 'bg-ground'}`}>
      {status === 'open' && <span className="h-1.5 w-1.5 rounded-full bg-crit" />}
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

/** Image from the box that falls back to a grey placeholder when missing or rotated out. */
export function BoxImage({ src, alt, className }: { src?: string; alt: string; className: string }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  if (!src || failed) {
    return <div className={`${className} flex items-center justify-center bg-ground text-[11px] text-mute`}>No image</div>;
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt={alt} onError={() => setFailed(true)} className={`${className} object-cover`} />;
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-[14px] text-red-700">
      <span>{message}</span>
      {onRetry && <button onClick={onRetry} className="shrink-0 font-medium hover:underline">Try again</button>}
    </div>
  );
}

/** Dialog frame: Escape or clicking outside closes it (unless busy). */
export function Dialog({ eyebrow, title, onClose, busy, wide, children }: {
  eyebrow: string; title: string; onClose: () => void; busy?: boolean; wide?: boolean; children: React.ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && !busy && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [busy, onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#0F1621]/45 p-4"
      onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div className={`flex max-h-[92vh] w-full flex-col rounded-lg bg-white shadow-2xl ${wide ? 'max-w-3xl' : 'max-w-lg'}`}>
        <div className="flex items-start justify-between border-b border-line px-6 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.08em] text-pri">{eyebrow}</p>
            <h2 className="mt-1 text-xl font-semibold">{title}</h2>
          </div>
          <button type="button" disabled={busy} onClick={onClose} aria-label="Close" className="rounded-md p-1.5 text-mute hover:bg-ground">
            <X size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function ConfirmDialog({ title, message, confirmLabel, onCancel, onConfirm }: {
  title: string; message: string; confirmLabel: string; onCancel: () => void; onConfirm: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
      onCancel();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
      setBusy(false);
    }
  };
  return (
    <Dialog eyebrow="Confirm" title={title} onClose={onCancel} busy={busy}>
      <div className="space-y-3 px-6 py-5 text-[14.5px] text-slate-700">
        <p>{message}</p>
        {error && <ErrorNote message={error} />}
      </div>
      <div className="flex justify-end gap-2 border-t border-line px-6 py-4">
        <button type="button" onClick={onCancel} disabled={busy} className={btnCls}>Cancel</button>
        <button type="button" onClick={confirm} disabled={busy}
          className="rounded-lg bg-crit px-3.5 py-2 text-[14.5px] font-medium text-white transition hover:opacity-90 disabled:opacity-50">
          {busy ? 'Working…' : confirmLabel}
        </button>
      </div>
    </Dialog>
  );
}
