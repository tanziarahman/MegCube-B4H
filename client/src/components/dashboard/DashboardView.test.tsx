import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import DashboardView from './DashboardView';

describe('DashboardView', () => {
  it('renders security activity, camera health, and attention signals', async () => {
    render(<DashboardView />);

    await waitFor(() => expect(screen.getByText('Recognitions')).toBeInTheDocument());

    expect(screen.getByText('Strangers')).toBeInTheDocument();
    expect(screen.getAllByText('12').length).toBeGreaterThan(0);
    expect(screen.getByText('Loading bay is offline')).toBeInTheDocument();
    expect(screen.getAllByText('Entrance camera').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Ada Lovelace').length).toBeGreaterThan(0);
    expect(screen.getByText('Security activity by hour')).toBeInTheDocument();
    expect(screen.getByText('Unique recognized people')).toBeInTheDocument();
    expect(screen.getByText('Tracked strangers, not unique identities')).toBeInTheDocument();
  });
});