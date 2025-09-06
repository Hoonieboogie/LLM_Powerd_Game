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
    color: #4B2E2E;
  }
</style>
""", unsafe_allow_html=True)

# 게임 제목
st.markdown("<div class='handwriting-title'>About Time 🍂</div>", unsafe_allow_html=True)

# 랜딩 페이지
if not st.session_state.started:
    # 3등분된 컬럼을 만들고 가운데에 버튼 배치
    col1, col2, col3 = st.columns([1, 2, 1])  # 가운데(col2)가 더 넓게
    with col2:
        st.write("")  # 약간의 위쪽 여백
        if st.button("게임 시작", use_container_width=True):
            st.session_state.started = True
            st.rerun()
else:
    game_play.run()