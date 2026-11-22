# ============================
# Movie Update Channel Commands
# ============================

def is_update_admin(message):
    return (
        message.from_user is not None
        and message.from_user.id in ADMINS
    )


async def _parse_channel_id(client, raw_target: str):
    raw_target = raw_target.strip()

    if raw_target.startswith(("https://t.me/", "http://t.me/", "t.me/")):
        slug = raw_target.rstrip("/").split("/")[-1]
        if slug.startswith("+"):
            raise ValueError("Invite links are not supported. Use channel ID or @username.")
        raw_target = slug

    try:
        return int(raw_target)
    except ValueError:
        chat = await client.get_chat(raw_target)
        return chat.id


@Client.on_message(filters.command("add_update_channel"))
async def add_update_channel_cmd(client, message):
    if not is_update_admin(message):
        return await message.reply_text("❌ You are not authorized to use this command.")

    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: /add_update_channel <channel_id or @username>"
        )

    try:
        ch_id = await _parse_channel_id(client, message.command[1])
        chat = await client.get_chat(ch_id)

        if chat.type != enums.ChatType.CHANNEL:
            return await message.reply_text("❌ Target must be a Telegram channel.")

        me = await client.get_me()
        member = await client.get_chat_member(chat.id, me.id)

        if member.status not in (
            enums.ChatMemberStatus.ADMINISTRATOR,
            enums.ChatMemberStatus.OWNER
        ):
            return await message.reply_text(
                "❌ Please make the bot an administrator in that channel."
            )

        if member.privileges and not member.privileges.can_post_messages:
            return await message.reply_text(
                "❌ The bot needs permission to post messages."
            )

        added = await db.add_update_channel(
            chat.id, chat.title or str(chat.id)
        )

        if not added:
            return await message.reply_text(
                f"ℹ️ Channel already configured: {chat.title} ({chat.id})"
            )

        await message.reply_text(
            f"✅ Movie Update Channel Added!\n\n"
            f"Title: {chat.title}\n"
            f"ID: <code>{chat.id}</code>\n"
            f"Verification: OFF"
        )

    except Exception as e:
        logger.exception("add_update_channel failed")
        await message.reply_text(f"❌ Error: <code>{e}</code>")


@Client.on_message(filters.command("list_update_channels"))
async def list_update_channels_cmd(client, message):
    if not is_update_admin(message):
        return await message.reply_text("❌ You are not authorized.")

    try:
        channels = await db.get_all_update_channels()

        if not channels:
            return await message.reply_text("ℹ️ No update channels configured.")

        lines = ["📢 Configured Movie Update Channels:\n"]

        for index, ch in enumerate(channels, 1):
            lines.append(
                f"{index}. {ch.get('title', 'Unknown')}\n"
                f"ID: <code>{ch['channel_id']}</code>\n"
                f"Verification: {'ON' if ch.get('is_verify') else 'OFF'}\n"
            )

        await message.reply_text("\n".join(lines))

    except Exception as e:
        logger.exception("list_update_channels failed")
        await message.reply_text(f"❌ Error: <code>{e}</code>")


async def _toggle_channel_verify(client, message, enable):
    if len(message.command) < 2:
        return await message.reply_text(
            f"Usage: /{message.command[0]} <channel_id>"
        )

    try:
        ch_id = await _parse_channel_id(client, message.command[1])
        channel = await db.get_update_channel(ch_id)

        if not channel:
            return await message.reply_text(
                f"❌ Channel <code>{ch_id}</code> is not configured."
            )

        await db.update_channel_setting(ch_id, "is_verify", enable)

        status = "enabled ✅" if enable else "disabled ❌"

        await message.reply_text(
            f"✅ Channel verification {status}\n"
            f"Title: {channel.get('title', ch_id)}\n"
            f"ID: <code>{ch_id}</code>"
        )

    except Exception as e:
        logger.exception("Channel verification update failed")
        await message.reply_text(f"❌ Error: <code>{e}</code>")


@Client.on_message(filters.command("channel_verify_on"))
async def channel_verify_on_cmd(client, message):
    if not is_update_admin(message):
        return await message.reply_text("❌ You are not authorized.")

    await _toggle_channel_verify(client, message, True)


@Client.on_message(filters.command("channel_verify_off"))
async def channel_verify_off_cmd(client, message):
    if not is_update_admin(message):
        return await message.reply_text("❌ You are not authorized.")

    await _toggle_channel_verify(client, message, False)
