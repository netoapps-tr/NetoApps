"""Extract a contact sheet from a local screen recording."""
import sys
from pathlib import Path

import cv2
from PIL import Image, ImageDraw


def main():
    capture = cv2.VideoCapture(sys.argv[1])
    duration = capture.get(cv2.CAP_PROP_FRAME_COUNT) / capture.get(cv2.CAP_PROP_FPS)
    output = Path(sys.argv[2])
    output.mkdir(parents=True, exist_ok=True)
    sheet = Image.new('RGB', (1600, 1000), '#222222')
    draw = ImageDraw.Draw(sheet)
    for index in range(16):
        seconds = duration * index / 16
        capture.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        ok, frame = capture.read()
        if not ok:
            continue
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        image.save(output / f'{index}.png')
        image.thumbnail((398, 220))
        x, y = (index % 4) * 400, (index // 4) * 250
        sheet.paste(image, (x, y + 25))
        draw.text((x + 6, y + 5), f'{seconds:.2f} s', fill='white')
    sheet.save(output / 'contact.jpg', quality=65)
    capture.release()


if __name__ == '__main__':
    main()
