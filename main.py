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
st.write("한국 시간 기준으로 어제의 영화관입장권통합전산망(KOBIS) 일별 박스오피스를 보여줍니다.")


# ---------------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 날짜 계산
# ---------------------------------------------------------
# 배포 서버가 한국 시간이 아닐 수 있으므로
# 서버의 현재 시간을 그대로 사용하지 않고 KST를 사용합니다.
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
    같은 날짜를 1시간 안에 다시 요청하면
    API를 다시 호출하지 않고 저장된 결과를 사용합니다.
    """

    # Streamlit Secrets에서 API 인증키를 가져옵니다.
    # 실제 인증키를 코드에 직접 작성하지 않습니다.
    api_key = st.secrets.get("KOBIS_KEY")

    if not api_key:
        return {
            "success": False,
            "error_type": "key",
            "message": "KOBIS_KEY를 찾을 수 없습니다.",
            "data": None
        }

    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

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

        # HTTP 요청 자체가 실패했는지 확인합니다.
        response.raise_for_status()

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
    # 4. KOBIS의 faultInfo 오류 확인
    # -----------------------------------------------------
    # 인증키가 잘못되어도 HTTP 상태코드는 200일 수 있으므로
    # faultInfo가 있는지도 반드시 확인합니다.
    fault_info = result.get("faultInfo")

    if fault_info:
        fault_code = fault_info.get("errorCode", "")
        fault_message = fault_info.get("message", "알 수 없는 오류")

        return {
            "success": False,
            "error_type": "fault",
            "message": f"{fault_message} (오류 코드: {fault_code})",
            "data": None
        }

    # boxOfficeResult가 없는 경우도 확인합니다.
    boxoffice_result = result.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "error_type": "empty",
            "message": "boxOfficeResult가 없습니다.",
            "data": None
        }

    # 영화 목록을 가져옵니다.
    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "error_type": "empty",
            "message": "해당 날짜의 영화 목록이 없습니다.",
            "data": None
        }

    return {
        "success": True,
        "error_type": None,
        "message": "",
        "data": movie_list
    }


# ---------------------------------------------------------
# 5. API 호출
# ---------------------------------------------------------
result = get_boxoffice(target_date)


# ---------------------------------------------------------
# 6. 오류가 발생했을 때 안내
# ---------------------------------------------------------
if not result["success"]:

    if result["error_type"] == "key":
        st.error("🔑 KOBIS 인증키를 찾을 수 없습니다.")
        st.markdown("""
        **확인할 것**
        1. Streamlit Cloud의 **Settings → Secrets**에 들어갑니다.
        2. 아래와 같이 `KOBIS_KEY`가 등록되어 있는지 확인합니다.
        3. 인증키 앞뒤에 불필요한 따옴표나 공백이 없는지도 확인합니다.

        ```toml
        KOBIS_KEY = "발급받은_인증키"
        ```
        """)

    elif result["error_type"] == "fault":
        st.error("🚨 KOBIS API에서 오류를 반환했습니다.")
        st.write(f"오류 내용: {result['message']}")
        st.markdown("""
        **확인할 것**
        - KOBIS 인증키가 정확한지 확인하세요.
        - KOBIS Open API의 사용 가능 상태인지 확인하세요.
        - API 요청 주소와 날짜 형식이 올바른지 확인하세요.
        """)

    elif result["error_type"] == "request":
        st.error("🌐 KOBIS API에 연결하지 못했습니다.")
        st.write(f"요청 오류: {result['message']}")
        st.markdown("""
        **확인할 것**
        - 인터넷 연결 상태를 확인하세요.
        - KOBIS 서버가 정상적으로 동작하는지 확인하세요.
        - 잠시 후 다시 실행해 보세요.
        """)

    elif result["error_type"] == "json":
        st.error("📄 KOBIS API의 응답을 읽지 못했습니다.")
        st.markdown("""
        **확인할 것**
        - KOBIS API가 정상적으로 응답하고 있는지 확인하세요.
        - API 요청 주소가 정확한지 확인하세요.
        """)

    else:
        st.warning("📭 해당 날짜의 박스오피스 영화 목록이 없습니다.")
        st.markdown("""
        **확인할 것**
        - 조회 날짜에 실제 영화관 박스오피스 집계가 있었는지 확인하세요.
        - KOBIS API가 해당 날짜의 데이터를 제공하는지 확인하세요.
        - 잠시 후 다시 실행해 보세요.
        """)

    # 오류가 있으면 아래의 그래프나 표는 만들지 않습니다.
    st.stop()


# ---------------------------------------------------------
# 7. 데이터를 표 형태로 변환
# ---------------------------------------------------------
movie_list = result["data"]
df = pd.DataFrame(movie_list)


# ---------------------------------------------------------
# 8. 숫자 데이터를 숫자형으로 변환
# ---------------------------------------------------------
# KOBIS에서는 숫자도 문자열로 보내므로
# 그래프와 정렬에 사용할 수 있도록 숫자로 변환합니다.
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
# 9. 순위를 기준으로 정렬
# ---------------------------------------------------------
df = df.sort_values("rank").reset_index(drop=True)


# ---------------------------------------------------------
# 10. 조회 날짜 표시
# ---------------------------------------------------------
st.subheader(f"📅 {display_date} 박스오피스")

st.caption(
    "※ 데이터는 KOBIS 영화관입장권통합전산망 일별 박스오피스 기준입니다."
)


# ---------------------------------------------------------
# 11. 1위 영화 지표 카드
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
# 12. 전체 박스오피스 표
# ---------------------------------------------------------
st.subheader("🎥 전체 박스오피스")

# 사용자에게 보여줄 열만 선택합니다.
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

# 표에서 보기 편하도록 열 이름을 한국어로 변경합니다.
table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]

# 관객수와 누적관객, 스크린수에 천 단위 쉼표를 표시합니다.
display_df = table_df.copy()

for column in ["관객수", "누적관객", "스크린수"]:
    display_df[column] = display_df[column].map(
        lambda x: f"{x:,}"
    )

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# ---------------------------------------------------------
# 13. 관객수 상위 5편 막대그래프
# ---------------------------------------------------------
st.subheader("📊 관객수 상위 5편")

# 관객수가 많은 순서로 정렬한 뒤 5편만 선택합니다.
top5 = (
    df.sort_values("audiCnt", ascending=False)
    .head(5)
    .copy()
)

# 영화명을 인덱스로 설정합니다.
chart_df = top5.set_index("movieNm")[["audiCnt"]]

# Streamlit의 기본 막대그래프를 사용합니다.
st.bar_chart(
    chart_df,
    y="audiCnt",
    x_label="영화",
    y_label="관객수"
)
