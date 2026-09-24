import asyncio
import os
import io
import tempfile
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from PIL import Image, ImageDraw, ImageFont
from colorthief import ColorThief

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())

class CollectingPhotos(StatesGroup):
    waiting_photos = State()

user_photos = {}
WATERMARK_TEXT = "@greedeeworld"


def create_collage(images: list, max_size=800) -> bytes:
    n = len(images)
    if n == 2:
        cols, rows = 2, 1
    elif n <= 4:
        cols, rows = 2, 2
    else:
        cols, rows = 3, 2

    cell_size = max_size // cols
    canvas = Image.new("RGB", (cols * cell_size, rows * cell_size), (15, 15, 15))

    for i, img_bytes in enumerate(images[:cols * rows]):
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img = img.resize((cell_size, cell_size), Image.LANCZOS)
        col = i % cols
        row = i // cols
        canvas.paste(img, (col * cell_size, row * cell_size))

    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()
    draw.text((20, canvas.height - 40), WATERMARK_TEXT, fill=(255, 255, 255), font=font)

    buffer = io.BytesIO()
    canvas.save(buffer, format="JPEG", quality=90)
    buffer.seek(0)
    return buffer.getvalue()


def get_color_name(rgb):
    r, g, b = rgb
    brightness = (r + g + b) / 3
    
    if brightness < 50:
        return "черный", "⚫"
    elif brightness > 200 and abs(r - g) < 30 and abs(g - b) < 30:
        return "белый", "⚪"
    elif abs(r - g) < 30 and abs(g - b) < 30:
        return "серый", "🔘"
    elif r > 150 and g < 100 and b < 100:
        return "красный", "🔴"
    elif r > 200 and g > 100 and g < 150 and b < 100:
        return "оранжевый", "🟠"
    elif r > 200 and g > 200 and b < 100:
        return "желтый", "🟡"
    elif g > 150 and r < 150 and b < 150:
        return "зеленый", "🟢"
    elif b > 150 and r < 100 and g < 150:
        return "синий", "🔵"
    elif r > 100 and b > 100 and g < 100:
        return "фиолетовый", "🟣"
    elif r > 100 and g > 50 and g < 100 and b < 50:
        return "коричневый", "🟤"
    elif r > 200 and g > 150 and b > 150:
        return "розовый", "🌸"
    elif r > 200 and g > 180 and b > 150 and brightness > 180:
        return "бежевый", "🟫"
    else:
        return "цветной", "🎨"


def analyze_colors(images: list) -> dict:
    all_colors = []
    
    for img_bytes in images:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            tmp.write(img_bytes)
            tmp_path = tmp.name
        
        try:
            thief = ColorThief(tmp_path)
            dominant = thief.get_color(quality=1)
            all_colors.append(dominant)
        except Exception as e:
            print(f"Ошибка анализа цвета: {e}")
            all_colors.append((128, 128, 128))
        finally:
            os.unlink(tmp_path)
    
    color_names = []
    color_emojis = []
    for rgb in all_colors:
        name, emoji = get_color_name(rgb)
        color_names.append(name)
        color_emojis.append(emoji)
    
    return {
        "colors": color_names,
        "emojis": color_emojis,
        "count": len(all_colors)
    }


