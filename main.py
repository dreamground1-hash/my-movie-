import streamlit as st
import requests
import pandas as pd

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# =========================================================
# 1. 페이지 기본 설정
# =========================================================

st.set_page_config(
    page_title="박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 박스오피스 조회")

st.write(
    "한국 시간 기준으로 원하는 날짜의 "
    "영화관입장권통합전산망(KOBIS) 일별 박스오피스를 확인할 수 있습니다."
)


# =========================================================
# 2. 한국 시간 기준으로 오늘과 어제 날짜 계산
# =========================================================

# Streamlit Cloud 서버의 시간은 한국 시간이 아닐 수 있습니다.
# 그래서 한국 시간(KST)을 기준으로 날짜를 계산합니다.
kst = ZoneInfo("Asia/Seoul")

today_kst = datetime.now(kst).date()

# 오늘의 박스오피스는 아직 집계 전이므로
# 선택할 수 있는 가장 늦은 날짜는 어제입니다.
yesterday_kst = today_kst - timedelta(days=1)


# =========================================================
# 3. 날짜 선택
# =========================================================

st.subheader("📅 조회할 날짜")

selected_date = st.date_input(
    "박스오피스 날짜를 선택하세요.",
    value=yesterday_kst,
    min_value=datetime(2004, 1, 1).date(),
    max_value=yesterday_kst
)

# 선택한 날짜를 KOBIS API에서 사용하는
# YYYYMMDD 형식으로 변환합니다.
target_date = selected_date.strftime("%Y%m%d")

# 화면에 보여줄 날짜입니다.
display_date = selected_date.strftime("%Y년 %m월 %d일")


# =========================================================
# 4. KOBIS API에서 데이터 가져오기
# =========================================================

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    """
    선택한 날짜의 박스오피스 데이터를 가져옵니다.

    ttl=3600은 3600초, 즉 약 1시간입니다.
    같은 날짜를 1시간 안에 다시 조회하면
    KOBIS API를 다시 호출하지 않고 저장된 결과를 사용합니다.
    """

    # -----------------------------------------------------
    # KOBIS 인증키 가져오기
    # -----------------------------------------------------
    # 실제 인증키를 코드에 작성하지 않습니다.
    # Streamlit Cloud의 Secrets에서 가져옵니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except KeyError:
        return {
            "success": False,
            "error_type": "key",
            "message": "KOBIS_KEY를 찾을 수 없습니다.",
            "data": None
        }


    # -----------------------------------------------------
    # KOBIS API 주소
    # -----------------------------------------------------

    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )


    # -----------------------------------------------------
    # API 요청 변수
    # -----------------------------------------------------

    params = {
        "key": api_key,
        "targetDt": target_dt
    }


    # -----------------------------------------------------
    # API 요청
    # -----------------------------------------------------

    try:

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류가 있는지 확인합니다.
        response.raise_for_status()

        # 응답 내용을 JSON으로 변환합니다.
        result = response.json()


    except requests.exceptions.RequestException as e:

        return {
            "success": False,
            "error_type": "request",
            "message": str(e),
            "data": None
        }


    except ValueError:

        return {
            "success": False,
            "error_type": "json",
            "message": "API 응답을 JSON 형식으로 읽을 수 없습니다.",
            "data": None
        }


    # =====================================================
    # 5. KOBIS faultInfo 확인
    # =====================================================

    # KOBIS는 인증키가 틀려도 HTTP 상태코드 200을
    # 반환하고 faultInfo를 보내는 경우가 있습니다.
    # 따라서 반드시 faultInfo를 확인합니다.

    fault_info = result.get("faultInfo")

    if fault_info:

        fault_code = fault_info.get(
            "errorCode",
            ""
        )

        fault_message = fault_info.get(
            "message",
            "알 수 없는 오류"
        )

        return {
            "success": False,
            "error_type": "fault",
            "message": (
                f"{fault_message} "
                f"(오류 코드: {fault_code})"
            ),
            "data": None
        }


    # =====================================================
    # 6. boxOfficeResult 확인
    # =====================================================

    boxoffice_result = result.get(
        "boxOfficeResult"
    )

    if not boxoffice_result:

        return {
            "success": False,
            "error_type": "empty",
            "message": "boxOfficeResult가 없습니다.",
            "data": None
        }


    # =====================================================
    # 7. 영화 목록 가져오기
    # =====================================================

    movie_list = boxoffice_result.get(
        "dailyBoxOfficeList",
        []
    )


    # 영화 목록이 비어 있으면
    # 집계 전일 가능성이 있으므로 따로 처리합니다.
    if not movie_list:

        return {
            "success": False,
            "error_type": "empty",
            "message": "영화 목록이 없습니다.",
            "data": None
        }


    # 정상적으로 데이터를 가져온 경우
    return {
        "success": True,
        "error_type": None,
        "message": "",
        "data": movie_list
    }


