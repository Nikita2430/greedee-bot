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

def create_collage(images, max_size=800):
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
        img = img.crop(((w-side)//2, (h-side)//2, (w+side)//2, (h+side)//2))
        img = img.resize((cell_size, cell_size), Image.LANCZOS)
        canvas.paste(img, ((i % cols) * cell_size, (i // cols) * cell_size))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()
    draw.text((20, canvas.height - 40), WATERMARK_TEXT, fill=(255,255,255), font=font)
    buffer = io.BytesIO()
    canvas.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()

def get_color_name(rgb):
    r, g, b = rgb
    brightness = (r + g + b) / 3
    if brightness < 50:
        return "черный", "⚫"
    elif brightness > 200 and abs(r-g) < 30 and abs(g-b) < 30:
        return "белый", "⚪"
    elif abs(r-g) < 30 and abs(g-b) < 30:
        return "серый", "🔘"
    elif r > 150 and g < 100 and b < 100:
        return "красный", ""
    elif g > 150 and r < 150 and b < 150:
        return "зеленый", ""
    elif b > 150 and r < 100 and g < 150:
        return "синий", ""
    else:
        return "цветной", "🎨"

def analyze_colors(images):
    all_colors = []
    for img_bytes in images:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(img_bytes)
            tmp_path = tmp.name
        try:
            all_colors.append(ColorThief(tmp_path).get_color(quality=1))
        except:
            all_colors.append((128, 128, 128))
        finally:
            os.unlink(tmp_path)
    names, emojis = [], []
    for rgb in all_colors:
        n, e = get_color_name(rgb)
        names.append(n)
        emojis.append(e)
    return {"colors": names, "emojis": emojis}

def generate_style_text(n_photos, color_data):
    colors = list(set(color_data["colors"]))
    palette = " ".join(color_data["emojis"])
    colors_str = ", ".join(colors)
    if len(colors) == 1:
        harmony = f"🎯 Монохром в оттенке «{colors[0]}» — сильное минималистичное решение."
    elif len(colors) == 2:
        harmony = f" Отличная пара: {colors[0]} + {colors[1]}. Сбалансированный образ."
    else:
        harmony = f"🌈 Смелая палитра из {len(colors)} цветов."
    if n_photos == 2:
        tip = "Две вещи работают, когда они контрастируют по фактуре."
    elif n_photos >= 4:
        tip = "Многослойный образ — следи за акцентами."
    else:
        tip = "Классическая тройка — идеальный баланс."
    text = f"🖤 Собрал твой образ из {n_photos} вещей.\n\n"
    text += f"🎨 Палитра: {palette}\n"
    text += f"Цвета: {colors_str}\n\n"
    text += f"{harmony}\n"
    text += f"{tip}\n\n"
    text += "Хочешь усилить образ? Загляни в новые дропы Greedee World 👇"
    return text

def get_result_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Собрать ещё", callback_data="restart")],
        [InlineKeyboardButton(text="🛍 В магазин Greedee World", url="https://greedee.ru")],
        [InlineKeyboardButton(text="📢 Наш канал", url="https://t.me/greedeeworld")],
    ])

@dp.message(Command("start"))
async def cmd_start(message, state):
    await state.clear()
    user_photos.pop(message.from_user.id, None)
    text = "🖤 <b>Greedee World AI-стилист</b>\n\nЗагрузи 2–6 фото своих вещей.\n\nКидай фото по одному, когда закончишь — нажми «Готово»."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Готово", callback_data="finish")]])
    await message.answer(text, reply_markup=kb)
    await state.set_state(CollectingPhotos.waiting_photos)

@dp.message(CollectingPhotos.waiting_photos, F.photo)
async def receive_photo(message, state):
    uid = message.from_user.id
    user_photos.setdefault(uid, [])
    if len(user_photos[uid]) >= 6:
        await message.answer("⚠️ Максимум 6 вещей. Жми «Готово».")
        return
    data = await bot.download_file((await bot.get_file(message.photo[-1].file_id)).file_path)
    user_photos[uid].append(data.read())
    await message.answer(f"➕ Добавил ({len(user_photos[uid])}/6). Можешь ещё {6 - len(user_photos[uid])} или жми «Готово».")

@dp.callback_query(CollectingPhotos.waiting_photos, F.data == "finish")
async def finish_collection(callback, state):
    photos = user_photos.get(callback.from_user.id, [])
    if len(photos) < 2:
        await callback.answer("Нужно минимум 2 вещи 😎", show_alert=True)
        return
    await callback.message.edit_text("⏳ Собираю образ и анализирую цвета...")
    collage_bytes = await asyncio.to_thread(create_collage, photos)
    color_data = await asyncio.to_thread(analyze_colors, photos)
    await callback.message.answer_photo(
        BufferedInputFile(collage_bytes, filename="look.jpg"),
        caption=generate_style_text(len(photos), color_data),
        reply_markup=get_result_keyboard()
    )
    user_photos.pop(callback.from_user.id, None)
    await state.clear()

@dp.callback_query(F.data == "restart")
async def restart(callback, state):
    await cmd_start(callback.message, state)
    await callback.answer()

if __name__ == "__main__":
    print(" Greedee AI Stylist запущен...")
    asyncio.run(dp.start_polling(bot))
