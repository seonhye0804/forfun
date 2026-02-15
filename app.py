# app.py
# 실행: streamlit run app.py
#
# 기능(실작동):
# - 시작(학생 이름 입력) -> 질문 리스트 -> 질문 풀이(카드/조건 확인 + 답변 작성) -> 제출/자가채점 -> 리스트 복귀
# - 답변/별점/제출시간을 로컬 SQLite에 자동 저장(서버 재시작해도 유지)
# - 간단한 “조건 충족(키워드 기반)” 점검(완벽 자동채점 아님)

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

import streamlit as st


# ---------------------------
# 0) 질문/카드 (사용자 제공 내용 반영)
# ---------------------------
@dataclass
class Question:
    qid: str
    title: str
    prompt: str
    cards: List[str]
    # 아주 단순한 조건 점검(키워드 기반). "모두 포함"이 아니라 "힌트/경고" 용도.
    # 각 튜플: (설명, 포함되어야 할 키워드들 중 최소 1개/모두 등)
    must_include_all: List[Tuple[str, List[str]]]
    must_include_any: List[Tuple[str, List[str]]]


Q1_CARD1 = """다음 사례를 답변에 포함하시오

전 세계적으로 고카페인 음료 섭취가 늘어나면서 국가마다 대책을 마련하는 상황입니다. 우리나라 역시 청소년의 고카페인 음료 섭취가 증가하고 있으며, 고카페인 음료는 100 mL당 카페인 15 mg 이상을 포함한 음료를 의미합니다. 질병관리청 조사에 따르면 중고등학생의 고카페인 음료 주 3회 이상 섭취율은 2015년 3.3%에서 2017년 8.0%, 2019년에는 12.2%로 꾸준히 증가했습니다. 2020년 조사에서는 청소년 중 약 30%가 하루 3병 이상의 고카페인 음료를 섭취한 경험이 있다고 응답했습니다. (질병관리청)
"""

Q1_CARD2 = """‘도핑사회’ 이외에 저자가 언급한 사회의 종류를 포함하여 답변하시오"""

Q2_CARD1 = """다음 정보를 답변할 때 참고하시오

오순절은 이스라엘의 명절이다. 예수 그리스도께서 부활하신지 오십일 째 되는 날이 오순절이었는데 이 날, 예수님께서 약속하신 성령이 내려왔다. 사람들이 특별한 영감을 받은 것이다. 또한 이 날 교회가 탄생했다.
"""

Q2_CARD2 = """‘오순절’과 저자가 지향하는 피로사회’가 공통적으로 가진 특징에 착안하여 서술하시오"""

Q2_CARD3 = """‘오순절’ 개념을 설명에 포함함으로서 저자가 얻을 수 있는 효과를 마지막에 포함하시오"""


QUESTIONS: List[Question] = [
    Question(
        qid="q1",
        title="질문 1",
        prompt="질문 1: <피로사회> 장 서두에 ‘도핑사회’를 언급한 이유를 카드에 나온 조건을 모두 사용해서 답하시오",
        cards=[Q1_CARD1, Q1_CARD2],
        # 키워드 점검(자동 채점이 아니라 제출 전 경고용)
        must_include_all=[
            ("‘도핑사회’라는 표현(또는 도핑)을 언급", ["도핑사회", "도핑"]),
        ],
        must_include_any=[
            # 카드2: 도핑사회 이외 사회 종류 포함 -> 최소 1개라도 언급되면 경고 해제
            ("도핑사회 이외의 ‘사회’ 종류 언급(예: 성과사회/규율사회/우울사회 등)", ["성과사회", "규율사회", "훈육사회", "우울사회"]),
            # 카드1 사례 관련 키워드
            ("고카페인 음료 사례(카페인/에너지드링크/청소년/섭취율 등) 언급", ["카페인", "고카페인", "에너지", "청소년", "섭취", "질병관리청", "100 mL", "15 mg", "2015", "2017", "2019", "2020"]),
        ],
    ),
    Question(
        qid="q2",
        title="질문 2",
        prompt="질문 2: 저자가 피로사회를 설명하면서 ‘오순절’을 언급한 이유를 카드에 나온 조건을 모두 사용해서 답하시오",
        cards=[Q2_CARD1, Q2_CARD2, Q2_CARD3],
        must_include_all=[
            ("‘오순절’을 직접 언급", ["오순절"]),
        ],
        must_include_any=[
            ("오순절 설명 요소(성령/영감/교회 탄생/부활 후 50일 등) 언급", ["성령", "영감", "교회", "탄생", "오십", "50", "부활"]),
            ("공통 특징(공통/특징/닮음/유사 등) 연결 서술", ["공통", "특징", "닮", "유사", "같", "연결"]),
            ("마지막에 ‘효과/의도/목적’ 등 저자가 얻는 효과를 명시", ["효과", "의도", "목적", "설득", "강조", "전략"]),
        ],
    ),
]


