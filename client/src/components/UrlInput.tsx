import React, { useState, useEffect } from 'react';
import { Button, Space, message, AutoComplete, Popconfirm, Typography, Tooltip, Tag, Flex, Divider } from 'antd';
import { DeleteOutlined, ClearOutlined, InfoCircleOutlined } from '@ant-design/icons';
import * as cache from '../services/cache'; // Прямое использование сервиса кэша
import { useParsing } from '../hooks/useParsing';

const { Text } = Typography;

interface UrlInputProps {
    onSubmit: (url: string) => void;
    isLoading: boolean;
}

const HISTORY_KEY = 'searchHistory';

// Функция для нормализации URL (удаление повторяющихся слешей в пути)
const normalizeUrlSlashes = (inputUrl: string): string => {
    if (!inputUrl) return '';

    // Удаляем все повторяющиеся слеши, кроме тех, что следуют за протоколом (http://, https://)
    // Сначала разделяем URL на протокол и остальную часть
    const parts = inputUrl.split('://');
    let normalized = parts[0];
    if (parts.length > 1) {
        normalized += '://' + parts[1].replace(/\/{2,}/g, '/');
    } else {
        normalized = normalized.replace(/\/{2,}/g, '/');
    }

    return normalized;
};

export const UrlInput: React.FC<UrlInputProps> = ({ onSubmit, isLoading }) => {
    const [url, setUrl] = useState<string>('');
    const [history, setHistory] = useState<string[]>([]);
    const { handleClearCache } = useParsing();

    useEffect(() => {
        const storedHistory = cache.getItem<string[]>(HISTORY_KEY);
        if (storedHistory) {
            setHistory(storedHistory);
        }
    }, []);

    const saveHistory = (updatedHistory: string[]) => {
        cache.setItem(HISTORY_KEY, updatedHistory);
        setHistory(updatedHistory);
    };

    const addUrlToHistory = (newUrl: string) => {
        const updatedHistory = [newUrl, ...history.filter(item => item !== newUrl)].slice(0, 10); // Сохраняем до 10 последних уникальных элементов
        saveHistory(updatedHistory);
    };

    const removeUrlFromHistory = (urlToRemove: string) => {
        const updatedHistory = history.filter(item => item !== urlToRemove);
        saveHistory(updatedHistory);
        message.success('Элемент удален из истории.', 1.5);
    };

    const clearAllHistory = () => {
        cache.removeItem(HISTORY_KEY);
        setHistory([]);
        message.success('История очищена.', 1.5);
    };

    const handleSubmit = () => {
        if (!url.trim()) {
            message.error('Пожалуйста, введите URL.');
            return;
        }
        const normalizedUrl = normalizeUrlSlashes(url); // Нормализуем URL перед отправкой
        addUrlToHistory(normalizedUrl); // Добавляем нормализованный URL в историю
        onSubmit(normalizedUrl);
    };

    const getDomainAndPath = (fullUrl: string) => {
        let domain = '';
        let path = fullUrl;

        if (fullUrl.includes('rollingmoto.ru')) {
            domain = 'rollingmoto';
            path = fullUrl.replace(/^https?:\/\/www\.rollingmoto\.ru/, '');
        } else if (fullUrl.includes('motoland-shop.ru')) {
            domain = 'motoland';
            path = fullUrl.replace(/^https?:\/\/motoland-shop\.ru/, '');
        }
        return { domain, path: path || '/' }; // Убеждаемся, что path не пустой, если URL был только доменом
    };

    const renderOption = (item: string) => {
        const { domain, path } = getDomainAndPath(item);
        return {
            value: item,
            label: (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Space>
                        {domain && <Tag color={domain === 'rollingmoto' ? 'blue' : 'green'}>{domain}</Tag>}
                        <Text style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {path}
                        </Text>
                    </Space>
                    <Popconfirm
                        title="Удалить из истории?"
                        onConfirm={(e) => {
                            e?.stopPropagation(); // Предотвращаем закрытие AutoComplete
                            removeUrlFromHistory(item);
                        }}
                        okText="Да"
                        cancelText="Нет"
                    >
                        <Button
                            icon={<DeleteOutlined />}
                            size="small"
                            type="text"
                            onClick={(e) => e.stopPropagation()} // Предотвращаем выбор элемента при клике на кнопку
                        />
                    </Popconfirm>
                </div>
            ),
        };
    };

    const options = history.map(item => renderOption(item));

    const supportedSitesContent = (
        <div>
            <Text strong>Поддерживаемые сайты:</Text>
            <br />
            <ul>
                <li><Text>https://www.rollingmoto.ru</Text></li>
                <li><Text>https://motoland-shop.ru</Text></li>
            </ul>
            <Text type="secondary">* Также поддерживаются ссылки на конкретные товары.</Text>
        </div>
    );

    return (
        <Flex gap={8} style={{ width: '100%', margin: 16 }}>
            <Tooltip title={supportedSitesContent} placement="bottom" color='white'>
                <Button
                    icon={<InfoCircleOutlined />}
                    type="text"
                    disabled={isLoading}
                    style={{ marginRight: 8 }}
                />
            </Tooltip>
            <Space.Compact style={{ width: '80%' }}>
                <AutoComplete
                    value={url}
                    options={options}
                    onSelect={(value) => setUrl(value as string)}
                    onSearch={setUrl}
                    onChange={(value) => setUrl(value)}
                    placeholder="Вставьте ссылку на rollingmoto.ru или motoland-shop.ru"
                    disabled={isLoading}
                    style={{ flex: 1, minWidth: 300 }}
                    popupRender={(menu) => (
                        <div>
                            {menu}
                            {history.length > 0 && (
                                <>
                                    <Divider style={{ margin: '4px 0' }} />
                                    <Popconfirm
                                        title="Очистить всю историю поиска?"
                                        onConfirm={clearAllHistory}
                                        okText="Да"
                                        cancelText="Нет"
                                    >
                                        <Button
                                            icon={<ClearOutlined />}
                                            type="link"
                                            disabled={isLoading}
                                            style={{ width: '100%' }}
                                        >
                                            Очистить историю
                                        </Button>
                                    </Popconfirm>
                                </>
                            )}
                        </div>
                    )}
                />
                <Button type="primary" onClick={handleSubmit} loading={isLoading}>
                    Начать парсинг
                </Button>
            </Space.Compact>
            <Button
                icon={<ClearOutlined />}
                onClick={() => {
                    handleClearCache();
                    message.success('Кэш успешно очищен!', 1.5);
                }}
                disabled={isLoading}
            >
                Очистить кэш
            </Button>
        </Flex>
    );
}; 