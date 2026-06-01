#!/usr/bin/env python3
import asyncio, random, time, re, json, logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from urllib.parse import parse_qs
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes)
from telegram.error import TelegramError
from config import BOT_TOKEN, ADMIN_IDS
from database import Database

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
db = Database()

I = {
    "coin":"🪙","money":"💰","fire":"🔥","rocket":"🚀","crown":"👑","star":"⭐","trophy":"🏆",
    "chart":"📊","link":"🔗","gear":"⚙️","lock":"🔐","check":"✅","cross":"❌","warning":"⚠️",
    "info":"ℹ️","user":"👤","users":"👥","ban":"⛔","plus":"➕","minus":"➖","set":"🎯",
    "broadcast":"📢","stats":"📊","history":"📋","search":"🔍","lightning":"⚡","target":"🎯",
    "channel":"📺","bot":"🤖","globe":"🌍","calendar":"📅","clock":"🕐","refresh":"🔄",
    "back":"🔙","home":"🏠","welcome":"👋","wave":"🖐️","point":"👉","settings":"⚙️",
    "unlock":"🔓","send":"📤","speaker":"🔊","tada":"🎉"
}

def btn(text, cb, icon=None):
    return InlineKeyboardButton(f"{icon} {text}" if icon else text, callback_data=cb)

def menu_btn(t, c, i=None): return btn(t, c, i)
def back_btn(c="menu_main"): return btn("🔙 Back", c)

def build_menu(buttons, cols=2, header=None, footer=None):
    m = []
    if header: m.append(header) if not isinstance(header[0], list) else m.extend(header)
    row = []
    for i, b in enumerate(buttons):
        row.append(b)
        if (i+1)%cols==0: m.append(row); row=[]
    if row: m.append(row)
    if footer: m.append(footer) if not isinstance(footer[0], list) else m.extend(footer)
    return InlineKeyboardMarkup(m)

admin_ctx = {}

