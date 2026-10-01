import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import CapturesView from './CapturesView';
import { sampleCaptures } from '@/mocks/handlers';
import { server } from '@/test/setup';

describe('CapturesView', () => {
  it('renders captures with their camera name', async () => {
    render(<CapturesView />);

    expect(await screen.findByText('5610081')).toBeVisible();
    // the name appears on the card and in the Device filter
    expect(screen.getAllByText('Entrance camera')).toHaveLength(2);
    expect(screen.getByText('Showing 1–1 of 1')).toBeVisible();
  });

  it('reloads from the backend when Refresh is clicked on page 1', async () => {
    let requests = 0;
    server.use(
      http.get('/api/capture', () => {
        requests += 1;
        return HttpResponse.json(sampleCaptures);
      }),
    );
    const user = userEvent.setup();
    render(<CapturesView />);
    await screen.findByText('5610081');
    expect(requests).toBe(1);

    await user.click(screen.getByRole('button', { name: 'Refresh' }));

    await waitFor(() => expect(requests).toBe(2));
  });
});
