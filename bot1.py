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
        
