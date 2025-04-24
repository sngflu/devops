import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import VideoCatalog from './videoCatalog';
import axios from 'axios';

vi.mock('axios');

const originalConfirm = window.confirm;
beforeEach(() => {
    window.confirm = vi.fn(() => true);
});
afterEach(() => {
    window.confirm = originalConfirm;
});

global.fetch = vi.fn();

global.localStorage = {
    getItem: vi.fn(() => 'mock-token'),
};

vi.mock('react-player', () => ({
    default: () => <div data-testid="react-player">ReactPlayer Mock</div>,
}));

let mockLocation = { state: null };

vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom');
    return {
        ...actual,
        useLocation: () => mockLocation,
        Link: ({ children }) => <div>{children}</div>,
    };
});

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

    const mockVideos = [mockVideo];

    beforeEach(() => {
        axios.get.mockImplementation((url, config) => {
            if (url === 'http://127.0.0.1:5174/videos') {
                return Promise.resolve({ data: mockVideos });
            }
            if (url === `http://127.0.0.1:5174/videos/${mockVideo.filename}/logs`) {
                return Promise.resolve({ data: mockVideo.logs });
            }
            return Promise.reject(new Error('Unknown endpoint'));
        });

        axios.put.mockResolvedValue({ data: { new_filename: 'video1_renamed.mp4' } });
        axios.delete.mockResolvedValue({});

        global.fetch.mockImplementation((url, config) => {
            if (url === `http://127.0.0.1:5174/video/${mockVideo.filename}`) {
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve({ url: 'mock-video-url' }),
                });
            }
            if (url === 'mock-video-url') {
                return Promise.resolve({
                    ok: true,
                    blob: () => Promise.resolve(new Blob(['video-content'], { type: 'video/mp4' })),
                });
            }
            return Promise.reject(new Error('Unknown endpoint'));
        });

        vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-url');
        vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => { });
    });

    afterEach(() => {
        vi.resetAllMocks();
    });

    it('renders the catalog correctly', async () => {
        render(
            <MemoryRouter>
                <VideoCatalog />
            </MemoryRouter>
        );
        expect(screen.getByText('Processed Videos')).toBeInTheDocument();
        expect(screen.getByText('Home')).toBeInTheDocument();
    });

    it('loads videos on mount and displays video items', async () => {
        render(
            <MemoryRouter>
                <VideoCatalog />
            </MemoryRouter>
        );
        expect(await screen.findByText('test1.mp4')).toBeInTheDocument();
    });

    it('handles video click correctly', async () => {
        render(
            <MemoryRouter>
                <VideoCatalog />
            </MemoryRouter>
        );
        const videoItem = await screen.findByText('test1.mp4');
        fireEvent.click(videoItem);
        expect(await screen.findByTestId('react-player')).toBeInTheDocument();
        expect(await screen.findByText('Detection Logs')).toBeInTheDocument();
    });

    it('handles download correctly', async () => {
        render(
            <MemoryRouter>
                <VideoCatalog />
            </MemoryRouter>
        );
        const videoItem = await screen.findByText('test1.mp4');
        fireEvent.click(videoItem);
        await waitFor(() => {
            expect(screen.getByTestId('react-player')).toBeInTheDocument();
        });
        const downloadButton = screen.getByText(/Скачать видео|Download/i);
        fireEvent.click(downloadButton);
        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalledWith('mock-video-url');
            expect(URL.createObjectURL).toHaveBeenCalled();
            expect(URL.revokeObjectURL).toHaveBeenCalled();
        });
    });

    it('handles download error by logging error', async () => {
        global.fetch.mockImplementationOnce(() =>
            Promise.resolve({
                ok: true,
                json: () => Promise.resolve({ url: 'mock-video-url' }),
            })
        ).mockImplementationOnce(() =>
            Promise.reject(new Error('Download error'))
        );
        console.error = vi.fn();
        render(
            <MemoryRouter>
                <VideoCatalog />
            </MemoryRouter>
        );
        const videoItem = await screen.findByText('test1.mp4');
        fireEvent.click(videoItem);
        const downloadButton = await screen.findByText(/Скачать видео|Download/i);
        fireEvent.click(downloadButton);
        await waitFor(() => {
            expect(console.error).toHaveBeenCalledWith('Ошибка при скачивании файла:', expect.any(Error));
        });
    });

    it('handles delete correctly', async () => {
        render(
            <MemoryRouter>
                <VideoCatalog />
            </MemoryRouter>
        );
        const videoItem = await screen.findByText('test1.mp4');
        expect(videoItem).toBeInTheDocument();
        const deleteButton = screen.getByText('Delete');
        fireEvent.click(deleteButton);
        await waitFor(() => {
            expect(axios.delete).toHaveBeenCalledWith(
                `http://127.0.0.1:5174/videos/${mockVideo.filename}`,
                { headers: { Authorization: 'Bearer mock-token' } }
            );
        });
        await waitFor(() => {
            expect(screen.queryByText('test1.mp4')).not.toBeInTheDocument();
        });
    });

    it('handles renaming correctly', async () => {
        render(
            <MemoryRouter>
                <VideoCatalog />
            </MemoryRouter>
        );
        const videoItem = await screen.findByText('test1.mp4');
        fireEvent.click(videoItem);
        const renameButton = screen.getByText('Rename');
        fireEvent.click(renameButton);
        const input = screen.getByDisplayValue('test1.mp4');
        expect(input).toBeInTheDocument();
        fireEvent.change(input, { target: { value: 'renamed.mp4' } });
        fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });
        await waitFor(() => {
            expect(axios.put).toHaveBeenCalledWith(
                `http://127.0.0.1:5174/videos/${mockVideo.filename}`,
                { new_name: 'renamed.mp4' },
                { headers: { Authorization: 'Bearer mock-token' } }
            );
        });
        await waitFor(() => {
            expect(screen.getByText('renamed.mp4')).toBeInTheDocument();
        });
    });

    it('extracts date and time from filename correctly', () => {
        const filename = 'video_20230425_153045_sample.mp4';
        const expected = '25.04.2023, 15:30:45';
    });

    it('handles log click (frame seeking) correctly', async () => {
        const fakeVideo = document.createElement('video');
        fakeVideo.currentTime = 0;
        fakeVideo.play = vi.fn();
        fakeVideo.pause = vi.fn();
        const playerWrapper = document.createElement('div');
        playerWrapper.className = 'react-player';
        playerWrapper.appendChild(fakeVideo);
        document.body.appendChild(playerWrapper);

        render(
            <MemoryRouter>
                <VideoCatalog />
            </MemoryRouter>
        );
        const videoItem = await screen.findByText('test1.mp4');
        fireEvent.click(videoItem);
        const frameElement = await screen.findByText(/Frame 1/);
        fireEvent.click(frameElement);
        expect(fakeVideo.currentTime).toBeCloseTo(1 / 30);
        await waitFor(() => expect(fakeVideo.play).toHaveBeenCalled());
        await waitFor(() => expect(fakeVideo.pause).toHaveBeenCalled());
        document.body.removeChild(playerWrapper);
    });
});
