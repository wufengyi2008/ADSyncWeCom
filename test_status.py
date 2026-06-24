from database import Database

db = Database()
users = db.fetch_all('SELECT name, sync_status FROM users LIMIT 10')
for u in users:
    print(f"{u['name']}: {u['sync_status']}")