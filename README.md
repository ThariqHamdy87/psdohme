# HME Portal - Main Database & SK Pengurus Dashboard ⚡🎓

Aplikasi web berbasis **Python Flask** & **SQLite** untuk manajemen data pokok anggota dan Surat Keputusan (SK) Pengurus **Himpunan Mahasiswa Elektro (HME)**.

---

## 🔑 Informasi Login Kahim

| Field | Nilai | Keterangan |
| :--- | :--- | :--- |
| **URL Login** | `http://localhost:5000/login` | Portal masuk Ketua Himpunan |
| **Username** | `kahim` | Akun Kahim |
| **Password** | `HME` | Password login default |

---

## 📋 Skema Main Database ([schema.sql](file:///c:/Users/Thariq%20M.%20Hamdy/OneDrive/Documents/web%20hme/schema.sql))

Data anggota **tidak lagi dimasukkan dari backend**. Database diinisialisasi bersih (0 data anggota) dan seluruh data pengurus dimasukkan dari **sisi depan (frontend / user)**.

### Struktur Kolom Tabel `anggota`:
1. **`nama`** — Nama lengkap pengurus/mahasiswa
2. **`nim`** — Nomor Induk Mahasiswa (Unique)
3. **`jabatan`** — Jabatan amanah di kepengurusan HME
4. **`golongan`** — Golongan hierarki kepengurusan (Otomatis ditentukan dari jabatan)
5. **`nomor_ab`** — Nomor Anggota Biasa resmi HME (Unique)
6. **`no_sk`** — Nomor Surat Keputusan pengangkatan pengurus

---

## ⚡ Klasifikasi Golongan Otomatis

Sistem secara otomatis mengelompokkan pengurus ke dalam golongannya berdasarkan jabatan:

- **Golongan I (Pengurus Inti)**:
  Kahim (Ketua Himpunan), Wakahim (Wakil Ketua), Sekretaris Umum, Bendahara Umum.
- **Golongan II (Ketua Divisi)**:
  Ketua Divisi IPTEK, Ketua Divisi PSDM, Ketua Divisi Humas, Kadiv, Koordinator, Kepala Biro.
- **Golongan III (Staf Divisi)**:
  Staf Divisi, Anggota Divisi, Staf Ahli.
- **Golongan IV (Anggota Biasa)**:
  Anggota Biasa (AB) HME umum.

---

## 🚀 Cara Memasukkan SK Pengurus dari Depan (Frontend)

1. **Upload Berkas PDF SK Pengurus**:
   - Di dashboard utama, tarik (*drag & drop*) berkas PDF SK Pengurus ke area unggah.
   - Klik **"Proses & Masukkan ke Main Database"**.
   - Sistem membaca Nama, NIM, Jabatan, Nomor AB, mengklasifikasi golongannya secara otomatis, dan menyimpannya langsung ke database SQLite.
   - Anda juga dapat mengklik tombol **"Unduh Contoh PDF SK"** untuk mencoba berkas SK contoh siap upload.

2. **Input Pengurus Manual dari Depan**:
   - Klik tombol **"Input Pengurus Manual"** di dashboard.
   - Masukkan Nama, NIM, Jabatan, Nomor AB, dan Nomor SK.
   - Golongan dapat otomatis terdeteksi atau dipilih manual dari dropdown.

3. **Filter & Analisis Data**:
   - Filter seketika berdasarkan Golongan (Golongan I, II, III, IV).
   - Pencarian live berdasarkan Nama, NIM, Jabatan, atau Nomor AB.
   - Ekspor laporan ke **CSV**.
