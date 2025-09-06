import streamlit as st
import game_play
import base64

st.set_page_config(page_title="About Time 🍂", layout="wide")

# ===== 배경 이미지 설정 =====
def get_base64_of_image(image_file):
    with open(image_file, "rb") as f:
        return base64.b64encode(f.read()).decode()

bg_file = "background_about_time.jpg"
bg_base64 = get_base64_of_image(bg_file)

st.markdown(f"""
<style>
/* 배경 */
html, body, .stApp, [data-testid="stAppViewContainer"], .main .block-container {{
  background: transparent !important;
}}
.stApp {{ position: relative; }}
.stApp::before {{
  content: "";
  position: fixed;
  inset: 0;
  background-image:
    linear-gradient(rgba(255,255,255,0.70), rgba(255,255,255,0.70)),
    url('data:image/jpeg;base64,{bg_base64}');
  background-repeat: no-repeat;
  background-position: center;
  background-size: cover;
  z-index: 0;
}}
.stApp > * {{ position: relative; z-index: 1; }}
[data-testid="stHeader"], [data-testid="stToolbar"] {{
  background: transparent !important;
}}
</style>
""", unsafe_allow_html=True)

# ===== 텍스트 & 버튼 스타일 =====
st.markdown("""
<style>
/* 본문 텍스트 */
[data-testid="stAppViewContainer"] *:not(svg) { color: #2b2b2b !important; }

/* 사이드바 텍스트 */
[data-testid="stSidebar"] *:not(svg) { color: #f5f5f5 !important; }

/* 버튼 */
.stButton > button {
  color: #ffffff !important;       /* 텍스트: 흰색 */
  background: #D2B48C !important;  /* 기본: 파스텔 갈색 (Tan) */
  border: none !important;
}
.stButton > button:hover, .stButton > button:focus {
  background: #8B4513 !important;  /* hover: 진한 갈색 (SaddleBrown) */
}
</style>
""", unsafe_allow_html=True)

# ===== 제목 폰트 =====
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

# ===== 체크포인트 강조 =====
st.markdown("""
<style>
.checkpoint-label {
    font-weight: 900 !important; /* 굵게 */
    color: #9B2222 !important;   /* 갈색 (원하면 유지) */
}
</style>
""", unsafe_allow_html=True)

# ===== Select Box 폰트 색깔 =====
st.markdown("""
<style>
/* selectbox 텍스트 색상 */
.stSelectbox div[data-baseweb="select"] * {
  color: #ffffff !important;   /* 흰색으로 변경 */
}
</style>
""", unsafe_allow_html=True)

"""흰색으로 바꿀 때
.stSelectbox div[data-baseweb="select"] * {
  color: #4B2E2E !important;   /* 진한 갈색 */
}
"""

# ===== 제목 =====
st.markdown("<div class='handwriting-title'>About Time 🍂</div>", unsafe_allow_html=True)

# ===== 랜딩 페이지 =====
if "started" not in st.session_state:
    st.session_state.started = False

if not st.session_state.started:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("게임 시작", use_container_width=True):
            st.session_state.started = True
            st.rerun()
else:
    game_play.run()