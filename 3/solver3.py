"""
HackThisSite Programming Level 3 Solver (Python 3)
Reverses the PHP encryptString() algorithm to recover serial numbers.
"""
import hashlib
import time


def eval_cross_total(hex_string):
    """Sum of hex digit values — equivalent to PHP evalCrossTotal()."""
    return sum(int(c, 16) for c in hex_string)


def md5hex(data):
    """MD5 hex digest. Accepts str or int (converted to decimal string like PHP)."""
    if isinstance(data, int):
        data = str(data)
    return hashlib.md5(data.encode("latin-1")).hexdigest()


# Valid characters for the variable parts of serials: A-Z and 0-9
VALID = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")


def known_char(pos):
    """Return the fixed character at position *pos* within the 20-char serial
    format, or None for variable positions.

    Format per serial:  XXX-XXX-OEM-XXX-1.1\\n
    Indices mod 20:     0123456789...
    """
    p = pos % 20
    if p in (3, 7, 11, 15):
        return "-"
    if p == 8:
        return "O"
    if p == 9:
        return "E"
    if p == 10:
        return "M"
    if p == 16:
        return "1"
    if p == 17:
        return "."
    if p == 18:
        return "1"
    if p == 19:
        return "\n"
    return None


def decrypt(enc):
    """Brute-force reverse the encryption and return the plaintext serials."""
    n = len(enc)
    known = [known_char(i) for i in range(n)]

    def recurse(pos, pt, pw, total, md5_ctx):
        if pos == n:
            return "".join(pt)

        # encrypted[i] = ord(char) + hex_digit - intMD5Total
        # => ord(char) + hex_digit = encrypted[i] + intMD5Total
        target = enc[pos] + total
        kc = known[pos]

        # Pre-compute the half that depends only on the current total
        total_md5_half = md5hex(total)[:16]

        if pos < 32:
            # Still building the 32-char password MD5 hex string
            if kc is not None:
                h = target - ord(kc)
                if h < 0 or h > 15:
                    return None
                ctx = md5_ctx.copy()
                ctx.update(kc.encode("latin-1"))
                new_total = eval_cross_total(ctx.hexdigest()[:16] + total_md5_half)
                pt.append(kc)
                result = recurse(pos + 1, pt, pw + format(h, "x"), new_total, ctx)
                pt.pop()
                return result
            else:
                for h in range(16):
                    co = target - h
                    if co < 0 or co > 127:
                        continue
                    c = chr(co)
                    if c not in VALID:
                        continue
                    ctx = md5_ctx.copy()
                    ctx.update(c.encode("latin-1"))
                    new_total = eval_cross_total(ctx.hexdigest()[:16] + total_md5_half)
                    pt.append(c)
                    result = recurse(
                        pos + 1, pt, pw + format(h, "x"), new_total, ctx
                    )
                    if result is not None:
                        return result
                    pt.pop()
                return None
        else:
            # Password MD5 fully known — hex digit is determined
            h = int(pw[pos % 32], 16)
            co = target - h
            if kc is not None:
                if co != ord(kc):
                    return None
                c = kc
            else:
                if co < 0 or co > 127:
                    return None
                c = chr(co)
                if c not in VALID:
                    return None

            ctx = md5_ctx.copy()
            ctx.update(c.encode("latin-1"))
            new_total = eval_cross_total(ctx.hexdigest()[:16] + total_md5_half)
            pt.append(c)
            result = recurse(pos + 1, pt, pw, new_total, ctx)
            pt.pop()
            return result

    # Bootstrap: try every valid (first_char, first_hex_digit) pair.
    # The initial intMD5Total = ord(char0) + hex0 - enc[0].
    chars0 = [known[0]] if known[0] else sorted(VALID)
    for c0 in chars0:
        for h0 in range(16):
            init_total = ord(c0) + h0 - enc[0]
            if init_total < 0 or init_total > 480:
                continue

            ctx = hashlib.md5(c0.encode("latin-1"))
            new_total = eval_cross_total(
                ctx.hexdigest()[:16] + md5hex(init_total)[:16]
            )
            result = recurse(1, [c0], format(h0, "x"), new_total, ctx)
            if result is not None:
                return result

    return None


if __name__ == "__main__":
    encrypted_input = input("Enter Encrypted String: ").strip()
    values = list(map(int, encrypted_input.split()))
    num_serials = len(values) // 20
    print(f"Decrypting {len(values)} values ({num_serials} serials)...")

    t0 = time.time()
    plaintext = decrypt(values)
    dt = time.time() - t0

    if plaintext:
        serials = plaintext.strip().split("\n")
        print(f"\nDecrypted in {dt:.2f}s:\n")
        for i, s in enumerate(serials, 1):
            print(f"  {i}. {s}")
        print(f"\n>>> Answer (last serial): {serials[-1]}")
    else:
        print("Decryption failed.")
