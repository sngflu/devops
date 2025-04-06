import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import MainPage from './mainPage';
import axios from 'axios';

vi.mock('axios');
const navigateMock = vi.fn();

vi.mock('react-router-dom', () => ({
    useNavigate: () => navigateMock
}));

describe('MainPage Component', () => {
    beforeEach(() => {
        vi.resetAllMocks();

        vi.spyOn(Storage.prototype, 'getItem').mockReturnValue('fake-token');
    });

    it('renders the main page correctly', () => {
        render(<MainPage />);
        expect(screen.getByText('Upload a video for weapon detection')).toBeInTheDocument();
        expect(screen.getByText('Open file')).toBeInTheDocument();
        expect(screen.getByText('Catalog')).toBeInTheDocument();
    });

    it('handles file upload correctly', async () => {
        render(<MainPage />);

        const file = new File(['dummy content'], 'test-video.mp4', { type: 'video/mp4' });

        fireEvent.click(screen.getByText('Open file'));

        const input = document.querySelector('input[type="file"]');
        fireEvent.change(input, { target: { files: [file] } });

        await waitFor(() => {
            expect(screen.getByText(/test-video.mp4/)).toBeInTheDocument();
        });

        expect(screen.getByText('Upload again')).toBeInTheDocument();
        expect(screen.getByText('Detect')).toBeInTheDocument();
    });

    it('sends video to backend when detect is clicked', async () => {
        axios.post.mockResolvedValue({
            data: {
                video_url: 'processed-video.mp4',
                frame_objects: [[1, 2, 0]]
            }
        });

        render(<MainPage />);

        const file = new File(['dummy content'], 'test-video.mp4', { type: 'video/mp4' });
        fireEvent.click(screen.getByText('Open file'));
        const input = document.querySelector('input[type="file"]');
        fireEvent.change(input, { target: { files: [file] } });

        fireEvent.click(screen.getByText('Detect'));

        await waitFor(() => {
            expect(axios.post).toHaveBeenCalledWith(
                'http://127.0.0.1:5174/predict',
                expect.any(FormData),
                expect.objectContaining({
                    headers: expect.objectContaining({
                        'Content-Type': 'multipart/form-data',
                        'Authorization': 'Bearer fake-token'
                    })
                })
            );
        });

        expect(navigateMock).toHaveBeenCalledWith('/result', expect.any(Object));
    });
});
