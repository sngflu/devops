import { Link, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import ReactPlayer from 'react-player';
import DetectionResults from '../detectionResult/detectionResults';
import './resultPage.css';

const ResultPage = () => {
    const { state } = useLocation();
    const [videoUrl, setVideoUrl] = useState('');
    const token = localStorage.getItem('token');

    useEffect(() => {
        const fetchVideo = async () => {
            try {
                const response = await fetch(`http://127.0.0.1:5174/video/${state.video_url}`, {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const url = URL.createObjectURL(blob);
                    setVideoUrl(url);
                } else {
                    console.error('Failed to fetch video:', response.status);
                }
            } catch (error) {
                console.error('Error fetching video:', error);
            }
        };

        fetchVideo();

        return () => {
            if (videoUrl) {
                URL.revokeObjectURL(videoUrl);
            }
        };
    }, [state.video_url, token]);

    const handleDownload = () => {
        if (videoUrl) {
            const link = document.createElement('a');
            link.href = videoUrl;
            link.download = state.video_url;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    };

    return (
        <div className="content-result">
            <div className="main-container">
                <div></div>

                <div className="player-section">
                    <div className="player-wrapper">
                        {videoUrl && (
                            <ReactPlayer
                                url={videoUrl}
                                controls
                                playing
                                data-testid="react-player"
                                config={{
                                    file: {
                                        attributes: {
                                            controlsList: 'nodownload',
                                            crossOrigin: 'anonymous'
                                        }
                                    }
                                }}
                            />
                        )}
                    </div>
                    <div className="buttons">
                        <Link to="/">
                            <button>Home</button>
                        </Link>
                        <button onClick={handleDownload}>Download</button>
                    </div>
                </div>

                <div className="detection-container">
                    <h2>Detection Log</h2>
                    <div className="detection-results">
                        <DetectionResults frameObjects={state.frame_objects} />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ResultPage;