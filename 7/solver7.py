"""
HackThisSite Programming Level 7 Solver
Unscramble image lines (pay-TV style) and recognize the text.

The image has 2 text lines, each rendered in a different R-value.
Each line has 6 column groups: first 3 are copies of the same char,
last 3 are unique characters. Answer = upper_line_chars + lower_line_chars.

Uses structural feature analysis (holes, symmetry, density profiles)
combined with Tesseract OCR for robust character recognition.
"""

import os
import requests
import re
import numpy as np
import pytesseract
import time
from io import BytesIO
from PIL import Image, ImageFilter
from collections import Counter
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# ─── Configuration ──────────────────────────────────────────────
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

USERNAME = os.getenv("HTS_USERNAME")
PASSWORD = os.getenv("HTS_PASSWORD")
URL_LOGIN = "https://www.hackthissite.org/user/login"
URL_PROG7 = "https://www.hackthissite.org/missions/prog/7/"
HEADERS = {"Referer": "https://www.hackthissite.org/"}


# ─── Image Processing ──────────────────────────────────────────
def find_text_r_values(arr):
    h, w, _ = arr.shape
    r_chan = arr[:, :, 0]
    r_counts = Counter(r_chan.flatten())
    bg_r = r_counts.most_common(1)[0][0]
    candidates = []
    for rval, count in r_counts.most_common():
        if rval == bg_r or count < 80:
            continue
        nrows = sum(1 for y in range(h) if np.any(r_chan[y] == rval))
        if 10 <= nrows <= 60:
            candidates.append((rval, count, nrows))
    candidates.sort(key=lambda x: -x[1])
    if len(candidates) < 2:
        for rval, count in r_counts.most_common(10):
            if rval == bg_r or count < 40:
                continue
            nrows = sum(1 for y in range(h) if np.any(r_chan[y] == rval))
            if not any(v[0] == rval for v in candidates) and 5 <= nrows <= 70:
                candidates.append((rval, count, nrows))
            if len(candidates) >= 2:
                break
    return bg_r, candidates[:2]


def nn_sort_rows(binary_rows):
    n = len(binary_rows)
    if n <= 1:
        return list(range(n))
    dist = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        for j in range(i + 1, n):
            d = np.sum(binary_rows[i] != binary_rows[j])
            dist[i][j] = d
            dist[j][i] = d
    best_order = None
    best_cost = float('inf')
    for start in range(n):
        order = [start]
        used = {start}
        cost = 0
        for _ in range(n - 1):
            last = order[-1]
            d = dist[last].copy()
            d[list(used)] = float('inf')
            nxt = int(np.argmin(d))
            cost += d[nxt]
            order.append(nxt)
            used.add(nxt)
        if cost < best_cost:
            best_cost = cost
            best_order = order
    return best_order


def find_column_groups(sorted_rows):
    col_sums = sorted_rows.sum(axis=0)
    in_run = False
    runs = []
    for x in range(len(col_sums)):
        if col_sums[x] > 0:
            if not in_run:
                run_start = x
                in_run = True
        else:
            if in_run:
                runs.append((run_start, x - 1))
                in_run = False
    if in_run:
        runs.append((run_start, len(col_sums) - 1))
    return runs


# ─── Character Feature Extraction ──────────────────────────────
def count_holes(bm):
    """Count enclosed holes using flood fill from border."""
    h, w = bm.shape
    padded = np.zeros((h + 2, w + 2), dtype=np.uint8)
    padded[1:-1, 1:-1] = bm
    visited = np.zeros_like(padded, dtype=bool)
    # Flood fill from (0,0)
    stack = [(0, 0)]
    while stack:
        y, x = stack.pop()
        if y < 0 or y >= h + 2 or x < 0 or x >= w + 2:
            continue
        if visited[y, x] or padded[y, x] == 1:
            continue
        visited[y, x] = True
        stack.extend([(y-1, x), (y+1, x), (y, x-1), (y, x+1)])
    # Count unvisited background regions
    n_holes = 0
    for y in range(1, h + 1):
        for x in range(1, w + 1):
            if padded[y, x] == 0 and not visited[y, x]:
                n_holes += 1
                stack = [(y, x)]
                while stack:
                    cy, cx = stack.pop()
                    if cy < 0 or cy >= h + 2 or cx < 0 or cx >= w + 2:
                        continue
                    if visited[cy, cx] or padded[cy, cx] == 1:
                        continue
                    visited[cy, cx] = True
                    stack.extend([(cy-1, cx), (cy+1, cx), (cy, cx-1), (cy, cx+1)])
    return n_holes


