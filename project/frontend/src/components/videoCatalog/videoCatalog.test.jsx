import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import VideoCatalog from './videoCatalog';
import axiosInstance from '../../utils/axios';

vi.mock('../../utils/axios', () => ({
    default: {
        get: vi.fn(),
        put: vi.fn(),
        delete: vi.fn()
    }
}));

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
        axiosInstance.get.mockImplementation((url) => {
            if (url === '/videos') {
                return Promise.resolve({ data: mockVideos });
            }
            if (url === `/videos/${mockVideo.filename}/logs`) {
                return Promise.resolve({ data: mockVideo.logs });
            }
            return Promise.reject(new Error('Unknown endpoint'));
        });

        axiosInstance.put.mockResolvedValue({ data: { new_filename: 'video1_renamed.mp4' } });
        axiosInstance.delete.mockResolvedValue({});

        global.fetch.mockImplementation((url) => {
            if (url === `/video/${mockVideo.filename}`) {
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
            expect(axiosInstance.delete).toHaveBeenCalledWith(
                `/videos/${mockVideo.filename}`
            );
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
            expect(axiosInstance.put).toHaveBeenCalledWith(
                `/videos/${mockVideo.filename}`,
                { new_name: 'renamed.mp4' }
            );
        });
    });

    it('extracts date and time from filename correctly', () => {
        const filename = 'video_20230425_153045_sample.mp4';
        const expected = '25.04.2023, 15:30:45';
    });
});
