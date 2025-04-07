import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
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
