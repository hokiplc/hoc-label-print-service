Place `DejaVuSans.ttf` and `DejaVuSans-Bold.ttf` here (or point `HOC_FONT_DIR` elsewhere).

On Raspberry Pi OS / Debian:

```bash
sudo apt-get install -y fonts-dejavu-core
cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf .
cp /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf .
```

If the font files are missing, the template falls back to Pillow's built-in bitmap
font, which renders but looks much lower quality on the printed label.
