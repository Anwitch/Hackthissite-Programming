"""
HackThisSite Programming Level 7 - Manual OCR Solver

Downloads the scrambled image, unscrambles the 2 text lines,
displays them scaled up for the user to read, then submits
the user's answer.
"""

import requests
import numpy as np
import time
import os
from io import BytesIO
from PIL import Image
from collections import Counter
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

USERNAME = os.getenv("HTS_USERNAME")
PASSWORD = os.getenv("HTS_PASSWORD")
URL_LOGIN = "https://www.hackthissite.org/user/login"
URL_PROG7 = "https://www.hackthissite.org/missions/prog/7/"
HEADERS = {"Referer": "https://www.hackthissite.org/"}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


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

    def path_cost(order):
        return sum(dist[order[i]][order[i+1]] for i in range(len(order)-1))

    # Greedy NN from every starting point
    best_order = None
    best_cost = float('inf')
    for start in range(n):
        order = [start]
        used = {start}
        for _ in range(n - 1):
            last = order[-1]
            d = dist[last].copy()
            d[list(used)] = float('inf')
            nxt = int(np.argmin(d))
            order.append(nxt)
            used.add(nxt)
        cost = path_cost(order)
        if cost < best_cost:
            best_cost = cost
            best_order = order

    # 2-opt: reverse segments
    improved = True
    while improved:
        improved = False
        for i in range(n - 1):
            for j in range(i + 2, n):
                # Cost of removing edges (i-1,i) and (j,j+1) vs new edges
                old = dist[best_order[i-1]][best_order[i]] if i > 0 else 0
                old += dist[best_order[j]][best_order[j+1]] if j < n-1 else 0
                new = dist[best_order[i-1]][best_order[j]] if i > 0 else 0
                new += dist[best_order[i]][best_order[j+1]] if j < n-1 else 0
                if new < old:
                    best_order[i:j+1] = best_order[i:j+1][::-1]
                    improved = True

    # Or-opt: relocate single rows to better positions
    improved = True
    while improved:
        improved = False
        for i in range(n):
            # Remove row i from order
            row_i = best_order[i]
            remaining = best_order[:i] + best_order[i+1:]
            # Current cost contribution of row i
            old_cost = 0
            if i > 0:
                old_cost += dist[best_order[i-1]][row_i]
            if i < n - 1:
                old_cost += dist[row_i][best_order[i+1]]
            if i > 0 and i < n - 1:
                old_cost -= dist[best_order[i-1]][best_order[i+1]]
            # Try inserting at every position in remaining
            best_pos = i
            best_delta = 0
            for j in range(len(remaining) + 1):
                insert_cost = 0
                if j > 0:
                    insert_cost += dist[remaining[j-1]][row_i]
                if j < len(remaining):
                    insert_cost += dist[row_i][remaining[j]]
                if j > 0 and j < len(remaining):
                    insert_cost -= dist[remaining[j-1]][remaining[j]]
                delta = insert_cost - old_cost
                if delta < best_delta - 0.5:
                    best_delta = delta
                    best_pos = j
            if best_delta < -0.5:
                remaining.insert(best_pos, row_i)
                best_order = remaining
                improved = True
                break  # restart

    return best_order


def build_line_image(sorted_rows, scale=8):
    """Build a scaled-up PIL image from sorted binary rows (white text on black)."""
    h, w = sorted_rows.shape
    # Invert: 1 (text) → white, 0 → black
    pixels = (sorted_rows * 255).astype(np.uint8)
    img = Image.fromarray(pixels, mode='L')
    img = img.resize((w * scale, h * scale), Image.NEAREST)
    return img


