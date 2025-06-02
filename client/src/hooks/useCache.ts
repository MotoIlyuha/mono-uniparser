import { useCallback } from 'react';
import * as cache from '../services/cache';

export const useCache = () => {
    const getCachedItem = useCallback(<T>(key: string): T | null => {
        return cache.getItem<T>(key);
    }, []);

    const setCachedItem = useCallback(<T>(key: string, value: T): void => {
        cache.setItem(key, value);
    }, []);

    const removeCachedItem = useCallback((key: string): void => {
        cache.removeItem(key);
    }, []);

    const clearAllCache = useCallback((): void => {
        cache.clearCache();
    }, []);

    return { getCachedItem, setCachedItem, removeCachedItem, clearAllCache };
}; 