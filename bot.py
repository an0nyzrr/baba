# spidtok-server/bot.py
# author: Найзер (spidos team)
"""The admin side of badges: resolve a @tiktok name to an id and grant
whatever badge it should carry, and the donation queue -- a user asks, an
admin says yes or no, and a yes becomes a checkmark with no manual sqlite
work involved.

Everything that changes a badge goes through here. The http server in
api.py only ever reads.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
import db
import tiktok

log = logging.getLogger("spidtok.bot")
router = Router()

KNOWN_BADGES = ", ".join(sorted(db.BADGE_DEFAULTS))


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


async def resolve_or_reply(message: Message, username: str) -> tiktok.Profile | None:
    profile = await asyncio.to_thread(tiktok.resolve, username)
    if profile is None:
        await message.reply(
            f"не нашёл @{username} на TikTok — проверь ник и попробуй ещё раз."
        )
    return profile


# --------------------------------------------------------------- everyone

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        f"<b>{config.APP_NAME}</b>\n"
        f"Мод на TikTok — разработка {config.TEAM_NAME}, кодер {config.CODER_NAME}.\n\n"
        f"Канал: {config.CHANNEL}\n\n"
        f"💳 <b>Донат на галочку:</b>\n"
        f"https://dalink.to/nyzer\n\n"
        f"В комментарии к донату обязательно укажи свой Telegram-юзернейм (@ник), "
        f"чтобы я нашёл заявку.\n\n"
        f"После доната напиши /donate ваш_tiktok_ник — галочка выдаётся после подтверждения.",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("donate"))
async def cmd_donate(message: Message, command: CommandObject) -> None:
    tt_username = (command.args or "").strip().lstrip("@")
    if not tiktok.is_valid_username(tt_username):
        await message.reply(
            "формат: <code>/donate ваш_tiktok_ник</code>", parse_mode=ParseMode.HTML
        )
        return

    profile = await resolve_or_reply(message, tt_username)
    if profile is None:
        return

    donation_id = db.queue_donation(
        tg_user_id=message.from_user.id,
        tg_username=message.from_user.username,
        tt_username=profile.username,
        tt_uid=profile.uid,
    )
    await message.reply(
        "заявка принята, жди подтверждения. Как донат согласуют — "
        "галочка появится на твоём аккаунте сама."
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ одобрить", callback_data=f"don:{donation_id}:yes"),
            InlineKeyboardButton(text="❌ отклонить", callback_data=f"don:{donation_id}:no"),
        ]]
    )
    admin_text = (
        f"донат-заявка #{donation_id}\n"
        f"от: @{message.from_user.username or message.from_user.id}\n"
        f"tiktok: @{profile.username} (id {profile.uid}, {profile.nickname})"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, admin_text, reply_markup=kb)
        except Exception as exc:  # noqa: BLE001 - one unreachable admin shouldn't break the rest
            log.warning("couldn't reach admin %s: %s", admin_id, exc)


# ----------------------------------------------------------------- admins

@router.callback_query(F.data.startswith("don:"))
async def on_donation_decision(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("не твоё дело", show_alert=True)
        return

    _, donation_id_s, decision = callback.data.split(":")
    donation_id = int(donation_id_s)
    donation = db.get_donation(donation_id)
    if donation is None:
        await callback.answer("заявка не найдена", show_alert=True)
        return
    if donation["status"] != "pending":
        await callback.answer("уже решено", show_alert=True)
        return

    approved = decision == "yes"
    db.decide_donation(donation_id, approved, callback.from_user.id)

    if approved:
        db.grant_badge(donation["tt_uid"], config.BADGE_CHECKMARK, callback.from_user.id)
        verdict = "одобрено, галочка выдана"
    else:
        verdict = "отклонено"

    await callback.message.edit_text(callback.message.text + f"\n\n→ {verdict}")
    await callback.answer()

    try:
        await callback.bot.send_message(
            donation["tg_user_id"],
            "✅ донат одобрен, галочка уже на аккаунте." if approved
            else "❌ донат отклонён. Если это ошибка — напиши ещё раз.",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("couldn't notify donor %s: %s", donation["tg_user_id"], exc)


@router.message(Command("grant"))
async def cmd_grant(message: Message, command: CommandObject) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = (command.args or "").split()
    if len(parts) != 2:
        await message.reply(
            f"формат: <code>/grant tiktok_ник бейдж</code>\n"
            f"бейджи: {KNOWN_BADGES}",
            parse_mode=ParseMode.HTML,
        )
        return
    tt_username, badge_id = parts[0].lstrip("@"), parts[1]

    profile = await resolve_or_reply(message, tt_username)
    if profile is None:
        return

    db.grant_badge(profile.uid, badge_id, message.from_user.id)
    await message.reply(
        f"выдал «{badge_id}» → @{profile.username} ({profile.nickname}, id {profile.uid})"
    )


@router.message(Command("revoke"))
async def cmd_revoke(message: Message, command: CommandObject) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = (command.args or "").split()
    if len(parts) != 2:
        await message.reply("формат: <code>/revoke tiktok_ник бейдж</code>", parse_mode=ParseMode.HTML)
        return
    tt_username, badge_id = parts[0].lstrip("@"), parts[1]

    profile = await resolve_or_reply(message, tt_username)
    if profile is None:
        return

    removed = db.revoke_badge(profile.uid, badge_id)
    await message.reply("снял." if removed else "такого бейджа у него и не было.")


@router.message(Command("badges"))
async def cmd_badges(message: Message, command: CommandObject) -> None:
    if not is_admin(message.from_user.id):
        return
    tt_username = (command.args or "").strip().lstrip("@")
    profile = await resolve_or_reply(message, tt_username)
    if profile is None:
        return
    rows = db.badges_for(profile.uid)
    if not rows:
        await message.reply(f"у @{profile.username} бейджей нет.")
        return
    listed = "\n".join(f"• {r['badge_id']}" for r in rows)
    await message.reply(f"@{profile.username} ({profile.uid}):\n{listed}")


@router.message(Command("pending"))
async def cmd_pending(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    rows = db.pending_donations()
    if not rows:
        await message.reply("очередь пуста.")
        return
    listed = "\n".join(
        f"#{r['id']} @{r['tt_username']} от @{r['tg_username'] or r['tg_user_id']}"
        for r in rows
    )
    await message.reply(listed)


async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    db.init()
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    log.info("spidtok bot starting, %d admin(s) configured", len(config.ADMIN_IDS))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
