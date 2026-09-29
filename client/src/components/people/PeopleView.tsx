'use client';

import { FormEvent, useEffect, useState } from 'react';
import { Eye, Image as ImageIcon, Pencil, Plus, RefreshCw, Trash2, X } from 'lucide-react';
import {
  createPersonnel,
  deletePersonnel,
  fetchPersonnel,
  fetchPersonnelGroups,
  updatePersonnel,
  type PersonnelGroup,
  type PersonnelRecord,
} from '@/lib/personnel';

const PAGE_SIZE = 10;
type Modal = { kind: 'details' | 'edit' | 'add'; person?: PersonnelRecord } | null;

function displayName(person?: PersonnelRecord) {
  return person?.person_info?.name?.trim() || 'Unnamed person';
}

function Photo({ person, large = false }: { person: PersonnelRecord; large?: boolean }) {
  const [failed, setFailed] = useState(false);
  const name = displayName(person);

  useEffect(() => {
    setFailed(false);
  }, [person.face_image1]);

  if (!person.face_image1 || failed) {
    return <div className={`${large ? 'h-40 w-32 text-4xl' : 'h-14 w-12 text-base'} flex shrink-0 items-center justify-center rounded-md bg-pri-bg font-semibold text-pri`}>{name.slice(0, 1).toUpperCase()}</div>;
  }
  return <img src={person.face_image1} alt={`${name} face`} onError={() => setFailed(true)} className={`${large ? 'h-40 w-32' : 'h-14 w-12'} shrink-0 rounded-md object-cover ring-1 ring-line`} />;
}