# =========================================================
# 8. 선택한 날짜의 데이터 가져오기
# =========================================================

result = get_boxoffice(target_date)


# =========================================================
# 9. 오류 처리
# =========================================================

if not result["success"]:

    # -----------------------------------------------------
    # 인증키 오류
    # -----------------------------------------------------

    if result["error_type"] == "key":

        st.error(
            "🔑 KOBIS 인증키를 찾을 수 없습니다."
        )

        st.markdown("""
        ### 확인할 것

        1. Streamlit Cloud에서 **Settings → Secrets**로 이동합니다.
        2. `KOBIS_KEY`가 등록되어 있는지 확인합니다.
        3. 인증키 앞뒤에 불필요한 공백이 없는지 확인합니다.

        Secrets에는 다음과 같은 형태로 입력합니다.

        ```toml
        KOBIS_KEY = "발급받은_인증키"
        ```
        """)


    # -----------------------------------------------------
    # KOBIS faultInfo 오류
    # -----------------------------------------------------

    elif result["error_type"] == "fault":

        st.error(
            "🚨 KOBIS API에서 오류를 반환했습니다."
        )

        st.write(
            f"오류 내용: {result['message']}"
        )

        st.markdown("""
        ### 확인할 것

        - KOBIS 인증키가 정확한지 확인하세요.
        - Streamlit Cloud의 Secrets에 키가 제대로 등록되어 있는지 확인하세요.
        - KOBIS Open API 사용이 가능한 상태인지 확인하세요.
        - API 요청 주소가 정확한지 확인하세요.
        """)


    # -----------------------------------------------------
    # 인터넷/API 연결 오류
    # -----------------------------------------------------

    elif result["error_type"] == "request":

        st.error(
            "🌐 KOBIS API에 연결하지 못했습니다."
        )

        st.write(
            f"요청 오류: {result['message']}"
        )

        st.markdown("""
        ### 확인할 것

        - 인터넷 연결 상태를 확인하세요.
        - KOBIS 서버가 정상적으로 동작하는지 확인하세요.
        - 잠시 후 다시 실행해 보세요.
        """)


    # -----------------------------------------------------
    # JSON 변환 오류
    # -----------------------------------------------------

    elif result["error_type"] == "json":

        st.error(
            "📄 KOBIS API의 응답을 읽지 못했습니다."
        )

        st.markdown("""
        ### 확인할 것

        - KOBIS API가 정상적으로 응답하는지 확인하세요.
        - API 요청 주소가 정확한지 확인하세요.
        - 잠시 후 다시 실행해 보세요.
        """)


    # -----------------------------------------------------
    # 영화 목록이 없는 경우
    # -----------------------------------------------------

    else:

        st.warning(
            f"📭 {display_date}의 박스오피스 영화 목록이 없습니다."
        )

        st.info(
            "그날은 아직 집계 전입니다."
        )

        st.markdown("""
        ### 확인할 것

        - 선택한 날짜의 박스오피스가 아직 집계되지 않았는지 확인하세요.
        - 다른 날짜를 선택해 보세요.
        """)


    # 오류가 발생했으므로
    # 아래의 표와 그래프는 만들지 않습니다.
    st.stop()


# =========================================================
# 10. API 데이터를 DataFrame으로 변환
# =========================================================

movie_list = result["data"]

df = pd.DataFrame(movie_list)


# =========================================================
# 11. 숫자 데이터를 숫자형으로 변환
# =========================================================

# KOBIS API에서는 숫자도 문자열로 전달됩니다.
# 정렬과 그래프에 사용할 수 있도록 숫자로 변환합니다.

number_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt"
]

for column in number_columns:

    if column in df.columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        ).fillna(0).astype(int)


# =========================================================
# 12. 영화 순위 기준으로 정렬
# =========================================================

df = (
    df.sort_values("rank")
    .reset_index(drop=True)
)


# =========================================================
# 13. 날짜 표시
# =========================================================

st.subheader(
    f"📅 {display_date} 박스오피스"
)

st.caption(
    "※ 데이터는 KOBIS 영화관입장권통합전산망 "
    "일별 박스오피스 기준입니다."
)


