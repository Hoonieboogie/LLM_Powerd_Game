import streamlit as st
import game_play

st.set_page_config(page_title="About Time 🍂", layout="wide")

# 세션 상태 초기화
if "started" not in st.session_state:
    st.session_state.started = False

# CSS 스타일 (Google Fonts + custom)
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Shadows+Into+Light&display=swap" rel="stylesheet">
<style>
  .handwriting-title {
    font-family: 'Shadows Into Light', cursive !important;
    text-align: center;
    font-size: 60px;
    margin-top: 40px;
    color: #4B2E2E; /* 글자색도 바꿀 수 있음 */
  }
</style>
""", unsafe_allow_html=True)

# 게임 제목 (div 사용)
st.markdown("<div class='handwriting-title'>About Time 🍂</div>", unsafe_allow_html=True)

# 랜딩 페이지
if not st.session_state.started:
    if st.button("게임 시작"):
        st.session_state.started = True
        st.rerun()

# 게임 실행 화면
else:
    game_play.run()