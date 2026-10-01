import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import AlarmsView from './AlarmsView';
import IncidentDetail from './IncidentDetail';
import { rowsToWindows, windowsToRows } from './RuleFormModal';
import { sampleAlarmStatus, sampleIncident, sampleIncidentDetail } from '@/mocks/handlers';
import { server } from '@/test/setup';

describe('AlarmsView', () => {
  it('lists open alarms and acknowledges one', async () => {
    const user = userEvent.setup();
    let patched: unknown = null;
    server.use(http.patch('/api/alarms/incidents/:id', async ({ request }) => {
      patched = await request.json();
      return HttpResponse.json({ ...sampleIncident, status: 'acknowledged' });
    }));
    render(<AlarmsView />);

    const row = (await screen.findByRole('link', { name: 'Night watch D3' })).closest('tr')!;
    expect(within(row).getByText('IPCAM-D3')).toBeVisible();
    expect(within(row).getByText('Stranger')).toBeVisible();
    expect(within(row).getByText('3 detections')).toBeVisible();
    await user.click(within(row).getByRole('button', { name: 'Acknowledge alarm 41' }));
    await waitFor(() => expect(patched).toEqual({ status: 'acknowledged' }));
  });

  it('explains what is missing without a database', async () => {
    server.use(http.get('/api/alarms/status', () => HttpResponse.json({ ...sampleAlarmStatus, database: false })));
    render(<AlarmsView />);
    expect(await screen.findByText('Alarms need the portal database')).toBeVisible();
  });

  it('warns when email or polling is not working', async () => {
    server.use(http.get('/api/alarms/status', () => HttpResponse.json({
      ...sampleAlarmStatus,
      smtp: { configured: false, host: null, sender: null },
      workers: { ingest: { running: true, last_ok: null, last_error: 'ConnectError: box offline' } },
      notifications: { pending: 2, failed: 0 },
    })));
    render(<AlarmsView />);
    expect(await screen.findByText(/can’t read new detections from the box right now \(ConnectError: box offline\)/)).toBeVisible();
    expect(screen.getByText(/alarms are recorded but not emailed \(2 waiting\)/)).toBeVisible();
  });

  it('shows rules in plain words and creates a new one', async () => {
    const user = userEvent.setup();
    let created: Record<string, unknown> | null = null;
    server.use(http.post('/api/alarms/rules', async ({ request }) => {
      created = await request.json() as Record<string, unknown>;
      return HttpResponse.json({ ...created, id: 8, version: 1 }, { status: 201 });
    }));
    render(<AlarmsView />);
    await user.click(await screen.findByRole('tab', { name: /Rules/ }));

    expect(await screen.findByText('Every day 22:00–06:00')).toBeVisible();
    expect(screen.getByText('IPCAM-D3')).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'New rule' }));
    const dialog = screen.getByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Create rule' }));
    expect(within(dialog).getByText('Give the rule a name.')).toBeVisible();

    await user.type(within(dialog).getByPlaceholderText('e.g. After-hours on D3'), 'After hours D3');
    await user.click(within(dialog).getByRole('button', { name: 'Create rule' }));
    expect(within(dialog).getByText('Pick at least one camera.')).toBeVisible();

    await user.click(within(dialog).getByRole('checkbox', { name: 'IPCAM-D3' }));
    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Who triggers it' }), 'strangers');
    await user.click(within(dialog).getByRole('checkbox', { name: /Guard desk/ }));
    await user.click(within(dialog).getByRole('button', { name: 'Create rule' }));

    await waitFor(() => expect(created).not.toBeNull());
    expect(created).toMatchObject({
      name: 'After hours D3', camera_ids: [2], match_mode: 'strangers', event_kinds: ['stranger'],
      recipient_ids: [1], cooldown_seconds: 300, timezone: 'Asia/Dhaka',
    });
    expect((created!.windows as unknown[]).length).toBe(7);
    expect(await screen.findByText('Created “After hours D3”.')).toBeVisible();
  });

  it('disables the test email until SMTP is set up', async () => {
    const user = userEvent.setup();
    server.use(http.get('/api/alarms/status', () => HttpResponse.json({ ...sampleAlarmStatus, smtp: { configured: false } })));
    render(<AlarmsView />);
    await user.click(await screen.findByRole('tab', { name: /Recipients/ }));
    expect(await screen.findByText('guard@example.org')).toBeVisible();
    expect(screen.getByRole('button', { name: /Send test/ })).toBeDisabled();
  });
});

describe('IncidentDetail', () => {
  it('shows the alarm and who was emailed, and resolves it', async () => {
    const user = userEvent.setup();
    let patched: unknown = null;
    server.use(http.patch('/api/alarms/incidents/:id', async ({ request }) => {
      patched = await request.json();
      return HttpResponse.json({ ...sampleIncident, status: 'resolved' });
    }));
    render(<IncidentDetail incidentRef="41" />);

    expect(await screen.findByText('guard@example.org')).toBeVisible();
    expect(screen.getByText(/^Sent/)).toBeVisible();
    expect(screen.getAllByText('IPCAM-D3').length).toBeGreaterThan(0);
    await user.type(screen.getByPlaceholderText('Shown as who handled it'), 'Nishat');
    await user.click(screen.getByRole('button', { name: 'Resolve' }));
    await waitFor(() => expect(patched).toEqual({ status: 'resolved', note: '', by: 'Nishat' }));
  });

  it('shows an error for an unknown alarm', async () => {
    server.use(http.get('/api/alarms/incidents/:ref', () => HttpResponse.json({ detail: 'No such alarm' }, { status: 404 })));
    render(<IncidentDetail incidentRef="999" />);
    expect(await screen.findByText(/No such alarm/)).toBeVisible();
    expect(sampleIncidentDetail.events).toHaveLength(1);
  });
});

describe('schedule rows', () => {
  it('groups per-day windows by hours and back', () => {
    const windows = [
      { isoDow: 1, start: '22:00', end: '06:00' }, { isoDow: 2, start: '22:00', end: '06:00' },
      { isoDow: 6, start: '00:00', end: '23:59' },
    ];
    const rows = windowsToRows(windows);
    expect(rows).toEqual([{ days: [1, 2], start: '22:00', end: '06:00' }, { days: [6], start: '00:00', end: '23:59' }]);
    expect(rowsToWindows(rows)).toEqual(windows);
  });
});
