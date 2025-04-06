import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import VideoCatalog from './videoCatalog';
import axios from 'axios';
import { Link } from 'react-router-dom';

vi.mock('axios');
vi.mock('react-player', () => ({
    default: () => <div data-testid="react-player">Video Player</div>
}));
vi.mock('react-router-dom', () => ({
    Link: ({ to, children }) => <a href={to}>{children}</a>
}));

describe('VideoCatalog Component', () => {
    const mockVideos = [
        {
            filename: 'user_20230101_120000_testvideo1.mp4',
            original_name: 'testvideo1.mp4',
            log_count: 5
        },
        {
            filename: 'user_20230102_130000_testvideo2.mp4',
            original_name: 'testvideo2.mp4',
            log_count: 3
        }
    ];

    const mockLogs = [
        [1, 2, 0],
        [10, 1, 1],
        [20, 0, 2]
    ];

    beforeEach(() => {
        vi.resetAllMocks();

        vi.spyOn(Storage.prototype, 'getItem').mockReturnValue('fake-token');

        global.fetch = vi.fn();
        global.URL.createObjectURL = vi.fn(() => 'blob:video-url');
        global.URL.revokeObjectURL = vi.fn();

        global.confirm = vi.fn(() => true);

        axios.get.mockImplementation((url) => {
            if (url === 'http://127.0.0.1:5174/videos') {
                return Promise.resolve({ data: mockVideos });
            } else if (url.includes('/logs')) {
                return Promise.resolve({ data: mockLogs });
            }
            return Promise.reject(new Error('Not found'));
        });

        global.fetch.mockResolvedValue({
            ok: true,
            blob: () => Promise.resolve(new Blob(['video data'], { type: 'video/mp4' }))
        });
    });

    it('loads videos on mount', async () => {
        render(<VideoCatalog />);

        await waitFor(() => {
            expect(axios.get).toHaveBeenCalledWith(
                'http://127.0.0.1:5174/videos',
                expect.any(Object)
            );
        });

        expect(screen.getByText('testvideo1.mp4')).toBeInTheDocument();
        expect(screen.getByText('testvideo2.mp4')).toBeInTheDocument();
    });

    it('loads video details when a video is clicked', async () => {
        render(<VideoCatalog />);

        await waitFor(() => {
            expect(screen.getByText('testvideo1.mp4')).toBeInTheDocument();
        });

        fireEvent.click(screen.getByText('testvideo1.mp4'));

        await waitFor(() => {
            expect(axios.get).toHaveBeenCalledWith(
                'http://127.0.0.1:5174/videos/user_20230101_120000_testvideo1.mp4/logs',
                expect.any(Object)
            );
        });

        expect(global.fetch).toHaveBeenCalled();

        await waitFor(() => {
            expect(screen.getByText('Frame 1: 2 weapons, 0 knives detected')).toBeInTheDocument();
            expect(screen.getByText('Frame 10: 1 weapons, 1 knives detected')).toBeInTheDocument();
        });
    });

    it('handles video deletion', async () => {
        axios.delete.mockResolvedValue({ data: 'success' });

        render(<VideoCatalog />);

        await waitFor(() => {
            expect(screen.getByText('testvideo1.mp4')).toBeInTheDocument();
        });

        const deleteButtons = screen.getAllByText('Delete');
        fireEvent.click(deleteButtons[0]);

        expect(global.confirm).toHaveBeenCalledWith('Are you sure you want to delete this video?');

        await waitFor(() => {
            expect(axios.delete).toHaveBeenCalledWith(
                'http://127.0.0.1:5174/videos/user_20230101_120000_testvideo1.mp4',
                expect.any(Object)
            );
        });
    });

    it('handles video renaming', async () => {
        axios.put.mockResolvedValue({
            data: {
                new_filename: 'user_20230101_120000_newname.mp4'
            }
        });

        render(<VideoCatalog />);

        await waitFor(() => {
            expect(screen.getByText('testvideo1.mp4')).toBeInTheDocument();
        });

        const renameButtons = screen.getAllByText('Rename');
        fireEvent.click(renameButtons[0]);

        const inputField = screen.getByDisplayValue('testvideo1.mp4');
        expect(inputField).toBeInTheDocument();

        fireEvent.change(inputField, { target: { value: 'newname.mp4' } });

        const saveButton = screen.getByText('Save');
        fireEvent.click(saveButton);

        await waitFor(() => {
            expect(axios.put).toHaveBeenCalledWith(
                'http://127.0.0.1:5174/videos/user_20230101_120000_testvideo1.mp4',
                { new_name: 'newname.mp4' },
                expect.any(Object)
            );
        });
    });
});
