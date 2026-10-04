'use client';

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { BASIS_LABELS, updateCountingCamera, type CountBasis, type CountingCamera } from '@/lib/counting';
import { ErrorNote, inputCls } from '@/components/alarms/shared';

/** Per camera: include it in counting, and which walk-pasts count. Collapsed by default. */
export default function CameraSettings({ cameras, onChanged }: {
  cameras: CountingCamera[]; onChanged: (camera: CountingCamera) => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const save = async (id: number, change: { countEnabled?: boolean; countBasis?: CountBasis }) => {
    setBusy(id);
    setError(null);
    try {
      onChanged(await updateCountingCamera(id, change));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save the camera setting');
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="rounded-xl border border-line bg-white">
      <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-left">
        <span className="text-[15px] font-semibold text-slate-800">Camera settings</span>
        <ChevronDown size={18} className={`text-mute transition ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="space-y-3 border-t border-line px-4 py-4">
          <p className="text-[13px] text-mute">
            Cameras left out still record walk-pasts; they just aren’t in the totals unless you pick them in the camera filter.
          </p>
          {error && <ErrorNote message={error} />}
          <div className="divide-y divide-line">
            {cameras.filter((c) => !c.deleted).map((c) => (
              <div key={c.id} className="flex flex-wrap items-center gap-4 py-3">
                <span className="w-40 font-medium text-slate-800">{c.name}</span>
                <label className="flex items-center gap-2 text-[14px] text-slate-700">
                  <input type="checkbox" checked={c.countEnabled} disabled={busy === c.id}
                    aria-label={`Include ${c.name} in counting`}
                    onChange={(e) => save(c.id, { countEnabled: e.target.checked })} />
                  Include in counting
                </label>
                <select aria-label={`What counts on ${c.name}`} value={c.countBasis} disabled={busy === c.id}
                  onChange={(e) => save(c.id, { countBasis: e.target.value as CountBasis })} className={`${inputCls} w-72`}>
                  {(Object.keys(BASIS_LABELS) as CountBasis[]).map((b) => <option key={b} value={b}>{BASIS_LABELS[b]}</option>)}
                </select>
              </div>
            ))}
            {!cameras.length && <p className="py-3 text-[14px] text-mute">No cameras yet: they appear once the backend has synced with the box.</p>}
          </div>
        </div>
      )}
    </section>
  );
}
