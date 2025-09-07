import streamlit as st
import os, re, json
import random
from openai import OpenAI
from dotenv import load_dotenv

# ====== 환경 세팅 ======
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")

client = OpenAI(api_key=OPENAI_API_KEY)

gpt_4_1_mini = 'gpt-4.1-mini'
gpt_4o_mini = 'gpt-4o-mini'
gpt_4o = 'gpt-4o'
gpt_5_nano = 'gpt-5-nano'

MODEL_NAME = os.getenv("OPENAI_MODEL", gpt_4o)

# ====== 세션 상태 초기화 ======
def _init_state():
    ss = st.session_state
    ss.setdefault("turn", 0)
    ss.setdefault("tickets", 3)
    ss.setdefault("mode", "select_cp")      # select_cp, past, present, gameover
    ss.setdefault("init_story", "")
    ss.setdefault("checkpoints", [])
    ss.setdefault("selected_cp", None)
    ss.setdefault("history", [])            
    ss.setdefault("present_outcome", "")
    ss.setdefault("notes", "")
    ss.setdefault("story_ready", False)
    ss.setdefault("cp_logs", {})            
    ss.setdefault("just_generated", False)  
    # 등장인물/역할
    ss.setdefault("char1", "")
    ss.setdefault("char2", "")
    ss.setdefault("victim", "")
    ss.setdefault("role", "")
    # 위험도 관리
    ss.setdefault("risk", 0)
    ss.setdefault("touched_cps", set())   
    ss.setdefault("improved_cps", set())  

# ====== 메인 실행 ======
def run():
    _init_state()

    with st.sidebar:
        st.metric("턴", f"{st.session_state.turn}/20")
        st.metric("티켓", f"{st.session_state.tickets}/3")
        st.write("모드:", st.session_state.mode)
        st.text_area("메모", key="notes", height=200, placeholder="(메모장)")

    if st.session_state.mode == "select_cp":
        _mode_select_cp()
    elif st.session_state.mode == "past":
        _mode_past()
    elif st.session_state.mode == "present":
        _mode_present()
    elif st.session_state.mode == "gameover":
        _mode_gameover()

# ====== 모드 구현 ======
def _mode_select_cp():
    if not st.session_state.checkpoints:
        with st.spinner("스토리를 생성 중..."):
            story = _generate_initial_story_stream()
            st.session_state.init_story = story
            st.session_state.checkpoints = _extract_checkpoints(story)
            st.session_state.cp_logs = {i: [] for i in range(len(st.session_state.checkpoints))}
            c1, c2, victim = _extract_cast_and_victim(story)
            st.session_state.char1, st.session_state.char2 = c1, c2
            st.session_state.victim = victim
            st.session_state.role = _other_of(c1, c2, victim)
            st.session_state.story_ready = True
            st.session_state.just_generated = True
        st.success("스토리 생성 완료!")

    if st.session_state.init_story and not st.session_state.just_generated:
        highlighted = _highlight_checkpoints(st.session_state.init_story)
        st.markdown(highlighted, unsafe_allow_html=True)

    if st.session_state.role and st.session_state.victim:
        st.info(
            f"주인공: **{st.session_state.char1}**, **{st.session_state.char2}**\n\n"
            f"당신의 역할은 **{st.session_state.role}**. 목표는 **{st.session_state.victim}** 의 비극을 막는 것입니다."
        )

    st.divider()
    st.subheader("타임슬립 시작")

    cp_list = st.session_state.checkpoints
    end_tag = re.compile(r'^\s*\[(?:엔딩|결말|체크포인트\s*5|CP5)(?::[^\]]*)?\]')

    if cp_list and end_tag.match(cp_list[-1]):
        options = list(range(1, len(cp_list)))  
    else:
        options = list(range(1, len(cp_list) + 1))  

    selected_num = st.selectbox(
        "돌아갈 체크포인트를 고르세요",
        options=options,
        index=0
    )

    can_time_slip = bool(st.session_state.role.strip())
    if st.button("⏳ 이 시점으로 타임슬립", disabled=not can_time_slip):
        st.session_state.selected_cp = selected_num - 1
        st.session_state.mode = "past"
        st.rerun()

    st.session_state.just_generated = False


