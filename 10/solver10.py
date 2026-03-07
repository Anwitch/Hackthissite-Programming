"""
HackThisSite Programming Level 10 Solver
Steganography + multi-layer hash brute-force challenge.

Pipeline:
 1. Login & download the stego image
 2. Find 88 data pixels (in whichever R/G/B channel has exactly ~88 non-zero values)
 3. Column positions of those pixels → base64 → 64-char hex string
 4. This hex string is a hash (SHA-256 or layered MD5) of the 10-char password
 5. Brute-force: password has 2 unique chars (1 upper + 1 lower), try all combos
 6. Submit answer
"""

import os
import requests
import re
import hashlib
import base64
import time
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# ─── Configuration ──────────────────────────────────────────────
USERNAME = os.getenv("HTS_USERNAME")
PASSWORD = os.getenv("HTS_PASSWORD")
URL_LOGIN = "https://www.hackthissite.org/user/login"
URL_PROG10 = "https://www.hackthissite.org/missions/prog/10/"
HEADERS = {"Referer": "https://www.hackthissite.org/"}

MAX_HASH_DEPTH = 15  # max layers of hashing to try


# ─── Image data extraction ─────────────────────────────────────
def extract_target_hash(session):
    """Download image, extract 88 data pixels, decode to 64-char hex string."""
    page = session.get(URL_PROG10, headers=HEADERS)
    img_match = re.findall(r'src="(/missions/prog/10/image\.php\?[^"]+)"', page.text)
    if not img_match:
        raise RuntimeError("Could not find image URL on page")

    img_url = "https://www.hackthissite.org" + img_match[0]
    resp = session.get(img_url, headers=HEADERS)
    img = Image.open(BytesIO(resp.content))
    w, h = img.size
    pixels = list(img.getdata())

    # Find which channel has ~88 non-zero values (the data channel)
    for ch_idx in range(3):
        nonzero_indices = [i for i in range(len(pixels)) if pixels[i][ch_idx] != 0]
        if 80 <= len(nonzero_indices) <= 100:
            # Extract column positions (= pixel index mod width)
            cols = [idx % w for idx in nonzero_indices]
            b64_str = "".join(chr(c) for c in cols)

            decoded = base64.b64decode(b64_str)
            hex_str = decoded.decode("ascii")
            return hex_str

    raise RuntimeError(f"Could not find data channel with ~88 pixels (w={w}, h={h})")


# ─── Brute-force engine ────────────────────────────────────────
def generate_passwords():
    """Yield all possible 10-char passwords (2 unique chars: 1 upper + 1 lower)."""
    for u in range(26):
        upper = chr(65 + u)  # A-Z
        for l in range(26):
            lower = chr(97 + l)  # a-z
            for mask in range(1024):  # 2^10 orderings
                pw = []
                for bit in range(10):
                    if (mask >> (9 - bit)) & 1:
                        pw.append(upper)
                    else:
                        pw.append(lower)
                yield "".join(pw)


def sha256hex(s):
    return hashlib.sha256(s.encode("ascii")).hexdigest()


def md5hex(s):
    return hashlib.md5(s.encode("ascii")).hexdigest()


def brute_force_sha256(target_hex):
    """Try SHA-256 hash chain: sha256(sha256(...(password)...)) at multiple depths."""
    print(f"  Brute-forcing SHA-256 (depth 1-{MAX_HASH_DEPTH})...")

    # Build all password hashes at depth 1 first
    # Then iterate depths by hashing the previous layer
    # Store as dict: {hash_value: original_password}

    current = {}
    total = 0
    for pw in generate_passwords():
        h = sha256hex(pw)
        current[h] = pw
        total += 1

    print(f"  Generated {total} password hashes (depth 1)")

    for depth in range(1, MAX_HASH_DEPTH + 1):
        if target_hex in current:
            return current[target_hex], depth
        # Hash all values to get next depth
        next_layer = {}
        for h, pw in current.items():
            h2 = sha256hex(h)
            next_layer[h2] = pw
        current = next_layer
        print(f"  Depth {depth + 1} computed...")

    return None, 0


