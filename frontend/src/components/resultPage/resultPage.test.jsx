import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import ResultPage from './resultPage';

vi.mock('react-router-dom', async (importOriginal) => {
    const actual = await importOriginal();
    return {
        ...actual,
        useLocation: vi.fn(),
    };
});

vi.mock('react-player', () => ({
    default: (props) => <div data-testid="react-player">ReactPlayer Mock</div>,
}));

describe('ResultPage Component', () => {
    const mockState = {
        video_url: 'test-video.mp4',
        frame_objects: [
            [1, 2, 0],
            [2, 0, 0],
            [3, 0, 1],
            [4, 1, 1]
        ],
    };

    const mockVideoBlob = new Blob(['test-video-content'], { type: 'video/mp4' });
    const mockVideoUrl = 'blob:mock-video-url';

    beforeEach(() => {
        const mockLocalStorage = {
            getItem: vi.fn(() => 'mock-token'),
        };
        global.localStorage = mockLocalStorage;

        useLocation.mockReturnValue({ state: mockState });

        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            blob: vi.fn().mockResolvedValue(mockVideoBlob),
        });

        vi.spyOn(global.URL, 'createObjectURL').mockReturnValue(mockVideoUrl);
    });

    it('renders the ResultPage correctly', async () => {
        render(
            <MemoryRouter>
                <ResultPage />
            </MemoryRouter>
        );

        expect(await screen.findByText('Detection Log')).toBeInTheDocument();
        expect(screen.getByText('Home')).toBeInTheDocument();
        expect(screen.getByText('Download')).toBeInTheDocument();
    });

    it('fetches and displays the video correctly', async () => {
        render(
            <MemoryRouter>
                <ResultPage />
            </MemoryRouter>
        );

        expect(global.fetch).toHaveBeenCalledWith('http://127.0.0.1:5174/video/test-video.mp4', {
            headers: {
                Authorization: `Bearer ${localStorage.getItem('token')}`,
            },
        });

        expect(await screen.findByTestId('react-player')).toBeInTheDocument();
    });

    it('displays detection results correctly', async () => {
        render(
            <MemoryRouter>
                <ResultPage />
            </MemoryRouter>
        );

        expect(await screen.findByText('Frame 1: 2 weapons, 0 knives')).toBeInTheDocument();
        expect(screen.getByText('Frame 3: 0 weapons, 1 knives')).toBeInTheDocument();
        expect(screen.getByText('Frame 4: 1 weapons, 1 knives')).toBeInTheDocument();
        expect(screen.queryByText('Frame 2: 0 weapons, 0 knives')).not.toBeInTheDocument();
    });
});
