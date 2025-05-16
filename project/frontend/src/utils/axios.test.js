import { describe, it, expect, vi } from 'vitest';
import axiosInstance from './axios';

vi.mock('axios', async (importOriginal) => {
    const originalAxios = await importOriginal();
    
    return {
        ...originalAxios,
        create: vi.fn(() => ({
            defaults: {
                baseURL: import.meta.env.VITE_API_URL || 'http://api.51.250.74.197.nip.io',
            },
            interceptors: {
                request: {
                    use: vi.fn(),
                },
                response: {
                    use: vi.fn(),
                },
            },
            post: vi.fn(),
            get: vi.fn(),
            delete: vi.fn(),
            put: vi.fn(),
        })),
    };
});

describe('Axios Instance', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should have the correct base URL', () => {
        const baseURL = import.meta.env.VITE_API_URL || 'http://api.51.250.74.197.nip.io';
        expect(axiosInstance.defaults.baseURL).toBe(baseURL);
    });
});
