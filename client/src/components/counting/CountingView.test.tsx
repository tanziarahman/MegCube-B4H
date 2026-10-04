import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import CountingView from './CountingView';
import { autoGranularity, filterQuery, rangeDays, DEFAULT_FILTERS } from '@/lib/counting';
import { sampleCountingSummary, sampleSighting } from '@/mocks/handlers';
import { server } from '@/test/setup';

const pad = (n: number) => String(n).padStart(2, '0');
const day = (offset: number) => {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

/** Records the query string of every summary request. */
function watchSummary(): URLSearchParams[] {
  const seen: URLSearchParams[] = [];
  server.use(http.get('/api/counting/summary', ({ request }) => {
    seen.push(new URL(request.url).searchParams);
    return HttpResponse.json(sampleCountingSummary);
  }));
  return seen;
}

describe('CountingView', () => {
  it('shows different people from faces, as an estimate with a range', async () => {
    render(<CountingView />);
    const tile = (await screen.findByText('Different people', { selector: 'p' })).closest('div')!.parentElement!;
    expect(within(tile).getByText('≈ 8')).toBeVisible();
    expect(within(tile).getByText('estimate')).toBeVisible();
    expect(within(tile).getByText('Likely 6–10 · from 10 of 12 walk-pasts')).toBeVisible();
    expect(screen.getByText(/told apart by comparing faces and clothing, so it’s an estimate.*2 walk-pasts had no usable picture/)).toBeVisible();
    expect(screen.getByText('9 face + body · 2 face only · 1 body only')).toBeVisible();

    const byCamera = screen.getByRole('heading', { name: 'By camera' }).closest('section')!;
    expect(within(byCamera).getByText('IPCAM-D3').closest('tr')).toHaveTextContent('IPCAM-D3101010');
    expect(screen.getByRole('img', { name: /New people per hour, 24 bars/ })).toBeVisible();
    expect(screen.getByTestId('cell-7-9')).toHaveAttribute('title', expect.stringContaining('8 on average per day'));
  });

  it('counts a person once: new the first time, not again when they come back', async () => {
    const user = userEvent.setup();
    server.use(http.get('/api/counting/sightings', () => HttpResponse.json({ total: 2, page: 1, size: 20, items: [
      { ...sampleSighting, id: 2, first_seen_at: '2026-10-04T05:00:00+00:00', person_no: 1, new_person: false,
        person_first_seen_at: '2026-10-04T03:00:00+00:00' },
      { ...sampleSighting, id: 1, first_seen_at: '2026-10-04T03:00:00+00:00', person_no: 1, new_person: true,
        person_first_seen_at: '2026-10-04T03:00:00+00:00' },
    ] })));
    render(<CountingView />);

    const list = (await screen.findByRole('heading', { name: 'Walk-pasts' })).closest('section')!;
    const [cameBack, first] = await within(list).findAllByText('Person 1');
    expect(within(first.closest('tr')!).getByText('New person')).toBeVisible();
    expect(within(cameBack.closest('tr')!).getByText('Came back')).toBeVisible();
    expect(within(cameBack.closest('tr')!).getByText(/^First seen /)).toBeVisible();

    // The chart counts each person once, when they first appear; walk-pasts are one click away.
    expect(screen.getByRole('button', { name: 'New people' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('Peak 6 new people')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Walk-pasts' }));
    expect(screen.getByRole('img', { name: /Walk-pasts per hour/ })).toBeVisible();
    expect(screen.getByText('Peak 8 walk-pasts')).toBeVisible();
  });

  it('says when a walk-past couldn’t be matched to anyone', async () => {
    server.use(http.get('/api/counting/sightings', () => HttpResponse.json({ total: 1, page: 1, size: 20, items: [
      { ...sampleSighting, person_no: null, new_person: null, person_first_seen_at: null }] })));
    render(<CountingView />);
    expect(await screen.findByText('Can’t tell')).toBeVisible();
  });

  it('says why people can’t be told apart without face matching', async () => {
    server.use(http.get('/api/counting/summary', () => HttpResponse.json({
      ...sampleCountingSummary,
      totals: { ...sampleCountingSummary.totals, face_estimate: null },
      face_matching: { available: false, reason: 'The face models aren’t installed' },
    })));
    render(<CountingView />);
    const tile = (await screen.findByText('Different people', { selector: 'p' })).closest('div')!.parentElement!;
    expect(within(tile).getByText('12')).toBeVisible();
    expect(within(tile).getByText('At most this many · 12 visits')).toBeVisible();
    expect(screen.getByText('People can’t be told apart yet, so different people is the same as walk-pasts for now (The face models aren’t installed).')).toBeVisible();
  });

  it('asks for a shorter period when there are too many faces to compare', async () => {
    server.use(http.get('/api/counting/summary', () => HttpResponse.json({
      ...sampleCountingSummary,
      totals: { ...sampleCountingSummary.totals, face_estimate: { ...sampleCountingSummary.totals.face_estimate,
        people: null, low: null, high: null, too_many: true } },
    })));
    render(<CountingView />);
    expect(await screen.findByText(/too many walk-pasts to compare: pick a shorter period/)).toBeVisible();
  });

  it('drops the estimate label when recognised people are all there is', async () => {
    server.use(http.get('/api/counting/summary', () => HttpResponse.json({
      ...sampleCountingSummary, identity_available: true, totals: { ...sampleCountingSummary.totals, face_estimate: null },
    })));
    render(<CountingView />);
    await screen.findByText('Different people', { selector: 'p' });
    expect(screen.queryByText('estimate')).toBeNull();
    expect(screen.getByText('Exact for recognised people · 12 visits')).toBeVisible();
  });

  it('sends the chosen cameras, period, hours and weekdays', async () => {
    const user = userEvent.setup();
    const seen = watchSummary();
    render(<CountingView />);
    await waitFor(() => expect(seen.length).toBeGreaterThan(0));
    expect(seen.at(-1)!.toString()).toBe('');                 // today: the backend's default

    await user.click(screen.getByRole('button', { name: 'Cameras' }));
    await user.click(await screen.findByRole('checkbox', { name: 'IPCAM-D3' }));
    await user.selectOptions(screen.getByRole('combobox', { name: 'Period' }), 'yesterday');
    await user.selectOptions(screen.getByRole('combobox', { name: 'From hour' }), '22');
    await user.selectOptions(screen.getByRole('combobox', { name: 'To hour' }), '5');
    expect(screen.getByText('past midnight')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Mon' }));
    await user.click(screen.getByRole('button', { name: 'Tue' }));

    await waitFor(() => {
      const q = seen.at(-1)!;
      expect(q.getAll('camera_id')).toEqual(['2']);
      expect(q.get('start')).toBe(`${day(-1)} 00:00:00`);
      expect(q.get('end')).toBe(`${day(0)} 00:00:00`);
      expect(q.get('hours')).toBe('22-5');
      expect(q.get('days')).toBe('1,2');
    });
  });

  it('turns a custom range into box-time start and end', () => {
    const q = filterQuery({ ...DEFAULT_FILTERS, preset: 'custom', fromDate: '2026-10-01', toDate: '2026-10-03' });
    expect(q.get('start')).toBe('2026-10-01 00:00:00');
    expect(q.get('end')).toBe('2026-10-04 00:00:00');                       // through the end of the 3rd
    const withTimes = filterQuery({ ...DEFAULT_FILTERS, preset: 'custom', fromDate: '2026-10-01', fromTime: '09:30',
      toDate: '2026-10-01', toTime: '17:00' });
    expect(withTimes.get('start')).toBe('2026-10-01 09:30:00');
    expect(withTimes.get('end')).toBe('2026-10-01 17:00:00');
    expect(autoGranularity(rangeDays({ ...DEFAULT_FILTERS, preset: 'yesterday' }))).toBe('hour');
    expect(autoGranularity(rangeDays({ ...DEFAULT_FILTERS, preset: 'last30' }))).toBe('day');
  });

  it('says so when no one walked past', async () => {
    server.use(http.get('/api/counting/summary', () => HttpResponse.json({
      ...sampleCountingSummary,
      totals: { ...sampleCountingSummary.totals, walk_pasts: 0, visits: 0, unique_people: 0 },
    })));
    render(<CountingView />);
    expect(await screen.findByText('No one walked past in this period.')).toBeVisible();
  });

  it('shows an error and tries again', async () => {
    const user = userEvent.setup();
    let calls = 0;
    server.use(http.get('/api/counting/summary', () => {
      calls += 1;
      return calls === 1 ? HttpResponse.json({ detail: 'Something broke' }, { status: 500 })
        : HttpResponse.json(sampleCountingSummary);
    }));
    render(<CountingView />);
    expect(await screen.findByText('Couldn’t load the counts: Something broke')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(screen.queryByText(/Something broke/)).toBeNull());
    expect(await screen.findByText('Walk-pasts', { selector: 'p' })).toBeVisible();
  });

  it('explains what is missing without a database', async () => {
    const noDb = () => HttpResponse.json({ detail: 'The database isn\'t configured: set DATABASE_URL in fastapi-app/.env' }, { status: 503 });
    server.use(http.get('/api/counting/summary', noDb), http.get('/api/counting/cameras', noDb));
    render(<CountingView />);
    expect(await screen.findByText('People counting needs the portal database')).toBeVisible();
  });

  it('saves camera settings', async () => {
    const user = userEvent.setup();
    let patched: unknown = null;
    server.use(http.patch('/api/counting/cameras/:id', async ({ params, request }) => {
      patched = { id: params.id, ...(await request.json() as object) };
      return HttpResponse.json({ id: 1, device_id: 1, name: 'Hikvision', deleted: false, count_enabled: false, count_basis: 'merged' });
    }));
    render(<CountingView />);
    await user.click(await screen.findByRole('button', { name: 'Camera settings' }));
    const box = await screen.findByRole('checkbox', { name: 'Include Hikvision in counting' });
    expect(box).toBeChecked();
    await user.click(box);
    await waitFor(() => expect(patched).toEqual({ id: '1', count_enabled: false }));
    await waitFor(() => expect(screen.getByRole('checkbox', { name: 'Include Hikvision in counting' })).not.toBeChecked());

    await user.selectOptions(screen.getByRole('combobox', { name: 'What counts on IPCAM-D3' }), 'face');
    await waitFor(() => expect(patched).toEqual({ id: '2', count_basis: 'face' }));
  });
});
