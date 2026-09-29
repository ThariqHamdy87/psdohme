import pymysql
import pymysql.cursors
import os
import re
import io
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from pypdf import PdfReader

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Konfigurasi Koneksi MySQL (Database: hme_db)
# Kompatibel dengan HeidiSQL, XAMPP, dan WSL MySQL
MYSQL_CONFIG = {
    'host': os.environ.get('MYSQL_HOST', '127.0.0.1'),
    'port': int(os.environ.get('MYSQL_PORT', 3306)),
    'user': os.environ.get('MYSQL_USER', 'root'),
    'password': os.environ.get('MYSQL_PASSWORD', 'root'),
    'database': os.environ.get('MYSQL_DB', 'hme_db'),
    'charset': 'utf8mb4',
    'autocommit': True,
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db():
    try:
        return pymysql.connect(**MYSQL_CONFIG)
    except Exception:
        # Fallback coba tanpa password jika diatur tanpa password di HeidiSQL/XAMPP
        alt_config = dict(MYSQL_CONFIG)
        alt_config['password'] = ''
        return pymysql.connect(**alt_config)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Silakan login terlebih dahulu untuk mengakses dashboard.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# -----------------------------------------------------------------------------
# KLASIFIKASI GOLONGAN OTOMATIS BERDASARKAN JABATAN
# -----------------------------------------------------------------------------
def classify_golongan(jabatan):
    """
    Menentukan Golongan Pengurus secara otomatis berdasarkan nama jabatan:
    - Golongan I   : Pengurus Inti (Kahim, Wakahim, Sekum, Bendum)
    - Golongan II  : Ketua Divisi / Kepala Departemen / Kepala Biro
    - Golongan III : Staf Divisi / Anggota Divisi
    - Golongan IV  : Anggota Biasa (AB)
    """
    if not jabatan:
        return 'Golongan IV (Anggota Biasa)'
    
    j = jabatan.lower().strip()
    
    # Golongan I: Pengurus Inti
    if any(k in j for k in [
        'ketua himpunan', 'kahim', 'wakil ketua', 'wakahim', 
        'sekretaris umum', 'sekum', 'sekretaris 1', 'sekretaris 2', 
        'bendahara umum', 'bendum', 'bendahara 1', 'bendahara 2', 
        'pengurus inti', 'bph inti'
    ]):
        return 'Golongan I (Pengurus Inti)'
        
    # Golongan II: Ketua Divisi / Kadiv
    elif any(k in j for k in [
        'ketua divisi', 'kadiv', 'kepala departemen', 'kadep', 
        'ketua bidang', 'kabid', 'kepala biro', 'kabiro', 'koordinator'
    ]):
        return 'Golongan II (Ketua Divisi)'
        
    # Golongan III: Staf Divisi
    elif any(k in j for k in [
        'staf', 'staff', 'subbidang', 'bidang', 'divisi', 'departemen', 'biro', 'anggota divisi', 'medpub'
    ]):
        return 'Golongan III (Staf Divisi)'
        
    # Golongan IV: Anggota Biasa
    else:
        return 'Golongan IV (Anggota Biasa)'

# -----------------------------------------------------------------------------
# PDF PARSER: EKSTRAKSI DATA SK PENGURUS DARI DEPAN (PATOKAN HANYA PADA TABEL)
# -----------------------------------------------------------------------------
import pdfplumber

def parse_sk_pdf(file_stream, custom_no_sk=''):
    """
    Mengekstrak data pengurus HANYA dari tabel yang ada di berkas PDF SK.
    Mengabaikan Kop Surat, alamat, nomor telepon/kontak, preamble, dan tanda tangan.
    """
    file_bytes = file_stream.read()
    extracted_members = []
    detected_no_sk = custom_no_sk.strip() if custom_no_sk else ''

    # 1. Cari Nomor SK dari dokumen jika belum diisi custom
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        for page in reader.pages:
            t = page.extract_text() or ''
            for line in t.split('\n'):
                line_clean = line.replace('\xa0', ' ').strip()
                if not detected_no_sk:
                    # Pola umum Nomor SK (misal: 154/P/SK/HME FPTI UPI/V/2026 atau Nomor: ...)
                    sk_m = re.search(r'(?:nomor|no)?\s*[:=.]?\s*([0-9]+/[A-Za-z0-9\/\.\-_ ]+HME[A-Za-z0-9\/\.\-_ ]*)', line_clean, re.I)
                    if not sk_m:
                        sk_m = re.search(r'(?:nomor|no)\s*[:=.]?\s*([0-9A-Za-z\/\.\-_ ]+SK[0-9A-Za-z\/\.\-_ ]*)', line_clean, re.I)
                    if sk_m:
                        detected_no_sk = sk_m.group(1).strip()
                        break
    except Exception:
        pass

    if not detected_no_sk:
        detected_no_sk = 'SK-HME-2026/01'

    auto_ab_counter = 1

    # 2. METODE UTAMA: Ekstraksi murni berbasis tabel grafis (pdfplumber)
    # Teks di luar tabel (seperti Kop Surat, alamat Jl. Setiabudhi, nomor kontak HP) otomatis 100% diabaikan!
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    header_row_idx = -1
                    col_map = {}

                    # Cari baris kepala tabel (Header Row)
                    for r_idx, row in enumerate(table):
                        row_lower = [re.sub(r'\s+', ' ', str(cell or '').replace('\xa0', ' ').strip().lower()) for cell in row]

                        has_nama = any('nama' in c for c in row_lower)
                        has_nim = any('nim' in c or 'npm' in c for c in row_lower)
                        has_jabatan = any('jabatan' in c or 'amanah' in c or 'bidang' in c or 'posisi' in c for c in row_lower)

                        if has_nama or (has_nim and has_jabatan):
                            header_row_idx = r_idx
                            for c_idx, c in enumerate(row_lower):
                                if 'nama' in c:
                                    col_map['nama'] = c_idx
                                elif 'nim' in c or 'npm' in c:
                                    col_map['nim'] = c_idx
                                elif any(k in c for k in ['jabatan', 'amanah', 'bidang', 'posisi', 'subbidang']):
                                    col_map['jabatan'] = c_idx
                                elif any(k in c for k in ['nomor ab', 'no ab', 'no. ab', 'kode', 'id anggota']):
                                    col_map['nomor_ab'] = c_idx
                            break

                    # Jika tabel memiliki header yang valid
                    if header_row_idx != -1 and ('nama' in col_map or 'nim' in col_map):
                        for row in table[header_row_idx + 1:]:
                            if not row:
                                continue

                            nama_val = str(row[col_map['nama']] if 'nama' in col_map and col_map['nama'] < len(row) else '').strip()
                            nim_val = str(row[col_map['nim']] if 'nim' in col_map and col_map['nim'] < len(row) else '').strip()
                            jabatan_val = str(row[col_map['jabatan']] if 'jabatan' in col_map and col_map['jabatan'] < len(row) else '').strip()
                            ab_val = str(row[col_map['nomor_ab']] if 'nomor_ab' in col_map and col_map['nomor_ab'] < len(row) else '').strip()

                            # Bersihkan Nama
                            nama = re.sub(r'[\r\n]+', ' ', nama_val.replace('\xa0', ' ')).strip()
                            nama = re.sub(r'^\d+[\s\.\)\|\-]+', '', nama).strip()

                            # Ekstrak NIM
                            nim_m = re.search(r'\b([0-9]{6,15}|[A-Z][0-9]{6,12})\b', nim_val)
                            if not nim_m:
                                # Jika NIM berada di kolom nama karena formatting cell
                                nim_m = re.search(r'\b([0-9]{6,15}|[A-Z][0-9]{6,12})\b', nama)
                                if nim_m:
                                    nim = nim_m.group(1)
                                    nama = nama.replace(nim, '').strip()
                                else:
                                    continue
                            else:
                                nim = nim_m.group(1)

                            # Validasi: Tolak jika nomor telepon (misal diawali 08 dengan panjang >= 10)
                            if nim.startswith('08') and len(nim) >= 10:
                                continue

                            # Bersihkan Jabatan
                            jabatan = re.sub(r'[\r\n]+', ' ', jabatan_val.replace('\xa0', ' ')).strip()

                            # Ekstrak Nomor AB jika ada di kolom tersendiri atau kode di belakang jabatan (misal: 2024.08.011)
                            nomor_ab = ab_val.strip()
                            if not nomor_ab:
                                code_m = re.search(r'\b(AB[\s\-_]?HME[\s\-_0-9A-Za-z]+|\d{4}\.\d{2}\.\d{3})\b', jabatan, re.I)
                                if code_m:
                                    nomor_ab = code_m.group(1).replace(' ', '-')
                                    jabatan = jabatan.replace(code_m.group(0), '').strip()

                            if not nomor_ab:
                                nim_prefix = nim[:2] if len(nim) >= 2 else '24'
                                nomor_ab = f'AB-HME-{nim_prefix}-{auto_ab_counter:03d}'
                                auto_ab_counter += 1

                            # Hindari baris duplikat header atau kosong
                            if len(nama) >= 2 and not re.search(r'^(nama|nim\.?|no\.?|nomor|jabatan)$', nama, re.I):
                                golongan = classify_golongan(jabatan)
                                extracted_members.append({
                                    'nama': nama,
                                    'nim': nim,
                                    'jabatan': jabatan or 'Staf Pengurus HME',
                                    'golongan': golongan,
                                    'nomor_ab': nomor_ab,
                                    'no_sk': detected_no_sk
                                })
    except Exception as e:
        print('pdfplumber extraction warning:', e)

    # 3. METODE FALLBACK (Hanya jika dokumen tidak memiliki garis tabel biner):
    # Dibatasi KETAT: HANYA membaca baris SETELAH kepala tabel ditemukan!
    if not extracted_members:
        reader = PdfReader(io.BytesIO(file_bytes))
        lines = []
        for page in reader.pages:
            t = page.extract_text() or ''
            for l in t.split('\n'):
                c = l.replace('\xa0', ' ').strip()
                if c:
                    lines.append(c)

        is_inside_table = False
        for line in lines:
            line_lower = line.lower()

            # Mulai membaca HANYA jika baris adalah kepala tabel
            if ('nama' in line_lower and ('nim' in line_lower or 'jabatan' in line_lower)) or ('nim' in line_lower and 'jabatan' in line_lower):
                is_inside_table = True
                continue

            # Berhenti jika tabel telah selesai (bagian pengesahan / tanda tangan)
            if is_inside_table and re.search(r'^(ditetapkan di|mengetahui|ketua himpunan|tembusan)\b', line, re.I):
                is_inside_table = False
                break

            if not is_inside_table:
                # Lewati semua teks Kop Surat / Alamat / Preamble!
                continue

            # Lewati baris alamat / kontak
            if re.search(r'\b(jl\.|jalan|bandung|kontak|telepon|telp|email|fax|pos)\b', line, re.I):
                continue

            # Cari NIM
            nim_match = re.search(r'\b([0-9]{6,15}|[A-Z][0-9]{6,12})\b', line)
            if not nim_match:
                continue

            nim = nim_match.group(1)
            # Lewati nomor telepon
            if nim.startswith('08') and len(nim) >= 10:
                continue

            nim_idx = line.find(nim)
            left_part = line[:nim_idx].strip()
            right_part = line[nim_idx + len(nim):].strip()

            nama = re.sub(r'^\s*\d+[\s\.\)\|\-]+', '', left_part).strip()
            if not nama or re.search(r'^(nama|nim\.?|no\.?)$', nama, re.I):
                continue

            ab_match = re.search(r'\b(AB[\s\-_]?HME[\s\-_0-9A-Za-z]+|\d{4}\.\d{2}\.\d{3})\b', right_part, re.I)
            nomor_ab = ''
            jabatan = right_part

            if ab_match:
                nomor_ab = ab_match.group(1).replace(' ', '-')
                jabatan = right_part.replace(ab_match.group(0), '').strip()
            else:
                nim_prefix = nim[:2] if len(nim) >= 2 else '24'
                nomor_ab = f'AB-HME-{nim_prefix}-{auto_ab_counter:03d}'
                auto_ab_counter += 1

            jabatan = re.sub(r'^[\s\|\-]+|[\s\|\-]+$', '', jabatan).strip()

            if len(nama) >= 2 and not re.search(r'^(nama|nim|pengurus|surat|keputusan)$', nama, re.I):
                golongan = classify_golongan(jabatan)
                extracted_members.append({
                    'nama': nama,
                    'nim': nim,
                    'jabatan': jabatan or 'Staf Pengurus HME',
                    'golongan': golongan,
                    'nomor_ab': nomor_ab,
                    'no_sk': detected_no_sk
                })

    return extracted_members, detected_no_sk

# -----------------------------------------------------------------------------
# ROUTE OTENTIKASI KAHIM
# -----------------------------------------------------------------------------
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user'] = {
                'id': user['id'],
                'username': user['username'],
                'nama': user['nama_lengkap'],
                'role': user['role']
            }
            flash(f'Selamat datang kembali, {user["nama_lengkap"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Username atau password salah! Akses default: kahim / HME', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Anda telah berhasil logout dari sistem.', 'info')
    return redirect(url_for('login'))

# -----------------------------------------------------------------------------
# ROUTE DASHBOARD UTAMA
# -----------------------------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    cursor = conn.cursor()

    # Ambil data anggota dari Main Database
    cursor.execute("SELECT * FROM anggota ORDER BY id ASC")
    anggota_list = cursor.fetchall()

    # Metrik Golongan & Statistik
    total_anggota = len(anggota_list)
    
    cursor.execute("SELECT COUNT(*) AS c FROM anggota WHERE golongan LIKE %s", ('%Golongan I%',))
    total_gol_1 = cursor.fetchone()['c']

    cursor.execute("SELECT COUNT(*) AS c FROM anggota WHERE golongan LIKE %s", ('%Golongan II%',))
    total_gol_2 = cursor.fetchone()['c']

    cursor.execute("SELECT COUNT(*) AS c FROM anggota WHERE golongan LIKE %s", ('%Golongan III%',))
    total_gol_3 = cursor.fetchone()['c']

    cursor.execute("SELECT COUNT(*) AS c FROM anggota WHERE golongan LIKE %s", ('%Golongan IV%',))
    total_gol_4 = cursor.fetchone()['c']

    cursor.execute("SELECT COUNT(DISTINCT no_sk) AS c FROM anggota WHERE no_sk IS NOT NULL AND no_sk != ''")
    total_sk = cursor.fetchone()['c']

    conn.close()

    return render_template(
        'dashboard.html',
        user=session.get('user'),
        anggota=anggota_list,
        total_anggota=total_anggota,
        total_gol_1=total_gol_1,
        total_gol_2=total_gol_2,
        total_gol_3=total_gol_3,
        total_gol_4=total_gol_4,
        total_sk=total_sk
    )

# -----------------------------------------------------------------------------
# INPUT SK DARI DEPAN (UPLOAD BERKAS SK PDF)
# -----------------------------------------------------------------------------
@app.route('/sk/upload', methods=['POST'])
@login_required
def upload_sk():
    if 'sk_file' not in request.files:
        flash('Silakan pilih berkas PDF SK Pengurus terlebih dahulu.', 'warning')
        return redirect(url_for('dashboard'))

    file = request.files['sk_file']
    if file.filename == '':
        flash('Belum ada berkas PDF yang dipilih.', 'warning')
        return redirect(url_for('dashboard'))

    if not file.filename.lower().endswith('.pdf'):
        flash('Berkas SK harus berformat PDF (.pdf)', 'danger')
        return redirect(url_for('dashboard'))

    custom_no_sk = request.form.get('custom_no_sk', '').strip()

    try:
        members, no_sk = parse_sk_pdf(file.stream, custom_no_sk)

        if not members:
            flash('Berkas PDF terbaca, namun tidak ditemukan tabel daftar pengurus berisikan Nama & NIM. Silakan cek format berkas atau input manual.', 'warning')
            return redirect(url_for('dashboard'))

        conn = get_db()
        cursor = conn.cursor()
        inserted_count = 0
        skipped_count = 0

        for m in members:
            try:
                cursor.execute(
                    """
                    INSERT INTO anggota (nama, nim, jabatan, golongan, nomor_ab, no_sk)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (m['nama'], m['nim'], m['jabatan'], m['golongan'], m['nomor_ab'], m['no_sk'])
                )
                inserted_count += 1
            except (pymysql.IntegrityError, pymysql.err.IntegrityError):
                # Duplikasi NIM atau Nomor AB diabaikan / update
                skipped_count += 1

        conn.close()

        if inserted_count > 0:
            flash(f'Sukses! Sebanyak {inserted_count} pengurus dari SK "{no_sk}" berhasil dimasukkan ke Main Database beserta golongannya.', 'success')
            if skipped_count > 0:
                flash(f'Catatan: {skipped_count} data dilewati karena NIM atau Nomor AB sudah terdaftar sebelumnya.', 'info')
        else:
            flash('Seluruh data pada SK tersebut sudah ada di Main Database sebelumnya.', 'info')

    except Exception as e:
        flash(f'Gagal memproses berkas PDF SK: {str(e)}', 'danger')

    return redirect(url_for('dashboard'))

# -----------------------------------------------------------------------------
# INPUT SK DARI DEPAN (FORM INPUT PENGURUS MANUAL)
# -----------------------------------------------------------------------------
@app.route('/anggota/add', methods=['POST'])
@login_required
def add_anggota():
    nama = request.form.get('nama', '').strip()
    nim = request.form.get('nim', '').strip()
    jabatan = request.form.get('jabatan', '').strip()
    golongan = request.form.get('golongan', '').strip()
    nomor_ab = request.form.get('nomor_ab', '').strip()
    no_sk = request.form.get('no_sk', '').strip() or 'SK-HME-2026/01'

    if not nama or not nim or not jabatan or not nomor_ab:
        flash('Nama, NIM, Jabatan, dan Nomor AB wajib diisi!', 'warning')
        return redirect(url_for('dashboard'))

    # Jika golongan tidak dipilih manual, tentukan secara otomatis
    if not golongan or golongan == 'auto':
        golongan = classify_golongan(jabatan)

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO anggota (nama, nim, jabatan, golongan, nomor_ab, no_sk)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (nama, nim, jabatan, golongan, nomor_ab, no_sk)
        )
        flash(f'Pengurus "{nama}" berhasil didaftarkan ke Main Database sebagai {golongan}!', 'success')
    except (pymysql.IntegrityError, pymysql.err.IntegrityError) as e:
        err = str(e).lower()
        if 'nim' in err:
            flash(f'NIM "{nim}" sudah terdaftar di Main Database!', 'danger')
        elif 'nomor_ab' in err:
            flash(f'Nomor AB "{nomor_ab}" sudah dipakai anggota lain!', 'danger')
        else:
            flash(f'Gagal menyimpan: {str(e)}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/anggota/edit/<int:id>', methods=['POST'])
@login_required
def edit_anggota(id):
    nama = request.form.get('nama', '').strip()
    nim = request.form.get('nim', '').strip()
    jabatan = request.form.get('jabatan', '').strip()
    golongan = request.form.get('golongan', '').strip()
    nomor_ab = request.form.get('nomor_ab', '').strip()
    no_sk = request.form.get('no_sk', '').strip() or 'SK-HME-2026/01'

    if not nama or not nim or not jabatan or not nomor_ab:
        flash('Semua kolom wajib diisi lengkap!', 'warning')
        return redirect(url_for('dashboard'))

    if not golongan or golongan == 'auto':
        golongan = classify_golongan(jabatan)

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE anggota 
            SET nama = %s, nim = %s, jabatan = %s, golongan = %s, nomor_ab = %s, no_sk = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (nama, nim, jabatan, golongan, nomor_ab, no_sk, id)
        )
        flash(f'Data pengurus "{nama}" berhasil diperbarui!', 'success')
    except (pymysql.IntegrityError, pymysql.err.IntegrityError):
        flash('Gagal update: NIM atau Nomor AB bentrok dengan data pengurus lain.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/anggota/delete/<int:id>', methods=['POST'])
@login_required
def delete_anggota(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT nama FROM anggota WHERE id = %s", (id,))
    target = cursor.fetchone()

    if target:
        nama = target['nama']
        cursor.execute("DELETE FROM anggota WHERE id = %s", (id,))
        flash(f'Data pengurus "{nama}" telah dihapus dari Main Database.', 'info')
    else:
        flash('Data pengurus tidak ditemukan.', 'warning')

    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/anggota/reset', methods=['POST'])
@login_required
def reset_anggota():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM anggota")
    conn.close()
    flash('Seluruh data anggota di Main Database telah dikosongkan. Siap menerima input SK baru.', 'info')
    return redirect(url_for('dashboard'))

# -----------------------------------------------------------------------------
# DOWNLOAD CONTOH FILE PDF SK PENGURUS UNTUK TESTING DARI DEPAN
# -----------------------------------------------------------------------------
@app.route('/sk/download-sample')
@login_required
def download_sample_sk():
    """
    Menghasilkan file PDF contoh SK Pengurus HME 2026 yang siap diunggah langsung dari frontend.
    """
    pdf_content = """% Title
BT
/F1 15 Tf
85 780 Td
(SURAT KEPUTUSAN KETUA HIMPUNAN MAHASISWA ELEKTRO) Tj
0 -20 Td
/F1 11 Tf
55 0 Td
(NOMOR: SK-HME-2026/01 TENTANG SUSUNAN PENGURUS HME 2026) Tj
ET

% Table Grid Lines
0.8 w
0 0 0 RG
50 560 495 180 re S
50 715 m 545 715 l S
50 690 m 545 690 l S
50 665 m 545 665 l S
50 640 m 545 640 l S
50 615 m 545 615 l S
50 590 m 545 590 l S

% Vertical Lines (Col 1: Nama, Col 2: NIM, Col 3: Jabatan, Col 4: Nomor AB)
180 560 m 180 740 l S
270 560 m 270 740 l S
430 560 m 430 740 l S

% Header Row
BT
/F1 10.5 Tf
90 723 Td
(NAMA LENGKAP) Tj
105 0 Td
(NIM) Tj
75 0 Td
(JABATAN) Tj
75 0 Td
(NOMOR AB) Tj
ET

% Row 1: Thariq
BT
/F1 10 Tf
60 698 Td
(Thariq Maulana Hamdy) Tj
135 0 Td
(220501099) Tj
90 0 Td
(Ketua Himpunan) Tj
75 0 Td
(AB-HME-22-001) Tj
ET

% Row 2: Ahmad Fauzi
BT
/F1 10 Tf
60 673 Td
(Ahmad Fauzi Rahman) Tj
135 0 Td
(220501015) Tj
90 0 Td
(Wakil Ketua Himpunan) Tj
75 0 Td
(AB-HME-22-002) Tj
ET

% Row 3: Adinda
BT
/F1 10 Tf
60 648 Td
(Adinda Nur Aisyah) Tj
135 0 Td
(220501042) Tj
90 0 Td
(Sekretaris Umum) Tj
75 0 Td
(AB-HME-22-003) Tj
ET

% Row 4: Clarissa
BT
/F1 10 Tf
60 623 Td
(Clarissa Amanda) Tj
135 0 Td
(220501088) Tj
90 0 Td
(Bendahara Umum) Tj
75 0 Td
(AB-HME-22-004) Tj
ET

% Row 5: Davin
BT
/F1 10 Tf
60 598 Td
(Davin Rafif Mahendra) Tj
135 0 Td
(230501034) Tj
90 0 Td
(Ketua Divisi IPTEK) Tj
75 0 Td
(AB-HME-23-015) Tj
ET

% Row 6: Agus
BT
/F1 10 Tf
60 573 Td
(Agus) Tj
135 0 Td
(2305867) Tj
90 0 Td
(Staf Divisi IPTEK) Tj
75 0 Td
(AB-HME-23-045) Tj
ET
"""
    content_bytes = pdf_content.encode('latin1')
    stream_len = len(content_bytes)

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {stream_len} >>\nstream\n".encode('latin1') + content_bytes + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects):
        offsets.append(len(pdf))
        pdf.extend(f"{i+1} 0 obj\n".encode('latin1') + obj + b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode('latin1'))
    for off in offsets:
        pdf.extend(f"{off:010d} 00000 n \n".encode('latin1'))

    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode('latin1'))

    return send_file(
        io.BytesIO(pdf),
        mimetype='application/pdf',
        as_attachment=True,
        download_name='contoh_berkas_sk_pengurus_hme.pdf'
    )

if __name__ == '__main__':
    print("=" * 60)
    print(" HME PORTAL - FLASK SERVER RUNNING (ENGINE: MYSQL / MARIADB)")
    print(" Akses Login  : http://localhost:5000/login")
    print(" Akun Kahim   : username: kahim | password: HME")
    print(" Database     : MySQL 'hme_db' on 127.0.0.1:3306")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