# ── MAIN MENU ──
async def main_menu(uq, uid, text=None):
    ud = db.get_user(uid)
    c = ud["coins"]; r = ud["referrals_done"]
    h = f"{I['coin']} **{c:.2f}** coins  •  {I['chart']} **{r}** referrals\n{I['bot']} Referral Bot"
    t = text or (
        f"╔══════════════════════════════╗\n║   {I['rocket']} WELCOME {I['rocket']}   ║\n╚══════════════════════════════╝\n\n"
        f"{I['wave']} Hey! Send me any referral link & I'll make\nreal-looking referrals for you!\n\n"
        f"{I['coin']} Balance: **{c:.2f}** coins\n{I['chart']} Referrals: **{r}**\n\n👇 **Choose an option:**"
    )
    kb = build_menu([
        menu_btn("🚀 New Referral", "menu_ref", "🎯"),
        menu_btn("💰 My Wallet", "menu_wallet", "💳"),
        menu_btn("📊 My Stats", "menu_stats", "📈"),
        menu_btn("❓ Help", "menu_help", "ℹ️"),
    ], cols=2)
    if isinstance(uq, Update):
        await uq.message.reply_text(f"{h}\n\n{t}", reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else:
        await uq.edit_message_text(f"{h}\n\n{t}", reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

# ── FORCE JOIN ──
async def check_fj(update, ctx):
    uid = update.effective_user.id
    if uid in ADMIN_IDS: return True
    if db.is_banned(uid):
        await update.message.reply_text(f"{I['ban']} **Banned.** Contact admin.", parse_mode=ParseMode.MARKDOWN)
        return False
    chs = db.get_force_channels()
    if not chs: return True
    nj = []
    for ch in chs:
        try:
            m = await ctx.bot.get_chat_member(chat_id=f"@{ch['channel_username'].replace('@','')}", user_id=uid)
            if m.status in ("left","kicked"): nj.append(ch)
        except: nj.append(ch)
    if nj:
        btns = []
        for ch in nj:
            u = ch["channel_username"].replace("@","")
            btns.append([InlineKeyboardButton(f"📺 Join {ch['channel_title'] or u}", url=f"https://t.me/{u}")])
        btns.append([InlineKeyboardButton(f"{I['refresh']} Check Again", callback_data="fj_check")])
        await update.message.reply_text(
            f"╔══════════════════════════════╗\n║  {I['channel']} JOIN REQUIRED {I['channel']}    ║\n╚══════════════════════════════╝\n\n"
            f"{I['warning']} Join **ALL** channels then click verify:",
            reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)
        return False
    return True

# ── START ──
async def start_cmd(upd, ctx):
    u = upd.effective_user
    db.get_or_create_user(u.id, u.username, u.first_name, u.last_name)
    if not await check_fj(upd, ctx): return
    await main_menu(upd, u.id)

# ── HELP ──
async def help_cmd(upd, ctx):
    u = upd.effective_user
    db.get_or_create_user(u.id, u.username, u.first_name, u.last_name)
    if not await check_fj(upd, ctx): return
    cpr = db.get_setting("coins_per_referral", 10)
    mx = db.get_setting("max_referrals_per_day", 5)
    pr = db.get_setting("price_per_coin", 1.0)
    t = (f"╔══════════════════════════════╗\n║    {I['info']} HELP {I['info']}     ║\n╚══════════════════════════════╝\n\n"
         f"{I['rocket']} **How It Works**\n➊ Get a referral link (t.me/Bot?start=CODE)\n➋ Send it here\n➌ We auto-detect requirements\n➍ We create REAL-LOOKING referrals\n➎ You earn {I['coin']}**{cpr} coins** each!\n\n"
         f"{I['settings']} **Settings:**\n{I['coin']} Per referral: **{cpr}** coins\n{I['money']} Per coin: **${pr}**\n{I['chart']} Max/day: **{mx}**\n\n"
         f"📌 **Commands:**\n/start - Menu\n/refer <link> - Process referral\n/balance - Coins\n/stats - Your stats\n/help - This")
    kb = build_menu([menu_btn("🚀 New Referral", "menu_ref", "🎯"), menu_btn("🏠 Main Menu", "menu_main", "🏠")], cols=2)
    await upd.message.reply_text(t, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

# ── REFER ──
async def refer_cmd(upd, ctx):
    u = upd.effective_user
    db.get_or_create_user(u.id, u.username, u.first_name, u.last_name)
    if not await check_fj(upd, ctx): return
    if not ctx.args:
        t = (f"╔══════════════════════════════╗\n║   {I['link']} SEND LINK {I['link']}   ║\n╚══════════════════════════════╝\n\n"
             f"{I['point']} Paste your referral link!\n\n`https://t.me/BotName?start=CODE`\n\n{I['warning']} Must contain `?start=`")
        kb = build_menu([menu_btn("📤 Send Link", "menu_ref", "🔗"), back_btn("menu_main")], cols=2)
        await upd.message.reply_text(t, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        return
    link = " ".join(ctx.args)
    bot, code = None, None
    if "t.me/" in link:
        path = link.split("t.me/",1)[1]
        if "?" in path:
            bp, q = path.split("?",1)
            p = parse_qs(q)
            code = p.get("start",[None])[0] or p.get("startapp",[None])[0] or p.get("ref",[None])[0]
            bot = bp.split("?")[0].split("/")[0]
    if not bot or not code:
        t = f"{I['cross']} **Invalid link!**\nUse: `https://t.me/BotName?start=CODE`"
        kb = build_menu([menu_btn("📤 Try Again", "menu_ref", "🔗"), back_btn("menu_main")], cols=2)
        await upd.message.reply_text(t, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        return
    today = db.get_user_today_referrals(u.id)
    mx = db.get_setting("max_referrals_per_day", 5)
    if today >= mx:
        t = (f"╔══════════════════════════════╗\n║  {I['warning']} LIMIT REACHED {I['warning']}   ║\n╚══════════════════════════════╝\n\n"
             f"{I['cross']} **{today}/{mx}** used today!\n{I['clock']} Come back tomorrow.\n{I['coin']} Balance: **{db.get_user(u.id)['coins']:.2f}** coins")
        kb = build_menu([menu_btn("💰 My Wallet", "menu_wallet", "💳"), back_btn("menu_main")], cols=2)
        await upd.message.reply_text(t, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        return
    rem = mx - today
    opts = [c for c in [1,3,5] if c <= rem]
    if rem not in opts and rem>0: opts.append(rem)
    btns = [menu_btn(f"{c}x", f"ref_{c}_{bot}_{code}", "🎯") for c in opts]
    btns.append(menu_btn("✏️ Custom", f"ref_custom_{bot}_{code}", "✏️"))
    kb = build_menu(btns, cols=len(btns), footer=[back_btn("menu_main")])
    t = (f"╔══════════════════════════════╗\n║  {I['target']} REFERRAL SETUP {I['target']}    ║\n╚══════════════════════════════╝\n\n"
         f"{I['bot']} **Bot:** `@{bot}`\n{I['link']} **Code:** `{code}`\n{I['chart']} **Today:** {today}/{mx}\n{I['coin']} **Each:** +{db.get_setting('coins_per_referral',10)} coins\n\nHow many?")
    await upd.message.reply_text(t, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

# ── WALLET ──
async def balance_cmd(upd, ctx):
    u = upd.effective_user
    db.get_or_create_user(u.id, u.username, u.first_name, u.last_name)
    if not await check_fj(upd, ctx): return
    await show_wallet(upd, u.id)

async def show_wallet(uq, uid):
    ud = db.get_user(uid)
    pr = db.get_setting("price_per_coin", 1.0)
    t = (f"╔══════════════════════════════╗\n║   {I['money']} YOUR WALLET {I['money']}    ║\n╚══════════════════════════════╝\n\n"
         f"{I['coin']} **Balance:** `{ud['coins']:.2f}` coins\n{I['money']} **Value:** `${ud['coins']*pr:.2f}`\n"
         f"{I['chart']} **Total earned:** `{ud['total_coins_earned']:.2f}`\n{I['chart']} **Referrals:** {ud['referrals_done']}\n\n"
         f"{I['lightning']} Send a link to earn more!")
    kb = build_menu([menu_btn("🚀 New Referral", "menu_ref", "🎯"), menu_btn("📊 Stats", "menu_stats", "📈"), back_btn("menu_main")], cols=2)
    if isinstance(uq, Update): await uq.message.reply_text(t, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else: await uq.edit_message_text(t, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

# ── STATS ──
async def stats_cmd(upd, ctx):
    u = upd.effective_user
    db.get_or_create_user(u.id, u.username, u.first_name, u.last_name)
    if not await check_fj(upd, ctx): return
    await show_stats(upd, u.id)

async def show_stats(uq, uid):
    ud = db.get_user(uid)
    logs = db.get_user_referral_logs(uid, 10)
    t = (f"╔══════════════════════════════╗\n║   {I['stats']} YOUR STATS {I['stats']}    ║\n╚══════════════════════════════╝\n\n"
         f"{I['user']} **ID:** `{uid}`\n{I['user']} **@**{ud.get('username') or 'N/A'}\n{I['calendar']} **Joined:** {ud['joined_at'][:10]}\n"
         f"{I['coin']} **Coins:** {ud['coins']:.2f}\n{I['chart']} **Referrals:** {ud['referrals_done']} total | {ud['referrals_today']} today\n{I['link']} **Links shared:** {ud['total_links_shared']}")
    if logs:
        t += f"\n\n{I['history']} **Recent:**\n"
        for l in logs[-5:]:
            s = f"{I['check']}" if l['status']=='completed' else f"{I['clock']}"
            t += f"{s} `@{l['bot_username']}` +{l['coins_earned']} coins\n"
    kb = build_menu([menu_btn("💰 Wallet", "menu_wallet", "💳"), menu_btn("🚀 Refer", "menu_ref", "🎯"), back_btn("menu_main")], cols=2)
    if isinstance(uq, Update): await uq.message.reply_text(t, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else: await uq.edit_message_text(t, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

# ── CALLBACKS ──
async def cb_handler(upd, ctx):
    q = upd.callback_query
    await q.answer()
    u = upd.effective_user
    d = q.data
    if d == "fj_check":
        chs = db.get_force_channels()
        nj = []
        for ch in chs:
            try:
                m = await ctx.bot.get_chat_member(chat_id=f"@{ch['channel_username'].replace('@','')}", user_id=u.id)
                if m.status in ("left","kicked"): nj.append(ch)
            except: nj.append(ch)
        if nj:
            btns = []
            for ch in nj:
                un = ch["channel_username"].replace("@","")
                btns.append([InlineKeyboardButton(f"📺 Join {ch['channel_title'] or un}", url=f"https://t.me/{un}")])
            btns.append([InlineKeyboardButton(f"{I['refresh']} Check Again", callback_data="fj_check")])
            await q.edit_message_text(f"{I['cross']} Still missing channels!", reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)
        else:
            kb = InlineKeyboardMarkup([[menu_btn(f"{I['rocket']} Start Using Bot", "menu_main", "🚀")]])
            await q.edit_message_text(f"{I['check']} **All joined! You're good to go!**", reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        return
    if d == "menu_main": await main_menu(q, u.id); return
    if d == "menu_wallet": await show_wallet(q, u.id); return
    if d == "menu_stats": await show_stats(q, u.id); return
    if d == "menu_help":
        cpr = db.get_setting("coins_per_referral",10)
        mx = db.get_setting("max_referrals_per_day",5)
        pr = db.get_setting("price_per_coin",1.0)
        t = (f"╔══════════════════════════════╗\n║   {I['info']} HELP {I['info']}     ║\n╚══════════════════════════════╝\n\n"
             f"{I['rocket']} **How It Works**\n➊ Get a referral link\n➋ Send it here\n➌ We auto-detect requirements\n➍ We create REAL-LOOKING referrals\n➎ You earn coins!\n\n"
             f"{I['coin']} Per referral: **{cpr}** coins\n{I['money']} Per coin: **${pr}**\n{I['chart']} Max/day: **{mx}**")
        kb = build_menu([menu_btn("🚀 New Referral", "menu_ref", "🎯"), back_btn("menu_main")], cols=2)
        await q.edit_message_text(t, reply_markup=kb, parse_mode=ParseMode.MARKDOWN); return
    if d == "menu_ref":
        t = (f"╔══════════════════════════════╗\n║   {I['link']} SEND YOUR LINK {I['link']}     ║\n╚══════════════════════════════╝\n\n"
             f"{I['point']} Paste your referral link here:\n\n`https://t.me/BotName?start=CODE`")
        kb = build_menu([back_btn("menu_main")], cols=1)
        await q.edit_message_text(t, reply_markup=kb, parse_mode=ParseMode.MARKDOWN); return
    if d.startswith("ref_"):
        parts = d.split("_", 3)
        if len(parts) >= 4:
            cnt, bot, code = parts[1], parts[2], parts[3]
            if cnt == "custom":
                admin_ctx[u.id] = {"step":"cnt", "bot":bot, "code":code}
                await q.edit_message_text(f"✏️ Send number (1-{db.get_setting('max_referrals_per_day',5)}):", parse_mode=ParseMode.MARKDOWN)
            else:
                await do_ref(q, u.id, bot, code, int(cnt))
        return
    if d.startswith("admin_"):
        await admin_cb(q, ctx, u)

async def do_ref(q, uid, bot, code, cnt):
    cpr = db.get_setting("coins_per_referral",10)
    total = cpr * cnt
    lid = db.log_referral_link(uid, bot, code, f"https://t.me/{bot}?start={code}")
    for i in range(cnt):
        bars = ["⬜⬜⬜⬜⬜","🟨🟨⬜⬜⬜","🟩🟩🟩⬜⬜","🟩🟩🟩🟩🟩"]
        b = bars[min(i, len(bars)-1)]
        s = (
            f"╔══════════════════════════════╗\n║  {I['rocket']} PROCESSING {I['rocket']}  ║\n╚══════════════════════════════╝\n\n"
            f"{I['bot']} **@{bot}**\n{I['target']} `{i}/{cnt}`\n\n`{b}`\n\n"
            f"{I['clock']} **Referral {i+1}...**")
        if i == 0: s += f"\n   {I['channel']} Joining channels..."
        elif i == 1: s += f"\n   {I['check']} Solving captcha..."
        elif i == 2: s += f"\n   {I['user']} Setting up profile..."
        else: s += f"\n   {I['lightning']} Completing..."
        await q.edit_message_text(s, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(random.uniform(4,8))
        if i < cnt-1: await asyncio.sleep(random.uniform(6,12))
    db.add_coins(uid, total)
    db.complete_referral(lid, total)
    nb = db.get_user(uid)['coins']
    t = (f"╔══════════════════════════════╗\n║  {I['check']} COMPLETE! {I['check']}    ║\n╚══════════════════════════════╝\n\n"
         f"{I['bot']} **@{bot}**\n{I['target']} **{cnt}/{cnt} done**\n\n{I['coin']} **+{total} coins earned!**\n{I['money']} **Balance:** `{nb:.2f}` coins\n\n"
         f"{I['info']} Each used unique account with:\n{I['check']} AI photo & bio\n{I['check']} Channels joined\n{I['check']} Aged profile")
    kb = build_menu([menu_btn("🚀 Another", "menu_ref", "🎯"), menu_btn("💰 Wallet", "menu_wallet", "💳"), back_btn("menu_main")], cols=2)
    await q.edit_message_text(t, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
# ── ADMIN PANEL ──
async def admin_cmd(upd, ctx):
    u = upd.effective_user
    if u.id not in ADMIN_IDS:
        await upd.message.reply_text(f"{I['ban']} **Access Denied**", parse_mode=ParseMode.MARKDOWN)
        return
    await admin_menu(upd, u.id)

async def admin_menu(uq, uid):
    s = db.get_user_stats()
    t = (f"╔══════════════════════════════╗\n║  {I['lock']} ADMIN PANEL {I['lock']}      ║\n╚══════════════════════════════╝\n\n"
         f"{I['crown']} Welcome Admin!\n{I['users']} Users: **{s['total_users']}**\n{I['chart']} Referrals: **{s['total_referrals']}**\n{I['coin']} Coins Issued: **{s['total_coins']:.2f}**\n\n👇 **Select:**")
    btns = [
        [menu_btn("👥 Users", "admin_users","👥"), menu_btn("💰 Coins", "admin_coins","💰")],
        [menu_btn("⚙️ Settings", "admin_settings","⚙️"), menu_btn("📊 Stats", "admin_bstats","📊")],
        [menu_btn("📢 Broadcast", "admin_bcast","📢"), menu_btn("🔗 Channels", "admin_channels","🔗")],
        [menu_btn("📋 Logs", "admin_logs","📋")],
    ]
    kb = InlineKeyboardMarkup(btns)
    if isinstance(uq, Update): await uq.message.reply_text(t, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else: await uq.edit_message_text(t, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

async def admin_cb(q, ctx, u):
    d = q.data
    if d == "admin_users":
        btns = [[menu_btn("📋 List All Users", "admin_ulist","📋")],
                [menu_btn("⛔ Ban", "admin_ban","⛔"), menu_btn("✅ Unban", "admin_unban","✅")],
                [back_btn("admin_back")]]
        await q.edit_message_text("👥 **User Management**", reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_ulist":
        us = db.get_all_users()
        if not us: await q.edit_message_text("No users.")
        else:
            t = f"╔═══ USERS ({len(us)}) ═══╗\n\n"
            for u2 in us[:15]:
                bi = f"{I['ban']}" if u2["banned"] else f"{I['check']}"
                nm = u2["username"] or u2["first_name"] or "N/A"
                t += f"{bi} `{u2['user_id']}` @{nm}\n   {I['coin']}{u2['coins']:.1f} | {I['chart']}{u2['referrals_done']} refs | {u2['joined_at'][:10]}\n\n"
            if len(us)>15: t += f"...+{len(us)-15} more\n"
            await q.edit_message_text(t, parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_ban":
        admin_ctx[u.id] = {"step":"ban"}
        await q.edit_message_text(f"{I['ban']} Enter User ID to ban:", parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_unban":
        admin_ctx[u.id] = {"step":"unban"}
        await q.edit_message_text(f"{I['unlock']} Enter User ID to unban:", parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_coins":
        btns = [[menu_btn("➕ Add", "admin_add","➕"), menu_btn("➖ Remove", "admin_rem","➖")],
                [menu_btn("🎯 Set", "admin_set","🎯")], [back_btn("admin_back")]]
        await q.edit_message_text("💰 **Coin Management**", reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_add":
        admin_ctx[u.id] = {"step":"add_uid"}
        await q.edit_message_text("➕ Enter User ID to add coins to:", parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_rem":
        admin_ctx[u.id] = {"step":"rem_uid"}
        await q.edit_message_text("➖ Enter User ID to remove coins from:", parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_set":
        admin_ctx[u.id] = {"step":"set_uid"}
        await q.edit_message_text("🎯 Enter User ID to set coins for:", parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_settings":
        cpr = db.get_setting("coins_per_referral",10)
        pr = db.get_setting("price_per_coin",1.0)
        mn = db.get_setting("min_referrals_per_day",1)
        mx = db.get_setting("max_referrals_per_day",5)
        t = (f"╔═══ SETTINGS ═══╗\n\n{I['money']} Price/Coin: **${pr}**\n{I['coin']} Coins/Ref: **{cpr}**\n{I['chart']} Min/Day: **{mn}**\n{I['chart']} Max/Day: **{mx}**\n\nClick to change:")
        btns = [
            [menu_btn(f"💵 ${pr}", "admin_sprice","💵"), menu_btn(f"🎯 {cpr}", "admin_scoin","🎯")],
            [menu_btn(f"📉 {mn}", "admin_smin","📉"), menu_btn(f"📈 {mx}", "admin_smax","📈")],
            [back_btn("admin_back")]]
        await q.edit_message_text(t, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_sprice":
        admin_ctx[u.id] = {"step":"price"}
        await q.edit_message_text(f"💵 Current: **${db.get_setting('price_per_coin',1.0)}**\nEnter new price:", parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_scoin":
        admin_ctx[u.id] = {"step":"coinref"}
        await q.edit_message_text(f"🎯 Current: **{db.get_setting('coins_per_referral',10)}**\nEnter new coins per referral:", parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_smin":
        admin_ctx[u.id] = {"step":"minref"}
        await q.edit_message_text(f"📉 Current: **{db.get_setting('min_referrals_per_day',1)}**\nEnter new min:", parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_smax":
        admin_ctx[u.id] = {"step":"maxref"}
        await q.edit_message_text(f"📈 Current: **{db.get_setting('max_referrals_per_day',5)}**\nEnter new max:", parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_bstats":
        s = db.get_user_stats()
        us = db.get_all_users()
        su = sorted(us, key=lambda x: x["referrals_done"], reverse=True)[:5]
        t = (f"╔═══ STATISTICS ═══╗\n\n{I['users']} Users: **{s['total_users']}**\n{I['chart']} Referrals: **{s['total_referrals']}**\n{I['coin']} Coins: **{s['total_coins']:.2f}**\n\n{I['trophy']} **Top 5:**\n")
        for i, u2 in enumerate(su, 1):
            m = ["🥇","🥈","🥉","4️⃣","5️⃣"]
            nm = u2["username"] or u2["first_name"] or f"ID {u2['user_id']}"
            t += f"{m[i-1]} **{nm}** — {u2['referrals_done']} refs\n"
        await q.edit_message_text(t, reply_markup=InlineKeyboardMarkup([[back_btn("admin_back")]]), parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_bcast":
        admin_ctx[u.id] = {"step":"bcast"}
        await q.edit_message_text(f"{I['broadcast']} **Send broadcast to ALL users:**\n\nEnter your message (supports Markdown):", parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_channels":
        chs = db.get_force_channels()
        t = f"╔═══ FORCE JOIN CHANNELS ═══╗\n\n"
        if chs:
            for ch in chs: t += f"{I['channel']} `{ch['channel_username']}`\n"
        else: t += "No channels set.\n"
        t += "\nUsers must join to use bot."
        btns = [[menu_btn("➕ Add", "admin_chadd","➕"), menu_btn("➖ Remove", "admin_chrem","➖")],[back_btn("admin_back")]]
        await q.edit_message_text(t, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_chadd":
        admin_ctx[u.id] = {"step":"chadd"}
        await q.edit_message_text("➕ Send channel username:\nExample: `@my_channel`", parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_chrem":
        admin_ctx[u.id] = {"step":"chrem"}
        await q.edit_message_text("➖ Send channel username to remove:\nExample: `@my_channel`", parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_logs":
        logs = db.get_all_referral_logs(15)
        if not logs:
            await q.edit_message_text("No logs yet.", reply_markup=InlineKeyboardMarkup([[back_btn("admin_back")]]))
            return
        t = f"╔═══ REFERRAL LOGS ═══╗\n\n"
        for l in logs[:10]:
            ud = db.get_user(l["user_id"])
            nm = ud["username"] or ud["first_name"] or f"ID {l['user_id']}"
            s = f"{I['check']}" if l["status"]=="completed" else f"{I['clock']}"
            t += f"{s} @{nm} → @{l['bot_username']} +{l['coins_earned']}c\n"
        await q.edit_message_text(t, reply_markup=InlineKeyboardMarkup([[back_btn("admin_back")]]), parse_mode=ParseMode.MARKDOWN)
    elif d == "admin_back":
        await admin_menu(q, u.id)

# ── ADMIN TEXT HANDLER ──
async def handle_admin_text(upd, ctx, u, s):
    txt = upd.message.text
    if s == "ban":
        try:
            db.ban_user(int(txt))
            del admin_ctx[u.id]
            await upd.message.reply_text(f"{I['ban']} Banned `{txt}`", parse_mode=ParseMode.MARKDOWN)
        except: await upd.message.reply_text("❌ Invalid ID")
    elif s == "unban":
        try:
            db.unban_user(int(txt))
            del admin_ctx[u.id]
            await upd.message.reply_text(f"{I['unlock']} Unbanned `{txt}`", parse_mode=ParseMode.MARKDOWN)
        except: await upd.message.reply_text("❌ Invalid ID")
    elif s == "add_uid":
        try:
            admin_ctx[u.id] = {"step":"add_amt", "tid":int(txt)}
            await upd.message.reply_text(f"✏️ Amount to add to `{txt}`:", parse_mode=ParseMode.MARKDOWN)
        except: await upd.message.reply_text("❌ Invalid ID")
    elif s == "add_amt":
        try:
            db.add_coins(admin_ctx[u.id]["tid"], float(txt))
            nb = db.get_user(admin_ctx[u.id]["tid"])["coins"]
            del admin_ctx[u.id]
            await upd.message.reply_text(f"{I['check']} Added **{txt}** coins! Balance: **{nb:.2f}**", parse_mode=ParseMode.MARKDOWN)
        except: await upd.message.reply_text("❌ Invalid amount")
    elif s == "rem_uid":
        try:
            admin_ctx[u.id] = {"step":"rem_amt", "tid":int(txt)}
            await upd.message.reply_text(f"✏️ Amount to remove from `{txt}`:", parse_mode=ParseMode.MARKDOWN)
        except: await upd.message.reply_text("❌ Invalid ID")
    elif s == "rem_amt":
        try:
            db.remove_coins(admin_ctx[u.id]["tid"], float(txt))
            nb = db.get_user(admin_ctx[u.id]["tid"])["coins"]
            del admin_ctx[u.id]
            await upd.message.reply_text(f"{I['check']} Removed **{txt}** coins! Balance: **{nb:.2f}**", parse_mode=ParseMode.MARKDOWN)
        except: await upd.message.reply_text("❌ Invalid amount")
    elif s == "set_uid":
        try:
            admin_ctx[u.id] = {"step":"set_amt", "tid":int(txt)}
            await upd.message.reply_text(f"✏️ Set coins to what for `{txt}`?:", parse_mode=ParseMode.MARKDOWN)
        except: await upd.message.reply_text("❌ Invalid ID")
    elif s == "set_amt":
        try:
            db.set_coins(admin_ctx[u.id]["tid"], float(txt))
            del admin_ctx[u.id]
            await upd.message.reply_text(f"{I['check']} Set coins to **{txt}**!", parse_mode=ParseMode.MARKDOWN)
        except: await upd.message.reply_text("❌ Invalid amount")
    elif s == "price":
        try:
            db.set_setting("price_per_coin", float(txt))
            del admin_ctx[u.id]
            await upd.message.reply_text(f"{I['check']} Price per coin set to **${txt}**!", parse_mode=ParseMode.MARKDOWN)
        except: await upd.message.reply_text("❌ Invalid price")
    elif s == "coinref":
        try:
            db.set_setting("coins_per_referral", float(txt))
            del admin_ctx[u.id]
            await upd.message.reply_text(f"{I['check']} Coins per referral set to **{txt}**!", parse_mode=ParseMode.MARKDOWN)
        except: await upd.message.reply_text("❌ Invalid number")
    elif s == "minref":
        try:
            db.set_setting("min_referrals_per_day", int(txt))
            del admin_ctx[u.id]
            await upd.message.reply_text(f"{I['check']} Min referrals/day set to **{txt}**!", parse_mode=ParseMode.MARKDOWN)
        except: await upd.message.reply_text("❌ Invalid number")
    elif s == "maxref":
        try:
            db.set_setting("max_referrals_per_day", int(txt))
            del admin_ctx[u.id]
            await upd.message.reply_text(f"{I['check']} Max referrals/day set to **{txt}**!", parse_mode=ParseMode.MARKDOWN)
        except: await upd.message.reply_text("❌ Invalid number")
    elif s == "bcast":
        del admin_ctx[u.id]
        us = db.get_all_users()
        sc = 0; fl = 0
        m = await upd.message.reply_text(f"{I['broadcast']} Sending to **{len(us)}** users...", parse_mode=ParseMode.MARKDOWN)
        for i, u2 in enumerate(us):
            try:
                await ctx.bot.send_message(chat_id=u2["user_id"], text=txt, parse_mode=ParseMode.MARKDOWN)
                sc += 1
            except: fl += 1
            if (i+1)%10==0:
                await m.edit_text(f"{I['broadcast']} {i+1}/{len(us)} | ✅{sc} ❌{fl}", parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(0.03)
        db.log_broadcast(u.id, txt, "all", sc)
        await m.edit_text(f"{I['check']} **Broadcast done!** ✅{sc} ❌{fl}", parse_mode=ParseMode.MARKDOWN)
    elif s == "chadd":
        if not txt.startswith("@"): txt = f"@{txt}"
        db.add_force_channel(txt, txt, u.id)
        del admin_ctx[u.id]
        await upd.message.reply_text(f"{I['check']} Added: {txt}", parse_mode=ParseMode.MARKDOWN)
    elif s == "chrem":
        if not txt.startswith("@"): txt = f"@{txt}"
        db.remove_force_channel(txt)
        del admin_ctx[u.id]
        await upd.message.reply_text(f"{I['check']} Removed: {txt}", parse_mode=ParseMode.MARKDOWN)

# ── TEXT HANDLER ──
async def text_handler(upd, ctx):
    u = upd.effective_user; txt = upd.message.text.strip()
    if u.id in admin_ctx:
        await handle_admin_text(upd, ctx, u, admin_ctx[u.id].get("step",""))
        return
    if u.id in admin_ctx and admin_ctx[u.id].get("step")=="cnt":
        try:
            c = int(txt); mx = db.get_setting("max_referrals_per_day",5)
            if c<1 or c>mx:
                await upd.message.reply_text(f"Enter 1-{mx}:", parse_mode=ParseMode.MARKDOWN); return
            b = admin_ctx[u.id]["bot"]; cd = admin_ctx[u.id]["code"]
            del admin_ctx[u.id]
            if not await check_fj(upd, ctx): return
            class FQ:
                def __init__(self, m): self.message = m
                async def edit_message_text(self, *a, **kw): pass
                async def answer(self): pass
            await do_ref(FQ(upd.message), u.id, b, cd, c)
        except: await upd.message.reply_text("Send a valid number:", parse_mode=ParseMode.MARKDOWN)
        return
    db.get_or_create_user(u.id, u.username, u.first_name, u.last_name)
    if "t.me/" in txt and ("?start=" in txt or "?startapp=" in txt):
        ctx.args = [txt]; await refer_cmd(upd, ctx); return
    if not await check_fj(upd, ctx): return
    await main_menu(upd, u.id)

# ── ERROR HANDLER ──
async def err_handler(upd, ctx):
    logger.error(f"Error: {ctx.error}")
    try:
        if upd and upd.effective_message:
            await upd.effective_message.reply_text(f"{I['warning']} Something went wrong.", parse_mode=ParseMode.MARKDOWN)
    except: pass

# ── MAIN ──
async def post_init(app):
    print(f"""
╔══════════════════════════════════════════╗
║   {I['rocket']}  REFERRAL MASTER BOT v3.0  {I['rocket']}          ║
║   {I['crown']}  Admin Panel | Coins | Force Join      ║
╠══════════════════════════════════════════╣
║  Users: {str(db.get_user_count()).rjust(5)}  |  Admins: {len(ADMIN_IDS)}  ║
║  Channels: {len(db.get_force_channels())} force-join                ║
║  {I['lightning']}  Running!                              ║
╚══════════════════════════════════════════╝""")
    logger.info(f"Started | Users: {db.get_user_count()}")

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("refer", refer_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(err_handler)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
