import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { DeveloperLogin } from '../pages/DeveloperLogin';
import { AuthProvider } from '../context/AuthContext';
import * as authApi from '../api/auth';

vi.mock('../api/auth', () => ({
  loginDeveloper: vi.fn(),
}));

describe('DeveloperLogin Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders login form with username, password fields and login button on white background', () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <DeveloperLogin />
        </AuthProvider>
      </BrowserRouter>
    );

    expect(screen.getByText(/Developer Portal/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/admin/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/••••••••••••/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sign in to Developer Mode/i })).toBeInTheDocument();
  });

  it('displays error message when login fails with invalid credentials', async () => {
    authApi.loginDeveloper.mockRejectedValueOnce({
      response: { data: { detail: 'Invalid username or password' } },
    });

    render(
      <BrowserRouter>
        <AuthProvider>
          <DeveloperLogin />
        </AuthProvider>
      </BrowserRouter>
    );

    const usernameInput = screen.getByPlaceholderText(/admin/i);
    const passwordInput = screen.getByPlaceholderText(/••••••••••••/i);
    const submitBtn = screen.getByRole('button', { name: /Sign in to Developer Mode/i });

    fireEvent.change(usernameInput, { target: { value: 'admin' } });
    fireEvent.change(passwordInput, { target: { value: 'wrongpass' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Invalid username or password/i)).toBeInTheDocument();
    });
  });

  it('successfully authenticates and saves JWT token on valid credentials', async () => {
    authApi.loginDeveloper.mockResolvedValueOnce({
      access_token: 'fake-jwt-token-123',
      token_type: 'bearer',
    });

    render(
      <BrowserRouter>
        <AuthProvider>
          <DeveloperLogin />
        </AuthProvider>
      </BrowserRouter>
    );

    const usernameInput = screen.getByPlaceholderText(/admin/i);
    const passwordInput = screen.getByPlaceholderText(/••••••••••••/i);
    const submitBtn = screen.getByRole('button', { name: /Sign in to Developer Mode/i });

    fireEvent.change(usernameInput, { target: { value: 'admin' } });
    fireEvent.change(passwordInput, { target: { value: 'correctpass' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(localStorage.getItem('developer_token')).toBe('fake-jwt-token-123');
      expect(localStorage.getItem('developer_user')).toBe('admin');
    });
  });
});