def _mode_past():
    if st.session_state.selected_cp is None:
        st.warning("체크포인트를 먼저 선택하세요.")
        st.session_state.mode = "select_cp"
        st.rerun()
        return

    cp_idx = st.session_state.selected_cp
    cp_raw = st.session_state.checkpoints[cp_idx]
    cp_body = _strip_cp_tag(cp_raw)

    st.subheader(f"체크포인트 {cp_idx+1} — 과거 개입")
    st.markdown("**해당 시점의 사건**")
    st.write(cp_body)

    logs = st.session_state.cp_logs.get(cp_idx, [])
    if logs:
        st.markdown("**이 체크포인트의 대화 로그**")
        for t, ex in enumerate(logs, 1):
            st.markdown(f"- **턴 {t} — 당신({st.session_state.role}):** {ex['user']}")
            st.markdown(f"  > {ex['assistant']}")

    if st.session_state.turn >= 20:
        st.error("턴이 모두 소진되었습니다. 현재로 돌아가 결말을 확인하세요.")
        if st.button("현재로 돌아가기 🕰️"):
            st.session_state.mode = "present"
            st.rerun()
        return

    user_input = st.text_input(
        label="어떻게 바꾸시겠습니까?",
        key=f"turn_{st.session_state.turn}",
        placeholder=f"{st.session_state.role}의 대사/행동을 입력하세요.",
        label_visibility="collapsed"
    )

    if st.button("답변 제출"):
        if not user_input.strip():
            st.warning("먼저 답변을 입력해주세요!")
        else:
            st.session_state.turn += 1
            with st.spinner("스토리 생성 중..."):
                messages = _build_cp_messages(cp_idx, cp_body, user_input)
                visible_text = _generate_event_stream_and_update_risk(messages, cp_idx)

            st.session_state.cp_logs[cp_idx].append({"user": user_input, "assistant": visible_text})
            st.session_state.history.append((cp_idx, user_input, visible_text))

            # 새 개입 반영 후 결말 캐시 무효화 (다음에 현재로 돌아가면 새 엔딩 생성)
            st.session_state.present_outcome = ""

            st.success("턴 진행 완료!")
            st.rerun()

    st.divider()
    if st.button("현재로 돌아가기 🕰️"):
        st.session_state.mode = "present"
        st.rerun()


def _mode_present():
    st.subheader("현재 결말 확인")

    # 티켓 직후에는 결말을 다시 생성하지 않음
    if not st.session_state.present_outcome:
        with st.spinner("결말 생성 중..."):
            outcome = _generate_outcome_nonstream()
            st.session_state.present_outcome = outcome
    else:
        outcome = st.session_state.present_outcome

    # 태그 제거 후 본문 출력
    st.write(_strip_ending_tag(outcome))

    # 성공 / 실패 판정
    if _is_success(outcome):
        st.success("승리 엔딩 🎉 비극을 막아냈습니다!")
        if st.button("게임 종료로 이동"):
            st.session_state.mode = "gameover"
            st.rerun()
    else:
        st.error("아직 비극입니다...")

        # 플레이어는 결말을 반드시 확인한 뒤 티켓 선택 가능
        if st.session_state.tickets > 0 and st.session_state.turn < 20:
            st.info(f"남은 티켓: {st.session_state.tickets}장")
            if st.button("🎟️ 티켓 사용하기 (체크포인트로 돌아가기)"):
                # 스피너 없이 곧바로 선택 화면으로 이동
                st.session_state.tickets -= 1
                st.session_state.present_outcome = ""  # 결말 캐시 초기화
                st.session_state.mode = "select_cp"
                st.rerun()
        else:
            # 티켓 없음 → 게임 종료 버튼만 제공
            if st.button("게임 종료로 이동"):
                st.session_state.mode = "gameover"
                st.rerun()


