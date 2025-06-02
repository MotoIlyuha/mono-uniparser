import requests
from bs4 import BeautifulSoup

def parse_rollingmoto_product(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Вызовет исключение для ошибок HTTP
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к URL: {e}")
        return None, None, None, None, None, None

    soup = BeautifulSoup(response.text, 'html.parser')

    # Получение наименования товара
    product_title_tag = soup.find('h1', {'id': 'pagetitle'})
    product_title = product_title_tag.text.strip() if product_title_tag else "Наименование не найдено"

    # Получение всех изображений
    image_urls = []
    # Ищем div с классом 'owl-stage' и стилем 'transform: translate3d(0px, 0px, 0px); transition: all; width: 3900px;' (или его части)
    # Поскольку стили могут меняться, лучше ориентироваться на класс и родительский элемент, если возможно.
    # В данном случае, я буду искать 'a' теги внутри 'div' с классом 'product-detail-gallery__item'
    gallery_items = soup.find_all('div', class_='product-detail-gallery__item')
    for item in gallery_items:
        img_link = item.find('a', class_='product-detail-gallery__link')
        if img_link and img_link.has_attr('href'):
            image_url = img_link['href']
            # Проверяем, является ли URL абсолютным или относительным
            if not image_url.startswith('http'):
                image_url = f"https://www.rollingmoto.ru{image_url}" # Добавляем базовый URL
            image_urls.append(image_url)

    # Получение новой и старой цены
    new_price_tag = soup.find('div', class_='price', attrs={'data-value': True})
    new_price = new_price_tag['data-value'] if new_price_tag else "Цена не найдена"

    old_price_tag = soup.find('div', class_='price discount', attrs={'data-value': True})
    old_price = old_price_tag['data-value'] if old_price_tag else "Старая цена не найдена"

    # Получение описания товара
    description_tag = soup.find('div', class_='content detail-text-wrap')
    description = description_tag.get_text(strip=True) if description_tag else "Описание не найдено"

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

    return product_title, image_urls, new_price, old_price, description, characteristics

if __name__ == "__main__":
    product_url = "https://www.rollingmoto.ru/product/mototsikl-ataki-carrera-300-4t-172fmm-5-pts-19-17-2024-g-_110758/?oid=110763#props"
    title, images, new_price, old_price, description, characteristics = parse_rollingmoto_product(product_url)

    print(f"Наименование товара: {title}")
    print("Изображения:")
    for img_url in images:
        print(f"- {img_url}")
    print(f"Новая цена: {new_price} ₽")
    print(f"Старая цена: {old_price} ₽")
    print(f"Описание: {description}")
    print("Характеристики:")
    if characteristics:
        for key, value in characteristics.items():
            print(f"- {key}: {value}")
    else:
        print("Характеристики не найдены")
