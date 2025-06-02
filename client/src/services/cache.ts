export const getItem = <T>(key: string): T | null => {
    try {
        const serializedValue = localStorage.getItem(key);
        if (serializedValue === null) {
            return null;
        }
        return JSON.parse(serializedValue) as T;
    } catch (error) {
        console.error(`Error getting item from cache for key "${key}":`, error);
        return null;
    }
};

export const setItem = <T>(key: string, value: T): void => {
    try {
        const serializedValue = JSON.stringify(value);
        localStorage.setItem(key, serializedValue);
    } catch (error) {
        console.error(`Error setting item in cache for key "${key}":`, error);
    }
};

export const removeItem = (key: string): void => {
    try {
        localStorage.removeItem(key);
    } catch (error) {
        console.error(`Error removing item from cache for key "${key}":`, error);
    }
};

export const clearCache = (): void => {
    try {
        localStorage.clear();
    } catch (error) {
        console.error("Error clearing cache:", error);
    }
}; 