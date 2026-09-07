import streamlit as st
import requests
import pandas as pd
import plotly.express as px

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 1. 페이지 기본 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 박스오피스 조회")

st.write(
    "한국 시간 기준으로 원하는 날짜의 "
    "영화관입장권통합전산망(KOBIS) 박스오피스를 확인할 수 있습니다."
)


# ---------------------------------------------------------
# 2. 한국 시간 기준 날짜 계산
# ---------------------------------------------------------
# Streamlit Cloud의 서버 시간은 한국 시간이 아닐 수 있으므로
# 한국 시간(KST)을 기준으로 날짜를 계산합니다.
kst = ZoneInfo("Asia/Seoul")

today_kst = datetime.now(kst).date()

# 오늘은 아직 집계 전이므로 선택할 수 있는 가장 늦은 날짜는 어제입니다.
yesterday_kst = today_kst - timedelta(days=1)


# ---------------------------------------------------------
# 3. 날짜 선택
# ---------------------------------------------------------
st.subheader("📅 조회할 날짜")

selected_date = st.date_input(
    "박스오피스 날짜를 선택하세요.",
    value=yesterday_kst,
    min_value=datetime(2004, 1, 1).date(),
    max_value=yesterday_kst
)

# KOBIS API가 사용하는 날짜 형식으로 변환합니다.
target_date = selected_date.strftime("%Y%m%d")

# 화면에 표시할 날짜
display_date = selected_date.strftime("%Y년 %m월 %d일")


# ---------------------------------------------------------
# 4. KOBIS API에서 데이터 가져오기
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    """
    같은 날짜의 API 결과를 약 1시간 동안 기억합니다.

    따라서 같은 날짜를 다시 조회하면
    API를 다시 호출하지 않고 캐시된 결과를 사용합니다.
    """

    # Streamlit Secrets에서 인증키를 가져옵니다.
    # 실제 인증키를 코드에 직접 적지 않습니다.
    api_key = st.secrets.get("KOBIS_KEY")

    # 인증키가 없는 경우
    if not api_key:
        return {
            "success": False,
            "error_type": "key",
            "message": "KOBIS_KEY를 찾을 수 없습니다.",
            "data": None
        }

    # KOBIS 일별 박스오피스 API 주소
    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    # API에 보낼 값
    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        # KOBIS API 요청
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류 확인
        response.raise_for_status()

        # JSON 데이터로 변환
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


    # -----------------------------------------------------
    # 5. KOBIS faultInfo 확인
    # -----------------------------------------------------
    # 인증키가 잘못되어도 HTTP 상태코드는 200일 수 있기 때문에
    # faultInfo가 있는지를 따로 확인해야 합니다.
    fault_info = result.get("faultInfo")

    if fault_info:
        fault_code = fault_info.get("errorCode", "")
        fault_message = fault_info.get(
            "message",
            "알 수 없는 오류"
        )

        return {
            "success": False,
            "error_type": "fault",
            "message": f"{fault_message} (오류 코드: {fault_code})",
            "data": None
        }


    # -----------------------------------------------------
    # 6. boxOfficeResult 확인
    # -----------------------------------------------------
    boxoffice_result = result.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "error_type": "empty",
            "message": "boxOfficeResult가 없습니다.",
            "data": None
        }


    # 영화 목록 가져오기
    movie_list = boxoffice_result.get(
        "dailyBoxOfficeList",
        []
    )

    # 영화 목록이 비어 있는 경우
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


# ---------------------------------------------------------
# 7. 선택한 날짜의 데이터 가져오기
# ---------------------------------------------------------
result = get_boxoffice(target_date)


# ---------------------------------------------------------
# 8. 오류 처리
# ---------------------------------------------------------
if not result["success"]:

    # 인증키가 없는 경우
    if result["error_type"] == "key":

        st.error("🔑 KOBIS 인증키를 찾을 수 없습니다.")

        st.markdown("""
        **확인할 것**

        1. Streamlit Cloud에서 **Settings → Secrets**로 이동합니다.
        2. `KOBIS_KEY`가 등록되어 있는지 확인합니다.
        3. 인증키 앞뒤에 불필요한 공백이 없는지 확인합니다.

        Secrets에는 다음과 같은 형태로 입력합니다.

        ```toml
        KOBIS_KEY = "발급받은_인증키"
        ```
        """)


    # KOBIS faultInfo가 온 경우
    elif result["error_type"] == "fault":

        st.error("🚨 KOBIS API에서 오류를 반환했습니다.")

        st.write(
            f"오류 내용: {result['message']}"
        )

        st.markdown("""
        **확인할 것**

        - KOBIS 인증키가 정확한지 확인하세요.
        - KOBIS Open API 사용이 가능한지 확인하세요.
        - API 요청 주소가 정확한지 확인하세요.
        """)


    # API 연결에 실패한 경우
    elif result["error_type"] == "request":

        st.error("🌐 KOBIS API에 연결하지 못했습니다.")

        st.write(
            f"요청 오류: {result['message']}"
        )

        st.markdown("""
        **확인할 것**

        - 인터넷 연결 상태를 확인하세요.
        - KOBIS 서버가 정상적으로 동작하는지 확인하세요.
        - 잠시 후 다시 실행해 보세요.
        """)


    # JSON 변환에 실패한 경우
    elif result["error_type"] == "json":

        st.error(
            "📄 KOBIS API의 응답을 읽지 못했습니다."
        )

        st.markdown("""
        **확인할 것**

        - KOBIS API가 정상적으로 응답하는지 확인하세요.
        - API 요청 주소가 정확한지 확인하세요.
        """)


    # 영화 목록이 비어 있는 경우
    else:

        st.warning(
            f"📭 {display_date} 박스오피스 데이터를 찾을 수 없습니다."
        )

        st.info(
            "그날은 아직 집계 전입니다."
        )

        st.markdown("""
        **확인할 것**

        - 선택한 날짜가 KOBIS에서 아직 집계되지 않았는지 확인하세요.
        - 날짜를 다른 날짜로 선택해 보세요.
        """)

    # 오류가 발생하면 아래의 표와 그래프를 만들지 않습니다.
    st.stop()


