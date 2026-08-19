import aiosqlite
import random
import string

DB_NAME = "books_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                group_id INTEGER,
                title TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                name TEXT,
                pin TEXT UNIQUE
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS group_members (
                group_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (group_id, user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                category_id INTEGER,
                pages INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.commit()

# --- БАЗАНЫ ЖАНА ДАННЫЙЛАРДЫ ТАЗАЛОО ФУНКЦИЯЛАРЫ ---

async def clear_all_data():
    """Маалымат базасындагы бардык таблицаларды толугу менен тазалайт"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM users")
        await db.execute("DELETE FROM categories")
        await db.execute("DELETE FROM groups")
        await db.execute("DELETE FROM group_members")
        await db.execute("DELETE FROM logs")
        await db.commit()

async def clear_user_logs(user_id: int):
    """Бир гана ошол колдонуучунун окуган барактарынын тарыхын (логдорду) өчүрөт"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM logs WHERE user_id = ?", (user_id,))
        await db.commit()

async def clear_user_full_data(user_id: int):
    """
    Бир гана ушул колдонуучунун бардык данныеларын тазалайт:
    - Өзүнүн окуган барактар тарыхы (logs)
    - Өзүнүн гана категориялары (categories)
    - Топтордон чыгуусу (group_members)
    """
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM logs WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM categories WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM group_members WHERE user_id = ?", (user_id,))
        await db.commit()

# --- КОЛДОНУУЧУЛАР ЖАНА КАТЕГОРИЯЛАР ---

async def add_user(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (id, username, full_name) VALUES (?, ?, ?)",
            (user_id, username, full_name)
        )
        await db.commit()

async def create_user_category(user_id: int, title: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO categories (user_id, title) VALUES (?, ?)",
            (user_id, title)
        )
        await db.commit()

async def rename_category_by_title(user_id: int, old_title: str, new_title: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id FROM categories WHERE user_id = ? AND title = ?",
            (user_id, old_title)
        ) as cursor:
            cat = await cursor.fetchone()
            if not cat:
                return False
            
            await db.execute(
                "UPDATE categories SET title = ? WHERE id = ?",
                (new_title, cat[0])
            )
            await db.commit()
            return True

# --- ТОПТОР МЕНЕН ИШТӨӨ ---

async def generate_unique_pin(db):
    chars = string.ascii_uppercase + string.digits
    while True:
        pin = ''.join(random.choices(chars, k=6))
        async with db.execute("SELECT id FROM groups WHERE pin = ?", (pin,)) as cursor:
            if not await cursor.fetchone():
                return pin

async def create_group_with_categories(admin_id: int, group_name: str, category_names: list):
    async with aiosqlite.connect(DB_NAME) as db:
        pin = await generate_unique_pin(db)
        
        cursor = await db.execute(
            "INSERT INTO groups (admin_id, name, pin) VALUES (?, ?, ?)",
            (admin_id, group_name, pin)
        )
        group_id = cursor.lastrowid
        
        await db.execute(
            "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
            (group_id, admin_id)
        )
        
        for cat_name in category_names:
            c_title = cat_name.strip()
            if not c_title:
                continue
            await db.execute(
                "INSERT INTO categories (user_id, group_id, title) VALUES (?, ?, ?)",
                (admin_id, group_id, c_title)
            )
        await db.commit()
    return pin

async def join_group_by_pin(user_id: int, pin: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, admin_id FROM groups WHERE pin = ?", (pin.upper(),)) as cursor:
            group = await cursor.fetchone()
            if not group:
                return False, "❌ ПИН-код ката же табылган жок!"
            
            group_id, admin_id = group

        await db.execute(
            "INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?, ?)",
            (group_id, user_id)
        )
            
        async with db.execute(
            "SELECT title FROM categories WHERE group_id = ? AND user_id = ?",
            (group_id, admin_id)
        ) as cursor:
            admin_cats = await cursor.fetchall()
            
        for cat in admin_cats:
            c_title = cat[0]
            async with db.execute(
                "SELECT id FROM categories WHERE user_id = ? AND group_id = ? AND title = ?",
                (user_id, group_id, c_title)
            ) as check_cursor:
                if not await check_cursor.fetchone():
                    await db.execute(
                        "INSERT INTO categories (user_id, group_id, title) VALUES (?, ?, ?)",
                        (user_id, group_id, c_title)
                    )
        await db.commit()
        return True, "✅ Топтун категориялары ийгиликтүү кошулду!"

async def get_user_categories(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, title, group_id FROM categories WHERE user_id = ?", 
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()

# --- ЛОГДОР МЕНЕН ИШТӨӨ ---

async def log_pages(user_id: int, category_id: int, pages: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "INSERT INTO logs (user_id, category_id, pages) VALUES (?, ?, ?)",
            (user_id, category_id, pages)
        )
        await db.commit()
        return cursor.lastrowid

async def update_last_log(log_id: int, new_pages: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE logs SET pages = ? WHERE id = ?",
            (new_pages, log_id)
        )
        await db.commit()

async def delete_log(log_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "DELETE FROM logs WHERE id = ?",
            (log_id,)
        )
        await db.commit()

# --- СТАТИСТИКА ЖАНА ОТЧЕТТОР ---

async def get_monthly_category_summary(user_id: int, year: int, month: int):
    month_str = f"{year}-{month:02d}"
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('''
            SELECT c.id, c.title, COALESCE(SUM(l.pages), 0)
            FROM categories c
            LEFT JOIN logs l ON c.id = l.category_id 
                AND l.user_id = ? 
                AND strftime('%Y-%m', l.created_at) = ?
            WHERE c.user_id = ?
            GROUP BY c.id
        ''', (user_id, month_str, user_id)) as cursor:
            cats = await cursor.fetchall()

        async with db.execute('''
            SELECT COALESCE(SUM(pages), 0)
            FROM logs
            WHERE user_id = ? AND strftime('%Y-%m', created_at) = ?
        ''', (user_id, month_str)) as cursor:
            row = await cursor.fetchone()
            total = row[0] if row else 0

        return cats, total

async def get_category_logs_by_month(user_id: int, category_id: int, year: int, month: int):
    month_str = f"{year}-{month:02d}"
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT title FROM categories WHERE id = ?", (category_id,)) as cursor:
            cat_row = await cursor.fetchone()
            cat_title = cat_row[0] if cat_row else "Категория"

        async with db.execute('''
            SELECT strftime('%d.%m.%Y %H:%M', created_at), pages
            FROM logs
            WHERE user_id = ? AND category_id = ? AND strftime('%Y-%m', created_at) = ?
            ORDER BY id DESC
        ''', (user_id, category_id, month_str)) as cursor:
            logs = await cursor.fetchall()

        async with db.execute('''
            SELECT COALESCE(SUM(pages), 0)
            FROM logs
            WHERE user_id = ? AND category_id = ? AND strftime('%Y-%m', created_at) = ?
        ''', (user_id, category_id, month_str)) as cursor:
            row = await cursor.fetchone()
            total = row[0] if row else 0

        return cat_title, logs, total

# --- ДАТА АРАЛЫГЫ МЕНЕН ЭКСПОРТ КЫЛУУ ---

async def get_admin_excel_data_by_range(admin_id: int, start_date: str = None, end_date: str = None):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, name, pin FROM groups WHERE admin_id = ?", (admin_id,)) as cursor:
            groups = await cursor.fetchall()
        
        if not groups:
            return None

        result_groups = []
        for g_id, g_name, g_pin in groups:
            async with db.execute("SELECT id, title FROM categories WHERE group_id = ? AND user_id = ?", (g_id, admin_id)) as cursor:
                cats = await cursor.fetchall()
            
            async with db.execute('''
                SELECT u.full_name, u.username, u.id
                FROM group_members gm 
                JOIN users u ON gm.user_id = u.id 
                WHERE gm.group_id = ?
            ''', (g_id,)) as cursor:
                members = await cursor.fetchall()

            group_data = {
                'name': g_name,
                'pin': g_pin,
                'categories': [c[1] for c in cats],
                'rows': []
            }

            for m_name, m_user, m_id in members:
                row = {
                    'name': m_name,
                    'username': f"@{m_user}" if m_user else "жок",
                    'cats_pages': [],
                    'total': 0
                }
                m_total = 0
                for _, c_title in cats:
                    query = '''
                        SELECT SUM(l.pages) 
                        FROM logs l 
                        JOIN categories c ON l.category_id = c.id
                        WHERE l.user_id = ? AND c.title = ? AND c.group_id = ?
                    '''
                    params = [m_id, c_title, g_id]

                    if start_date and end_date:
                        query += " AND date(l.created_at) >= date(?) AND date(l.created_at) <= date(?)"
                        params.extend([start_date, end_date])

                    async with db.execute(query, params) as cursor:
                        p = (await cursor.fetchone())[0] or 0
                        row['cats_pages'].append(p)
                        m_total += p

                row['total'] = m_total
                group_data['rows'].append(row)

            result_groups.append(group_data)

        return result_groups
