# app.py
# Streamlit: <피로사회> 수업용 웹앱 (단순 버전)
# 흐름: 시작(학생 이름) -> 질문 리스트 -> 질문 풀이(카드 확인 + 답변 작성) -> 제출/자가채점 -> 리스트 복귀
#
# 실행: streamlit run app.py

import streamlit as st
from dataclasses import dataclass
from typing import List, Dict, Optional, Any


# ---------------------------
# 0) 질문/카드 (사용자 제공 내용 반영)
# ---------------------------
@dataclass
class Question:
    qid: str
    title: str
    prompt: str
    cards: List[str]


Q1_CARD1 = """ **다음 사례를 답변에 포함하시오**

전 세계적으로 고카페인 음료 섭취가 늘어나면서 국가마다 대책을 마련하는 상황입니다. 우리나라 역시 청소년의 고카페인 음료 섭취가 증가하고 있으며, 고카페인 음료는 100 mL당 카페인 15 mg 이상을 포함한 음료를 의미합니다. 질병관리청 조사에 따르면 중고등학생의 고카페인 음료 주 3회 이상 섭취율은 2015년 3.3%에서 2017년 8.0%, 2019년에는 12.2%로 꾸준히 증가했습니다. 2020년 조사에서는 청소년 중 약 30%가 하루 3병 이상의 고카페인 음료를 섭취한 경험이 있다고 응답했습니다. (질병관리청)
"""

Q1_CARD2 = """‘도핑사회’ 이외에 저자가 언급한 사회의 종류를 포함하여 답변하시오"""

Q2_CARD1 = """**다음 정보를 답변할 때 참고하시오**

오순절은 이스라엘의 명절이다. 예수 그리스도께서 부활하신지 오십일 째 되는 날이 오순절이었는데 이 날, 예수님께서 약속하신 성령이 내려왔다. 사람들이 특별한 영감을 받은 것이다. 또한 이 날 교회가 탄생했다.
"""

Q2_CARD2 = """‘오순절’과 저자가 지향하는 피로사회’가 공통적으로 가진 특징에 착안하여 서술하시오"""

Q2_CARD3 = """‘오순절’ 개념을 설명에 포함함으로서 저자가 얻을 수 있는 효과를 마지막에 포함하시오"""


QUESTIONS: List[Question] = [
    Question(
        qid="q1",
        title="질문 1",
        prompt="<피로사회> 장 서두에 ‘도핑사회’를 언급한 이유를 카드에 나온 조건을 모두 사용해서 답하시오",
        cards=[Q1_CARD1, Q1_CARD2],
    ),
    Question(
        qid="q2",
        title="질문 2",
        prompt="저자가 피로사회를 설명하면서 ‘오순절’을 언급한 이유를 카드에 나온 조건을 모두 사용해서 답하시오",
        cards=[Q2_CARD1, Q2_CARD2, Q2_CARD3],
    ),
]


# ---------------------------
# 1) 페이지 라우팅 (session_state)
# ---------------------------
PAGES = ("start", "list", "solve", "review")


def init_state() -> None:
    if "page" not in st.session_state:
        st.session_state.page = "start"
    if "student" not in st.session_state:
        st.session_state.student = ""
    if "active_qid" not in st.session_state:
        st.session_state.active_qid = None
    if "answers" not in st.session_state:
        # answers[qid] = {"text": "...", "rating": int|None}
        st.session_state.answers: Dict[str, Dict[str, Any]] = {}
    if "draft" not in st.session_state:
        st.session_state.draft = ""


def go(page: str, qid: Optional[str] = None) -> None:
    if page not in PAGES:
        return
    st.session_state.page = page
    if qid is not None:
        st.session_state.active_qid = qid
    st.rerun()


def get_question(qid: str) -> Question:
    for q in QUESTIONS:
        if q.qid == qid:
            return q
    return QUESTIONS[0]




def frame_open():
    st.markdown('<div class="frame">', unsafe_allow_html=True)


def frame_close():
    st.markdown("</div>", unsafe_allow_html=True)


def render_top_label(label: str):
    st.caption(label)


# ---------------------------
# 3) 페이지 렌더링
# ---------------------------
def render_start_page():
   

    # 시작화면 타이틀(요청: 크게)
    st.markdown("# **피로사회 마무리 퀴즈**\n")
    

    st.text_input("학생 이름", key="student", placeholder="예: 2학년 3반 홍길동")

    if st.button("시작하기"):
        if not st.session_state.student.strip():
            st.warning("학생 이름을 입력해 주세요.")
        else:
            go("list")

    st.markdown("</div>", unsafe_allow_html=True)
  


