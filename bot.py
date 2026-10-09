import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
NAME = os.getenv("BOT_NAME", "Abbos")
TZ = ZoneInfo("Asia/Tashkent")
REMIND_BEFORE = 5

TASKS = [
    "O'qishga borish",
    "Ovqatlanish",
    "Dars qilish",
    "Sport qilish",
    "Kitob o'qish",
    "Ingliz tili",
    "Uyni yig'ishtirish",
    "Dasturlash",
    "Dam olish",
    "Uxlash",
]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

if not TOKEN:
    raise RuntimeError("BOT_TOKEN Environment Variable topilmadi.")


def plan_text(times: dict) -> str:
    lines = [f"Assalomu alaykum, {NAME}! Bugungi rejalaringiz:\n"]
    for i, task in enumerate(TASKS):
        t = times.get(i)
        mark = f"⏰ {t}" if t else "—"
        lines.append(f"{i + 1}. {task}  {mark}")
    lines.append("\nRejani bosing va soatni tanlang 👇")
    return "\n".join(lines)


def plan_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"{i + 1}. {task}", callback_data=f"t:{i}")]
        for i, task in enumerate(TASKS)
    ]
    return InlineKeyboardMarkup(rows)


def hours_keyboard(idx: int) -> InlineKeyboardMarkup:
    rows, row = [], []
    for h in range(24):
        row.append(InlineKeyboardButton(f"{h:02d}", callback_data=f"h:{idx}:{h}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back")])
    return InlineKeyboardMarkup(rows)


def minutes_keyboard(idx: int, hour: int) -> InlineKeyboardMarkup:
    rows, row = [], []
    for m in range(0, 60, 5):
        row.append(
            InlineKeyboardButton(
                f"{hour:02d}:{m:02d}",
                callback_data=f"m:{idx}:{hour}:{m}",
            )
        )
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Soatlarga", callback_data=f"t:{idx}")])
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    times = context.chat_data.setdefault("times", {})
    await update.message.reply_text(
        plan_text(times),
        reply_markup=plan_keyboard(),
    )


async def remind(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=(
            f"🔔 Hurmatli {NAME}, siz soat {data['time']} da "
            f"«{data['task']}» ga ketishingiz kerak! "
            f"({REMIND_BEFORE} daqiqa qoldi)"
        ),
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split(":")
    times = context.chat_data.setdefault("times", {})
    chat_id = query.message.chat_id

    if data[0] == "back":
        await query.edit_message_text(
            plan_text(times),
            reply_markup=plan_keyboard(),
        )

    elif data[0] == "t":
        idx = int(data[1])
        await query.edit_message_text(
            f"«{TASKS[idx]}» uchun soatni tanlang (24 soatlik):",
            reply_markup=hours_keyboard(idx),
        )

    elif data[0] == "h":
        idx, hour = int(data[1]), int(data[2])
        await query.edit_message_text(
            f"«{TASKS[idx]}» — daqiqani tanlang:",
            reply_markup=minutes_keyboard(idx, hour),
        )

    elif data[0] == "m":
        idx, hour, minute = map(int, data[1:4])

        now = datetime.now(TZ)
        target = now.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )
        remind_at = target - timedelta(minutes=REMIND_BEFORE)

        if remind_at <= now:
            await query.edit_message_text(
                f"⚠️ {hour:02d}:{minute:02d} ga eslatma qo'yib bo'lmaydi "
                f"(vaqt o'tib ketgan yoki 5 daqiqadan kam qolgan). "
                f"Boshqa vaqt tanlang:",
                reply_markup=hours_keyboard(idx),
            )
            return

        job_name = f"{chat_id}_{idx}"

        for job in context.job_queue.get_jobs_by_name(job_name):
            job.schedule_removal()

        time_str = f"{hour:02d}:{minute:02d}"

        context.job_queue.run_once(
            remind,
            when=remind_at,
            name=job_name,
            data={
                "chat_id": chat_id,
                "task": TASKS[idx],
                "time": time_str,
            },
        )

        times[idx] = time_str

        await query.edit_message_text(
            f"✅ Saqlandi: «{TASKS[idx]}» — {time_str}\n"
            f"Eslatma {remind_at.strftime('%H:%M')} da keladi.\n\n"
            + plan_text(times),
            reply_markup=plan_keyboard(),
        )


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reja", start))
    app.add_handler(CallbackQueryHandler(buttons))

    app.run_polling()


if __name__ == "__main__":
    main()
