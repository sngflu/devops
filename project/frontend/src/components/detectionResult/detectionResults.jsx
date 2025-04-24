import './detectionResult.css';

const DetectionResults = ({ frameObjects, onFrameClick, currentFrame }) => {
    const filteredFrameObjects = frameObjects.filter(frameObject =>
        frameObject[1] > 0 || frameObject[2] > 0
    );

    const uniqueSequenceFrames = filteredFrameObjects.filter((frameObject, index) => {
        if (index === 0) return true;

        const prevFrame = filteredFrameObjects[index - 1];
        const currentFrame = frameObject;

        return (currentFrame[0] - prevFrame[0] > 1) ||
            (currentFrame[1] !== prevFrame[1]) ||
            (currentFrame[2] !== prevFrame[2]);
    });

    const formatDetectionMessage = (weapons, knives) => {
        if (weapons > 0 && knives > 0) {
            return "Detected weapon and knife.";
        } else if (weapons > 0) {
            return "Detected weapon.";
        } else if (knives > 0) {
            return "Detected knife.";
        }
        return "";
    };

    return (
        <div className="log">
            {uniqueSequenceFrames.map((frameObject, index) => (
                <div
                    key={index}
                    className={`log-item ${currentFrame === frameObject[0] ? 'active' : ''}`}
                    onClick={() => onFrameClick(frameObject[0])}
                    style={{ cursor: 'pointer' }}
                >
                    <p>
                        Frame {frameObject[0]}. {formatDetectionMessage(frameObject[1], frameObject[2])}
                    </p>
                </div>
            ))}
        </div>
    );
};

export default DetectionResults;