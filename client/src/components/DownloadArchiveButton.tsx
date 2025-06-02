import React, { useState } from 'react';
import { Button, message } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import type { Product } from '../types';
import { downloadArchive } from '../services/api';

interface DownloadArchiveButtonProps {
    selectedProducts: Product[];
    isLoading: boolean;
}

export const DownloadArchiveButton: React.FC<DownloadArchiveButtonProps> = ({ selectedProducts, isLoading }) => {
    const [isDownloading, setIsDownloading] = useState(false);

    const handleDownload = async () => {
        if (selectedProducts.length === 0) {
            message.warning('Выберите хотя бы один товар для скачивания архива.');
            return;
        }

        try {
            setIsDownloading(true); // Устанавливаем состояние загрузки
            message.loading('Подготовка архива к скачиванию...', 0); // Показываем сообщение о загрузке
            const blob = await downloadArchive(selectedProducts);

            // Создаем ссылку для скачивания файла
            const url = window.URL.createObjectURL(new Blob([blob]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', 'product_images.zip'); // Предлагаемое имя файла
            document.body.appendChild(link);
            link.click();
            link.parentNode?.removeChild(link); // Очищаем ссылку
            window.URL.revokeObjectURL(url); // Освобождаем URL-объект

            message.destroy(); // Закрываем сообщение о загрузке
            message.success('Архив успешно скачан!', 3);
        } catch (error) {
            message.destroy();
            console.error('Ошибка при скачивании архива:', error);
            message.error('Не удалось скачать архив. Пожалуйста, попробуйте еще раз.');
        } finally {
            setIsDownloading(false); // Сбрасываем состояние загрузки в любом случае
        }
    };

    // Кнопка активна, если выбрано больше 1 товара и не идет загрузка
    const isDisabled = selectedProducts.length <= 1 || isLoading || isDownloading;

    return (
        <Button
            type="primary"
            icon={<DownloadOutlined />}
            onClick={handleDownload}
            disabled={isDisabled}
            loading={isDownloading}
        >
            Скачать архив ({selectedProducts.length})
        </Button>
    );
}; 