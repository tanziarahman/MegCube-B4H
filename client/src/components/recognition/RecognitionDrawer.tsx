'use client';

import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
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

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-3 flex items-center gap-2 text-[14px] font-medium">
      <span className="h-4 w-[3px] rounded-full bg-pri" />
      {children}
    </h3>
  );
}

interface Props {
  row: RecognitionRow | null;
  deviceName: string;
  onClose: () => void;
}

/** Right-hand "Record details" panel, modelled on the box's own record details view. */
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

  const details: { label: string; value: string; mono?: boolean }[] = [
    { label: 'Capture device', value: deviceName },
    { label: 'Capture time', value: row.time, mono: true },
    { label: 'Name', value: row.name },
    { label: 'Group', value: row.groups },
    { label: 'Similarity', value: row.similarity, mono: true },
    { label: 'Living fraction', value: row.living, mono: true },
    { label: 'Track ID', value: row.trackId, mono: true },
    ...row.attributes,
  ];

  const bigSrc = view === 'face' ? row.faceImg : row.panoramaImg;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label="Record details">
      {/* backdrop */}
      <button aria-label="Close" onClick={onClose} className="absolute inset-0 cursor-default bg-black/30" />

      <aside className="relative flex h-full w-full max-w-[460px] flex-col bg-white shadow-xl">
        <header className="flex items-center justify-between border-b border-line px-5 py-4">
          <h2 className="text-[15px] font-semibold">Record details</h2>
          <button onClick={onClose} aria-label="Close" className="rounded p-1 text-mute hover:bg-ground">
            <X size={18} />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4 text-[13px]">
          {/* Recognition info */}
          <SectionTitle>Recognition info</SectionTitle>

          <div className="mb-1 grid grid-cols-2 gap-2 text-[12px] text-mute">
            <span>{view === 'face' ? 'Capture image' : 'Panoramic'}</span>
            <span>Base image</span>
          </div>
          <div className="relative mb-5 grid grid-cols-2 gap-2">
            <a href={bigSrc} target="_blank" rel="noreferrer" className={bigSrc ? '' : 'pointer-events-none'}>
              <Img src={bigSrc} alt={view === 'face' ? 'Capture image' : 'Panoramic'} className="h-52 w-full rounded bg-ground object-contain" />
            </a>
            <a href={row.baseImg} target="_blank" rel="noreferrer" className={row.baseImg ? '' : 'pointer-events-none'}>
              <Img src={row.baseImg} alt="Base image" className="h-52 w-full rounded bg-ground object-contain" />
            </a>
            <span className="absolute -bottom-3 left-1/2 -translate-x-1/2 rounded bg-pri px-3 py-0.5 font-mono text-[13px] font-semibold text-white">
              {row.similarity}
            </span>
          </div>

          {/* thumbnails switch the big image */}
          <div className="mb-5 flex gap-3">
            {([
              ['face', row.faceImg, 'Capture image'],
              ['panorama', row.panoramaImg, 'Panoramic'],
            ] as const).map(([key, src, text]) => (
              <button
                key={key}
                onClick={() => setView(key)}
                className={`flex flex-col items-center gap-1 text-[11.5px] ${view === key ? 'text-pri' : 'text-mute'}`}
              >
                <Img
                  src={src}
                  alt={text}
                  className={`h-[72px] w-[72px] rounded object-cover ring-2 ${view === key ? 'ring-pri' : 'ring-transparent'}`}
                />
                {text}
              </button>
            ))}
          </div>

          <dl className="mb-6 grid grid-cols-[120px_1fr] gap-x-3 gap-y-2">
            {details.map((d) => (
              <div key={d.label} className="contents">
                <dt className="text-mute">{d.label}</dt>
                <dd className={`break-words ${d.mono ? 'font-mono text-[12.5px]' : ''}`}>{d.value || '—'}</dd>
              </div>
            ))}
          </dl>

          {/* Other results */}
          <SectionTitle>Other results</SectionTitle>
          {row.otherResults.length === 0 ? (
            <p className="mb-6 rounded bg-ground px-3 py-4 text-center text-mute">No other candidates</p>
          ) : (
            <table className="mb-6 w-full">
              <thead className="bg-[#F7F8FA] text-left text-[12px] text-mute">
                <tr>
                  <th className="px-2 py-2 font-medium">Base image</th>
                  <th className="px-2 py-2 font-medium">Similarity</th>
                  <th className="px-2 py-2 font-medium">Name</th>
                  <th className="px-2 py-2 font-medium">Group</th>
                </tr>
              </thead>
              <tbody>
                {row.otherResults.map((c, i) => (
                  <tr key={`${c.personId}-${i}`} className="border-t border-line align-middle">
                    <td className="px-2 py-2">
                      <Img src={c.baseImg} alt={`${c.name} base image`} className="h-[48px] w-[40px] rounded object-cover" />
                    </td>
                    <td className="px-2 py-2 font-mono">{c.similarity}</td>
                    <td className="px-2 py-2">{c.name}</td>
                    <td className="max-w-[120px] truncate px-2 py-2" title={c.groups}>{c.groups}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

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
