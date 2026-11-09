# ╔═══════════════════════════════════════════════════════════════╗
# ║          BOT MAKE BY LE NHAN  ·  v2.0                        ║
# ║          Zalo Group Bot + Telegram Manager                    ║
# ║          Owner  : Huynh Le Nhan                              ║
# ║          Prefix : ?                                          ║
# ║          Deploy : Render.com (single file)                   ║
# ╚═══════════════════════════════════════════════════════════════╝
# language: Python 3.11+, file: bot.py

import os, sys, json, time, sqlite3, re, threading, random, hashlib, io, math, datetime
import requests
from flask import Flask, jsonify, send_file, request as freq
from zlapi import ZaloAPI
from zlapi.models import *

# ═══════════════════════════════════════════════════════════════════
#  CONFIG  —  set qua Environment Variables trên Render
# ═══════════════════════════════════════════════════════════════════
PREFIX        = "?"
BOT_NAME      = "Bot Make By Le Nhan"
OWNER_NAME    = "Huynh Le Nhan"
VERSION       = "2.0"
# UIDs Zalo owner, cách nhau dấu phẩy trong env OWNER_IDS
OWNER_IDS     = [x.strip() for x in os.environ.get("OWNER_IDS","").split(",") if x.strip()]
DB_PATH       = "data/bot.db"
SESSION_PATH  = "data/session.json"
PORT          = int(os.environ.get("PORT", 10000))
OPENAI_KEY    = os.environ.get("OPENAI_KEY", "")
GEMINI_KEY    = os.environ.get("GEMINI_KEY", "")
TELE_TOKEN    = os.environ.get("TELE_TOKEN", "")
TELE_CHAT_ID  = os.environ.get("TELE_CHAT_ID", "")

# Permission
P_USR=0; P_GRP=1; P_BOT=2; P_HI=3; P_DEV=99
PNAME = {P_USR:"👤 USR", P_GRP:"🔰 GRP ADMIN", P_BOT:"🛡 BOT ADMIN", P_HI:"⭐ HI ADMIN", P_DEV:"👑 DEV"}

BOT_START = time.time()
_zalo_live = False
_qr_msg_ids = []
_dashboard_mid = None
_tele_offset = 0
_db_lock = threading.Lock()

# ═══════════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════════
os.makedirs("data", exist_ok=True)
os.makedirs("data/media", exist_ok=True)

