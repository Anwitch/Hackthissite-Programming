import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import numpy as np
import bz2
import os

# =========================
# EKSTRAK FILE BZ2
# =========================
script_dir = os.path.dirname(__file__)
bz2_file_path = os.path.join(script_dir, 'plotMe.xml.bz2')
xml_file_path = os.path.join(script_dir, 'plotMe.xml', 'plotMe.xml')

# Pastikan direktori tujuan ada
os.makedirs(os.path.dirname(xml_file_path), exist_ok=True)

with bz2.BZ2File(bz2_file_path, 'rb') as f_in:
    with open(xml_file_path, 'wb') as f_out:
        f_out.write(f_in.read())

# =========================
# BACA FILE XML
# =========================
tree = ET.parse(xml_file_path)
root = tree.getroot()

lines = []
arcs = []

# =========================
# AMBIL DATA LINE
# =========================
for elem in root.findall(".//Line"):
    x1 = float(elem.find("XStart").text)
    y1 = float(elem.find("YStart").text)
    x2 = float(elem.find("XEnd").text)
    y2 = float(elem.find("YEnd").text)

    color_elem = elem.find("Color")
    color = color_elem.text.lower() if color_elem is not None else "white"

    # Supaya white tetap kelihatan di background hitam
    if color == "white":
        color = "gray"

    lines.append((x1, y1, x2, y2, color))


# =========================
# AMBIL DATA ARC
# =========================
for elem in root.findall(".//Arc"):
    xc = float(elem.find("XCenter").text)
    yc = float(elem.find("YCenter").text)
    radius = float(elem.find("Radius").text)
    arc_start = float(elem.find("ArcStart").text)
    arc_extend = float(elem.find("ArcExtend").text)

    color_elem = elem.find("Color")
    color = color_elem.text.lower() if color_elem is not None else "white"

    if color == "white":
        color = "gray"

    arcs.append((xc, yc, radius, arc_start, arc_extend, color))


# =========================
# VISUALISASI
# =========================
fig, ax = plt.subplots(figsize=(7, 6), dpi=150)

# Perlebar X supaya teks merah tidak kepotong
ax.set_xlim(0, 700)
ax.set_ylim(0, 600)
ax.set_aspect('equal')

ax.set_xlabel("X")
ax.set_ylabel("Y")
ax.set_title("Visualization of Lines and Arcs")

# Background hitam
fig.patch.set_facecolor("black")
ax.set_facecolor("black")

# Warna teks putih
ax.tick_params(colors='white')
ax.xaxis.label.set_color('white')
ax.yaxis.label.set_color('white')
ax.title.set_color('white')

# Gambar garis
for x1, y1, x2, y2, color in lines:
    ax.plot([x1, x2], [y1, y2], color=color, linewidth=2)

# Gambar arc
for xc, yc, radius, arc_start, arc_extend, color in arcs:
    theta = np.linspace(
        np.radians(arc_start),
        np.radians(arc_start + arc_extend),
        100
    )

    x_arc = xc + radius * np.cos(theta)
    y_arc = yc + radius * np.sin(theta)

    ax.plot(x_arc, y_arc, color=color, linewidth=2)

plt.grid(False)
plt.show()