export default function PeopleView() {
  const [people, setPeople] = useState<PersonnelRecord[]>([]);
  const [groups, setGroups] = useState<PersonnelGroup[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState<Modal>(null);
  const [saving, setSaving] = useState(false);

  const load = async (nextPage = page) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchPersonnel(nextPage, PAGE_SIZE);
      setPeople(result.person_list);
      setTotal(result.total_count);
      setPage(nextPage);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load personnel');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(1);
    fetchPersonnelGroups().then(setGroups).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!modal || saving) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setModal(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [modal, saving]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!modal) return;
    setSaving(true);
    setError(null);
    try {
      const form = new FormData(event.currentTarget);
      const selected = form.getAll('group_id');
      form.delete('group_id');
      form.set('group_ids', JSON.stringify(selected));
      if (modal.kind === 'edit' && modal.person) await updatePersonnel(modal.person.person_id, form);
      else await createPersonnel(form);
      setModal(null);
      await load(modal.kind === 'add' ? 1 : page);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save person');
    } finally {
      setSaving(false);
    }
  };

  const remove = async (person: PersonnelRecord) => {
    if (!window.confirm(`Delete ${displayName(person)} from the face library?`)) return;
    try {
      await deletePersonnel(person.person_id);
      await load(page > 1 && people.length === 1 ? page - 1 : page);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete person');
    }
  };

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const input = 'mt-1 block h-10 w-full rounded-md border border-line bg-white px-3 text-[13px] outline-none transition focus:border-pri focus:ring-2 focus:ring-pri-bg';
  const modalPerson = modal?.person;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-mute">Manage the face library used for recognition.</p>
          <p className="mt-1 text-xs text-mute">{total} registered {total === 1 ? 'person' : 'people'}</p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => load(page)} title="Refresh personnel" className="flex h-10 items-center gap-2 rounded-md border border-line bg-white px-3 text-[13px] font-medium hover:bg-ground"><RefreshCw size={15} /> Refresh</button>
          <button type="button" onClick={() => setModal({ kind: 'add' })} className="flex h-10 items-center gap-2 rounded-md bg-pri px-4 text-[13px] font-medium text-white shadow-sm hover:bg-[#1A43A0]"><Plus size={16} /> Add person</button>
        </div>
      </div>

      {error && <div className="flex items-center justify-between rounded-md border border-crit/20 bg-crit-bg px-3 py-2 text-[13px] text-crit"><span>{error}</span><button type="button" onClick={() => setError(null)} aria-label="Dismiss error"><X size={15} /></button></div>}

      <div className="overflow-hidden rounded-lg border border-line bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-[13px]">
            <thead className="border-b border-line bg-[#F8F9FB] text-left text-[11px] uppercase tracking-[0.06em] text-mute"><tr><th className="px-5 py-3 font-semibold">Person</th><th className="px-5 py-3 font-semibold">Code</th><th className="px-5 py-3 font-semibold">Groups</th><th className="px-5 py-3 font-semibold">Person ID</th><th className="px-5 py-3 text-right font-semibold">Actions</th></tr></thead>
            <tbody>
              {loading && <tr><td colSpan={5} className="px-5 py-16 text-center text-mute">Loading face library...</td></tr>}
              {!loading && !people.length && <tr><td colSpan={5} className="px-5 py-16 text-center"><ImageIcon className="mx-auto mb-2 text-mute" size={25} /><p className="font-medium">No people registered</p><p className="mt-1 text-mute">Add a reference photo to start recognition.</p></td></tr>}
              {!loading && people.map((person) => <tr key={person.person_id} className="border-b border-line last:border-0 hover:bg-[#FBFCFE]">
                <td className="px-5 py-3"><div className="flex items-center gap-3"><Photo person={person} /><div><p className="font-semibold text-ink">{displayName(person)}</p><p className="mt-0.5 text-xs text-mute">{person.person_info?.birthday || 'No birthday recorded'}</p></div></div></td>
                <td className="px-5 py-3 font-mono text-xs text-mute">{person.person_info?.code || '-'}</td>
                <td className="px-5 py-3"><div className="flex max-w-[260px] flex-wrap gap-1.5">{person.groups?.length ? person.groups.map((group) => <span key={group.group_id} className="rounded-full bg-pri-bg px-2 py-1 text-xs font-medium text-pri">{group.group_name}</span>) : <span className="text-mute">Unassigned</span>}</div></td>
                <td className="px-5 py-3 font-mono text-xs text-mute">#{person.person_id}</td>
                <td className="px-5 py-3"><div className="flex justify-end gap-1"><button type="button" onClick={() => setModal({ kind: 'details', person })} title="View details" className="flex h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-xs font-medium hover:bg-ground"><Eye size={14} /> Details</button><button type="button" onClick={() => setModal({ kind: 'edit', person })} title="Edit person" className="flex h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-xs font-medium hover:bg-ground"><Pencil size={14} /> Edit</button><button type="button" onClick={() => remove(person)} title="Delete person" aria-label={`Delete ${displayName(person)}`} className="flex h-8 w-8 items-center justify-center rounded-md text-crit hover:bg-crit-bg"><Trash2 size={15} /></button></div></td>
              </tr>)}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-line px-5 py-3 text-[13px]"><span className="text-mute">Page {page} of {pages}</span><div className="flex gap-2"><button disabled={page <= 1 || loading} onClick={() => load(page - 1)} className="h-8 rounded-md border border-line px-3 disabled:opacity-40">Previous</button><button disabled={page >= pages || loading} onClick={() => load(page + 1)} className="h-8 rounded-md border border-line px-3 disabled:opacity-40">Next</button></div></div>
      </div>

      {modal?.kind === 'details' && modalPerson && <div role="dialog" aria-modal="true" aria-labelledby="person-details-title" className="fixed inset-0 z-50 flex items-center justify-center bg-[#0F1621]/45 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) setModal(null); }}><div className="w-full max-w-xl rounded-lg bg-white shadow-2xl"><div className="flex items-start justify-between border-b border-line px-6 py-5"><div><p className="text-xs font-semibold uppercase tracking-[0.08em] text-pri">Face library profile</p><h2 id="person-details-title" className="mt-1 text-xl font-semibold">{displayName(modalPerson)}</h2></div><button type="button" onClick={() => setModal(null)} aria-label="Close details" className="rounded-md p-1.5 text-mute hover:bg-ground"><X size={18} /></button></div><div className="grid gap-6 px-6 py-6 sm:grid-cols-[128px_1fr]"><Photo person={modalPerson} large /><dl className="grid grid-cols-2 gap-x-5 gap-y-4 text-sm"><div><dt className="text-xs text-mute">Person ID</dt><dd className="mt-1 font-mono">#{modalPerson.person_id}</dd></div><div><dt className="text-xs text-mute">Code</dt><dd className="mt-1">{modalPerson.person_info?.code || '-'}</dd></div><div><dt className="text-xs text-mute">Birthday</dt><dd className="mt-1">{modalPerson.person_info?.birthday || '-'}</dd></div><div><dt className="text-xs text-mute">Groups</dt><dd className="mt-1">{modalPerson.groups?.map((group) => group.group_name).join(', ') || 'Unassigned'}</dd></div><div className="col-span-2"><dt className="text-xs text-mute">Remarks</dt><dd className="mt-1">{modalPerson.person_info?.remarks || 'No remarks recorded.'}</dd></div></dl></div><div className="flex justify-end gap-2 border-t border-line px-6 py-4"><button type="button" onClick={() => setModal({ kind: 'edit', person: modalPerson })} className="flex h-9 items-center gap-1.5 rounded-md bg-pri px-3 text-[13px] font-medium text-white"><Pencil size={14} /> Edit person</button></div></div></div>}

      {(modal?.kind === 'add' || modal?.kind === 'edit') && <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0F1621]/45 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget && !saving) setModal(null); }}><form onSubmit={submit} className="w-full max-w-xl rounded-lg bg-white shadow-2xl"><div className="flex items-start justify-between border-b border-line px-6 py-5"><div><p className="text-xs font-semibold uppercase tracking-[0.08em] text-pri">{modal.kind === 'edit' ? 'Update record' : 'New record'}</p><h2 className="mt-1 text-xl font-semibold">{modal.kind === 'edit' ? `Edit ${displayName(modalPerson)}` : 'Add person'}</h2></div><button type="button" disabled={saving} onClick={() => setModal(null)} aria-label="Close form" className="rounded-md p-1.5 text-mute hover:bg-ground"><X size={18} /></button></div><div className="grid gap-4 px-6 py-5 sm:grid-cols-2"><label className="text-xs font-medium text-mute">Name<input required name="name" defaultValue={modalPerson?.person_info?.name || ''} className={input} /></label><label className="text-xs font-medium text-mute">Reference photo<input required={modal.kind === 'add'} accept="image/*" type="file" name="photo" className={`${input} px-2 py-2 text-xs`} />{modal.kind === 'edit' && <span className="mt-1 block text-[11px] text-mute">Leave empty to keep the current photo.</span>}</label><label className="text-xs font-medium text-mute">Code<input name="code" defaultValue={modalPerson?.person_info?.code || ''} className={input} /></label><label className="text-xs font-medium text-mute">Birthday<input type="date" name="birthday" defaultValue={modalPerson?.person_info?.birthday || ''} className={input} /></label><fieldset className="sm:col-span-2"><legend className="text-xs font-medium text-mute">Groups</legend><div className="mt-2 flex flex-wrap gap-2">{groups.map((group) => <label key={group.group_id} className="flex cursor-pointer items-center gap-2 rounded-md border border-line px-3 py-2 text-xs hover:bg-ground"><input type="checkbox" name="group_id" value={group.group_id} defaultChecked={modalPerson?.groups?.some((item) => item.group_id === group.group_id)} className="accent-[#1F4FB5]" />{group.group_name}</label>)}</div></fieldset><label className="text-xs font-medium text-mute sm:col-span-2">Remarks<textarea name="remarks" defaultValue={modalPerson?.person_info?.remarks || ''} rows={3} className={`${input} h-auto py-2`} /></label></div><div className="flex justify-end gap-2 border-t border-line px-6 py-4"><button type="button" disabled={saving} onClick={() => setModal(null)} className="h-9 rounded-md border border-line px-3 text-[13px]">Cancel</button><button disabled={saving} className="h-9 rounded-md bg-pri px-4 text-[13px] font-medium text-white disabled:opacity-50">{saving ? 'Saving...' : modal.kind === 'edit' ? 'Save changes' : 'Add person'}</button></div></form></div>}
    </div>
  );
}