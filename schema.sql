-- ============================================================================
-- MAIN DATABASE SCHEMA - HIMPUNAN MAHASISWA ELEKTRO (HME)
-- Database Engine: MySQL / MariaDB (HeidiSQL Compatible)
-- Database Name: hme_db
-- ============================================================================

CREATE DATABASE IF NOT EXISTS hme_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE hme_db;

-- 1. Table Users (Otentikasi Login Admin / Kahim)
DROP TABLE IF EXISTS users;
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    nama_lengkap VARCHAR(100) DEFAULT 'Ketua Himpunan',
    role VARCHAR(20) DEFAULT 'kahim',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Table Anggota (Main Database HME)
-- Kolom: nama, nim, jabatan, golongan, nomor_ab, no_sk
DROP TABLE IF EXISTS anggota;
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
    INDEX idx_anggota_nim (nim),
    INDEX idx_anggota_nomor_ab (nomor_ab),
    INDEX idx_anggota_jabatan (jabatan),
    INDEX idx_anggota_golongan (golongan)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- SEED OTENTIKASI KAHIM
-- ----------------------------------------------------------------------------
-- Data anggota TIDAK dimasukkan dari backend.
-- Seluruh data pengurus dimasukkan dari depan (user) via Upload SK Pengurus atau Form SK.
INSERT INTO users (username, password, nama_lengkap, role)
VALUES ('kahim', 'HME', 'Ketua Himpunan Mahasiswa Elektro', 'kahim');
