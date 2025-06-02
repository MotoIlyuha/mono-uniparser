import requests
from bs4 import BeautifulSoup
import re

def _normalize_url_slashes(url):
    """Replaces multiple slashes with a single slash in the URL path,
    preserving http:// or https://.
    """
    if '://' in url:
        protocol, rest = url.split('://', 1)
        # Split by the first slash after protocol to keep domain part separate
        if '/' in rest:
            domain, path = rest.split('/', 1)
            # Remove redundant slashes in the path part and then strip any leading slashes
            normalized_path = re.sub(r'/{2,}', '/', path).lstrip('/')
            return f"{protocol}://{domain}/{normalized_path}"
        else:
            return url # No path, nothing to normalize
    else:
        # If no protocol, just replace double slashes
        return re.sub(r'/{2,}', '/', url)

def parse_vehicle_description(description):
    brand_match = re.search(r'\b([A-ZА-Я]{2,})\b', description)
    brand = brand_match.group(1) if brand_match else ""
    model_pattern = re.compile(rf'{brand}\s+(.*?)\s+\(?\d{{4}}')
    model_match = model_pattern.search(description)
    model = model_match.group(1).strip() if model_match else ""
    year_match = re.search(r'\(?(\d{4})\)?\s*г?\.', description)
    year = year_match.group(1) if year_match else ""
    return brand, model, year

def _fetch_page(url):
    response = requests.get(url, timeout=10)
    response.raise_for_status() # Вызывает исключение для плохих статусов HTTP
    return BeautifulSoup(response.text, 'html.parser')

def _parse_rollingmoto_catalog(soup, site_root_url):
    products_data = []
    products_on_page = soup.find_all('div', class_='catalog_item_wrapp')

    for product in products_on_page:
        try:
            product_title = product.find('a', class_="dark_link js-notice-block__title option-font-bold font_sm")
            if not product_title: continue

            product_link = site_root_url + product_title.get('href').lstrip('/')
            product_link = _normalize_url_slashes(product_link)
            product_name = product_title.find('span').text.strip() if product_title.find('span') else ""
            product_brand, product_model, product_year = parse_vehicle_description(product_name)

            product_info = product.find('div', class_='cost prices clearfix')
            if not product_info: continue

            images = []
            for link in product_info.find_all('link'):
                if 'schema.org' in link.get('href'): continue
                img_url = link.get('href')
                if img_url and not img_url.startswith('http'):
                    img_url = site_root_url + img_url.lstrip('/')
                if img_url: images.append(img_url)

            description = ""
            meta_desc = [meta for meta in product_info.find_all('meta') if meta.get('itemprop') == 'description']
            if meta_desc: description = meta_desc[0].get('content', '')

            price_value = product_info.find('span', class_='price_value').text.strip() if product_info.find('span', class_='price_value') else "N/A"
            price_discount = None
            sale_value = None
            inner_sale = None

            if product_info.find('div', class_='price discount'):
                price_discount_tag = product_info.find('div', class_='price discount').find('span')
                price_discount = price_discount_tag.text.strip() if price_discount_tag else None

                sale_block = product_info.find('div', class_='sale_block')
                sale_value_tag = sale_block.find('span') if sale_block else None
                sale_value = sale_value_tag.text.strip() if sale_value_tag else None

                inner_sale_div = product_info.find('div', class_='inner-sale')
                inner_sale_tag = inner_sale_div.find('span') if inner_sale_div else None
                inner_sale = inner_sale_tag.text.strip() if inner_sale_tag else None

            products_data.append({
                "brand": product_brand,
                "model": product_model,
                "year": product_year,
                "name": product_name,
                "link": product_link,
                "images": images,
                "description": description,
                "price": price_value,
                "old_price": price_discount,
                "discount": sale_value,
                "economy": inner_sale,
                "site": "rollingmoto"
            })
        except Exception as e:
            print(f"Ошибка парсинга товара Rollingmoto: {e}")
            continue
    return products_data

