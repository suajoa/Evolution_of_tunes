"""
악보 진화기 - 핵심 로직 (Streamlit 등 UI에 의존하지 않음)

변수 3가지
  1) 전체 음표의 수  2) 각 음의 길이  3) 각 음의 높이
"""
import copy
import io
import math
import random
import struct
import wave
from array import array
from dataclasses import dataclass, field

# ---------------------------------------------------------------- 설정
SCALE = {0, 2, 4, 5, 7, 9, 11}           # C 장조 (바꾸면 다른 음계)
LOW, HIGH = 60, 84                       # C4 ~ C6
PITCH_POOL = [p for p in range(LOW, HIGH + 1) if p % 12 in SCALE]
DURATIONS = [0.25, 0.5, 1.0, 2.0, 4.0]   # 4분음표 = 1.0
DUR_NAME = {0.25: "16분", 0.5: "8분", 1.0: "4분", 2.0: "2분", 4.0: "온"}
MIN_NOTES, MAX_NOTES = 4, 32
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def pitch_name(p: int) -> str:
    return f"{NOTE_NAMES[p % 12]}{p // 12 - 1}"


# ---------------------------------------------------------------- 악보
@dataclass
class Score:
    pitches: list = field(default_factory=list)     # 각 음의 높이 (MIDI 번호)
    durations: list = field(default_factory=list)   # 각 음의 길이 (4분음표=1.0)

    @property
    def note_count(self) -> int:                    # 전체 음표의 수
        return len(self.pitches)

    @property
    def total_beats(self) -> float:
        return sum(self.durations)


def random_score(n: int = 8) -> Score:
    return Score(
        pitches=[random.choice(PITCH_POOL) for _ in range(n)],
        durations=[random.choice(DURATIONS[1:4]) for _ in range(n)],
    )


# ---------------------------------------------------------------- 변이 (한 번에 변수 하나만)
# 반환: (새 악보, 강조할 음 인덱스 또는 None, 변경 설명)
def mutate_count(s: Score):
    new = copy.deepcopy(s)
    add = (new.note_count <= MIN_NOTES) or (
        new.note_count < MAX_NOTES and random.random() < 0.5)
    if add:
        i = random.randint(0, new.note_count)
        new.pitches.insert(i, random.choice(PITCH_POOL))
        new.durations.insert(i, random.choice(DURATIONS))
        return new, i, f"음표 추가 ({s.note_count}개 → {new.note_count}개)"
    i = random.randrange(new.note_count)
    del new.pitches[i], new.durations[i]
    return new, None, f"음표 삭제 ({s.note_count}개 → {new.note_count}개)"


def mutate_duration(s: Score):
    new = copy.deepcopy(s)
    i = random.randrange(new.note_count)
    old = new.durations[i]
    new.durations[i] = random.choice([d for d in DURATIONS if d != old])
    return new, i, (f"{i + 1}번째 음 길이 변경 "
                    f"({DUR_NAME[old]} → {DUR_NAME[new.durations[i]]})")


def mutate_pitch(s: Score):
    new = copy.deepcopy(s)
    i = random.randrange(new.note_count)
    old = new.pitches[i]
    pos = PITCH_POOL.index(old)
    step = random.choice([-3, -2, -1, 1, 2, 3])
    idx = min(max(pos + step, 0), len(PITCH_POOL) - 1)
    if PITCH_POOL[idx] == old:                      # 경계에서 변화가 없으면 반대 방향
        idx = min(max(pos - step, 0), len(PITCH_POOL) - 1)
    new.pitches[i] = PITCH_POOL[idx]
    return new, i, (f"{i + 1}번째 음 높이 변경 "
                    f"({pitch_name(old)} → {pitch_name(new.pitches[i])})")


MUTATIONS = [("음표 수", mutate_count),
             ("음의 길이", mutate_duration),
             ("음의 높이", mutate_pitch)]


# ---------------------------------------------------------------- 오선 SVG
_LETTER = {0: (0, ""), 1: (0, "#"), 2: (1, ""), 3: (1, "#"), 4: (2, ""),
           5: (3, ""), 6: (3, "#"), 7: (4, ""), 8: (4, "#"), 9: (5, ""),
           10: (5, "#"), 11: (6, "")}
_ROW_H, _STEP, _LEFT, _DX = 135, 5, 64, 40


