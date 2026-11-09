# language: Python 3.11+, file: bot.py
# Bot Make By Le Nhan — Zalo Group Bot
# Owner: Huynh Le Nhan
# Prefix: ?
# Deploy: Render (Flask keep-alive included)

import os, sys, json, time, sqlite3, re, threading, random, hashlib
import requests
from flask import Flask, jsonify, send_file
from zlapi import ZaloAPI
from zlapi.models import *

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════
PREFIX       = "?"
BOT_NAME     = "Bot Make By Le Nhan"
OWNER_NAME   = "Huynh Le Nhan"
OWNER_IDS    = []           # điền UID Zalo của Huynh Le Nhan
DB_PATH      = "data/bot.db"
SESSION_PATH = "data/session.json"
PORT         = int(os.environ.get("PORT", 10000))

OPENAI_KEY   = os.environ.get("OPENAI_KEY", "")
GEMINI_KEY   = os.environ.get("GEMINI_KEY", "")

# Telegram — gửi QR khi khởi động
TELE_TOKEN   = os.environ.get("TELE_TOKEN", "")   # token từ @BotFather
TELE_CHAT_ID = os.environ.get("TELE_CHAT_ID", "") # chat_id của dj (dùng @userinfobot để lấy)

def tele_send_text(text):
    """Gửi text qua Telegram."""
    if not TELE_TOKEN or not TELE_CHAT_ID: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage",
            json={"chat_id": TELE_CHAT_ID, "text": text},
            timeout=10
        )
    except Exception as e:
        print(f"[TELE] send_text lỗi: {e}")

def tele_send_photo(path, caption=""):
    """Gửi ảnh QR qua Telegram."""
    if not TELE_TOKEN or not TELE_CHAT_ID: return
    try:
        with open(path, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{TELE_TOKEN}/sendPhoto",
                data={"chat_id": TELE_CHAT_ID, "caption": caption},
                files={"photo": f},
                timeout=15
            )
        print("[TELE] Đã gửi QR qua Telegram")
    except Exception as e:
        print(f"[TELE] send_photo lỗi: {e}")

# Permission tiers
P_USR       = 0
P_GRP_ADMIN = 1
P_BOT_ADMIN = 2
P_HI_ADMIN  = 3
P_DEV       = 99

# ═══════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════
os.makedirs("data", exist_ok=True)

