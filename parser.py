import sys
import os
import re
import requests
import zipfile
import tempfile
import shutil
import webbrowser
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QProgressBar, QStatusBar, QLabel, QMenu, QMessageBox, QFileDialog,
    QDialog, QPlainTextEdit, QDialogButtonBox, QAbstractItemView
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QPoint
from PyQt6.QtGui import QPixmap, QAction, QPalette, QColor
from bs4 import BeautifulSoup

# Попробуем импортировать Pillow, но сделаем это необязательным
try:
    from PIL import Image
    from io import BytesIO
    PILLOW_INSTALLED = True
except ImportError:
    PILLOW_INSTALLED = False
    print("Предупреждение: Библиотека Pillow не найдена. Определение формата изображений может быть менее точным.")


# --- Парсер описания ---
def parse_vehicle_description(description):
    brand_match = re.search(r'\b([A-ZА-Я]{2,})\b', description)
    brand = brand_match.group(1) if brand_match else ""
    model_pattern = re.compile(rf'{brand}\s+(.*?)\s+\(?\d{{4}}')
    model_match = model_pattern.search(description)
    model = model_match.group(1).strip() if model_match else ""
    year_match = re.search(r'\(?(\d{4})\)?\s*г?\.', description)
    year = year_match.group(1) if year_match else ""
    return brand, model, year