def staff_svg(score: Score, mark=None, per_row: int = 12):
    """높은음자리표 오선 위에 음표를 그린 SVG 문자열과 높이(px)를 반환."""
    n = score.note_count
    rows = max(1, math.ceil(n / per_row))
    width = _LEFT + per_row * _DX + 16
    height = rows * _ROW_H
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
         f'height="{height}" font-family="sans-serif">',
         '<rect width="100%" height="100%" fill="white"/>']

    for r in range(rows):
        yb = r * _ROW_H + 82                        # 맨 아래 줄(E4)의 y
        if mark is not None and r * per_row <= mark < (r + 1) * per_row:
            mx = _LEFT + (mark - r * per_row) * _DX
            o.append(f'<rect x="{mx + 2}" y="{r * _ROW_H + 2}" width="{_DX - 4}" '
                     f'height="{_ROW_H - 6}" rx="6" fill="#fff3bf"/>')
        for k in range(5):
            y = yb - k * 10
            o.append(f'<line x1="10" x2="{width - 6}" y1="{y}" y2="{y}" '
                     f'stroke="#222" stroke-width="1"/>')
        o.append(f'<line x1="10" x2="10" y1="{yb}" y2="{yb - 40}" stroke="#222"/>')
        o.append(f'<text x="16" y="{yb - 6}" font-size="54" fill="#222">\U0001D11E</text>')

        for j in range(per_row):
            i = r * per_row + j
            if i >= n:
                break
            p, d = score.pitches[i], score.durations[i]
            letter, acc = _LETTER[p % 12]
            step = letter + 7 * (p // 12 - 1)       # E4 = 30 (맨 아래 줄)
            x = _LEFT + j * _DX + _DX // 2
            y = yb - (step - 30) * _STEP
            col = "#d9381e" if i == mark else "#111"

            if step <= 28:                          # 아래 보조선
                ledgers = range(28, step - 1, -2)
            elif step >= 40:                        # 위 보조선
                ledgers = range(40, step + 1, 2)
            else:
                ledgers = []
            for s in ledgers:
                ly = yb - (s - 30) * _STEP
                o.append(f'<line x1="{x - 11}" x2="{x + 11}" y1="{ly}" y2="{ly}" '
                         f'stroke="#222"/>')
            if acc:
                o.append(f'<text x="{x - 19}" y="{y + 5}" font-size="14" fill="{col}">{acc}</text>')

            fill = col if d <= 1.0 else "white"
            o.append(f'<ellipse cx="{x}" cy="{y}" rx="6.5" ry="4.6" fill="{fill}" '
                     f'stroke="{col}" stroke-width="1.6" transform="rotate(-20 {x} {y})"/>')

            if d < 4.0:                             # 온음표는 줄기 없음
                up = step < 34
                sx = x + 6 if up else x - 6
                ye = y - 32 if up else y + 32
                o.append(f'<line x1="{sx}" x2="{sx}" y1="{y}" y2="{ye}" '
                         f'stroke="{col}" stroke-width="1.5"/>')
                flags = 2 if d == 0.25 else 1 if d == 0.5 else 0
                for f in range(flags):
                    if up:
                        fy = ye + 7 * f
                        o.append(f'<path d="M{sx} {fy} q10 4 8 16" fill="none" '
                                 f'stroke="{col}" stroke-width="1.6"/>')
                    else:
                        fy = ye - 7 * f
                        o.append(f'<path d="M{sx} {fy} q10 -4 8 -16" fill="none" '
                                 f'stroke="{col}" stroke-width="1.6"/>')

            o.append(f'<text x="{x}" y="{yb + 34}" font-size="10" text-anchor="middle" '
                     f'fill="#555">{pitch_name(p)}</text>')
            o.append(f'<text x="{x}" y="{yb + 46}" font-size="10" text-anchor="middle" '
                     f'fill="#888">{DUR_NAME[d]}</text>')
    o.append("</svg>")
    return "".join(o), height


# ---------------------------------------------------------------- 소리 / 파일 출력
def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def midi_bytes(pitches, durations, bpm: int = 100, ppq: int = 480) -> bytes:
    track = bytearray()
    track += b"\x00\xff\x51\x03" + struct.pack(">I", 60_000_000 // bpm)[1:]
    for p, d in zip(pitches, durations):
        track += b"\x00" + bytes([0x90, p, 90])
        track += _vlq(int(d * ppq)) + bytes([0x80, p, 0])
    track += b"\x00\xff\x2f\x00"
    return (b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq)
            + b"MTrk" + struct.pack(">I", len(track)) + bytes(track))


def wav_bytes(pitches, durations, bpm: int = 100, sr: int = 16000) -> bytes:
    """간단한 가산 합성으로 브라우저에서 바로 재생할 수 있는 WAV를 만든다."""
    spb = 60.0 / bpm
    buf = array("h")
    for p, d in zip(pitches, durations):
        n = max(1, int(d * spb * sr))
        w = 2 * math.pi * 440.0 * 2 ** ((p - 69) / 12) / sr
        for t in range(n):
            env = min(1.0, t / (0.01 * sr)) * math.exp(-2.0 * t / n)
            env *= min(1.0, (n - t) / 80)           # 끝부분 클릭 방지
            v = math.sin(w * t) + 0.3 * math.sin(2 * w * t) + 0.1 * math.sin(3 * w * t)
            buf.append(int(0.55 * env * v / 1.4 * 32767))
    bio = io.BytesIO()
    with wave.open(bio, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(buf.tobytes())
    return bio.getvalue()
