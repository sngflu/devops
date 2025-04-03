import { useNavigate } from 'react-router-dom';
import './header.css';

const Header = ({ children }) => {
    const navigate = useNavigate();

    return (
        <div className="header" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
            <h1>{children}</h1>
        </div>
    );
};

export default Header;