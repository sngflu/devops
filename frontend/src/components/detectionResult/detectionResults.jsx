import './detectionResult.css'

const DetectionResults = ({ frameObjects, fpsCount }) => {
    const filteredFrameObjects = frameObjects.filter(frameObject => frameObject[1] !== 0 || frameObject[2] !== 0);

    const handleFrameClick = (frameNumber) => {
        const video = document.querySelector('.react-player video');
        video.currentTime = frameNumber / 60;
    };

    return (
        <div className="log">
            {filteredFrameObjects.map((frameObject, index) => (
                <div key={index} className="log-item" onClick={() => handleFrameClick(frameObject[0])}>
                    Frame {frameObject[0]}: {frameObject[1]} weapons, {frameObject[2]} knives
                </div>
            ))}
        </div>
    );
};

export default DetectionResults;