def db():
    c = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with _db_lock:
        c = db()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            uid TEXT PRIMARY KEY, name TEXT,
            perm INTEGER DEFAULT 0, money INTEGER DEFAULT 500,
            exp INTEGER DEFAULT 0, hp INTEGER DEFAULT 100,
            atk INTEGER DEFAULT 10, blocked INTEGER DEFAULT 0,
            warn INTEGER DEFAULT 0, joined TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS groups(
            gid TEXT PRIMARY KEY, name TEXT, prefix TEXT DEFAULT '?',
            bot_on INTEGER DEFAULT 1,
            welcome INTEGER DEFAULT 0,
            welcome_msg TEXT DEFAULT 'Chào {name} đến với nhóm! 🎉',
            antispam INTEGER DEFAULT 0, antispam_limit INTEGER DEFAULT 5,
            antibadword INTEGER DEFAULT 0,
            antiurl INTEGER DEFAULT 0,
            antiforward INTEGER DEFAULT 0,
            anticard INTEGER DEFAULT 0,
            antibot INTEGER DEFAULT 0,
            antiadd INTEGER DEFAULT 0,
            event_notify INTEGER DEFAULT 1,
            pr_on INTEGER DEFAULT 0, pr_msg TEXT DEFAULT '',
            silent_all INTEGER DEFAULT 0,
            lang TEXT DEFAULT 'vi',
            nsfw INTEGER DEFAULT 0,
            rain_on INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS badwords(id INTEGER PRIMARY KEY AUTOINCREMENT, gid TEXT, word TEXT, UNIQUE(gid,word));
        CREATE TABLE IF NOT EXISTS silenced(uid TEXT, gid TEXT, ts REAL DEFAULT 0, PRIMARY KEY(uid,gid));
        CREATE TABLE IF NOT EXISTS bot_admins(uid TEXT, gid TEXT, PRIMARY KEY(uid,gid));
        CREATE TABLE IF NOT EXISTS spam_track(uid TEXT, gid TEXT, count INTEGER DEFAULT 0, last_time REAL DEFAULT 0, PRIMARY KEY(uid,gid));
        CREATE TABLE IF NOT EXISTS aliases(gid TEXT, alias TEXT, cmd TEXT, PRIMARY KEY(gid,alias));
        CREATE TABLE IF NOT EXISTS scheduled(id INTEGER PRIMARY KEY AUTOINCREMENT, gid TEXT, uid TEXT, msg TEXT, send_at REAL, repeat_sec INTEGER DEFAULT 0, sent INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY AUTOINCREMENT, from_uid TEXT, to_uid TEXT, amount INTEGER, note TEXT, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS msg_log(id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT, gid TEXT, msg TEXT, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS pets(uid TEXT PRIMARY KEY, name TEXT, type TEXT, hp INTEGER DEFAULT 100, atk INTEGER DEFAULT 10, level INTEGER DEFAULT 1, exp INTEGER DEFAULT 0, hunger INTEGER DEFAULT 100, last_feed REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS game_sessions(gid TEXT PRIMARY KEY, game TEXT, data TEXT, host TEXT, created REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS warns(id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT, gid TEXT, reason TEXT, by_uid TEXT, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY AUTOINCREMENT, gid TEXT, title TEXT, content TEXT, by_uid TEXT, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS polls(gid TEXT PRIMARY KEY, question TEXT, options TEXT, votes TEXT, closed INTEGER DEFAULT 0, by_uid TEXT);
        CREATE TABLE IF NOT EXISTS rain(id INTEGER PRIMARY KEY AUTOINCREMENT, gid TEXT, uid TEXT, amount INTEGER, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS checkin(uid TEXT, gid TEXT, last_date TEXT, streak INTEGER DEFAULT 0, PRIMARY KEY(uid,gid));
        CREATE TABLE IF NOT EXISTS shop(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price INTEGER, effect TEXT, desc TEXT);
        CREATE TABLE IF NOT EXISTS inventory(uid TEXT, item_id INTEGER, qty INTEGER DEFAULT 1, PRIMARY KEY(uid,item_id));
        CREATE TABLE IF NOT EXISTS tele_sessions(chat_id TEXT PRIMARY KEY, state TEXT, data TEXT);
        """)
        # seed shop items
        c.execute("INSERT OR IGNORE INTO shop(id,name,price,effect,desc) VALUES(1,'Thuốc HP',100,'hp+50','Hồi 50 HP')")
        c.execute("INSERT OR IGNORE INTO shop(id,name,price,effect,desc) VALUES(2,'Kiếm Sắt',500,'atk+15','Tăng 15 ATK')")
        c.execute("INSERT OR IGNORE INTO shop(id,name,price,effect,desc) VALUES(3,'Giáp Vàng',800,'hp+100','Tăng 100 MaxHP')")
        c.execute("INSERT OR IGNORE INTO shop(id,name,price,effect,desc) VALUES(4,'Bùa Hộ Mệnh',300,'block','Chặn 1 đòn tấn công')")
        c.execute("INSERT OR IGNORE INTO shop(id,name,price,effect,desc) VALUES(5,'Thức Ăn Pet',50,'pet_feed','Cho pet ăn +50 Hunger')")
        c.commit(); c.close()

init_db()

# ─── DB helpers ────────────────────────────────────────────────
def _exec(sql, p=()):
    with _db_lock:
        c=db(); c.execute(sql,p); c.commit(); c.close()

def _one(sql, p=()):
    with _db_lock:
        c=db(); r=c.execute(sql,p).fetchone(); c.close()
        return dict(r) if r else None

def _all(sql, p=()):
    with _db_lock:
        c=db(); rows=c.execute(sql,p).fetchall(); c.close()
        return [dict(r) for r in rows]

def upsert_user(uid, name=None):
    with _db_lock:
        c=db()
        c.execute("INSERT OR IGNORE INTO users(uid,name) VALUES(?,?)",(uid,name or uid))
        if name: c.execute("UPDATE users SET name=? WHERE uid=?",(name,uid))
        c.commit(); c.close()

def get_user(uid):
    return _one("SELECT * FROM users WHERE uid=?", (uid,)) or {"uid":uid,"perm":0,"money":500,"exp":0,"hp":100,"atk":10,"blocked":0,"warn":0}

def get_money(uid):   return (get_user(uid)).get("money",0)
def add_money(uid,a): _exec("UPDATE users SET money=money+? WHERE uid=?",(a,uid))
def set_perm(uid,p):  _exec("UPDATE users SET perm=? WHERE uid=?",(p,uid))

def upsert_group(gid, name=None):
    with _db_lock:
        c=db()
        c.execute("INSERT OR IGNORE INTO groups(gid,name) VALUES(?,?)",(gid,name or gid))
        if name: c.execute("UPDATE groups SET name=? WHERE gid=?",(name,gid))
        c.commit(); c.close()

def get_group(gid):     return _one("SELECT * FROM groups WHERE gid=?",(gid,)) or {}
def set_grp(gid,f,v):   _exec(f"UPDATE groups SET {f}=? WHERE gid=?",(v,gid))
def get_grp(gid,f):     return get_group(gid).get(f)

def is_bot_admin(uid,gid): return bool(_one("SELECT 1 FROM bot_admins WHERE uid=? AND gid=?",(uid,gid)))
def set_bot_admin(uid,gid,v):
    if v: _exec("INSERT OR IGNORE INTO bot_admins(uid,gid) VALUES(?,?)",(uid,gid))
    else: _exec("DELETE FROM bot_admins WHERE uid=? AND gid=?",(uid,gid))

def is_silenced(uid,gid): return bool(_one("SELECT 1 FROM silenced WHERE uid=? AND gid=?",(uid,gid)))
def set_silent(uid,gid,v):
    if v: _exec("INSERT OR IGNORE INTO silenced(uid,gid) VALUES(?,?)",(uid,gid))
    else: _exec("DELETE FROM silenced WHERE uid=? AND gid=?",(uid,gid))

def get_badwords(gid):   return [r["word"] for r in _all("SELECT word FROM badwords WHERE gid=?",(gid,))]
def add_badword(gid,w):  _exec("INSERT OR IGNORE INTO badwords(gid,word) VALUES(?,?)",(gid,w.lower()))
def del_badword(gid,w):  _exec("DELETE FROM badwords WHERE gid=? AND word=?",(gid,w.lower()))

def get_alias(gid,a):
    r=_one("SELECT cmd FROM aliases WHERE gid=? AND alias=?",(gid,a))
    return r["cmd"] if r else None
def set_alias(gid,a,cmd): _exec("INSERT OR REPLACE INTO aliases(gid,alias,cmd) VALUES(?,?,?)",(gid,a,cmd))
def del_alias(gid,a):     _exec("DELETE FROM aliases WHERE gid=? AND alias=?",(gid,a))
def list_aliases(gid):    return [(r["alias"],r["cmd"]) for r in _all("SELECT alias,cmd FROM aliases WHERE gid=?",(gid,))]

def log_msg(uid,gid,msg): _exec("INSERT INTO msg_log(uid,gid,msg) VALUES(?,?,?)",(uid,gid,msg))
def total_msgs(gid):
    r=_one("SELECT COUNT(*) cnt FROM msg_log WHERE gid=?",(gid,)); return r["cnt"] if r else 0
def top_senders(gid,n=10):
    return [(r["uid"],r["cnt"]) for r in _all("SELECT uid,COUNT(*) cnt FROM msg_log WHERE gid=? GROUP BY uid ORDER BY cnt DESC LIMIT ?",(gid,n))]

def track_spam(uid,gid,limit):
    now=time.time()
    r=_one("SELECT count,last_time FROM spam_track WHERE uid=? AND gid=?",(uid,gid))
    cnt=(r["count"]+1) if r and (now-r["last_time"])<10 else 1
    _exec("INSERT OR REPLACE INTO spam_track(uid,gid,count,last_time) VALUES(?,?,?,?)",(uid,gid,cnt,now))
    return cnt>=limit

def resolve_perm(uid,gid=None):
    if uid in OWNER_IDS: return P_DEV
    u=get_user(uid)
    if u.get("perm",0)>=P_HI: return u["perm"]
    if gid and is_bot_admin(uid,gid): return P_BOT
    return u.get("perm",P_USR)

def pname(p): return PNAME.get(p,"👤 USR")

# checkin
def do_checkin(uid,gid):
    today=datetime.date.today().isoformat()
    r=_one("SELECT last_date,streak FROM checkin WHERE uid=? AND gid=?",(uid,gid))
    if r and r["last_date"]==today: return None,"already"
    streak=1
    if r:
        try:
            prev=datetime.date.fromisoformat(r["last_date"])
            streak=(r["streak"]+1) if (datetime.date.today()-prev).days==1 else 1
        except: pass
    _exec("INSERT OR REPLACE INTO checkin(uid,gid,last_date,streak) VALUES(?,?,?,?)",(uid,gid,today,streak))
    bonus=100+(streak-1)*20
    upsert_user(uid); add_money(uid,bonus)
    return bonus,streak

# warn
def add_warn(uid,gid,reason,by_uid):
    _exec("INSERT INTO warns(uid,gid,reason,by_uid) VALUES(?,?,?,?)",(uid,gid,reason,by_uid))
    r=_one("SELECT COUNT(*) cnt FROM warns WHERE uid=? AND gid=?",(uid,gid))
    return r["cnt"] if r else 1

def get_warns(uid,gid):
    return _all("SELECT reason,by_uid,ts FROM warns WHERE uid=? AND gid=? ORDER BY ts DESC",(uid,gid))

# ═══════════════════════════════════════════════════════════════════
#  TELEGRAM LAYER
# ═══════════════════════════════════════════════════════════════════
def tele(method, **kw):
    if not TELE_TOKEN: return None
    try:
        r=requests.post(f"https://api.telegram.org/bot{TELE_TOKEN}/{method}",json=kw,timeout=15)
        return r.json()
    except: return None

def tele_text(text, chat_id=None, parse_mode="HTML", reply_markup=None, disable_preview=True):
    cid=chat_id or TELE_CHAT_ID
    if not cid: return None
    kw={"chat_id":cid,"text":text,"parse_mode":parse_mode,"disable_web_page_preview":disable_preview}
    if reply_markup: kw["reply_markup"]=reply_markup
    return tele("sendMessage",**kw)

def tele_photo(path, caption="", chat_id=None, reply_markup=None):
    cid=chat_id or TELE_CHAT_ID
    if not cid or not TELE_TOKEN: return None
    try:
        with open(path,"rb") as f:
            data={"chat_id":cid,"caption":caption,"parse_mode":"HTML"}
            if reply_markup: data["reply_markup"]=json.dumps(reply_markup)
            r=requests.post(f"https://api.telegram.org/bot{TELE_TOKEN}/sendPhoto",
                data=data,files={"photo":f},timeout=20)
        return r.json()
    except: return None

def tele_edit(msg_id, text, chat_id=None, reply_markup=None, parse_mode="HTML"):
    cid=chat_id or TELE_CHAT_ID
    kw={"chat_id":cid,"message_id":msg_id,"text":text,"parse_mode":parse_mode,"disable_web_page_preview":True}
    if reply_markup: kw["reply_markup"]=reply_markup
    tele("editMessageText",**kw)

def tele_delete(msg_id, chat_id=None):
    tele("deleteMessage",chat_id=chat_id or TELE_CHAT_ID,message_id=msg_id)

def tele_answer(cb_id, text="", alert=False):
    tele("answerCallbackQuery",callback_query_id=cb_id,text=text,show_alert=alert)

# ─── Keyboards ─────────────────────────────────────────────────
def kb(*rows): return {"inline_keyboard":list(rows)}
def btn(text, cb): return {"text":text,"callback_data":cb}
def url_btn(text, url): return {"text":text,"url":url}
def back(to="main"): return [btn("◀️ Quay lại",to)]

def kb_main():
    return kb(
        [btn("📊 Dashboard","dashboard"),  btn("📈 Thống kê","stats")],
        [btn("👥 Nhóm","groups"),          btn("👑 Admins","admins")],
        [btn("🛡 Anti","anti_menu"),       btn("🔇 Silence","silence_menu")],
        [btn("💰 Economy","economy"),      btn("🎮 Games","games_info")],
        [btn("⚠️ Warns","warns_menu"),     btn("📝 Notes","notes_menu")],
        [btn("⚙️ Cài đặt","settings"),    btn("🔄 Restart","confirm_restart")],
        [btn("❓ Trợ giúp","help_menu"),   btn("🔑 QR Login","get_qr")],
    )

def _uptime():
    s=int(time.time()-BOT_START); h=s//3600; m=(s%3600)//60; s2=s%60
    return f"{h}h {m}m {s2}s"

def dashboard_text():
    u=_one("SELECT COUNT(*) cnt FROM users") or {}
    g=_one("SELECT COUNT(*) cnt FROM groups") or {}
    m=_one("SELECT COUNT(*) cnt FROM msg_log") or {}
    mn=_one("SELECT SUM(money) s FROM users") or {}
    today=datetime.date.today().isoformat()
    td=_one("SELECT COUNT(*) cnt FROM msg_log WHERE ts>=?",(today,)) or {}
    status="🟢 Online" if _zalo_live else "🔴 Offline"
    return (
        f"╔════════════════════════╗\n"
        f"║ 🤖 <b>{BOT_NAME}</b>\n"
        f"║ 👑 <b>{OWNER_NAME}</b>  v{VERSION}\n"
        f"╠════════════════════════╣\n"
        f"║ Zalo  : {status}\n"
        f"║ Uptime: {_uptime()}\n"
        f"╠════════════════════════╣\n"
        f"║ 👤 Users  : <b>{u.get('cnt',0):,}</b>\n"
        f"║ 👥 Nhóm   : <b>{g.get('cnt',0):,}</b>\n"
        f"║ 💬 Tin/ngày: <b>{td.get('cnt',0):,}</b>\n"
        f"║ 💬 Tổng   : <b>{m.get('cnt',0):,}</b>\n"
        f"║ 💰 Economy: <b>{(mn.get('s') or 0):,}</b>\n"
        f"╚════════════════════════╝"
    )

# ─── Telegram poll loop ────────────────────────────────────────
def tele_poll(zbot):
    global _tele_offset, _dashboard_mid
    # gửi dashboard
    r=tele_text(dashboard_text(), reply_markup=kb_main())
    if r and r.get("ok"):
        _dashboard_mid=r["result"]["message_id"]
    while True:
        try:
            upds=tele("getUpdates",offset=_tele_offset,timeout=30) or {}
            for u2 in upds.get("result",[]):
                _tele_offset=u2["update_id"]+1
                if "callback_query" in u2: _cb(u2["callback_query"],zbot)
                elif "message" in u2:      _tm(u2["message"],zbot)
        except Exception as e: print(f"[TELE] {e}")
        time.sleep(1)

def _auth(cid):
    return str(cid)==str(TELE_CHAT_ID)

def _cb(cb, zbot):
    cid=str(cb["from"]["id"]); cb_id=cb["id"]; data=cb.get("data",""); mid=cb["message"]["message_id"]
    if not _auth(cid): tele_answer(cb_id,"⛔ Không có quyền",True); return
    tele_answer(cb_id)

    def edit(txt, mk=None): tele_edit(mid, txt, reply_markup=mk)

    # ── main / dashboard ──
    if data in ("main","dashboard"):
        edit(dashboard_text(), kb_main())

    elif data == "stats":
        u=_one("SELECT COUNT(*) cnt FROM users") or {}
        g=_one("SELECT COUNT(*) cnt FROM groups") or {}
        m=_one("SELECT COUNT(*) cnt FROM msg_log") or {}
        rich=_all("SELECT uid,name,money FROM users ORDER BY money DESC LIMIT 5")
        top_msg=_all("SELECT uid,COUNT(*) cnt FROM msg_log GROUP BY uid ORDER BY cnt DESC LIMIT 5")
        lines_r="\n".join(f"  #{i+1} {r.get('name') or r['uid'][:10]}: {r['money']:,}💰" for i,r in enumerate(rich))
        lines_m="\n".join(f"  #{i+1} {r['uid'][:10]}: {r['cnt']} tin" for i,r in enumerate(top_msg))
        edit(f"📈 <b>Thống kê bot</b>\n\n"
             f"👤 Users: <b>{u.get('cnt',0):,}</b>\n"
             f"👥 Nhóm:  <b>{g.get('cnt',0):,}</b>\n"
             f"💬 Tin:   <b>{m.get('cnt',0):,}</b>\n\n"
             f"💰 Top giàu:\n{lines_r}\n\n"
             f"💬 Top nhắn tin:\n{lines_m}",
             kb([back()]))

    elif data == "groups":
        gs=_all("SELECT gid,name FROM groups ORDER BY rowid DESC LIMIT 12")
        if not gs: edit("Chưa có nhóm.",kb([back()])); return
        rows=[[btn(f"{'🟢' if get_grp(r['gid'],'bot_on') else '🔴'} {(r.get('name') or r['gid'])[:18]}",f"grp_{r['gid']}")]
               for r in gs]
        rows.append(back())
        edit("👥 <b>Danh sách nhóm</b>",kb(*rows))

    elif data.startswith("grp_"):
        gid=data[4:]
        g2=get_group(gid); tc=total_msgs(gid)
        top=top_senders(gid,3)
        tstr="\n".join(f"  #{i+1} {u2[:10]}: {c}" for i,(u2,c) in enumerate(top))
        edit(f"📌 <b>{g2.get('name') or gid[:20]}</b>\n"
             f"GID: <code>{gid}</code>\n"
             f"Bot: {'🟢 ON' if g2.get('bot_on',1) else '🔴 OFF'}\n"
             f"Prefix: <code>{g2.get('prefix','?')}</code>\n"
             f"Tin nhắn: {tc:,}\n"
             f"Top:\n{tstr or '  Chưa có'}",
             kb([btn("🔴 Tắt bot" if g2.get("bot_on",1) else "🟢 Bật bot",f"bot_tog_{gid}"),
                 btn("🛡 Anti",f"grp_anti_{gid}")],
                [btn("📢 Broadcast",f"bc_{gid}"), btn("⚙️ Settings",f"grp_set_{gid}")],
                back("groups")))

    elif data.startswith("bot_tog_"):
        gid=data[8:]; cur=get_grp(gid,"bot_on") or 0
        set_grp(gid,"bot_on",0 if cur else 1)
        _cb({**cb,"data":f"grp_{gid}"},zbot)

    elif data.startswith("grp_anti_"):
        gid=data[9:]; g2=get_group(gid)
        def ico(v): return "✅" if v else "❌"
        edit(f"🛡 <b>Anti — {(g2.get('name') or gid)[:16]}</b>\n\n"
             f"{ico(g2.get('antispam'))} Spam (limit {g2.get('antispam_limit',5)}/10s)\n"
             f"{ico(g2.get('antibadword'))} Badword\n"
             f"{ico(g2.get('antiurl'))} URL\n"
             f"{ico(g2.get('antiforward'))} Forward\n"
             f"{ico(g2.get('anticard'))} Card\n"
             f"{ico(g2.get('antibot'))} Bot\n"
             f"{ico(g2.get('antiadd'))} Add",
             kb([btn(f"{'❌' if g2.get('antispam') else '✅'} Spam",  f"tog_antispam_{gid}"),
                 btn(f"{'❌' if g2.get('antibadword') else '✅'} Badword",f"tog_antibadword_{gid}")],
                [btn(f"{'❌' if g2.get('antiurl') else '✅'} URL",   f"tog_antiurl_{gid}"),
                 btn(f"{'❌' if g2.get('antiforward') else '✅'} Fwd",f"tog_antiforward_{gid}")],
                [btn(f"{'❌' if g2.get('anticard') else '✅'} Card", f"tog_anticard_{gid}"),
                 btn(f"{'❌' if g2.get('antibot') else '✅'} Bot",   f"tog_antibot_{gid}")],
                [btn(f"{'❌' if g2.get('antiadd') else '✅'} Add",   f"tog_antiadd_{gid}")],
                back(f"grp_{gid}")))

    elif data.startswith("tog_"):
        parts=data.split("_",2); field=parts[1]; gid=parts[2]
        cur=get_grp(gid,field) or 0; set_grp(gid,field,0 if cur else 1)
        _cb({**cb,"data":f"grp_anti_{gid}"},zbot)

    elif data.startswith("grp_set_"):
        gid=data[8:]; g2=get_group(gid)
        edit(f"⚙️ <b>Settings — {(g2.get('name') or gid)[:16]}</b>\n\n"
             f"Prefix: <code>{g2.get('prefix','?')}</code>\n"
             f"Welcome: {'✅' if g2.get('welcome') else '❌'}\n"
             f"Event: {'✅' if g2.get('event_notify') else '❌'}",
             kb([btn("{'❌' if g2.get('welcome') else '✅'} Welcome",f"tog_welcome_{gid}"),
                 btn("{'❌' if g2.get('event_notify') else '✅'} Event",f"tog_event_notify_{gid}")],
                back(f"grp_{gid}")))

    elif data.startswith("bc_"):
        gid=data[3:]
        # lưu state chờ nhập nội dung broadcast
        _exec("INSERT OR REPLACE INTO tele_sessions(chat_id,state,data) VALUES(?,?,?)",
            (cid,"bc_wait",gid))
        edit(f"📢 Nhập nội dung broadcast cho nhóm <code>{gid}</code>:\n(Gửi tin nhắn tiếp theo)",
             kb([back(f"grp_{gid}")]))

    elif data == "anti_menu":
        gs=_all("SELECT gid,name FROM groups LIMIT 10")
        if not gs: edit("Chưa có nhóm.",kb([back()])); return
        rows=[[btn(f"🛡 {(r.get('name') or r['gid'])[:18]}",f"grp_anti_{r['gid']}")] for r in gs]
        rows.append(back())
        edit("🛡 <b>Chọn nhóm để quản lý Anti</b>",kb(*rows))

    elif data == "silence_menu":
        gs=_all("SELECT gid,name FROM groups LIMIT 10")
        if not gs: edit("Chưa có nhóm.",kb([back()])); return
        rows=[[btn(f"🔇 {(r.get('name') or r['gid'])[:18]}",f"sil_grp_{r['gid']}")] for r in gs]
        rows.append(back())
        edit("🔇 <b>Quản lý Silence</b>",kb(*rows))

    elif data.startswith("sil_grp_"):
        gid=data[8:]
        silenced=_all("SELECT uid FROM silenced WHERE gid=?",(gid,))
        lines="\n".join(f"• {r['uid']}" for r in silenced) or "Trống"
        edit(f"🔇 <b>Silenced — {gid[:16]}</b>\n\n{lines}",kb([back("silence_menu")]))

    elif data == "admins":
        rows=_all("SELECT uid,name,perm FROM users WHERE perm>0 ORDER BY perm DESC LIMIT 20")
        lines="\n".join(f"{pname(r['perm'])} {r.get('name') or r['uid'][:14]}" for r in rows)
        edit(f"👑 <b>Admins ({len(rows)})</b>\n\n{lines or 'Chưa có'}",kb([back()]))

    elif data == "economy":
        rich=_all("SELECT uid,name,money FROM users ORDER BY money DESC LIMIT 10")
        txs=_all("SELECT from_uid,to_uid,amount,note FROM transactions ORDER BY id DESC LIMIT 5")
        lines_r="\n".join(f"#{i+1} {r.get('name') or r['uid'][:10]}: {r['money']:,}💰" for i,r in enumerate(rich))
        lines_t="\n".join(f"{t['from_uid'][:8]}→{t['to_uid'][:8]}: {t['amount']:,} ({t['note']})" for t in txs)
        edit(f"💰 <b>Economy</b>\n\n🏆 Top giàu:\n{lines_r or 'Trống'}\n\n📋 Giao dịch gần đây:\n{lines_t or 'Chưa có'}",
             kb([btn("💸 Buff user","buff_input")],back()))

    elif data == "buff_input":
        _exec("INSERT OR REPLACE INTO tele_sessions(chat_id,state,data) VALUES(?,?,?)",(cid,"buff_wait",""))
        edit("💸 Nhập: <code>uid amount</code>\nVD: <code>123456 1000</code>",kb([back("economy")]))

    elif data == "games_info":
        edit("🎮 <b>Games trong bot</b>\n\n"
             "🎲 <code>?taixiu tai/xiu tiền</code>\n"
             "🦀 <code>?baucua con tiền</code>\n"
             "🃏 <code>?poker</code>\n"
             "🐺 <code>?masoi start|join|begin</code>\n"
             "🏔 <code>?tutien</code> — Tu tiên RPG\n"
             "🐾 <code>?pet</code> — Nuôi thú cưng\n"
             "🌍 <code>?life</code> — Cuộc sống RPG\n"
             "⚓ <code>?htht</code> — Hải Tặc\n"
             "⚔️ <code>?warcard @uid</code>\n"
             "🛒 <code>?shop</code> — Cửa hàng\n"
             "📅 <code>?checkin</code> — Điểm danh\n"
             "🌧 <code>?rain tiền</code> — Rải tiền nhóm",
             kb([back()]))

    elif data == "warns_menu":
        gs=_all("SELECT gid,name FROM groups LIMIT 10")
        if not gs: edit("Chưa có nhóm.",kb([back()])); return
        rows=[[btn(f"⚠️ {(r.get('name') or r['gid'])[:18]}",f"warns_grp_{r['gid']}")] for r in gs]
        rows.append(back())
        edit("⚠️ <b>Quản lý Warns</b>",kb(*rows))

    elif data.startswith("warns_grp_"):
        gid=data[10:]
        ws=_all("SELECT uid,COUNT(*) cnt FROM warns WHERE gid=? GROUP BY uid ORDER BY cnt DESC LIMIT 10",(gid,))
        lines="\n".join(f"⚠️ {r['uid'][:14]}: {r['cnt']} cảnh cáo" for r in ws) or "Chưa có"
        edit(f"⚠️ <b>Warns — {gid[:16]}</b>\n\n{lines}",kb([back("warns_menu")]))

    elif data == "notes_menu":
        gs=_all("SELECT gid,name FROM groups LIMIT 10")
        if not gs: edit("Chưa có nhóm.",kb([back()])); return
        rows=[[btn(f"📝 {(r.get('name') or r['gid'])[:18]}",f"notes_grp_{r['gid']}")] for r in gs]
        rows.append(back())
        edit("📝 <b>Ghi chú nhóm</b>",kb(*rows))

    elif data.startswith("notes_grp_"):
        gid=data[10:]
        notes=_all("SELECT title,content,by_uid FROM notes WHERE gid=? ORDER BY id DESC LIMIT 10",(gid,))
        lines="\n\n".join(f"📌 <b>{n['title']}</b>\n{n['content'][:100]}" for n in notes) or "Chưa có ghi chú"
        edit(f"📝 <b>Ghi chú — {gid[:16]}</b>\n\n{lines}",kb([back("notes_menu")]))

    elif data == "settings":
        edit("⚙️ <b>Cài đặt bot</b>\n\n"
             "Lệnh Telegram:\n"
             "/broadcast gid nội_dung\n"
             "/buff uid amount\n"
             "/setperm uid level\n"
             "/addword gid word\n"
             "/silence uid gid\n"
             "/unsilence uid gid\n"
             "/warn uid gid lý_do\n"
             "/setwelcome gid nội_dung",
             kb([back()]))

    elif data == "help_menu":
        edit("❓ <b>Trợ giúp</b>\n\n"
             "Zalo prefix: <code>?</code>\n\n"
             "Quyền hạn:\n"
             "👤 USR — Tất cả\n"
             "🔰 GRP ADMIN — Admin Zalo\n"
             "🛡 BOT ADMIN — Do HI ADMIN set\n"
             "⭐ HI ADMIN — Do Owner set\n"
             "👑 DEV — Owner bot\n\n"
             "/help để xem lệnh Telegram đầy đủ",
             kb([back()]))

    elif data == "confirm_restart":
        edit("⚠️ Xác nhận restart bot?",
             kb([btn("✅ Xác nhận","do_restart"), btn("❌ Huỷ","main")]))

    elif data == "do_restart":
        edit("♻️ Đang restart...")
        time.sleep(1); os.execv(sys.executable,[sys.executable]+sys.argv)

    elif data == "get_qr":
        edit("📱 Đang lấy QR mới...")
        try:
            import qrcode as qrc
            qr_data=zbot.getQRCodeLogin()
            qr_url=qr_data["data"]["qr_url"]
            img=qrc.make(qr_url); img.save("qr.png")
            res=tele_photo("qr.png",f"📱 <b>QR Login</b>\n⏳ Hiệu lực ~2 phút\n👑 {OWNER_NAME}")
            if res and res.get("ok"):
                _qr_msg_ids.append(res["result"]["message_id"])
            tele_delete(mid)
        except Exception as e:
            edit(f"❌ Lỗi QR: {e}")

# ─── Telegram text messages ────────────────────────────────────
def _tm(msg, zbot):
    cid=str(msg.get("from",{}).get("id",""))
    text=msg.get("text","")
    if not _auth(cid): return

    # check state machine
    sess=_one("SELECT state,data FROM tele_sessions WHERE chat_id=?",(cid,))
    if sess and sess.get("state"):
        st=sess["state"]; dt=sess["data"]
        _exec("DELETE FROM tele_sessions WHERE chat_id=?",(cid,))
        if st=="bc_wait":
            gid=dt
            try:
                zbot._send(text, gid, GroupType.GROUP)
                tele_text(f"✅ Broadcast xong → nhóm <code>{gid}</code>",chat_id=cid)
            except Exception as e:
                tele_text(f"❌ Lỗi: {e}",chat_id=cid)
            return
        elif st=="buff_wait":
            try:
                parts=text.split(); uid2=parts[0]; amt=int(parts[1])
                upsert_user(uid2); add_money(uid2,amt)
                tele_text(f"💸 Buff {amt:,} → {uid2}",chat_id=cid)
            except:
                tele_text("❌ Sai cú pháp. Nhập: uid amount",chat_id=cid)
            return

    if not text.startswith("/"): return
    parts=text.split(); cmd=parts[0].lower(); args=parts[1:]
    def reply(t): tele_text(t,chat_id=cid)

    if cmd=="/start":
        reply(f"👋 <b>{BOT_NAME}</b> v{VERSION}\n👑 {OWNER_NAME}\n\n/help — xem lệnh\n/stats — thống kê")

    elif cmd=="/help":
        reply(
            "📋 <b>Lệnh Telegram Manager</b>\n\n"
            "<b>Thông tin</b>\n"
            "/start — Giới thiệu\n"
            "/stats — Thống kê\n"
            "/groups — Nhóm\n"
            "/admins — Admins\n"
            "/top [gid] — Top nhắn tin\n"
            "/rich — Top giàu\n"
            "/uptime — Uptime\n\n"
            "<b>Quản lý</b>\n"
            "/broadcast gid msg — Gửi tin nhóm\n"
            "/buff uid amt — Buff tiền\n"
            "/setperm uid 0-3 — Đặt quyền\n"
            "/silence uid gid — Tắt chat\n"
            "/unsilence uid gid — Bỏ silence\n"
            "/warn uid gid reason — Cảnh cáo\n"
            "/clearwarn uid gid — Xoá warn\n"
            "/kick uid gid — Kick Zalo\n\n"
            "<b>Anti</b>\n"
            "/anti gid — Trạng thái anti\n"
            "/addword gid word — Badword\n"
            "/delword gid word — Xoá badword\n"
            "/badwords gid — Danh sách\n\n"
            "<b>Bot</b>\n"
            "/setwelcome gid msg — Welcome\n"
            "/setperm uid level — Quyền\n"
            "/setowner uid — Set owner\n"
            "/restart — Restart\n"
            "/qr — QR login\n"
        )

    elif cmd=="/stats":
        u=_one("SELECT COUNT(*) cnt FROM users") or {}
        g=_one("SELECT COUNT(*) cnt FROM groups") or {}
        m=_one("SELECT COUNT(*) cnt FROM msg_log") or {}
        reply(f"📊 Users: {u.get('cnt',0)} | Nhóm: {g.get('cnt',0)} | Tin: {m.get('cnt',0):,}")

    elif cmd=="/uptime":
        reply(f"⏱ Uptime: {_uptime()}\n🤖 {BOT_NAME}")

    elif cmd=="/groups":
        gs=_all("SELECT gid,name FROM groups LIMIT 20")
        lines="\n".join(f"• {r.get('name') or r['gid'][:16]} — <code>{r['gid']}</code>" for r in gs)
        reply(f"👥 <b>Nhóm ({len(gs)})</b>\n\n{lines or 'Trống'}")

    elif cmd=="/admins":
        rows=_all("SELECT uid,name,perm FROM users WHERE perm>0 ORDER BY perm DESC LIMIT 20")
        lines="\n".join(f"{pname(r['perm'])} {r.get('name') or r['uid']}" for r in rows)
        reply(f"👑 <b>Admins</b>\n\n{lines or 'Trống'}")

    elif cmd=="/top":
        gid=args[0] if args else None
        if not gid:
            gs=_all("SELECT gid FROM groups LIMIT 1"); gid=gs[0]["gid"] if gs else None
        if not gid: reply("Cần gid"); return
        top=top_senders(gid)
        lines="\n".join(f"#{i+1} {u2[:12]}: {c}" for i,(u2,c) in enumerate(top))
        reply(f"📊 <b>Top nhắn tin</b>\n\n{lines or 'Chưa có'}")

    elif cmd=="/rich":
        rich=_all("SELECT uid,name,money FROM users ORDER BY money DESC LIMIT 10")
        lines="\n".join(f"#{i+1} {r.get('name') or r['uid'][:10]}: {r['money']:,}💰" for i,r in enumerate(rich))
        reply(f"💰 <b>Top giàu</b>\n\n{lines or 'Trống'}")

    elif cmd=="/broadcast":
        if len(args)<2: reply("Dùng: /broadcast gid nội_dung"); return
        gid=args[0]; bmsg=" ".join(args[1:])
        try: zbot._send(bmsg,gid,GroupType.GROUP); reply(f"✅ Gửi xong → {gid}")
        except Exception as e: reply(f"❌ {e}")

    elif cmd=="/buff":
        if len(args)<2: reply("Dùng: /buff uid amount"); return
        upsert_user(args[0]); add_money(args[0],int(args[1]))
        reply(f"💸 Buff {int(args[1]):,} → {args[0]}")

    elif cmd=="/setperm":
        if len(args)<2: reply("Dùng: /setperm uid 0-3"); return
        upsert_user(args[0]); set_perm(args[0],int(args[1]))
        reply(f"✅ {args[0]} → {pname(int(args[1]))}")

    elif cmd=="/silence":
        if len(args)<2: reply("Dùng: /silence uid gid"); return
        set_silent(args[0],args[1],True); reply(f"🔇 Silenced {args[0]}")

    elif cmd=="/unsilence":
        if len(args)<2: reply("Dùng: /unsilence uid gid"); return
        set_silent(args[0],args[1],False); reply(f"🔊 Unsilenced {args[0]}")

    elif cmd=="/warn":
        if len(args)<2: reply("Dùng: /warn uid gid [reason]"); return
        reason=" ".join(args[2:]) if len(args)>2 else "Vi phạm"
        cnt=add_warn(args[0],args[1],reason,"TELE")
        reply(f"⚠️ Warn #{cnt} → {args[0]}\nLý do: {reason}")
        try: zbot._send(f"⚠️ [{args[0]}] bị cảnh cáo #{cnt}\nLý do: {reason}",args[1],GroupType.GROUP)
        except: pass

    elif cmd=="/clearwarn":
        if len(args)<2: reply("Dùng: /clearwarn uid gid"); return
        _exec("DELETE FROM warns WHERE uid=? AND gid=?",(args[0],args[1]))
        reply(f"✅ Đã xoá warn của {args[0]}")

    elif cmd=="/kick":
        if len(args)<2: reply("Dùng: /kick uid gid"); return
        try: zbot.removeUsersFromGroup(args[0],args[1]); reply(f"👢 Kicked {args[0]}")
        except Exception as e: reply(f"❌ {e}")

    elif cmd=="/anti":
        if not args: reply("Dùng: /anti gid"); return
        g2=get_group(args[0]); ico=lambda v:"✅" if v else "❌"
        reply(f"🛡 <b>Anti — {args[0]}</b>\n"
              f"{ico(g2.get('antispam'))} Spam\n{ico(g2.get('antibadword'))} Badword\n"
              f"{ico(g2.get('antiurl'))} URL\n{ico(g2.get('antiforward'))} Forward\n"
              f"{ico(g2.get('anticard'))} Card\n{ico(g2.get('antibot'))} Bot\n{ico(g2.get('antiadd'))} Add")

    elif cmd=="/addword":
        if len(args)<2: reply("Dùng: /addword gid word"); return
        add_badword(args[0],args[1]); reply(f"✅ Thêm badword: {args[1]}")

    elif cmd=="/delword":
        if len(args)<2: reply("Dùng: /delword gid word"); return
        del_badword(args[0],args[1]); reply(f"✅ Xoá badword: {args[1]}")

    elif cmd=="/badwords":
        if not args: reply("Dùng: /badwords gid"); return
        bw=get_badwords(args[0]); reply(f"🤬 {', '.join(bw) if bw else 'Trống'}")

    elif cmd=="/setwelcome":
        if len(args)<2: reply("Dùng: /setwelcome gid nội_dung"); return
        set_grp(args[0],"welcome_msg"," ".join(args[1:])); set_grp(args[0],"welcome",1)
        reply(f"✅ Welcome set cho {args[0]}")

    elif cmd=="/setowner":
        if not args: reply("Dùng: /setowner uid"); return
        OWNER_IDS.append(args[0]); reply(f"✅ {args[0]} → DEV")

    elif cmd=="/restart":
        reply("♻️ Restarting..."); time.sleep(1)
        os.execv(sys.executable,[sys.executable]+sys.argv)

    elif cmd=="/qr":
        reply("📱 Đang lấy QR...")
        try:
            import qrcode as qrc
            qr_data=zbot.getQRCodeLogin(); qr_url=qr_data["data"]["qr_url"]
            img=qrc.make(qr_url); img.save("qr.png")
            tele_photo("qr.png",f"📱 QR Login — {BOT_NAME}\n⏳ ~2 phút",chat_id=cid)
        except Exception as e:
            reply(f"❌ {e}")

# ─── Dashboard auto refresh ────────────────────────────────────
def dash_refresh():
    global _dashboard_mid
    while True:
        time.sleep(90)
        if _dashboard_mid:
            try: tele_edit(_dashboard_mid, dashboard_text(), kb_main())
            except: pass

# ═══════════════════════════════════════════════════════════════════
#  ZALO BOT CLASS
# ═══════════════════════════════════════════════════════════════════
class LENhanBot(ZaloAPI):

    def onMessage(self,mid,author_id,message,message_object,thread_id,thread_type):
        try: self._handle(author_id,message,message_object,thread_id,thread_type)
        except Exception as e: print(f"[ERR msg] {e}")

    def onGroupMessage(self,mid,author_id,message,message_object,thread_id,thread_type):
        try: self._handle(author_id,message,message_object,thread_id,thread_type,is_group=True)
        except Exception as e: print(f"[ERR grp] {e}")

    def onMemberJoinGroup(self,member_id,source,group_id,group_object):
        try:
            g2=get_group(group_id)
            if g2.get("event_notify") and g2.get("welcome"):
                wmsg=g2.get("welcome_msg","Chào {name}!").replace("{name}",str(member_id))
                self._send(wmsg,group_id,GroupType.GROUP)
        except: pass

    def onMemberLeaveGroup(self,member_id,leave_type,group_id,group_object):
        try:
            g2=get_group(group_id)
            if g2.get("event_notify"):
                self._send(f"👋 {member_id} đã rời nhóm.",group_id,GroupType.GROUP)
        except: pass

    def _send(self,text,tid,ttype):
        try: self.send(Message(text=str(text)),thread_id=tid,thread_type=ttype)
        except: pass

    def _handle(self,uid,message,message_object,tid,ttype,is_group=False):
        if not message: return
        gid=tid if is_group else None
        upsert_user(uid)
        if gid: upsert_group(gid)
        g2=get_group(gid) if gid else {}
        px=g2.get("prefix",PREFIX) or PREFIX

        # ── Anti checks ──
        if gid:
            p2=resolve_perm(uid,gid)
            if g2.get("antispam") and p2<P_BOT:
                if track_spam(uid,gid,g2.get("antispam_limit",5) or 5):
                    self._send(f"⚠️ [{uid[:10]}] spam quá giới hạn — tạm silence.",tid,ttype)
                    set_silent(uid,gid,True); return
            if is_silenced(uid,gid):
                try: self.undoMessage(message_object.msgId,tid,ttype)
                except: pass; return
            if g2.get("antibadword"):
                bw=get_badwords(gid)
                if any(w in message.lower() for w in bw):
                    try: self.undoMessage(message_object.msgId,tid,ttype)
                    except: pass
                    self._send("🚫 Tin nhắn chứa từ cấm.",tid,ttype); return
            if g2.get("antiurl") and p2<P_BOT:
                if re.search(r'https?://|www\.',message,re.I):
                    try: self.undoMessage(message_object.msgId,tid,ttype)
                    except: pass
                    self._send("🚫 Không gửi link trong nhóm này.",tid,ttype); return
            if gid: log_msg(uid,gid,message)

        if not message.startswith(px): return
        raw=message[len(px):].strip()
        if not raw: return
        parts=raw.split(); cmd=parts[0].lower(); args=parts[1:]

        if gid:
            al=get_alias(gid,cmd)
            if al:
                p2=al.split()+args; cmd=p2[0].lower(); args=p2[1:]

        if gid and not g2.get("bot_on",1) and cmd!="bot": return

        self._cmd(cmd,args,uid,gid,tid,ttype,message_object,g2)

    def _cmd(self,cmd,args,uid,gid,tid,ttype,mobj,g2):
        R=lambda t: self._send(t,tid,ttype)
        p=resolve_perm(uid,gid)

        # ══ THÔNG TIN ══════════════════════════════════
        if cmd=="menu":    R(self._menu())
        elif cmd=="ping":  R(f"🏓 Pong! {BOT_NAME}\n⏱ {_uptime()}\n👑 {OWNER_NAME}")
        elif cmd=="info":
            u2=get_user(uid)
            R(f"👤 UID: {uid}\n💰 {u2.get('money',0):,} coins\n⚔️ EXP: {u2.get('exp',0)}\n"
              f"❤️ HP: {u2.get('hp',100)} | ATK: {u2.get('atk',10)}\n🔰 {pname(p)}")
        elif cmd=="uid":   R(f"🔍 UID: {args[0] if args else uid}")
        elif cmd=="check":
            import platform
            R(f"🖥 {BOT_NAME} v{VERSION}\nOS: {platform.system()}\nPy: {sys.version.split()[0]}\n👑 {OWNER_NAME}")
        elif cmd=="cpu":
            try:
                import psutil
                cpu=psutil.cpu_percent(interval=1); ram=psutil.virtual_memory()
                R(f"💻 CPU: {cpu}%\nRAM: {ram.percent}% ({ram.used//1048576}/{ram.total//1048576}MB)")
            except: R("⚠️ Cài psutil để dùng lệnh này")
        elif cmd=="uptcard": R(f"⏱ Uptime: {_uptime()}\n🤖 {BOT_NAME} v{VERSION}")
        elif cmd=="ffid":
            target=(args[0] if args else uid).lstrip("@")
            u2=get_user(target)
            R(f"🔎 UID: {target}\nTên: {u2.get('name','?')}\n{pname(u2.get('perm',0))}\n💰 {u2.get('money',0):,}")
        elif cmd=="lich":
            R(f"📅 {datetime.datetime.now().strftime('%A, %d/%m/%Y — %H:%M:%S')}")
        elif cmd=="source":
            R(f"📦 MsgID: {getattr(mobj,'msgId','?')}\nUID: {uid}\nGID: {gid}")
        elif cmd=="alys":
            top=top_senders(gid) if gid else []
            R("📊 Top nhắn tin:\n"+"\n".join(f"#{i+1} {u2}: {c}" for i,(u2,c) in enumerate(top)) if top else "Chưa có dữ liệu")
        elif cmd=="prefix":
            if not args: R(f"📌 Prefix: {g2.get('prefix',PREFIX)}"); return
            if p<P_HI: R("❌ Cần HI ADMIN"); return
            set_grp(gid,"prefix",args[0]); R(f"✅ Prefix → {args[0]}")
        elif cmd=="encode":
            if len(args)<2: R(f"Dùng: {PREFIX}encode base64|md5|hex|decode <text>"); return
            import base64 as b64; m2=args[0].lower(); t=" ".join(args[1:])
            if m2=="base64":   R(f"🔐 {b64.b64encode(t.encode()).decode()}")
            elif m2=="md5":    R(f"🔐 {hashlib.md5(t.encode()).hexdigest()}")
            elif m2=="hex":    R(f"🔐 {t.encode().hex()}")
            elif m2=="decode":
                try: R(f"🔓 {b64.b64decode(t).decode()}")
                except: R("❌ Không decode được")
        elif cmd=="translate":
            if len(args)<2: R(f"Dùng: {PREFIX}translate <lang> <text>"); return
            lang=args[0]; t=" ".join(args[1:])
            try:
                r=requests.get(f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={lang}&dt=t&q={requests.utils.quote(t)}",timeout=8)
                R(f"🌐 ({lang}): {r.json()[0][0][0]}")
            except: R("❌ Lỗi dịch")
        elif cmd=="qr":
            R(f"📱 QR cho: {' '.join(args) if args else uid}\n(Dùng /qr trên Telegram để lấy QR đăng nhập)")

        # ══ ADMIN ══════════════════════════════════════
        elif cmd=="admin":
            if p<P_HI: R("❌ Cần HI ADMIN"); return
            if len(args)<2: R(f"Dùng: {PREFIX}admin add/remove <uid>"); return
            t=args[1].lstrip("@"); upsert_user(t)
            if args[0]=="add":    set_perm(t,P_HI); R(f"✅ Thêm HI ADMIN: {t}")
            elif args[0]=="remove": set_perm(t,P_USR); R(f"✅ Xoá HI ADMIN: {t}")
        elif cmd=="acl":
            if p<P_BOT: R("❌ Cần BOT ADMIN"); return
            rows=_all("SELECT uid,perm FROM users ORDER BY perm DESC LIMIT 20")
            R("📋 Phân quyền:\n"+"\n".join(f"{pname(r['perm'])} {r['uid']}" for r in rows))
        elif cmd=="key-as":
            if p<P_HI: R("❌ Cần HI ADMIN"); return
            if not args: R(f"Dùng: {PREFIX}key-as <uid>"); return
            t=args[0].lstrip("@"); upsert_user(t)
            cur=is_bot_admin(t,gid); set_bot_admin(t,gid,not cur)
            R(f"{'✅ Thêm' if not cur else '❌ Xoá'} BOT ADMIN: {t}")
        elif cmd=="blockbot":
            if p<P_BOT: R("❌ Cần BOT ADMIN"); return
            if not args: R(f"Dùng: {PREFIX}blockbot <uid>"); return
            t=args[0].lstrip("@"); upsert_user(t)
            _exec("UPDATE users SET blocked=1 WHERE uid=?",(t,)); R(f"🚫 Blocked {t}")
        elif cmd=="bot":
            if not gid: return
            if p<P_BOT: R("❌ Cần BOT ADMIN"); return
            val=0 if args and args[0].lower() in ["off","0"] else 1
            set_grp(gid,"bot_on",val); R(f"{'🟢 Bot bật' if val else '🔴 Bot tắt'}")
        elif cmd=="baotri":
            if p<P_HI: R("❌ Cần HI ADMIN"); return
            R(f"🔧 BẢO TRÌ\n{' '.join(args) if args else 'Vui lòng chờ...'}\n👑 {OWNER_NAME}")
        elif cmd=="restart":
            if p<P_HI: R("❌ Cần HI ADMIN"); return
            R("♻️ Restart..."); time.sleep(1); os.execv(sys.executable,[sys.executable]+sys.argv)
        elif cmd=="alias":
            if not gid: return
            if not args:
                als=list_aliases(gid); R("📎 Aliases:\n"+"\n".join(f"{a}→{c}" for a,c in als) if als else "Chưa có")
            elif args[0]=="add" and len(args)>=3:
                if p<P_BOT: R("❌ Cần BOT ADMIN"); return
                set_alias(gid,args[1]," ".join(args[2:])); R(f"✅ {args[1]} → {' '.join(args[2:])}")
            elif args[0]=="del" and len(args)>=2:
                if p<P_BOT: R("❌ Cần BOT ADMIN"); return
                del_alias(gid,args[1]); R(f"✅ Xoá {args[1]}")
        elif cmd=="command":
            if p<P_BOT: R("❌ Cần BOT ADMIN"); return
            R(f"⚙️ Dùng {PREFIX}alias để tạo alias lệnh")
        elif cmd=="manager":
            if p<P_HI: R("❌ Cần HI ADMIN"); return
            R(f"🤖 {BOT_NAME} v{VERSION}\nOwner: {OWNER_NAME}\nPrefix: {g2.get('prefix',PREFIX)}\nBot: {'ON' if g2.get('bot_on',1) else 'OFF'}")
        elif cmd=="stg":
            if p<P_BOT: R("❌ Cần BOT ADMIN"); return
            if not args:
                g3=get_group(gid) if gid else {}
                R("⚙️ Settings:\n"+"\n".join(f"{k}: {v}" for k,v in g3.items() if k not in ("gid","name")))
            elif len(args)>=2:
                set_grp(gid,args[0],args[1]); R(f"✅ {args[0]} = {args[1]}")
        elif cmd=="sys":
            if p<P_DEV: R("❌ Cần DEV"); return
            R(f"🔧 Py {sys.version.split()[0]} | {BOT_NAME} v{VERSION}")
        elif cmd=="test":
            if p<P_HI: R("❌ Cần HI ADMIN"); return
            R(f"✅ Bot hoạt động bình thường!")
        elif cmd in ("mod","multibot","null","var","im","call","tree"): R("🔧 Đang phát triển.")

        # ══ MODERATION ═════════════════════════════════
        elif cmd=="kick":
            if not gid: R("❌ Chỉ dùng trong nhóm"); return
            if p<P_GRP: R("❌ Cần GRP ADMIN"); return
            if not args: R(f"Dùng: {PREFIX}kick <uid>"); return
            for t in args:
                t=t.lstrip("@")
                try: self.removeUsersFromGroup(t,gid); R(f"👢 Kicked {t}")
                except: R(f"❌ Lỗi kick {t}")
        elif cmd=="block":
            if not gid: return
            if p<P_GRP: R("❌ Cần GRP ADMIN"); return
            if not args: R(f"Dùng: {PREFIX}block <uid>"); return
            t=args[0].lstrip("@")
            try: self.removeUsersFromGroup(t,gid); R(f"🚫 Blocked {t}")
            except: R("❌ Lỗi")
        elif cmd=="approve": R("✅ Duyệt yêu cầu: đang phát triển.")
        elif cmd=="dmsg":
            if p<P_HI: R("❌ Cần HI ADMIN"); return
            if not args: R(f"Dùng: {PREFIX}dmsg <id>"); return
            try: self.undoMessage(args[0],tid,ttype); R("🗑 Xoá xong")
            except: R("❌ Lỗi")
        elif cmd=="silent":
            if not gid: return
            if p<P_GRP: R("❌ Cần GRP ADMIN"); return
            if not args: R(f"Dùng: {PREFIX}silent <uid|all>"); return
            if args[0].lower()=="all": set_grp(gid,"silent_all",1); R("🔇 Tắt chat toàn nhóm")
            else: set_silent(args[0].lstrip("@"),gid,True); R(f"🔇 Silence {args[0]}")
        elif cmd=="ckg":
            if p<P_BOT: R("❌ Cần BOT ADMIN"); return
            try: R(f"🔗 {self.getGroupLink(gid)}")
            except: R("❌ Lỗi lấy link")
        elif cmd=="wc":
            if not gid: return
            if p<P_BOT: R("❌ Cần BOT ADMIN"); return
            if not args:
                R(f"🎉 Welcome: {'✅' if get_grp(gid,'welcome') else '❌'}\n{get_grp(gid,'welcome_msg')}")
            elif args[0] in ("on","1"):  set_grp(gid,"welcome",1); R("✅ Welcome ON")
            elif args[0] in ("off","0"): set_grp(gid,"welcome",0); R("✅ Welcome OFF")
            elif args[0]=="set": set_grp(gid,"welcome_msg"," ".join(args[1:])); R("✅ Đã set")
        elif cmd=="event":
            if p<P_BOT: R("❌ Cần BOT ADMIN"); return
            val=0 if args and args[0] in ("off","0") else 1
            set_grp(gid,"event_notify",val); R(f"{'🔔 Event ON' if val else '🔕 Event OFF'}")
        elif cmd=="pr":
            if p<P_HI: R("❌ Cần HI ADMIN"); return
            if not args: R(f"Dùng: {PREFIX}pr set <msg>|on|off"); return
            if args[0]=="set": set_grp(gid,"pr_msg"," ".join(args[1:])); R("✅ Set PR")
            elif args[0] in ("on","1"):  set_grp(gid,"pr_on",1); R("✅ PR ON")
            elif args[0] in ("off","0"): set_grp(gid,"pr_on",0); R("✅ PR OFF")
        elif cmd=="treo":
            if not gid: return
            if len(args)<2: R(f"Dùng: {PREFIX}treo <giây> <msg>"); return
            try:
                _exec("INSERT INTO scheduled(gid,uid,msg,send_at) VALUES(?,?,?,?)",
                    (gid,uid," ".join(args[1:]),time.time()+int(args[0])))
                R(f"⏳ Lên lịch sau {args[0]}s")
            except: R("❌ Lỗi")
        elif cmd=="spm":
            if p<P_BOT: R("❌ Cần BOT ADMIN"); return
            if len(args)<2: R(f"Dùng: {PREFIX}spm <n> <msg>"); return
            n=min(int(args[0]),10); m2=" ".join(args[1:])
            for _ in range(n): self._send(m2,tid,ttype); time.sleep(0.5)
        elif cmd=="getlink": R("📎 Getlink attachment: đang phát triển.")
        elif cmd=="warn":
            if p<P_BOT: R("❌ Cần BOT ADMIN"); return
            if not args: R(f"Dùng: {PREFIX}warn <uid> [lý do]"); return
            t=args[0].lstrip("@"); reason=" ".join(args[1:]) if len(args)>1 else "Vi phạm nội quy"
            cnt=add_warn(t,gid,reason,uid)
            R(f"⚠️ [{t}] bị cảnh cáo #{cnt}\nLý do: {reason}")
            if cnt>=3: R(f"🚨 {t} đã bị cảnh cáo {cnt} lần! Xem xét kick.")
        elif cmd=="clearwarn":
            if p<P_BOT: R("❌ Cần BOT ADMIN"); return
            if not args: R(f"Dùng: {PREFIX}clearwarn <uid>"); return
            t=args[0].lstrip("@")
            _exec("DELETE FROM warns WHERE uid=? AND gid=?",(t,gid))
            R(f"✅ Xoá warn của {t}")
        elif cmd=="warns":
            target=(args[0] if args else uid).lstrip("@")
            ws=get_warns(target,gid)
            R(f"⚠️ Warns của {target}: {len(ws)}\n"+"\n".join(f"• {w['reason']}" for w in ws[:5]) if ws else f"✅ {target} chưa có warn")

        # ══ NOTES / POLL ═══════════════════════════════
        elif cmd=="note":
            if not gid: return
            if not args: R(f"Dùng: {PREFIX}note save <tiêu đề> | <nội dung>\n{PREFIX}note list\n{PREFIX}note show <tiêu đề>"); return
            if args[0]=="save":
                raw2=" ".join(args[1:])
                if "|" not in raw2: R("Dùng: ?note save <tiêu đề> | <nội dung>"); return
                title,content=raw2.split("|",1)
                _exec("INSERT INTO notes(gid,title,content,by_uid) VALUES(?,?,?,?)",(gid,title.strip(),content.strip(),uid))
                R(f"📝 Đã lưu: {title.strip()}")
            elif args[0]=="list":
                notes=_all("SELECT title FROM notes WHERE gid=? ORDER BY id DESC LIMIT 10",(gid,))
                R("📝 Ghi chú:\n"+"\n".join(f"• {n['title']}" for n in notes) if notes else "Chưa có ghi chú")
            elif args[0]=="show" and len(args)>1:
                title=" ".join(args[1:])
                n=_one("SELECT content FROM notes WHERE gid=? AND title LIKE ?",(gid,f"%{title}%"))
                R(f"📌 {title}\n\n{n['content']}" if n else "❌ Không tìm thấy")
            elif args[0]=="del" and len(args)>1:
                if p<P_BOT: R("❌ Cần BOT ADMIN"); return
                _exec("DELETE FROM notes WHERE gid=? AND title=?",(gid," ".join(args[1:])))
                R("✅ Đã xoá")

        elif cmd=="poll":
            if not gid: return
            if not args: R(f"Dùng: {PREFIX}poll <câu hỏi> | <A> | <B> | ...\n{PREFIX}vote A/B/C\n{PREFIX}pollresult"); return
            if args[0]=="vote":
                pl=_one("SELECT * FROM polls WHERE gid=?",(gid,))
                if not pl or pl["closed"]: R("Chưa có poll đang mở"); return
                choice=(args[1].upper() if len(args)>1 else "")
                opts=json.loads(pl["options"]); votes=json.loads(pl["votes"] or "{}")
                if choice not in opts: R(f"Chọn: {', '.join(opts.keys())}"); return
                votes[uid]=choice
                _exec("UPDATE polls SET votes=? WHERE gid=?",(json.dumps(votes),gid))
                R(f"✅ Đã vote: {choice}")
            elif args[0]=="result" or args[0]=="pollresult":
                pl=_one("SELECT * FROM polls WHERE gid=?",(gid,))
                if not pl: R("Chưa có poll"); return
                opts=json.loads(pl["options"]); votes=json.loads(pl["votes"] or "{}")
                counts={k:0 for k in opts}
                for v in votes.values(): counts[v]=counts.get(v,0)+1
                total=len(votes)
                lines="\n".join(f"{k}. {opts[k]}: {counts.get(k,0)} ({counts.get(k,0)*100//max(total,1)}%)" for k in opts)
                R(f"📊 Kết quả: {pl['question']}\n{lines}\nTổng: {total} vote")
            elif args[0]=="close":
                if p<P_BOT: R("❌ Cần BOT ADMIN"); return
                _exec("UPDATE polls SET closed=1 WHERE gid=?",(gid,)); R("🔒 Đã đóng poll")
            else:
                # tạo poll
                raw2=" ".join(args); parts2=raw2.split("|")
                question=parts2[0].strip(); opts={chr(65+i):o.strip() for i,o in enumerate(parts2[1:])}
                if not opts: R("Cần ít nhất 1 lựa chọn, cách nhau |"); return
                _exec("INSERT OR REPLACE INTO polls(gid,question,options,votes,closed,by_uid) VALUES(?,?,?,?,0,?)",
                    (gid,question,json.dumps(opts),"{}",uid))
                opt_str="\n".join(f"  {k}. {v}" for k,v in opts.items())
                R(f"📊 Poll: {question}\n{opt_str}\nDùng {PREFIX}vote A/B/C để bỏ phiếu")

        # ══ ANTI ═══════════════════════════════════════
        elif cmd=="antispam":
            if p<P_BOT: R("❌ Cần BOT ADMIN"); return
            if args and args[0] in ("on","1"):
                lim=int(args[1]) if len(args)>1 and args[1].isdigit() else 5
                set_grp(gid,"antispam",1); set_grp(gid,"antispam_limit",lim); R(f"✅ Antispam ON (limit {lim})")
            else: set_grp(gid,"antispam",0); R("✅ Antispam OFF")
        elif cmd=="antibadword":
            if p<P_BOT: R("❌ Cần BOT ADMIN"); return
            if not args:
                bw=get_badwords(gid); R(f"🤬 Badwords: {', '.join(bw) if bw else 'Trống'}")
            elif args[0] in ("on","1"):  set_grp(gid,"antibadword",1); R("✅ ON")
            elif args[0] in ("off","0"): set_grp(gid,"antibadword",0); R("✅ OFF")
            elif args[0]=="add":
                for w in args[1:]: add_badword(gid,w)
                R(f"✅ Thêm: {', '.join(args[1:])}")
            elif args[0]=="del":
                for w in args[1:]: del_badword(gid,w)
                R(f"✅ Xoá: {', '.join(args[1:])}")
        elif cmd=="antiurl":
            if p<P_BOT: R("❌"); return
            val=1 if not args or args[0] in ("on","1") else 0
            set_grp(gid,"antiurl",val); R(f"✅ Anti URL {'ON' if val else 'OFF'}")
        elif cmd=="antiforward":
            if p<P_BOT: R("❌"); return
            val=1 if not args or args[0] in ("on","1") else 0
            set_grp(gid,"antiforward",val); R(f"✅ Anti Forward {'ON' if val else 'OFF'}")
        elif cmd=="anticard":
            if p<P_BOT: R("❌"); return
            val=1 if not args or args[0] in ("on","1") else 0
            set_grp(gid,"anticard",val); R(f"✅ Anti Card {'ON' if val else 'OFF'}")
        elif cmd=="antibot":
            if p<P_BOT: R("❌"); return
            val=1 if not args or args[0] in ("on","1") else 0
            set_grp(gid,"antibot",val); R(f"✅ Anti Bot {'ON' if val else 'OFF'}")
        elif cmd=="antiadd":
            if p<P_BOT: R("❌"); return
            val=1 if not args or args[0] in ("on","1") else 0
            set_grp(gid,"antiadd",val); R(f"✅ Anti Add {'ON' if val else 'OFF'}")
        elif cmd=="antistatus":
            if not gid: return
            g3=get_group(gid) if gid else {}; ico=lambda v:"✅" if v else "❌"
            R(f"🛡 Anti Status:\n{ico(g3.get('antispam'))} Spam\n{ico(g3.get('antibadword'))} Badword\n"
              f"{ico(g3.get('antiurl'))} URL\n{ico(g3.get('antiforward'))} Forward\n"
              f"{ico(g3.get('anticard'))} Card\n{ico(g3.get('antibot'))} Bot\n{ico(g3.get('antiadd'))} Add")

        # ══ ECONOMY ════════════════════════════════════
        elif cmd=="money":
            u2=get_user(uid); R(f"💰 Số dư: {u2.get('money',0):,} coins\n📊 Rank: #{self._rank(uid)}")
        elif cmd=="buff":
            if p<P_BOT: R("❌ Cần BOT ADMIN"); return
            if len(args)<2: R(f"Dùng: {PREFIX}buff <uid> <amt>"); return
            t=args[0].lstrip("@"); upsert_user(t); add_money(t,int(args[1]))
            R(f"💸 Buff {int(args[1]):,} → {t}")
        elif cmd=="gift":
            if len(args)<2: R(f"Dùng: {PREFIX}gift <uid> <amt>"); return
            t=args[0].lstrip("@"); amt=int(args[1])
            if get_money(uid)<amt: R("❌ Không đủ tiền"); return
            add_money(uid,-amt); upsert_user(t); add_money(t,amt)
            _exec("INSERT INTO transactions(from_uid,to_uid,amount,note) VALUES(?,?,?,?)",(uid,t,amt,"gift"))
            R(f"🎁 Tặng {amt:,} → {t}\n💰 Còn lại: {get_money(uid):,}")
        elif cmd=="checkin":
            bonus,streak=do_checkin(uid,gid or "global")
            if bonus is None: R("✅ Hôm nay đã điểm danh rồi!")
            else: R(f"📅 Điểm danh!\n+{bonus:,} coins (streak {streak} ngày)\n💰 Tổng: {get_money(uid):,}")
        elif cmd=="shop":
            if not args:
                items=_all("SELECT * FROM shop")
                R("🛒 Cửa hàng:\n"+"\n".join(f"[{i['id']}] {i['name']} — {i['price']:,}💰\n   {i['desc']}" for i in items))
            elif args[0]=="buy":
                if len(args)<2: R(f"Dùng: {PREFIX}shop buy <id>"); return
                item=_one("SELECT * FROM shop WHERE id=?",(int(args[1]),))
                if not item: R("❌ Không tìm thấy"); return
                if get_money(uid)<item["price"]: R("❌ Không đủ tiền"); return
                add_money(uid,-item["price"])
                inv=_one("SELECT qty FROM inventory WHERE uid=? AND item_id=?",(uid,item["id"]))
                if inv: _exec("UPDATE inventory SET qty=qty+1 WHERE uid=? AND item_id=?",(uid,item["id"]))
                else: _exec("INSERT INTO inventory(uid,item_id) VALUES(?,?)",(uid,item["id"]))
                # apply effect
                eff=item["effect"]
                if eff.startswith("hp+"): _exec("UPDATE users SET hp=hp+? WHERE uid=?",(int(eff[3:]),uid)); R(f"💊 Mua {item['name']}! +{eff[3:]} HP")
                elif eff.startswith("atk+"): _exec("UPDATE users SET atk=atk+? WHERE uid=?",(int(eff[4:]),uid)); R(f"⚔️ Mua {item['name']}! +{eff[4:]} ATK")
                else: R(f"🛒 Mua {item['name']}! -{item['price']:,}💰")
            elif args[0]=="inv":
                inv=_all("SELECT i.name,v.qty FROM inventory v JOIN shop i ON v.item_id=i.id WHERE v.uid=?",(uid,))
                R("🎒 Túi đồ:\n"+"\n".join(f"• {r['name']} x{r['qty']}" for r in inv) if inv else "Túi trống")
        elif cmd=="rain":
            if not gid: R("❌ Chỉ dùng trong nhóm"); return
            if not args: R(f"Dùng: {PREFIX}rain <tổng tiền>"); return
            total_rain=int(args[0])
            if get_money(uid)<total_rain: R("❌ Không đủ tiền"); return
            members=_all("SELECT uid FROM users WHERE uid!=? ORDER BY RANDOM() LIMIT 10",(uid,))
            if not members: R("❌ Không đủ người"); return
            per=total_rain//len(members); add_money(uid,-total_rain)
            names=[]
            for m2 in members:
                add_money(m2["uid"],per); names.append(m2["uid"][:8])
            R(f"🌧 Rải tiền! {total_rain:,} cho {len(members)} người\n+{per:,}/người\n{', '.join(names)}")
        elif cmd=="rich":
            top=_all("SELECT uid,name,money FROM users ORDER BY money DESC LIMIT 10")
            R("🏆 Top giàu:\n"+"\n".join(f"#{i+1} {r.get('name') or r['uid'][:10]}: {r['money']:,}💰" for i,r in enumerate(top)))

        # ══ GAMES ══════════════════════════════════════
        elif cmd=="taixiu":
            if not gid: R("❌ Chỉ chơi trong nhóm"); return
            if len(args)<2: R(f"Dùng: {PREFIX}taixiu tai/xiu <tiền>"); return
            bet="tai" if args[0].lower() in ("tai","tài") else "xiu"
            try: amt=int(args[1])
            except: R("❌ Số tiền không hợp lệ"); return
            if amt<=0: R("❌ Tiền phải > 0"); return
            if get_money(uid)<amt: R("❌ Không đủ tiền"); return
            dice=[random.randint(1,6) for _ in range(3)]
            total=sum(dice); result="tai" if total>=11 else "xiu"; win=bet==result
            add_money(uid,amt if win else -amt)
            R(f"🎲 {'·'.join(str(d) for d in dice)} = {total}\n"
              f"{'TÀI ≥11' if result=='tai' else 'XỈU ≤10'} | {'🎉 +'+str(amt) if win else '😢 -'+str(amt)} coins\n💰 {get_money(uid):,}")

        elif cmd=="baucua":
            amap={"cua":"🦀","tom":"🦐","tôm":"🦐","ca":"🐟","cá":"🐟","nai":"🦌","bau":"🏺","bầu":"🏺","ga":"🐓","gà":"🐓"}
            anames={"🦀":"Cua","🦐":"Tôm","🐟":"Cá","🦌":"Nai","🏺":"Bầu","🐓":"Gà"}
            if len(args)<2: R(f"🎮 {PREFIX}baucua <cua|tom|ca|nai|bau|ga> <tiền>"); return
            pick=args[0].lower()
            if pick not in amap: R("❌ Chọn: cua tom ca nai bau ga"); return
            try: amt=int(args[1])
            except: R("❌ Số tiền không hợp lệ"); return
            if get_money(uid)<amt: R("❌ Không đủ tiền"); return
            all_animals=list(anames.keys())
            rolled=[random.choice(all_animals) for _ in range(3)]
            picked=amap[pick]; cnt=rolled.count(picked)
            if cnt>0: add_money(uid,amt*cnt); R(f"🎲 {' '.join(rolled)}\n✅ {anames[picked]} ×{cnt} → +{amt*cnt:,}\n💰 {get_money(uid):,}")
            else: add_money(uid,-amt); R(f"🎲 {' '.join(rolled)}\n❌ Không có {anames[picked]} → -{amt:,}\n💰 {get_money(uid):,}")

        elif cmd=="poker":
            suits=["♠","♥","♦","♣"]; values=["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
            deck=[f"{v}{s}" for v in values for s in suits]
            random.shuffle(deck)
            hand=deck[:5]; dealer=deck[5:10]
            R(f"🃏 Poker\n👤 Bạn: {' '.join(hand)}\n🤖 Dealer: {'?' * 5}\nDùng {PREFIX}taixiu nếu muốn đặt cược.")

        elif cmd=="masoi":
            if not gid: R("❌ Chỉ chơi trong nhóm"); return
            if not args: R(f"🐺 Ma Sói\n{PREFIX}masoi start|join|begin|end"); return
            act=args[0].lower()
            if act=="start":
                _exec("INSERT OR REPLACE INTO game_sessions VALUES(?,?,?,?,?)",
                    (gid,"masoi",json.dumps({"players":[uid],"phase":"lobby"}),uid,time.time()))
                R(f"🐺 Phòng Ma Sói tạo xong!\n{PREFIX}masoi join để vào ({PREFIX}masoi begin khi đủ ≥4)")
            elif act=="join":
                r2=_one("SELECT data FROM game_sessions WHERE gid=? AND game=?",(gid,"masoi"))
                if not r2: R("Chưa có phòng"); return
                data2=json.loads(r2["data"])
                if uid not in data2["players"]: data2["players"].append(uid)
                _exec("UPDATE game_sessions SET data=? WHERE gid=? AND game=?",(json.dumps(data2),gid,"masoi"))
                R(f"✅ Vào phòng! ({len(data2['players'])} người)")
            elif act=="begin":
                r2=_one("SELECT data,host FROM game_sessions WHERE gid=? AND game=?",(gid,"masoi"))
                if not r2: R("Chưa có phòng"); return
                if r2["host"]!=uid: R("Chỉ host mới bắt đầu"); return
                data2=json.loads(r2["data"]); players=data2["players"]
                if len(players)<4: R("Cần ≥4 người"); return
                n_wolf=max(1,len(players)//4)
                roles=["🐺 Ma Sói"]*n_wolf+["👨‍🌾 Dân Làng"]*(len(players)-n_wolf)
                random.shuffle(roles)
                for pp,role in zip(players,roles):
                    try: self._send(f"🎭 Vai của bạn:\n{role}",pp,ThreadType.USER)
                    except: pass
                R(f"🐺 Game bắt đầu! {len(players)} người\n{n_wolf} Ma Sói 🐺 | {len(players)-n_wolf} Dân Làng 👨‍🌾")
                _exec("DELETE FROM game_sessions WHERE gid=? AND game=?",(gid,"masoi"))
            elif act=="end":
                if p<P_BOT: R("❌ Cần BOT ADMIN"); return
                _exec("DELETE FROM game_sessions WHERE gid=? AND game=?",(gid,"masoi"))
                R("🏁 Kết thúc game Ma Sói")

        elif cmd=="tutien":
            u2=get_user(uid); exp=u2.get("exp",0)
            levels=["Phàm Nhân","Luyện Khí","Trúc Cơ","Kim Đan","Nguyên Anh","Hóa Thần","Luyện Hư","Hợp Thể","Đại Thừa","Độ Kiếp"]
            lv=min(exp//1000,len(levels)-1); gain=random.randint(10,80)
            _exec("UPDATE users SET exp=exp+? WHERE uid=?",(gain,uid))
            R(f"🏔 Tu Tiên — {levels[lv]}\n修为: {exp}→{exp+gain}/{(lv+1)*1000}\n+{gain} tu vi")

        elif cmd=="pet":
            pet=_one("SELECT * FROM pets WHERE uid=?",(uid,))
            if not args or args[0]=="info":
                if not pet: R(f"🐾 Chưa có pet!\n{PREFIX}pet tao <tên> <loại(cho/meo/ran/rong)>"); return
                hungry=pet.get("hunger",100); hungy_str="😋 No" if hungry>60 else "😕 Đói" if hungry>20 else "😨 Rất đói"
                R(f"🐾 {pet['name']} [{pet['type']}] Lv.{pet['level']}\n❤️ HP:{pet['hp']} ⚔️ ATK:{pet['atk']}\n📊 EXP:{pet['exp']}/100 {hungy_str}")
            elif args[0]=="tao" and len(args)>=3:
                _exec("INSERT OR REPLACE INTO pets(uid,name,type) VALUES(?,?,?)",(uid,args[1],args[2]))
                R(f"🎉 Tạo pet {args[1]} [{args[2]}]!")
            elif args[0]=="train":
                if not pet: R("Chưa có pet"); return
                gain=random.randint(10,50)
                new_exp=pet["exp"]+gain; levelup=new_exp>=100
                _exec("UPDATE pets SET exp=?,atk=atk+1,level=level+? WHERE uid=?",(new_exp%100 if levelup else new_exp,1 if levelup else 0,uid))
                R(f"💪 +{gain} EXP, +1 ATK{' | LEVEL UP! 🎉' if levelup else ''}")
            elif args[0]=="feed":
                if not pet: R("Chưa có pet"); return
                _exec("UPDATE pets SET hunger=MIN(100,hunger+50),last_feed=? WHERE uid=?",(time.time(),uid))
                R(f"🍖 Cho {pet['name']} ăn! +50 Hunger")
            elif args[0]=="battle" and len(args)>1:
                if not pet: R("Chưa có pet"); return
                target=args[1].lstrip("@")
                enemy=_one("SELECT * FROM pets WHERE uid=?",(target,))
                if not enemy: R(f"❌ {target} chưa có pet"); return
                my_power=pet["atk"]+random.randint(1,10)
                en_power=enemy["atk"]+random.randint(1,10)
                win=my_power>en_power; reward=random.randint(50,200)
                if win: add_money(uid,reward)
                R(f"⚔️ Pet Battle!\n🐾 {pet['name']}({my_power}) vs {enemy['name']}({en_power})\n{'🏆 Thắng! +'+str(reward)+'💰' if win else '💀 Thua...'}")

        elif cmd=="life":
            events=[("💼 Đi làm",200),("🎰 Trúng số",500),("🏥 Viện phí",-300),
                    ("🛒 Mua sắm",-150),("💡 Tiết kiệm",100),("🤝 Giúp đỡ",300),
                    ("🎮 Thua game",-200),("📈 Đầu tư lời",800),("🔥 Cháy nhà",-500),
                    ("🎁 Quà bất ngờ",400)]
            ev,money=random.choice(events); add_money(uid,money)
            R(f"🌍 {ev}\n{'+' if money>0 else ''}{money:,} coins\n💰 {get_money(uid):,}")

        elif cmd=="htht":
            islands=["Đảo Skull","Vương Quốc Rỗng","Biển Đông","Đảo Báu","Grand Line","Đảo Bánh Báo"]
            enemies=["Hải Quân","Cướp Biển","Quái Vật","Lính Thủy","Thuyền Trưởng Địch"]
            win=random.random()>0.4; reward=random.randint(100,1000)
            if win: add_money(uid,reward)
            else: add_money(uid,-reward//2)
            R(f"⚓ {random.choice(islands)} — {random.choice(enemies)}\n"
              f"{'🏆 Thắng +'+str(reward) if win else '💀 Thua -'+str(reward//2)} coins\n💰 {get_money(uid):,}")

        elif cmd=="warcard":
            if not args: R(f"Dùng: {PREFIX}warcard @uid"); return
            target=args[0].lstrip("@")
            my_p=random.randint(50,100); en_p=random.randint(50,100)
            win=my_p>en_p; reward=random.randint(100,500)
            if win: add_money(uid,reward); add_money(target,-reward//2)
            else: add_money(uid,-reward//2); add_money(target,reward//2)
            R(f"⚔️ WAR CARD\n{uid[:10]}({my_p}) vs {target[:10]}({en_p})\n{'🏆 Thắng! +'+str(reward) if win else '💀 Thua! -'+str(reward//2)} coins")

        # ══ FUN ════════════════════════════════════════
        elif cmd=="cute":
            s=random.randint(1,100); R(f"🌸 Cute: {s}/100\n{'💕 Siêu dễ thương!' if s>80 else '😊 Khá cute' if s>50 else '😄 Cần cố thêm'}")
        elif cmd=="dam":
            s=random.randint(1,100); R(f"😈 Dam: {s}/100\n{'😳 Rất rất... dam' if s>80 else '😐 Bình thường' if s>40 else '😇 Trong sáng'}")
        elif cmd=="gay":
            s=random.randint(0,100); R(f"🌈 Gay: {s}%\n{'🏳️‍🌈 Rất rất rất...' if s>80 else '😄 Bình thường' if s>40 else '😎 Straight 100%'}")
        elif cmd=="les":
            s=random.randint(0,100); R(f"💜 Les: {s}%\n{'💕 Chị chị em em' if s>70 else '😄 Bình thường'}")
        elif cmd=="love":
            poems=["Yêu em từ cái nhìn đầu tiên,\nMắt em như trăng soi trên biển.",
                   "Tình yêu như ánh nắng ban mai,\nSưởi ấm lòng ta mỗi sớm ngày.",
                   "Em là bến đỗ của cuộc đời,\nNơi ta tìm về mỗi cuối ngày.",
                   "Nhắm mắt lại chỉ thấy dáng em,\nMở mắt ra cũng vẫn chỉ thấy em."]
            target=" ".join(args) if args else "bạn ơi"
            R(f"💌 Tỏ tình với {target}\n\n{random.choice(poems)}\n\n— {OWNER_NAME} Bot 💕")
        elif cmd=="altp":
            R(random.choice(["Tôi là Triệu Phú! 💸","Tiền mua được tất cả, trừ... à không, mua được hết 😂",
                              "Hôm nay chọn bạo lực với ví tiền 💀","Born to flex, forced to work 😤"]))
        elif cmd=="meme": R("😂 Tìm meme: đang phát triển.")
        elif cmd=="image": R("🖼 Xử lý ảnh: đang phát triển.")
        elif cmd=="sticker": R("🎨 Tạo sticker: đang phát triển.")
        elif cmd=="voice": R("🎙 TTS: đang phát triển.")
        elif cmd=="vtxt": R("🎵➡️📝 Voice-to-text: đang phát triển.")

        # ══ MEDIA ══════════════════════════════════════
        elif cmd=="tiktok":
            if not args: R(f"Dùng: {PREFIX}tiktok <link>"); return
            try:
                r=requests.get(f"https://tikwm.com/api/?url={args[0]}",timeout=12)
                d=r.json()
                if d.get("code")==0: R(f"🎵 TikTok\n▶️ {d['data']['play']}\n🎵 {d['data'].get('music','N/A')}")
                else: R("❌ Không tải được")
            except: R("❌ Lỗi")
        elif cmd=="download":
            if not args: R(f"Dùng: {PREFIX}download <link>"); return
            try:
                r=requests.get(f"https://tikwm.com/api/?url={args[0]}",timeout=12)
                d=r.json()
                if d.get("code")==0: R(f"📥 Video: {d['data']['play']}\n🎵 Audio: {d['data'].get('music','N/A')}")
                else: R("❌ Không tải được")
            except: R("❌ Lỗi")
        elif cmd in ("bufffl","bufftim","buffview"):
            buff_map={"bufffl":"Follow","bufftim":"Tim","buffview":"View"}
            if not args: R(f"Dùng: {PREFIX}{cmd} <link>"); return
            R(f"📈 TikTok {buff_map[cmd]}: {args[0]}\n⚠️ Cần cấu hình Buff API — liên hệ {OWNER_NAME}")
        elif cmd=="ttinfo":
            if not args: R(f"Dùng: {PREFIX}ttinfo <user>"); return
            R(f"📊 TikTok: @{args[0]}\n🔗 https://www.tiktok.com/@{args[0]}")
        elif cmd=="ttuser":
            if not args: R(f"Dùng: {PREFIX}ttuser <user>"); return
            R(f"👤 @{args[0]}\n🔗 https://www.tiktok.com/@{args[0]}")
        elif cmd=="capcut":
            if not args: R(f"Dùng: {PREFIX}capcut <từ khóa>"); return
            kw=" ".join(args)
            R(f"🎬 CapCut: {kw}\n🔗 https://www.capcut.com/search?q={requests.utils.quote(kw)}")
        elif cmd=="pinterest":
            if not args: R(f"Dùng: {PREFIX}pinterest <từ khóa>"); return
            kw=" ".join(args)
            R(f"📌 Pinterest: {kw}\n🔗 https://www.pinterest.com/search/pins/?q={requests.utils.quote(kw)}")
        elif cmd in ("zing","nhaccuatui","audiomack","soundcloud","autosend"):
            src={"zing":"ZingMP3","nhaccuatui":"NhacCuaTui","audiomack":"Audiomack","soundcloud":"SoundCloud","autosend":"AutoSend"}[cmd]
            if not args: R(f"Dùng: {PREFIX}{cmd} <tên bài>"); return
            R(f"🎵 {src}: {' '.join(args)}\n(Đang phát triển)")

        # ══ AI ═════════════════════════════════════════
        elif cmd in ("gpt","gem"):
            if not args: R(f"Dùng: {PREFIX}{cmd} <câu hỏi>"); return
            question=" ".join(args)
            if cmd=="gpt":
                if not OPENAI_KEY: R("⚠️ Chưa cấu hình OPENAI_KEY"); return
                try:
                    r=requests.post("https://api.openai.com/v1/chat/completions",
                        headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},
                        json={"model":"gpt-3.5-turbo","messages":[{"role":"user","content":question}]},timeout=25)
                    R(f"🤖 GPT:\n{r.json()['choices'][0]['message']['content']}")
                except Exception as e: R(f"❌ GPT: {e}")
            else:
                if not GEMINI_KEY: R("⚠️ Chưa cấu hình GEMINI_KEY"); return
                try:
                    r=requests.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}",
                        json={"contents":[{"parts":[{"text":question}]}]},timeout=25)
                    R(f"💎 Gemini:\n{r.json()['candidates'][0]['content']['parts'][0]['text']}")
                except Exception as e: R(f"❌ Gemini: {e}")

        else:
            R(f"❓ Lệnh `{PREFIX}{cmd}` không tồn tại\nDùng {PREFIX}menu để xem danh sách")

    def _rank(self,uid):
        rows=_all("SELECT uid FROM users ORDER BY money DESC")
        for i,r in enumerate(rows):
            if r["uid"]==uid: return i+1
        return 999

    def _menu(self):
        return (
            f"╔══════════════════════════╗\n"
            f"║  🤖 {BOT_NAME}\n"
            f"║  👑 Owner: {OWNER_NAME}\n"
            f"║  v{VERSION} — prefix: {PREFIX}\n"
            f"╠══════════════════════════╣\n"
            f"║ 📋 INFO\n"
            f"║ menu info ping uid check\n"
            f"║ cpu uptcard ffid lich alys\n"
            f"╠══════════════════════════╣\n"
            f"║ 👑 ADMIN\n"
            f"║ admin acl key-as bot baotri\n"
            f"║ restart alias prefix stg\n"
            f"║ manager warn clearwarn warns\n"
            f"╠══════════════════════════╣\n"
            f"║ 🛡 ANTI\n"
            f"║ antispam antibadword antiurl\n"
            f"║ antiforward anticard antibot\n"
            f"║ antiadd antistatus\n"
            f"╠══════════════════════════╣\n"
            f"║ 🔨 MOD\n"
            f"║ kick block silent dmsg wc\n"
            f"║ event pr treo ckg spm\n"
            f"║ approve note poll\n"
            f"╠══════════════════════════╣\n"
            f"║ 💰 ECONOMY\n"
            f"║ money buff gift checkin\n"
            f"║ shop rain rich encode translate\n"
            f"╠══════════════════════════╣\n"
            f"║ 🎮 GAME\n"
            f"║ taixiu baucua masoi poker\n"
            f"║ tutien pet life htht warcard\n"
            f"╠══════════════════════════╣\n"
            f"║ 😂 FUN\n"
            f"║ cute dam gay les love altp\n"
            f"║ meme sticker image voice\n"
            f"╠══════════════════════════╣\n"
            f"║ 🎵 MEDIA\n"
            f"║ tiktok download capcut\n"
            f"║ pinterest zing bufffl\n"
            f"║ bufftim buffview ttinfo\n"
            f"╠══════════════════════════╣\n"
            f"║ 🤖 AI\n"
            f"║ gpt gem translate\n"
            f"╚══════════════════════════╝"
        )

# ═══════════════════════════════════════════════════════════════════
#  BACKGROUND THREADS
# ═══════════════════════════════════════════════════════════════════
def run_scheduler(bot):
    while True:
        try:
            rows=_all("SELECT * FROM scheduled WHERE sent=0 AND send_at<=?",(time.time(),))
            for row in rows:
                try:
                    bot._send(row["msg"],row["gid"],GroupType.GROUP)
                    if row.get("repeat_sec",0):
                        _exec("UPDATE scheduled SET send_at=? WHERE id=?",(time.time()+row["repeat_sec"],row["id"]))
                    else:
                        _exec("UPDATE scheduled SET sent=1 WHERE id=?",(row["id"],))
                except: pass
        except: pass
        time.sleep(5)

# ═══════════════════════════════════════════════════════════════════
#  FLASK
# ═══════════════════════════════════════════════════════════════════
flask_app=Flask(__name__)

@flask_app.route("/")
def index():
    uptime=int(time.time()-BOT_START)
    return jsonify({"status":"online","bot":BOT_NAME,"version":VERSION,
                    "owner":OWNER_NAME,"uptime":uptime,"zalo":_zalo_live})

@flask_app.route("/health")
def health(): return jsonify({"ok":True,"ts":time.time()})

@flask_app.route("/qr")
def show_qr():
    if os.path.exists("qr.png"): return send_file("qr.png",mimetype="image/png")
    return "QR chưa sẵn sàng",404

@flask_app.route("/stats")
def api_stats():
    return jsonify({
        "users":    (_one("SELECT COUNT(*) cnt FROM users") or {}).get("cnt",0),
        "groups":   (_one("SELECT COUNT(*) cnt FROM groups") or {}).get("cnt",0),
        "messages": (_one("SELECT COUNT(*) cnt FROM msg_log") or {}).get("cnt",0),
    })

def run_flask():
    flask_app.run(host="0.0.0.0",port=PORT,debug=False,use_reloader=False)

# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════
def _do_qr_login(bot):
    """Lấy QR, gửi Telegram, chờ quét — chạy trong thread riêng."""
    global _zalo_live
    print("[INFO] Lấy QR...")
    tele_text(f"🔑 <b>{BOT_NAME}</b> cần đăng nhập...\n📱 Đang lấy QR")
    try:
        import qrcode as qrc
        qr_data = bot.getQRCodeLogin()
        qr_url  = qr_data["data"]["qr_url"]
        img = qrc.make(qr_url)
        img.save("qr.png")
        print(f"[INFO] QR saved — http://0.0.0.0:{PORT}/qr")
        res = tele_photo(
            "qr.png",
            f"📱 <b>Quét QR để đăng nhập Zalo</b>\n"
            f"⏳ Hiệu lực ~2 phút\n"
            f"🌐 Hoặc xem: <code>your-render-url/qr</code>"
        )
        if res and res.get("ok"):
            _qr_msg_ids.append(res["result"]["message_id"])
    except Exception as e:
        print(f"[ERR] QR: {e}")
        tele_text(f"❌ Lỗi lấy QR: {e}\nThử /qr trên Telegram để lấy lại.")
        return

    # Chờ quét — poll trạng thái login mỗi 3 giây
    deadline = time.time() + 180  # 3 phút
    while time.time() < deadline:
        try:
            status = bot.getLoginStatus()
            code = status.get("data", {}).get("code", -1)
            if code == 1:  # logged in
                imei_val    = bot.imei
                cookies_val = bot.cookies
                os.makedirs("data", exist_ok=True)
                json.dump({"imei": imei_val, "cookies": cookies_val},
                          open(SESSION_PATH, "w"))
                print("[INFO] Session saved!")
                _zalo_live = True
                for mid in _qr_msg_ids:
                    tele_delete(mid)
                _qr_msg_ids.clear()
                tele_text(
                    f"✅ <b>Đăng nhập thành công!</b>\n"
                    f"🤖 {BOT_NAME} v{VERSION} đang chạy\n"
                    f"👑 {OWNER_NAME}",
                    reply_markup=kb_main()
                )
                return
        except Exception as e:
            print(f"[WARN] login poll: {e}")
        time.sleep(3)

    tele_text("⏰ QR hết hạn. Dùng /qr trên Telegram để lấy QR mới.")


def main():
    global _zalo_live
    os.makedirs("data", exist_ok=True)

    # 1. Khởi động Flask (để Render không báo lỗi port)
    threading.Thread(target=run_flask, daemon=True).start()
    print(f"[INFO] Flask ::{PORT}")
    time.sleep(2)

    # 2. Đọc danh sách tài khoản từ file accounts.json
    accounts = []
    if os.path.exists("accounts.json"):
        try:
            accounts = json.load(open("accounts.json"))
        except:
            print("[WARN] Lỗi đọc accounts.json, dùng mặc định 1 tài khoản.")
            accounts = [{"name": "main"}]
    else:
        accounts = [{"name": "main"}]

    bots = []

    # 3. Khởi tạo và đăng nhập từng tài khoản bằng QR
    for acc in accounts:
        acc_name = acc.get("name", "bot")
        session_file = f"data/session_{acc_name}.json"
        
        imei, cookies = None, None
        if os.path.exists(session_file):
            try:
                sess = json.load(open(session_file))
                imei = sess.get("imei")
                cookies = sess.get("cookies")
                print(f"[INFO] Đã load session cho {acc_name}")
            except Exception as e:
                print(f"[WARN] Lỗi load session {acc_name}: {e}")

        # Khởi tạo bot
        bot = LENhanBot(imei or "", cookies or "")
        
        # Nếu chưa có session, gọi hàm lấy QR
        if not (imei and cookies):
            print(f"[INFO] Chưa có session cho {acc_name}, đang lấy QR...")
            threading.Thread(target=_do_qr_login, args=(bot,), daemon=True).start()
        else:
            # Nếu đã có session, chạy listen luôn
            print(f"[INFO] Đang chạy {acc_name} bằng session...")
            threading.Thread(target=bot.listen, daemon=True).start()
            _zalo_live = True
            
        bots.append(bot)

    # 4. Chạy các luồng nền (Telegram, Scheduler, Dashboard)
    if bots:
        threading.Thread(target=run_scheduler, args=(bots[0],), daemon=True).start()
        threading.Thread(target=tele_poll, args=(bots[0],), daemon=True).start()
        threading.Thread(target=dash_refresh, daemon=True).start()

    # 5. Giữ cho process luôn sống
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