def _mode_gameover():
    st.subheader("게임 종료")

    # 마지막 결말 출력
    st.markdown("### 최종 결말")
    st.write(_strip_ending_tag(st.session_state.present_outcome))

    # 성공/실패 여부 안내
    if _is_success(st.session_state.present_outcome):
        st.success("승리 엔딩 🎉 비극을 막아냈습니다!")
    else:
        st.error("패배 엔딩 😢 비극을 막지 못했습니다.")

    st.write("---")
    st.write("다시 시작하려면 페이지 새로고침(F5)을 눌러주세요.")

# ====== LLM 유틸 ======
def _strip_cp_tag(text: str) -> str:
    return re.sub(
        r'^\s*\[(?:체크포인트\s*[1-5]|CP[1-5]|엔딩|결말)(?::[^\]]*)?\]\s*',
        '',
        text.strip()
    )

def _extract_checkpoints(text: str):
    pattern = r'\s*(?=\[(?:체크포인트\s*[1-5]|CP[1-5]|엔딩|결말)(?::[^\]]*)?\])'
    blocks = re.split(pattern, text)
    chunks = [b.strip() for b in blocks if b.strip()]
    if len(chunks) >= 5:
        return chunks[:5]
    paras = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    return paras[:5]


def _highlight_checkpoints(text: str) -> str:
    pattern = r'\[(?:체크포인트\s*[1-5]|CP[1-5]|엔딩|결말)(?::[^\]]*)?\]'
    return re.sub(
        pattern,
        lambda m: f"<span class='checkpoint-label'>{m.group(0)}</span>",
        text
    )

def _generate_initial_story_stream():
    system_query = """ 
    너는 최고의 시나리오 작가다. 
    아래 규칙을 모두 지켜 ‘대한민국’을 배경으로 한 자연스럽고 개연성 있는 **연인의 죽음** 서사를 정확히 5문단으로 작성하라.
    다시 한 번 기억하라. 너는 최고의 시나리오 작가다. 다양한 소재로 스토리를 만들어라.

    [형식]
    - 각 문단은 반드시 다음 머리표로 시작한다: [체크포인트 1: 소제목 1] … [체크포인트 4: 소제목 4], [엔딩: 소제목 5]
    - 소제목은 문단의 핵심 사건을 요약한 짧고 자연스러운 한국어 표현으로 작성한다.
    - 머리표 다음 줄에서 바로 본문을 시작하며, 본문은 줄바꿈 이후에만 작성한다.
    - 정확히 5문단만 출력한다. 제목/서론/요약/맺음말/추가 문구/메타 발언은 금지한다(머리표 제외).

    [등장인물]
    - 오직 두 인물만 등장한다. 이름은 2글자의 한글 이름으로만 표기한다(예: 민우, 지연 등).
    - 성(姓)/영문/별칭/이모지/괄호 설명은 금지한다.
    - 첫 문단 첫 문장에 반드시 두 인물의 이름을 모두 명시한다.
    - 제3의 ‘사람’(경찰/의사/친구/가해자/목격자 등)이 고유명사나 대사/능동적 결정으로 등장하는 것은 금지한다.
    (비·도로·신호·차량 등 ‘배경/사물/환경’은 묘사 가능하되, 특정 인물을 행위 주체로 만들지 마라.)

    [내용 구조]
    - 이 이야기는 **연인 관계의 두 사람**이 주인공이다.
    - [체크포인트 1]~[체크포인트 4]:
    - 각 문단은 **구체적이고 현실적인 사건 하나만** 다룬다.
    - 각 사건은 반드시 두 인물의 상호작용(대화나 행동)을 포함해야 하며, 만약 한 캐릭터가 과거로 시간 이동을 한다면 해당 사건에 개입할 수 있게 사건이 전개되어야 한다.
    - 즉, 한쪽 인물의 단독 행동(혼자 사고, 혼자 병에 걸림 등)으로만 사건이 전개되는 것은 금지한다.
    - 사건은 훗날 [엔딩]의 비극에 **직접 작용하는 원인(플래그)**이 되어야 하며, 점층적으로 위험이 커지는 연쇄가 되어야 한다.
    - [엔딩]: 두 사람 중 한 명이 최종적으로 **죽음** 혹은 **돌이킬 수 없는 상실**을 맞이한다.
        - [엔딩]에서의 비극은 앞선 4개의 사건 중 **최소 2개 이상의 플래그가 겹쳐** 필연적으로 발생한 결과임을 자연스럽게 드러내야 한다.
    - “갑자기/우연히/운명처럼” 식의 돌발 전개 금지. **사건 단서 -> 선택/행동 -> 결과**의 인과를 명확히 보여라.
    - 마지막 문장의 끝에서 반드시 피해자의 이름을 직접 명시한다. (예: “… 결국 민우는 숨을 거둔다.”)

    [문체/언어]
    - 성인이 쉽게 이해할 수 있는 **직관적인 한국어**로 쓴다. 영문 철자 금지(외래어는 한글 표기).
    - 추상적·과장된 표현 금지: “비극의 기로”, “운명의 굴레”, “영혼 깊숙이” 등.
    - 등장인물의 대사는 반드시 **일상적이고 현실적인 한국어 대화**여야 한다.
    - 각 문단은 3~5문장으로 간결하게 쓴다.

    명심해라. 전체 스토리 설정과 전개는 모두 타당하고 자연스러워야 해. 너가 최고의 작가라는 것을 잊지마.
    """

    user_query = (
        "위 규칙을 정확히 지켜 정확히 5문단의 이야기를 작성하라. "
        "[체크포인트 1: …]~[체크포인트 4: …], [엔딩: …] 형식을 반드시 지키고, "
        "각 문단은 하나의 구체적 사건만 다루며 두 인물이 모두 관여할 수 있도록 하라. "
        "각 문단이 자연스럽게 연결되어 엔딩의 비극으로 이어지게 만들어라."
    )

    messages = [
        {"role": "system", "content": system_query},
        {"role": "user", "content": user_query},
    ]
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        stream=True,
    )
    placeholder = st.empty()
    story_text = ""
    for chunk in response:
        delta = chunk.choices[0].delta.content or ""
        story_text += delta
        highlighted = _highlight_checkpoints(story_text)
        placeholder.markdown(highlighted, unsafe_allow_html=True)

    st.session_state.init_story = story_text
    st.session_state.init_story_html = _highlight_checkpoints(story_text)
    return story_text