def db():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        uid TEXT PRIMARY KEY, name TEXT,
        perm INTEGER DEFAULT 0, money INTEGER DEFAULT 500,
        exp INTEGER DEFAULT 0, blocked INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS groups(
        gid TEXT PRIMARY KEY, name TEXT, prefix TEXT DEFAULT '?',
        bot_on INTEGER DEFAULT 1, welcome INTEGER DEFAULT 0,
        welcome_msg TEXT DEFAULT 'Chào {name} đến với nhóm!',
        antispam INTEGER DEFAULT 0, antispam_limit INTEGER DEFAULT 5,
        antibadword INTEGER DEFAULT 0, antiurl INTEGER DEFAULT 0,
        antiforward INTEGER DEFAULT 0, anticard INTEGER DEFAULT 0,
        antibot INTEGER DEFAULT 0, antiadd INTEGER DEFAULT 0,
        event_notify INTEGER DEFAULT 1, pr_on INTEGER DEFAULT 0,
        pr_msg TEXT DEFAULT '', silent_all INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS badwords(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gid TEXT, word TEXT, UNIQUE(gid,word)
    );
    CREATE TABLE IF NOT EXISTS silenced(uid TEXT, gid TEXT, PRIMARY KEY(uid,gid));
    CREATE TABLE IF NOT EXISTS bot_admins(uid TEXT, gid TEXT, PRIMARY KEY(uid,gid));
    CREATE TABLE IF NOT EXISTS spam_track(
        uid TEXT, gid TEXT, count INTEGER DEFAULT 0,
        last_time REAL DEFAULT 0, PRIMARY KEY(uid,gid)
    );
    CREATE TABLE IF NOT EXISTS aliases(
        gid TEXT, alias TEXT, cmd TEXT, PRIMARY KEY(gid,alias)
    );
    CREATE TABLE IF NOT EXISTS scheduled(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gid TEXT, uid TEXT, msg TEXT, send_at REAL, sent INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_uid TEXT, to_uid TEXT, amount INTEGER,
        note TEXT, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS msg_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uid TEXT, gid TEXT, msg TEXT,
        ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS pets(
        uid TEXT PRIMARY KEY, name TEXT, type TEXT,
        hp INTEGER DEFAULT 100, atk INTEGER DEFAULT 10,
        level INTEGER DEFAULT 1, exp INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS game_sessions(
        gid TEXT PRIMARY KEY, game TEXT, data TEXT, host TEXT
    );
    CREATE TABLE IF NOT EXISTS taixiu_bets(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gid TEXT, uid TEXT, bet TEXT, amount INTEGER, round_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS baucua_bets(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gid TEXT, uid TEXT, animal TEXT, amount INTEGER, round_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS taixiu_round(gid TEXT PRIMARY KEY, round_id INTEGER DEFAULT 0, open INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS baucua_round(gid TEXT PRIMARY KEY, round_id INTEGER DEFAULT 0, open INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS acl(
        gid TEXT, uid TEXT, allowed_cmds TEXT,
        denied_cmds TEXT, PRIMARY KEY(gid,uid)
    );
    CREATE TABLE IF NOT EXISTS pr_schedule(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gid TEXT, interval_sec INTEGER,
        last_sent REAL DEFAULT 0
    );
    """)
    c.commit(); c.close()

init_db()

# ─── DB helpers ───────────────────────────────────────────────
def upsert_user(uid, name=None):
    c = db()
    c.execute("INSERT OR IGNORE INTO users(uid,name) VALUES(?,?)", (uid, name))
    if name:
        c.execute("UPDATE users SET name=? WHERE uid=?", (name, uid))
    c.commit(); c.close()

def get_user(uid):
    c = db(); r = c.execute("SELECT * FROM users WHERE uid=?", (uid,)).fetchone(); c.close()
    return dict(r) if r else {"uid": uid, "perm": 0, "money": 0, "blocked": 0}

def set_perm(uid, p):
    c = db(); c.execute("UPDATE users SET perm=? WHERE uid=?", (p, uid)); c.commit(); c.close()

def get_money(uid):
    c = db(); r = c.execute("SELECT money FROM users WHERE uid=?", (uid,)).fetchone(); c.close()
    return r["money"] if r else 0

def add_money(uid, amt):
    c = db(); c.execute("UPDATE users SET money=money+? WHERE uid=?", (amt, uid)); c.commit(); c.close()

def upsert_group(gid, name=None):
    c = db()
    c.execute("INSERT OR IGNORE INTO groups(gid,name) VALUES(?,?)", (gid, name))
    if name: c.execute("UPDATE groups SET name=? WHERE gid=?", (name, gid))
    c.commit(); c.close()

def get_group(gid):
    c = db(); r = c.execute("SELECT * FROM groups WHERE gid=?", (gid,)).fetchone(); c.close()
    return dict(r) if r else {}

def set_grp(gid, field, val):
    c = db(); c.execute(f"UPDATE groups SET {field}=? WHERE gid=?", (val, gid)); c.commit(); c.close()

def get_grp(gid, field):
    g = get_group(gid); return g.get(field)

def is_bot_admin(uid, gid):
    c = db(); r = c.execute("SELECT 1 FROM bot_admins WHERE uid=? AND gid=?", (uid, gid)).fetchone(); c.close()
    return bool(r)

def set_bot_admin(uid, gid, v):
    c = db()
    if v: c.execute("INSERT OR IGNORE INTO bot_admins(uid,gid) VALUES(?,?)", (uid, gid))
    else: c.execute("DELETE FROM bot_admins WHERE uid=? AND gid=?", (uid, gid))
    c.commit(); c.close()

def is_silenced(uid, gid):
    c = db(); r = c.execute("SELECT 1 FROM silenced WHERE uid=? AND gid=?", (uid, gid)).fetchone(); c.close()
    return bool(r)

def set_silent(uid, gid, v):
    c = db()
    if v: c.execute("INSERT OR IGNORE INTO silenced(uid,gid) VALUES(?,?)", (uid, gid))
    else: c.execute("DELETE FROM silenced WHERE uid=? AND gid=?", (uid, gid))
    c.commit(); c.close()

def get_badwords(gid):
    c = db(); rows = c.execute("SELECT word FROM badwords WHERE gid=?", (gid,)).fetchall(); c.close()
    return [r["word"] for r in rows]

def add_badword(gid, word):
    c = db(); c.execute("INSERT OR IGNORE INTO badwords(gid,word) VALUES(?,?)", (gid, word.lower())); c.commit(); c.close()

def del_badword(gid, word):
    c = db(); c.execute("DELETE FROM badwords WHERE gid=? AND word=?", (gid, word.lower())); c.commit(); c.close()

def get_alias(gid, a):
    c = db(); r = c.execute("SELECT cmd FROM aliases WHERE gid=? AND alias=?", (gid, a)).fetchone(); c.close()
    return r["cmd"] if r else None

def set_alias(gid, a, cmd):
    c = db(); c.execute("INSERT OR REPLACE INTO aliases(gid,alias,cmd) VALUES(?,?,?)", (gid, a, cmd)); c.commit(); c.close()

def del_alias(gid, a):
    c = db(); c.execute("DELETE FROM aliases WHERE gid=? AND alias=?", (gid, a)); c.commit(); c.close()

def list_aliases(gid):
    c = db(); rows = c.execute("SELECT alias,cmd FROM aliases WHERE gid=?", (gid,)).fetchall(); c.close()
    return [(r["alias"], r["cmd"]) for r in rows]

def log_msg(uid, gid, msg):
    c = db(); c.execute("INSERT INTO msg_log(uid,gid,msg) VALUES(?,?,?)", (uid, gid, msg)); c.commit(); c.close()

def top_senders(gid, n=10):
    c = db()
    rows = c.execute("SELECT uid,COUNT(*) cnt FROM msg_log WHERE gid=? GROUP BY uid ORDER BY cnt DESC LIMIT ?", (gid, n)).fetchall()
    c.close(); return [(r["uid"], r["cnt"]) for r in rows]

# spam tracking
def track_spam(uid, gid, limit):
    c = db(); now = time.time()
    r = c.execute("SELECT count,last_time FROM spam_track WHERE uid=? AND gid=?", (uid, gid)).fetchone()
    if r and (now - r["last_time"]) < 10:
        cnt = r["count"] + 1
    else:
        cnt = 1
    c.execute("INSERT OR REPLACE INTO spam_track(uid,gid,count,last_time) VALUES(?,?,?,?)", (uid, gid, cnt, now))
    c.commit(); c.close()
    return cnt >= limit

# ═══════════════════════════════════════════════════════════════
# PERMISSION RESOLVER
# ═══════════════════════════════════════════════════════════════
def resolve_perm(uid, gid=None, zalo_admins=None):
    if uid in OWNER_IDS: return P_DEV
    u = get_user(uid)
    if u.get("perm", 0) >= P_HI_ADMIN: return u["perm"]
    if gid and is_bot_admin(uid, gid): return P_BOT_ADMIN
    if gid and zalo_admins and uid in zalo_admins: return P_GRP_ADMIN
    return u.get("perm", P_USR)

def check_perm(uid, need, gid=None, zalo_admins=None):
    return resolve_perm(uid, gid, zalo_admins) >= need

# ═══════════════════════════════════════════════════════════════
# BOT CLASS
# ═══════════════════════════════════════════════════════════════
class LENhanBot(ZaloAPI):

    def onMessage(self, mid, author_id, message, message_object, thread_id, thread_type):
        try:
            self._handle(author_id, message, message_object, thread_id, thread_type)
        except Exception as e:
            print(f"[ERR] onMessage: {e}")

    def onGroupMessage(self, mid, author_id, message, message_object, thread_id, thread_type):
        try:
            self._handle(author_id, message, message_object, thread_id, thread_type, is_group=True)
        except Exception as e:
            print(f"[ERR] onGroupMessage: {e}")

    def onMemberJoinGroup(self, member_id, source, group_id, group_object):
        try:
            g = get_group(group_id)
            if g.get("event_notify") and g.get("welcome"):
                name = member_id
                msg = g.get("welcome_msg", "Chào {name}!").replace("{name}", str(name))
                self._send(msg, group_id, GroupType.GROUP)
        except Exception as e:
            print(f"[ERR] onMemberJoin: {e}")

    def _send(self, text, thread_id, thread_type):
        try:
            self.send(Message(text=str(text)), thread_id=thread_id, thread_type=thread_type)
        except: pass

    def _reply(self, text, thread_id, thread_type):
        self._send(text, thread_id, thread_type)

    def _handle(self, uid, message, message_object, thread_id, thread_type, is_group=False):
        if not message: return
        gid = thread_id if is_group else None

        # ensure user & group exist
        upsert_user(uid)
        if gid: upsert_group(gid)

        # get per-group prefix
        g = get_group(gid) if gid else {}
        prefix = g.get("prefix", PREFIX) or PREFIX

        # anti-spam
        if gid and g.get("antispam") and not check_perm(uid, P_BOT_ADMIN, gid):
            limit = g.get("antispam_limit", 5) or 5
            if track_spam(uid, gid, limit):
                self._send(f"⚠️ @{uid} spam quá giới hạn, tạm thời bị chặn.", thread_id, thread_type)
                set_silent(uid, gid, True)
                return

        # anti-silent
        if gid and is_silenced(uid, gid):
            try: self.undoMessage(message_object.msgId, thread_id, thread_type)
            except: pass
            return

        # anti-bad word
        if gid and g.get("antibadword"):
            bw = get_badwords(gid)
            msg_lower = message.lower()
            if any(w in msg_lower for w in bw):
                try: self.undoMessage(message_object.msgId, thread_id, thread_type)
                except: pass
                self._send(f"🚫 Tin nhắn chứa từ cấm đã bị xoá.", thread_id, thread_type)
                return

        # anti-url
        if gid and g.get("antiurl") and not check_perm(uid, P_BOT_ADMIN, gid):
            if re.search(r'https?://|www\.', message, re.I):
                try: self.undoMessage(message_object.msgId, thread_id, thread_type)
                except: pass
                self._send("🚫 Không được gửi link trong nhóm này.", thread_id, thread_type)
                return

        # log
        if gid: log_msg(uid, gid, message)

        # check command
        if not message.startswith(prefix): return
        raw = message[len(prefix):].strip()
        if not raw: return
        parts = raw.split()
        cmd = parts[0].lower()
        args = parts[1:]

        # resolve alias
        if gid:
            aliased = get_alias(gid, cmd)
            if aliased:
                parts2 = aliased.split() + args
                cmd = parts2[0].lower()
                args = parts2[1:]

        # bot on/off check
        if gid and not g.get("bot_on", 1) and cmd != "bot":
            return

        # dispatch
        self._dispatch(cmd, args, uid, gid, thread_id, thread_type, message_object, g)

    def _dispatch(self, cmd, args, uid, gid, tid, ttype, msg_obj, g):
        R = lambda t: self._reply(t, tid, ttype)
        perm = resolve_perm(uid, gid)

        # ─────────────────────────────────────────────
        # THÔNG TIN & HỆ THỐNG
        # ─────────────────────────────────────────────
        if cmd == "menu":
            R(self._menu())

        elif cmd == "ping":
            start = time.time()
            R(f"🏓 Pong! | {BOT_NAME}\n⏱ {round((time.time()-start)*1000)}ms\n👑 Tác giả: {OWNER_NAME}")

        elif cmd == "info":
            u = get_user(uid)
            R(f"👤 Thông tin tài khoản\n"
              f"UID: {uid}\n"
              f"Tiền: {u.get('money',0):,} 💰\n"
              f"EXP: {u.get('exp',0)}\n"
              f"Quyền: {self._perm_name(perm)}")

        elif cmd == "uid":
            target = args[0] if args else uid
            R(f"🔍 UID: {target}")

        elif cmd == "check":
            import platform
            R(f"🖥 Hệ thống\nOS: {platform.system()} {platform.release()}\n"
              f"Python: {sys.version.split()[0]}\nBot: {BOT_NAME}\nOwner: {OWNER_NAME}")

        elif cmd == "cpu":
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=1)
                ram = psutil.virtual_memory()
                R(f"💻 CPU: {cpu}%\nRAM: {ram.percent}% ({ram.used//1024//1024}MB/{ram.total//1024//1024}MB)")
            except:
                R("⚠️ Không đọc được thông tin CPU (psutil chưa cài)")

        elif cmd == "uptcard":
            R(f"⏱ Bot đang hoạt động\n👑 Owner: {OWNER_NAME}\n🤖 {BOT_NAME}")

        elif cmd == "source":
            if msg_obj:
                R(f"📦 Message data:\n{json.dumps({'mid': str(msg_obj.msgId), 'uid': uid, 'gid': str(gid)}, indent=2, ensure_ascii=False)}")

        elif cmd == "ffid":
            target = args[0] if args else uid
            u = get_user(target)
            R(f"🔎 Thông tin UID: {target}\nTên: {u.get('name','Chưa biết')}\nQuyền: {self._perm_name(u.get('perm',0))}\nTiền: {u.get('money',0):,} 💰")

        elif cmd == "lich":
            import datetime
            now = datetime.datetime.now()
            R(f"📅 {now.strftime('%A, %d/%m/%Y %H:%M:%S')}")

        elif cmd == "prefix":
            if not args:
                R(f"📌 Prefix hiện tại: `{g.get('prefix', PREFIX)}`")
            elif perm >= P_HI_ADMIN:
                new_p = args[0]
                set_grp(gid, "prefix", new_p)
                R(f"✅ Đã đổi prefix thành: {new_p}")
            else:
                R("❌ Cần quyền HI ADMIN")

        elif cmd == "qr":
            text = " ".join(args) if args else uid
            R(f"📱 Tạo QR cho: {text}\n(Tính năng QR cần thư viện qrcode — xem docs)")

        elif cmd == "encode":
            if not args:
                R(f"Dùng: {PREFIX}encode <base64|md5|hex> <text>")
            else:
                method = args[0].lower()
                text = " ".join(args[1:])
                if method == "base64":
                    import base64 as b64
                    R(f"🔐 Base64: {b64.b64encode(text.encode()).decode()}")
                elif method == "md5":
                    R(f"🔐 MD5: {hashlib.md5(text.encode()).hexdigest()}")
                elif method == "hex":
                    R(f"🔐 HEX: {text.encode().hex()}")
                elif method == "decode":
                    import base64 as b64
                    try: R(f"🔓 Decode: {b64.b64decode(text).decode()}")
                    except: R("❌ Không decode được")
                else:
                    R("Hỗ trợ: base64, md5, hex, decode")

        elif cmd == "translate":
            if len(args) < 2:
                R(f"Dùng: {PREFIX}translate <lang> <text>\nVD: {PREFIX}translate en Xin chào")
            else:
                lang = args[0]; text = " ".join(args[1:])
                try:
                    r = requests.get(f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={lang}&dt=t&q={requests.utils.quote(text)}", timeout=5)
                    result = r.json()[0][0][0]
                    R(f"🌐 Dịch ({lang}): {result}")
                except:
                    R("❌ Lỗi dịch thuật")

        elif cmd == "voice":
            R("🎙 Tính năng TTS đang phát triển.")

        elif cmd == "vtxt":
            R("🎵➡️📝 Tính năng voice-to-text đang phát triển.")

        # ─────────────────────────────────────────────
        # ADMIN & PHÂN QUYỀN
        # ─────────────────────────────────────────────
        elif cmd == "admin":
            if perm < P_HI_ADMIN:
                R("❌ Cần quyền HI ADMIN"); return
            if not args:
                R(f"Dùng: {PREFIX}admin add/remove @uid"); return
            action = args[0].lower()
            target = args[1] if len(args) > 1 else None
            if not target: R("❌ Thiếu UID"); return
            target = target.lstrip("@")
            if action == "add":
                upsert_user(target)
                set_perm(target, P_HI_ADMIN)
                R(f"✅ Đã thêm {target} làm HI ADMIN")
            elif action == "remove":
                set_perm(target, P_USR)
                R(f"✅ Đã xoá quyền HI ADMIN của {target}")
            else:
                R("Hành động: add / remove")

        elif cmd == "acl":
            if perm < P_BOT_ADMIN:
                R("❌ Cần quyền BOT ADMIN"); return
            # list permissions
            c = db()
            rows = c.execute("SELECT uid,perm FROM users ORDER BY perm DESC LIMIT 20").fetchall()
            c.close()
            lines = [f"{r['uid']}: {self._perm_name(r['perm'])}" for r in rows]
            R("📋 Danh sách phân quyền:\n" + "\n".join(lines) if lines else "Trống")

        elif cmd == "blockbot":
            if perm < P_BOT_ADMIN:
                R("❌ Cần quyền BOT ADMIN"); return
            if not args: R(f"Dùng: {PREFIX}blockbot <uid>"); return
            target = args[0].lstrip("@")
            upsert_user(target)
            c = db(); c.execute("UPDATE users SET blocked=1 WHERE uid=?", (target,)); c.commit(); c.close()
            R(f"🚫 Đã chặn {target} dùng bot")

        elif cmd == "bot":
            if not gid: return
            if perm < P_BOT_ADMIN:
                R("❌ Cần quyền BOT ADMIN"); return
            if args and args[0].lower() in ["off","0"]:
                set_grp(gid, "bot_on", 0)
                R("🔴 Bot đã tắt trong nhóm này")
            else:
                set_grp(gid, "bot_on", 1)
                R("🟢 Bot đã bật trong nhóm này")

        elif cmd == "baotri":
            if perm < P_HI_ADMIN:
                R("❌ Cần quyền HI ADMIN"); return
            msg = " ".join(args) if args else "Bot đang bảo trì, vui lòng chờ!"
            R(f"🔧 THÔNG BÁO BẢO TRÌ\n{msg}\n👑 {OWNER_NAME}")

        elif cmd == "restart":
            if perm < P_HI_ADMIN:
                R("❌ Cần quyền HI ADMIN"); return
            R("♻️ Đang khởi động lại bot...")
            os.execv(sys.executable, [sys.executable] + sys.argv)

        elif cmd == "alias":
            if not gid: return
            if not args:
                als = list_aliases(gid)
                if not als: R("Chưa có alias nào."); return
                R("📎 Danh sách alias:\n" + "\n".join(f"{a} → {c}" for a,c in als))
            elif args[0] == "add" and len(args) >= 3:
                if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
                set_alias(gid, args[1], " ".join(args[2:]))
                R(f"✅ Alias `{args[1]}` → `{' '.join(args[2:])}`")
            elif args[0] == "del" and len(args) >= 2:
                if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
                del_alias(gid, args[1])
                R(f"✅ Đã xoá alias `{args[1]}`")

        elif cmd == "command":
            if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
            R(f"⚙️ Quản lý lệnh: dùng {PREFIX}alias để tạo alias lệnh")

        elif cmd == "manager":
            if perm < P_HI_ADMIN: R("❌ Cần HI ADMIN"); return
            R(f"🤖 Bot Manager\nBot: {BOT_NAME}\nOwner: {OWNER_NAME}\nPrefix: {g.get('prefix',PREFIX)}\nBot on: {'✅' if g.get('bot_on',1) else '❌'}")

        elif cmd == "im":
            if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
            if not args:
                R(f"Dùng: {PREFIX}im <setting> <value>"); return
            # personal bot settings
            R(f"⚙️ Đã lưu setting: {' '.join(args)}")

        elif cmd == "var":
            if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
            R("📊 Var user đang phát triển.")

        elif cmd == "stg":
            if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
            if not args:
                g2 = get_group(gid) if gid else {}
                info = "\n".join(f"{k}: {v}" for k,v in g2.items() if k not in ("gid","name"))
                R(f"⚙️ Setting nhóm:\n{info}")
            else:
                field = args[0]; val = args[1] if len(args)>1 else None
                if val:
                    set_grp(gid, field, val)
                    R(f"✅ Đã set {field} = {val}")

        elif cmd == "sys":
            if perm < P_DEV: R("❌ Cần DEV"); return
            R(f"🔧 System: Python {sys.version.split()[0]}")

        elif cmd == "test":
            if perm < P_HI_ADMIN: R("❌ Cần HI ADMIN"); return
            R(f"✅ Bot đang hoạt động bình thường\n{BOT_NAME} — ready!")

        elif cmd == "mod":
            if perm < P_DEV: R("❌ Cần DEV"); return
            R("🛠 Account Modifier — đang phát triển.")

        elif cmd == "multibot":
            if perm < P_DEV: R("❌ Cần DEV"); return
            R("🤖 Multi-bot management — đang phát triển.")

        elif cmd == "null":
            pass  # no-op

        elif cmd == "key-as":
            if perm < P_HI_ADMIN: R("❌ Cần HI ADMIN"); return
            if not gid or not args: R(f"Dùng: {PREFIX}key-as <uid>"); return
            target = args[0].lstrip("@")
            upsert_user(target)
            cur = is_bot_admin(target, gid)
            set_bot_admin(target, gid, not cur)
            R(f"{'✅ Đã thêm' if not cur else '❌ Đã xoá'} quyền admin nhóm cho {target}")

        # ─────────────────────────────────────────────
        # MODERATION
        # ─────────────────────────────────────────────
        elif cmd == "kick":
            if not gid: R("❌ Chỉ dùng trong nhóm"); return
            if perm < P_GRP_ADMIN: R("❌ Cần quyền admin nhóm"); return
            if not args: R(f"Dùng: {PREFIX}kick <uid>"); return
            for t in args:
                t = t.lstrip("@")
                try:
                    self.removeUsersFromGroup(t, gid)
                    R(f"👢 Đã kick {t}")
                except:
                    R(f"❌ Không kick được {t}")

        elif cmd == "block":
            if not gid: return
            if perm < P_GRP_ADMIN: R("❌ Cần admin nhóm"); return
            if not args: R(f"Dùng: {PREFIX}block <uid>"); return
            target = args[0].lstrip("@")
            try:
                self.removeUsersFromGroup(target, gid)
                R(f"🚫 Đã block & kick {target}")
            except:
                R(f"❌ Lỗi")

        elif cmd == "approve":
            if not gid: return
            if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
            R("✅ Chức năng duyệt yêu cầu tham gia nhóm đang phát triển.")

        elif cmd == "dmsg":
            if perm < P_HI_ADMIN: R("❌ Cần HI ADMIN"); return
            if not args: R(f"Dùng: {PREFIX}dmsg <message_id>"); return
            try:
                self.undoMessage(args[0], tid, ttype)
                R("🗑 Đã xoá tin nhắn")
            except:
                R("❌ Không xoá được")

        elif cmd == "silent":
            if not gid: return
            if perm < P_GRP_ADMIN: R("❌ Cần admin nhóm"); return
            if not args: R(f"Dùng: {PREFIX}silent <uid|all>"); return
            if args[0].lower() == "all":
                set_grp(gid, "silent_all", 1)
                R("🔇 Đã tắt chat toàn nhóm")
            else:
                target = args[0].lstrip("@")
                set_silent(target, gid, True)
                R(f"🔇 Đã tắt chat của {target}")

        elif cmd == "ckg":
            if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
            try:
                link = self.getGroupLink(gid)
                R(f"🔗 Link nhóm: {link}")
            except:
                R("❌ Không lấy được link nhóm")

        elif cmd == "wc":
            if not gid: return
            if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
            if not args:
                cur = get_grp(gid, "welcome")
                R(f"🎉 Welcome: {'✅ Bật' if cur else '❌ Tắt'}\nMsg: {get_grp(gid,'welcome_msg')}")
            elif args[0] in ["on","1"]:
                set_grp(gid, "welcome", 1); R("✅ Đã bật welcome")
            elif args[0] in ["off","0"]:
                set_grp(gid, "welcome", 0); R("✅ Đã tắt welcome")
            elif args[0] == "set":
                msg = " ".join(args[1:]); set_grp(gid, "welcome_msg", msg)
                R(f"✅ Đã set welcome msg: {msg}")

        elif cmd == "event":
            if not gid: return
            if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
            if args and args[0] in ["off","0"]:
                set_grp(gid, "event_notify", 0); R("🔕 Đã tắt thông báo event")
            else:
                set_grp(gid, "event_notify", 1); R("🔔 Đã bật thông báo event")

        elif cmd == "pr":
            if not gid: return
            if perm < P_HI_ADMIN: R("❌ Cần HI ADMIN"); return
            if not args:
                R(f"Dùng: {PREFIX}pr set <nội dung> | {PREFIX}pr on/off")
            elif args[0] == "set":
                msg = " ".join(args[1:]); set_grp(gid, "pr_msg", msg)
                R(f"✅ Đã set PR msg")
            elif args[0] in ["on","1"]:
                set_grp(gid, "pr_on", 1); R("✅ Đã bật auto PR")
            elif args[0] in ["off","0"]:
                set_grp(gid, "pr_on", 0); R("✅ Đã tắt auto PR")

        elif cmd == "treo":
            if not gid: return
            if not args or len(args) < 2:
                R(f"Dùng: {PREFIX}treo <giây> <nội dung>"); return
            try:
                delay = int(args[0]); msg = " ".join(args[1:])
                send_at = time.time() + delay
                c2 = db()
                c2.execute("INSERT INTO scheduled(gid,uid,msg,send_at) VALUES(?,?,?,?)", (gid, uid, msg, send_at))
                c2.commit(); c2.close()
                R(f"⏳ Đã lên lịch gửi sau {delay}s")
            except:
                R("❌ Lỗi lên lịch")

        elif cmd == "spm":
            if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
            if not args or len(args) < 2:
                R(f"Dùng: {PREFIX}spm <số lần> <nội dung>"); return
            try:
                n = min(int(args[0]), 10); msg = " ".join(args[1:])
                for _ in range(n):
                    self._send(msg, tid, ttype)
                    time.sleep(0.5)
            except:
                R("❌ Lỗi")

        elif cmd == "getlink":
            R("📎 Tính năng getlink attachment đang phát triển.")

        # ─────────────────────────────────────────────
        # ANTI SETTINGS
        # ─────────────────────────────────────────────
        elif cmd == "antispam":
            if not gid: return
            if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
            if args and args[0] in ["on","1"]:
                set_grp(gid, "antispam", 1)
                limit = int(args[1]) if len(args)>1 and args[1].isdigit() else 5
                set_grp(gid, "antispam_limit", limit)
                R(f"✅ Anti spam ON (giới hạn {limit} tin/10s)")
            else:
                set_grp(gid, "antispam", 0); R("✅ Anti spam OFF")

        elif cmd == "antibadword":
            if not gid: return
            if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
            if not args:
                bw = get_badwords(gid)
                R(f"🤬 Từ cấm: {', '.join(bw) if bw else 'Chưa có'}")
            elif args[0] in ["on","1"]:
                set_grp(gid, "antibadword", 1); R("✅ Anti bad word ON")
            elif args[0] in ["off","0"]:
                set_grp(gid, "antibadword", 0); R("✅ Anti bad word OFF")
            elif args[0] == "add" and len(args)>1:
                for w in args[1:]: add_badword(gid, w)
                R(f"✅ Đã thêm: {', '.join(args[1:])}")
            elif args[0] == "del" and len(args)>1:
                for w in args[1:]: del_badword(gid, w)
                R(f"✅ Đã xoá: {', '.join(args[1:])}")

        elif cmd == "antiurl":
            if not gid: return
            if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
            val = 1 if not args or args[0] in ["on","1"] else 0
            set_grp(gid, "antiurl", val); R(f"✅ Anti URL {'ON' if val else 'OFF'}")

        elif cmd == "antiforward":
            if not gid: return
            if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
            val = 1 if not args or args[0] in ["on","1"] else 0
            set_grp(gid, "antiforward", val); R(f"✅ Anti forward {'ON' if val else 'OFF'}")

        elif cmd == "anticard":
            if not gid: return
            if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
            val = 1 if not args or args[0] in ["on","1"] else 0
            set_grp(gid, "anticard", val); R(f"✅ Anti card {'ON' if val else 'OFF'}")

        elif cmd == "antibot":
            if not gid: return
            if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
            val = 1 if not args or args[0] in ["on","1"] else 0
            set_grp(gid, "antibot", val); R(f"✅ Anti bot {'ON' if val else 'OFF'}")

        elif cmd == "antiadd":
            if not gid: return
            if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
            val = 1 if not args or args[0] in ["on","1"] else 0
            set_grp(gid, "antiadd", val); R(f"✅ Anti add {'ON' if val else 'OFF'}")

        elif cmd == "antistatus":
            if not gid: return
            g2 = get_group(gid) if gid else {}
            status = {
                "antispam": g2.get("antispam",0),
                "antibadword": g2.get("antibadword",0),
                "antiurl": g2.get("antiurl",0),
                "antiforward": g2.get("antiforward",0),
                "anticard": g2.get("anticard",0),
                "antibot": g2.get("antibot",0),
                "antiadd": g2.get("antiadd",0),
            }
            lines = "\n".join(f"{'✅' if v else '❌'} {k}" for k,v in status.items())
            R(f"🛡 Trạng thái Anti:\n{lines}")

        # ─────────────────────────────────────────────
        # ECONOMY
        # ─────────────────────────────────────────────
        elif cmd == "money":
            u = get_user(uid)
            R(f"💰 Số dư: {u.get('money',0):,} coins\n👤 UID: {uid}")

        elif cmd == "buff":
            if perm < P_BOT_ADMIN: R("❌ Cần BOT ADMIN"); return
            if len(args) < 2: R(f"Dùng: {PREFIX}buff <uid> <số tiền>"); return
            target = args[0].lstrip("@"); amt = int(args[1])
            upsert_user(target); add_money(target, amt)
            R(f"💸 Đã buff {amt:,} coins cho {target}")

        elif cmd == "gift":
            if len(args) < 2: R(f"Dùng: {PREFIX}gift <uid> <số tiền>"); return
            target = args[0].lstrip("@"); amt = int(args[1])
            if get_money(uid) < amt: R("❌ Không đủ tiền"); return
            add_money(uid, -amt); upsert_user(target); add_money(target, amt)
            c2 = db()
            c2.execute("INSERT INTO transactions(from_uid,to_uid,amount,note) VALUES(?,?,?,?)",
                (uid, target, amt, "gift")); c2.commit(); c2.close()
            R(f"🎁 Đã tặng {amt:,} coins cho {target}")

        elif cmd == "alys":
            top = top_senders(gid) if gid else []
            if not top: R("Chưa có dữ liệu"); return
            lines = [f"#{i+1} {u}: {cnt} tin" for i,(u,cnt) in enumerate(top)]
            R("📊 Top nhắn tin nhiều nhất:\n" + "\n".join(lines))

        # ─────────────────────────────────────────────
        # GAMES — Tài Xỉu
        # ─────────────────────────────────────────────
        elif cmd == "taixiu":
            if not gid: R("❌ Chỉ chơi trong nhóm"); return
            if not args:
                R(f"Dùng: {PREFIX}taixiu tai/xiu <số tiền>\nVD: {PREFIX}taixiu tai 500"); return
            if args[0].lower() not in ["tai","xiu","tài","xỉu"]:
                R("Chọn: tai hoặc xiu"); return
            bet_type = "tai" if args[0].lower() in ["tai","tài"] else "xiu"
            try: amount = int(args[1]) if len(args)>1 else 100
            except: amount = 100
            if get_money(uid) < amount: R("❌ Không đủ tiền"); return

            dice = [random.randint(1,6) for _ in range(3)]
            total = sum(dice)
            result = "tai" if total >= 11 else "xiu"
            win = (bet_type == result)

            add_money(uid, amount if win else -amount)
            emoji = "🎲"
            dice_str = " ".join(str(d) for d in dice)
            R(f"{emoji} Tài Xỉu\nXúc xắc: {dice_str} = {total}\n"
              f"Kết quả: {'TÀI' if result=='tai' else 'XỈU'}\n"
              f"{'🎉 Thắng' if win else '😢 Thua'} {amount:,} coins\n"
              f"💰 Số dư: {get_money(uid):,}")

        # ─────────────────────────────────────────────
        # GAMES — Bầu Cua
        # ─────────────────────────────────────────────
        elif cmd == "baucua":
            animals = ["🦀 Cua", "🦐 Tôm", "🐟 Cá", "🦌 Nai", "🏺 Bầu", "🐓 Gà"]
            animal_map = {
                "cua":"🦀 Cua","tom":"🦐 Tôm","tôm":"🦐 Tôm",
                "ca":"🐟 Cá","cá":"🐟 Cá","nai":"🦌 Nai",
                "bau":"🏺 Bầu","bầu":"🏺 Bầu","ga":"🐓 Gà","gà":"🐓 Gà"
            }
            if not args or len(args) < 2:
                R(f"🎮 Bầu Cua\nDùng: {PREFIX}baucua <con> <tiền>\nCon: cua, tom, ca, nai, bau, ga"); return
            pick = args[0].lower()
            if pick not in animal_map: R(f"❌ Con hợp lệ: {', '.join(animal_map.keys())}"); return
            try: amount = int(args[1])
            except: R("❌ Số tiền không hợp lệ"); return
            if get_money(uid) < amount: R("❌ Không đủ tiền"); return

            rolled = [random.choice(animals) for _ in range(3)]
            picked_name = animal_map[pick]
            count = rolled.count(picked_name)
            if count > 0:
                add_money(uid, amount * count)
                R(f"🎲 Bầu Cua\n{' | '.join(rolled)}\n✅ {picked_name} xuất hiện {count} lần!\n🎉 Thắng {amount*count:,} coins\n💰 Số dư: {get_money(uid):,}")
            else:
                add_money(uid, -amount)
                R(f"🎲 Bầu Cua\n{' | '.join(rolled)}\n❌ Không có {picked_name}\n😢 Thua {amount:,} coins\n💰 Số dư: {get_money(uid):,}")

        # ─────────────────────────────────────────────
        # GAMES — Cờ Caro (đơn giản)
        # ─────────────────────────────────────────────
        elif cmd == "caro":
            R("♟ Cờ Caro AI đang phát triển — coming soon!")

        # ─────────────────────────────────────────────
        # GAMES — Ma Sói
        # ─────────────────────────────────────────────
        elif cmd == "masoi":
            if not gid: R("❌ Chỉ chơi trong nhóm"); return
            if not args:
                R(f"🐺 Ma Sói\n{PREFIX}masoi start — Tạo phòng\n{PREFIX}masoi join — Tham gia\n{PREFIX}masoi begin — Bắt đầu")
                return
            action = args[0].lower()
            if action == "start":
                c2 = db()
                c2.execute("INSERT OR REPLACE INTO game_sessions(gid,game,data,host) VALUES(?,?,?,?)",
                    (gid,"masoi",json.dumps({"players":[uid],"phase":"lobby"}),uid))
                c2.commit(); c2.close()
                R(f"🐺 Phòng Ma Sói đã tạo!\nHost: {uid}\nDùng {PREFIX}masoi join để tham gia")
            elif action == "join":
                c2 = db()
                r = c2.execute("SELECT data FROM game_sessions WHERE gid=? AND game=?", (gid,"masoi")).fetchone()
                if not r: R("Chưa có phòng. Dùng ?masoi start"); c2.close(); return
                data = json.loads(r["data"])
                if uid not in data["players"]:
                    data["players"].append(uid)
                    c2.execute("UPDATE game_sessions SET data=? WHERE gid=? AND game=?",
                        (json.dumps(data),gid,"masoi"))
                    c2.commit()
                R(f"✅ {uid} đã vào phòng! ({len(data['players'])} người)")
                c2.close()
            elif action == "begin":
                c2 = db()
                r = c2.execute("SELECT data,host FROM game_sessions WHERE gid=? AND game=?", (gid,"masoi")).fetchone()
                if not r: R("Chưa có phòng"); c2.close(); return
                if r["host"] != uid: R("Chỉ host mới bắt đầu được"); c2.close(); return
                data = json.loads(r["data"])
                players = data["players"]
                if len(players) < 4: R("Cần ít nhất 4 người"); c2.close(); return
                roles = ["Ma sói"] * max(1, len(players)//4) + ["Dân làng"] * (len(players) - max(1,len(players)//4))
                random.shuffle(roles)
                assignment = dict(zip(players, roles))
                R(f"🐺 Game bắt đầu! {len(players)} người\n" + "\n".join(f"{p}: Vai bí mật" for p in players))
                # In private, send role
                for p, role in assignment.items():
                    try: self._send(f"🎭 Vai của bạn: {role}", p, ThreadType.USER)
                    except: pass
                c2.execute("DELETE FROM game_sessions WHERE gid=? AND game=?", (gid,"masoi"))
                c2.commit(); c2.close()

        # ─────────────────────────────────────────────
        # GAMES — Tu Tiên
        # ─────────────────────────────────────────────
        elif cmd == "tutien":
            u = get_user(uid)
            exp = u.get("exp", 0)
            levels = ["Phàm Nhân","Luyện Khí","Trúc Cơ","Kim Đan","Nguyên Anh","Hóa Thần","Luyện Hư","Hợp Thể","Đại Thừa","Độ Kiếp"]
            lv = min(exp // 1000, len(levels)-1)
            c2 = db(); c2.execute("UPDATE users SET exp=exp+? WHERE uid=?", (random.randint(10,50), uid)); c2.commit(); c2.close()
            R(f"🏔 Tu Tiên\n境界: {levels[lv]}\n修为: {exp} / {(lv+1)*1000}\n+{random.randint(10,50)} tu vi")

        # ─────────────────────────────────────────────
        # GAMES — Pet
        # ─────────────────────────────────────────────
        elif cmd == "pet":
            c2 = db()
            pet = c2.execute("SELECT * FROM pets WHERE uid=?", (uid,)).fetchone()
            if not args or args[0] == "info":
                if not pet:
                    R(f"🐾 Bạn chưa có pet!\nDùng: {PREFIX}pet tao <tên> <loại>\nLoại: cho, meo, ran, rong")
                else:
                    R(f"🐾 Pet của bạn\nTên: {pet['name']}\nLoại: {pet['type']}\nHP: {pet['hp']}\nATK: {pet['atk']}\nLv: {pet['level']}")
            elif args[0] == "tao" and len(args) >= 3:
                name = args[1]; ptype = args[2]
                c2.execute("INSERT OR REPLACE INTO pets(uid,name,type) VALUES(?,?,?)", (uid,name,ptype))
                c2.commit()
                R(f"🎉 Đã tạo pet `{name}` loại {ptype}!")
            elif args[0] == "train":
                if not pet: R("Bạn chưa có pet"); c2.close(); return
                gain = random.randint(1,5)
                c2.execute("UPDATE pets SET exp=exp+?, atk=atk+1 WHERE uid=?", (gain*10, uid))
                c2.commit()
                R(f"💪 Pet đã luyện tập! +{gain*10} EXP, +1 ATK")
            c2.close()

        # ─────────────────────────────────────────────
        # GAMES — Cuộc Sống (RPG)
        # ─────────────────────────────────────────────
        elif cmd == "life":
            events = [
                ("💼 Đi làm", 200), ("🎰 Trúng số nhỏ", 500),
                ("🏥 Bệnh viện", -300), ("🛒 Mua sắm", -150),
                ("🍜 Ăn phở", -50), ("💡 Tiết kiệm điện", 100),
                ("🤝 Giúp hàng xóm", 300), ("🎮 Thua game", -200),
            ]
            event, money = random.choice(events)
            add_money(uid, money)
            sign = "+" if money > 0 else ""
            R(f"🌍 Cuộc sống hôm nay\n{event}\n{sign}{money:,} coins\n💰 Số dư: {get_money(uid):,}")

        # ─────────────────────────────────────────────
        # GAMES — Hải Tặc (HTHT)
        # ─────────────────────────────────────────────
        elif cmd == "htht":
            islands = ["Đảo Skull","Vương Quốc Rỗng","Biển Đông","Đảo Báu","Vùng Grand Line"]
            enemies = ["Hải Quân","Cướp Biển Mạnh","Quái Vật Biển","Lính Thủy"]
            enemy = random.choice(enemies); island = random.choice(islands)
            win = random.random() > 0.4
            reward = random.randint(100, 800)
            if win:
                add_money(uid, reward)
                R(f"⚓ Hải Tặc\n📍 Vị trí: {island}\n⚔️ Gặp {enemy}\n🏆 Thắng! +{reward:,} coins\n💰 Số dư: {get_money(uid):,}")
            else:
                add_money(uid, -reward//2)
                R(f"⚓ Hải Tặc\n📍 Vị trí: {island}\n⚔️ Gặp {enemy}\n💀 Thua! -{reward//2:,} coins\n💰 Số dư: {get_money(uid):,}")

        # ─────────────────────────────────────────────
        # FUN
        # ─────────────────────────────────────────────
        elif cmd == "cute":
            score = random.randint(1, 100)
            stars = "⭐" * (score // 20)
            R(f"🌸 Chỉ số CUTE của bạn\n{stars}\n{score}/100 điểm cute!\n{'Siêu dễ thương! 💕' if score > 80 else 'Khá cute đó 😊' if score > 50 else 'Cần cố thêm 😄'}")

        elif cmd == "dam":
            score = random.randint(1, 100)
            R(f"😈 Chỉ số DAM của bạn\n{score}/100\n{'Cực kỳ... dam 😳' if score > 80 else 'Bình thường thôi 😐' if score > 40 else 'Trong sáng lắm 😇'}")

        elif cmd == "gay":
            score = random.randint(0, 100)
            R(f"🌈 Chỉ số GAY đo được: {score}%\n{'Rất rất rất... 🏳️‍🌈' if score > 80 else 'Bình thường 😄' if score > 40 else 'Straight 100% 😎'}")

        elif cmd == "les":
            score = random.randint(0, 100)
            R(f"💜 Chỉ số LES: {score}%\n{'Chị chị em em 💕' if score > 70 else 'Bình thường thôi 😄'}")

        elif cmd == "love":
            poems = [
                "Yêu em từ cái nhìn đầu tiên,\nMắt em như trăng soi trên biển.",
                "Tình yêu như ánh nắng ban mai,\nSưởi ấm lòng ta mỗi sớm ngày.",
                "Em là bến đỗ của cuộc đời,\nNơi ta tìm về mỗi cuối ngày."
            ]
            target = " ".join(args) if args else "bạn ơi"
            R(f"💌 Tỏ tình với {target}\n\n{random.choice(poems)}\n\n— {OWNER_NAME} Bot")

        elif cmd == "altp":
            quotes = [
                "Tôi là Triệu Phú! Giàu rồi không cần làm nữa!",
                "Tiền không mua được hạnh phúc... nhưng mua được thứ khác 💸",
                "Hôm nay tôi thức dậy và chọn bạo lực với ví tiền.",
            ]
            R(f"💰 {random.choice(quotes)}")

        elif cmd == "meme":
            R("😂 Tìm meme: tính năng tìm kiếm GIF/sticker đang phát triển.")

        elif cmd == "image":
            R("🖼 Xử lý ảnh: tính năng đang phát triển.")

        elif cmd == "sticker":
            R("🎨 Tạo sticker pixel: tính năng đang phát triển.")

        elif cmd == "warcard":
            if not args: R(f"Dùng: {PREFIX}warcard @uid"); return
            target = args[0].lstrip("@")
            my_power = random.randint(50, 100)
            enemy_power = random.randint(50, 100)
            win = my_power > enemy_power
            reward = random.randint(100, 300)
            if win: add_money(uid, reward)
            else: add_money(uid, -reward//2)
            R(f"⚔️ WAR CARD\n{uid} ({my_power}) vs {target} ({enemy_power})\n"
              f"{'🏆 Thắng! +' + str(reward) if win else '💀 Thua! -' + str(reward//2)} coins")

        # ─────────────────────────────────────────────
        # TikTok / MEDIA
        # ─────────────────────────────────────────────
        elif cmd == "tiktok":
            if not args: R(f"Dùng: {PREFIX}tiktok <link>"); return
            url = args[0]
            try:
                r = requests.get(f"https://tikwm.com/api/?url={url}", timeout=10)
                data = r.json()
                if data.get("code") == 0:
                    video_url = data["data"]["play"]
                    R(f"🎵 TikTok Video\n{video_url}")
                else:
                    R("❌ Không tải được video")
            except:
                R("❌ Lỗi tải TikTok")

        elif cmd == "download":
            if not args: R(f"Dùng: {PREFIX}download <link tiktok>"); return
            url = args[0]
            try:
                r = requests.get(f"https://tikwm.com/api/?url={url}", timeout=10)
                data = r.json()
                if data.get("code") == 0:
                    R(f"📥 Download:\nVideo: {data['data']['play']}\nAudio: {data['data'].get('music','N/A')}")
                else:
                    R("❌ Không tải được")
            except:
                R("❌ Lỗi")

        elif cmd in ["bufffl","bufftim","buffview"]:
            buff_type = {"bufffl":"Follow","bufftim":"Tim","buffview":"View"}[cmd]
            if not args: R(f"Dùng: {PREFIX}{cmd} <link tiktok>"); return
            R(f"📈 TikTok {buff_type} Buff\nLink: {args[0]}\n⚠️ Cần cấu hình Buff API key — liên hệ {OWNER_NAME}")

        elif cmd == "ttinfo":
            if not args: R(f"Dùng: {PREFIX}ttinfo <username tiktok>"); return
            username = args[0].lstrip("@")
            try:
                r = requests.get(f"https://www.tiktok.com/@{username}", timeout=5, headers={"User-Agent":"Mozilla/5.0"})
                R(f"📊 TikTok: @{username}\n🔗 https://www.tiktok.com/@{username}")
            except:
                R("❌ Không lấy được thông tin")

        elif cmd == "ttuser":
            if not args: R(f"Dùng: {PREFIX}ttuser <username>"); return
            R(f"👤 TikTok User: @{args[0]}\n🔗 https://www.tiktok.com/@{args[0]}")

        elif cmd == "capcut":
            if not args: R(f"Dùng: {PREFIX}capcut <từ khóa>"); return
            kw = " ".join(args)
            R(f"🎬 Tìm template CapCut: {kw}\n🔗 https://www.capcut.com/search?q={requests.utils.quote(kw)}")

        elif cmd == "pinterest":
            if not args: R(f"Dùng: {PREFIX}pinterest <từ khóa>"); return
            kw = " ".join(args)
            R(f"📌 Pinterest: {kw}\n🔗 https://www.pinterest.com/search/pins/?q={requests.utils.quote(kw)}")

        elif cmd in ["zing","nhaccuatui","audiomack","soundcloud","autosend"]:
            source_map = {"zing":"ZingMP3","nhaccuatui":"NhacCuaTui","audiomack":"Audiomack","soundcloud":"SoundCloud","autosend":"AutoSend"}
            if not args: R(f"Dùng: {PREFIX}{cmd} <tên bài hát>"); return
            kw = " ".join(args)
            R(f"🎵 {source_map[cmd]}: {kw}\n(Tính năng stream nhạc đang phát triển)")

        # ─────────────────────────────────────────────
        # AI
        # ─────────────────────────────────────────────
        elif cmd in ["gpt","gem"]:
            if not args: R(f"Dùng: {PREFIX}{cmd} <câu hỏi>"); return
            question = " ".join(args)
            if cmd == "gpt":
                if not OPENAI_KEY: R("⚠️ Chưa cấu hình OPENAI_KEY"); return
                try:
                    r = requests.post("https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type":"application/json"},
                        json={"model":"gpt-3.5-turbo","messages":[{"role":"user","content":question}]},
                        timeout=20)
                    answer = r.json()["choices"][0]["message"]["content"]
                    R(f"🤖 GPT: {answer}")
                except Exception as e:
                    R(f"❌ Lỗi GPT: {e}")
            else:
                if not GEMINI_KEY: R("⚠️ Chưa cấu hình GEMINI_KEY"); return
                try:
                    r = requests.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}",
                        json={"contents":[{"parts":[{"text":question}]}]},
                        timeout=20)
                    answer = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                    R(f"💎 Gemini: {answer}")
                except Exception as e:
                    R(f"❌ Lỗi Gemini: {e}")

        elif cmd == "call":
            if perm < P_HI_ADMIN: R("❌ Cần HI ADMIN"); return
            if not args: R(f"Dùng: {PREFIX}call <command>"); return
            # execute another command
            self._dispatch(args[0].lower(), args[1:], uid, gid, tid, ttype, msg_obj, g)

        elif cmd == "tree":
            if perm < P_HI_ADMIN: R("❌ Cần HI ADMIN"); return
            R("🌲 Advanced tree — đang phát triển.")

        # ─────────────────────────────────────────────
        # UNKNOWN
        # ─────────────────────────────────────────────
        else:
            R(f"❓ Lệnh `{PREFIX}{cmd}` không tồn tại\nDùng {PREFIX}menu để xem danh sách lệnh")

    def _perm_name(self, p):
        return {P_USR:"USR", P_GRP_ADMIN:"GRP ADMIN", P_BOT_ADMIN:"BOT ADMIN", P_HI_ADMIN:"HI ADMIN", P_DEV:"DEV"}.get(p, "USR")

    def _menu(self):
        return f"""╔══════════════════════════╗
║  🤖 {BOT_NAME}
║  👑 Owner: {OWNER_NAME}
╠══════════════════════════╣
║ 📋 THÔNG TIN
║  {PREFIX}menu  {PREFIX}info  {PREFIX}ping  {PREFIX}uid
║  {PREFIX}check  {PREFIX}cpu  {PREFIX}lich  {PREFIX}ffid
║  {PREFIX}uptcard  {PREFIX}source  {PREFIX}alys
╠══════════════════════════╣
║ 🛡 ADMIN
║  {PREFIX}admin  {PREFIX}acl  {PREFIX}key-as  {PREFIX}bot
║  {PREFIX}baotri  {PREFIX}restart  {PREFIX}alias
║  {PREFIX}prefix  {PREFIX}stg  {PREFIX}manager  {PREFIX}im
╠══════════════════════════╣
║ 🚫 ANTI
║  {PREFIX}antispam  {PREFIX}antibadword  {PREFIX}antiurl
║  {PREFIX}antiforward  {PREFIX}anticard  {PREFIX}antibot
║  {PREFIX}antiadd  {PREFIX}antistatus
╠══════════════════════════╣
║ 🔨 MODERATION
║  {PREFIX}kick  {PREFIX}block  {PREFIX}silent  {PREFIX}dmsg
║  {PREFIX}approve  {PREFIX}wc  {PREFIX}event  {PREFIX}pr
║  {PREFIX}treo  {PREFIX}ckg  {PREFIX}spm
╠══════════════════════════╣
║ 💰 ECONOMY
║  {PREFIX}money  {PREFIX}buff  {PREFIX}gift  {PREFIX}encode
║  {PREFIX}translate  {PREFIX}qr
╠══════════════════════════╣
║ 🎮 GAME
║  {PREFIX}taixiu  {PREFIX}baucua  {PREFIX}caro  {PREFIX}masoi
║  {PREFIX}tutien  {PREFIX}pet  {PREFIX}life  {PREFIX}htht
║  {PREFIX}warcard
╠══════════════════════════╣
║ 😂 FUN
║  {PREFIX}cute  {PREFIX}dam  {PREFIX}gay  {PREFIX}les
║  {PREFIX}love  {PREFIX}altp  {PREFIX}meme  {PREFIX}sticker
╠══════════════════════════╣
║ 🎵 MEDIA
║  {PREFIX}tiktok  {PREFIX}download  {PREFIX}pinterest
║  {PREFIX}capcut  {PREFIX}zing  {PREFIX}nhaccuatui
║  {PREFIX}audiomack  {PREFIX}soundcloud  {PREFIX}ttinfo
║  {PREFIX}bufffl  {PREFIX}bufftim  {PREFIX}buffview
╠══════════════════════════╣
║ 🤖 AI
║  {PREFIX}gpt  {PREFIX}gem  {PREFIX}translate
╚══════════════════════════╝"""

# ═══════════════════════════════════════════════════════════════
# SCHEDULER — xử lý ?treo
# ═══════════════════════════════════════════════════════════════
def run_scheduler(bot):
    while True:
        try:
            c2 = db()
            rows = c2.execute("SELECT * FROM scheduled WHERE sent=0 AND send_at<=?", (time.time(),)).fetchall()
            for row in rows:
                try:
                    bot._send(row["msg"], row["gid"], GroupType.GROUP)
                    c2.execute("UPDATE scheduled SET sent=1 WHERE id=?", (row["id"],))
                except: pass
            c2.commit(); c2.close()
        except: pass
        time.sleep(5)

# ═══════════════════════════════════════════════════════════════
# FLASK — keep-alive cho Render free tier
# ═══════════════════════════════════════════════════════════════
app = Flask(__name__)

@app.route("/")
def index():
    return jsonify({"status":"online","bot":BOT_NAME,"owner":OWNER_NAME})

@app.route("/health")
def health():
    return jsonify({"status":"ok","time":time.time()})

@app.route("/qr")
def show_qr():
    if os.path.exists("qr.png"):
        return send_file("qr.png", mimetype="image/png")
    return "QR chưa sẵn sàng", 404

def run_flask():
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    os.makedirs("data", exist_ok=True)

    # start Flask keep-alive
    t_flask = threading.Thread(target=run_flask, daemon=True)
    t_flask.start()
    print(f"[INFO] Flask running on port {PORT}")

    # load session nếu có
    imei = cookies = None
    if os.path.exists(SESSION_PATH):
        try:
            with open(SESSION_PATH) as f:
                sess = json.load(f)
            imei = sess.get("imei")
            cookies = sess.get("cookies")
            print("[INFO] Loaded session")
        except:
            pass

    bot = LENhanBot(imei or "", cookies or "")

    # start scheduler
    t_sched = threading.Thread(target=run_scheduler, args=(bot,), daemon=True)
    t_sched.start()

    if imei and cookies:
        print(f"[INFO] Đăng nhập bằng session...")
        bot.listen()
    else:
        print("[INFO] Lấy QR đăng nhập...")
        try:
            import qrcode, io
            qr_data = bot.getQRCodeLogin()
            qr_url = qr_data["data"]["qr_url"]
            img = qrcode.make(qr_url)
            img.save("qr.png")
            print(f"[INFO] QR đã lưu tại qr.png")
            print(f"[INFO] Mở http://localhost:{PORT}/qr để quét")

            # ── Gửi QR qua Telegram ──────────────────────
            tele_send_text(
                f"🤖 {BOT_NAME} khởi động!\n"
                f"📱 Quét QR bên dưới để đăng nhập Zalo\n"
                f"⏳ QR có hiệu lực ~2 phút"
            )
            tele_send_photo("qr.png", caption=f"QR Login — {BOT_NAME}")
            # ─────────────────────────────────────────────
        except Exception as e:
            print(f"[ERR] QR: {e}")
            tele_send_text(f"❌ Bot lỗi khi lấy QR: {e}")

        def on_login(imei_val, cookies_val):
            os.makedirs("data", exist_ok=True)
            with open(SESSION_PATH, "w") as f:
                json.dump({"imei": imei_val, "cookies": cookies_val}, f)
            print("[INFO] Session đã lưu!")
            tele_send_text(f"✅ Đăng nhập thành công!\n🤖 {BOT_NAME} đang chạy.")

        bot.listen(on_login_callback=on_login)

if __name__ == "__main__":
    main()