# ---------------------------
# 1) DB (SQLite, 로컬 저장)
# ---------------------------
DB_PATH = "fatigue_quiz.sqlite3"


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def db_init() -> None:
    conn = db_connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS responses (
            student TEXT NOT NULL,
            qid TEXT NOT NULL,
            answer TEXT NOT NULL,
            rating INTEGER,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (student, qid)
        );
        """
    )
    conn.commit()
    conn.close()


def db_upsert_response(student: str, qid: str, answer: str, rating: Optional[int]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = db_connect()
    conn.execute(
        """
        INSERT INTO responses (student, qid, answer, rating, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(student, qid) DO UPDATE SET
            answer=excluded.answer,
            rating=excluded.rating,
            updated_at=excluded.updated_at;
        """,
        (student, qid, answer, rating, now),
    )
    conn.commit()
    conn.close()


def db_load_all(student: str) -> Dict[str, Dict[str, Any]]:
    conn = db_connect()
    cur = conn.execute(
        "SELECT qid, answer, rating, updated_at FROM responses WHERE student = ?;",
        (student,),
    )
    out: Dict[str, Dict[str, Any]] = {}
    for qid, answer, rating, updated_at in cur.fetchall():
        out[qid] = {"text": answer, "rating": rating, "updated_at": updated_at}
    conn.close()
    return out


# ---------------------------
# 2) Session state / Routing
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
        st.session_state.answers = {}  # {qid: {"text":..., "rating":..., "updated_at":...}}
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


# ---------------------------
# 3) Styling (이전 골격 유지)
# ---------------------------
CSS = """
<style>
.block-container { padding-top: 2.2rem; padding-bottom: 2.2rem; max-width: 1100px; }
.frame {
  border: 2px solid #7a7a7a;
  border-radius: 4px;
  background: #ffffff;
  padding: 36px 42px;
  min-height: 520px;
}
.center-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 440px;
  gap: 18px;
}
.h-title { font-size: 36px; font-weight: 700; letter-spacing: -0.02em; margin: 0; }
.subtle { color: #4b4b4b; font-size: 15px; line-height: 1.5; }
div.stButton > button {
  border: 2px solid #6d6d6d !important;
  background: #bdbdbd !important;
  color: #1f1f1f !important;
  border-radius: 999px !important;
  padding: 10px 24px !important;
  min-width: 220px;
  font-weight: 600 !important;
}
.small-btn div.stButton > button { min-width: 180px; padding: 8px 18px !important; }
.card {
  border: 1.6px solid #8a8a8a;
  background: #d9d9d9;
  border-radius: 4px;
  padding: 14px 14px;
  min-height: 130px;
  white-space: pre-wrap;
  font-size: 14px;
  color: #222;
}
.hr { height: 2px; background: #8b8b8b; border: 0; margin: 10px 0 18px 0; }
.badge {
  display:inline-block;
  padding: 3px 10px;
  border:1px solid #8a8a8a;
  border-radius: 999px;
  font-size: 12px;
  color:#333;
  background:#f3f3f3;
}
</style>
"""


def frame_open():
    st.markdown('<div class="frame">', unsafe_allow_html=True)


def frame_close():
    st.markdown("</div>", unsafe_allow_html=True)


def render_top_label(label: str):
    st.caption(label)


# ---------------------------
# 4) 조건 점검(간단 키워드 기반)
# ---------------------------
def _contains_any(text: str, keywords: List[str]) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return any(k in t for k in keywords)


def _contains_all(text: str, keywords: List[str]) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return all(k in t for k in keywords)


def validate_answer(q: Question, answer: str) -> Dict[str, Any]:
    """
    제출을 막는 '정답검증'이 아니라, 학생에게 조건 누락 가능성을 알려주는 용도.
    """
    results = {
        "ok_basic": bool(answer.strip()),
        "all_checks": [],
        "any_checks": [],
    }

    for desc, kws in q.must_include_all:
        ok = _contains_all(answer, kws)
        results["all_checks"].append((desc, ok, kws))

    for desc, kws in q.must_include_any:
        ok = _contains_any(answer, kws)
        results["any_checks"].append((desc, ok, kws))

    return results


# ---------------------------
# 5) Pages
# ---------------------------
def render_start_page():
    render_top_label("1. 첫 접속 화면")
    frame_open()

    st.markdown('<div class="center-wrap">', unsafe_allow_html=True)
    st.markdown('<p class="h-title">피로사회 마무리 퀴즈</p>', unsafe_allow_html=True)
    st.markdown('<div class="subtle">학생 이름을 입력하고 시작하세요.</div>', unsafe_allow_html=True)

    st.text_input("학생 이름", key="student", placeholder="예: 2학년 3반 홍길동")

    cols = st.columns([1, 1, 1])
    with cols[1]:
        if st.button("시작하기"):
            if not st.session_state.student.strip():
                st.warning("학생 이름을 먼저 입력해 주세요.")
            else:
                # DB에서 기존 답변 불러오기
                st.session_state.answers = db_load_all(st.session_state.student.strip())
                go("list")

    st.markdown("</div>", unsafe_allow_html=True)
    frame_close()


def render_list_page():
    render_top_label("2. 질문 리스트")
    frame_open()

    student = st.session_state.student.strip()
    st.markdown(f"**학생:** {student}  <span class='badge'>로컬 자동 저장</span>", unsafe_allow_html=True)
    st.markdown("<hr class='hr'/>", unsafe_allow_html=True)

    done = 0
    for q in QUESTIONS:
        saved = st.session_state.answers.get(q.qid, {})
        has_text = bool((saved.get("text") or "").strip())
        has_rating = saved.get("rating") is not None

        if has_text:
            done += 1

        left, right = st.columns([3, 2], vertical_alignment="center")
        with left:
            st.markdown(f"**{q.title}**")
            st.markdown(f"<div class='subtle'>{q.prompt}</div>", unsafe_allow_html=True)
            status_bits = []
            status_bits.append("답변 ✅" if has_text else "답변 ⬜")
            status_bits.append("별점 ✅" if has_rating else "별점 ⬜")
            if saved.get("updated_at"):
                status_bits.append(f"저장: {saved['updated_at'][:19].replace('T',' ')} (UTC)")
            st.markdown(f"<div class='subtle'>{' · '.join(status_bits)}</div>", unsafe_allow_html=True)

        with right:
            st.markdown('<div class="small-btn">', unsafe_allow_html=True)
            if st.button("답변하기", key=f"goto_{q.qid}"):
                st.session_state.active_qid = q.qid
                st.session_state.draft = saved.get("text", "")
                go("solve", qid=q.qid)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("")

    st.markdown("<hr class='hr'/>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 2], vertical_alignment="center")
    with c1:
        if st.button("처음으로"):
            go("start")
    with c3:
        st.markdown(
            f"<div class='subtle' style='text-align:right;'>완료: {done}/{len(QUESTIONS)}</div>",
            unsafe_allow_html=True,
        )

    frame_close()


def render_solve_page():
    render_top_label("3. 질문 풀이 화면")
    frame_open()

    student = st.session_state.student.strip()
    qid = st.session_state.active_qid or QUESTIONS[0].qid
    q = get_question(qid)

    st.markdown(f"**{q.prompt}**")
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # 카드 출력(2개면 2열, 3개면 3열)
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

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # 답변 입력
    answer = st.text_area(
        label="",
        placeholder="여기에 답변을 입력하세요 (카드 조건을 모두 반영)",
        height=160,
        key="draft",
    )

    # 조건 점검(경고/힌트)
    with st.expander("조건 점검(자동 힌트) 보기", expanded=True):
        v = validate_answer(q, answer)
        if not v["ok_basic"]:
            st.warning("아직 답변이 비어 있어요.")
        for desc, ok, kws in v["all_checks"]:
            st.success(f"[필수] {desc}") if ok else st.error(f"[필수] {desc}  (힌트 키워드: {', '.join(kws)})")
        for desc, ok, kws in v["any_checks"]:
            st.success(f"[권장] {desc}") if ok else st.warning(f"[권장] {desc}  (힌트 키워드: {', '.join(kws)})")

        st.caption("※ 이 점검은 ‘키워드 포함 여부’만 확인합니다. 실제로 카드 조건을 충실히 반영했는지는 본인이 최종 확인하세요.")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    b1, b2, b3 = st.columns([1, 1, 3], vertical_alignment="center")
    with b1:
        if st.button("질문 리스트로"):
            go("list")
    with b2:
        if st.button("제출(저장)"):
            if not student:
                st.error("학생 이름이 없습니다. 처음 화면으로 돌아가 이름을 입력해 주세요.")
            elif not answer.strip():
                st.warning("답변을 입력한 뒤 제출해 주세요.")
            else:
                # DB 저장
                prev_rating = st.session_state.answers.get(qid, {}).get("rating", None)
                db_upsert_response(student, qid, answer.strip(), prev_rating)
                # 세션에도 반영
                st.session_state.answers[qid] = {
                    "text": answer.strip(),
                    "rating": prev_rating,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                go("review", qid=qid)
    with b3:
        st.markdown("<div class='subtle'>제출하면 자동 저장되고, 다음 화면에서 별점(자가채점)을 남길 수 있어요.</div>", unsafe_allow_html=True)

    frame_close()


def render_review_page():
    render_top_label("4. 제출 확인/자가채점")
    frame_open()

    student = st.session_state.student.strip()
    qid = st.session_state.active_qid or QUESTIONS[0].qid
    q = get_question(qid)

    saved = st.session_state.answers.get(qid, {"text": "", "rating": None, "updated_at": None})

    st.markdown("**나의 답변 확인 + 별점(자가채점)**")
    st.markdown(f"<div class='subtle'>{q.title} · {student}</div>", unsafe_allow_html=True)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    st.text_area(
        label="",
        value=saved.get("text", ""),
        height=200,
        disabled=True,
    )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown("<div class='subtle'>별점(1~5)</div>", unsafe_allow_html=True)

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
        if st.button("별점 저장하고 돌아가기"):
            if not student:
                st.error("학생 이름이 없습니다. 처음 화면으로 돌아가 이름을 입력해 주세요.")
            else:
                db_upsert_response(student, qid, saved.get("text", "").strip(), int(rating))
                st.session_state.answers[qid] = {
                    "text": saved.get("text", "").strip(),
                    "rating": int(rating),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                go("list")
    with c3:
        ts = saved.get("updated_at")
        if ts:
            st.markdown(
                f"<div class='subtle' style='text-align:right;'>마지막 저장: {ts[:19].replace('T',' ')} (UTC)</div>",
                unsafe_allow_html=True,
            )

    frame_close()


# ---------------------------
# 6) App entry
# ---------------------------
def main():
    st.set_page_config(page_title="피로사회 마무리 퀴즈", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)

    db_init()
    init_state()

    # 사이드바(교사용/디버그 느낌으로 최소만)
    with st.sidebar:
        st.markdown("### 메뉴")
        if st.session_state.student.strip():
            st.write("학생:", st.session_state.student.strip())
        else:
            st.write("학생: (미입력)")
        st.write("페이지:", st.session_state.page)

        st.markdown("---")
        st.markdown("### 안내")
        st.caption("답변/별점은 로컬 SQLite에 자동 저장됩니다.")
        st.caption("조건 점검은 키워드 기반 ‘힌트’입니다.")

        if st.button("세션 초기화(학생 전환용)"):
            st.session_state.page = "start"
            st.session_state.student = ""
            st.session_state.active_qid = None
            st.session_state.answers = {}
            st.session_state.draft = ""
            st.rerun()

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