def _stream_once_and_return(response_iter):
    placeholder = st.empty()
    acc = ""
    for ch in response_iter:
        delta = ch.choices[0].delta.content or ""
        acc += delta
        placeholder.markdown(acc)
    return placeholder, acc

def _strip_status(text: str):
    """
    출력 끝에 붙은 STATUS 태그를 파싱해 위험도(delta)를 계산하고,
    플레이어에게 보이는 텍스트에서는 태그(및 감싼 따옴표/공백/문장부호)를 제거한다.
    - 허용 예: <STATUS: risk_up1>, "<STATUS: risk_down2>", …<STATUS: neutral>
    """
    s = text.rstrip()
    # 끝부분에 달린 태그(따옴표 포함 가능)를 탐지
    tag_end_re = re.compile(
        r"""["“”']?\s*<STATUS:\s*(?:(risk_up|risk_down)\s*([+-]?\d+)?|neutral)\s*>\s*["“”']?\s*$""",
        re.IGNORECASE,
    )
    m = tag_end_re.search(s)
    delta = 0
    if m:
        kind = (m.group(1) or "").lower()
        num  = m.group(2)
        if kind == "risk_up":
            delta = int(num or 1)
        elif kind == "risk_down":
            delta = -int(num or 1)
        # 과한 숫자 방지
        delta = max(-2, min(2, delta))
        visible = tag_end_re.sub("", s).rstrip()
    else:
        # 본문 어딘가에 섞여 있으면(규칙 위반 대비) 제거만 시도
        visible = re.sub(r'["“”\']?\s*<STATUS:[^>]+>\s*["“”\']?', "", s, flags=re.I).rstrip()
    return visible, delta


