from PIL import Image
import os
from pathlib import Path

try:
    import pyperclip
except ModuleNotFoundError:
    pyperclip = None

CODE = {
    '.-': 'A', '-...': 'B', '-.-.': 'C',
    '-..': 'D', '.': 'E', '..-.': 'F',
    '--.': 'G', '....': 'H', '..': 'I',
    '.---': 'J', '-.-': 'K', '.-..': 'L',
    '--': 'M', '-.': 'N', '---': 'O',
    '.--.': 'P', '--.-': 'Q', '.-.': 'R',
    '...': 'S', '-': 'T', '..-': 'U',
    '...-': 'V', '.--': 'W', '-..-': 'X',
    '-.--': 'Y', '--..': 'Z',

    '-----': '0', '.----': '1', '..---': '2',
    '...--': '3', '....-': '4', '.....': '5',
    '-....': '6', '--...': '7', '---..': '8',
    '----.': '9'
}

def decode_morse(morse_code):
    words = morse_code.strip().split("  ")
    decoded_words = []

    for word in words:
        letters = word.split()
        decoded_letters = []
        for l in letters:
            decoded_letters.append(CODE.get(l, '?'))
        decoded_words.append("".join(decoded_letters))

    return " ".join(decoded_words)

script_dir = Path(__file__).resolve().parent
image_path = script_dir / "download.png"

print("Direktori aktif:", os.getcwd())

with Image.open(image_path) as im:
    im = im.convert("1")
    pixel = im.load()

    last = 0
    pos = -1
    morse = []

    for i in range(im.height):
        for j in range(im.width):
            pos += 1
            if pixel[j, i] == 255:
                morse.append(chr(pos - last))
                last = pos

morse = "".join(morse)
print("Morse raw:", morse)

decoded_text = decode_morse(morse)
print("Decoded text:", decoded_text)

if pyperclip is not None:
    pyperclip.copy(decoded_text)
    print("Teks sudah masuk clipboard!")
else:
    print("pyperclip belum terpasang; skip copy ke clipboard.")