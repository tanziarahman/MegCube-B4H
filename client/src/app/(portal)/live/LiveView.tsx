'use client';

import { useEffect, useRef, useState } from 'react';
import { Maximize2, RefreshCw, VideoOff, X } from 'lucide-react';
import { fetchPreviewCameras, streamUrl, type PreviewCamera } from '@/lib/preview';
import { fetchLatestRecognitions, type RecognitionRow } from '@/lib/recognition';

const LAYOUTS = [1, 4, 9] as const;
type Layout = (typeof LAYOUTS)[number];

const todayRange = () => {
  const d = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  return { start: `${d} 00:00:00`, end: `${d} 23:59:59` };
};

// ---------------------------------------------------------------- one video tile
function Tile({
  camera, selected, single, onSelect, onClose,
}: { camera?: PreviewCamera; selected: boolean; single: boolean; onSelect: () => void; onClose: () => void }) {
  const [retry, setRetry] = useState(0);
  const [failed, setFailed] = useState(false);
  const [hdChoice, setHdChoice] = useState<boolean | null>(null); // null = automatic
  const [fullscreen, setFullscreen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setHdChoice(null); setFailed(false); }, [camera?.id]);
  useEffect(() => {
    const onChange = () => setFullscreen(document.fullscreenElement === boxRef.current);
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  // Grid tiles use the light sub-stream; full screen and the 1-tile layout use the main stream.
  const hd = hdChoice ?? (single || fullscreen);
  useEffect(() => { setFailed(false); }, [hd]);

  return (
    <div
      ref={boxRef}
      onClick={onSelect}
      className={`relative flex min-h-0 items-center justify-center overflow-hidden rounded-md bg-[#1A212B] ${
        selected ? 'ring-2 ring-pri' : ''
      }`}
    >
      {!camera && (
        <p className="px-4 text-center text-[13px] text-[#8D99A8]">
          {selected ? 'Pick a camera from the list' : 'Empty — click to select, then pick a camera'}
        </p>
      )}

      {camera && !failed && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          key={`${hd}-${retry}`}
          src={streamUrl(camera, hd, retry)}
          alt={`Live video from ${camera.name}`}
          onError={() => setFailed(true)}
          className="h-full w-full object-contain"
        />
      )}

      {camera && failed && (
        <div className="flex flex-col items-center gap-2 px-4 text-center text-[13px] text-[#C7D0DA]">
          <VideoOff size={26} />
          <b className="text-white">{camera.name} · no video</b>
          <span>Stream unavailable. Check the camera, and that ffmpeg is installed on the backend.</span>
          <button
            onClick={(e) => { e.stopPropagation(); setFailed(false); setRetry((r) => r + 1); }}
            className="mt-1 flex items-center gap-1.5 rounded-md border border-white/30 px-3 py-1 text-white hover:bg-white/10"
          >
            <RefreshCw size={13} /> Retry
          </button>
        </div>
      )}

      {camera && (
        <div className="absolute inset-x-0 top-0 flex items-center justify-between bg-gradient-to-b from-black/70 to-transparent px-3 py-1.5 text-[12px] text-white">
          <span className="truncate"><b>{camera.name}</b>{camera.task && <span className="opacity-75"> · {camera.task}</span>}</span>
          <span className="flex shrink-0 gap-1">
            <button aria-label={hd ? 'Switch to low resolution' : 'Switch to high resolution'} title={hd ? 'HD (main stream)' : 'SD (sub-stream)'}
              onClick={(e) => { e.stopPropagation(); setHdChoice(!hd); }}
              className={`rounded px-1.5 text-[11px] font-semibold hover:bg-white/20 ${hd ? 'bg-white/25' : ''}`}>{hd ? 'HD' : 'SD'}</button>
            <button aria-label="Reconnect" title="Reconnect" onClick={(e) => { e.stopPropagation(); setFailed(false); setRetry((r) => r + 1); }}
              className="rounded p-1 hover:bg-white/20"><RefreshCw size={14} /></button>
            <button aria-label="Full screen" onClick={(e) => { e.stopPropagation(); boxRef.current?.requestFullscreen(); }}
              className="rounded p-1 hover:bg-white/20"><Maximize2 size={14} /></button>
            <button aria-label="Close video" onClick={(e) => { e.stopPropagation(); onClose(); }}
              className="rounded p-1 hover:bg-white/20"><X size={14} /></button>
          </span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- page body
export default function LiveView() {
  const [cameras, setCameras] = useState<PreviewCamera[]>([]);
  const [camError, setCamError] = useState<string | null>(null);
  const [layout, setLayout] = useState<Layout>(4);
  const [tiles, setTiles] = useState<(number | null)[]>(Array(9).fill(null));
  const [selected, setSelected] = useState(0);
  const [events, setEvents] = useState<RecognitionRow[]>([]);

  // Camera list; start by filling tiles with the online cameras.
  useEffect(() => {
    fetchPreviewCameras()
      .then((list) => {
        setCameras(list);
        const online = list.filter((c) => c.online).map((c) => c.id);
        setTiles(Array.from({ length: 9 }, (_, i) => online[i] ?? null));
      })
      .catch((e) => setCamError(e instanceof Error ? e.message : 'Could not load cameras'));
  }, []);

  // Latest recognitions, refreshed every 5 s (one box request per refresh).
  useEffect(() => {
    const load = () => fetchLatestRecognitions({ ...todayRange(), size: 8 })
      .then(setEvents).catch(() => {});
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const placeCamera = (id: number) => {
    setTiles((t) => {
      const next = [...t];
      const already = next.indexOf(id);
      if (already !== -1 && already < layout) next[already] = null; // move instead of duplicate
      next[selected] = id;
      return next;
    });
    setSelected((s) => (s + 1) % layout);
  };

  const cols = layout === 1 ? 'grid-cols-1' : layout === 4 ? 'grid-cols-2' : 'grid-cols-3';
  const byId = (id: number | null) => cameras.find((c) => c.id === id);

  return (
    <div className="flex flex-col gap-4 xl:h-[calc(100vh-150px)] xl:min-h-[520px] xl:flex-row">
      {/* Camera list */}
      <aside className="flex max-h-64 shrink-0 flex-col rounded-lg border border-line bg-white xl:max-h-none xl:w-60">
        <h2 className="border-b border-line px-4 py-3 text-[13px] font-semibold">Cameras</h2>
        {camError && <p className="p-4 text-[13px] text-crit">{camError}</p>}
        <ul className="flex-1 overflow-y-auto p-2">
          {cameras.map((c) => {
            const onWall = tiles.slice(0, layout).includes(c.id);
            return (
              <li key={c.id}>
                <button
                  disabled={!c.online}
                  onClick={() => placeCamera(c.id)}
                  className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-[13px] hover:bg-ground disabled:cursor-not-allowed disabled:text-mute disabled:hover:bg-transparent"
                  title={c.online ? `Show ${c.name} in the selected tile` : 'Camera offline'}
                >
                  <span className={`h-2 w-2 shrink-0 rounded-full ${c.online ? 'bg-ok' : 'bg-mute'}`} />
                  <span className="flex-1 truncate">{c.name}</span>
                  {onWall && <span className="rounded bg-pri-bg px-1.5 text-[11px] text-pri">on wall</span>}
                </button>
              </li>
            );
          })}
        </ul>
        <p className="border-t border-line p-3 text-[11.5px] leading-snug text-mute">
          Select a tile, then click a camera. Offline cameras are greyed out.
        </p>
      </aside>

      {/* Video wall */}
      <section className="flex h-[65vh] min-h-[360px] min-w-0 flex-1 flex-col gap-3 xl:h-auto xl:min-w-[420px]">
        <div className="flex items-center gap-2">
          <span className="text-[13px] text-mute">Layout</span>
          <div className="flex overflow-hidden rounded-md border border-line bg-white">
            {LAYOUTS.map((l) => (
              <button key={l} onClick={() => { setLayout(l); setSelected(0); }} aria-pressed={layout === l}
                className={`h-8 px-3 text-[13px] ${layout === l ? 'bg-pri-bg font-medium text-pri' : 'hover:bg-ground'}`}>
                {l}
              </button>
            ))}
          </div>
        </div>
        <div className={`grid flex-1 gap-2 ${cols}`} style={{ gridAutoRows: '1fr' }}>
          {tiles.slice(0, layout).map((id, i) => (
            <Tile
              key={i}
              camera={byId(id)}
              selected={selected === i}
              single={layout === 1}
              onSelect={() => setSelected(i)}
              onClose={() => setTiles((t) => t.map((v, j) => (j === i ? null : v)))}
            />
          ))}
        </div>
      </section>

      {/* Latest recognitions */}
      <aside className="flex max-h-80 shrink-0 flex-col rounded-lg border border-line bg-white xl:max-h-none xl:w-72">
        <h2 className="border-b border-line px-4 py-3 text-[13px] font-semibold">Latest recognitions</h2>
        <ul className="flex-1 space-y-2 overflow-y-auto p-3">
          {events.length === 0 && <li className="text-[13px] text-mute">No recognitions yet today.</li>}
          {events.map((e) => (
            <li key={e.id} className="flex gap-3 rounded-md border border-line p-2">
              {e.faceImg
                // eslint-disable-next-line @next/next/no-img-element
                ? <img src={e.faceImg} alt="" className="h-12 w-10 rounded object-cover" />
                : <div className="h-12 w-10 rounded bg-ground" />}
              <div className="min-w-0 text-[12.5px]">
                <p className="truncate font-semibold">{e.name}</p>
                <p className="truncate text-mute">{e.device} · <span className="font-mono">{e.time.slice(11)}</span></p>
                <p className="text-mute">Similarity <span className="font-mono text-ink">{e.similarity}</span></p>
              </div>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}