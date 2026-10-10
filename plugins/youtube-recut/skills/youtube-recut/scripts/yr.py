"""Shared project access for the youtube-recut scripts.

Every script takes the PROJECT FOLDER as its first argument. Nothing is written next to the scripts
(the plugin install is read-only); all state lives in the project:

  <project>/project.json      sources, tracks, reference edit, brand, audio (see references/project-json.md)
  <project>/plan/beats.json   the APPROVED beat plan (human-ruled; scripts never write it)
  <project>/plan/edit-plan.md the plan in prose, with the user's rulings
  <project>/transcripts/      <src>-raw-words.json per source (transcribe.py), optional corrections
  <project>/work/             beats-mapped.json, pieces.json, zoom-plan.json (generated, re-runnable)
  <project>/cards/            rendered intro/outro cards per track
  <project>/renders/          every render and its .ass/.log, versioned, never overwritten
  <project>/review/           QA reports, review proxies, the user's revisions log
"""
import datetime, json, os, pathlib, shutil, subprocess, sys

SKILL = pathlib.Path(__file__).resolve().parent.parent
ENV = pathlib.Path(os.environ.get('YR_ENV', pathlib.Path.home() / '.cache/youtube-recut/venv'))


def die(msg):
    sys.exit(f'[youtube-recut] {msg}')


class Project:
    def __init__(self, root):
        self.root = pathlib.Path(root).expanduser().resolve()
        pj = self.root / 'project.json'
        if not pj.exists():
            die(f'no project.json in {self.root} (start from {SKILL / "assets/project.template.json"})')
        self.cfg = json.load(open(pj))
        self.plan, self.work = self.root / 'plan', self.root / 'work'
        self.transcripts, self.renders = self.root / 'transcripts', self.root / 'renders'
        self.cards, self.review = self.root / 'cards', self.root / 'review'
        for d in (self.work, self.renders, self.cards, self.review, self.transcripts):
            d.mkdir(parents=True, exist_ok=True)

    # ---- config -------------------------------------------------------------------------------
    @property
    def sources(self):
        return {k: str(pathlib.Path(v).expanduser()) for k, v in self.cfg['sources'].items()}

    def track(self, t):
        if t not in self.cfg['tracks']:
            die(f'unknown track {t!r}; project has {list(self.cfg["tracks"])}')
        tr = dict(self.cfg['tracks'][t], side=t)
        tr['words'] = {k: str(self.transcripts / v) for k, v in tr['words'].items()}
        ref = tr.get('reference') or {}
        tr['vtt'] = str(pathlib.Path(ref['vtt']).expanduser()) if ref.get('vtt') else None
        tr['master'] = str(pathlib.Path(ref['master']).expanduser()) if ref.get('master') else None
        return tr

    @property
    def brand(self):
        b = dict(self.cfg.get('brand', {}))
        preset = b.pop('preset', None)
        if preset:
            base = json.load(open(SKILL / 'assets' / 'presets' / f'{preset}.json'))
            base.update(b)
            b = base
        for k in ('theme_wav', 'outro_wav'):
            if b.get(k):
                b[k] = str(pathlib.Path(b[k]).expanduser())
        return b

    @property
    def audio(self):
        a = {'target_lufs': -14, 'true_peak': -1.5, 'limit_dbfs': -2, 'denoise_atten_db': 12}
        a.update(self.cfg.get('audio', {}))
        return a

    # ---- state files --------------------------------------------------------------------------
    def beats(self):
        p = self.plan / 'beats.json'
        if not p.exists():
            die(f'no approved plan at {p}')
        return json.load(open(p))['tracks']

    def read(self, name, default=None):
        p = self.work / name
        if not p.exists():
            if default is not None:
                return default
            die(f'{p} missing: run the stage that writes it first')
        return json.load(open(p))

    def write(self, name, data):
        """Write work/<name>; the previous version is kept in work/.history/ (nothing is ever lost)."""
        p = self.work / name
        if p.exists():
            h = self.work / '.history'
            h.mkdir(exist_ok=True)
            shutil.copy2(p, h / f"{p.stem}.{datetime.datetime.now():%Y%m%dT%H%M%S}{p.suffix}")
        tmp = p.with_suffix('.tmp')
        json.dump(data, open(tmp, 'w'), indent=1)
        tmp.replace(p)


def ffmpeg_libass():
    """An ffmpeg that has the libass `subtitles` filter (captions are burned with it)."""
    cands = [os.environ.get('YR_FFMPEG')]
    try:
        import imageio_ffmpeg
        cands.append(imageio_ffmpeg.get_ffmpeg_exe())
    except ImportError:
        pass
    cands.append(shutil.which('ffmpeg'))
    for c in filter(None, cands):
        out = subprocess.run([c, '-hide_banner', '-filters'], capture_output=True, text=True).stdout
        if ' subtitles ' in out:
            return c
    die('no ffmpeg with libass (subtitles filter) found; run scripts/setup_env.sh')


def deepfilter_bin():
    b = ENV / 'bin' / 'deepFilter'
    if not b.exists():
        die(f'{b} missing; run scripts/setup_env.sh')
    return str(b)