def solve():
    t0 = time.time()
    session = requests.Session()

    # Login
    session.post(URL_LOGIN, data={"username": USERNAME, "password": PASSWORD}, headers=HEADERS)
    print(f"[1] Logged in ({time.time() - t0:.1f}s)")

    # Load page (starts the 180s timer)
    session.get(URL_PROG7, headers=HEADERS)

    # Download image
    resp = session.get("https://www.hackthissite.org/missions/prog/7/BMP", headers=HEADERS)
    img = Image.open(BytesIO(resp.content))
    arr = np.array(img)
    h, w = arr.shape[0], arr.shape[1]
    print(f"[2] Image: {w}x{h} ({time.time() - t0:.1f}s)")

    # Find text R-values
    bg_r, text_vals = find_text_r_values(arr)
    print(f"[3] bg_R={bg_r}, text lines: {[(v, n) for v, _, n in text_vals]}")

    if len(text_vals) < 2:
        print("ERROR: Could not find 2 text lines!")
        session.close()
        return

    r_chan = arr[:, :, 0]

    # Determine line order by average Y position (lower avg_y = upper in image)
    line_data = []
    for rval, count, nrows in text_vals:
        mask = (r_chan == rval).astype(np.float32)
        text_row_indices = [y for y in range(h) if mask[y].sum() > 0]
        avg_y = np.mean(text_row_indices)
        binary_rows = mask[text_row_indices]
        line_data.append((rval, avg_y, binary_rows))

    # Sort: upper line (smaller avg_y) first
    line_data.sort(key=lambda x: x[1])

    # Unscramble each line and show both FWD and REV
    line_images = []
    for li, (rval, avg_y, binary_rows) in enumerate(line_data):
        # Save scrambled (raw) for debugging
        raw_img = build_line_image(binary_rows, scale=3)
        raw_img.save(os.path.join(SCRIPT_DIR, f"line{li+1}_scrambled.png"))

        nn_order = nn_sort_rows(binary_rows)
        sorted_fwd = binary_rows[nn_order]
        sorted_rev = binary_rows[list(reversed(nn_order))]

        print(f"  Line {li+1} (R={rval}, {len(binary_rows)} rows, avg_y={avg_y:.0f})")

        # Show consecutive row distances to detect bad joins
        dists = []
        for r in range(len(nn_order) - 1):
            d = np.sum(binary_rows[nn_order[r]] != binary_rows[nn_order[r+1]])
            dists.append(d)
        avg_d = np.mean(dists) if dists else 0
        max_d = max(dists) if dists else 0
        print(f"    NN distances: avg={avg_d:.1f}, max={max_d:.0f}, total={sum(dists):.0f}")

        # Pick direction: the one with denser bottom rows (serif at bottom)
        fwd_bot = np.mean(sorted_fwd[-3:])
        fwd_top = np.mean(sorted_fwd[:3])
        rev_bot = np.mean(sorted_rev[-3:])
        rev_top = np.mean(sorted_rev[:3])

        # Usually the correct direction has heavier bottom (baseline/serif)
        fwd_score = fwd_bot - fwd_top
        rev_score = rev_bot - rev_top

        if fwd_score >= rev_score:
            primary, secondary = sorted_fwd, sorted_rev
            primary_name, secondary_name = "FWD", "REV"
        else:
            primary, secondary = sorted_rev, sorted_fwd
            primary_name, secondary_name = "REV", "FWD"

        print(f"  Line {li+1} (R={rval}, avg_y={avg_y:.0f}): best direction = {primary_name}")
        line_images.append((primary, secondary, primary_name, secondary_name))

    # Save multiple scale options + individual line images
    raw_lines = []  # (primary_rows, secondary_rows) per line
    for primary, secondary, pname, sname in line_images:
        raw_lines.append((primary, secondary))

    # Generate images at multiple scales
    for scale in [3, 4, 5, 6, 8]:
        gap = max(4, scale * 2)
        parts = []
        for li, (prim, sec) in enumerate(raw_lines):
            parts.append(build_line_image(prim, scale=scale))
        max_w = max(p.width for p in parts)
        total_h = sum(p.height for p in parts) + gap * (len(parts) - 1)
        canvas = Image.new('L', (max_w, total_h), 0)
        y_off = 0
        for p in parts:
            canvas.paste(p, (0, y_off))
            y_off += p.height + gap
        path = os.path.join(SCRIPT_DIR, f"decoded_{scale}x.png")
        canvas.save(path)
        print(f"  Saved: decoded_{scale}x.png  ({canvas.width}x{canvas.height})")

    # Save all 4 views (FWD+REV for both lines) at scale=3
    all_parts = []
    all_labels = []
    for li, (prim, sec) in enumerate(raw_lines):
        pname = line_images[li][2]
        sname = line_images[li][3]
        all_parts.append(build_line_image(prim, scale=3))
        all_labels.append(f"Line{li+1}_{pname}")
        all_parts.append(build_line_image(sec, scale=3))
        all_labels.append(f"Line{li+1}_{sname}")
    max_w = max(p.width for p in all_parts)
    total_h = sum(p.height for p in all_parts) + 8 * (len(all_parts) - 1)
    canvas = Image.new('L', (max_w, total_h), 0)
    y_off = 0
    for p in all_parts:
        canvas.paste(p, (0, y_off))
        y_off += p.height + 8
    alt_path = os.path.join(SCRIPT_DIR, "decoded_all_directions.png")
    canvas.save(alt_path)
    print(f"  Saved: decoded_all_directions.png (all FWD+REV)")

    # Save individual line images at scale=4
    for li, (prim, sec) in enumerate(raw_lines):
        for tag, data in [("primary", prim), ("secondary", sec)]:
            img = build_line_image(data, scale=4)
            p = os.path.join(SCRIPT_DIR, f"line{li+1}_{tag}.png")
            img.save(p)

    # Auto-open the 5x version
    default_path = os.path.join(SCRIPT_DIR, "decoded_5x.png")
    print(f"\n  >>> Opening: decoded_5x.png")
    try:
        os.startfile(default_path)
        print("  Image opened!")
    except Exception:
        print("  (Could not auto-open, please open manually)")

    dt = time.time() - t0
    remaining = 180 - dt
    print(f"\n  Time used: {dt:.1f}s, remaining: {remaining:.0f}s")
    print(f"  Format: upper line chars + lower line chars (no spaces)")
    print(f"  Available scales: decoded_3x.png, decoded_4x.png, decoded_5x.png, decoded_6x.png, decoded_8x.png")
    print(f"  Type '3x'-'8x' to open a different scale, 'alt' for all directions, 'q' to quit.\n")

    # Wait for user input
    while True:
        answer = input("  Enter solution (or scale like '5x', 'alt', 'q'): ").strip()

        if answer.lower() == 'q':
            print("  Quitting.")
            break

        if answer.lower() == 'alt':
            try:
                os.startfile(alt_path)
            except Exception:
                print(f"  Open manually: {alt_path}")
            continue

        if answer.lower() in ('3x', '4x', '5x', '6x', '8x'):
            p = os.path.join(SCRIPT_DIR, f"decoded_{answer.lower()}.png")
            try:
                os.startfile(p)
            except Exception:
                print(f"  Open manually: {p}")
            continue

        if not answer:
            continue

        dt = time.time() - t0
        if dt > 175:
            print("  Timer expired! Need to restart.")
            break

        print(f"  Submitting '{answer}' ({dt:.1f}s elapsed)...")
        resp = session.post(
            "https://www.hackthissite.org/missions/prog/7/index.php",
            data={"solution": answer, "submitbutton": "submit"},
            headers=HEADERS,
        )
        text = resp.text.lower()
        if "ongratulation" in text or "you have completed" in text:
            print(f"\n  ✓✓ CORRECT! Answer: {answer}")
            break
        elif "expired" in text:
            print("  Timer expired! Need to restart the script.")
            break
        else:
            print("  Wrong answer. Try again (or 'alt' for alternate views, 'q' to quit).")

    session.close()


if __name__ == "__main__":
    solve()
