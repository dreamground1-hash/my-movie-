import streamlit as st
import requests
import pandas as pd
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

st.title("🎬 어제의 박스오피스")
st.write(
    "한국 시간 기준으로 어제의 영화관입장권통합전산망(KOBIS) "
    "일별 박스오피스를 보여줍니다."
)


# ---------------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 날짜 계산
# ---------------------------------------------------------
# 배포 서버의 시간이 한국 시간이 아닐 수 있기 때문에
# 서버 시간 대신 한국 시간(KST)을 사용합니다.
kst = ZoneInfo("Asia/Seoul")

today_kst = datetime.now(kst).date()
yesterday_kst = today_kst - timedelta(days=1)

# KOBIS API가 요구하는 날짜 형식: YYYYMMDD
target_date = yesterday_kst.strftime("%Y%m%d")

# 화면에 보여줄 날짜
display_date = yesterday_kst.strftime("%Y년 %m월 %d일")


# ---------------------------------------------------------
# 3. KOBIS API에서 데이터 가져오기
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    """
    같은 날짜의 데이터를 1시간 동안 캐시합니다.
    따라서 같은 날짜를 다시 조회해도 API를 다시 호출하지 않습니다.
    """

    # Streamlit Secrets에서 KOBIS 인증키를 가져옵니다.
    # 실제 인증키는 코드에 작성하지 않습니다.
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

    # API에 전달할 요청 변수
    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        # KOBIS API에 요청합니다.
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류가 있으면 오류를 발생시킵니다.
        response.raise_for_status()

        # 응답을 JSON으로 변환합니다.
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
    # 4. KOBIS faultInfo 오류 확인
    # -----------------------------------------------------
    # 인증키가 틀려도 HTTP 상태코드는 200일 수 있습니다.
    # 따라서 faultInfo가 있는지 반드시 확인합니다.
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
    # 5. boxOfficeResult 확인
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
            "message": "해당 날짜의 영화 목록이 없습니다.",
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
# 6. API 호출
# ---------------------------------------------------------
result = get_boxoffice(target_date)


# ---------------------------------------------------------
# 7. 오류가 발생했을 때 안내
# ---------------------------------------------------------
if not result["success"]:

    # 인증키 오류
    if result["error_type"] == "key":

        st.error("🔑 KOBIS 인증키를 찾을 수 없습니다.")

        st.markdown("""
        **확인할 것**

        1. Streamlit Cloud의 **Settings → Secrets**에 들어갑니다.
        2. `KOBIS_KEY`가 등록되어 있는지 확인합니다.
        3. 인증키 앞뒤에 불필요한 공백이 없는지 확인합니다.

        Secrets에는 다음과 같은 형태로 입력합니다.

        ```toml
        KOBIS_KEY = "발급받은_인증키"
        ```
        """)


    # KOBIS faultInfo 오류
    elif result["error_type"] == "fault":

        st.error("🚨 KOBIS API에서 오류를 반환했습니다.")

        st.write(
            f"오류 내용: {result['message']}"
        )

        st.markdown("""
        **확인할 것**

        - KOBIS 인증키가 정확한지 확인하세요.
        - KOBIS Open API 사용이 가능한 상태인지 확인하세요.
        - API 요청 주소가 정확한지 확인하세요.
        - 조회 날짜가 올바른지 확인하세요.
        """)


    # 인터넷/API 연결 오류
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


    # JSON 변환 오류
    elif result["error_type"] == "json":

        st.error(
            "📄 KOBIS API의 응답을 읽지 못했습니다."
        )

        st.markdown("""
        **확인할 것**

        - KOBIS API가 정상적으로 응답하고 있는지 확인하세요.
        - API 요청 주소가 정확한지 확인하세요.
        """)


    # 데이터가 없는 경우
    else:

        st.warning(
            "📭 해당 날짜의 박스오피스 영화 목록이 없습니다."
        )

        st.markdown("""
        **확인할 것**

        - 조회 날짜에 실제 영화관 박스오피스 집계가 있었는지 확인하세요.
        - KOBIS API가 해당 날짜의 데이터를 제공하는지 확인하세요.
        - 잠시 후 다시 실행해 보세요.
        """)

    # 오류가 발생하면 아래의 그래프와 표를 만들지 않습니다.
    st.stop()


# ---------------------------------------------------------
# 8. 데이터를 DataFrame으로 변환
# ---------------------------------------------------------
movie_list = result["data"]

df = pd.DataFrame(movie_list)


# ---------------------------------------------------------
# 9. 숫자 데이터를 숫자형으로 변환
# ---------------------------------------------------------
# KOBIS API에서는 숫자도 문자열로 전달됩니다.
# 따라서 정렬과 그래프를 위해 숫자로 변환합니다.
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
# 10. 영화 순위 순서대로 정렬
# ---------------------------------------------------------
df = (
    df.sort_values("rank")
    .reset_index(drop=True)
)


# ---------------------------------------------------------
# 11. 조회 날짜 표시
# ---------------------------------------------------------
st.subheader(
    f"📅 {display_date} 박스오피스"
)

st.caption(
    "※ 데이터는 KOBIS 영화관입장권통합전산망 "
    "일별 박스오피스 기준입니다."
)


# ---------------------------------------------------------
# 12. 1위 영화 지표 카드
# ---------------------------------------------------------
first_movie = df.iloc[0]

st.subheader("🥇 1위 영화")

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
# 13. 전체 박스오피스 표
# ---------------------------------------------------------
st.subheader("🎥 전체 박스오피스")


# 필요한 열만 선택합니다.
table_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# 열 이름을 한국어로 변경합니다.
table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# ---------------------------------------------------------
# 14. 표에서 숫자를 보기 좋게 표시
# ---------------------------------------------------------
display_df = table_df.copy()

for column in [
    "관객수",
    "누적관객",
    "스크린수"
]:

    display_df[column] = display_df[column].map(
        lambda x: f"{x:,}"
    )


# 표 출력
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# ---------------------------------------------------------
# 15. 관객수 상위 5편 막대그래프
# ---------------------------------------------------------
st.subheader("📊 관객수 상위 5편")


# ---------------------------------------------------------
# 핵심 수정 부분
# ---------------------------------------------------------
# 관객수 기준으로 정렬하면 영화 제목이 가나다순으로
# 정렬될 수 있으므로, 먼저 '순위' 기준으로 정렬합니다.
top5 = (
    df.sort_values("rank")
    .head(5)
    .copy()
)


# 영화 제목 앞에 실제 순위를 붙입니다.
# 예: "1위 영화제목", "2위 영화제목" ...
top5["영화"] = (
    top5["rank"].astype(str)
    + "위 "
    + top5["movieNm"].astype(str)
)


# 순위를 기준으로 만들어진 영화 이름을 인덱스로 사용합니다.
chart_df = top5.set_index("영화")[["audiCnt"]]


# ---------------------------------------------------------
# 16. 막대그래프 출력
# ---------------------------------------------------------
st.bar_chart(
    chart_df,
    x_label="영화",
    y_label="관객수"
)