def brute_force_md5_double(target_hex):
    """Try splitting into 2 × 32-char MD5 hashes and cracking each independently."""
    if len(target_hex) != 64:
        return None

    h1, h2 = target_hex[:32], target_hex[32:]
    print(f"  Trying 2×MD5: {h1} | {h2}")

    char_pool = [chr(c) for c in range(32, 127)]

    def crack_md5_chain(target, max_depth=100):
        for ch in char_pool:
            h = ch
            for d in range(1, max_depth + 1):
                h = md5hex(h)
                if h == target:
                    return ch, d
        return None, 0

    c1, d1 = crack_md5_chain(h1)
    c2, d2 = crack_md5_chain(h2)

    if c1 and c2:
        print(f"  MD5 cracked: char1={c1!r} (depth {d1}), char2={c2!r} (depth {d2})")
        return c1, c2, d1, d2
    return None


# ─── Main solver ────────────────────────────────────────────────
def solve():
    t0 = time.time()
    session = requests.Session()

    # 1. Login
    resp = session.post(
        URL_LOGIN,
        data={"username": USERNAME, "password": PASSWORD},
        headers=HEADERS,
    )
    print(f"[1] Login: {resp.status_code}")

    # 2. Extract target hash from image
    target_hex = extract_target_hash(session)
    dt = time.time() - t0
    print(f"[2] Target hash ({dt:.1f}s): {target_hex}")

    # 3. Brute-force
    print("[3] Starting brute-force...")

    # Approach A: SHA-256 of full password
    result, depth = brute_force_sha256(target_hex)
    if result:
        dt = time.time() - t0
        print(f"\n★ FOUND via SHA-256 depth {depth} ({dt:.1f}s): {result}")
        submit(session, result)
        return

    # Approach B: 2×MD5 of individual chars
    md5_result = brute_force_md5_double(target_hex)
    if md5_result:
        c1, c2, d1, d2 = md5_result
        # We have 2 chars but need the ordering (10 positions)
        # Brute-force all 1024 orderings with SHA-256 check
        for mask in range(1024):
            pw = "".join(c1 if (mask >> (9 - i)) & 1 else c2 for i in range(10))
            # We don't have a separate validation hash, so submit the most common pattern
            # Actually, try to match the original hash as SHA-256 of the password
            if sha256hex(pw) == target_hex:
                dt = time.time() - t0
                print(f"\n★ FOUND via 2×MD5 ({dt:.1f}s): {pw}")
                submit(session, pw)
                return

    dt = time.time() - t0
    print(f"\n✗ Brute-force failed after {dt:.1f}s")
    session.close()


def submit(session, answer):
    print(f"Submitting: {answer}")
    resp = session.post(
        "https://www.hackthissite.org/missions/prog/10/index.php",
        data={"solution": answer, "submitbutton": "Submit"},
        headers=HEADERS,
    )
    print(f"Submit response status: {resp.status_code}")
    # Check for result indicators
    text = resp.text.lower()
    if "ongratulation" in text or "you have completed" in text:
        print("✓ ACCEPTED!")
    elif "wrong" in text or "incorrect" in text or "error" in text:
        # Find relevant lines
        for line in resp.text.split("\n"):
            ll = line.lower()
            if any(kw in ll for kw in ["wrong", "error", "incorrect", "fail", "time"]):
                print(f"  > {line.strip()[:300]}")
    else:
        # Dump parts of the response that might indicate success/failure
        for line in resp.text.split("\n"):
            stripped = line.strip()
            if stripped and len(stripped) > 5 and not stripped.startswith("<"):
                print(f"  | {stripped[:300]}")
    session.close()


if __name__ == "__main__":
    solve()
