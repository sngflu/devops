import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from './App';

vi.mock('./components/header/header', () => ({
    default: () => <div data-testid="header-component">Header Mock</div>
}));

vi.mock('./components/loginPage/login', () => ({
    default: () => <div data-testid="login-component">Login Mock</div>
}));


describe('App Component', () => {
    beforeEach(() => {
        localStorage.clear();
    });

    it('renders login page when not authenticated', () => {
        vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
        render(<App />);
        expect(screen.getByTestId('login-component')).toBeInTheDocument();
    });

    it('renders the header component', () => {
        vi.spyOn(Storage.prototype, 'getItem').mockReturnValue('fake-token');
        render(<App />);
        expect(screen.getByTestId('header-component')).toBeInTheDocument();
    });
});
