import { Link, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import ReactPlayer from 'react-player';
import axiosInstance from '../../utils/axios';
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
                    const data = await response.json();
                    setVideoUrl(data.url);
                } else {
                    console.error('Failed to fetch video:', response.status);
                }
            } catch (error) {
                console.error('Error fetching video:', error);
            }
        };

        fetchVideo();
    }, [state.video_url, token]);

    const handleDownload = async () => {
        if (videoUrl) {
            try {
                const response = await fetch(videoUrl);
                if (!response.ok) {
                    throw new Error(`Ошибка при загрузке файла: ${response.statusText}`);
                }
                const blob = await response.blob();
                const downloadUrl = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = downloadUrl;
                link.download = state.video_url;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(downloadUrl);
            } catch (error) {
                console.error('Ошибка при скачивании файла:', error);
            }
        }
    };

    // В компоненте ResultPage измените разметку на:
    return (
        <div className="content-result">
            <div className="main-container">
                <div></div> {/* Левая пустая секция */}

                <div className="player-section">
                    <div className="player-wrapper">
                        {videoUrl && (
                            <ReactPlayer
                                url={videoUrl}
                                controls
                                playing
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