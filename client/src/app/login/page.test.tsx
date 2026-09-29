import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import LoginPage from './page';

const push = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
}));

describe('LoginPage', () => {
  beforeEach(() => push.mockReset());

  it('signs in with valid credentials and navigates to the dashboard', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByRole('textbox', { name: 'Username' }), 'operator');
    await user.type(screen.getByLabelText('Password'), 'admin');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(push).toHaveBeenCalledWith('/');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('shows a validation error for an invalid or empty password without navigating', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByRole('textbox', { name: 'Username' }), '<script>alert(1)</script>');
    await user.type(screen.getByLabelText('Password'), 'wrong');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(screen.getByRole('alert')).toHaveTextContent('Incorrect username or password.');
    expect(push).not.toHaveBeenCalled();
  });

  it('keeps native keyboard navigation and password semantics accessible', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.tab();
    expect(screen.getByRole('textbox', { name: 'Username' })).toHaveFocus();
    await user.tab();
    expect(screen.getByLabelText('Password')).toHaveFocus();
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password');
  });
});
