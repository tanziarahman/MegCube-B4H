import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import PeopleView from './PeopleView';
import { emptyHandlers, networkFailureHandlers, samplePeople, serverErrorHandlers } from '@/mocks/handlers';
import { server } from '@/test/setup';

describe('PeopleView', () => {
  it('renders server data and opens a profile with keyboard-dismissable details', async () => {
    const user = userEvent.setup();
    render(<PeopleView />);

    expect(await screen.findByText('Ada Lovelace')).toBeVisible();
    expect(screen.getByText('Staff')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Details' }));
    expect(screen.getByRole('dialog')).toHaveTextContent('Face library profile');

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows a loading state before data arrives', async () => {
    server.use(
      http.get('/api/personnel', async () => {
        await new Promise((resolve) => setTimeout(resolve, 30));
        return HttpResponse.json(samplePeople);
      }),
    );
    render(<PeopleView />);

    expect(screen.getByText('Loading face library...')).toBeVisible();
    expect(await screen.findByText('Ada Lovelace')).toBeVisible();
  });

  it('renders the empty state for an empty face library', async () => {
    server.use(emptyHandlers.people);
    render(<PeopleView />);

    expect(await screen.findByText('No people registered')).toBeVisible();
    expect(screen.getByText('0 registered people')).toBeVisible();
  });

  it.each([serverErrorHandlers.people, networkFailureHandlers.people])('shows a recoverable load error', async (handler) => {
    server.use(handler);
    render(<PeopleView />);

    expect(await screen.findByText(/Could not load personnel|Failed to fetch/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Dismiss error' })).toBeEnabled();
  });

  it('enforces required name and photo fields before submitting a new person', async () => {
    const user = userEvent.setup();
    render(<PeopleView />);
    await screen.findByText('Ada Lovelace');
    await user.click(screen.getByRole('button', { name: 'Add person' }));

    const form = screen.getByRole('heading', { name: 'Add person' }).closest('form');
    expect(form).not.toBeNull();
    expect(within(form as HTMLFormElement).getByRole('textbox', { name: 'Name' })).toBeRequired();
    expect(within(form as HTMLFormElement).getByLabelText('Reference photo')).toBeRequired();

    await user.click(within(form as HTMLFormElement).getByRole('button', { name: 'Add person' }));
    expect(screen.getByRole('heading', { name: 'Add person' })).toBeVisible();
  });

});
