import { useNavigate } from 'react-router-dom';
import './header.css';

const Header = ({ children }) => {
    const navigate = useNavigate();

    const handleLogout = () => {
        localStorage.removeItem('token');
        navigate('/login');
        window.location.reload();
    };

    return (
        <div className="header">
            <h1 onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>{children}</h1>
            <button className="logout-btn" onClick={handleLogout}>Logout</button>
        </div>
    );
};

export default Header;