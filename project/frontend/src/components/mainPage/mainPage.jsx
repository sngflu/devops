import { useNavigate } from 'react-router-dom';
import { useRef, useState } from 'react'
import axiosInstance from '../../utils/axios';
import './mainPage.css';
import robot from '../../assets/robot.png';
import cctv from '../../assets/cctv.png';
import hands from '../../assets/hands.png';
import loading from '../../assets/loading.svg'

const MainPage = () => {
    const fileInputRef = useRef(null);
    const [isFileUploaded, setIsFileUploaded] = useState(false);
    const [uploadedFile, setUploadedFile] = useState(null);
    const navigate = useNavigate();
    const [isLoading, setIsLoading] = useState(false);

    const handleFileUpload = () => {
        fileInputRef.current.click();
    };

    const handleFileSelected = (event) => {
        const selectedFile = event.target.files[0];
        console.log('Selected file: ', selectedFile);
        setIsFileUploaded(true);
        setUploadedFile(selectedFile);
    };

    const sendVideoToBackend = async () => {
        const formData = new FormData();
        formData.append('file', uploadedFile);

        try {
            setIsLoading(true);
            const token = localStorage.getItem('token');
            const response = await axiosInstance.post('/predict',
                formData,
                {
                    headers: {
                        'Content-Type': 'multipart/form-data',
                        'Authorization': `Bearer ${token}`
                    }
                }
            );
            navigate('/result', {
                state: {
                    video_url: response.data.video_url,
                    frame_objects: response.data.frame_objects
                }
            });
        } catch (error) {
            console.error('Error sending video to backend:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const goToCatalog = () => {
        navigate('/catalog')
    }

    return (
        <div className="content-main">
            <div className='left'>
                <img src={robot} alt='robot' className='robot' />
            </div>
            <div className='center'>
                <img src={hands} alt='hands' className='hands' />
                <div>
                    <input
                        type='file'
                        ref={fileInputRef}
                        style={{ display: 'none' }}
                        onChange={handleFileSelected}
                        accept="video/mp4,video/avi,video/quicktime"
                    />
                    {isLoading ? (
                        <div className="loading">
                            <img src={loading} alt="loading" className='circle' />
                            <p className='processing-text'>Your video is being processed...</p>
                        </div>
                    ) : isFileUploaded ? (
                        <div>
                            <div className='buttons'>
                                <button onClick={handleFileUpload}>Upload again</button>
                                <button onClick={sendVideoToBackend}>Detect</button>
                            </div>
                            <p className='file-name'>
                                Uploaded file: {uploadedFile.name}
                            </p>
                        </div>
                    ) : (
                        <button onClick={handleFileUpload}>Open file</button>
                    )}
                </div>
                <p className='center-text'>
                    Upload a video for weapon detection
                </p>
                <div className='buttons'>
                    <button onClick={goToCatalog}>Catalog</button>
                </div>
            </div>
            <div className='right'>
                <img src={cctv} alt='cctv' className='cctv' />
            </div>
        </div>
    );
};

export default MainPage;