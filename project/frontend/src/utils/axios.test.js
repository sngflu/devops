import { describe, it, expect, vi } from 'vitest';
import axiosInstance from './axios';

vi.mock('axios', async (importOriginal) => {
    const originalAxios = await importOriginal();
    
    return {
        ...originalAxios,
        create: vi.fn(() => ({
            defaults: {
                baseURL: 'http://127.0.0.1:5174',
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
        expect(axiosInstance.defaults.baseURL).toBe('http://127.0.0.1:5174');
    });
});