# =========================================================
# 14. 1위 영화 정보
# =========================================================

first_movie = df.iloc[0]

st.subheader("🥇 1위 영화")


# =========================================================
# 15. 1위 영화 지표 카드 3개
# =========================================================

col1, col2, col3 = st.columns(3)


# 첫 번째 카드: 영화명
with col1:

    first_movie_name = str(
        first_movie["movieNm"]
    )

    # 1위 영화도 누적관객이 100만 명을 넘었다면
    # 트로피를 붙입니다.
    if first_movie["audiAcc"] > 1_000_000:
        first_movie_name += " 🏆"

    st.metric(
        label="영화명",
        value=first_movie_name
    )


# 두 번째 카드: 당일 관객수
with col2:

    st.metric(
        label="관객수",
        value=f"{first_movie['audiCnt']:,}명"
    )


# 세 번째 카드: 누적관객
with col3:

    st.metric(
        label="누적관객",
        value=f"{first_movie['audiAcc']:,}명"
    )


# =========================================================
# 16. 전체 박스오피스 표
# =========================================================

st.subheader("🎥 전체 박스오피스")


# 필요한 데이터만 선택합니다.
table_df = df[
    [
        "rank",
        "rankInten",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# =========================================================
# 17. 순위 증감 화살표
# =========================================================

def make_rank_change(rank_inten):
    """
    rankInten은 전날과 비교한 순위 증감입니다.

    양수:
    순위가 오른 영화 → 빨간 위 화살표

    음수:
    순위가 내려간 영화 → 파란 아래 화살표

    0:
    순위 변동 없음
    """

    if rank_inten > 0:

        return f"🔴 ↑ {rank_inten}"

    elif rank_inten < 0:

        return f"🔵 ↓ {abs(rank_inten)}"

    else:

        return "-"


table_df["순위 변동"] = table_df[
    "rankInten"
].apply(make_rank_change)


# =========================================================
# 18. 누적관객 100만 명 트로피
# =========================================================

def add_trophy(row):
    """
    누적관객이 1,000,000명을 초과한 영화의
    영화명 옆에 🏆를 붙입니다.
    """

    movie_name = str(
        row["movieNm"]
    )

    if row["audiAcc"] > 1_000_000:

        return f"{movie_name} 🏆"

    return movie_name


table_df["영화명"] = table_df.apply(
    add_trophy,
    axis=1
)


# =========================================================
# 19. 표에 표시할 열 선택
# =========================================================

display_df = table_df[
    [
        "rank",
        "순위 변동",
        "영화명",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# 열 이름을 한국어로 변경합니다.
display_df.columns = [
    "순위",
    "순위 변동",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# =========================================================
# 20. 숫자에 천 단위 쉼표 표시
# =========================================================

for column in [
    "관객수",
    "누적관객",
    "스크린수"
]:

    display_df[column] = display_df[
        column
    ].map(
        lambda x: f"{x:,}"
    )


# =========================================================
# 21. 전체 표 출력
# =========================================================

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# =========================================================
# 22. 관객수 상위 5편 그래프
# =========================================================

st.subheader("📊 관객수 상위 5편")


# 먼저 관객수가 많은 영화 5편을 선택합니다.
top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)


# =========================================================
# 23. 그래프용 영화 이름 만들기
# =========================================================

# 영화 제목 앞에 순위를 붙입니다.
# 예:
# 1위 영화A
# 2위 영화B
# 3위 영화C
#
# 이렇게 하면 영화 제목의 가나다순과 관계없이
# 순위가 먼저 표시됩니다.

top5["영화"] = (
    top5["rank"].astype(str)
    + "위 "
    + top5["movieNm"].astype(str)
)


# =========================================================
# 24. 관객수 내림차순 순서 고정
# =========================================================

# 관객수가 많은 순서가 그대로 유지되도록
# 영화 이름의 순서를 명시적으로 지정합니다.

movie_order = top5["영화"].tolist()

top5["영화"] = pd.Categorical(
    top5["영화"],
    categories=movie_order,
    ordered=True
)


# 다시 관객수가 많은 순서로 정렬합니다.
top5 = top5.sort_values(
    "audiCnt",
    ascending=False
)


# =========================================================
# 25. 그래프 데이터 만들기
# =========================================================

chart_df = top5[
    ["영화", "audiCnt"]
].copy()

chart_df = chart_df.set_index(
    "영화"
)


# =========================================================
# 26. 막대그래프 출력
# =========================================================

st.bar_chart(
    chart_df,
    x_label="영화",
    y_label="관객수"
)