def _normalize_markdown(text: str) -> str:
    """모델 답변 전체를 인용문 블록(> …)으로 강제 변환"""
    lines = text.strip().split("\n")
    normalized = []
    for line in lines:
        if line.strip():
            # 이미 '>'로 시작하면 그대로 두고, 아니면 붙이기
            normalized.append("> " + line if not line.lstrip().startswith(">") else line)
        else:
            normalized.append("")  # 빈 줄 유지
    return "\n".join(normalized)


def _generate_event_stream_and_update_risk(messages, cp_idx: int) -> str:
    """이벤트를 스트리밍 출력 → 태그 파싱해 risk 갱신 + 개입/개선 집계 → 화면을 태그 제거본으로 덮어쓰기"""
    resp_iter = client.chat.completions.create(
        model=MODEL_NAME,
        stream=True,
        messages=messages,
    )
    placeholder, full_text = _stream_once_and_return(resp_iter)
    visible, delta = _strip_status(full_text)

    # 누적 위험도 갱신
    st.session_state.risk += delta

    # 개입/개선 집계
    st.session_state.touched_cps.add(cp_idx)
    if delta < 0:
        st.session_state.improved_cps.add(cp_idx)

    # 태그 제거본을 인용문 블록으로 통일해서 덮어쓰기
    placeholder.markdown(
    f"<div class='assistant-reply'>{visible}</div>",
    unsafe_allow_html=True
    )
    return visible

