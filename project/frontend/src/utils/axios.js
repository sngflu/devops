// src/axios.js
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || '/api';   // относительный путь!

const axiosInstance = axios.create({ baseURL: API_URL });

axiosInstance.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default axiosInstance;
