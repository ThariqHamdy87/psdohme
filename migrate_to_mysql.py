import sqlite3
import pymysql

def init_mysql():
    mconn = pymysql.connect(
        host='127.0.0.1',
        port=3306,
        user='root',
        password='root',
        database='hme_db',
        autocommit=True
    )
    mcur = mconn.cursor()

    mcur.execute("DROP TABLE IF EXISTS anggota")
    mcur.execute("DROP TABLE IF EXISTS users")

    mcur.execute("""
    CREATE TABLE users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL,
        nama_lengkap VARCHAR(100) DEFAULT 'Ketua Himpunan',
        role VARCHAR(20) DEFAULT 'kahim',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """)

    mcur.execute("""
    CREATE TABLE anggota (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nama VARCHAR(150) NOT NULL,
        nim VARCHAR(30) NOT NULL UNIQUE,
        jabatan VARCHAR(100) NOT NULL,
        golongan VARCHAR(60) NOT NULL,
        nomor_ab VARCHAR(50) NOT NULL,
        no_sk VARCHAR(100) DEFAULT 'SK-HME-2026/01',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_nim (nim),
        INDEX idx_nomor_ab (nomor_ab),
        INDEX idx_golongan (golongan)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """)

    mcur.execute(
        "INSERT INTO users (username, password, nama_lengkap, role) VALUES (%s, %s, %s, %s)",
        ('kahim', 'HME', 'Ketua Himpunan Mahasiswa Elektro', 'kahim')
    )

    try:
        sconn = sqlite3.connect('database.db')
        scur = sconn.cursor()
        scur.execute('SELECT nama, nim, jabatan, golongan, nomor_ab, no_sk FROM anggota')
        rows = scur.fetchall()
        for r in rows:
            mcur.execute("""
                INSERT INTO anggota (nama, nim, jabatan, golongan, nomor_ab, no_sk)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE nama=VALUES(nama), jabatan=VALUES(jabatan), golongan=VALUES(golongan), nomor_ab=VALUES(nomor_ab), no_sk=VALUES(no_sk)
            """, r)
        print(f"Migrated {len(rows)} members from SQLite to MySQL successfully!")
        sconn.close()
    except Exception as e:
        print("Note on SQLite migration:", e)

    mcur.execute("SELECT COUNT(*) FROM anggota")
    print("Total rows in MySQL anggota table:", mcur.fetchone()[0])
    mconn.close()

if __name__ == '__main__':
    init_mysql()
