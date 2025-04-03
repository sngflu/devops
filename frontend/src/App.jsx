import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import Header from './components/header/header';
import MainPage from './components/mainPage/mainPage';
import ResultPage from './components/resultPage/resultPage';
import Login from './components/loginPage/login';
import VideoCatalog from './components/videoCatalog/videoCatalog';
import './App.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('token');
    setIsAuthenticated(!!token);
  }, []);

  const ProtectedRoute = ({ children }) => {
    if (!isAuthenticated) {
      return <Navigate to="/login" />;
    }
    return children;
  };

  const LoginRoute = () => {
    if (isAuthenticated) {
      return <Navigate to="/" />;
    }
    return <Login />;
  };

  return (
    <Router>
      <div className='App'>
        <div className='header'>
          <Header>Weapon Detection</Header>
        </div>
        <Routes>
          <Route path="/login" element={<LoginRoute />} />
          <Route path="/" element={
            <ProtectedRoute>
              <MainPage />
            </ProtectedRoute>
          } />
          <Route path="/result" element={
            <ProtectedRoute>
              <ResultPage />
            </ProtectedRoute>
          } />
          <Route path="/catalog" element={
            <ProtectedRoute>
              <VideoCatalog />
            </ProtectedRoute>
          } />
        </Routes>
      </div>
    </Router>
  );
}

export default App;