import logging
from flask import Flask, request, jsonify, send_file, render_template
import re
import os
from flask_cors import CORS # Импортируем CORS
from parser_logic import parse_product, parse_catalog
from archiver import create_zip_archive

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*", "methods": "*"}}) # Инициализируем CORS для вашего Flask-приложения

@app.route('/')
def test_page():
    logging.info("Запрос на главную страницу")
    return "Главная страница"

@app.route('/test')
def test_page():
    logging.info("Запрос на страницу теста")
    return render_template('test.html')

@app.route('/test_rollingmoto', methods=['POST'])
def test_rollingmoto():
    logging.info("Получен запрос на парсинг RollingMoto для теста")
    data = request.get_json()
    url = data.get('url')

    if not url:
        logging.warning("URL не предоставлен в запросе на парсинг RollingMoto")
        return jsonify({"error": "URL is required"}), 400

    # Здесь мы используем существующую логику парсинга каталога
    # Вы можете адаптировать это, если вам нужна другая логика парсинга
    try:
        products, total_items = parse_catalog(url)
        if products:
            logging.info(f"Успешно спарсен каталог RollingMoto: {url}, найдено товаров: {total_items}")
            return jsonify({"type": "catalog", "products": products, "totalItems": total_items})
        else:
            logging.error(f"Ошибка парсинга каталога RollingMoto или товары не найдены: {url}")
            return jsonify({"error": "Ошибка парсинга каталога или товары не найдены"}), 500
    except Exception as e:
        logging.error(f"Ошибка при парсинге RollingMoto: {str(e)}", exc_info=True)
        return jsonify({"error": f"Ошибка при парсинге RollingMoto: {str(e)}"}), 500

@app.route('/parse_url', methods=['POST'])
def parse_url():
    logging.info("Получен запрос на парсинг URL")
    data = request.get_json()
    url = data.get('url')

    if not url:
        logging.warning("URL не предоставлен в запросе на парсинг")
        return jsonify({"error": "URL is required"}), 400

    if not re.match(r"^https?://(www\.rollingmoto\.ru/|motoland-shop\.ru/)", url):
        logging.warning(f"Получен неверный URL: {url}")
        return jsonify({"error": "Неверный URL. Поддерживаются только rollingmoto.ru и motoland-shop.ru"}), 400

    # Determine if it's a product page or a catalog page
    is_rollingmoto_product = "rollingmoto.ru" in url and ("/product/" in url or "/moto/" in url)
    # Для Motoland, URL товара обычно имеет "/catalog/" и затем глубокий путь с несколькими сегментами
    # Например: /catalog/mototekhnika/mototsikly_1/enduro_1/mototsikl_motoland_250_enduro_gs_172fmm_5_pr250_/
    # Я буду искать как минимум 4 сегмента после "/catalog/"
    path_only_url = url.split('?')[0].split('#')[0] # Удаляем параметры запроса и хеш
    is_motoland_product = "motoland-shop.ru" in url and re.search(r"/catalog(?:/[^/]+){4,}/?$", path_only_url)

    if is_rollingmoto_product or is_motoland_product:
        logging.info(f"Определение типа страницы: товар. URL: {url}")
        product_details = parse_product(url)
        if product_details:
            logging.info(f"Успешно спарсен товар: {url}")
            return jsonify({"type": "product", "details": product_details})
        else:
            logging.error(f"Ошибка парсинга страницы товара: {url}")
            return jsonify({"error": "Ошибка парсинга страницы товара"}), 500
    else:
        logging.info(f"Определение типа страницы: каталог. URL: {url}")
        products, total_items = parse_catalog(url)
        if products:
            logging.info(f"Успешно спарсен каталог: {url}, найдено товаров: {total_items}")
            return jsonify({"type": "catalog", "products": products, "totalItems": total_items})
        else:
            logging.error(f"Ошибка парсинга каталога или товары не найдены: {url}")
            return jsonify({"error": "Ошибка парсинга каталога или товары не найдены"}), 500

@app.route('/download_archive', methods=['POST'])
def download_archive():
    logging.info("Получен запрос на скачивание архива")
    data = request.get_json()
    # Теперь ожидаем получить список полных данных о товарах
    products_data = data.get('products_data')

    if not products_data:
        logging.warning("Список товаров для архива не предоставлен")
        return jsonify({"error": "Список товаров для архива обязателен"}), 400

    archive_path = None # Инициализируем archive_path
    try:
        archive_path = create_zip_archive(products_data)
        logging.info(f"Архив успешно создан: {archive_path}")
        # Отправляем файл клиенту
        response = send_file(archive_path, as_attachment=True, download_name="product_images.zip")
        return response
    except Exception as e:
        logging.error(f"Ошибка при создании архива: {str(e)}", exc_info=True)
        return jsonify({"error": f"Ошибка при создании архива: {str(e)}"}), 500
    finally:
        # Удаляем временный архив после отправки
        if archive_path and os.path.exists(archive_path):
            try:
                os.remove(archive_path)
                logging.info(f"Временный архив удален: {archive_path}")
                # Также удаляем временную директорию, если она была создана archiver.py
                # archiver.py сам удаляет временную директорию в блоке finally
            except Exception as e:
                logging.error(f"Ошибка при удалении временного архива: {e}", exc_info=True)
                print(f"Ошибка при удалении временного архива: {e}")

if __name__ == '__main__':
    app.run(debug=False) 