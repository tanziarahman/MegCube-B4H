import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import DevicesTable from './DevicesTable';
import { emptyHandlers, networkFailureHandlers, sampleDevices, serverErrorHandlers } from '@/mocks/handlers';
import { server } from '@/test/setup';

describe('DevicesTable', () => {
  it('renders online/offline status, filters by name, and resets filters', async () => {
    const user = userEvent.setup();
    render(<DevicesTable />);

    expect(await screen.findByText('Entrance camera')).toBeVisible();
    expect(screen.getByText('Loading bay')).toBeVisible();
    expect(screen.getAllByText('Online').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Offline').length).toBeGreaterThan(0);

    await user.type(screen.getByPlaceholderText('e.g. Hikvision'), 'Entrance');
    expect(screen.getByText('Showing 1 of 2 cameras')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Reset' }));
    expect(screen.getByText('Loading bay')).toBeVisible();
  });

  it('shows skeleton loading and an empty state', async () => {
    server.use(emptyHandlers.devices);
    render(<DevicesTable />);

    expect(screen.getAllByRole('button', { name: 'New device' })).toHaveLength(1);
    expect(await screen.findByText('No cameras are configured on the box.')).toBeVisible();
  });

  it.each([serverErrorHandlers.devices, networkFailureHandlers.devices])('shows an error and exposes retry', async (handler) => {
    server.use(handler);
    render(<DevicesTable />);

    expect(await screen.findByText(/Couldn’t load devices/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeEnabled();
  });

  it('validates RTSP input and supports keyboard Escape dismissal', async () => {
    const user = userEvent.setup();
    render(<DevicesTable />);
    await screen.findByText('Entrance camera');
    await user.click(screen.getByRole('button', { name: 'New device' }));

    await user.selectOptions(screen.getByRole('combobox', { name: /Device type/ }), 'video');
    await user.selectOptions(screen.getByRole('combobox', { name: /Protocol/ }), 'rtsp');
    const url = screen.getByRole('textbox', { name: /RTSP address/ });
    expect(url).toBeRequired();
    expect(url).toHaveAttribute('pattern', 'rtsp://.+');
    await user.type(url, 'http://not-rtsp');
    expect(url).toBeInvalid();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('submits a valid device form and shows pending UI', async () => {
    const user = userEvent.setup();
    server.use(
      http.post('/api/devices', async () => {
        await new Promise((resolve) => setTimeout(resolve, 30));
        return HttpResponse.json({ device_id: 3 }, { status: 201 });
      }),
      http.get('/api/devices/detail', () => HttpResponse.json(sampleDevices)),
    );
    render(<DevicesTable />);
    await screen.findByText('Entrance camera');
    await user.click(screen.getByRole('button', { name: 'New device' }));
    const dialog = screen.getByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /Device name/ }), 'Warehouse camera');
    await user.selectOptions(within(dialog).getByRole('combobox', { name: /Device type/ }), 'video');
    await user.selectOptions(within(dialog).getByRole('combobox', { name: /Protocol/ }), 'rtsp');
    await user.type(within(dialog).getByRole('textbox', { name: /RTSP address/ }), 'rtsp://192.168.1.30/stream');
    await user.click(within(dialog).getByRole('button', { name: 'Add device' }));

    expect(await screen.findByText('Added “Warehouse camera” as device #3.')).toBeVisible();
  });
});
