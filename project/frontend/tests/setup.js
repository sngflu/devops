import { expect, afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';

expect.extend(require('@testing-library/jest-dom/matchers'));

afterEach(() => {
    cleanup();
});
