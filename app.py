"""
악보 진화기 - Streamlit 웹 앱
실행:  streamlit run app.py
"""
import streamlit as st
import streamlit.components.v1 as components

from score_core import (MUTATIONS, midi_bytes, random_score, staff_svg,
                        wav_bytes)

st.set_page_config(page_title="악보 진화기", page_icon="🎼", layout="wide")


# ---------------------------------------------------------------- 상태 관리
def new_candidates():
    """현재 기본 악보에서 변수 하나씩만 바꾼 후보 3개를 만든다."""
    st.session_state.candidates = [fn(st.session_state.base) for _, fn in MUTATIONS]


def reset():
    base = random_score()
    st.session_state.base = base
    st.session_state.history = [{"score": base, "desc": "시작 악보"}]
    new_candidates()


def choose(k: int):
    """후보 k를 새 기본 악보로 확정하고 다음 라운드 후보를 만든다."""
    score, _, desc = st.session_state.candidates[k]
    st.session_state.base = score
    st.session_state.history.append(
        {"score": score, "desc": f"{MUTATIONS[k][0]} · {desc}"})
    new_candidates()


def undo():
    st.session_state.history.pop()
    st.session_state.base = st.session_state.history[-1]["score"]
    new_candidates()


if "base" not in st.session_state:
    reset()


# ---------------------------------------------------------------- 보조 함수
@st.cache_data(show_spinner=False)
def cached_wav(pitches: tuple, durations: tuple, bpm: int) -> bytes:
    return wav_bytes(pitches, durations, bpm)


def show_score(score, mark=None):
    svg, height = staff_svg(score, mark)
    components.html(svg, height=height + 6)


def show_audio(score, bpm, key):
    st.audio(cached_wav(tuple(score.pitches), tuple(score.durations), bpm),
             format="audio/wav")
    st.download_button("MIDI 다운로드",
                       data=midi_bytes(score.pitches, score.durations, bpm),
                       file_name=f"{key}.mid", mime="audio/midi", key=f"dl_{key}")


# ---------------------------------------------------------------- 사이드바
with st.sidebar:
    st.header("설정")
    bpm = st.slider("템포 (BPM)", 60, 180, 100, step=5)
    st.button("🎲 새 악보로 시작", on_click=reset)
    st.button("↩ 이전 라운드로 되돌리기", on_click=undo,
              disabled=len(st.session_state.history) <= 1)
    with st.expander("진행 기록", expanded=False):
        for r, h in reversed(list(enumerate(st.session_state.history))):
            st.write(f"**라운드 {r}** — {h['desc']}")

# ---------------------------------------------------------------- 본문
st.title("🎼 악보 진화기")
st.caption("후보 악보는 기본 악보에서 변수 하나(음표 수 / 음의 길이 / 음의 높이)만 "
           "바뀐 것입니다. 마음에 드는 후보를 고르면 그 악보가 새 기본 악보가 됩니다.")

round_no = len(st.session_state.history) - 1
base = st.session_state.base

st.subheader(f"기본 악보 (라운드 {round_no})")
with st.container(border=True):
    left, right = st.columns([3, 1])
    with left:
        st.write(f"음표 {base.note_count}개 · 총 {base.total_beats:g}박")
        show_score(base)
    with right:
        show_audio(base, bpm, f"round_{round_no:02d}")

head, btn = st.columns([4, 1])
head.subheader("후보 악보 — 하나를 선택하세요")
btn.button("🔄 후보 다시 만들기", on_click=new_candidates)

for k, (label, _) in enumerate(MUTATIONS):
    cand, mark, desc = st.session_state.candidates[k]
    with st.container(border=True):
        left, right = st.columns([3, 1])
        with left:
            st.markdown(f"**후보 {k + 1} · 변경 변수: {label}**  \n{desc} "
                        f"(음표 {cand.note_count}개 · 총 {cand.total_beats:g}박)")
            show_score(cand, mark)
        with right:
            show_audio(cand, bpm, f"round_{round_no:02d}_cand{k + 1}")
            st.button("✅ 이 악보 선택", key=f"choose_{round_no}_{k}",
                      on_click=choose, args=(k,))