def _parse_motoland_catalog(soup, site_root_url):
    products_data = []
    catalog_block = soup.find('div', class_='catalog-block')
    if not catalog_block: return []

    product_cards = catalog_block.find_all('div', class_='grid-list__item')

    for product_card in product_cards:
        try:
            product_title_div = product_card.find('div', class_='catalog-block__info-title')
            if not product_title_div: continue

            product_link_tag = product_title_div.find('a')
            if not product_link_tag: continue

            product_link = site_root_url + product_link_tag.get('href').lstrip('/')
            product_link = _normalize_url_slashes(product_link)
            product_name = product_title_div.find('span').text.strip() if product_title_div.find('span') else product_link_tag.text.strip()

            product_brand, product_model, product_year = parse_vehicle_description(product_name)

            images = []
            image_list_link = product_card.find('a', class_='image-list__link')
            if image_list_link:
                product_images_tags = image_list_link.find_all('img')
                for image_tag in product_images_tags:
                    img_url = image_tag.get('data-src')
                    if img_url and not img_url.startswith('http'):
                        img_url = site_root_url + img_url.lstrip('/')
                    if img_url: images.append(img_url)

            price_value = "N/A"
            price_meta_tag = product_card.find('meta', itemprop='price')
            if price_meta_tag:
                price_value = price_meta_tag.get('content', "N/A")

            products_data.append({
                "brand": product_brand,
                "model": product_model,
                "year": product_year,
                "name": product_name,
                "link": product_link,
                "images": images,
                "description": "",
                "price": price_value,
                "old_price": None,
                "discount": None,
                "economy": None,
                "site": "motoland",
            })
        except Exception as e:
            print(f"Ошибка парсинга товара Motoland: {e}")
            continue
    return products_data

