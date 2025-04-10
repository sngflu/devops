import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import ReactPlayer from 'react-player';
import axios from 'axios';
import './videoCatalog.css';

const VideoCatalog = () => {
    const [videos, setVideos] = useState([]);
    const [selectedVideo, setSelectedVideo] = useState(null);
    const [logs, setLogs] = useState([]);
    const [editingVideo, setEditingVideo] = useState(null);
    const [newName, setNewName] = useState('');
    const [videoUrl, setVideoUrl] = useState('');
    const [currentFrame, setCurrentFrame] = useState(null);
    const token = localStorage.getItem('token');

    useEffect(() => {
        loadVideos();
    }, []);

    const loadVideos = async () => {
        try {
            const response = await axios.get('http://127.0.0.1:5174/videos', {
                headers: { Authorization: `Bearer ${token}` }
            });
            setVideos(response.data);
        } catch (error) {
            console.error('Error loading videos:', error);
        }
    };

    const handleVideoClick = async (video) => {
        if (editingVideo) return;

        setCurrentFrame(null);

        try {
            const logsResponse = await axios.get(
                `http://127.0.0.1:5174/videos/${video.filename}/logs`,
                { headers: { Authorization: `Bearer ${token}` } }
            );

            const videoResponse = await fetch(
                `http://127.0.0.1:5174/video/${video.filename}`,
                { headers: { Authorization: `Bearer ${token}` } }
            );

            if (videoResponse.ok) {
                const data = await videoResponse.json();
                setVideoUrl(data.url);
            }

            setSelectedVideo(video);
            setLogs(logsResponse.data);
        } catch (error) {
            console.error('Error loading video and logs:', error);
        }
    };

    const handleDownload = async () => {
        if (videoUrl && selectedVideo) {
            try {
                const response = await fetch(videoUrl);
                if (!response.ok) {
                    throw new Error(`Ошибка при загрузке файла: ${response.statusText}`);
                }
                const blob = await response.blob();
                const downloadUrl = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = downloadUrl;
                link.download = selectedVideo.original_name || selectedVideo.filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(downloadUrl);
            } catch (error) {
                console.error('Ошибка при скачивании файла:', error);
            }
        }
    };

    const handleDelete = async (video) => {
        if (!confirm('Are you sure you want to delete this video?')) return;

        try {
            await axios.delete(`http://127.0.0.1:5174/videos/${video.filename}`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setVideos(videos.filter(v => v.filename !== video.filename));
            if (selectedVideo?.filename === video.filename) {
                setSelectedVideo(null);
                setLogs([]);
                setVideoUrl('');
            }
        } catch (error) {
            console.error('Error deleting video:', error);
        }
    };

    const extractDateTimeFromFilename = (filename) => {
        const match = filename.match(/_(\d{8})_(\d{6})_/);
        if (match) {
            const datePart = match[1];
            const timePart = match[2];
            const year = datePart.slice(0, 4);
            const month = datePart.slice(4, 6);
            const day = datePart.slice(6, 8);
            const hours = timePart.slice(0, 2);
            const minutes = timePart.slice(2, 4);
            const seconds = timePart.slice(4, 6);
            return `${day}.${month}.${year}, ${hours}:${minutes}:${seconds}`;
        }
        return 'Unknown Date';
    };

    const handleRename = async (video, e) => {
        e.stopPropagation();
        if (editingVideo === video.filename) {
            try {
                const response = await axios.put(
                    `http://127.0.0.1:5174/videos/${video.filename}`,
                    { new_name: newName },
                    { headers: { Authorization: `Bearer ${token}` } }
                );

                setVideos(videos.map(v => {
                    if (v.filename === video.filename) {
                        return { ...v, filename: response.data.new_filename, original_name: newName };
                    }
                    return v;
                }));

                setEditingVideo(null);
                setNewName('');
            } catch (error) {
                console.error('Error renaming video:', error);
            }
        } else {
            setEditingVideo(video.filename);
            setNewName(video.original_name);
        }
    };

    const filterLogsSequence = (logs) => {
        return logs.filter((log, index) => {
            if (index === 0) return true;

            const prevLog = logs[index - 1];
            const currentLog = log;

            return (currentLog[0] - prevLog[0] > 1) ||
                (currentLog[1] !== prevLog[1]) ||
                (currentLog[2] !== prevLog[2]);
        });
    };

    const handleLogClick = (frameNumber) => {
        setCurrentFrame(frameNumber);
        const video = document.querySelector('.react-player video');
        if (video) {
            const timeInSeconds = frameNumber / 30;
            video.currentTime = timeInSeconds;
            video.play();
            setTimeout(() => {
                video.pause();
            }, 100);
        }
    };

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
        <div className="catalog-container">
            <div className="video-list">
                <div className="catalog-header">
                    <h2>Processed Videos</h2>
                    <Link to="/">
                        <button className="home-btn">Home</button>
                    </Link>
                </div>
                {videos.map((video) => (
                    <div
                        key={video.filename}
                        className={`video-item ${selectedVideo?.filename === video.filename ? 'active' : ''}`}
                    >
                        <div onClick={() => handleVideoClick(video)}>
                            {editingVideo === video.filename ? (
                                <input
                                    type="text"
                                    value={newName}
                                    onChange={(e) => setNewName(e.target.value)}
                                    onClick={(e) => e.stopPropagation()}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') {
                                            handleRename(video, e);
                                        }
                                    }}
                                    autoFocus
                                />
                            ) : (
                                <h3>{video.original_name}</h3>
                            )}
                            <p>Processed: {extractDateTimeFromFilename(video.filename)}</p>
                            <p>Detections: {video.log_count}</p>
                        </div>
                        <div className="video-actions">
                            <button
                                onClick={(e) => handleRename(video, e)}
                                className="rename-btn"
                            >
                                {editingVideo === video.filename ? 'Save' : 'Rename'}
                            </button>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    handleDelete(video);
                                }}
                                className="delete-btn"
                            >
                                Delete
                            </button>
                        </div>
                    </div>
                ))}
            </div>

            {selectedVideo && (
                <div className="video-detail">
                    <h2>{selectedVideo.original_name}</h2>
                    <div className='video-logs'>
                        <div className="video-player-wrapper">
                            {videoUrl && (
                                <ReactPlayer
                                    url={videoUrl}
                                    width="100%"
                                    height="100%"
                                    controls
                                    playing={false}
                                    className="react-player"
                                    config={{
                                        file: {
                                            attributes: {
                                                crossOrigin: 'anonymous'
                                            }
                                        }
                                    }}
                                />
                            )}
                        </div>
                        <div className="logs-container">
                            <h3>Detection Logs</h3>
                            <div className="logs-list">
                                {logs.length > 0 && filterLogsSequence(logs.filter(log => log[1] > 0 || log[2] > 0))
                                    .map((log, index) => (
                                        <div
                                            key={index}
                                            className={`log-item ${currentFrame === log[0] ? 'active' : ''}`}
                                            onClick={() => handleLogClick(log[0])}
                                            style={{ cursor: 'pointer' }}
                                        >
                                            <p>Frame {log[0]}. {formatDetectionMessage(log[1], log[2])}</p>
                                        </div>
                                    ))
                                }
                            </div>
                        </div>
                    </div>
                    <button onClick={handleDownload} className="rename-btn" style={{ marginTop: '10px' }}>
                        Скачать видео
                    </button>
                </div>
            )}
        </div>
    );
};

export default VideoCatalog;