# ---------------------------------------------------------
# 9. 데이터를 DataFrame으로 변환
# ---------------------------------------------------------
movie_list = result["data"]

df = pd.DataFrame(movie_list)


# ---------------------------------------------------------
# 10. 숫자 데이터를 숫자로 변환
# ---------------------------------------------------------
# KOBIS API에서는 숫자도 문자열로 전달됩니다.
# 그래프와 정렬에 사용할 수 있도록 숫자형으로 변환합니다.
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


# ---------------------------------------------------------
# 11. 영화 순위 순서대로 정렬
# ---------------------------------------------------------
df = (
    df.sort_values("rank")
    .reset_index(drop=True)
)


# ---------------------------------------------------------
# 12. 조회 날짜 표시
# ---------------------------------------------------------
st.subheader(
    f"📅 {display_date} 박스오피스"
)

st.caption(
    "※ 데이터는 KOBIS 영화관입장권통합전산망 "
    "일별 박스오피스 기준입니다."
)


# ---------------------------------------------------------
# 13. 1위 영화 확인
# ---------------------------------------------------------
first_movie = df.iloc[0]

st.subheader("🥇 1위 영화")


# ---------------------------------------------------------
# 14. 1위 영화 지표 카드 3개
# ---------------------------------------------------------
col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        label="영화명",
        value=str(first_movie["movieNm"])
    )


with col2:

    st.metric(
        label="관객수",
        value=f"{first_movie['audiCnt']:,}명"
    )


with col3:

    st.metric(
        label="누적관객",
        value=f"{first_movie['audiAcc']:,}명"
    )


# ---------------------------------------------------------
# 15. 전체 박스오피스 표 만들기
# ---------------------------------------------------------
st.subheader("🎥 전체 박스오피스")


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


# ---------------------------------------------------------
# 16. 순위 증감 화살표 만들기
# ---------------------------------------------------------
def make_rank_change(rank_inten):
    """
    전날보다 순위가 오른 경우 빨간 위 화살표,
    전날보다 순위가 내려간 경우 파란 아래 화살표를 표시합니다.

    0이면 변동이 없으므로 '-'로 표시합니다.
    """

    if rank_inten > 0:
        return f"🔴 ↑ {rank_inten}"

    elif rank_inten < 0:
        return f"🔵 ↓ {abs(rank_inten)}"

    else:
        return "-"


table_df["순위 변동"] = table_df["rankInten"].apply(
    make_rank_change
)


# ---------------------------------------------------------
# 17. 누적관객 100만 명 이상이면 트로피 붙이기
# ---------------------------------------------------------
def add_trophy(row):
    """
    누적관객이 1,000,000명을 넘은 영화의
    영화명 옆에 트로피를 붙입니다.
    """

    movie_name = str(row["movieNm"])

    if row["audiAcc"] > 1_000_000:
        return f"{movie_name} 🏆"

    return movie_name


table_df["영화명"] = table_df.apply(
    add_trophy,
    axis=1
)


# ---------------------------------------------------------
# 18. 표에 보여줄 열 선택
# ---------------------------------------------------------
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


# 열 이름 설정
display_df.columns = [
    "순위",
    "순위 변동",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# ---------------------------------------------------------
# 19. 숫자를 보기 좋게 표시
# ---------------------------------------------------------
for column in [
    "관객수",
    "누적관객",
    "스크린수"
]:

    display_df[column] = display_df[column].map(
        lambda x: f"{x:,}"
    )


# ---------------------------------------------------------
# 20. 표 출력
# ---------------------------------------------------------
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# ---------------------------------------------------------
# 21. 관객수 상위 5편 가져오기
# ---------------------------------------------------------
st.subheader("📊 관객수 상위 5편")


# ---------------------------------------------------------
# 핵심!
# ---------------------------------------------------------
# 관객수가 아니라 '순위'를 기준으로 정렬합니다.
# 이렇게 하면 그래프가 1위 → 2위 → 3위 → 4위 → 5위
# 순서로 만들어집니다.
top5 = (
    df.sort_values("rank")
    .head(5)
    .copy()
)


# 그래프에 사용할 영화 이름을 만듭니다.
# 예: "1위 영화제목", "2위 영화제목"
top5["영화"] = (
    top5["rank"].astype(str)
    + "위 "
    + top5["movieNm"].astype(str)
)


# ---------------------------------------------------------
# 22. Plotly용 데이터 만들기
# ---------------------------------------------------------
chart_df = top5[
    ["rank", "영화", "audiCnt"]
].copy()


# 순위 순서를 명시적으로 지정합니다.
# Plotly가 영화 제목을 가나다순으로 바꾸지 못하게 합니다.
rank_order = chart_df["영화"].tolist()


# ---------------------------------------------------------
# 23. 막대그래프 만들기
# ---------------------------------------------------------
fig = px.bar(
    chart_df,
    x="영화",
    y="audiCnt",
    category_orders={
        "영화": rank_order
    },
    labels={
        "영화": "영화",
        "audiCnt": "관객수"
    }
)


# 그래프 제목
fig.update_layout(
    title="관객수 상위 5편",
    xaxis_title="영화",
    yaxis_title="관객수",
    showlegend=False
)


# ---------------------------------------------------------
# 24. 그래프 출력
# ---------------------------------------------------------
st.plotly_chart(
    fig,
    use_container_width=True
)
