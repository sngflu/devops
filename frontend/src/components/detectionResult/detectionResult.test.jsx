import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DetectionResults from './detectionResults';

describe('DetectionResults Component', () => {
    const mockFrameObjects = [
        [1, 2, 0],  // Frame 1: 2 weapons
        [2, 0, 0],  // Frame 2: no detections
        [3, 0, 1],  // Frame 3: 1 knife
        [4, 1, 1]   // Frame 4: 1 weapon, 1 knife
    ];

    it('renders detection results correctly', () => {
        render(<DetectionResults
            frameObjects={mockFrameObjects}
            onFrameClick={() => { }}
            currentFrame={null}
        />);

        // Check for new message format
        expect(screen.getByText(/Frame 1\. Detected weapon\./)).toBeInTheDocument();
        expect(screen.getByText(/Frame 3\. Detected knife\./)).toBeInTheDocument();
        expect(screen.getByText(/Frame 4\. Detected weapon and knife\./)).toBeInTheDocument();
        // Frame 2 should not be displayed as it has no detections
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
});