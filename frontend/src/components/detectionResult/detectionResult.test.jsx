import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DetectionResults from './detectionResults';

describe('DetectionResults Component', () => {
    const mockFrameObjects = [
        [1, 2, 0],
        [2, 0, 0],
        [3, 0, 1],
        [4, 1, 1]
    ];

    it('renders detection results correctly', () => {
        render(<DetectionResults frameObjects={mockFrameObjects} fpsCount={30} />);

        expect(screen.getByText('Frame 1: 2 weapons, 0 knives')).toBeInTheDocument();
        expect(screen.getByText('Frame 3: 0 weapons, 1 knives')).toBeInTheDocument();
        expect(screen.getByText('Frame 4: 1 weapons, 1 knives')).toBeInTheDocument();

        expect(screen.queryByText('Frame 2: 0 weapons, 0 knives')).not.toBeInTheDocument();
    });

    it('handles frame click correctly', () => {
        const videoElement = { currentTime: 0 };
        document.querySelector = vi.fn().mockReturnValue(videoElement);

        render(<DetectionResults frameObjects={mockFrameObjects} fpsCount={30} />);

        fireEvent.click(screen.getByText('Frame 1: 2 weapons, 0 knives'));

        expect(videoElement.currentTime).toBe(1 / 60);

        fireEvent.click(screen.getByText('Frame 4: 1 weapons, 1 knives'));

        expect(videoElement.currentTime).toBe(4 / 60);
    });
});
