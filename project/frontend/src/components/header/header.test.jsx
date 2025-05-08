import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Header from './header';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', () => ({
    useNavigate: () => mockNavigate
}));

describe('Header Component', () => {
    beforeEach(() => {
        mockNavigate.mockClear();
        vi.restoreAllMocks();
    });

    it('renders header text correctly', () => {
        render(<Header>Weapon Detection</Header>);
        expect(screen.getByText('Weapon Detection')).toBeInTheDocument();
    });

    it('has a logout button', () => {
        render(<Header>Weapon Detection</Header>);
        expect(screen.getByText('Logout')).toBeInTheDocument();
    });

    it('handles logout correctly', () => {
        const removeItemMock = vi.spyOn(Storage.prototype, 'removeItem');
        const reloadMock = vi.fn();
        delete window.location;
        window.location = { reload: reloadMock };

        render(<Header>Weapon Detection</Header>);
        fireEvent.click(screen.getByText('Logout'));

        expect(removeItemMock).toHaveBeenCalledWith('token');
        expect(mockNavigate).toHaveBeenCalledWith('/login');
        expect(reloadMock).toHaveBeenCalled();
    });

    it('navigates to home when title is clicked', () => {
        render(<Header>Weapon Detection</Header>);

        fireEvent.click(screen.getByText('Weapon Detection'));

        expect(mockNavigate).toHaveBeenCalledWith('/');
    });
});