def generate_style_text(n_photos: int, color_data: dict) -> str:
    colors = color_data["colors"]
    emojis = color_data["emojis"]
    
    palette = " ".join(emojis)
    colors_list = ", ".join(set(colors))
    
    unique_colors = list(set(colors))
    
    if len(unique_colors) == 1:
        harmony = f"🎯 Монохром в оттенке «{unique_colors[0]}» — сильное минималистичное решение."
    elif len(unique_colors) == 2:
        if "черный" in unique_colors and "белый" in unique_colors:
            harmony = "⚡ Классический контраст черного и белого — вечная база."
        else:
            harmony = f"🔥 Отличная пара: {unique_colors[0]} + {unique_colors[1]}. Сбалансированный образ."
    elif len(unique_colors) == 3:
        harmony = f"🎨 Тройка цветов ({colors_list}) — есть где развернуться с аксессуарами."
    else:
        harmony = f"🌈 Смелая палитра из {len(unique_colors)} цветов. Главное — не перегрузи акцентами."
    
    if n_photos == 2:
        quantity_tip = "Две вещи работают, когда они контрастируют по фактуре или крою."
    elif n_photos == 3:
        quantity_tip = "Классическая тройка — идеальный баланс для повседневного образа."
    elif n_photos >= 4:
        quantity_tip = "Многослойный образ — следи, чтобы один элемент был акцентным."
    else:
        quantity_tip = ""
    
    return (
        f"🖤 Собрал твой образ из {n_photos} вещей.\n\n"
        f"🎨 Палитра: {palette}\n"
        f"Цвета: {colors_list}\n\n"
        f"{harmony}\n"
        f"{quantity_tip}\n\n"
        f"Хочешь усилить образ? Загляни в новые дропы Greedee World 👇"
    )


def get_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Собрать ещё", callback_data="restart")],
        [InlineKeyboardButton(text="🛍 В магазин Greedee World", url="https://greedee.ru")],
        [InlineKeyboardButton(text="📢 Наш канал", url="https://t.me/greedeeworld")],
    ])


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_photos.pop(message.from_user.id, None)

    text = (
        "🖤 <b>Greedee World AI-стилист</b>\n\n"
        "Загрузи 2–6 фото своих вещей — я соберу из них гармоничный образ и проанализирую цвета.\n\n"
        "Просто кидай фото по одному, когда закончишь — нажми «Готово»."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово, собирай образ", callback_data="finish")]
    ])
    await message.answer(text, reply_markup=kb)
    await state.set_state(CollectingPhotos.waiting_photos)


@dp.message(CollectingPhotos.waiting_photos, F.photo)
async def receive_photo(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    user_photos.setdefault(uid, [])

    if len(user_photos[uid]) >= 6:
        await message.answer("⚠️ Максимум 6 вещей. Нажми «Готово», чтобы собрать образ.")
        return

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    data = await bot.download_file(file.file_path)
    user_photos[uid].append(data.read())

    remaining = 6 - len(user_photos[uid])
    await message.answer(
        f"➕ Добавил ({len(user_photos[uid])}/6). "
        f"Можешь ещё {remaining} или жми «Готово»."
    )


@dp.callback_query(CollectingPhotos.waiting_photos, F.data == "finish")
async def finish_collection(callback: types.CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    photos = user_photos.get(uid, [])

    if len(photos) < 2:
        await callback.answer("Нужно минимум 2 вещи 😎", show_alert=True)
        return

    await callback.message.edit_text("⏳ Собираю твой образ и анализирую цвета...")
    print("📸 Начинаю создание коллажа...")

    collage_bytes = await asyncio.to_thread(create_collage, photos)
    print(f"✅ Коллаж создан, размер: {len(collage_bytes)} байт")

    print("🎨 Анализирую цвета...")
    color_data = await asyncio.to_thread(analyze_colors, photos)
    print(f"✅ Цвета проанализированы: {color_data}")

    style_text = generate_style_text(len(photos), color_data)
    print("✅ Текст сгенерирован")

    print("📤 Отправляю фото...")
    await callback.message.answer_photo(
        BufferedInputFile(collage_bytes, filename="look.jpg"),
        caption=style_text,
        reply_markup=get_result_keyboard()
    )
    print("✅ Фото отправлено!")

    user_photos.pop(uid, None)
    await state.clear()


@dp.callback_query(F.data == "restart")
async def restart(callback: types.CallbackQuery, state: FSMContext):
    await cmd_start(callback.message, state)
    await callback.answer()


async def main():
    print("🖤 Greedee AI Stylist запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