def render_list_page():
    

    st.markdown(f"**학생:** {st.session_state.student.strip()}")
    st.markdown("<hr class='hr'/>", unsafe_allow_html=True)

    for q in QUESTIONS:
        saved = st.session_state.answers.get(q.qid, {})
        has_text = bool((saved.get("text") or "").strip())
        has_rating = saved.get("rating") is not None

        left, right = st.columns([3, 2], vertical_alignment="center")
        with left:
            st.markdown(f"**{q.title}**")
            st.markdown(f"<div class='subtle' style='text-align:left'>{q.prompt}</div>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='subtle' style='text-align:left'>상태: {'답변 ✅' if has_text else '답변 ⬜'} · {'별점 ✅' if has_rating else '별점 ⬜'}</div>",
                unsafe_allow_html=True,
            )

        with right:
            st.markdown('<div class="small-btn">', unsafe_allow_html=True)
            if st.button("답변하기", key=f"goto_{q.qid}"):
                st.session_state.active_qid = q.qid
                st.session_state.draft = saved.get("text", "")
                go("solve", qid=q.qid)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    if st.button("처음으로"):
        go("start")

   


def render_solve_page():
   
    qid = st.session_state.active_qid or QUESTIONS[0].qid
    q = get_question(qid)

    st.markdown(f"**{q.prompt}**")
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # 카드 출력: 2개면 2열, 3개면 3열
    # 카드 출력: 2개면 2열, 3개면 3열
    if len(q.cards) == 2:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"<div class='card'>{q.cards[0]}</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='card'>{q.cards[1]}</div>", unsafe_allow_html=True)
    
    elif len(q.cards) == 3:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"<div class='card'>{q.cards[0]}</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='card'>{q.cards[1]}</div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='card'>{q.cards[2]}</div>", unsafe_allow_html=True)
    
    else:
        for card in q.cards:
            st.markdown(f"<div class='card'>{card}</div>", unsafe_allow_html=True)
            st.markdown("")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    answer = st.text_area(
        label="",
        placeholder="여기에 답변을 입력하세요",
        height=160,
        key="draft",
    )

    b1, b2, b3 = st.columns([1, 1, 3], vertical_alignment="center")
    with b1:
        if st.button("질문 리스트로"):
            go("list")
    with b2:
        if st.button("제출"):
            if not answer.strip():
                st.warning("답변을 입력해 주세요.")
            else:
                # 세션에만 저장
                prev_rating = st.session_state.answers.get(qid, {}).get("rating", None)
                st.session_state.answers[qid] = {"text": answer.strip(), "rating": prev_rating}
                go("review", qid=qid)
    with b3:
        st.markdown("<div class='subtle' style='text-align:left'>제출 후 별점을 매기고 질문 리스트로 돌아갑니다.</div>", unsafe_allow_html=True)

    


def render_review_page():

    qid = st.session_state.active_qid or QUESTIONS[0].qid
    q = get_question(qid)
    saved = st.session_state.answers.get(qid, {"text": "", "rating": None})

    st.markdown("**나의 답변 확인하고 스스로 채점해보기**")
    st.markdown(f"<div class='subtle' style='text-align:left'>{q.title}</div>", unsafe_allow_html=True)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    st.text_area(
        label="",
        value=saved.get("text", ""),
        height=200,
        disabled=True,
    )

    st.markdown("<div class='subtle' style='text-align:left'>별점(1~5)</div>", unsafe_allow_html=True)
    current_rating = saved.get("rating", None)
    default_index = (int(current_rating) - 1) if isinstance(current_rating, int) and 1 <= int(current_rating) <= 5 else 2

    rating = st.radio(
        label="",
        options=[1, 2, 3, 4, 5],
        horizontal=True,
        index=default_index,
        key=f"rating_{qid}",
    )

    c1, c2, c3 = st.columns([1, 1, 2], vertical_alignment="center")
    with c1:
        if st.button("수정하기"):
            st.session_state.draft = saved.get("text", "")
            go("solve", qid=qid)
    with c2:
        if st.button("저장하고 리스트로"):
            st.session_state.answers[qid] = {"text": saved.get("text", ""), "rating": int(rating)}
            go("list")
    with c3:
        st.markdown("<div class='subtle' style='text-align:right'>별점 저장 후 리스트로 돌아갑니다.</div>", unsafe_allow_html=True)

 


# ---------------------------
# 4) App entry
# ---------------------------
def main():
    st.set_page_config(page_title="피로사회 마무리 퀴즈", layout="wide")
  
    init_state()

    if st.session_state.page == "start":
        render_start_page()
    elif st.session_state.page == "list":
        render_list_page()
    elif st.session_state.page == "solve":
        render_solve_page()
    elif st.session_state.page == "review":
        render_review_page()
    else:
        go("start")


if __name__ == "__main__":
    main()
