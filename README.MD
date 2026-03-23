# HackThisSite — Programming Challenges Solver

Kumpulan solver otomatis untuk [HackThisSite Programming Challenges](https://www.hackthissite.org/missions/prog/).

> **Disclaimer:** Level 7 dan Level 8 **belum berhasil diselesaikan**. Script yang ada di folder `7/` Belum selesai. Namun script tersebut bisa dijadikan **referensi pendekatan** untuk menyelesaikan kedua level tersebut.

---

## Persyaratan

- Python 3.10+
- Ruby (untuk Level 1 saja)
- Dependencies Python (install via pip):

```bash
pip install requests python-dotenv pillow pytesseract numpy matplotlib
```

- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (opsional, untuk Level 2 dan Level 7 — jika tidak ada, solver akan meminta input manual)

---

## Konfigurasi Kredensial

Buat file `.env` di root folder berdasarkan `.env.example`:

```
HTS_USERNAME=username_hackthissite_kamu
HTS_PASSWORD=password_hackthissite_kamu
```

Semua solver membaca kredensial dari file `.env` ini secara otomatis.

---

## Struktur Folder

```
.
├── 1/              # Level 1  — Word Unscramble (Ruby)
├── 2/              # Level 2  — Morse Code Image Decoder
├── 3/              # Level 3  — Serial Number Reverse Engineering
├── 4/              # Level 4  — bz2 XML Plot Visualization
├── 5/              # Level 5  — Corrupted bz2 PNG Recovery
├── 7/              # Level 7  — Scrambled Image Lines (BELUM SELESAI)
├── 9/              # Level 9  — Sudoku + Blowfish Decryption
├── 10/             # Level 10 — Steganography + Hash Brute-force
├── 11/             # Level 11 — Shift Cipher Decoder
├── 12/             # Level 12 — String Processing (Prime/Composite)
├── .env.example    # Template konfigurasi
└── README.MD
```

---

## Level-by-Level

### Level 1 — Word Unscramble
**File:** `1/unscrambled.rb`  
**Bahasa:** Ruby  
**Deskripsi:** Diberikan daftar kata yang huruf-hurufnya diacak. Solver membaca `wordlist.txt` sebagai kamus, mengurutkan karakter tiap kata sebagai kunci, lalu mencocokan kata-kata acak dari `words.txt`.  
**Cara pakai:**
```bash
ruby 1/unscrambled.rb
```

---

### Level 2 — Morse Code Image
**File:** `2/Prog2.py`  
**Deskripsi:** Diberikan gambar yang berisi kode Morse. Solver membaca gambar, mengekstrak pola titik/garis dari piksel, lalu mendekode ke teks menggunakan tabel kode Morse.  
**Cara pakai:**
```bash
python 2/Prog2.py
```

---

### Level 3 — Serial Number Reverse Engineering
**File:** `3/solver.py`  
**Deskripsi:** Membalikkan algoritma `encryptString()` milik PHP untuk memulihkan serial number yang valid. Menggunakan MD5 hashing dan operasi digit hex.  
**Cara pakai:**
```bash
python 3/solver.py
```

---

### Level 4 — bz2 XML Plot
**File:** `4/solver4.py`  
**Deskripsi:** Mengekstrak file XML dari arsip bz2 (`plotMe.xml.bz2`), mem-parsing elemen `Line` dan `Arc`, lalu memvisualisasikannya dengan `matplotlib` untuk membaca teks tersembunyi dari gambar.  
**Cara pakai:**
```bash
python 4/solver4.py
```

---

### Level 5 — Corrupted bz2 PNG Recovery
**File:** `5/solver5.py`  
**Deskripsi:** File bz2 yang berisi PNG diunduh melalui FTP mode ASCII di Windows, sehingga semua byte `0x0A` (LF) dikonversi menjadi `0x0D 0x0A` (CRLF). Karena file biner dapat mengandung `0x0A` yang memang asli (bukan newline), tidak semua CRLF adalah hasil korupsi. Solver:
1. Mengunduh file korup dari server
2. Meng-split file berdasarkan `\r\n` lalu mencoba semua kombinasi CRLF mana yang perlu dikembalikan ke `\n`
3. Mendekompres bz2 → PNG
4. Membaca password dari gambar via OCR (atau input manual)
5. Mengirim jawaban  

**Cara pakai:**
```bash
python 5/solver5.py
```

---

### Level 7 — Scrambled Image Lines ⚠️ BELUM SELESAI
**File:** `7/solver7.py`  
**Status:** Belum berhasil diterima oleh server.  
**Deskripsi:** Gambar berisi 2 baris teks yang baris-barisnya telah diacak (pay-TV style scrambling). Setiap baris dikodekan dengan nilai R (red channel) yang berbeda, dan terdiri dari 6 kelompok kolom. Pendekatan yang dicoba: analisis fitur struktural + Tesseract OCR. Bisa dijadikan referensi untuk pengembangan lebih lanjut.

---

### Level 9 — Sudoku + Blowfish Decryption
**File:** `9/solver9.py`  
**Deskripsi:** Menyelesaikan puzzle Sudoku, meng-hash solusinya dengan SHA1 sebagai kunci Blowfish CBC, lalu mendekripsi string terenkripsi untuk mendapatkan password.  
**Cara pakai:**
```bash
python 9/solver9.py
```

---

### Level 10 — Steganography + Hash Brute-force
**File:** `10/solver10.py`  
**Deskripsi:** Menemukan 88 piksel data tersembunyi di gambar stego. Posisi kolom piksel dikonversi ke base64 → string hex 64 karakter (hash SHA-256 atau MD5 berlapis). Brute-force password 10 karakter yang hanya terdiri dari 2 karakter unik (1 huruf besar + 1 huruf kecil).  
**Cara pakai:**
```bash
python 10/solver10.py
```

---

### Level 11 — Shift Cipher Decoder
**File:** `11/solver11.py`  
**Deskripsi:** Halaman challenge memberikan angka-angka yang dipisahkan oleh karakter separator acak, beserta nilai shift. Solver mengekstrak angka, mengurangi nilai shift dari tiap angka, lalu mengkonversinya ke karakter ASCII.  
**Cara pakai:**
```bash
python 11/solver11.py
```

---

### Level 12 — String Processing
**File:** `12/solver12.py`  
**Deskripsi:** Diberikan string campuran angka dan huruf. Solver menjumlahkan digit prima dan komposit secara terpisah, menggeser karakter huruf sebesar +1, lalu menggabungkan hasilnya sebagai jawaban.  
**Cara pakai:**
```bash
python 12/solver12.py
```

---

## Catatan

- Setiap solver login otomatis ke HackThisSite menggunakan sesi HTTP dan membaca kredensial dari `.env`.
- Password/jawaban bersifat **session-specific** — berubah setiap kali halaman diakses, sehingga solver harus dijalankan secara langsung (bukan copy-paste jawaban lama).
- Level 6 tidak ada di repository ini.