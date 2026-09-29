import pymysql
import os

MYSQL_CONFIG = {
    'host': os.environ.get('MYSQL_HOST', '127.0.0.1'),
    'port': int(os.environ.get('MYSQL_PORT', 3306)),
    'user': os.environ.get('MYSQL_USER', 'root'),
    'password': os.environ.get('MYSQL_PASSWORD', 'root'),
    'charset': 'utf8mb4',
    'autocommit': True
}

SCHEMA_FILE = "schema.sql"

def init_database():
    print(f"Menginisialisasi MySQL database: hme_db...")
    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
    except Exception:
        # Fallback coba tanpa password jika disetel kosong di HeidiSQL
        alt_config = dict(MYSQL_CONFIG)
        alt_config['password'] = ''
        conn = pymysql.connect(**alt_config)

    cursor = conn.cursor()
    
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    # Jalankan query-query terpisah
    statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
    for stmt in statements:
        if stmt:
            cursor.execute(stmt)

    cursor.execute("USE hme_db")
    cursor.execute("SELECT COUNT(*) FROM users;")
    user_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM anggota;")
    anggota_count = cursor.fetchone()[0]
    
    conn.close()
    print("Sukses! MySQL hme_db berhasil disiapkan:")
    print(f" - {user_count} user login")
    print(f" - {anggota_count} data anggota HME")

if __name__ == "__main__":
    init_database()
