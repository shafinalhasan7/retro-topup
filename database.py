import sqlite3
import hashlib
import os
import random
import string
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "retro_topup.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def hash_password(password: str, salt: str = "retro_salt_2026") -> str:
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

def generate_order_code() -> str:
    digits = ''.join(random.choices(string.digits, k=5))
    return f"RT-{digits}"

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Admins
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 2. Games / Products
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'Games',
        image_url TEXT NOT NULL,
        badge TEXT,
        input_type TEXT NOT NULL DEFAULT 'uid',
        input_label TEXT NOT NULL DEFAULT 'Player ID (UID)',
        input_placeholder TEXT NOT NULL DEFAULT 'আপনার প্লেয়ার আইডি দিন (e.g. 1234567890)',
        instructions TEXT,
        description TEXT,
        delivery_time TEXT DEFAULT '২ - ১০ মিনিট',
        sort_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 3. Packages
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS packages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        category TEXT DEFAULT 'standard',
        price REAL NOT NULL,
        original_price REAL,
        badge TEXT,
        in_stock INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
    )
    """)

    # 4. Payment Methods
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payment_methods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT 'Personal',
        number TEXT NOT NULL,
        instructions TEXT,
        logo_color TEXT,
        sort_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )
    """)

    # 5. Orders
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_code TEXT UNIQUE NOT NULL,
        game_id INTEGER,
        game_name TEXT NOT NULL,
        package_id INTEGER,
        package_name TEXT NOT NULL,
        amount REAL NOT NULL,
        player_info TEXT NOT NULL,
        payment_method TEXT NOT NULL,
        payment_number TEXT NOT NULL,
        sender_number TEXT NOT NULL,
        trx_id TEXT NOT NULL,
        customer_whatsapp TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending',
        admin_note TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 6. Banners
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS banners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        subtitle TEXT,
        image_url TEXT NOT NULL,
        link_url TEXT DEFAULT '#',
        badge TEXT,
        sort_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )
    """)

    # 7. Site Settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Seed Admin (admin / admin123)
    cursor.execute("SELECT id FROM admins WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO admins (username, password_hash) VALUES (?, ?)", 
                       ("admin", hash_password("admin123")))

    # Seed Payment Methods with requested numbers (bKash & Nagad: 01925915240)
    cursor.execute("SELECT COUNT(*) as cnt FROM payment_methods")
    if cursor.fetchone()['cnt'] == 0:
        methods = [
            (
                "bKash",
                "Personal (Send Money)",
                "01925915240",
                "১. আপনার বিকাশ অ্যাপ অথবা *247# ডায়াল করে 'Send Money' সিলেক্ট করুন।\n২. প্রাপক নাম্বারে দিন: 01925915240\n৩. প্যাকেজের সঠিক এমাউন্ট পাঠান।\n৪. সফল ট্রানজেকশনের পর TrxID এবং আপনার বিকাশ নাম্বার নিচে দিন।",
                "#e2136e",
                1
            ),
            (
                "Nagad",
                "Personal (Send Money)",
                "01925915240",
                "১. আপনার নগদ অ্যাপ অথবা *167# ডায়াল করে 'Send Money' সিলেক্ট করুন।\n২. প্রাপক নাম্বারে দিন: 01925915240\n৩. প্যাকেজের সঠিক এমাউন্ট পাঠান।\n৪. সফল ট্রানজেকশনের পর TrxID এবং আপনার নগদ নাম্বার নিচে দিন।",
                "#f7941d",
                2
            ),
            (
                "Rocket",
                "Personal (Send Money)",
                "01925915240",
                "১. রকেট অ্যাপ অথবা *322# ডায়াল করে Send Money করুন।\n২. একাউন্ট নাম্বার: 01925915240\n৩. সফল ট্রানজেকশনের TrxID নিচে দিন।",
                "#8c3494",
                3
            )
        ]
        cursor.executemany("""
        INSERT INTO payment_methods (name, type, number, instructions, logo_color, sort_order)
        VALUES (?, ?, ?, ?, ?, ?)
        """, methods)

    # Seed Games (BeepBazaar style multi-game platform)
    cursor.execute("SELECT COUNT(*) as cnt FROM games")
    if cursor.fetchone()['cnt'] == 0:
        default_games = [
            (
                "free-fire-bd",
                "Free Fire (UID Top-Up)",
                "Battle Royale",
                "https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=600&q=80",
                "⚡ সবচেয়ে জনপ্রিয়",
                "uid",
                "Player ID (UID)",
                "আপনার ফ্রি ফায়ার প্লেয়ার আইডি দিন (e.g. 192837465)",
                "গেমে গিয়ে আপনার প্রোফাইল আইকনে ক্লিক করলেই UID পেয়ে যাবেন। ভুল আইডি দিলে ডায়মন্ড যাবে না।",
                "বাংলাদেশ সার্ভারের জন্য ১০০% দ্রুত ও নিরাপদ ফ্রি ফায়ার ডায়মন্ড টপ-আপ। অর্ডার নিশ্চিত করার ২-৫ মিনিটের মধ্যে আপনার আইডিতে ডায়মন্ড চলে যাবে।",
                "২ - ৫ মিনিট",
                1
            ),
            (
                "pubg-mobile",
                "PUBG Mobile (Global UC)",
                "Battle Royale",
                "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?auto=format&fit=crop&w=600&q=80",
                "🔥 Instant UC",
                "uid",
                "Player ID (Character ID)",
                "আপনার পাবজি ক্যারেক্টার আইডি দিন (e.g. 5123456789)",
                "PUBG Mobile এ প্রোফাইলে ঢুকে উপরের ডানপাশে দেখতে পাবেন ক্যারেক্টার আইডি।",
                "PUBG Mobile Global সার্ভারের জন্য দ্রুততম UC টপ-আপ। রয়্যাল পাস বা ক্রেট ওপেনিং এর জন্য সেরা অফার।",
                "৫ - ১০ মিনিট",
                2
            ),
            (
                "free-fire-id-pass",
                "Free Fire (ID Password / In-Game)",
                "Battle Royale",
                "https://images.unsplash.com/photo-1511512578047-dfb367046420?auto=format&fit=crop&w=600&q=80",
                "💎 বিশেষ অফার",
                "id_pass",
                "Facebook / Gmail আইডি ও পাসওয়ার্ড + ব্যাকআপ কোড",
                "আইডি ও পাসওয়ার্ড সঠিকভাবে দিন",
                "2-Step Verification বন্ধ রাখুন অথবা ৩টি ব্যাকআপ কোড প্রদান করুন যাতে সহজে লগইন করা যায়।",
                "ইন-গেম স্পেশাল এয়ারড্রপ, লেভেল আপ পাস এবং ডিসকাউন্ট বান্ডেলের জন্য ইন-গেম টপ-আপ।",
                "১০ - ৩০ মিনিট",
                3
            ),
            (
                "mobile-legends",
                "Mobile Legends: Bang Bang",
                "MOBA",
                "https://images.unsplash.com/photo-1563089145-599997674d42?auto=format&fit=crop&w=600&q=80",
                "⭐ ডায়মন্ড + পাস",
                "uid_zone",
                "User ID & Zone ID",
                "User ID (Zone ID) e.g. 12345678 (1234)",
                "প্রোফাইলে গিয়ে Nickname এর নিচে User ID এবং ব্র্যাকেটে Zone ID দেখতে পাবেন। যেমন: 12345678 (1234)",
                "মোবাইল লিজেন্ডস ডায়মন্ড এবং টুইলাইট পাস পান সর্বনিম্ন রেটে।",
                "২ - ১০ মিনিট",
                4
            ),
            (
                "call-of-duty-mobile",
                "Call of Duty: Mobile (CP)",
                "FPS Action",
                "https://images.unsplash.com/photo-1579373903781-fd5c0c30c4cd?auto=format&fit=crop&w=600&q=80",
                "🎯 হট ডিল",
                "uid",
                "Player UID",
                "আপনার সিওডি প্লেয়ার আইডি দিন",
                "ইন-গেম সেটিংস এ লিগ্যাল অ্যান্ড প্রাইভেসি সেকশনে UID পাবেন।",
                "CODM সিজন ব্যাটল পাস এবং লাকি ড্র এর জন্য দ্রুততম CP টপ-আপ।",
                "১০ - ২০ মিনিট",
                5
            ),
            (
                "clash-of-clans",
                "Clash of Clans (Gems)",
                "Strategy",
                "https://images.unsplash.com/photo-1550745165-9bc0b252726f?auto=format&fit=crop&w=600&q=80",
                "🛡️ গোল্ড পাস",
                "uid",
                "Player Tag (#)",
                "আপনার প্লেয়ার ট্যাগ দিন (e.g. #9ABC123)",
                "ক্ল্যাশ অফ ক্ল্যান্স প্রোফাইলে আপনার নামের নিচে # দিয়ে শুরু হওয়া কোডটি দিন।",
                "ক্ল্যাশ অফ ক্ল্যান্স জেমস এবং গোল্ড পাস পান সবচেয়ে কম মূল্যে।",
                "৫ - ১৫ মিনিট",
                6
            ),
            (
                "google-play-card",
                "Google Play Gift Card (US)",
                "Gift Cards",
                "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?auto=format&fit=crop&w=600&q=80",
                "🎁 ডিজিটাল কোড",
                "email",
                "আপনার ডেলিভারি ইমেইল / হোয়াটসঅ্যাপ",
                "ইমেইল অথবা হোয়াটসঅ্যাপ নম্বর দিন",
                "কোডটি অর্ডার সম্পন্ন হওয়ার পর হোয়াটসঅ্যাপ এবং ট্র্যাকিং পেজে দেয়া হবে।",
                "ইউএস গুগল প্লে গিফট কার্ড দিয়ে যেকোনো গেম ও অ্যাপস পারচেজ করুন সহজেই।",
                "১০ - ২০ মিনিট",
                7
            ),
            (
                "honor-of-kings",
                "Honor of Kings (Tokens)",
                "MOBA",
                "https://images.unsplash.com/photo-1552824796-015886616a6d?auto=format&fit=crop&w=600&q=80",
                "👑 নিউ গেম",
                "uid",
                "Player UID",
                "আপনার HoK প্লেয়ার আইডি দিন",
                "ইন-গেম প্রোফাইল সেটিংসে প্লেয়ার UID দেখতে পাবেন।",
                "Honor of Kings গ্লোবাল সার্ভার টোকেন টপ আপ।",
                "৫ - ১৫ মিনিট",
                8
            )
        ]
        
        for g in default_games:
            cursor.execute("""
            INSERT INTO games (slug, name, category, image_url, badge, input_type, input_label, input_placeholder, instructions, description, delivery_time, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, g)

    # Seed Packages for Free Fire BD
    cursor.execute("SELECT COUNT(*) as cnt FROM packages")
    if cursor.fetchone()['cnt'] == 0:
        # Get game IDs
        cursor.execute("SELECT id, slug FROM games")
        game_map = {row['slug']: row['id'] for row in cursor.fetchall()}

        ff_id = game_map.get("free-fire-bd")
        if ff_id:
            ff_pkgs = [
                (ff_id, "25 Diamonds", "diamond", 22.0, 25.0, None, 1, 1),
                (ff_id, "50 Diamonds", "diamond", 40.0, 45.0, None, 1, 2),
                (ff_id, "115 Diamonds", "diamond", 85.0, 95.0, "🔥 হট চয়েস", 1, 3),
                (ff_id, "240 Diamonds", "diamond", 170.0, 185.0, "+10 বোনাস", 1, 4),
                (ff_id, "355 Diamonds", "diamond", 250.0, 275.0, None, 1, 5),
                (ff_id, "610 Diamonds", "diamond", 415.0, 450.0, "⚡ সেরা মূল্য", 1, 6),
                (ff_id, "1240 Diamonds", "diamond", 820.0, 900.0, "💎 মেগা প্যাক", 1, 7),
                (ff_id, "2530 Diamonds", "diamond", 1650.0, 1800.0, "👑 ভিআইপি", 1, 8),
                (ff_id, "Weekly Membership", "special", 185.0, 210.0, "⭐ উইকলি", 1, 9),
                (ff_id, "Monthly Membership", "special", 870.0, 980.0, "🏆 মান্থলি", 1, 10),
                (ff_id, "Level Up Pass", "special", 170.0, 195.0, "🆙 লেভেল আপ", 1, 11),
                (ff_id, "Weekly Lite", "special", 55.0, 65.0, None, 1, 12),
            ]
            cursor.executemany("""
            INSERT INTO packages (game_id, name, category, price, original_price, badge, in_stock, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ff_pkgs)

        pubg_id = game_map.get("pubg-mobile")
        if pubg_id:
            pubg_pkgs = [
                (pubg_id, "60 UC", "uc", 95.0, 105.0, None, 1, 1),
                (pubg_id, "325 UC + 30 Bonus", "uc", 460.0, 500.0, "🔥 জনপ্রিয়", 1, 2),
                (pubg_id, "660 UC + 60 Bonus", "uc", 910.0, 990.0, "⚡ রয়্যাল পাস", 1, 3),
                (pubg_id, "1800 UC", "uc", 2390.0, 2550.0, "💎 বিগ প্যাক", 1, 4),
                (pubg_id, "3850 UC", "uc", 4750.0, 5100.0, "👑 মেগা UC", 1, 5),
                (pubg_id, "8100 UC", "uc", 9650.0, 10500.0, "🔥 আল্টিমেট", 1, 6),
            ]
            cursor.executemany("""
            INSERT INTO packages (game_id, name, category, price, original_price, badge, in_stock, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, pubg_pkgs)

        ml_id = game_map.get("mobile-legends")
        if ml_id:
            ml_pkgs = [
                (ml_id, "86 Diamonds", "diamond", 155.0, 175.0, None, 1, 1),
                (ml_id, "172 Diamonds", "diamond", 310.0, 340.0, "🔥 বেস্ট", 1, 2),
                (ml_id, "257 Diamonds", "diamond", 460.0, 500.0, None, 1, 3),
                (ml_id, "706 Diamonds", "diamond", 1240.0, 1350.0, "⚡ মেগা", 1, 4),
                (ml_id, "Weekly Diamond Pass", "pass", 215.0, 240.0, "⭐ উইকলি পাস", 1, 5),
                (ml_id, "Twilight Pass", "pass", 1150.0, 1300.0, "👑 টুইলাইট", 1, 6),
            ]
            cursor.executemany("""
            INSERT INTO packages (game_id, name, category, price, original_price, badge, in_stock, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ml_pkgs)

        ff_id_pass = game_map.get("free-fire-id-pass")
        if ff_id_pass:
            ff_id_pkgs = [
                (ff_id_pass, "Special Airdrop 90 Tk", "airdrop", 90.0, 100.0, "🔥 এয়ারড্রপ", 1, 1),
                (ff_id_pass, "Special Airdrop 190 Tk", "airdrop", 190.0, 210.0, "🔥 এয়ারড্রপ", 1, 2),
                (ff_id_pass, "Level Up Pass (In-Game)", "pass", 160.0, 180.0, "🆙 লেভেল আপ", 1, 3),
                (ff_id_pass, "Evo Access 30 Days", "special", 240.0, 270.0, "⚡ ইভো পাস", 1, 4),
            ]
            cursor.executemany("""
            INSERT INTO packages (game_id, name, category, price, original_price, badge, in_stock, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ff_id_pkgs)

        gplay_id = game_map.get("google-play-card")
        if gplay_id:
            gplay_pkgs = [
                (gplay_id, "$5 USD Gift Card", "card", 620.0, 680.0, None, 1, 1),
                (gplay_id, "$10 USD Gift Card", "card", 1220.0, 1320.0, "🔥 মোস্ট পপুলার", 1, 2),
                (gplay_id, "$15 USD Gift Card", "card", 1820.0, 1950.0, None, 1, 3),
                (gplay_id, "$25 USD Gift Card", "card", 2990.0, 3200.0, "⚡ বিগ সেভার", 1, 4),
            ]
            cursor.executemany("""
            INSERT INTO packages (game_id, name, category, price, original_price, badge, in_stock, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, gplay_pkgs)

    # Seed Banners
    cursor.execute("SELECT COUNT(*) as cnt FROM banners")
    if cursor.fetchone()['cnt'] == 0:
        default_banners = [
            (
                "Free Fire Bangladesh UID Instant Topup",
                "সেরা রেটে ২-৫ মিনিটে ইনস্ট্যান্ট ডায়মন্ড ডেলিভারি!",
                "https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=1200&q=80",
                "/game/free-fire-bd",
                "🔥 হট অফার",
                1
            ),
            (
                "PUBG Mobile Global UC Flash Sale",
                "রয়্যাল পাস ও ক্রেট ওপেনিং এর জন্য সর্বনিম্ন রেটে UC নিন!",
                "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?auto=format&fit=crop&w=1200&q=80",
                "/game/pubg-mobile",
                "⚡ ফ্ল্যাশ সেল",
                2
            ),
            (
                "Mobile Legends Weekly Diamond Pass",
                "উইকলি ডায়মন্ড পাস নিন আকর্ষণীয় ক্যাশব্যাক অফারে!",
                "https://images.unsplash.com/photo-1563089145-599997674d42?auto=format&fit=crop&w=1200&q=80",
                "/game/mobile-legends",
                "⭐ স্পেশাল",
                3
            )
        ]
        cursor.executemany("""
        INSERT INTO banners (title, subtitle, image_url, link_url, badge, sort_order)
        VALUES (?, ?, ?, ?, ?, ?)
        """, default_banners)

    # Seed Site Settings (Numbers requested: 01925915240)
    default_settings = {
        "site_name": "Retro Topup",
        "tagline": "Bangladesh's Most Trusted & Fastest Gaming Topup Platform",
        "site_notice": "⚡ Retro Topup এ স্বাগতম! বিকাশ ও নগদ এ পেমেন্ট করে তাৎক্ষণিক ডায়মন্ড ও ইউসি টপ-আপ নিন। হেল্প ও সাপোর্টের জন্য সরাসরি WhatsApp (01925915240) এ যোগাযোগ করুন।",
        "whatsapp_number": "01925915240",
        "support_phone": "01925915240",
        "bkash_number": "01925915240",
        "nagad_number": "01925915240",
        "rocket_number": "01925915240",
        "hero_title": "RETRO TOPUP - GAMING TOP-UP BD",
        "hero_subtitle": "ফ্রি ফায়ার, পাবজি, মোবাইল লিজেন্ডস সহ সকল গেমের ডায়মন্ড ও ইউসি টপ-আপ করুন চোখের পলকে!",
        "currency_symbol": "৳",
        "delivery_time": "২ - ১০ মিনিট",
        "working_hours": "২৪/৭ সার্বক্ষণিক সেবা",
        "contact_email": "support@retrotopup.com",
        "facebook_page": "https://facebook.com",
        "youtube_channel": "https://youtube.com",
        "telegram_group": "https://telegram.org"
    }
    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()

def get_setting(key: str, default: str = "") -> str:
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else default

def get_all_settings() -> dict:
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {row['key']: row['value'] for row in rows}

def set_setting(key: str, value: str):
    conn = get_db()
    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?", (key, value, value))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Retro Topup database successfully initialized!")
