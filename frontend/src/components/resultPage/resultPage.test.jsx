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
            [1, 1, 0],  // weapon only
            [2, 0, 0],  // no detections
            [3, 0, 1],  // knife only
            [4, 1, 1]   // both weapon and knife
        ],
    };

    beforeEach(() => {
        const mockLocalStorage = {
            getItem: vi.fn(() => 'mock-token'),
        };
        global.localStorage = mockLocalStorage;

        useLocation.mockReturnValue({ state: mockState });

        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: vi.fn().mockResolvedValue({ url: 'mock-video-url' }),
        });
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

    it('displays detection results correctly', async () => {
        render(
            <MemoryRouter>
                <ResultPage />
            </MemoryRouter>
        );

        // Wait for and check detection messages in the new format
        expect(await screen.findByText(/Frame 1\. Detected weapon\./)).toBeInTheDocument();
        expect(screen.getByText(/Frame 3\. Detected knife\./)).toBeInTheDocument();
        expect(screen.getByText(/Frame 4\. Detected weapon and knife\./)).toBeInTheDocument();
        // Frame 2 should not be displayed as it has no detections
        expect(screen.queryByText(/Frame 2\./)).not.toBeInTheDocument();
    });

    it('handles frame seeking correctly', async () => {
        render(
            <MemoryRouter>
                <ResultPage />
            </MemoryRouter>
        );

        const firstLog = await screen.findByText(/Frame 1\./);
        fireEvent.click(firstLog);
        // Add assertions for frame seeking behavior
    });
});