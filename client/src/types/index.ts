export interface Product {
    brand: string;
    model: string;
    year: string;
    name: string;
    link: string;
    images: string[];
    description: string;
    price: string;
    old_price?: string;
    discount?: string;
    economy?: string;
    site: 'rollingmoto' | 'motoland';
    characteristics?: { [key: string]: string };
}

export interface CatalogResponse {
    type: 'catalog';
    products: Product[];
    totalItems: number;
}

export interface ProductDetailsResponse {
    type: 'product';
    details: Product;
}

export type ServerResponse = CatalogResponse | ProductDetailsResponse; 