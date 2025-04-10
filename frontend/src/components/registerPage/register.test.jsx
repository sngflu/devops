import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Register from './register';
import axiosInstance from '../../utils/axios';

vi.mock('../../utils/axios', () => ({
    default: {
        post: vi.fn()
    }
}));

describe('Register Component', () => {
    it('renders register form correctly', () => {
        render(<Register />);

        expect(screen.getByRole('heading', { name: /register/i })).toBeInTheDocument();
        expect(screen.getByPlaceholderText('Username')).toBeInTheDocument();
        expect(screen.getByPlaceholderText('Password')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /register/i })).toBeInTheDocument();
    });

    it('handles successful registration', async () => {
        axiosInstance.post.mockResolvedValue({
            data: { token: 'fake-token' }
        });

        render(<Register />);

        fireEvent.change(screen.getByPlaceholderText('Username'), {
            target: { value: 'newuser' }
        });

        fireEvent.change(screen.getByPlaceholderText('Password'), {
            target: { value: 'newpassword' }
        });

        fireEvent.click(screen.getByRole('button', { name: /register/i }));

        await waitFor(() => {
            expect(axiosInstance.post).toHaveBeenCalledWith(
                'http://127.0.0.1:5174/register',
                { username: 'newuser', password: 'newpassword' }
            );
        });
    });

    it('displays an error message if registration fails', async () => {
        const errorMessage = 'Username already taken';
        axiosInstance.post.mockRejectedValue({
            response: { data: { message: errorMessage } }
        });

        render(<Register />);

        fireEvent.change(screen.getByPlaceholderText('Username'), {
            target: { value: 'newuser' }
        });

        fireEvent.change(screen.getByPlaceholderText('Password'), {
            target: { value: 'newpassword' }
        });

        fireEvent.click(screen.getByRole('button', { name: /register/i }));

        await waitFor(() => {
            expect(screen.getByText(errorMessage)).toBeInTheDocument();
        });
    });

    it('sets and displays the error message if registration fails due to missing message', async () => {
        const defaultErrorMessage = 'Registration failed';

        axiosInstance.post.mockRejectedValue({
            response: { data: {} }
        });

        render(<Register />);

        fireEvent.change(screen.getByPlaceholderText('Username'), {
            target: { value: 'newuser' }
        });

        fireEvent.change(screen.getByPlaceholderText('Password'), {
            target: { value: 'newpassword' }
        });

        fireEvent.click(screen.getByRole('button', { name: /register/i }));

        await waitFor(() => {
            expect(screen.getByText(defaultErrorMessage)).toBeInTheDocument();
        });

        expect(screen.getByText('Registration failed')).toBeInTheDocument();
    });
});