import { useState, useCallback } from 'react';
import { parseUrl } from '../services/api';
import { isValidUrl, normalizeUrlSlashes } from '../utils/urlValidator';
import type { ServerResponse } from '../types';
import { useCache } from './useCache';
import axios from 'axios';
import { clearCache } from '../services/cache';

export const useParsing = () => {
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [data, setData] = useState<ServerResponse | null>(null);
    const [currentUrl, setCurrentUrl] = useState<string>('');

    const { getCachedItem, setCachedItem } = useCache();

    const startParsing = useCallback(async (url: string) => {
        setIsLoading(true);
        setError(null);
        setCurrentUrl(url);

        const normalizedUrl = normalizeUrlSlashes(url);

        if (!isValidUrl(normalizedUrl)) {
            setError("Неверный URL. Поддерживаются только rollingmoto.ru и motoland-shop.ru");
            setIsLoading(false);
            return;
        }

        // Попытка получить данные из кэша
        const cachedData = getCachedItem<ServerResponse>(normalizedUrl);
        if (cachedData) {
            console.log(`Данные для ${normalizedUrl} найдены в кэше.`);
            setData(cachedData);
            setIsLoading(false);
            return;
        }

        try {
            console.log(`Отправка запроса на парсинг URL: ${normalizedUrl}`);
            const response = await parseUrl(normalizedUrl);
            setData(response);
            setCachedItem(normalizedUrl, response); // Кэшируем полученные данные
        } catch (err) {
            console.error("Ошибка парсинга:", err);
            if (axios.isAxiosError(err) && err.response) {
                setError(err.response.data.error || "Произошла ошибка при парсинге URL.");
            } else {
                setError("Произошла непредвиденная ошибка.");
            }
        } finally {
            setIsLoading(false);
        }
    }, [getCachedItem, setCachedItem]);

    const handleClearCache = useCallback(() => {
        clearCache();
        console.log('Кэш успешно очищен.');
    }, []);

    return { isLoading, error, data, currentUrl, startParsing, setData, handleClearCache };
}; 