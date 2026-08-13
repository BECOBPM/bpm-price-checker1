import streamlit as st
import pandas as pd
import re

# 1. 페이지 기본 설정 (와이드 레이아웃)
st.set_page_config(page_title="BECO BPM", layout="wide")

# 2. 상단 여백 제거 및 헤더 템플릿 CSS
st.markdown("""
    <style>
        /* 메인 컨테이너 상단 여백 최소화 */
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
            max-width: 98% !important;
        }
        /* 상단 헤더 배너 스타일 */
        .top-header-banner {
            background: linear-gradient(135deg, #0e5a36 0%, #1a73e8 100%);
            color: white;
            padding: 22px 30px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }
        .top-header-banner h1 {
            color: white !important;
            margin: 0;
            font-size: 1.75rem;
            font-weight: 700;
        }
        .top-header-banner p {
            color: #e0e0e0;
            margin: 6px 0 0 0;
            font-size: 0.92rem;
        }
    </style>
""", unsafe_allow_html=True)

# 3. 상단 배너 출력
st.markdown("""
    <div class="top-header-banner">
        <h1>🌿 부산환경공단 BPM (Beco Parts Master)</h1>
        <p>자재 수불 이력 기반 공정·투명 계약지원 시스템 | 기술개발 및 단가심사 자동화</p>
    </div>
""", unsafe_allow_html=True)


# --- [데이터 로드 예시] ---
@st.cache_data
def load_sample_data():
    # 사내 자재 이력 샘플 데이터
    data = [
        {"자재명": "볼베어링", "자재규격": "6304zz", "입고단가": 3190},
        {"자재명": "볼베어링", "자재규격": "6302zz", "입고단가": 2850},
        {"자재명": "스텐볼밸브", "자재규격": "15A 나사식", "입고단가": 3850},
    ]
    return pd.DataFrame(data)

@st.cache_data
def load_price_index_data():
    # 물가지(물가자료/거래가격) DB 샘플 데이터
    # 실제 환경에서는 pd.read_excel("물가지_데이터.xlsx")로 읽어오시면 됩니다.
    price_data = [
        {"품목명": "볼베어링", "규격": "6302ZZ", "추천단가": 2700, "출처": "물가자료 2026.04"},
        {"품목명": "볼베어링", "규격": "6304ZZ", "추천단가": 3100, "출처": "거래가격 2026.04"},
        {"품목명": "스텐볼밸브", "규격": "15A 나사식", "추천단가": 3800, "출처": "거래가격 2026.04"},
    ]
    return pd.DataFrame(price_data)

df_history = load_sample_data()
df_mulga = load_price_index_data()


# --- [기능 1] '베어링 6302' 다중 키워드 검색 함수 ---
def search_materials(df, query):
    if not query or not query.strip():
        return df
    
    # 입력 검색어를 띄어쓰기 기준으로 분리 (예: ["베어링", "6302"])
    tokens = query.strip().lower().split()
    
    # 자재명 + 자재규격을 하나의 검색 대상 문자열로 결합
    combined_target = (df['자재명'].astype(str) + " " + df['자재규격'].astype(str)).str.lower()
    
    # 모든 키워드가 포함되었는지 검사 (AND 조건)
    mask = pd.Series(True, index=df.index)
    for token in tokens:
        mask &= combined_target.str.contains(re.escape(token), regex=True, na=False)
        
    return df[mask]


# --- [기능 2] 참조 물가지 자동 탐색 매칭 함수 ---
def find_reference_price(df_mulga, item_name, item_spec):
    if df_mulga is None or df_mulga.empty:
        return None
    
    # 규격에서 핵심 숫자/알파벳 추출 (예: 6304zz -> 6304)
    spec_clean = re.sub(r'[^a-zA-Z0-9]', '', str(item_spec)).lower()
    spec_nums = re.findall(r'\d+', str(item_spec))
    
    matched_rows = []
    for _, row in df_mulga.iterrows():
        m_name = str(row['품목명']).lower()
        m_spec = str(row['규격']).lower()
        m_spec_clean = re.sub(r'[^a-zA-Z0-9]', '', m_spec)
        
        # 품목명이 포함되거나 유사하고, 규격 내 핵심 숫자가 일치하는 경우
        name_match = (str(item_name).lower() in m_name) or (m_name in str(item_name).lower())
        spec_match = (spec_clean in m_spec_clean) or (m_spec_clean in spec_clean)
        
        if not spec_match and spec_nums:
            # 숫자로 지정된 규격(예: 6302) 대조
            spec_match = any(num in m_spec for num in spec_nums)
            
        if name_match and spec_match:
            matched_rows.append(row)
            
    if matched_rows:
        return pd.DataFrame(matched_rows)
    return None


# --- UI 구성 ---
col_search, col_select = st.columns([1, 1])

with col_search:
    search_input = st.text_input("🔍 자재명 또는 규격 검색", value="베어링 6302")

# 다중 키워드 필터링 적용
filtered_df = search_materials(df_history, search_input)

with col_select:
    if not filtered_df.empty:
        options = [f"{row['자재명']} | {row['자재규격']}" for _, row in filtered_df.iterrows()]
        selected_option = st.selectbox(f"검색 결과 ({len(filtered_df)}건)", options)
        
        # 선택된 자재 정보 추출
        selected_index = options.index(selected_option)
        selected_item = filtered_df.iloc[selected_index]
    else:
        st.selectbox("검색 결과 (0건)", ["검색 결과가 없습니다"])
        selected_item = None

# 선택 품목 상세 카드 및 물가지 연동
if selected_item is not None:
    st.markdown(f"### 📦 선택 품목: **[{selected_item['자재명']}]** `({selected_item['자재규격']})`")
    
    # 단가 통계 지표
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("사내 구매 이력", "1 건")
    c2.metric("사내 평균 단가", f"{selected_item['입고단가']:,} 원")
    c3.metric("과거 최저 단가", f"{selected_item['입고단가']:,} 원")
    c4.metric("과거 최고 단가", f"{selected_item['입고단가']:,} 원")
    
    st.markdown("---")
    st.markdown("### 💡 참조 물가지 자동 탐색 및 추천 단가")
    
    # 물가지 매칭 실행
    ref_result = find_reference_price(df_mulga, selected_item['자재명'], selected_item['자재규격'])
    
    if ref_result is not None and not ref_result.empty:
        for _, ref in ref_result.iterrows():
            st.success(f"✅ **[물가지 매칭 성공]** 추천 단가: **{ref['추천단가']:,} 원** (출처: {ref['출처']} / 규격: {ref['규격']})")
    else:
        st.info("⭕ 참조 물가지에서 일치하는 자동 추천 단가가 없습니다. 직접 입력해 주세요.")