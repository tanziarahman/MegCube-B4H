import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import RecognitionTable from './RecognitionTable';
import { emptyHandlers, networkFailureHandlers, sampleRecognition, serverErrorHandlers } from '@/mocks/handlers';
import { server } from '@/test/setup';

describe('RecognitionTable', () => {
  it('renders records and opens a drawer that is dismissible with Escape', async () => {
    const user = userEvent.setup();
    render(<RecognitionTable />);

    expect(await screen.findByText('Ada Lovelace')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Details' }));
    expect(screen.getByRole('dialog', { name: 'Record details' })).toBeVisible();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Record details' })).not.toBeInTheDocument();
  });

  it('shows loading and empty states without relying on timing sleeps', async () => {
    server.use(emptyHandlers.recognition);
    render(<RecognitionTable />);

    expect(screen.getByText('Loading…')).toBeVisible();
    expect(await screen.findByText('No records for these filters.')).toBeVisible();
  });

  it.each([serverErrorHandlers.recognition, networkFailureHandlers.recognition])('shows a retryable network error', async (handler) => {
    server.use(handler);
    render(<RecognitionTable />);

    expect(await screen.findByText(/Couldn’t load records/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeEnabled();
  });

  it('confirms deletion, exposes an alert dialog, and shows pending text', async () => {
    const user = userEvent.setup();
    server.use(
      http.delete('/api/recognition/:alarmId', async () => {
        await new Promise((resolve) => setTimeout(resolve, 30));
        return HttpResponse.json({ deleted: 101 });
      }),
      http.get('/api/recognition', () => HttpResponse.json(sampleRecognition)),
    );
    render(<RecognitionTable />);
    await screen.findByText('Ada Lovelace');
    await user.click(screen.getByRole('button', { name: /Delete the recognition of Ada Lovelace/ }));
    expect(screen.getByRole('alertdialog')).toBeVisible();
    expect(screen.getByRole('alertdialog').querySelector('button:not([aria-label="Cancel"])')).toHaveFocus();
    await user.click(screen.getByRole('button', { name: 'Delete' }));
    expect(await screen.findByRole('button', { name: 'Deleting…' })).toBeDisabled();
  });

  it('closes confirmation with Escape and keeps keyboard focus predictable', async () => {
    const user = userEvent.setup();
    render(<RecognitionTable />);
    await screen.findByText('Ada Lovelace');
    await user.click(screen.getByRole('button', { name: /Delete the recognition of Ada Lovelace/ }));
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });
});