def _build_cp_messages(cp_idx: int, cp_body: str, user_input: str):
    role   = st.session_state.role.strip() or "플레이어"
    victim = st.session_state.victim.strip() or "피해자"
    c1     = st.session_state.char1 or role
    c2     = st.session_state.char2 or victim
    partner = c2 if role == c1 else c1

    cp_turn    = len(st.session_state.cp_logs.get(cp_idx, []))
    total_turn = int(st.session_state.turn)
    risk_now   = int(st.session_state.risk)

    rnd = random.Random(f"{total_turn}-{cp_idx}-{risk_now}")
    r = rnd.random()

    # 톤 프로파일 선택
    if cp_turn == 0:
        tone_profile = "negative_anchor" if r < 0.6 else ("subtle_mixed" if r < 0.8 else "positive_feint")
    else:
        if r < 0.4:
            tone_profile = "positive_feint"
        elif r < 0.7:
            tone_profile = "subtle_mixed"
        else:
            tone_profile = "negative_anchor"

    # 사람이 읽을 톤 이름
    tone_kind = {
        "negative_anchor": "부정적",
        "positive_feint":  "긍정적",
        "subtle_mixed":    "미묘"
    }.get(tone_profile, "미묘")

    # 공통 규칙
    base_rules = (
        f"등장인물은 '{c1}'와 '{c2}' 두 명뿐이다. "
        f"플레이어는 '{role}', 상대 인물은 '{partner}', 피해자는 '{victim}'이다. "
        "아래 '플레이어 발화'는 글자 하나도 바꾸지 말고 **첫 문장으로 그대로** 넣어라. "
        "따옴표/어미/조사/구두점/순서를 수정하거나 요약/확장/의역해서는 안 된다. "
        f"이번 턴의 **장면 톤은 '{tone_kind}'** 이다. 이 톤은 **오직 상대 인물('{partner}')의 반응과 사건 서술**에만 적용한다. "
        f"플레이어('{role}')의 첫 문장은 톤 적용 대상이 아니다. "
        "상대 인물의 반응과 사건 서술은 **플레이어 발화의 직접적 결과**로 이어져야 하며, 인과 개연성을 절대로 훼손하지 마라. "
        "예: 조언을 따른 경우 상대가 불만을 표현할 수는 있으나, '무시했다'와 같이 모순되는 반응은 금지. "
        "한 문단(3~5문장)으로 작성하되, 이번 장면에서는 누구도 죽거나 완전히 구원받지 않는다(최종 결말 금지). "
        "사건을 즉시 종결하지 말고 이후 개입 여지를 남겨라. "
        "제3의 사람(친구/가족/경찰/의사/동료/목격자 등) 및 외부 기관/연락은 등장 금지. "
        "배경 사물/환경은 묘사 가능하되 의사결정을 하지 않는다. "
        "메타 표현/설명은 금지한다."
    )

    # 마커 출력 금지 규칙
    marker_rule = (
        "아래 마커 '<<<'와 '>>>'는 **입력 경계 표시용**이다. "
        "**출력 텍스트에는 절대 포함하지 마라.** "
        "첫 문장은 마커를 제거하고 **플레이어 발화 내용만** 그대로 넣어라."
    )

    # 톤별 규칙
    if tone_profile == "negative_anchor":
        tone_rules = (
            f"상대 인물('{partner}')의 반응과 서술은 **부정적 정서**(의심/냉담/회피/짜증 등)를 담되, "
            "플레이어 발화 내용과 모순되지 않게 **합리적 맥락**을 유지하라. "
            "STATUS 태그는 '<STATUS: risk_up1>' 또는 '<STATUS: neutral>' 중 하나만 사용한다."
        )
    elif tone_profile == "positive_feint":
        tone_rules = (
            f"상대 인물('{partner}')의 반응과 서술은 **긍정적 정서**(따뜻함/안도/작은 화해/격려)를 드러내되, "
            "근본 문제 해결 확정은 피하고 작은 숙제를 남겨라. "
            "STATUS 태그는 반드시 '<STATUS: risk_down1>'만 사용한다."
        )
    else:  # subtle_mixed
        tone_rules = (
            f"상대 인물('{partner}')의 반응과 서술은 대체로 평온하되, **미묘한 이상 신호 1개만** 심어라 "
            "(시선 회피, 말끝 흐리기 등). 급격한 정서 전환은 금지. "
            "STATUS 태그는 반드시 '<STATUS: neutral>'만 사용한다."
        )

    status_tail = (
        "문단의 '마지막 줄 끝'에 태그를 **따옴표 없이 단독으로** 정확히 1개 붙여라. "
        "허용 형식: <STATUS: risk_upN>, <STATUS: risk_downN>, <STATUS: neutral>. "
        "N 생략 시 1, N의 절대값 최대 2. "
        "태그 앞뒤에는 마침표/쉼표/따옴표/괄호 등 문장부호를 두지 마라."
    )

    rules = base_rules + " " + marker_rule + " " + tone_rules + " " + status_tail

    msgs = [{"role": "system", "content": rules}]
    msgs.append({"role": "user", "content": f"원래 사건:\n{cp_body}"})
    for ex in st.session_state.cp_logs.get(cp_idx, []):
        msgs.append({"role": "user", "content": f"{role}의 이전 개입: {ex['user']}"})
        msgs.append({"role": "assistant", "content": ex["assistant"]})
    msgs.append({
        "role": "user",
        "content": (
            "플레이어 발화(첫 문장에 그대로 삽입, 변경 금지):\n"
            f"<<<\n{user_input}\n>>>\n\n"
            "위 규칙에 따라 1문단(3~5문장)으로 작성하라."
        )
    })
    return msgs

def _history_text_for_outcome() -> str:
    """각 체크포인트 원래 사건 + 플레이어 개입 전체 기록을 요약"""
    lines = []
    for cp_idx, exchanges in st.session_state.cp_logs.items():
        cp_raw = st.session_state.checkpoints[cp_idx]
        cp_body = _strip_cp_tag(cp_raw)

        lines.append(f"[체크포인트 {cp_idx+1}] 원래 사건: {cp_body}")
        for ex in exchanges:
            lines.append(f"  - 개입: {ex['user']}")
            lines.append(f"    결과: {ex['assistant']}")
    return "\n".join(lines) if lines else "아직 개입 기록이 없습니다."


