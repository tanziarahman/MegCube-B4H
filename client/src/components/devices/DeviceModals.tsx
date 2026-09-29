'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import { AlertCircle, Eye, EyeOff, X } from 'lucide-react';
import type { DeviceDetail } from '@/lib/devices';

// Which box writes are wired. Adding, editing and deleting all use the box's captured requests.
export const CREATE_READY = true;
export const UPDATE_READY = true;
export const DELETE_READY = true;
const NOT_READY_NOTE = 'Saving to the box isn’t connected yet.';

// Options the box is known to use. Add more here once the box's lists are captured.
const DEVICE_TYPES = [
  { value: 'video', label: 'Video' },
  { value: 'picture', label: 'Picture' },
];
// Only the Video "New device" request has been captured so far.
const ADDABLE_TYPES = ['video'];
const PROTOCOLS = [
  { value: 'rtsp', label: 'RTSP' },
  { value: 'gb28181', label: 'GB28181' },
];
// Only the RTSP "New device" request has been captured so far.
const ADDABLE_PROTOCOLS = ['rtsp'];

const input =
  'mt-1 block w-full rounded-lg border border-line bg-white px-3 py-2.5 text-[14.5px] text-slate-700 outline-none transition focus:border-pri disabled:bg-ground disabled:text-mute';
const label = 'text-[13px] font-medium text-mute';

export interface DeviceFormValues {
  name: string;
  type: string;
  protocol: string;
  url: string;       // rtsp://host:port/path, without credentials
  user: string;
  password: string;  // empty on edit = keep current
}

/** Split a masked address (rtsp://user:****@host/path) into a credential-free URL and the user name. */
function fromAddress(address: string): { url: string; user: string } {
  try {
    const u = new URL(address.replace(/^rtsp:/i, 'http:'));
    const host = u.port ? `${u.hostname}:${u.port}` : u.hostname;
    return { url: `rtsp://${host}${u.pathname}${u.search}`, user: decodeURIComponent(u.username) };
  } catch {
    return { url: '', user: '' };
  }
}