def normalize_bitmap(sorted_rows, col_start, col_end, target_h=27, target_w=20):
    """Extract character, trim whitespace, normalize to fixed size."""
    char_data = sorted_rows[:, col_start:col_end + 1].copy()
    # Trim empty rows
    row_sums = char_data.sum(axis=1)
    non_empty = np.where(row_sums > 0)[0]
    if len(non_empty) == 0:
        return None
    char_data = char_data[non_empty[0]:non_empty[-1] + 1]
    # Trim empty cols
    col_sums = char_data.sum(axis=0)
    non_empty_c = np.where(col_sums > 0)[0]
    if len(non_empty_c) == 0:
        return None
    char_data = char_data[:, non_empty_c[0]:non_empty_c[-1] + 1]
    img = Image.fromarray((char_data * 255).astype(np.uint8), mode='L')
    img = img.resize((target_w, target_h), Image.NEAREST)
    return (np.array(img) > 127).astype(np.uint8)


def compute_features(bm):
    """Compute comprehensive structural features."""
    h, w = bm.shape
    density = np.mean(bm)
    holes = count_holes(bm)

    # Symmetry
    h_sym = np.mean(bm == bm[:, ::-1])
    v_sym = np.mean(bm == bm[::-1, :])

    # Quadrant densities
    mh, mw = h // 2, w // 2
    q_tl = np.mean(bm[:mh, :mw]) if mh > 0 and mw > 0 else 0
    q_tr = np.mean(bm[:mh, mw:]) if mh > 0 else 0
    q_bl = np.mean(bm[mh:, :mw]) if mw > 0 else 0
    q_br = np.mean(bm[mh:, mw:])

    # Edge strip densities (outer ~15%)
    es = max(2, h // 7)
    ew = max(2, w // 7)
    top_d = np.mean(bm[:es, :])
    bot_d = np.mean(bm[-es:, :])
    left_d = np.mean(bm[:, :ew])
    right_d = np.mean(bm[:, -ew:])

    # Middle horizontal strip
    mid_d = np.mean(bm[mh-1:mh+2, :]) if mh > 1 else np.mean(bm[mh:mh+1, :])

    # Center of mass
    ys, xs = np.where(bm == 1)
    cx = np.mean(xs) / w if len(xs) > 0 else 0.5
    cy = np.mean(ys) / h if len(ys) > 0 else 0.5

    # Width profile: span of non-zero pixels at top vs middle vs bottom
    def span_at(rows):
        cols = np.where(bm[rows, :].sum(axis=0) > 0)[0]
        return (cols[-1] - cols[0] + 1) if len(cols) > 0 else 0

    top_span = span_at(slice(0, es))
    mid_span = span_at(slice(mh-1, mh+2))
    bot_span = span_at(slice(-es, None))

    # Vertical profile: fraction of rows with left-edge pixel
    left_col_active = sum(1 for y in range(h) if bm[y, :ew].sum() > 0) / h
    right_col_active = sum(1 for y in range(h) if bm[y, -ew:].sum() > 0) / h

    # Check for vertical bar on left or right (continuous full-height)
    left_bar = left_col_active > 0.85
    right_bar = right_col_active > 0.85

    # Diagonal presence: top-left to bottom-right vs top-right to bottom-left
    diag_lr = 0  # top-left to bottom-right
    diag_rl = 0  # top-right to bottom-left
    for y in range(h):
        x_lr = int(y * (w - 1) / (h - 1)) if h > 1 else w // 2
        x_rl = int((h - 1 - y) * (w - 1) / (h - 1)) if h > 1 else w // 2
        rx = max(1, w // 10)
        if bm[y, max(0, x_lr-rx):min(w, x_lr+rx+1)].sum() > 0:
            diag_lr += 1
        if bm[y, max(0, x_rl-rx):min(w, x_rl+rx+1)].sum() > 0:
            diag_rl += 1
    diag_lr /= h
    diag_rl /= h

    return {
        'density': density,
        'holes': holes,
        'h_sym': h_sym,
        'v_sym': v_sym,
        'q_tl': q_tl, 'q_tr': q_tr, 'q_bl': q_bl, 'q_br': q_br,
        'top_d': top_d, 'bot_d': bot_d, 'left_d': left_d, 'right_d': right_d,
        'mid_d': mid_d,
        'cx': cx, 'cy': cy,
        'top_span': top_span, 'mid_span': mid_span, 'bot_span': bot_span,
        'left_bar': left_bar, 'right_bar': right_bar,
        'left_col_active': left_col_active, 'right_col_active': right_col_active,
        'diag_lr': diag_lr, 'diag_rl': diag_rl,
    }


# ─── Structural Character Classifier ───────────────────────────
def classify_char(bm):
    """Classify a normalized character bitmap using structural features.
    Returns a list of (char, confidence) tuples, sorted by confidence desc."""
    f = compute_features(bm)
    candidates = []

    holes = f['holes']
    h_sym = f['h_sym']
    v_sym = f['v_sym']
    left_d = f['left_d']
    right_d = f['right_d']
    top_d = f['top_d']
    bot_d = f['bot_d']
    mid_d = f['mid_d']
    density = f['density']
    left_bar = f['left_bar']
    right_bar = f['right_bar']
    cx = f['cx']
    cy = f['cy']
    top_span = f['top_span']
    mid_span = f['mid_span']
    bot_span = f['bot_span']
    diag_lr = f['diag_lr']
    diag_rl = f['diag_rl']
    lca = f['left_col_active']
    rca = f['right_col_active']

    # === 2 HOLES ===
    if holes == 2:
        if h_sym > 0.82:
            candidates.append(('8', 0.9))
            candidates.append(('B', 0.4))
        elif left_d > right_d + 0.1:
            candidates.append(('B', 0.9))
            candidates.append(('8', 0.3))
        else:
            candidates.append(('B', 0.7))
            candidates.append(('8', 0.6))

    # === 1 HOLE ===
    elif holes == 1:
        if h_sym > 0.82 and v_sym > 0.75:
            candidates.append(('O', 0.9))
            candidates.append(('0', 0.85))
        elif h_sym > 0.80:
            if cy < 0.45:
                # Hole is in top half → could be A (hole in upper-mid)
                candidates.append(('A', 0.7))
                candidates.append(('O', 0.5))
            elif top_span < bot_span * 0.6:
                candidates.append(('A', 0.85))
            else:
                candidates.append(('O', 0.7))
                candidates.append(('D', 0.5))
                candidates.append(('A', 0.4))
        elif left_bar:
            if cy < 0.42:
                candidates.append(('P', 0.85))
                candidates.append(('R', 0.4))
            elif bot_d > 0.2 and f['q_br'] > 0.15:
                candidates.append(('R', 0.7))
                candidates.append(('B', 0.4))
            elif v_sym > 0.7:
                candidates.append(('D', 0.85))
            else:
                candidates.append(('P', 0.6))
                candidates.append(('R', 0.55))
                candidates.append(('D', 0.4))
        elif right_d > left_d + 0.1:
            candidates.append(('Q', 0.7))
            candidates.append(('D', 0.5))
        else:
            if cy > 0.55:
                candidates.append(('6', 0.7))
            elif cy < 0.45:
                candidates.append(('9', 0.7))
            candidates.append(('A', 0.5))
            candidates.append(('O', 0.4))
            candidates.append(('D', 0.4))

    # === 0 HOLES ===
    else:
        # --- Characters with left vertical bar ---
        if left_bar and right_bar:
            if mid_d > 0.4:
                candidates.append(('H', 0.85))
            elif v_sym > 0.7:
                candidates.append(('U', 0.7))
                candidates.append(('H', 0.5))
            elif diag_lr > 0.6 and diag_rl > 0.3:
                candidates.append(('N', 0.8))
                candidates.append(('M', 0.4))
            elif top_d > 0.4 and bot_d > 0.4:
                candidates.append(('M', 0.7))
                candidates.append(('N', 0.5))
            else:
                candidates.append(('H', 0.5))
                candidates.append(('N', 0.5))
                candidates.append(('U', 0.4))
                candidates.append(('M', 0.4))

        elif left_bar and not right_bar:
            if top_d > 0.4 and bot_d > 0.4 and mid_d > 0.3:
                candidates.append(('E', 0.85))
            elif top_d > 0.4 and mid_d > 0.3 and bot_d < 0.25:
                candidates.append(('F', 0.85))
            elif bot_d > 0.4 and top_d < 0.2:
                candidates.append(('L', 0.85))
            elif mid_d > 0.3 and top_d > 0.3:
                candidates.append(('E', 0.6))
                candidates.append(('F', 0.55))
                candidates.append(('K', 0.4))
            elif rca > 0.4:
                candidates.append(('K', 0.7))
                candidates.append(('R', 0.4))
            else:
                candidates.append(('L', 0.5))
                candidates.append(('E', 0.5))
                candidates.append(('F', 0.4))

        elif right_bar and not left_bar:
            candidates.append(('J', 0.85))

        # --- No full-height vertical bar ---
        elif not left_bar and not right_bar:
            # High horizontal symmetry
            if h_sym > 0.78:
                if top_d > 0.5 and bot_d < 0.2:
                    candidates.append(('T', 0.9))
                elif top_d > 0.5 and bot_d > 0.3:
                    candidates.append(('I', 0.7))
                    candidates.append(('T', 0.5))
                elif diag_lr > 0.7 and diag_rl > 0.7:
                    if v_sym > 0.7:
                        candidates.append(('X', 0.9))
                    else:
                        candidates.append(('X', 0.6))
                        candidates.append(('Z', 0.4))
                elif top_span > bot_span * 1.5:
                    if mid_d < 0.15:
                        candidates.append(('V', 0.9))
                    elif cy < 0.45:
                        candidates.append(('Y', 0.85))
                    else:
                        candidates.append(('V', 0.6))
                        candidates.append(('Y', 0.5))
                elif bot_span > top_span * 1.5:
                    candidates.append(('A', 0.6))
                    candidates.append(('W', 0.5))
                elif density < 0.18:
                    candidates.append(('I', 0.7))
                    candidates.append(('1', 0.6))
                elif v_sym > 0.7:
                    candidates.append(('X', 0.65))
                    candidates.append(('O', 0.4))
                else:
                    candidates.append(('Y', 0.5))
                    candidates.append(('V', 0.5))
                    candidates.append(('T', 0.4))

            # S-like: diagonal, no strong bars
            elif abs(cx - 0.5) < 0.12 and abs(cy - 0.5) < 0.12:
                if top_d > 0.25 and bot_d > 0.25 and mid_d > 0.2:
                    if top_span > mid_span * 0.8 and bot_span > mid_span * 0.8:
                        candidates.append(('S', 0.7))
                        candidates.append(('Z', 0.5))
                    else:
                        candidates.append(('S', 0.6))
                        candidates.append(('Z', 0.5))
                elif diag_lr > 0.6 or diag_rl > 0.6:
                    candidates.append(('Z', 0.6))
                    candidates.append(('S', 0.5))
                    candidates.append(('N', 0.4))
                else:
                    candidates.append(('S', 0.5))
                    candidates.append(('C', 0.4))

            # C/G: left curve
            elif lca > 0.6 and rca < 0.5:
                if mid_d > 0.25 and rca > 0.3:
                    candidates.append(('G', 0.8))
                    candidates.append(('C', 0.4))
                else:
                    candidates.append(('C', 0.8))
                    candidates.append(('G', 0.4))

            # W: wide bottom
            elif bot_span > top_span * 1.3 and h_sym > 0.65 and density > 0.25:
                candidates.append(('W', 0.7))
                candidates.append(('M', 0.4))

            # Converging top → V or Y
            elif top_span > bot_span * 1.3:
                if mid_d < 0.15 and bot_d < 0.15:
                    candidates.append(('V', 0.85))
                elif cy < 0.45:
                    candidates.append(('Y', 0.8))
                    candidates.append(('V', 0.4))
                else:
                    candidates.append(('V', 0.6))
                    candidates.append(('Y', 0.55))
                    candidates.append(('7', 0.3))

            # Z: top+bottom bars with diagonal
            elif top_d > 0.35 and bot_d > 0.35 and mid_d < 0.3:
                candidates.append(('Z', 0.7))
                candidates.append(('S', 0.4))

            # Diagonal only
            elif diag_lr > 0.6 and diag_rl < 0.4:
                candidates.append(('Z', 0.5))
                candidates.append(('7', 0.45))
                candidates.append(('N', 0.4))
            elif diag_rl > 0.6 and diag_lr < 0.4:
                candidates.append(('N', 0.5))
                candidates.append(('2', 0.4))

            # Fallback
            else:
                candidates.append(('S', 0.3))
                candidates.append(('C', 0.3))
                candidates.append(('Z', 0.3))
                candidates.append(('G', 0.3))

    # Also add a few alternative chars at low confidence
    if not candidates:
        candidates.append(('?', 0.1))

    candidates.sort(key=lambda x: -x[1])
    return candidates, f


# ─── Tesseract OCR (smoothed) ──────────────────────────────────
def ocr_char_tesseract(sorted_rows, col_start, col_end):
    """OCR a single character with anti-aliased scaling for better Tesseract results."""
    char_data = sorted_rows[:, col_start:col_end + 1]
    inv = ((1 - char_data) * 255).astype(np.uint8)
    pad = 6
    h, w = inv.shape
    padded = np.ones((h + 2 * pad, w + 2 * pad), dtype=np.uint8) * 255
    padded[pad:pad + h, pad:pad + w] = inv
    img = Image.fromarray(padded, mode='L')

    results = []
    # Try two scale approaches: NN (crisp) and BILINEAR (smooth)
    scale = 12
    for resample in [Image.NEAREST, Image.BILINEAR]:
        big = img.resize((padded.shape[1] * scale, padded.shape[0] * scale), resample)
        if resample == Image.BILINEAR:
            big = big.point(lambda p: 0 if p < 128 else 255)
        for psm in [10, 13, 8]:
            try:
                text = pytesseract.image_to_string(
                    big,
                    config=f'--psm {psm} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                ).strip().upper()
                if text and len(text) == 1 and text.isalnum():
                    results.append(text)
            except Exception:
                pass

    if results:
        # Return most common
        c = Counter(results)
        return c.most_common(1)[0][0], c.most_common(1)[0][1] / len(results)
    return None, 0


# ─── Combined Recognition ──────────────────────────────────────
def recognize_char(sorted_rows, col_start, col_end):
    """Combine structural and OCR classification."""
    bm = normalize_bitmap(sorted_rows, col_start, col_end)
    if bm is None:
        return '?'

    struct_cands, feats = classify_char(bm)
    ocr_char, ocr_conf = ocr_char_tesseract(sorted_rows, col_start, col_end)

    # Combine results
    scores = {}
    for ch, conf in struct_cands:
        scores[ch] = scores.get(ch, 0) + conf

    if ocr_char:
        # OCR result gets a bonus
        scores[ocr_char] = scores.get(ocr_char, 0) + ocr_conf * 0.8

    # Pick the best
    if scores:
        best = max(scores, key=scores.get)
        return best
    return struct_cands[0][0] if struct_cands else '?'


def recognize_copy_char(sorted_rows, groups_3):
    """Recognize the copy character using 3 copies for majority vote."""
    votes = []
    for cs, ce in groups_3:
        ch = recognize_char(sorted_rows, cs, ce)
        votes.append(ch)

    if votes:
        c = Counter(votes)
        return c.most_common(1)[0][0]
    return '?'


# ─── Line Processing ───────────────────────────────────────────
def process_line(sorted_rows):
    """Process one line direction, return 4-char string."""
    groups = find_column_groups(sorted_rows)
    widths = [g[1] - g[0] + 1 for g in groups]

    if len(groups) >= 6:
        copy_groups = groups[:3]
        char_groups = groups[3:6]
    elif len(groups) >= 3:
        copy_groups = groups[:1]
        char_groups = groups[1:]
    else:
        return '????'

    copy_ch = recognize_copy_char(sorted_rows, copy_groups)
    chars = [recognize_char(sorted_rows, cs, ce) for cs, ce in char_groups]
    result = copy_ch + ''.join(chars)
    return result, widths


def print_char_debug(sorted_rows, col_start, col_end, label=""):
    """Print ASCII art of a character for debugging."""
    bm = normalize_bitmap(sorted_rows, col_start, col_end)
    if bm is None:
        print(f"  [{label}] (empty)")
        return
    h, w = bm.shape
    feats = compute_features(bm)
    struct_cands, _ = classify_char(bm)
    ocr_ch, _ = ocr_char_tesseract(sorted_rows, col_start, col_end)
    print(f"  [{label}] struct={[f'{c}:{v:.1f}' for c,v in struct_cands[:3]]} ocr={ocr_ch}")
    print(f"    holes={feats['holes']} h_sym={feats['h_sym']:.2f} v_sym={feats['v_sym']:.2f} "
          f"L={feats['left_d']:.2f} R={feats['right_d']:.2f} T={feats['top_d']:.2f} B={feats['bot_d']:.2f} "
          f"M={feats['mid_d']:.2f} d={feats['density']:.2f}")
    print(f"    spans T={feats['top_span']} M={feats['mid_span']} B={feats['bot_span']} "
          f"cx={feats['cx']:.2f} cy={feats['cy']:.2f} diag={feats['diag_lr']:.2f}/{feats['diag_rl']:.2f} "
          f"Lbar={feats['left_bar']} Rbar={feats['right_bar']}")
    for y in range(h):
        print(f"    {''.join('#' if bm[y][x] else '.' for x in range(w))}")


# ─── Main Solver ───────────────────────────────────────────────
def solve():
    t0 = time.time()
    session = requests.Session()

    # Login
    session.post(URL_LOGIN,
                 data={"username": USERNAME, "password": PASSWORD},
                 headers=HEADERS)
    print(f"[1] Logged in ({time.time() - t0:.1f}s)")

    # Load page (starts timer)
    page = session.get(URL_PROG7, headers=HEADERS)

    # Download image
    resp = session.get("https://www.hackthissite.org/missions/prog/7/BMP", headers=HEADERS)
    img = Image.open(BytesIO(resp.content))
    arr = np.array(img)
    w, h = img.size
    print(f"[2] Image: {w}x{h} ({time.time() - t0:.1f}s)")

    # Find text colors
    bg_r, text_vals = find_text_r_values(arr)
    print(f"[3] bg_R={bg_r}")
    for rval, count, nrows in text_vals:
        print(f"    text R={rval}: {count}px, {nrows} rows")

    if len(text_vals) < 2:
        print("ERROR: Could not find 2 text lines!")
        session.close()
        return False

    # Determine which line is "upper" (more rows in top half of image)
    r_chan = arr[:, :, 0]
    line_y_avgs = []
    for rval, count, nrows in text_vals:
        mask = (r_chan == rval).astype(np.float32)
        text_row_indices = [y for y in range(h) if mask[y].sum() > 0]
        avg_y = np.mean(text_row_indices)
        line_y_avgs.append(avg_y)

    # Sort: upper line first (lower avg_y = higher in image)
    order = sorted(range(len(text_vals)), key=lambda i: line_y_avgs[i])

    # Process each line (both FWD and REV)
    line_results = []  # each is a list of candidate 4-char strings
    for idx in order:
        rval, count, nrows = text_vals[idx]
        mask = (r_chan == rval).astype(np.float32)
        text_row_indices = [y for y in range(h) if mask[y].sum() > 0]
        binary_rows = mask[text_row_indices]

        nn_order = nn_sort_rows(binary_rows)
        sorted_fwd = binary_rows[nn_order]
        sorted_rev = binary_rows[list(reversed(nn_order))]

        # Debug: show characters
        li = order.index(idx) + 1
        print(f"\n{'='*60}")
        print(f"Line {li} (R={rval}, avg_y={line_y_avgs[idx]:.0f})")
        print(f"{'='*60}")

        candidates = set()
        for direction, srows in [("FWD", sorted_fwd), ("REV", sorted_rev)]:
            groups = find_column_groups(srows)
            widths = [g[1] - g[0] + 1 for g in groups]
            print(f"\n  {direction}: groups={len(groups)}, widths={widths}")

            if len(groups) >= 6:
                copy_groups = groups[:3]
                char_groups = groups[3:6]
            else:
                print(f"  WARNING: expected 6 groups, got {len(groups)}")
                continue

            # Debug each character
            for gi, (cs, ce) in enumerate(copy_groups):
                print_char_debug(srows, cs, ce, f"Copy{gi+1}")
            for gi, (cs, ce) in enumerate(char_groups):
                print_char_debug(srows, cs, ce, f"Unique{gi+1}")

            # Get result
            result, _ = process_line(srows)
            print(f"  {direction} result: {result}")
            candidates.add(result)

        line_results.append(candidates)
        print(f"\n  Line {li} candidates: {candidates}")

    # Build answers
    if len(line_results) < 2:
        print("ERROR: < 2 lines processed")
        session.close()
        return False

    answers = set()
    for t1 in line_results[0]:
        for t2 in line_results[1]:
            answers.add(t1 + t2)
    # Also try reversed line order (in case upper/lower detection was wrong)
    for t1 in line_results[1]:
        for t2 in line_results[0]:
            answers.add(t1 + t2)

    dt = time.time() - t0
    print(f"\n[4] {len(answers)} candidates ({dt:.1f}s, {180 - dt:.0f}s left)")

    # Submit answers
    for answer in sorted(answers):
        if '?' in answer:
            continue
        dt = time.time() - t0
        if dt > 170:
            print("  Timer nearly expired!")
            break
        print(f"  → Submitting: {answer!r}")
        resp = session.post(
            "https://www.hackthissite.org/missions/prog/7/index.php",
            data={"solution": answer, "submitbutton": "submit"},
            headers=HEADERS,
        )
        text = resp.text.lower()
        if "ongratulation" in text or "you have completed" in text:
            print(f"\n  ✓ ACCEPTED: {answer}")
            session.close()
            return True
        if "expired" in text:
            print("  Timer expired!")
            break

    print("\n  All attempts failed")
    session.close()
    return False


if __name__ == "__main__":
    solve()
