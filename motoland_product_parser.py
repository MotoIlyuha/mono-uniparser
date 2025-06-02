import requests
from bs4 import BeautifulSoup

def parse_motoland_images(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Вызвать исключение для плохих кодов состояния (4xx или 5xx)
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении страницы: {e}")
        return [], None, None, None, {}, None

    soup = BeautifulSoup(response.text, 'html.parser')
    image_urls = []
    product_name = None
    new_price = None
    old_price = None
    characteristics = {}
    description = None

    # Найти div с классом "detail-gallery-big swipeignore image-list__link"
    gallery_div = soup.find('div', class_='detail-gallery-big swipeignore image-list__link')

    if gallery_div:
        # Найти все теги img внутри этого div
        img_tags = gallery_div.find_all('img')
        for img in img_tags:
            src = img.get('data-src')
            if src:
                image_urls.append(src)
    else:
        print("Div с указанным классом не найден.")

    # Найти наименование товара в h1 с классом "font_24 switcher-title js-popup-title mb mb--0"
    name_tag = soup.find('h1', class_='font_24 switcher-title js-popup-title mb mb--0')
    if name_tag:
        product_name = name_tag.get_text(strip=True)

    # Найти цены
    price_row_div = soup.find('div', class_='price__row')
    if price_row_div:
        new_price_tag = price_row_div.find('span', class_='price__new-val font_24')
        if new_price_tag:
            new_price = new_price_tag.get_text(strip=True)

        old_price_tag = price_row_div.find('del', class_='price__old-val font_15 secondary-color')
        if old_price_tag:
            old_price = old_price_tag.get_text(strip=True)

    # Найти характеристики товара
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

    # Найти описание товара
    description_div = soup.find('div', class_='content content--max-width js-detail-description')
    if description_div:
        description = description_div.get_text(strip=True)

    return image_urls, product_name, new_price, old_price, characteristics, description

if __name__ == "__main__":
    target_url = "https://motoland-shop.ru/catalog/mototekhnika/mototsikly_1/enduro_1/mototsikl_motoland_250_enduro_gs_172fmm_5_pr250_/#char"
    images, name, new_price, old_price, characteristics, description = parse_motoland_images(target_url)

    if name:
        print(f"Наименование товара: {name}")

    if new_price:
        print(f"Новая цена: {new_price}")

    if old_price:
        print(f"Старая цена: {old_price}")

    if characteristics:
        print("Характеристики:")
        for key, value in characteristics.items():
            print(f"  {key}: {value}")

    if description:
        print(f"Описание: {description}")

    if images:
        print("Найденные URL-адреса изображений:")
        for img_url in images:
            print(img_url)
    else:
        print("Изображения не найдены или произошла ошибка.")
