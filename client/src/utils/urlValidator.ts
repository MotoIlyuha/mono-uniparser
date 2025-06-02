export const isValidUrl = (url: string): boolean => {
    // Регулярное выражение для проверки URL на соответствие rollingmoto.ru или motoland-shop.ru
    const regex = /^https?:\/\/(www\.rollingmoto\.ru\/|motoland-shop\.ru\/)/;
    return regex.test(url);
};

export const normalizeUrlSlashes = (url: string): string => {
    if (url.includes('://')) {
        const [protocol, rest] = url.split('://', 2);
        const [domain, ...pathParts] = rest.split('/');
        const normalizedPath = pathParts.filter(part => part !== '').join('/');
        return `${protocol}://${domain}/${normalizedPath}`;
    } else {
        // Handle relative URLs or URLs without protocol
        return url.replace(/\/{2,}/g, '/');
    }
}; 