def parse_catalog(url):
    url = _normalize_url_slashes(url) # Нормализуем входящий URL
    pagination_base_url = url.split('?')[0] # Базовый URL для пагинации (например, https://www.rollingmoto.ru/catalog/mototekhnika/)
    products_data = []
    page_num = 1
    items_per_page = 20 # Значение по умолчанию, может быть уточнено после первой страницы

    site = 'unknown'
    site_root_url = '' # Новая переменная для корневого URL сайта

    if 'rollingmoto.ru' in url:
        site = 'rollingmoto'
        site_root_url = 'https://www.rollingmoto.ru/'
    elif 'motoland-shop.ru' in url:
        site = 'motoland'
        site_root_url = 'https://motoland-shop.ru/'

    if site == 'unknown':
        return [], 0 # Возвращаем пустой список и 0 товаров для неизвестного сайта

    total_items_overall = 0
    total_pages = 1

    # Шаг 1: Парсим первую страницу для определения общего числа товаров и товаров на страницу
    try:
        soup = _fetch_page(url) # Используем исходный URL для первой страницы

        if site == 'rollingmoto':
            total_items_tag = soup.find('span', class_='element-count muted font_xs rounded3')
            if total_items_tag:
                text = total_items_tag.text.strip()
                match = re.search(r'\d+', text)
                if match:
                    total_items_overall = int(match.group(0))
                    products_on_first_page = soup.find_all('div', class_='catalog_item_wrapp')
                    if products_on_first_page:
                        items_per_page = len(products_on_first_page)
                    total_pages = (total_items_overall + items_per_page - 1) // items_per_page
                else:
                    print("Не удалось определить общее число товаров на первой странице Rollingmoto.")
            else:
                print("Элемент с общим числом товаров не найден на первой странице Rollingmoto.")
            products_data.extend(_parse_rollingmoto_catalog(soup, site_root_url)) # Передаем site_root_url

        elif site == 'motoland':
            total_items_tag = soup.find('span', class_='element-count font_18 bordered button-rounded-x')
            if total_items_tag:
                text = total_items_tag.text.strip()
                match = re.search(r'\d+', text)
                if match:
                    total_items_overall = int(match.group(0))
                    products_on_first_page = soup.find_all('div', class_='grid-list__item')
                    if products_on_first_page:
                        items_per_page = len(products_on_first_page)
                    total_pages = (total_items_overall + items_per_page - 1) // items_per_page
                else:
                    print("Не удалось определить общее число товаров на первой странице Motoland.")
            else:
                print("Элемент с общим числом товаров не найден на первой странице Motoland.")
            products_data.extend(_parse_motoland_catalog(soup, site_root_url)) # Передаем site_root_url

    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети или HTTP при загрузке первой страницы: {e}")
        return [], 0
    except Exception as e:
        print(f"Произошла ошибка во время парсинга первой страницы: {e}")
        return [], 0

    # Шаг 2: Парсим все остальные страницы
    for page_num in range(2, total_pages + 1):
        try:
            current_url = f"{pagination_base_url}?PAGEN_1={page_num}" # Используем pagination_base_url
            current_url = _normalize_url_slashes(current_url) # Нормализуем URL для пагинации
            soup = _fetch_page(current_url)

            if site == 'rollingmoto':
                # print(f"Rollingmoto пагинация: base_url={base_url}, current_url={current_url}") # Удаляем строку для отладки
                products_on_page = soup.find_all('div', class_='catalog_item_wrapp')
                if not products_on_page:
                    print(f"На странице {page_num} товары не найдены. Предполагается конец каталога.")
                    break
                products_data.extend(_parse_rollingmoto_catalog(soup, site_root_url)) # Передаем site_root_url

            elif site == 'motoland':
                catalog_block = soup.find('div', class_='catalog-block')
                if not catalog_block:
                    print(f"Блок каталога на странице Motoland {page_num} не найден. Предполагается конец.")
                    break
                products_on_page = catalog_block.find_all('div', class_='grid-list__item')
                if not products_on_page:
                    print(f"На странице Motoland {page_num} товары не найдены. Предполагается конец каталога.")
                    break
                products_data.extend(_parse_motoland_catalog(soup, site_root_url)) # Передаем site_root_url

        except requests.exceptions.RequestException as e:
            print(f"Ошибка сети или HTTP при загрузке страницы {page_num}: {e}. Пропускаем.")
            continue
        except Exception as e:
            print(f"Ошибка парсинга страницы {page_num}: {e}. Пропускаем.")
            continue

    return products_data, total_items_overall

