import axios from 'axios';
import type { ServerResponse, Product } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'; // Базовый URL для Flask-сервера, используем переменную окружения

const api = axios.create({
    baseURL: API_BASE_URL,
});

export const parseUrl = async (url: string): Promise<ServerResponse> => {
    const response = await api.post('/parse_url', { url });
    return response.data;
};

export const downloadArchive = async (productsData: Product[]): Promise<Blob> => {
    const response = await api.post('/download_archive', { products_data: productsData }, {
        responseType: 'blob', // Ожидаем бинарные данные (ZIP-файл)
    });
    return response.data;
}; 