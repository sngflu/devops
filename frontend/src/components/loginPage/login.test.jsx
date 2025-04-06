import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Login from './login';
import axiosInstance from '../../utils/axios';

vi.mock('../../utils/axios', () => ({
    default: {
        post: vi.fn()
    }
}));

describe('Login Component', () => {
    it('renders login form correctly', () => {
        render(<Login />);

        expect(screen.getByRole('heading', { name: /login/i })).toBeInTheDocument();
        expect(screen.getByPlaceholderText('Username')).toBeInTheDocument();
        expect(screen.getByPlaceholderText('Password')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument();
    });

    it('handles successful login', async () => {
        axiosInstance.post.mockResolvedValue({
            data: { token: 'fake-token' }
        });

        render(<Login />);

        fireEvent.change(screen.getByPlaceholderText('Username'), {
            target: { value: 'testuser' }
        });

        fireEvent.change(screen.getByPlaceholderText('Password'), {
            target: { value: 'password123' }
        });

        fireEvent.click(screen.getByRole('button', { name: /login/i }));

        await waitFor(() => {
            expect(axiosInstance.post).toHaveBeenCalledWith(
                'http://127.0.0.1:5174/login',
                { username: 'testuser', password: 'password123' }
            );
        });
    });
});
