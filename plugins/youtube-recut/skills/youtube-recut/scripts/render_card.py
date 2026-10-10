"""Render a track's record intro/outro card (Playwright frames -> H.264 + brand audio).

Usage: python render_card.py <project> <track> <intro|outro> <out.mp4>
Text, series label, music and frame counts come from the brand preset (assets/presets/<preset>.json).
Intro audio = the first N frames of the theme with a short fade (the render's music bed continues the theme
under the voice); outro = the outro bumper. Refuses to overwrite.
"""
import asyncio, pathlib, subprocess, sys, tempfile, urllib.parse
from playwright.async_api import async_playwright

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from yr import Project, SKILL, ffmpeg_libass  # noqa: E402

HTML = SKILL / 'assets' / 'cards' / 'record-anim.html'


async def frames(qs, out_dir, n, fps):
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel='chrome', headless=True)
        page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
        await page.goto(f'file://{HTML}?{qs}')
        await page.evaluate('window.ready')
        for i in range(n):
            await page.evaluate(f'window.setT({i / fps}, {n / fps})')
            await page.screenshot(path=str(out_dir / f'{i:04d}.png'))
        await browser.close()


def main():
    P = Project(sys.argv[1]); tr = P.track(sys.argv[2]); kind, out = sys.argv[3], pathlib.Path(sys.argv[4])
    if out.exists():
        sys.exit(f'Refusing to overwrite {out}')
    b = P.brand; c = b['cards']; fps = c['fps']
    n = c['intro_frames'] if kind == 'intro' else c['outro_frames']
    audio = b['theme_wav'] if kind == 'intro' else b['outro_wav']
    qs = urllib.parse.urlencode({'mode': kind, 'side': tr['n'], 'title': tr['title'] if kind == 'intro' else '',
                                 'series': b['series'], 'track_word': b.get('track_word', 'Track'), 'brand': b['card_brand'],
                                 'name': b['card_name'], 'eyebrow': b['outro_eyebrow'], 'headline': b['outro_headline'],
                                 'urls': '|'.join(b['outro_urls'])})
    dur = n / fps
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        asyncio.run(frames(qs, tmp, n, fps))
        fade = f",afade=t=out:st={dur - c['intro_fade_s']:.3f}:d={c['intro_fade_s']}" if kind == 'intro' else ''
        subprocess.run([ffmpeg_libass(), '-hide_banner', '-loglevel', 'error', '-n', '-framerate', str(fps), '-i', str(tmp / '%04d.png'),
                        '-i', audio, '-filter_complex',
                        f'[0:v]scale=3840:2160:flags=lanczos,format=yuv420p[v];[1:a]aresample=48000,apad,atrim=end={dur:.6f}{fade}[a]',
                        '-map', '[v]', '-map', '[a]', '-frames:v', str(n), '-c:v', 'libx264', '-preset', 'medium', '-crf', '16',
                        '-r', str(fps), '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2', str(out)], check=True)
    print('CARD', out)


if __name__ == '__main__':
    main()
