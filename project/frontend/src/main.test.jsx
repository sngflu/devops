import { describe, it, expect } from 'vitest';
import { render, act } from '@testing-library/react';
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

describe('Main Entry Point', () => {
    it('renders the App component without errors', () => {
        const rootElement = document.createElement('div');
        rootElement.id = 'root';
        document.body.appendChild(rootElement);

        ReactDOM.createRoot(rootElement).render(
            <React.StrictMode>
                <App />
            </React.StrictMode>
        );

        expect(() => render(<App />)).not.toThrow();
    });
});
beforeEach(() => {
    document.body.innerHTML = '';
});

afterEach(() => {
    document.body.innerHTML = '';
});

it('should find root element in DOM', () => {
    const root = document.createElement('div');
    root.id = 'root';
    document.body.appendChild(root);

    expect(document.getElementById('root')).not.toBeNull();
});

it('should throw error when root element is missing', () => {
    expect(() => {
        ReactDOM.createRoot(document.getElementById('root')).render(
            <React.StrictMode>
                <App />
            </React.StrictMode>
        );
    }).toThrow();
});

it('should render with StrictMode', async () => {
    const root = document.createElement('div');
    root.id = 'root';
    document.body.appendChild(root);

    const renderSpy = vi.spyOn(ReactDOM, 'createRoot');
    const mockRoot = ReactDOM.createRoot(root);

    await act(async () => {
        mockRoot.render(
            <React.StrictMode>
                <App />
            </React.StrictMode>
        );
    });

    expect(renderSpy).toHaveBeenCalledWith(root);
    expect(root.innerHTML.length).toBeGreaterThan(0);
    expect(root.firstChild).not.toBeNull();

    renderSpy.mockRestore();
});