import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import ResultPage from './resultPage';

let seekToMock;

vi.mock('react-router-dom', async (importOriginal) => {
    const actual = await importOriginal();
    return {
        ...actual,
        useLocation: vi.fn(),
        Link: ({ children }) => <div>{children}</div>,
    };
});

vi.mock('react-player', () => ({
    default: vi.fn().mockImplementation(({ ref }) => {
        seekToMock = vi.fn();
        if (ref) {
            ref.current = {
                seekTo: seekToMock,
            };
        }
        return <div data-testid="react-player">ReactPlayer Mock</div>;
    }),
}));

vi.mock('../detectionResult/detectionResults', () => ({
    default: ({ frameObjects, onFrameClick, currentFrame }) => (
        <div data-testid="detection-results">
            {frameObjects.map((frame, index) => (
                <div key={index} onClick={() => onFrameClick(index + 1)}>
                    Frame {index + 1}
                </div>
            ))}
        </div>
    ),
}));

describe('ResultPage Component', () => {
    const mockState = {
        video_url: 'test-video.mp4',
        frame_objects: [
            [1, 1, 0],  // weapon
            [2, 0, 0],  // nothing
            [3, 0, 1],  // knife
            [4, 1, 1]   // weapon and knife
        ],
    };

    beforeEach(() => {
        vi.spyOn(global, 'fetch').mockResolvedValue({
            ok: true,
            json: vi.fn().mockResolvedValue({ url: 'mock-video-url' }),
            blob: vi.fn().mockResolvedValue(new Blob()),
        });

        vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-url');
        vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => { });

        useLocation.mockReturnValue({ state: mockState });

        const mockLocalStorage = {
            getItem: vi.fn(() => 'mock-token'),
        };
        global.localStorage = mockLocalStorage;
    });

    afterEach(() => {
        vi.restoreAllMocks();
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

    it('handles fetch video error', async () => {
        global.fetch.mockRejectedValueOnce(new Error('Fetch error'));
        console.error = vi.fn();

        render(
            <MemoryRouter>
                <ResultPage />
            </MemoryRouter>
        );

        await waitFor(() => {
            expect(console.error).toHaveBeenCalledWith('Error fetching video:', expect.any(Error));
        });
    });

    it('does not try to seek when player ref is not available', async () => {
        vi.doMock('react-player', () => ({
            default: () => <div>ReactPlayer Mock</div>,
        }));

        render(
            <MemoryRouter>
                <ResultPage />
            </MemoryRouter>
        );

        const frameElements = await screen.findAllByText(/Frame \d/);
        fireEvent.click(frameElements[0]);
    });
});