# --- Поток парсинга по ссылке (с пагинацией и определением общего числа товаров) ---
class ParserThread(QThread):
    # Сигнал прогресса: (номер_страницы, обработано_всего, всего_товаров_общий)
    progress = pyqtSignal(int, int, int)
    product_parsed = pyqtSignal(dict)
    finished = pyqtSignal(list, str)
    # Новый сигнал для обновления статуса загрузки страницы
    status_message = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url.split('?')[0] # Убираем существующие параметры пагинации
        self.base_url = '' # Будет определен на основе URL
        self.paused = False
        self.stopped = False
        self.items_per_page = 20 # Предполагаемое количество товаров на странице по умолчанию

        if 'rollingmoto.ru' in self.url:
            self.site = 'rollingmoto'
            self.base_url = 'https://www.rollingmoto.ru/'
        elif 'motoland-shop.ru' in self.url:
            self.site = 'motoland'
            self.base_url = 'https://motoland-shop.ru/'
        else:
            self.site = 'unknown'
            self.base_url = ''
            self.status_message.emit("Ошибка: Неподдерживаемый сайт.")

    def run(self):
        if self.site == 'unknown':
            self.finished.emit([], "Неподдерживаемый сайт")
            return

        products_data = []
        total_items_processed = 0
        page_title = "Результаты парсинга"

        if self.site == 'rollingmoto':
            # Логика парсинга Rollingmoto (существующая)
            total_items_overall = 0
            total_pages = 1

            try:
                # --- Шаг 1: Парсим первую страницу для определения общего числа товаров ---
                first_page_url = self.url
                self.status_message.emit("Загрузка первой страницы для определения общего числа товаров...")

                response = requests.get(first_page_url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                # Находим заголовок страницы
                page_title_tag = soup.find('h1')
                page_title = page_title_tag.text.strip() if page_title_tag else "Результаты парсинга"

                # Находим элемент с общим числом товаров
                total_items_tag = soup.find('span', class_='element-count muted font_xs rounded3')
                if total_items_tag:
                    text = total_items_tag.text.strip()
                    match = re.search(r'\d+', text)
                    if match:
                        total_items_overall = int(match.group(0))
                        products_on_first_page = soup.find_all('div', class_='catalog_item_wrapp')
                        if products_on_first_page:
                             self.items_per_page = len(products_on_first_page)
                        total_pages = (total_items_overall + self.items_per_page - 1) // self.items_per_page
                        self.status_message.emit(f"Найдено всего товаров: {total_items_overall} на {total_pages} страницах.")
                    else:
                        self.status_message.emit("Не удалось определить общее число товаров на первой странице.")
                        return self._run_without_total_count()
                else:
                    self.status_message.emit("Элемент с общим числом товаров не найден на первой странице.")
                    return self._run_without_total_count()

                # --- Шаг 2: Парсим все страницы, зная общее число и количество страниц ---
                for page_num in range(1, total_pages + 1):
                    if self.stopped: break

                    if page_num > 1:
                        current_url = f"{self.url}{'?PAGEN_1=' + str(page_num)}"
                        self.status_message.emit(f"Загрузка страницы {page_num}/{total_pages}...")
                        try:
                            response = requests.get(current_url, timeout=10)
                            response.raise_for_status()
                            soup = BeautifulSoup(response.text, 'html.parser')
                        except requests.exceptions.RequestException as e:
                             self.status_message.emit(f"Ошибка сети или HTTP при загрузке страницы {page_num}: {e}. Пропускаем.")
                             continue
                        except Exception as e:
                             self.status_message.emit(f"Ошибка парсинга страницы {page_num}: {e}. Пропускаем.")
                             continue

                    products_on_page = soup.find_all('div', class_='catalog_item_wrapp')
                    if not products_on_page and page_num > 1:
                        self.status_message.emit(f"На странице {page_num} товары не найдены. Предполагается конец каталога.")
                        break

                    for product in products_on_page:
                        while self.paused:
                            self.msleep(100)
                            if self.stopped:
                                self.finished.emit(products_data, page_title)
                                return
                        if self.stopped:
                            self.finished.emit(products_data, page_title)
                            return

                        try:
                            product_title = product.find('a', class_="dark_link js-notice-block__title option-font-bold font_sm")
                            if not product_title: continue

                            product_link = self.base_url + product_title.get('href')
                            product_name = product_title.find('span').text.strip()
                            product_brand, product_model, product_year = parse_vehicle_description(product_name)

                            product_info = product.find('div', class_='cost prices clearfix')
                            if not product_info: continue

                            images = []
                            for link in product_info.find_all('link'):
                                if 'schema.org' in link.get('href'): continue
                                img_url = link.get('href')
                                if img_url and not img_url.startswith('http'):
                                    img_url = self.base_url + img_url.lstrip('/')
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
                            })
                            total_items_processed += 1
                            self.progress.emit(page_num, total_items_processed, total_items_overall)
                            self.product_parsed.emit(products_data[-1])

                        except Exception as e:
                            print(f"Ошибка парсинга товара на странице {page_num}, обработано {total_items_processed}: {e}")
                            continue

                if not self.stopped:
                    self.status_message.emit("Парсинг всех страниц завершен.")

            except requests.exceptions.RequestException as e:
                self.status_message.emit(f"Ошибка сети или HTTP при загрузке первой страницы: {e}")
                self.finished.emit(products_data, page_title)
            except Exception as e:
                self.status_message.emit(f"Произошла ошибка во время парсинга первой страницы: {e}")
                self.finished.emit(products_data, page_title)

        elif self.site == 'motoland':
            # Логика парсинга Motoland
            total_items_overall = 0
            total_pages = 1

            try:
                # --- Шаг 1: Парсим первую страницу для определения общего числа товаров ---
                first_page_url = self.url
                self.status_message.emit("Загрузка первой страницы Motoland для определения общего числа товаров...")

                response = requests.get(first_page_url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')

                # Находим заголовок страницы (если есть H1, иначе используем базовый URL)
                page_title_tag = soup.find('h1')
                page_title = page_title_tag.text.strip() if page_title_tag else f"Результаты парсинга {self.base_url}"

                # Находим элемент с общим числом товаров для Motoland
                total_items_tag = soup.find('span', class_='element-count font_18 bordered button-rounded-x')
                if total_items_tag:
                    text = total_items_tag.text.strip()
                    match = re.search(r'\d+', text)
                    if match:
                        total_items_overall = int(match.group(0))
                        # Попробуем определить количество товаров на первой странице, чтобы уточнить items_per_page
                        products_on_first_page = soup.find_all('div', class_='grid-list__item')
                        if products_on_first_page:
                             self.items_per_page = len(products_on_first_page)
                        # Рассчитываем общее количество страниц
                        total_pages = (total_items_overall + self.items_per_page - 1) // self.items_per_page # Округление вверх
                        self.status_message.emit(f"Найдено всего товаров на Motoland: {total_items_overall} на {total_pages} страницах.")
                    else:
                        self.status_message.emit("Не удалось определить общее число товаров на первой странице Motoland.")
                        # Если не удалось найти общее число, продолжаем парсить по страницам, пока не кончатся товары
                        return self._run_motoland_without_total_count()
                else:
                    self.status_message.emit("Элемент с общим числом товаров не найден на первой странице Motoland.")
                    # Если элемент не найден, продолжаем парсить по страницам, пока не кончатся товары
                    return self._run_motoland_without_total_count()

                # --- Шаг 2: Парсим все страницы, зная общее число и количество страниц ---
                for page_num in range(1, total_pages + 1):
                    if self.stopped: break

                    # Для первой страницы HTML уже загружен, для остальных - делаем запрос
                    if page_num > 1:
                        current_url = f"{self.url}{'?PAGEN_1=' + str(page_num)}"
                        self.status_message.emit(f"Загрузка страницы Motoland {page_num}/{total_pages}...")
                        try:
                            response = requests.get(current_url, timeout=10)
                            response.raise_for_status()
                            soup = BeautifulSoup(response.content, 'html.parser')
                        except requests.exceptions.RequestException as e:
                             self.status_message.emit(f"Ошибка сети или HTTP при загрузке страницы Motoland {page_num}: {e}. Пропускаем.")
                             continue
                        except Exception as e:
                             self.status_message.emit(f"Ошибка парсинга страницы Motoland {page_num}: {e}. Пропускаем.")
                             continue

                    # Находим карточки товаров
                    catalog_block = soup.find('div', class_='catalog-block')
                    if not catalog_block:
                         self.status_message.emit(f"Блок каталога на странице Motoland {page_num} не найден.")
                         if page_num == 1: # Если на первой странице нет каталога, это ошибка или пустой каталог
                             self.finished.emit([], page_title)
                             return
                         else: # На последующих страницах отсутствие блока каталога может означать конец
                             break

                    product_cards = catalog_block.find_all('div', class_='grid-list__item')

                    if not product_cards and page_num > 1: # Если на последующих страницах нет товаров, это конец или ошибка
                        self.status_message.emit(f"На странице Motoland {page_num} товары не найдены. Предполагается конец каталога.")
                        break # Выходим из цикла пагинации
                    elif not product_cards and page_num == 1: # Если на первой странице нет товаров
                         self.status_message.emit("Товары на первой странице Motoland не найдены.")
                         self.finished.emit([], page_title)
                         return

                    for product_card in product_cards:
                        while self.paused:
                            self.msleep(100)
                            if self.stopped:
                                self.finished.emit(products_data, page_title)
                                return
                        if self.stopped:
                            self.finished.emit(products_data, page_title)
                            return

                        try:
                            product_title_div = product_card.find('div', class_='catalog-block__info-title')
                            if not product_title_div: continue

                            product_link_tag = product_title_div.find('a')
                            if not product_link_tag: continue

                            product_link = self.base_url + product_link_tag.get('href')
                            product_name = product_title_div.find('span').text.strip() if product_title_div.find('span') else product_link_tag.text.strip()

                            # Для Motoland бренд/модель/год извлекаем из наименования для консистентности, но отображаем полное наименование
                            product_brand, product_model, product_year = parse_vehicle_description(product_name)

                            images = []
                            image_list_link = product_card.find('a', class_='image-list__link')
                            if image_list_link:
                                product_images_tags = image_list_link.find_all('img')
                                for image_tag in product_images_tags:
                                    img_url = image_tag.get('data-src')
                                    if img_url and not img_url.startswith('http'):
                                        img_url = self.base_url + img_url.lstrip('/')
                                    if img_url: images.append(img_url)

                            # --- Парсинг цены для Motoland ---
                            price_value = "N/A"
                            price_meta_tag = product_card.find('meta', itemprop='price')
                            if price_meta_tag:
                                price_value = price_meta_tag.get('content', "N/A")

                            products_data.append({
                                "brand": product_brand,
                                "model": product_model,
                                "year": product_year,
                                "name": product_name, # Полное наименование
                                "link": product_link,
                                "images": images,
                                "description": "",
                                "price": price_value,
                                "old_price": None,
                                "discount": None,
                                "economy": None,
                                "site": "motoland",
                            })
                            total_items_processed += 1
                            self.progress.emit(page_num, total_items_processed, total_items_overall)
                            self.product_parsed.emit(products_data[-1])

                        except Exception as e:
                            print(f"Ошибка парсинга товара на странице Motoland {page_num}, обработано {total_items_processed}: {e}")
                            continue

                if not self.stopped:
                     self.status_message.emit("Парсинг всех страниц Motoland завершен.")

            except requests.exceptions.RequestException as e:
                 self.status_message.emit(f"Ошибка сети или HTTP при загрузке первой страницы Motoland: {e}")
                 self.finished.emit(products_data, page_title)
            except Exception as e:
                 self.status_message.emit(f"Произошла ошибка во время парсинга Motoland: {e}")
                 self.finished.emit(products_data, page_title)

        # Этот self.finished.emit будет вызван после завершения всех веток (rollingmoto или motoland)
        if not self.stopped:
             self.finished.emit(products_data, page_title)

    # Метод для старого поведения Rollingmoto, если не удалось определить общее число товаров
    def _run_without_total_count(self):
         # Этот метод остается только для Rollingmoto
         if self.site != 'rollingmoto':
              # Это не должно происходить, но на всякий случай
              self.finished.emit([], "Ошибка внутренней логики парсера (Rollingmoto fallback)")
              return

         products_data = []
         page_num = 1
         total_items_processed = 0
         page_title = "Результаты парсинга"

         while True:
             if self.stopped: break

             current_url = f"{self.url}{'?PAGEN_1=' + str(page_num) if page_num > 1 else ''}"
             self.status_message.emit(f"Загрузка страницы {page_num} (без определения общего числа)...")

             try:
                 response = requests.get(current_url, timeout=10)
                 response.raise_for_status()
                 soup = BeautifulSoup(response.text, 'html.parser')

                 if page_num == 1:
                      page_title_tag = soup.find('h1')
                      page_title = page_title_tag.text.strip() if page_title_tag else "Результаты парсинга"

                 products_on_page = soup.find_all('div', class_='catalog_item_wrapp')

                 if not products_on_page:
                     if page_num == 1:
                          self.finished.emit([], "Нет товаров")
                     break

                 total_items_on_current_page = len(products_on_page)

                 for product in products_on_page:
                     while self.paused:
                         self.msleep(100)
                         if self.stopped:
                             self.finished.emit(products_data, page_title)
                             return
                     if self.stopped:
                         self.finished.emit(products_data, page_title)
                         return

                     try:
                         product_title = product.find('a', class_="dark_link js-notice-block__title option-font-bold font_sm")
                         if not product_title: continue

                         product_link = self.base_url + product_title.get('href')
                         product_name = product_title.find('span').text.strip()
                         product_brand, product_model, product_year = parse_vehicle_description(product_name)

                         product_info = product.find('div', class_='cost prices clearfix')
                         if not product_info: continue

                         images = []
                         for link in product_info.find_all('link'):
                             if 'schema.org' in link.get('href'): continue
                             img_url = link.get('href')
                             if img_url and not img_url.startswith('http'):
                                 img_url = self.base_url + img_url.lstrip('/')
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
                         })
                         total_items_processed += 1

                         self.progress.emit(page_num, total_items_processed, total_items_processed + total_items_on_current_page) # Прогресс по текущим найденным
                         self.product_parsed.emit(products_data[-1])

                     except Exception as e:
                         print(f"Ошибка парсинга товара на странице {page_num}, обработано {total_items_processed}: {e}")
                         continue

                 page_num += 1

             except requests.exceptions.RequestException as e:
                 self.status_message.emit(f"Ошибка сети или HTTP при загрузке страницы {page_num}: {e}")
                 break
             except Exception as e:
                 self.status_message.emit(f"Произошла ошибка во время парсинга: {e}")
                 break

         self.finished.emit(products_data, page_title)

    # Добавляем метод для парсинга Motoland без определения общего числа (fallback)
    def _run_motoland_without_total_count(self):
        products_data = []
        page_num = 1
        total_items_processed = 0
        page_title = "Результаты парсинга Motoland"

        while True:
            if self.stopped: break

            current_url = f"{self.url}{'?PAGEN_1=' + str(page_num) if page_num > 1 else ''}"
            self.status_message.emit(f"Загрузка страницы Motoland {page_num} (без определения общего числа)...")

            try:
                response = requests.get(current_url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')

                if page_num == 1:
                     page_title_tag = soup.find('h1')
                     page_title = page_title_tag.text.strip() if page_title_tag else "Результаты парсинга Motoland"


                catalog_block = soup.find('div', class_='catalog-block')
                if not catalog_block:
                     if page_num == 1:
                          self.status_message.emit("Блок каталога на первой странице Motoland не найден.")
                          self.finished.emit([], page_title)
                          return
                     else:
                          self.status_message.emit(f"Блок каталога на странице Motoland {page_num} не найден. Предполагается конец.")
                          break

                product_cards = catalog_block.find_all('div', class_='grid-list__item')

                if not product_cards:
                    if page_num == 1:
                         self.status_message.emit("Товары на первой странице Motoland не найдены.")
                         self.finished.emit([], page_title)
                         return
                    else:
                        self.status_message.emit(f"На странице Motoland {page_num} товары не найдены. Предполагается конец каталога.")
                        break

                total_items_on_current_page = len(product_cards)

                for product_card in product_cards:
                    while self.paused:
                        self.msleep(100)
                        if self.stopped:
                            self.finished.emit(products_data, page_title)
                            return
                    if self.stopped:
                        self.finished.emit(products_data, page_title)
                        return

                    try:
                        product_title_div = product_card.find('div', class_='catalog-block__info-title')
                        if not product_title_div: continue

                        product_link_tag = product_title_div.find('a')
                        if not product_link_tag: continue

                        product_link = self.base_url + product_link_tag.get('href')
                        product_name = product_title_div.find('span').text.strip() if product_title_div.find('span') else product_link_tag.text.strip()

                        product_brand, product_model, product_year = parse_vehicle_description(product_name)

                        images = []
                        image_list_link = product_card.find('a', class_='image-list__link')
                        if image_list_link:
                            product_images_tags = image_list_link.find_all('img')
                            for image_tag in product_images_tags:
                                img_url = image_tag.get('data-src')
                                if img_url and not img_url.startswith('http'):
                                    img_url = self.base_url + img_url.lstrip('/')
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
                        total_items_processed += 1

                        self.progress.emit(page_num, total_items_processed, total_items_processed + total_items_on_current_page) # Прогресс по текущим найденным
                        self.product_parsed.emit(products_data[-1])

                    except Exception as e:
                        print(f"Ошибка парсинга товара на странице Motoland {page_num}, обработано {total_items_processed}: {e}")
                        continue

                page_num += 1

            except requests.exceptions.RequestException as e:
                self.status_message.emit(f"Ошибка сети или HTTP при загрузке страницы Motoland {page_num}: {e}")
                break
            except Exception as e:
                self.status_message.emit(f"Произошла ошибка во время парсинга Motoland без полного числа: {e}")
                break

        self.finished.emit(products_data, page_title)

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def stop(self):
        self.stopped = True

# --- Поток парсинга локального файла (без пагинации) ---
class ParserThreadLocal(QThread):
    progress = pyqtSignal(int, int) # Прогресс: (текущий, всего)
    product_parsed = pyqtSignal(dict)
    finished = pyqtSignal(list, str)
    status_message = pyqtSignal(str) # Добавлен сигнал статуса

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.base_url = 'https://www.rollingmoto.ru/' # Базовый URL все равно нужен для изображений
        self.paused = False
        self.stopped = False

    def run(self):
        products_data = []
        self.status_message.emit("Чтение файла...")
        try:
            with open(self.file_path, encoding="utf-8") as f:
                html = f.read()
            soup = BeautifulSoup(html, 'html.parser')

            page_title_tag = soup.find('h1')
            page_title = page_title_tag.text.strip() if page_title_tag else os.path.basename(self.file_path) # Заголовок из H1 или имя файла

            products = soup.find_all('div', class_='catalog_item_wrapp')
            total = len(products)
            self.status_message.emit(f"Найдено {total} товаров в файле. Парсинг...")

            for idx, product in enumerate(products, 1):
                while self.paused:
                    self.msleep(100)
                    if self.stopped:
                        self.finished.emit(products_data, page_title)
                        return
                if self.stopped:
                    self.finished.emit(products_data, page_title)
                    return
                try:
                    product_title = product.find('a', class_="dark_link js-notice-block__title option-font-bold font_sm")
                    if not product_title: continue

                    product_link = self.base_url + product_title.get('href')
                    product_name = product_title.find('span').text.strip()
                    product_brand, product_model, product_year = parse_vehicle_description(product_name)

                    product_info = product.find('div', class_='cost prices clearfix')
                    if not product_info: continue

                    images = []
                    for link in product_info.find_all('link'):
                        if 'schema.org' in link.get('href'):
                            continue
                        img_url = link.get('href')
                        if img_url and not img_url.startswith('http'):
                             img_url = self.base_url + img_url.lstrip('/')
                        if img_url:
                           images.append(img_url)


                    description = ""
                    meta_desc = [meta for meta in product_info.find_all('meta') if meta.get('itemprop') == 'description']
                    if meta_desc:
                        description = meta_desc[0].get('content', '')

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
                    })
                    self.product_parsed.emit(products_data[-1])
                    self.progress.emit(idx, total) # Прогресс для локального файла

                except Exception as e:
                    print(f"Ошибка парсинга товара из файла, индекс {idx}: {e}")
                    continue

            self.finished.emit(products_data, page_title)
        except FileNotFoundError:
            self.finished.emit([], f"Ошибка: Файл не найден по пути {self.file_path}")
        except Exception as e:
            self.finished.emit([], f"Ошибка чтения или парсинга файла: {e}")


    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def stop(self):
        self.stopped = True