function Shell({ eyebrow, title, onClose, busy, children }: {
  eyebrow: string; title: string; onClose: () => void; busy?: boolean; children: React.ReactNode;
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
    >
      <div className="w-full max-w-lg rounded-lg bg-white shadow-2xl">
        <div className="flex items-start justify-between border-b border-line px-6 py-5">
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

/** New device / Edit device form (same fields as the box's "New device" dialog). */
export function DeviceFormModal({ device, onClose, onSubmit }: {
  device: DeviceDetail | null;            // null = new device
  onClose: () => void;
  onSubmit?: (values: DeviceFormValues) => Promise<void>;
}) {
  const editing = device !== null;
  const typeValue = editing ? DEVICE_TYPES.find((t) => t.label === device.type)?.value ?? '' : '';
  const [type, setType] = useState(typeValue);
  const initial = editing ? fromAddress(device.address) : { url: '', user: '' };
  const [protocol, setProtocol] = useState(editing ? device.protocol.toLowerCase() : '');
  const typeSupported = !type || ADDABLE_TYPES.includes(type);
  const protocolSupported = !protocol || ADDABLE_PROTOCOLS.includes(protocol);
  const ready = (editing ? UPDATE_READY : CREATE_READY) && typeSupported && protocolSupported;
  const [saving, setSaving] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!ready || !onSubmit) return;
    const f = new FormData(e.currentTarget);
    const values: DeviceFormValues = {
      name: String(f.get('name') ?? '').trim(),
      type,
      protocol,
      url: String(f.get('url') ?? '').trim(),
      user: String(f.get('user') ?? '').trim(),
      password: String(f.get('password') ?? ''),
    };
    setSaving(true);
    setError(null);
    try {
      await onSubmit(values);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the device');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Shell
      eyebrow={editing ? 'Update device' : 'New device'}
      title={editing ? `Edit ${device.name}` : 'Add device'}
      onClose={onClose}
      busy={saving}
    >
      <form onSubmit={submit} autoComplete="off" data-lpignore="true" data-1p-ignore="true">
        <div className="grid gap-4 px-6 py-5">
          <label className={label}>
            Device ID
            <input disabled value={editing ? `#${device.id}` : ''} placeholder="Assigned automatically" className={input} />
          </label>

          <label className={label}>
            Device name <span className="text-crit">*</span>
            <input required name="name" defaultValue={editing ? device.name : ''} placeholder="e.g. Entrance camera" className={input} />
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className={label}>
              Device type <span className="text-crit">*</span>
              <select required name="type" value={type} onChange={(e) => setType(e.target.value)} className={input}>
                <option value="" disabled>Please select</option>
                {DEVICE_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </label>
            <label className={label}>
              Protocol <span className="text-crit">*</span>
              <select required name="protocol" value={protocol} onChange={(e) => setProtocol(e.target.value)} className={input}>
                <option value="" disabled>Please select</option>
                {PROTOCOLS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </label>
          </div>

          {/* stream settings appear once a protocol is chosen, like on the box */}
          {protocol === 'rtsp' && (
            <div className="grid gap-4 rounded-lg border border-line bg-slate-50/60 p-4">
              <label className={label}>
                RTSP address <span className="text-crit">*</span>
                <input
                  required
                  name="url"
                  defaultValue={initial.url}
                  placeholder="rtsp://192.168.90.24:554/ISAPI/Streaming/channels/201"
                  pattern="rtsp://.+"
                  title="Must start with rtsp://"
                  className={`${input} font-mono text-[13.5px]`}
                />
              </label>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className={label}>
                  Username
                  <input name="user" defaultValue={initial.user} autoComplete="off" data-lpignore="true" data-1p-ignore="true" spellCheck={false} className={input} />
                </label>
                <label className={label}>
                  Password
                  <div className="relative">
                    {/* Deliberately a text field, masked with CSS: a real type="password" field makes the
                        browser offer to save these camera credentials as if they were a site login. */}
                    <input
                      name="password"
                      type="text"
                      autoComplete="off"
                      data-lpignore="true"
                      data-1p-ignore="true"
                      spellCheck={false}
                      style={showPassword ? undefined : ({ WebkitTextSecurity: 'disc' } as React.CSSProperties)}
                      className={`${input} pr-10`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      className="absolute right-2 top-1/2 mt-0.5 -translate-y-1/2 rounded p-1 text-mute hover:bg-ground"
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                  {editing && <span className="mt-1 block text-[12px] text-mute">Leave empty to keep the current password.</span>}
                </label>
              </div>
            </div>
          )}

          {protocol === 'gb28181' && (
            <p className="rounded-lg border border-dashed border-line bg-slate-50/60 px-4 py-3 text-[13.5px] text-mute">
              GB28181 cameras register with the box using IDs instead of a stream address. Their
              settings will appear here once that part is connected.
            </p>
          )}

          {error && <p className="rounded-md bg-crit-bg px-3 py-2 text-[13px] text-crit">{error}</p>}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-line px-6 py-4">
          {!ready && (
            <span className="mr-auto text-[12.5px] text-mute">
              {!typeSupported
                ? `${editing ? 'Editing' : 'Adding'} Picture devices isn’t connected yet.`
                : !protocolSupported
                  ? `${editing ? 'Editing' : 'Adding'} GB28181 devices isn’t connected yet.`
                  : NOT_READY_NOTE}
            </span>
          )}
          <button type="button" disabled={saving} onClick={onClose} className="h-9 rounded-md border border-line px-3 text-[13.5px] hover:bg-ground">
            Cancel
          </button>
          <button
            disabled={saving || !ready}
            className="h-9 rounded-md bg-pri px-4 text-[13.5px] font-medium text-white disabled:opacity-50"
          >
            {saving ? 'Saving…' : editing ? 'Save changes' : 'Add device'}
          </button>
        </div>
      </form>
    </Shell>
  );
}

/** "Are you sure?" dialog for deleting a device (same look as the Recognition delete dialog). */
export function ConfirmDeleteDevice({ device, onCancel, onConfirm }: {
  device: DeviceDetail;
  onCancel: () => void;
  onConfirm?: () => Promise<void>;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    cancelRef.current?.focus();   // safe default: Enter cancels, not deletes
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && !busy && onCancel();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [busy, onCancel]);

  const confirm = async () => {
    if (!DELETE_READY || !onConfirm) return;
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
      onCancel();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete the device');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" role="alertdialog" aria-modal="true" aria-labelledby="del-dev-title">
      <button aria-label="Cancel" onClick={() => !busy && onCancel()} className="absolute inset-0 cursor-default bg-black/40" />
      <div className="relative w-full max-w-[420px] rounded-lg bg-white p-5 shadow-xl">
        <div className="flex gap-3">
          <AlertCircle size={22} className="mt-0.5 shrink-0 text-[#F59E0B]" />
          <div>
            <h2 id="del-dev-title" className="text-[16px] font-medium">Are you sure you want to delete this device?</h2>
            <p className="mt-1 text-[13.5px] text-mute">
              {device.name} (#{device.id}). The box will stop analysing this camera. This can&apos;t be undone.
            </p>
            {error && <p className="mt-2 text-[13px] text-crit">{error}</p>}
            {!DELETE_READY && <p className="mt-2 text-[12.5px] text-mute">{NOT_READY_NOTE.replace('Saving to', 'Deleting on')}</p>}
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button ref={cancelRef} onClick={onCancel} disabled={busy} className="h-9 rounded-md border border-line bg-white px-4 text-[13.5px] hover:bg-ground disabled:opacity-40">
            Cancel
          </button>
          <button
            onClick={confirm}
            disabled={busy || !DELETE_READY}
            className="h-9 rounded-md bg-[#E5484D] px-4 text-[13.5px] font-medium text-white hover:bg-[#D13A3F] disabled:opacity-50"
          >
            {busy ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  );
}