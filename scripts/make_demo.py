"""Regenerate the original CC0 demo assets. Development-only dependency: cairosvg."""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def main():
    try:
        import cairosvg
    except ImportError:
        raise SystemExit('To regenerate assets: python -m pip install cairosvg')
    if not shutil.which('ffmpeg'):
        raise SystemExit('FFmpeg must be installed and on PATH')
    assets = ROOT / 'web' / 'assets'
    with tempfile.TemporaryDirectory() as temp:
        image = Path(temp) / 'cover.png'
        cairosvg.svg2png(url=str(assets / 'demo-cover.svg'), write_to=str(image), output_width=1920, output_height=1080)
        for height in (1080, 720, 480):
            width = round(height * 16 / 9)
            # 480 uses the conventional 854x480 even-pixel raster.
            width += width % 2
            filters = (f"zoompan=z='1+0.0005*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':"
                       f"d=144:s={width}x{height}:fps=24,fade=t=in:st=0:d=0.4,fade=t=out:st=5.5:d=0.5,format=yuv420p")
            command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(image),
                       '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100:duration=6',
                       '-filter_complex', f'[0:v]{filters}[v];[1:a]volume=0.05,afade=t=in:d=0.5,afade=t=out:st=5.4:d=0.6[a]',
                       '-map', '[v]', '-map', '[a]', '-t', '6', '-c:v', 'libx264', '-preset', 'fast',
                       '-crf', '25', '-c:a', 'aac', '-b:a', '64k', '-movflags', '+faststart', '-threads', '2',
                       str(assets / f'demo-{height}.mp4')]
            subprocess.run(command, check=True)
            print(f'Created demo-{height}.mp4')


if __name__ == '__main__':
    main()
