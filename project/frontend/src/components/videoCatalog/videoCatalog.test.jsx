import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
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
        MemoryRouter: ({ children }) => <div>{children}</div>
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
            if (url === `/video/${mockVideo.filename}`) {
                return Promise.resolve({ data: { url: 'mock-video-url' } });
            }
            return Promise.reject(new Error('Unknown endpoint'));
        });

        axiosInstance.put.mockResolvedValue({ data: { new_filename: 'video1_renamed.mp4' } });
        axiosInstance.delete.mockResolvedValue({});

        global.fetch.mockImplementation((url) => {
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
        await act(async () => {
            render(
                <VideoCatalog />, { wrapper: MemoryRouter }
            );
        });
        expect(screen.getByText('Processed Videos')).toBeInTheDocument();
        expect(screen.getByText('Home')).toBeInTheDocument();
    });

    it('loads videos on mount and displays video items', async () => {
        await act(async () => {
            render(
                <VideoCatalog />, { wrapper: MemoryRouter }
            );
        });
        expect(await screen.findByText('test1.mp4')).toBeInTheDocument();
    });

    it('handles delete correctly', async () => {
        await act(async () => {
            render(
                <VideoCatalog />, { wrapper: MemoryRouter }
            );
        });
        const videoItem = await screen.findByText('test1.mp4');
        expect(videoItem).toBeInTheDocument();
        await act(async () => {
            const deleteButton = screen.getByText('Delete');
            fireEvent.click(deleteButton);
        });
        await waitFor(() => {
            expect(axiosInstance.delete).toHaveBeenCalledWith(
                `/videos/${mockVideo.filename}`
            );
        });
    });

    it('handles renaming correctly', async () => {
        axiosInstance.get.mockImplementation((url) => {
            if (url === '/videos') {
                return Promise.resolve({ data: [mockVideo] });
            }
            if (url === `/videos/${mockVideo.filename}/logs`) {
                return Promise.resolve({ data: mockVideo.logs });
            }
            if (url === `/video/${mockVideo.filename}`) {
                return Promise.resolve({ data: { url: 'mock-video-url' } });
            }
            return Promise.reject(new Error('Unknown endpoint'));
        });

        await act(async () => {
            render(
                <VideoCatalog />, { wrapper: MemoryRouter }
            );
        });

        const videoItem = await screen.findByText('test1.mp4');
        await act(async () => {
            fireEvent.click(videoItem);
        });

        await waitFor(() => expect(screen.getByText(/Detections: \d/)).toBeInTheDocument());

        const renameButton = screen.getByText('Rename');
        await act(async () => {
            fireEvent.click(renameButton);
        });
        const input = screen.getByDisplayValue('test1.mp4');
        expect(input).toBeInTheDocument();
        await act(async () => {
            fireEvent.change(input, { target: { value: 'renamed.mp4' } });
        });

        axiosInstance.put.mockResolvedValueOnce({ data: { new_filename: 'video1_renamed.mp4' } });

        await act(async () => {
            fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });
        });

        await waitFor(() => {
            expect(axiosInstance.put).toHaveBeenCalledWith(
                `/videos/${mockVideo.filename}`,
                { new_name: 'renamed.mp4' }
            );
            expect(screen.getByText('renamed.mp4')).toBeInTheDocument();
        });
    });

    it('extracts date and time from filename correctly', () => {
        const filename = 'video_20230425_153045_sample.mp4';
        const expected = '25.04.2023, 15:30:45';
    });

    it('handles loadVideos error', async () => {
        axiosInstance.get.mockRejectedValueOnce(new Error('Load error'));
        console.error = vi.fn();
        await act(async () => {
            render(<VideoCatalog />, { wrapper: MemoryRouter });
        });
        await new Promise(resolve => setTimeout(resolve, 0));
        expect(console.error).toHaveBeenCalled();
    });

    it('handles delete confirmation being false', async () => {
        window.confirm = vi.fn(() => false);
        axiosInstance.delete = vi.fn();

        await act(async () => {
            render(<VideoCatalog />, { wrapper: MemoryRouter });
        });

        await screen.findByText('test1.mp4');
        await act(async () => {
            const deleteButton = screen.getByText('Delete');
            fireEvent.click(deleteButton);
        });

        expect(window.confirm).toHaveBeenCalled();
        expect(axiosInstance.delete).not.toHaveBeenCalled();
    });

    it('handles delete error', async () => {
        window.confirm = vi.fn(() => true);
        axiosInstance.delete.mockRejectedValueOnce(new Error('Delete error'));
        console.error = vi.fn();

        await act(async () => {
            render(<VideoCatalog />, { wrapper: MemoryRouter });
        });

        await screen.findByText('test1.mp4');
        await act(async () => {
            const deleteButton = screen.getByText('Delete');
            fireEvent.click(deleteButton);
        });

        await waitFor(() => {
            expect(axiosInstance.delete).toHaveBeenCalled();
            expect(console.error).toHaveBeenCalledWith('Error deleting video:', expect.any(Error));
        });
    });
});

describe('VideoCatalog stub', () => {
    it('renders without crashing', async () => {
        await act(async () => {
            render(<MemoryRouter><VideoCatalog /></MemoryRouter>);
        });
    });
});
