from PIL import Image, ImageDraw, ImageFont
import io


def add_watermark(image_bytes: bytes, text: str = "SkyDe NFT") -> bytes:
    """Добавить водяной знак на изображение."""

    # Открываем изображение
    image = Image.open(io.BytesIO(image_bytes))

    # Конвертируем в RGBA если нужно
    if image.mode != 'RGBA':
        image = image.convert('RGBA')

    # Создаем слой для водяного знака
    watermark_layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark_layer)

    # Получаем размеры изображения
    width, height = image.size

    # Размер шрифта в зависимости от размера изображения
    font_size = int(min(width, height) / 10)

    try:
        # Пытаемся использовать стандартный шрифт
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        try:
            # Для Windows
            font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", font_size)
        except:
            # Если не найден, используем дефолтный
            font = ImageFont.load_default()

    # Получаем размеры текста
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Рассчитываем позицию для диагонального размещения
    diagonal = int((width**2 + height**2) ** 0.5)
    rotated_watermark = Image.new('RGBA', (diagonal, diagonal), (0, 0, 0, 0))
    rotated_draw = ImageDraw.Draw(rotated_watermark)

    # Рисуем текст несколько раз по диагонали
    spacing = int(diagonal / 3)

    for i in range(-1, 3):
        for j in range(-1, 3):
            x = diagonal // 2 - text_width // 2 + i * spacing
            y = diagonal // 2 - text_height // 2 + j * spacing

            # Полупрозрачный белый текст с черной обводкой
            rotated_draw.text((x - 2, y - 2), text, font=font, fill=(0, 0, 0, 100))
            rotated_draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 100))
            rotated_draw.text((x, y), text, font=font, fill=(255, 255, 255, 120))

    # Поворачиваем на 45 градусов
    rotated_watermark = rotated_watermark.rotate(45, expand=False)

    # Обрезаем до размера исходного изображения
    left = (diagonal - width) // 2
    top = (diagonal - height) // 2
    rotated_watermark = rotated_watermark.crop((left, top, left + width, top + height))

    # Накладываем водяной знак на изображение
    watermarked = Image.alpha_composite(image, rotated_watermark)

    # Конвертируем обратно в RGB для сохранения в JPEG
    watermarked = watermarked.convert('RGB')

    # Сохраняем в bytes
    output = io.BytesIO()
    watermarked.save(output, format='JPEG', quality=95)
    output.seek(0)

    return output.getvalue()