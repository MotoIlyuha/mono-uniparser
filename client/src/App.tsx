import { useState, useEffect } from 'react';
import { Layout, message, Spin, Empty, Typography, ConfigProvider, Flex } from 'antd';
import { Splitter } from 'antd';
import { UrlInput } from './components/UrlInput';
import { ProductList } from './components/ProductList';
import { ProductDetails } from './components/ProductDetails';
import { DownloadArchiveButton } from './components/DownloadArchiveButton';
import { useParsing } from './hooks/useParsing';
import type { Product, CatalogResponse, ProductDetailsResponse } from './types';
import ru_RU from 'antd/locale/ru_RU';

const { Header, Content, Footer } = Layout;
const { Text } = Typography;

function App() {
    const { isLoading, error, data, startParsing } = useParsing();
    const [products, setProducts] = useState<Product[]>([]);
    const [selectedProducts, setSelectedProducts] = useState<Product[]>([]);
    const [displayProductDetails, setDisplayProductDetails] = useState<Product | null>(null);
    const [totalCatalogItems, setTotalCatalogItems] = useState<number>(0);
    const [isProductPage, setIsProductPage] = useState<boolean>(false);

    useEffect(() => {
        if (data) {
            if (data.type === 'catalog') {
                const catalogData = data as CatalogResponse;
                setProducts(catalogData.products);
                setTotalCatalogItems(catalogData.totalItems);
                setDisplayProductDetails(null);
                setIsProductPage(false);
            } else if (data.type === 'product') {
                setDisplayProductDetails((data as ProductDetailsResponse).details);
                setSelectedProducts([]);
                setIsProductPage(true);
            }
        } else {
            setProducts([]);
            setTotalCatalogItems(0);
            setDisplayProductDetails(null);
            setIsProductPage(false);
        }
    }, [data]);

    useEffect(() => {
        if (error) {
            message.error(error);
        }
    }, [error]);

    const handleProductListSelect = (selectedRows: Product[]) => {
        setSelectedProducts(selectedRows);
    };

    const handleProductListClick = (product: Product) => {
        if (product.link) {
            startParsing(product.link);
        } else {
            message.warning('Ссылка на товар отсутствует.');
        }
    };

    const handleUrlSubmit = (url: string) => {
        startParsing(url);
    };

    return (
        <ConfigProvider locale={ru_RU}>
            <Layout style={{ minHeight: '100vh' }}>
                <Header style={{ background: '#fff', padding: '0 24px', borderBottom: '1px solid #f0f0f0' }}>
                    <UrlInput onSubmit={handleUrlSubmit} isLoading={isLoading} />
                </Header>
                <Content style={{ padding: '24px 24px 0' }}>
                    <Spin spinning={isLoading} tip="Загрузка данных...">
                        <Splitter layout="horizontal">
                            <Splitter.Panel
                                min={500}
                                defaultSize={isProductPage ? '30%' : '50%'}
                                resizable={true}
                                style={{paddingRight: 16}}
                            >
                                {products.length > 0 ? (
                                    <>
                                        <Flex align="center" justify="space-between" style={{ marginBottom: 16 }}>
                                            <Text strong>
                                                Найдено товаров: {products.length} {totalCatalogItems > 0 && `(Всего: ${totalCatalogItems})`}
                                            </Text>
                                            {products.length > 0 && selectedProducts.length > 1 && (
                                                <DownloadArchiveButton
                                                    selectedProducts={selectedProducts}
                                                    isLoading={isLoading}
                                                />
                                            )}
                                        </Flex>
                                        <ProductList
                                            products={products}
                                            onSelectChange={handleProductListSelect}
                                            onRowClick={handleProductListClick}
                                            selectedProduct={displayProductDetails}
                                        />
                                    </>
                                ) : (
                                    !isProductPage && <Empty description="Нет товаров для отображения" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                                )}
                            </Splitter.Panel>
                            <Splitter.Panel
                                min={300}
                                defaultSize={isProductPage ? '70%' : '50%'}
                                resizable={true}
                            >
                                <ProductDetails product={displayProductDetails} />
                            </Splitter.Panel>
                        </Splitter>
                    </Spin>
                </Content>
                <Footer style={{ textAlign: 'center' }}>
                    Универсальный парсер ©2025 <a href='https://t.me/MotoIlyuha'>Моторин Илья</a>
                </Footer>
            </Layout>
        </ConfigProvider>
    );
}

export default App;
