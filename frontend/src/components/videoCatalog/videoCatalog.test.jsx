import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import VideoCatalog from './videoCatalog';

vi.mock('react-player', () => ({
    default: () => <div data-testid="react-player">ReactPlayer Mock</div>,
}));

describe('VideoCatalog Component', () => {
    const mockVideo = {
        filename: 'video1_20240407.mp4',
        original_name: 'test1.mp4',
        log_count: 3,
        logs: [
            [1, 1, 0],
            [3, 0, 1],
            [4, 1, 1],
        ],
    };

    beforeEach(() => {
        global.localStorage = {
            getItem: vi.fn(() => 'mock-token'),
        };

        global.fetch = vi.fn((url) => {
            if (url.includes('/get-videos')) {
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve({ videos: [mockVideo] }),
                });
            }
            if (url.includes('/get-video')) {
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve({ url: 'mock-video-url' }),
                });
            }
            if (url.includes('/get-logs')) {
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve({ logs: mockVideo.logs }),
                });
            }
            return Promise.reject(new Error('Unknown endpoint'));
        });
    });

    it('renders the catalog correctly', () => {
        render(
            <MemoryRouter>
                <VideoCatalog />
            </MemoryRouter>
        );

        expect(screen.getByText('Processed Videos')).toBeInTheDocument();
        expect(screen.getByText('Home')).toBeInTheDocument();
    });

});
