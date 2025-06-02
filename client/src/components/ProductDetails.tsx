import React, { useState } from 'react';
import { Card, Descriptions, Typography, Image, Space, Button, message } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import type { ImageProps } from 'antd/es/image';
import type { Product } from '../types';

const { Title, Text, Link } = Typography;

interface ProductDetailsProps {
    product: Product | null;
}

export const ProductDetails: React.FC<ProductDetailsProps> = ({ product }) => {
    const [showAllCharacteristics, setShowAllCharacteristics] = useState(false);

    if (!product) {
        return (
            <Card
                title="Информация о товаре"
                style={{ height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column' }}
                styles={{body: {flex: 1, overflowY: 'auto', paddingRight: '12px' }}}
            >
                <Text type="secondary">Выберите товар из списка или введите прямую ссылку на товар.</Text>
            </Card>
        );
    }

    const handleSingleImageDownload = async (imageUrl: string, productName: string) => {
        try {
            message.loading('Скачивание изображения...', 0);
            const response = await fetch(imageUrl);
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;

            const filename = `${productName.replace(/[^a-zA-Z0-9-_.]/g, '')}_${imageUrl.substring(imageUrl.lastIndexOf('/') + 1)}`;
            link.setAttribute('download', filename); // Предлагаемое имя файла
            document.body.appendChild(link);
            link.click();
            link.parentNode?.removeChild(link);
            window.URL.revokeObjectURL(url);

            message.destroy();
            message.success('Изображение успешно скачано!', 3);
        } catch (error) {
            message.destroy();
            console.error('Ошибка при скачивании изображения:', error);
            message.error('Не удалось скачать изображение. Пожалуйста, попробуйте еще раз.');
        }
    };

    return (
        <Card
            title={product.name}
            style={{ height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column' }}
            bodyStyle={{ flex: 1, overflowY: 'auto', paddingRight: '12px' }}
        >
            <Title level={5} style={{ marginTop: 0, marginBottom: 16 }}>Изображения ({product.images ? product.images.length : 0})</Title>
            {
                product.images && product.images.length > 0 ? (
                    <div style={{ overflowX: 'auto', whiteSpace: 'nowrap', paddingBottom: 8 }}>
                        <Image.PreviewGroup
                            preview={{
                                toolbarRender: (imageElement) => {
                                    const imageUrl = (imageElement.props as ImageProps).src;
                                    return (
                                        <Button
                                            icon={<DownloadOutlined />}
                                            type="link"
                                            onClick={() => handleSingleImageDownload(imageUrl || '', product.name)}
                                            style={{ color: '#fff' }}
                                        >
                                            Скачать
                                        </Button>
                                    );
                                },
                            }}>
                            <Space wrap={false}>
                                {product.images.map((image, index) => (
                                    <Image
                                        key={index}
                                        width={100}
                                        src={image}
                                        alt={`${product.name} - ${index + 1}`}
                                        fallback="https://via.placeholder.com/100?text=No+Image"
                                    />
                                ))}
                            </Space>
                        </Image.PreviewGroup>
                    </div>
                ) : (
                    <Text type="secondary">Изображения отсутствуют.</Text>
                )
            }
            <Descriptions bordered column={1} size="small" style={{ marginTop: 24 }}>
                {product.site === 'rollingmoto' && (
                    <>
                        <Descriptions.Item label="Бренд"><Text copyable>{product.brand}</Text></Descriptions.Item>
                        <Descriptions.Item label="Модель"><Text copyable>{product.model}</Text></Descriptions.Item>
                        <Descriptions.Item label="Год"><Text copyable>{product.year}</Text></Descriptions.Item>
                    </>
                )}
                {product.site === 'motoland' && (
                    <>
                        <Descriptions.Item label="Наименование"><Text copyable>{product.name}</Text></Descriptions.Item>
                    </>
                )}
                <Descriptions.Item label="Цена">
                    <Text copyable strong type="success">{product.price}</Text>
                    {product.old_price && <Text copyable delete type="danger" style={{ marginLeft: 8 }}>{product.old_price}</Text>}
                    {product.discount && <Text copyable type="warning" style={{ marginLeft: 8 }}>Скидка: {product.discount}</Text>}
                    {product.economy && <Text copyable type="secondary" style={{ marginLeft: 8 }}>Экономия: {product.economy}</Text>}
                </Descriptions.Item>
                <Descriptions.Item label="Описание">
                    <Typography.Paragraph copyable ellipsis={{ expandable: 'collapsible', rows: 3 }}>
                        {product.description || 'Нет описания'}
                    </Typography.Paragraph>
                </Descriptions.Item>
                {product.characteristics && Object.keys(product.characteristics).length > 0 && (
                    <Descriptions.Item label="Характеристики">
                        <Descriptions column={1} size="small">
                            {Object.entries(product.characteristics)
                                .slice(0, showAllCharacteristics ? undefined : 3)
                                .map(([key, value]) => (
                                    <Descriptions.Item key={key} label={key}>
                                        <Text copyable style={{textWrap: 'nowrap'}}>{value}</Text>
                                    </Descriptions.Item>
                                ))}
                        </Descriptions>
                        {Object.keys(product.characteristics).length > 3 && (
                            <Button
                                type="link"
                                onClick={() => setShowAllCharacteristics(!showAllCharacteristics)}
                                style={{ paddingLeft: 0, marginTop: 8 }}
                            >
                                {showAllCharacteristics ? 'Свернуть' : 'Показать все'}
                            </Button>
                        )}
                    </Descriptions.Item>
                )}
                <Descriptions.Item label="Ссылка">
                    <Link href={product.link} target="_blank" rel="noopener noreferrer">
                        Открыть страницу товара
                    </Link>
                </Descriptions.Item>
            </Descriptions>
        </Card>
    );
}; 