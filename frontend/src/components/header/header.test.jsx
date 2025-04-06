import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Header from './header';

vi.mock('react-router-dom', () => ({
    useNavigate: () => vi.fn()
}));

describe('Header Component', () => {
    it('renders header text correctly', () => {
        render(<Header>Weapon Detection</Header>);
        expect(screen.getByText('Weapon Detection')).toBeInTheDocument();
    });

    it('has a logout button', () => {
        render(<Header>Weapon Detection</Header>);
        expect(screen.getByText('Logout')).toBeInTheDocument();
    });

    it('handles logout correctly', () => {
        const localStorageMock = vi.spyOn(Storage.prototype, 'removeItem');
        const reloadMock = vi.fn();
        Object.defineProperty(window, 'location', {
            value: { reload: reloadMock },
            writable: true
        });

        render(<Header>Weapon Detection</Header>);

        fireEvent.click(screen.getByText('Logout'));

        expect(localStorageMock).toHaveBeenCalledWith('token');
        expect(reloadMock).toHaveBeenCalled();
    });
});
