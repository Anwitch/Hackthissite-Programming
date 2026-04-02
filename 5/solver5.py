"""
HackThisSite Programming Level 5 Solver

Someone downloaded a bz2-compressed PNG via Windows FTP in ASCII mode.
ASCII mode corrupts binary by converting LF (0x0A) → CRLF (0x0D 0x0A).

Reconstruction strategy (from programming5.py):
  Split file by b'\r\n', then:
  Level 1 – rejoin all with b'\n'  (all CRLFs were corrupted)
  Level 2 – try keeping ONE \r\n intact  (single real CRLF in original)
  Level 3 – try keeping TWO \r\n intact  (two real CRLFs in original)

Pipeline:
 1. Login & get challenge page (starts 600s timer)
 2. Download the corrupted bz2 file
 3. Reconstruct bz2 (levels 1-3)
 4. Decompress bz2 → PNG
 5. OCR password from PNG (or manual input)
 6. Submit answer
"""

import os
import re
import bz2
import itertools
import requests
import pytesseract
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# ─── Configuration ──────────────────────────────────────────────
USERNAME = os.getenv("HTS_USERNAME")
PASSWORD = os.getenv("HTS_PASSWORD")
URL_LOGIN = "https://www.hackthissite.org/user/login"
URL_PROG5 = "https://www.hackthissite.org/missions/prog/5/"
URL_SUBMIT = "https://www.hackthissite.org/missions/prog/5/index.php"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
    "Referer": "https://www.hackthissite.org/",
}


def _looks_logged_in(html: str) -> bool:
    h = (html or "").lower()
    # HTS pages usually include a logout link when authenticated.
    return ("logout" in h) or ("/?logout" in h) or ("hello," in h)


def _looks_login_error(html: str) -> bool:
    h = (html or "").lower()
    return any(k in h for k in ["invalid", "incorrect", "wrong password", "login failed"])


def _save_debug_html(filename: str, html: str) -> str:
    out = os.path.join(os.path.dirname(__file__), filename)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html or "")
    return out


# ─── Reconstruction Algorithm (from programming5.py) ──────────
def reconstruct_bz2(data):
    """
    Try to reconstruct a bz2 file corrupted by Windows FTP ASCII mode.
    Returns decompressed bytes on success, or None.
    """
    parts = data.split(b'\r\n')
    n_joins = len(parts) - 1
    print(f"    Split into {len(parts)} parts ({n_joins} CRLF positions)")

    def try_decompress(candidate, label):
        if not candidate.startswith(b'BZh'):
            return None
        try:
            result = bz2.decompress(candidate)
            print(f"    [SUCCESS] {label} → {len(result)} bytes")
            return result
        except (OSError, EOFError, Exception):
            return None

    def rejoin(parts, seps):
        buf = bytearray()
        for i, part in enumerate(parts[:-1]):
            buf.extend(part)
            buf.extend(seps[i])
        buf.extend(parts[-1])
        return bytes(buf)

    # Level 1: all CRLF → LF
    print("    Level 1: all CRLF→LF ...")
    r = try_decompress(b'\n'.join(parts), "all CRLF→LF")
    if r:
        return r

    # Level 2: one CRLF kept as-is
    print(f"    Level 2: single CRLF exception (0..{n_joins-1}) ...")
    base_seps = [b'\n'] * n_joins
    for i in range(n_joins):
        seps = list(base_seps)
        seps[i] = b'\r\n'
        r = try_decompress(rejoin(parts, seps), f"exception at {i}")
        if r:
            return r
        if i % 50 == 0 and i > 0:
            print(f"      ... checked {i}/{n_joins}", end="\r")

    # Level 3: two CRLFs kept as-is
    print(f"\n    Level 3: double CRLF exception ...")
    total = n_joins * (n_joins - 1) // 2
    checked = 0
    for i1, i2 in itertools.combinations(range(n_joins), 2):
        seps = list(base_seps)
        seps[i1] = b'\r\n'
        seps[i2] = b'\r\n'
        r = try_decompress(rejoin(parts, seps), f"exceptions at {i1},{i2}")
        if r:
            return r
        checked += 1
        if checked % 500 == 0:
            print(f"      ... {checked}/{total}", end="\r")

    print(f"\n    All levels failed.")
    return None


