"""Build an ASS caption file from word timings on the OUTPUT timeline (style from the brand preset).

Input JSON: {"words": [{"w": str, "s": float, "e": float}, ...]} already mapped to output time.
Default style: one centered line near the top, ~190 px at 4K, soft black
outline; every word is visible for the whole line and the spoken word is highlighted.

Default colors (override them in the brand preset's "caption" block):
  text   #f0ede3
  active #c8a64b
"""
import json
import sys

MAX_CHARS = 44        # a caption line holds ~44 chars at this size inside the 3840 frame
MAX_GAP = 0.6         # a pause longer than this starts a new line
MIN_HOLD = 0.25       # shortest time a word stays highlighted
TEXT = '&H00E3EDF0&'  # ASS is &HAABBGGRR: #f0ede3
ACTIVE = '&H004BA6C8&'  # #c8a64b
# Font "Manrope Cap" = a static Manrope Bold instance renamed so libass cannot match the ExtraLight
# default instance (assets/fonts, SIL Open Font License). size/margin_v are tuned for a 3840x2160 frame.
DEFAULT_STYLE = {'font': 'Manrope Cap', 'size': 204, 'margin_v': 56, 'text': TEXT, 'active': ACTIVE}


def ts(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f'{h}:{m:02d}:{s:05.2f}'


def lines_of(words):
    line, out = [], []
    for w in words:
        cand = ' '.join(x['w'] for x in line + [w])
        gap = w['s'] - line[-1]['e'] if line else 0
        ends_sentence = bool(line) and line[-1]['w'][-1:] in '.?!'
        if line and (len(cand) > MAX_CHARS or gap > MAX_GAP or ends_sentence):
            out.append(line); line = []
        line.append(w)
    if line:
        out.append(line)
    return out


def esc(t: str) -> str:
    return t.replace('\\', '\\\\').replace('{', '(').replace('}', ')')


def build(words, style=None, width=3840, height=2160):
    st = dict(DEFAULT_STYLE, **(style or {}))
    TEXT, ACTIVE = st['text'], st['active']
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{st['font']},{st['size']},{TEXT},{TEXT},&H00000000&,&H80000000&,-1,0,0,0,100,100,0,0,1,12,4,8,120,120,{st['margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    lines = lines_of(words)
    for li, line in enumerate(lines):
        nxt = lines[li + 1][0]['s'] if li + 1 < len(lines) else float('inf')
        for i, w in enumerate(line):
            start = w['s']
            end = line[i + 1]['s'] if i + 1 < len(line) else min(max(w['e'], w['s'] + MIN_HOLD), nxt)
            parts = []
            for j, x in enumerate(line):
                t = esc(x['w'])
                parts.append(f'{{\\c{ACTIVE}}}{t}{{\\c{TEXT}}}' if j == i else t)
            ev.append(f'Dialogue: 0,{ts(start)},{ts(end)},Cap,,0,0,0,,{{\\blur3}}' + ' '.join(parts))
    return head + '\n'.join(ev) + '\n'


if __name__ == '__main__':
    words = json.load(open(sys.argv[1]))['words']
    open(sys.argv[2], 'w').write(build(words))
    print('captions', sys.argv[2], len(words), 'words')
