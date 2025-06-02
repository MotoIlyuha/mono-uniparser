import React from 'react';
import { Table, Typography, Image } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { Product } from '../types';

const { Text } = Typography;

interface ProductListProps {
    products: Product[];
    onSelectChange: (selectedProducts: Product[]) => void;
    onRowClick: (product: Product) => void;
    selectedProduct: Product | null;
}

export const ProductList: React.FC<ProductListProps> = ({ products, onSelectChange, onRowClick, selectedProduct }) => {
    const columns: ColumnsType<Product> = [
        {
            title: 'Изображение',
            dataIndex: 'images',
            key: 'images',
            width: 125,
            render: (images: string[]) => (
                <Image.PreviewGroup>
                    {
                        images && images.length > 0 ? (
                            <Image src={images[0]} alt="Product Image" style={{ width: 80 }} />
                        ) : (
                            <Text type="secondary">Нет изображения</Text>
                        )
                    }
                </Image.PreviewGroup>
            ),
        },
        {
            title: 'Наименование',
            dataIndex: 'name',
            key: 'name',
            render: (text: string) => <Text strong>{text}</Text>,
        },
        {
            title: 'Цена',
            dataIndex: 'price',
            key: 'price',
            render: (text: string) => <Text copyable type="success">{text} ₽</Text>,
        }
    ];

    const rowSelection = {
        onChange: (_selectedRowKeys: React.Key[], selectedRows: Product[]) => {
            onSelectChange(selectedRows);
        },
        getCheckboxProps: (record: Product) => ({
            disabled: !record.link, // Отключаем чекбокс, если нет ссылки на товар
        }),
    };

    return (
        <Table
            columns={columns}
            dataSource={products}
            rowKey="link" // Уникальный ключ для каждой строки
            rowSelection={{ ...rowSelection, type: 'checkbox' }}
            onRow={(record) => ({
                onClick: () => {
                    onRowClick(record);
                },
                style: {
                    backgroundColor: selectedProduct && selectedProduct.link === record.link ? '#e6f7ff' : 'inherit',
                },
            })}
            pagination={{ pageSize: 20, pageSizeOptions: [20, 100] }} // Добавим пагинацию
            scroll={{ y: 'calc(100vh - 250px)' }} // Фиксируем высоту таблицы
        />
    );
}; 