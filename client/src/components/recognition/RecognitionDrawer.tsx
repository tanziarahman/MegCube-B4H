'use client';

import { useEffect, useState } from 'react';
import { Camera, Clock, Hash, X } from 'lucide-react';
import type { RecognitionRow } from '@/lib/recognition';

/** Image that falls back to a grey placeholder when missing or broken. */
function Img({ src, alt, className }: { src?: string; alt: string; className: string }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  if (!src || failed) {
    return (
      <div className={`${className} flex items-center justify-center bg-ground text-[11px] text-mute`}>
        No image
      </div>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt={alt} onError={() => setFailed(true)} className={className} />;
}

/** Thin horizontal bar for a 0–100 score. */
function ScoreBar({ value, strong }: { value: string; strong?: boolean }) {
  const n = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-ground">
      <div className={`h-full rounded-full ${strong ? 'bg-pri' : 'bg-[#C4CAD3]'}`} style={{ width: `${n}%` }} />
    </div>
  );
}

function Chips({ text }: { text: string }) {
  const items = text && text !== '—' ? text.split(',').map((s) => s.trim()).filter(Boolean) : [];
  if (!items.length) return <span className="text-mute">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((g) => (
        <span key={g} className="rounded border border-line bg-ground px-1.5 py-0.5 text-[11.5px]">{g}</span>
      ))}
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-4 rounded-lg border border-line">
      <h3 className="border-b border-line px-3 py-2 text-[11.5px] font-semibold uppercase tracking-wide text-mute">{title}</h3>
      <div className="p-3">{children}</div>
    </section>
  );
}

interface Props {
  row: RecognitionRow | null;
  deviceName: string;
  onClose: () => void;
}

/** Right-hand record details panel. */
export default function RecognitionDrawer({ row, deviceName, onClose }: Props) {
  const [view, setView] = useState<'face' | 'panorama'>('face');
  const [showRaw, setShowRaw] = useState(false);

  // reset per record
  useEffect(() => {
    setView('face');
    setShowRaw(false);
  }, [row?.id]);

  // close on Escape
  useEffect(() => {
    if (!row) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [row, onClose]);

  if (!row) return null;

  const captureSrc = view === 'face' ? row.faceImg : row.panoramaImg;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label="Record details">
      {/* backdrop */}
      <button aria-label="Close" onClick={onClose} className="absolute inset-0 cursor-default bg-black/30" />

      <aside className="relative flex h-full w-full max-w-[440px] flex-col bg-white shadow-xl">
        {/* Summary header */}
        <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="truncate text-[16px] font-semibold">{row.name}</h2>
              <span className="rounded-full bg-[#EEF3FF] px-2 py-0.5 font-mono text-[12px] font-semibold text-pri">
                {row.similarity}%
              </span>
            </div>
            <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-mute">
              <span className="flex items-center gap-1"><Clock size={12} /> <span className="font-mono">{row.time}</span></span>
              <span className="flex items-center gap-1"><Camera size={12} /> {deviceName}</span>
            </p>
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded p-1 text-mute hover:bg-ground">
            <X size={18} />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4 text-[13px]">
          {/* Face comparison */}
          <div className="mb-4">
            <div className="grid grid-cols-2 gap-3">
              <figure>
                <a href={captureSrc} target="_blank" rel="noreferrer" className={captureSrc ? '' : 'pointer-events-none'}>
                  <Img src={captureSrc} alt="Captured" className="aspect-[4/5] w-full rounded-lg bg-ground object-contain" />
                </a>
                <figcaption className="mt-1.5 flex items-center justify-between text-[11.5px] text-mute">
                  Captured
                  {/* small toggle instead of thumbnails */}
                  <span className="inline-flex overflow-hidden rounded border border-line">
                    {(['face', 'panorama'] as const).map((k) => (
                      <button
                        key={k}
                        onClick={() => setView(k)}
                        className={`px-1.5 py-0.5 ${view === k ? 'bg-pri text-white' : 'hover:bg-ground'}`}
                      >
                        {k === 'face' ? 'Face' : 'Scene'}
                      </button>
                    ))}
                  </span>
                </figcaption>
              </figure>
              <figure>
                <a href={row.baseImg} target="_blank" rel="noreferrer" className={row.baseImg ? '' : 'pointer-events-none'}>
                  <Img src={row.baseImg} alt="Library photo" className="aspect-[4/5] w-full rounded-lg bg-ground object-contain" />
                </a>
                <figcaption className="mt-1.5 text-[11.5px] text-mute">Library photo</figcaption>
              </figure>
            </div>
            <div className="mt-3 flex items-center gap-3">
              <span className="shrink-0 text-[12px] text-mute">Similarity</span>
              <ScoreBar value={row.similarity} strong />
              <span className="shrink-0 font-mono text-[12.5px] font-semibold">{row.similarity}</span>
            </div>
          </div>

          <Card title="Person">
            <div className="mb-2 font-medium">{row.name}</div>
            <Chips text={row.groups} />
          </Card>

          <Card title="Event">
            <dl className="grid grid-cols-2 gap-3">
              <div>
                <dt className="text-[11.5px] text-mute">Track ID</dt>
                <dd className="flex items-center gap-1 font-mono text-[12.5px]"><Hash size={12} className="text-mute" />{row.trackId}</dd>
              </div>
              <div>
                <dt className="text-[11.5px] text-mute">Living fraction</dt>
                <dd className="font-mono text-[12.5px]">{row.living}</dd>
              </div>
            </dl>
          </Card>

          {row.attributes.length > 0 && (
            <Card title="Face attributes">
              <dl className="grid grid-cols-2 gap-2">
                {row.attributes.map((a) => (
                  <div key={a.label} className="rounded-md bg-ground px-2.5 py-2">
                    <dt className="text-[11px] text-mute">{a.label}</dt>
                    <dd className="text-[12.5px]">{a.value}</dd>
                  </div>
                ))}
              </dl>
            </Card>
          )}

          <Card title={`Other candidates${row.otherResults.length ? ` · ${row.otherResults.length}` : ''}`}>
            {row.otherResults.length === 0 ? (
              <p className="text-center text-mute">No other candidates</p>
            ) : (
              <ol className="space-y-3">
                {row.otherResults.map((c, i) => (
                  <li key={`${c.personId}-${i}`} className="flex items-center gap-3">
                    <Img src={c.baseImg} alt={`${c.name}`} className="h-10 w-10 shrink-0 rounded-full object-cover" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="truncate font-medium">{c.name}</span>
                        <span className="font-mono text-[12px] text-mute">{c.similarity}</span>
                      </div>
                      <div className="mt-1"><ScoreBar value={c.similarity} /></div>
                      <div className="mt-1 truncate text-[11.5px] text-mute" title={c.groups}>{c.groups}</div>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </Card>

          {/* raw JSON kept for debugging, collapsed by default */}
          <button onClick={() => setShowRaw((s) => !s)} className="text-[12px] text-pri hover:underline">
            {showRaw ? 'Hide raw data' : 'Show raw data'}
          </button>
          {showRaw && (
            <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-ground p-3 font-mono text-[11px]">
              {JSON.stringify(row.raw, null, 2)}
            </pre>
          )}
        </div>
      </aside>
    </div>
  );
}