def _generate_outcome_nonstream() -> str:
    summary = _history_text_for_outcome()
    role = st.session_state.role or "플레이어"
    victim = st.session_state.victim or "피해자"
    c1 = st.session_state.char1 or role
    c2 = st.session_state.char2 or victim

    # 현재 누적 상태
    risk = int(st.session_state.risk)
    touched = st.session_state.get("touched_cps", set())
    improved = st.session_state.get("improved_cps", set())
    touched_cnt  = len(touched)
    improved_cnt = len(improved)

    # 성공/실패 기준
    is_success = (risk <= -2 and touched_cnt >= 2 and improved_cnt >= 2)

    # 실패 모드 분기(원인 유지 vs 나비효과)
    worsened_cnt = max(0, touched_cnt - improved_cnt)  # 악화로 볼 수 있는 개입 수 추정
    if not is_success:
        if improved_cnt == 0 or worsened_cnt > 0:
            failure_mode = "same"        # 원래 원인이 그대로 남아 같은 형태의 비극
        else:
            failure_mode = "butterfly"   # 일부 완화는 되었으나 다른 조합으로 비극(새 형태)

    only_two_rule = (
        f"결말에서도 등장인물은 오직 '{c1}'와 '{c2}' 두 사람만 등장한다. "
        "제3자(친구/가족/경찰/의사/목격자/군중/기관)의 고유명사/대사/능동적 결정은 금지한다. "
        "배경 사물/환경은 묘사 가능하되 인격을 부여하지 마라. "
    )

    if is_success:
        outcome_rules = (
            "너는 이야기 결말을 쓰는 작가다. " +
            only_two_rule +
            "주어진 원래 이야기와 플레이어의 개입 기록을 바탕으로, "
            f"'{victim}'의 비극이 **완전히 막아진 해피엔딩**을 작성하라. "
            "플레이어의 개입 덕분에 문제가 근본적으로 해결되었음을 **구체적 사건**으로 보여주라. "
            "가능하면 어떤 체크포인트의 위험이 어떻게 상쇄/해결되었는지 1~2문장으로 자연스럽게 드러내라. "
            "두 사람의 관계가 회복되고, 서로 신뢰하며 미래가 안정적이라는 점을 분명히 하라. "
            "불안, 단서, 갈등, 여운은 절대로 남기지 마라. "
            "마지막에 반드시 '<ENDING: success>'를 붙여라."
        )
    else:
        if failure_mode == "same":
            failure_hint = (
                "이번 실패는 **원래 비극의 원인 조합이 그대로 유지**되어 발생한다. "
                "원래 이야기의 [체크포인트]들 중 **최소 2개**의 위험 플래그가 **그대로 겹쳐** 비극이 일어났음을 "
                "1~2문장으로 **명확히 드러내라**(예: \"[체크포인트 2]의 늦은 연락과 [체크포인트 4]의 무리한 운전이 다시 겹쳤다\"). "
                "가능하면 원래 엔딩과 **동일한 유형의 비극**으로 귀결되게 하라."
            )
        else:  # butterfly
            failure_hint = (
                "이번 실패는 **나비효과**로 인해 **원래와 다른 형태의 비극**이 발생한다. "
                "플레이어의 개입으로 완화/변경된 위험(예: 한 체크포인트의 문제)은 있었으나, "
                "그로 인해 **다른 플래그 조합이나 새로운 변수**가 겹쳐 **다른 유형의 상실/사고**로 이어졌음을 "
                "1~2문장으로 **명확히 드러내라**(예: \"[체크포인트 1]의 일정은 조정했지만, 그 탓에 [체크포인트 3]의 약속이 엇갈렸다\"). "
                "원래 엔딩과 **유형이 겹치지 않도록** 유의하라."
            )

        outcome_rules = (
            "너는 이야기 결말을 쓰는 작가다. " +
            only_two_rule +
            "주어진 원래 이야기와 플레이어의 개입 기록을 바탕으로, "
            f"'{victim}'의 비극이 **결국 피할 수 없는 실패 결말**로 이어지도록 작성하라. "
            + failure_hint + " "
            "겉보기에는 잠시 좋아 보일 수 있으나, 근본 문제가 해결되지 않아 "
            f"'{victim}'이(가) 상실 또는 죽음에 도달해야 한다. "
            "사건의 인과관계를 통해 비극이 불가피함을 보여라. "
            "마지막에 반드시 '<ENDING: failure>'를 붙여라."
        )

    full_story = st.session_state.init_story

    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": outcome_rules},
            {"role": "user", "content": (
                f"원래 이야기:\n{full_story}\n\n"
                f"플레이어 개입 요약:\n{summary}\n\n"
                f"목표: '{victim}'의 비극을 막는 것이다."
            )},
        ],
    )
    return resp.choices[0].message.content.strip()