def parse_product(url):
    site = 'unknown'
    site_root_url = '' # Изменяем base_url на site_root_url
    if 'rollingmoto.ru' in url:
        site = 'rollingmoto'
        site_root_url = 'https://www.rollingmoto.ru/'
    elif 'motoland-shop.ru' in url:
        site = 'motoland'
        site_root_url = 'https://motoland-shop.ru/'
    else:
        print(f"Неподдерживаемый сайт для парсинга товара: {url}")
        return {}

    try:
        soup = _fetch_page(url)
        product_data = {}

        if site == 'rollingmoto':
            try:
                # Получение наименования товара
                product_title_tag = soup.find('h1', {'id': 'pagetitle'})
                product_name = product_title_tag.text.strip() if product_title_tag else "Наименование не найдено"
                product_brand, product_model, product_year = parse_vehicle_description(product_name)

                product_data["brand"] = product_brand
                product_data["model"] = product_model
                product_data["year"] = product_year
                product_data["name"] = product_name
                product_data["link"] = url

                # Получение всех изображений
                images = []
                gallery_items = soup.find_all('div', class_='product-detail-gallery__item')
                for item in gallery_items:
                    img_link = item.find('a', class_='product-detail-gallery__link')
                    if img_link and img_link.has_attr('href'):
                        image_url = img_link['href']
                        if not image_url.startswith('http'):
                            image_url = f"{site_root_url}{image_url}"
                        images.append(_normalize_url_slashes(image_url))
                product_data["images"] = images

                # Получение новой и старой цены
                new_price_tag = soup.find('div', class_='price', attrs={'data-value': True})
                product_data["price"] = new_price_tag['data-value'] if new_price_tag else "N/A"

                old_price_tag = soup.find('div', class_='price discount', attrs={'data-value': True})
                product_data["old_price"] = old_price_tag['data-value'] if old_price_tag else None

                product_data["discount"] = None
                product_data["economy"] = None

                # Получение описания товара
                description_tag = soup.find('div', class_='content detail-text-wrap')
                product_data["description"] = description_tag.get_text(strip=True) if description_tag else ""

                # Получение характеристик товара
                characteristics = {}
                characteristics_table = soup.find('table', class_='props_list nbg')
                if characteristics_table:
                    for row in characteristics_table.find_all('tr', class_='js-prop-replace'):
                        name_tag = row.find('span', class_='js-prop-title')
                        value_tag = row.find('span', class_='js-prop-value')
                        if name_tag and value_tag:
                            name = name_tag.get_text(strip=True)
                            value = value_tag.get_text(strip=True)
                            characteristics[name] = value
                product_data["characteristics"] = characteristics

                product_data["site"] = "rollingmoto"
                return product_data
            except Exception as e:
                print(f"Ошибка парсинга товара Rollingmoto на странице {url}: {e}")
                return {}

        elif site == 'motoland':
            try:
                # Получение наименования товара
                product_name = soup.find('h1', class_='font_24 switcher-title js-popup-title mb mb--0')
                product_data["name"] = product_name.get_text(strip=True) if product_name else "Наименование не найдено"
                product_brand, product_model, product_year = parse_vehicle_description(product_data["name"])

                product_data["brand"] = product_brand
                product_data["model"] = product_model
                product_data["year"] = product_year
                product_data["link"] = url

                # Получение изображений
                images = []
                gallery_div = soup.find('div', class_='detail-gallery-big swipeignore image-list__link')
                if gallery_div:
                    img_tags = gallery_div.find_all('img')
                    for img in img_tags:
                        src = img.get('data-src')
                        if src:
                            images.append(_normalize_url_slashes(site_root_url.rstrip('/') + src))
                product_data["images"] = images

                # Получение цен
                price_row_div = soup.find('div', class_='price__row')
                if price_row_div:
                    new_price_tag = price_row_div.find('span', class_='price__new-val font_24')
                    product_data["price"] = new_price_tag.get_text(strip=True) if new_price_tag else "N/A"

                    old_price_tag = price_row_div.find('del', class_='price__old-val font_15 secondary-color')
                    product_data["old_price"] = old_price_tag.get_text(strip=True) if old_price_tag else None
                else:
                    product_data["price"] = "N/A"
                    product_data["old_price"] = None

                product_data["discount"] = None
                product_data["economy"] = None

                # Получение описания
                description_div = soup.find('div', class_='content content--max-width js-detail-description')
                product_data["description"] = description_div.get_text(strip=True) if description_div else ""

                # Получение характеристик товара
                characteristics = {}
                characteristics_div = soup.find('div', class_='properties-group__items js-offers-group__items-wrap font_15')
                if characteristics_div:
                    items = characteristics_div.find_all('div', class_='properties-group__item')
                    for item in items:
                        name_tag = item.find('span', class_='properties-group__name')
                        value_tag = item.find('div', class_='properties-group__value color_dark')
                        if name_tag and value_tag:
                            name = name_tag.get_text(strip=True)
                            value = value_tag.get_text(strip=True)
                            characteristics[name] = value
                product_data["characteristics"] = characteristics

                product_data["site"] = "motoland"
                return product_data
            except Exception as e:
                print(f"Ошибка парсинга товара Motoland на странице {url}: {e}")
                return {}

    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети или HTTP при загрузке страницы товара {url}: {e}")
        return {}
    except Exception as e:
        print(f"Произошла непредвиденная ошибка во время обработки страницы товара {url}: {e}")
        return {} 