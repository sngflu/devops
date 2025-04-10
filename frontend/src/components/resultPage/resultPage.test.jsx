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

    it('fetches video URL on mount', async () => {
        render(
            <MemoryRouter>
                <ResultPage />
            </MemoryRouter>
        );

        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalledWith(
                `http://127.0.0.1:5174/video/${mockState.video_url}`,
                {
                    headers: {
                        'Authorization': 'Bearer mock-token'
                    }
                }
            );
        });
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

    it('handles download button click', async () => {
        render(
            <MemoryRouter>
                <ResultPage />
            </MemoryRouter>
        );

        const downloadButton = await screen.findByText('Download');
        fireEvent.click(downloadButton);

        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalledWith('mock-video-url');
            expect(URL.createObjectURL).toHaveBeenCalled();
            expect(URL.revokeObjectURL).toHaveBeenCalled();
        });
    });

    it('handles download error', async () => {
        global.fetch.mockImplementationOnce(() =>
            Promise.resolve({
                ok: true,
                json: () => Promise.resolve({ url: 'mock-video-url' }),
            })
        );

        global.fetch.mockImplementationOnce(() =>
            Promise.reject(new Error('Download error'))
        );

        console.error = vi.fn();

        render(
            <MemoryRouter>
                <ResultPage />
            </MemoryRouter>
        );

        await waitFor(() => expect(screen.getByText('Download')).toBeEnabled());

        const downloadButton = screen.getByText('Download');
        fireEvent.click(downloadButton);

        await waitFor(() => {
            expect(console.error).toHaveBeenCalledWith('Download error:', expect.any(Error));
        }, { timeout: 3000 });
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