# ─── Main Solver ───────────────────────────────────────────────
def solve():
    session = requests.Session()

    if not USERNAME or not PASSWORD:
        print("ERROR: HTS_USERNAME/HTS_PASSWORD tidak ditemukan.")
        print("       Isi file .env di folder Programming (lihat .env.example).")
        session.close()
        return

    # 1. Login
    # Some sites set cookies on GET before POSTing credentials.
    session.get(URL_LOGIN, headers=HEADERS)
    resp = session.post(
        URL_LOGIN,
        data={"username": USERNAME, "password": PASSWORD},
        headers=HEADERS,
        allow_redirects=True,
    )
    print(f"[1] Login: {resp.status_code} ({resp.url})")
    if _looks_login_error(resp.text) or (resp.url.rstrip("/") == URL_LOGIN.rstrip("/") and not _looks_logged_in(resp.text)):
        print("WARNING: Login mungkin gagal (status 200 tapi masih di halaman login).")
        print("         Cek username/password di .env atau apakah HTS butuh verifikasi tambahan.")

    # 2. Get challenge page & find download link
    page = session.get(URL_PROG5, headers=HEADERS)
    print(f"[2] Challenge page: {page.status_code} ({page.url})")

    link = re.search(r'href="([^"]*\.bz2[^"]*)"', page.text)
    if not link:
        print("ERROR: No .bz2 link found on page!")
        debug_path = _save_debug_html("prog5_debug.html", page.text)
        print(f"       Saved HTML for inspection: {debug_path}")

        # Fallback: known direct URL (historically used by HTS)
        file_url = "https://www.hackthissite.org/missions/prog/5/corrupted.png.bz2"
        print(f"[3] Fallback download: {file_url}")
        resp = session.get(file_url, headers={**HEADERS, "Referer": URL_PROG5})
        corrupted = resp.content
        print(f"[4] Downloaded: {resp.status_code}, {len(corrupted)} bytes")
        if not corrupted or corrupted[:3] != b"BZh":
            print("ERROR: Fallback download tidak menghasilkan file bz2 yang valid.")
            print("       Kemungkinan belum login / kena redirect / halaman berubah.")
            session.close()
            return
    else:
        file_url = link.group(1)
        if file_url.startswith('/'):
            file_url = "https://www.hackthissite.org" + file_url
        print(f"[3] Download: {file_url}")

        # 3. Download corrupted file
        resp = session.get(file_url, headers=HEADERS)
        corrupted = resp.content
        crlf_count = corrupted.count(b'\r\n')
        print(f"[4] Downloaded: {len(corrupted)} bytes, CRLF count: {crlf_count}")

        if not corrupted or corrupted[:3] != b'BZh':
            print(f"ERROR: Unexpected file header: {corrupted[:10].hex()}")
            session.close()
            return

    # 4. Reconstruct and decompress
    print("[5] Reconstructing bz2 ...")
    png_data = reconstruct_bz2(corrupted)

    if not png_data:
        print("ERROR: Could not reconstruct bz2!")
        out = os.path.join(os.path.dirname(__file__), "downloaded_orig.bin")
        with open(out, "wb") as f:
            f.write(corrupted)
        print(f"    Saved corrupted file to {out}")
        session.close()
        return

    # 5. Save PNG
    png_path = os.path.join(os.path.dirname(__file__), "password.png")
    with open(png_path, "wb") as f:
        f.write(png_data)
    print(f"[6] PNG saved: {png_path}")

    # 6. Try OCR to read password
    img = Image.open(BytesIO(png_data))
    password = None
    try:
        text = pytesseract.image_to_string(img).strip()
        # Clean up OCR noise: keep only printable ASCII
        text = re.sub(r'[^\x20-\x7E]', '', text).strip()
        if text:
            password = text
            print(f"[7] OCR result: '{password}'")
    except Exception as e:
        print(f"[7] OCR failed: {e}")

    if not password:
        print("[7] Could not auto-read password.")
        print(f"    Open {png_path} and read the password yourself.")
        password = input("    Enter password from image: ").strip()

    if not password:
        print("No password provided, aborting.")
        session.close()
        return

    # 7. Submit
    print(f"[8] Submitting: '{password}'")
    resp = session.post(
        URL_SUBMIT,
        data={"solution": password, "submitbutton": "submit"},
        headers={"Referer": URL_PROG5},
    )

    if "ongratulat" in resp.text or "completed" in resp.text.lower():
        print(">>> ACCEPTED!")
    else:
        for line in resp.text.split("\n"):
            s = line.strip()
            if s and len(s) > 5 and not s.startswith("<"):
                sl = s.lower()
                if any(k in sl for k in ["wrong", "error", "incorrect",
                                          "solution", "congratul", "time"]):
                    print(f"  > {s[:300]}")

    session.close()


if __name__ == "__main__":
    solve()
