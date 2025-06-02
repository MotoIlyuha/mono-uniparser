import requests
import zipfile
import tempfile
import shutil
import os
import re
from PIL import Image
from io import BytesIO

def download_image(url, destination_path):
    try:
        img_data = requests.get(url, timeout=10).content
        if not img_data: return False

        ext = os.path.splitext(url)[1].lower()
        if not ext or len(ext) > 5 or '.' not in ext:
            try:
                img = Image.open(BytesIO(img_data))
                img_format = img.format.lower()
                ext = f".{img_format if img_format != 'jpeg' else 'jpg'}"
                img.close()
            except Exception:
                ext = ".jpg"

        filename = os.path.basename(url)
        if '.' not in filename:
             filename += ext
        else:
             original_ext_in_url = os.path.splitext(os.path.basename(url))[1].lower()
             if original_ext_in_url and original_ext_in_url not in ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.bin']:
                 filename = os.path.splitext(filename)[0] + ext

        img_filename = re.sub(r'[\\/:*?"<>|]', '_', filename)
        img_filename = re.sub(r'[\\s]+', '_', img_filename).strip()
        if not img_filename or img_filename == '.': img_filename = f"img_{len(img_data)}.jpg" # Fallback filename

        final_path = os.path.join(destination_path, img_filename)
        with open(final_path, "wb") as f:
            f.write(img_data)
        return True
    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети при скачивании изображения {url}: {e}")
        return False
    except Exception as e:
        print(f"Ошибка скачивания изображения {url}: {e}")
        return False

def create_zip_archive(product_data_list):
    temp_dir = None
    archive_name = "product_images.zip"
    try:
        temp_dir = tempfile.mkdtemp()
        if not os.path.exists(temp_dir):
             raise Exception("Не удалось создать временную директорию.")

        for product in product_data_list:
            # Улучшенная очистка имени папки от недопустимых символов
            folder_name = product.get('name', 'Без названия')
            folder_name = re.sub(r'[\\/:*?"<>|]', '_', folder_name)
            folder_name = re.sub(r'[\\s]+', ' ', folder_name).strip()
            folder_name = folder_name[:200] # Обрезаем длинные имена
            if not folder_name or folder_name == '_': folder_name = "Без названия"
            product_dir = os.path.join(temp_dir, folder_name)
            os.makedirs(product_dir, exist_ok=True)

            for img_url in product.get("images", []):
                download_image(img_url, product_dir)

        # Путь для сохранения архива, который Flask затем отправит
        # Мы не знаем путь сохранения на стороне клиента, поэтому создаем временный архив
        archive_path = os.path.join(temp_dir, archive_name) 

        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zipf.write(file_path, arcname)

        # Возвращаем путь к архиву. app.py будет отвечать за его отправку и удаление
        return archive_path

    except Exception as e:
        print(f"Ошибка при создании архива: {e}")
        # В случае ошибки, очистим временную директорию
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise # Перевыбрасываем исключение, чтобы Flask мог его обработать 