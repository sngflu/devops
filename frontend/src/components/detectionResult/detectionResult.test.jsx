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
        render(<DetectionResults
            frameObjects={mockFrameObjects}
            onFrameClick={() => { }}
            currentFrame={null}
        />);

        expect(screen.getByText(/Frame 1\. Detected weapon\./)).toBeInTheDocument();
        expect(screen.getByText(/Frame 3\. Detected knife\./)).toBeInTheDocument();
        expect(screen.getByText(/Frame 4\. Detected weapon and knife\./)).toBeInTheDocument();
        expect(screen.queryByText(/Frame 2\./)).not.toBeInTheDocument();
    });

    it('handles frame click correctly', () => {
        const mockOnFrameClick = vi.fn();
        const videoElement = { currentTime: 0 };
        document.querySelector = vi.fn().mockReturnValue(videoElement);

        render(<DetectionResults
            frameObjects={mockFrameObjects}
            onFrameClick={mockOnFrameClick}
            currentFrame={null}
        />);

        const firstLog = screen.getByText(/Frame 1\. Detected weapon\./);
        fireEvent.click(firstLog);

        expect(mockOnFrameClick).toHaveBeenCalledWith(1);
    });

    it('renders empty message when no weapons or knives are detected', () => {
        const input = [
            [5, 0, 0], // не должен отображаться
            [6, 1, 0], // weapon
            [7, 0, 0], // не должен отображаться
            [8, 0, 1], // knife
            [9, 0, 0], // не должен отображаться
            [10, 0, 0], // пустой, но отличается от предыдущих по кадру
        ];

        render(<DetectionResults
            frameObjects={input}
            onFrameClick={() => { }}
            currentFrame={null}
        />);

        expect(screen.queryByText(/Frame 5/)).not.toBeInTheDocument();
        expect(screen.queryByText(/Frame 7/)).not.toBeInTheDocument();
        expect(screen.queryByText(/Frame 9/)).not.toBeInTheDocument();
        expect(screen.queryByText(/Frame 10/)).not.toBeInTheDocument();
    });

    it('highlights the current frame', () => {
        const mockFrameObjects = [
            [1, 2, 0],
            [2, 0, 0],
            [3, 0, 1],
            [4, 1, 1]
        ];

        render(<DetectionResults
            frameObjects={mockFrameObjects}
            onFrameClick={() => { }}
            currentFrame={3}
        />);

        const paragraph = screen.getByText(/Frame 3\. Detected knife\./);
        const logItem = paragraph.closest('.log-item');

        expect(logItem.classList.contains('active')).toBe(true);
    });
});