# --- Поток архивирования ---
class ArchiveThread(QThread):
    # Сигнал прогресса: (текущий файл/действие, всего действий, сообщение)
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(bool, str) # Сигнал завершения: (успех, сообщение)

    # Принимаем save_path как аргумент
    def __init__(self, products_data, page_title, save_path, base_url='https://www.rollingmoto.ru/'):
        super().__init__()
        self.products_data = products_data
        self.page_title = page_title
        self.save_path = save_path # Сохраняем путь для сохранения архива
        self.base_url = base_url
        self.stopped = False
        try:
            from PIL import Image
            from io import BytesIO
            self.PIL_INSTALLED = True
        except ImportError:
            self.PIL_INSTALLED = False


    def run(self):
        temp_dir = None
        total_images_to_download = sum(len(p.get('images', [])) for p in self.products_data)
        current_image_index = 0
        total_steps = total_images_to_download + 1 # +1 для шага создания ZIP

        if total_images_to_download == 0:
            self.finished.emit(False, "Нет изображений для создания архива.")
            return

        try:
            temp_dir = tempfile.mkdtemp()
            if not os.path.exists(temp_dir):
                 raise Exception("Не удалось создать временную директорию.")

            self.progress.emit(current_image_index, total_steps, "Скачивание изображений...")

            downloaded_images_count = 0
            for product in self.products_data:
                if self.stopped: break

                # Улучшенная очистка имени папки от недопустимых символов
                # Определяем имя папки в зависимости от сайта
                if product.get('site') == 'motoland':
                     folder_name = product.get('name', 'Без названия')
                else:
                     # Старая логика для Rollingmoto и других
                     folder_name = f"{product.get('brand', 'Unknown')}__{product.get('model', 'Unknown')}__{product.get('year', 'Unknown')}"

                folder_name = re.sub(r'[\\/:*?"<>|]', '_', folder_name)
                folder_name = re.sub(r'[\s]+', ' ', folder_name).strip()
                folder_name = folder_name[:200] # Обрезаем длинные имена
                if not folder_name or folder_name == '_': folder_name = "Без названия"
                product_dir = os.path.join(temp_dir, folder_name)
                os.makedirs(product_dir, exist_ok=True)

                for idx, img_url in enumerate(product.get("images", []), 1):
                    if self.stopped: break
                    if not img_url: continue

                    try:
                        img_data = requests.get(img_url, timeout=10).content
                        if not img_data: continue

                        ext = os.path.splitext(img_url)[1].lower()
                        if not ext or len(ext) > 5 or '.' not in ext:
                            if self.PIL_INSTALLED:
                                 try:
                                     from PIL import Image
                                     from io import BytesIO
                                     img = Image.open(BytesIO(img_data))
                                     img_format = img.format.lower()
                                     ext = f".{img_format if img_format != 'jpeg' else 'jpg'}"
                                     img.close()
                                 except Exception:
                                     ext = ".jpg"
                            else:
                                if 'png' in img_url.lower(): ext = '.png'
                                elif 'jpg' in img_url.lower() or 'jpeg' in img_url.lower(): ext = '.jpg'
                                elif 'gif' in img_url.lower(): ext = '.gif'
                                elif 'bmp' in img_url.lower(): ext = '.bmp'
                                else: ext = '.bin'

                        if '.' not in os.path.basename(img_url):
                             filename = f"img_{idx}{ext}"
                        else:
                             filename = os.path.basename(img_url)
                             original_ext_in_url = os.path.splitext(os.path.basename(img_url))[1].lower()
                             if original_ext_in_url and original_ext_in_url not in ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.bin']:
                                 filename = os.path.splitext(filename)[0] + ext

                        img_filename = re.sub(r'[\\/:*?"<>|]', '_', filename)
                        img_filename = re.sub(r'[\s]+', '_', img_filename).strip()
                        if not img_filename or img_filename == '.': img_filename = f"img_{idx}.jpg"

                        img_path = os.path.join(product_dir, img_filename)

                        with open(img_path, "wb") as f:
                            f.write(img_data)
                        downloaded_images_count += 1
                        current_image_index += 1
                        self.progress.emit(current_image_index, total_steps, f"Скачано изображений: {downloaded_images_count}/{total_images_to_download}")


                    except requests.exceptions.RequestException:
                         print(f"Ошибка сети при скачивании изображения для архива: {img_url}")
                    except Exception as e:
                        print(f"Ошибка скачивания изображения для архива {img_url}: {e}")

            if self.stopped:
                 self.finished.emit(False, "Создание архива отменено.")
                 return

            if downloaded_images_count == 0:
                 self.finished.emit(False, "Нет изображений для создания архива.")
                 return

            self.progress.emit(current_image_index, total_steps, "Создание ZIP архива...")

            # Используем путь, выбранный пользователем
            archive_path = self.save_path

            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)

            self.progress.emit(total_steps, total_steps, "Архив успешно создан.")
            self.finished.emit(True, archive_path) # Передаем путь к созданному архиву

        except Exception as e:
            self.finished.emit(False, f"Ошибка при создании архива: {e}")
        finally:
            if temp_dir and os.path.exists(temp_dir):
                 shutil.rmtree(temp_dir, ignore_errors=True)

    def stop(self):
        self.stopped = True