def _is_success(outcome: str) -> bool:
    m = re.search(r"<ENDING:\s*(success|failure)\s*>", outcome, re.I)
    return bool(m and m.group(1).lower() == "success")

def _strip_ending_tag(text: str) -> str:
    return re.sub(
        r"""["“”']?\s*<ENDING:\s*(?:success|failure)\s*>\s*["“”']?\s*$""",
        "",
        text.strip(),
        flags=re.IGNORECASE
    )

# ====== 이름 추출 ======
def _clean_korean_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    n = name.strip()
    # 앞뒤 불필요한 기호 제거
    n = re.sub(r'^[\"\'\(\)\[\]\{\}\,\.\?\!~…·\-:;]+', '', n)
    n = re.sub(r'[\"\'\(\)\[\]\{\}\,\.\?\!~…·\-:;]+$', '', n)

    # 조사 제거: 단, 조사 제거 후 이름이 2글자 미만으로 줄어들면 그대로 둠
    tmp = re.sub(r'(은|는|이|가|을|를|과|와|랑|도|만)$', '', n)
    if len(tmp) >= 2:
        n = tmp

    # 최종적으로 2~3글자 한글만 허용
    m = re.match(r'^[가-힣]{2,3}$', n)
    return m.group(0) if m else n

def _extract_cast_and_victim(story_text: str):
    try:
        sys = "너는 한국어 이야기에서 등장인물 이름을 추출하는 도우미다. 반드시 JSON만 출력하라."
        usr = (
            "아래 이야기에서 중심이 되는 두 인물의 '이름'을 정확히 추출하고, "
            "마지막 문단 기준으로 비극을 맞이하는 인물을 판단하여 반환하라. "
            'JSON: { "characters": ["이름1","이름2"], "victim": "이름중하나" }\n\n'
            f"{story_text}"
        )
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": usr},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        # 혹시 코드펜스(````json````)로 출력되면 제거
        raw = raw.strip("```").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
        data = json.loads(raw)

        # 이름 정제
        chars = [_clean_korean_name(x) for x in data.get("characters", []) if isinstance(x, str)]
        victim = _clean_korean_name(data.get("victim", ""))

        # 유효성 체크
        chars = [c for c in chars if re.match(r'^[가-힣]{2,3}$', c)]
        if len(chars) == 2 and victim in chars:
            return chars[0], chars[1], victim
    except Exception:
        pass

    # ===== fallback: 정규식 기반 이름 추출 =====
    candidates = re.findall(r'([가-힣]{2,3})(?=[은는이가을를과와랑도만은]*)', _strip_cp_tag(story_text))

    clean_candidates = [_clean_korean_name(c) for c in candidates if c]

    # 등장 빈도 계산 후 상위 2명
    freq = {}
    for c in clean_candidates:
        if not c:
            continue
        freq[c] = freq.get(c, 0) + 1
    top2 = sorted(freq, key=freq.get, reverse=True)[:2]
    if len(top2) < 2:
        top2 = ["인물A", "인물B"] if not top2 else [top2[0], "인물B"]

    # 마지막 문단에서 더 자주 등장한 이름을 victim으로 추정
    last_para = st.session_state.checkpoints[-1] if st.session_state.checkpoints else story_text.split("\n\n")[-1]
    victim_guess = top2[0] if last_para.count(top2[0]) >= last_para.count(top2[1]) else top2[1]
    return top2[0], top2[1], victim_guess


def _other_of(c1: str, c2: str, victim: str) -> str:
    """victim이 아닌 다른 쪽을 반환"""
    return c2 if victim == c1 else c1