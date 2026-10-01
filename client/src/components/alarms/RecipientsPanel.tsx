'use client';

import { FormEvent, useState } from 'react';
import { Pencil, Plus, Send, Trash2, UserRound } from 'lucide-react';
import { deleteContact, saveContact, sendTestEmail, type Contact } from '@/lib/alarms';
import { ConfirmDialog, Dialog, ErrorNote, Field, btnCls, inputCls, priBtnCls } from './shared';

function ContactForm({ contact, onClose, onSaved }: { contact: Contact | null; onClose: () => void; onSaved: () => Promise<void> }) {
  const [name, setName] = useState(contact?.name ?? '');
  const [email, setEmail] = useState(contact?.email ?? '');
  const [isActive, setIsActive] = useState(contact?.isActive ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await saveContact({ id: contact?.id, name, email, isActive });
      await onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save');
      setSaving(false);
    }
  };

  return (
    <Dialog eyebrow={contact ? 'Edit recipient' : 'New recipient'} title={contact ? contact.name : 'Add a recipient'} onClose={onClose} busy={saving}>
      <form onSubmit={submit} className="space-y-4 px-6 py-5">
        <Field label="Name"><input value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} className={inputCls} /></Field>
        <Field label="Email"><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required maxLength={254} className={inputCls} /></Field>
        <label className="flex items-center gap-2 text-[14px] text-slate-700">
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} className="h-4 w-4 accent-pri" />
          Receives alarm emails (untick to pause without removing them from rules)
        </label>
        {error && <ErrorNote message={error} />}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} disabled={saving} className={btnCls}>Cancel</button>
          <button type="submit" disabled={saving} className={priBtnCls}>{saving ? 'Saving…' : contact ? 'Save' : 'Add recipient'}</button>
        </div>
      </form>
    </Dialog>
  );
}

export default function RecipientsPanel({ contacts, smtpConfigured, smtpSender, onChanged }: {
  contacts: Contact[]; smtpConfigured: boolean; smtpSender: string | null; onChanged: () => Promise<void>;
}) {
  const [form, setForm] = useState<'new' | Contact | null>(null);
  const [deleting, setDeleting] = useState<Contact | null>(null);
  const [testTo, setTestTo] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; text: string } | null>(null);

  const test = async (e: FormEvent) => {
    e.preventDefault();
    setTesting(true);
    setTestResult(null);
    try {
      await sendTestEmail(testTo);
      setTestResult({ ok: true, text: `Test email sent to ${testTo}. Check the inbox (and spam).` });
    } catch (err) {
      setTestResult({ ok: false, text: err instanceof Error ? err.message : 'Could not send' });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[14px] text-mute">People who can receive alarm emails. Choose who gets what in each rule.</p>
        <button onClick={() => setForm('new')} className={priBtnCls}><Plus size={16} /> Add recipient</button>
      </div>

      {contacts.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-line bg-white py-10 text-[14.5px] text-mute">
          <UserRound size={24} className="text-slate-300" /> No recipients yet.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-line bg-white">
          <table className="w-full text-left text-[14.5px]">
            <thead>
              <tr className="border-b border-line bg-slate-50/70 text-[12.5px] uppercase tracking-wide text-mute">
                <th className="px-4 py-2.5 font-medium">Name</th>
                <th className="px-4 py-2.5 font-medium">Email</th>
                <th className="px-4 py-2.5 font-medium">Rules</th>
                <th className="px-4 py-2.5 font-medium">Emails</th>
                <th className="px-4 py-2.5 font-medium"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {contacts.map((c) => (
                <tr key={c.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-3 font-medium text-slate-800">{c.name}</td>
                  <td className="px-4 py-3 text-slate-700">{c.email}</td>
                  <td className="px-4 py-3 text-slate-700">{c.ruleCount}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-[12.5px] font-medium ${c.isActive ? 'bg-ok-bg text-ok' : 'bg-warn-bg text-warn'}`}>
                      {c.isActive ? 'On' : 'Paused'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1">
                      <button onClick={() => setForm(c)} className="flex h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-xs font-medium hover:bg-ground">
                        <Pencil size={14} /> Edit
                      </button>
                      <button onClick={() => setDeleting(c)} aria-label={`Delete ${c.name}`} className="flex h-8 w-8 items-center justify-center rounded-md text-crit hover:bg-crit-bg">
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <form onSubmit={test} className="rounded-xl border border-line bg-white p-4">
        <p className="font-medium text-slate-800">Send a test email</p>
        <p className="mt-0.5 text-[13.5px] text-mute">
          {smtpConfigured
            ? `Alarm emails are sent from ${smtpSender}. Send a test to check they arrive.`
            : 'Email isn’t set up yet: set SMTP_HOST, SMTP_FROM (and usually SMTP_USER / SMTP_PASSWORD) in fastapi-app/.env, then restart the backend. Alarms are still recorded and their emails wait in the queue.'}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <input type="email" required value={testTo} onChange={(e) => setTestTo(e.target.value)} placeholder="you@example.org"
            aria-label="Test email address" className={`${inputCls} w-72`} />
          <button type="submit" disabled={testing || !smtpConfigured} className={btnCls}><Send size={15} /> {testing ? 'Sending…' : 'Send test'}</button>
        </div>
        {testResult && (
          <p className={`mt-2 text-[13.5px] ${testResult.ok ? 'text-ok' : 'text-crit'}`}>{testResult.text}</p>
        )}
      </form>

      {form && <ContactForm contact={form === 'new' ? null : form} onClose={() => setForm(null)} onSaved={onChanged} />}
      {deleting && (
        <ConfirmDialog title={`Remove ${deleting.name}?`} confirmLabel="Remove"
          message={deleting.ruleCount ? `They will be taken off ${deleting.ruleCount} rule(s) and get no more alarm emails.` : 'They will get no more alarm emails.'}
          onCancel={() => setDeleting(null)} onConfirm={async () => { await deleteContact(deleting.id); await onChanged(); }} />
      )}
    </div>
  );
}