# --- Главное окно ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Почти универсальный парсер made by Motorin")
        self.resize(1200, 700)
        self.products = []
        self.page_title = ""
        self.temp_dir = tempfile.mkdtemp()


        # --- Верхняя панель ---
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Вставьте ссылку с https://www.rollingmoto.ru/")
        self.parse_btn = QPushButton("Начать парсинг по ссылке")
        self.parse_btn.clicked.connect(self.start_parsing)

        self.file_btn = QPushButton("Открыть HTML-файл")
        self.file_btn.clicked.connect(self.open_html_file)

        self.pause_btn = QPushButton("Пауза")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.toggle_pause)

        self.stop_btn = QPushButton("Остановить")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_parsing)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.url_input)
        top_layout.addWidget(self.parse_btn)
        # top_layout.addWidget(self.file_btn)
        # top_layout.addWidget(self.pause_btn)
        # top_layout.addWidget(self.stop_btn)

        # --- Таблица ---
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Наименование", "Цена", "Описание", "Изображения", "Ссылка"])
        self.table.setColumnWidth(0, 250)
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(2, 300)
        self.table.setColumnWidth(3, 300)
        self.table.setColumnWidth(4, 100)
        self.table.verticalHeader().setDefaultSectionSize(56)
        # Добавляем стиль для padding ячеек
        self.table.setStyleSheet("QTableWidget::item { padding: 4px; }")
        # Устанавливаем режим выделения, который позволяет выделять текст
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)


        # --- Прогрессбар и статусбар ---
        self.progress = QProgressBar()
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # --- Кнопка скачать архив ---
        self.archive_btn = QPushButton("Скачать архив")
        self.archive_btn.clicked.connect(self.download_archive)
        # self.archive_btn.setEnabled(False) # Изначально кнопка выключена

        # --- Основной layout ---
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.table)
        main_layout.addWidget(self.progress)
        main_layout.addWidget(self.archive_btn)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        self.thread = None
        self.archive_thread = None

        self._preview_windows = {}


    def start_parsing(self):
        url = self.url_input.text().strip()
        if not url or not (url.startswith("https://www.rollingmoto.ru/") or url.startswith("https://motoland-shop.ru")):
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, вставьте корректную ссылку")
            return
        self._prepare_for_parsing()
        self.thread = ParserThread(url)
        self._connect_thread_signals(self.thread)
        self.thread.start()

    def open_html_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите HTML-файл", "", "HTML Files (*.html *.htm)")
        if not file_path:
            return
        self._prepare_for_parsing()
        self.thread = ParserThreadLocal(file_path)
        self._connect_thread_signals(self.thread)
        self.thread.start()

    def _prepare_for_parsing(self):
         self.table.setRowCount(0)
         self.products = []
         self.page_title = "" # Сбрасываем заголовок страницы
         self.progress.setValue(0)
         # self.archive_btn.setEnabled(False) # Выключаем кнопку архива перед новым парсингом
         self.pause_btn.setEnabled(True)
         self.stop_btn.setEnabled(True)
         self.pause_btn.setText("Пауза")
         self.status.showMessage("Подготовка к парсингу...")

         # При подготовке к новому парсингу закрываем все активные окна превью
         self._close_all_preview_windows()


    def _connect_thread_signals(self, thread):
        if hasattr(self, 'thread') and self.thread is not None and self.thread.isRunning():
             self.thread.stop()
             try:
                # Проверяем, подключены ли сигналы перед отключением, чтобы избежать ошибок
                if self.thread.product_parsed.hasConnections():
                    self.thread.product_parsed.disconnect()
                if self.thread.progress.hasConnections():
                    self.thread.progress.disconnect()
                if self.thread.finished.hasConnections():
                    self.thread.finished.disconnect()
                if hasattr(self.thread, 'status_message') and self.thread.status_message.hasConnections():
                     self.thread.status_message.disconnect()
             except TypeError:
                 pass # Игнорируем ошибку, если сигналы уже были отключены


        thread.product_parsed.connect(self.add_product_to_table)
        thread.progress.connect(self.update_progress)
        thread.finished.connect(self.parsing_finished)
        if hasattr(thread, 'status_message'): # Проверка наличия сигнала у потока
            thread.status_message.connect(self.status.showMessage)


    def update_progress(self, *args):
        if len(args) == 3: # Для ParserThread (номер_страницы, обработано_всего, всего_товаров_общий)
            page_num, processed, total_overall = args
            self.progress.setMaximum(total_overall if total_overall > 0 else processed + 100)
            self.progress.setValue(processed)
            if total_overall > 0:
                self.status.showMessage(f"Страница {page_num}, обработано товаров: {processed}/{total_overall}")
            else:
                 self.status.showMessage(f"Страница {page_num}, обработано товаров: {processed} (общее неизвестно)")

        elif len(args) == 2: # Для ParserThreadLocal (текущий_в_файле, всего_в_файле)
            current, total = args
            self.progress.setMaximum(total)
            self.progress.setValue(current)
            self.status.showMessage(f"Обработано товаров в файле: {current}/{total}")
        else:
            self.status.showMessage(f"Обновление прогресса: {args}")


    def add_product_to_table(self, product):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # --- Наименование ---
        name_widget = QWidget()
        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Проверяем, с какого сайта товар
        if product.get("site") == "motoland":
             # Для Motoland показываем полное наименование как текст
             name_label = QLabel(product["name"])
             name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)
             name_label.setOpenExternalLinks(True)
             hbox.addWidget(name_label)
        else:
             # Для Rollingmoto и других - кнопки Бренд, Модель, Год
             brand_btn = QPushButton(product["brand"])
             brand_btn.setStyleSheet("font-weight:bold; color:#1565c0; background: none; border: none; text-align: left;")
             brand_btn.clicked.connect(lambda _, v=product["brand"]: self.copy_to_clipboard(v, f"Скопирован бренд - {v}"))
             hbox.addWidget(brand_btn)

             model_btn = QPushButton(product["model"])
             model_btn.setStyleSheet("color:#222; background: none; border: none; text-align: left;")
             model_btn.clicked.connect(lambda _, v=product["model"]: self.copy_to_clipboard(v, f"Скопирована модель - {v}"))
             hbox.addWidget(model_btn)

             year_btn = QPushButton(product["year"])
             year_btn.setStyleSheet("color:#888; background: none; border: none; text-align: left;")
             year_btn.clicked.connect(lambda _, v=product["year"]: self.copy_to_clipboard(v, f"Скопирован год - {v}"))
             hbox.addWidget(year_btn)

        hbox.addStretch(1)
        name_widget.setLayout(hbox)
        self.table.setCellWidget(row, 0, name_widget)

        # --- Цена ---
        price_widget = QWidget()
        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        price_btn = QPushButton(f"Цена: {product['price']} ₽")
        price_btn.setStyleSheet("color:green; background: none; border: none; text-align: left;")
        price_btn.clicked.connect(lambda _, v=product["price"]: self.copy_to_clipboard(v.replace("₽", "").strip(), f"Скопирована цена - {v}"))
        vbox.addWidget(price_btn)
        if product["old_price"]:
            old_btn = QPushButton(f"Старая цена: {product['old_price']}")
            old_btn.setStyleSheet("color:gray; background: none; border: none; text-align: left;")
            old_btn.clicked.connect(lambda _, v=product["old_price"]: self.copy_to_clipboard(v.replace("₽", "").strip(), f"Скопирована старая цена - {v}"))
            vbox.addWidget(old_btn)
        if product["discount"]:
            discount_text = product['discount'].replace("%", "").strip() + " %"
            disc_btn = QPushButton(f"Скидка: {discount_text}")
            disc_btn.setStyleSheet("color:red; background: none; border: none; text-align: left;")
            disc_btn.clicked.connect(lambda _, v=product["discount"]: self.copy_to_clipboard(v.replace("%", "").strip(), f"Скопирована скидка - {v}"))
            vbox.addWidget(disc_btn)
        if product["economy"]:
            economy_text = product['economy'].replace("₽", "").strip() + " ₽"
            econ_btn = QPushButton(f"Экономия: {economy_text}")
            econ_btn.setStyleSheet("color:orange; background: none; border: none; text-align: left;")
            econ_btn.clicked.connect(lambda _, v=product["economy"]: self.copy_to_clipboard(v.replace("₽", "").strip(), f"Скопирована экономия - {v}"))
            vbox.addWidget(econ_btn)
        vbox.addStretch(1)
        price_widget.setLayout(vbox)
        self.table.setCellWidget(row, 1, price_widget)


        # --- Описание ---
        desc_widget = QWidget()
        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        description_text = product.get("description", "")
        short_desc = description_text[:50] + ("..." if len(description_text) > 50 else "")
        desc_label = QLabel(short_desc)
        desc_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)
        desc_label.setOpenExternalLinks(True)

        show_btn = QPushButton("Показать")
        show_btn.setEnabled(bool(description_text))
        show_btn.clicked.connect(lambda _, d=description_text: self.show_full_description(d))

        copy_btn = QPushButton("Скопировать")
        copy_btn.setEnabled(bool(description_text))
        copy_btn.clicked.connect(lambda _, d=description_text: self.copy_to_clipboard(d, "Скопировано описание"))

        hbox.addWidget(desc_label)
        hbox.addWidget(show_btn)
        hbox.addWidget(copy_btn)
        hbox.addStretch(1)
        desc_widget.setLayout(hbox)
        self.table.setCellWidget(row, 2, desc_widget)

        # --- Изображения ---
        img_widget = QWidget()
        hbox2 = QHBoxLayout()
        hbox2.setContentsMargins(0, 0, 0, 0)
        hbox2.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        for img_url in product.get("images", []):
            img_label = QLabel()
            img_label.setFixedSize(48, 48)
            try:
                img_data = requests.get(img_url, timeout=5).content
                pixmap = QPixmap()
                pixmap.loadFromData(img_data)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(img_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    img_label.setPixmap(scaled_pixmap)
                    img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

                    # Превью при наведении (более надежный способ с отдельным окном)
                    img_label.setMouseTracking(True)
                    # Передаем ссылку на self в лямбду
                    img_label.enterEvent = lambda event, url=img_url, label=img_label, mw=self: mw._show_preview_window(event, url, label)
                    img_label.leaveEvent = lambda event, label=img_label, mw=self: mw._hide_preview_window(event, label)

                else:
                     img_label.setText("img")
                     img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)


            except Exception as e:
                print(f"Ошибка загрузки миниатюры или установки пиксмапа: {e}")
                img_label.setText("img")
                img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            img_label.mousePressEvent = lambda event, url=img_url: self.show_image_menu(url)

            hbox2.addWidget(img_label)

        hbox2.addStretch(1)
        img_widget.setLayout(hbox2)
        self.table.setCellWidget(row, 3, img_widget)

        # --- Ссылка на товар ---
        link_widget = QWidget()
        hbox_link = QHBoxLayout()
        hbox_link.setContentsMargins(0, 0, 0, 0)
        hbox_link.setAlignment(Qt.AlignmentFlag.AlignCenter)

        link_btn = QPushButton("Открыть")
        product_link = product.get("link")
        link_btn.setEnabled(bool(product_link))
        link_btn.clicked.connect(lambda _, url=product_link: self.open_url_in_browser(url))

        hbox_link.addWidget(link_btn)
        link_widget.setLayout(hbox_link)
        self.table.setCellWidget(row, 4, link_widget)


        # --- Сохраняем продукт ---
        self.products.append(product)

    def _show_preview_window(self, event, image_url, img_label):
        if img_label in self._preview_windows and self._preview_windows[img_label].isVisible():
             return

        try:
            img_data = requests.get(image_url, timeout=5).content
            preview_pixmap = QPixmap()
            preview_pixmap.loadFromData(img_data)
            if preview_pixmap.isNull():
                 print(f"Не удалось загрузить изображение для превью из данных: {image_url}")
                 return


            preview_label = QLabel()
            scaled_preview = preview_pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            preview_label.setPixmap(scaled_preview)
            preview_label.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
            preview_label.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            preview_label.setToolTipDuration(5000)


            tooltip_pos = QPoint(int(event.globalPosition().x()), int(event.globalPosition().y()))
            offset = QPoint(20, 20)
            preview_label.move(tooltip_pos + offset)

            preview_label.show()

            self._preview_windows[img_label] = preview_label
            preview_label.destroyed.connect(lambda: self._preview_windows.pop(img_label, None))


        except requests.exceptions.RequestException as e:
             print(f"Ошибка сети при загрузке превью изображения {image_url}: {e}")
        except Exception as e:
             print(f"Не удалось создать окно превью для {image_url}: {e}")


    def _hide_preview_window(self, event, img_label):
        if img_label in self._preview_windows:
             preview_window = self._preview_windows[img_label]
             if preview_window is not None and preview_window.isVisible():
                  preview_window.close()


    def _close_all_preview_windows(self):
        for img_label, preview_window in list(self._preview_windows.items()):
            if preview_window is not None and preview_window.isVisible():
                 preview_window.close()
        self._preview_windows.clear()


    def copy_to_clipboard(self, text, message):
        QApplication.clipboard().setText(text)
        self.status.showMessage(message, 3000)

    def show_full_description(self, description):
        if not description or not description.strip():
            QMessageBox.information(self, "Описание", "Описание отсутствует.")
            return

        dialog = DescriptionDialog(description, self)
        dialog.exec()


    def show_image_menu(self, image_url):
        menu = QMenu(self)
        view_action = QAction("Посмотреть", self)
        if image_url:
            view_action.triggered.connect(lambda: webbrowser.open(image_url))
        else:
            view_action.setEnabled(False)

        download_action = QAction("Скачать", self)
        if image_url:
            download_action.triggered.connect(lambda: self.download_image(image_url))
        else:
            download_action.setEnabled(False)

        menu.addAction(view_action)
        menu.addAction(download_action)
        cursor = self.cursor()
        menu.exec(cursor.pos())

    def open_url_in_browser(self, url):
        if url:
            try:
                webbrowser.open(url)
                self.status.showMessage(f"Открыта ссылка в браузере: {url}", 5000)
            except Exception as e:
                self.status.showMessage(f"Ошибка при открытии ссылки {url}: {e}", 5000)
        else:
            self.status.showMessage("Нет ссылки для открытия", 3000)


    def download_image(self, image_url):
        if not image_url:
             self.status.showMessage("Ошибка: Нет ссылки для скачивания изображения", 3000)
             return

        try:
            self.status.showMessage(f"Скачивание изображения: {image_url}", 0)
            img_data = requests.get(image_url, timeout=10).content
            if not img_data:
                self.status.showMessage("Ошибка: Не удалось загрузить данные изображения", 3000)
                return

            filename = os.path.basename(image_url)
            ext = os.path.splitext(filename)[1].lower()
            if not ext or len(ext) > 5 or '.' not in ext:
                if PILLOW_INSTALLED:
                     try:
                         from PIL import Image
                         from io import BytesIO
                         img = Image.open(BytesIO(img_data))
                         img_format = img.format.lower()
                         ext = f".{img_format if img_format != 'jpeg' else 'jpg'}"
                         img.close()
                     except Exception as e:
                         ext = ".jpg"
                         print(e)
                else:
                    if 'png' in image_url.lower(): ext = '.png'
                    elif 'jpg' in image_url.lower() or 'jpeg' in image_url.lower(): ext = '.jpg'
                    elif 'gif' in image_url.lower(): ext = '.gif'
                    elif 'bmp' in image_url.lower(): ext = '.bmp'
                    else: ext = '.bin'

            if '.' not in os.path.basename(image_url):
                 filename += ext
            else:
                 original_ext_in_url = os.path.splitext(os.path.basename(image_url))[1].lower()
                 if original_ext_in_url and original_ext_in_url not in ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.bin']:
                     filename = os.path.splitext(filename)[0] + ext

            file_filter = "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
            save_path, _ = QFileDialog.getSaveFileName(self, "Сохранить изображение", filename, file_filter)

            if not save_path:
                self.status.showMessage("Скачивание отменено пользователем", 3000)
                return

            with open(save_path, "wb") as f:
                f.write(img_data)
            self.status.showMessage(f"Изображение сохранено: {save_path}", 7000)

        except requests.exceptions.RequestException:
             self.status.showMessage("Ошибка сети при скачивании изображения", 3000)
        except Exception as e:
            self.status.showMessage(f"Ошибка скачивания изображения: {e}", 3000)


    def toggle_pause(self):
        if not hasattr(self, 'thread') or self.thread is None:
            self.status.showMessage("Парсинг не запущен", 3000)
            return

        if self.thread.isRunning():
            if not self.thread.paused:
                self.thread.pause()
                self.pause_btn.setText("Продолжить")
                self.status.showMessage("Парсинг на паузе")
            else:
                self.thread.resume()
                self.pause_btn.setText("Пауза")
                self.status.showMessage("Парсинг продолжается")
        else:
             self.status.showMessage("Поток парсинга не активен", 3000)


    def stop_parsing(self):
        if hasattr(self, 'thread') and self.thread is not None and self.thread.isRunning():
            self.thread.stop()
            self.status.showMessage("Запрос на остановку парсинга. Ожидайте завершения текущей операции...", 0)
        else:
             self.status.showMessage("Парсинг не запущен или уже остановлен", 3000)


    def parsing_finished(self, products, page_title):
        # Убедимся, что сохраняем переданный список продуктов
        self.products = products
        self.page_title = page_title

        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setText("Пауза")

        # Включаем кнопку архива, если список продуктов не пустой
        self.archive_btn.setEnabled(len(self.products) > 0)

        if hasattr(self, 'thread') and self.thread is not None and self.thread.stopped:
             self.status.showMessage(f"Парсинг остановлен пользователем. Собрано товаров: {len(self.products)}", 5000)
        elif len(self.products) > 0:
            self.status.showMessage(f"Парсинг завершён. Найдено товаров: {len(self.products)}", 5000)
        else:
            self.status.showMessage("Парсинг завершён. Товары не найдены или произошла ошибка.", 5000)


    def download_archive(self):
        if not self.products:
            QMessageBox.information(self, "Информация", "Нет данных для создания архива.")
            self.status.showMessage("Нет данных для создания архива", 3000)
            return

        # Генерируем предлагаемое имя файла
        archive_name = f"{self.page_title}"
        archive_name = re.sub(r'[\\/:*?"<>|]', '_', archive_name)
        archive_name = re.sub(r'[\s]+', ' ', archive_name).strip()
        if not archive_name: archive_name = "Архив"
        if not archive_name.endswith('.zip'): archive_name += '.zip'

        # Открываем диалог сохранения файла
        # Указываем директорию по умолчанию (например, Рабочий стол) и предлагаемое имя файла
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        # Стандартные фильтры для ZIP файлов
        file_filter = "ZIP Files (*.zip);;All Files (*)"
        save_path, _ = QFileDialog.getSaveFileName(self, "Сохранить архив", os.path.join(desktop, archive_name), file_filter)

        # Если пользователь отменил диалог, выходим
        if not save_path:
            self.status.showMessage("Создание архива отменено пользователем", 3000)
            return

        # Запускаем поток архивирования, передавая выбранный путь
        # Убедимся, что self.thread не None перед доступом к base_url
        base_url = self.thread.base_url if self.thread and hasattr(self.thread, 'base_url') else 'https://www.rollingmoto.ru/'
        self.archive_thread = ArchiveThread(self.products, self.page_title, save_path, base_url)
        self.archive_thread.progress.connect(self.update_archive_progress)
        self.archive_thread.finished.connect(self.archive_finished)
        self.archive_thread.start()


    def update_archive_progress(self, current, total, message):
        self.progress.setMaximum(total)
        self.progress.setValue(current)
        self.status.showMessage(f"Создание архива: {message}")

    def archive_finished(self, success, message):
        self.archive_btn.setEnabled(True)
        self.progress.setValue(0)

        if success:
            archive_path = message
            self.status.showMessage(f"Архив сохранён: '{os.path.basename(archive_path)}'", 10000)
            QMessageBox.information(self, "Готово", f"Архив успешно сохранён:\n'{archive_path}'")
        else:
            self.status.showMessage(f"Ошибка создания архива: {message}", 7000)
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать архив:\n{message}")

        self.archive_thread = None


    def closeEvent(self, event):
        if hasattr(self, 'thread') and self.thread is not None and self.thread.isRunning():
            self.thread.stop()
            self.thread.wait(3000)

        if hasattr(self, 'archive_thread') and self.archive_thread is not None and self.archive_thread.isRunning():
            self.archive_thread.stop()
            self.archive_thread.wait(3000)

        self._close_all_preview_windows()

        # Удаляем временную директорию при закрытии приложения
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
             try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
             except Exception as e:
                 print(f"Не удалось удалить временную директорию {self.temp_dir}: {e}")


        super().closeEvent(event)


class DescriptionDialog(QDialog):
    def __init__(self, description, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Полное описание")
        self.resize(500, 400)

        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlainText(description)
        self.description_edit.setReadOnly(True)
        self.description_edit.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self.description_edit)
        layout.addWidget(self.button_box)
        self.setLayout(layout)
        self.setModal(True)


def set_light_theme(app):
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(245, 245, 245))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 220))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Button, QColor(245, 245, 245))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(30, 144, 255))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    set_light_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())