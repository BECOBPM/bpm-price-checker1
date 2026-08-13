import streamlit as st
import pandas as pd
import re

# 1. 페이지 기본 설정
st.set_page_config(page_title="BECO BPM - 부산환경공단", layout="wide")

# 2. CSS 스타일링 (상단 여백 최소화 및 깔끔한 배너/사이드바)
st.markdown("""
    <style>
        /* 메인 컨테이너 패딩 조절 */
        .block-container {
            padding-top: 1.2rem !important;
            padding-bottom: 2rem !important;
            max-width: 98% !important;
        }
        /* 상단 헤더 배너 */
        .top-header-banner {
            background: linear-gradient(135deg, #0e5a36 0%, #1a73e8 100%);
            color: white;
            padding: 20px 28px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }
        .top-header-banner h1 {
            color: white !important;
            margin: 0;
            font-size: 1.65rem;
            font-weight: 700;
        }
        .top-header-banner p {
            color: #e0e0e0;
            margin: 5px 0 0 0;
            font-size: 0.9rem;
        }
        /* 사이드바 스타일 개선 */
        section[data-testid="stSidebar"] {
            background-color: #f8f9fa;
        }
    </style>
""", unsafe_allow_html=True)


# --- [데이터 로드 예시] ---
@st.cache_data
def load_sample_data():
    # 사내 자재 이력 DB 샘플
    data = [
        {"자재명": "볼베어링", "자재규격": "6304zz", "입고단가": 3190},
        {"자재명": "볼베어링", "자재규격": "6302zz", "입고단가": 2850},
        {"자재명": "스텐볼밸브", "자재규격": "15A 나사식", "입고단가": 3850},
        {"자재명": "고분자응집제", "자재규격": "중앙이온(액상)", "입고단가": 125000},
    ]
    return pd.DataFrame(data)

@st.cache_data
def load_price_index_data():
    # 물가지(물가자료/거래가격) DB 샘플
    price_data = [
        {"품목명": "볼베어링", "규격": "6302ZZ", "추천단가": 2700, "출처": "물가자료 2026.04"},
        {"품목명": "볼베어링", "규격": "6304ZZ", "추천단가": 3100, "출처": "거래가격 2026.04"},
        {"품목명": "스텐볼밸브", "규격": "15A 나사식", "추천단가": 3800, "출처": "거래가격 2026.04"},
        {"품목명": "고분자응집제", "규격": "중앙이온", "추천단가": 120000, "출처": "물가자료 2026.04"},
    ]
    return pd.DataFrame(price_data)

df_history = load_sample_data()
df_mulga = load_price_index_data()


# --- [핵심 로직 1] 공백 기반 다중 키워드 검색 (AND 조건) ---
def search_materials(df, query):
    if not query or not query.strip():
        return df
    
    tokens = query.strip().lower().split()
    combined_target = (df['자재명'].astype(str) + " " + df['자재규격'].astype(str)).str.lower()
    
    mask = pd.Series(True, index=df.index)
    for token in tokens:
        mask &= combined_target.str.contains(re.escape(token), regex=True, na=False)
        
    return df[mask]


# --- [핵심 로직 2] 물가지 자동 탐색 및 매칭 ---
def find_reference_price(df_mulga, item_name, item_spec):
    if df_mulga is None or df_mulga.empty:
        return None
    
    spec_clean = re.sub(r'[^a-zA-Z0-9]', '', str(item_spec)).lower()
    spec_nums = re.findall(r'\d+', str(item_spec))
    
    matched_rows = []
    for _, row in df_mulga.iterrows():
        m_name = str(row['품목명']).lower()
        m_spec = str(row['규격']).lower()
        m_spec_clean = re.sub(r'[^a-zA-Z0-9]', '', m_spec)
        
        name_match = (str(item_name).lower() in m_name) or (m_name in str(item_name).lower())
        spec_match = (spec_clean in m_spec_clean) or (m_spec_clean in spec_clean)
        
        if not spec_match and spec_nums:
            spec_match = any(num in m_spec for num in spec_nums)
            
        if name_match and spec_match:
            matched_rows.append(row)
            
    if matched_rows:
        return pd.DataFrame(matched_rows)
    return None


# ==========================================
# 3. 사이드바 (BECO BPM 메뉴 복원)
# ==========================================
with st.sidebar:
    st.title("🥬 BECO BPM 메뉴")
    st.caption("기능을 선택하세요")
    
    # 메뉴 선택 라디오 버튼
    selected_menu = st.radio(
        "메뉴 선택",
        ["🔍 단 품목 단가 검증", "📄 업체 견적서 일괄 검토", "📊 자재 데이터 분석"],
        index=0,
        label_visibility="collapsed"
    )
    
    st.caption("DB 기준: 자재 실시간 입고이력")
    st.markdown("---")
    
    # 다빈도 구매 자재 TOP 30 선택
    st.markdown("### ⭐ 다빈도 구매 자재 (TOP 30)")
    st.caption("목록에서 빠른 선택")
    
    top30_options = [
        "선택 안함",
        "고분자응집제 | 중앙이온(액상)",
        "볼베어링 | 6304zz",
        "볼베어링 | 6302zz",
        "스텐볼밸브 | 15A 나사식"
    ]
    quick_selected = st.selectbox("TOP 30 목록", top30_options, label_visibility="collapsed")


# ==========================================
# 4. 메인 화면 구성
# ==========================================

# 상단 배너
st.markdown("""
    <div class="top-header-banner">
        <h1>🌿 부산환경공단 BPM (Beco Parts Master)</h1>
        <p>자재 수불 이력 기반 공정·투명 계약지원 시스템 | 기술개발 및 단가심사 자동화</p>
    </div>
""", unsafe_allow_html=True)

# [메뉴 1] 단 품목 단가 검증 선택 시
if selected_menu == "🔍 단 품목 단가 검증":
    
    # TOP 30 선택 시 검색어 자동 입력 처리
    default_search_val = ""
    if quick_selected != "선택 안함":
        default_search_val = quick_selected.replace(" | ", " ")
    
    col_search, col_select = st.columns([1, 1])
    
    with col_search:
        search_input = st.text_input("🔍 자재명 또는 규격 검색", value=default_search_val, placeholder="예: 베어링 6302")
    
    # 검색어로 데이터 필터링
    filtered_df = search_materials(df_history, search_input)
    
    with col_select:
        if not filtered_df.empty:
            options = [f"{row['자재명']} | {row['자재규격']}" for _, row in filtered_df.iterrows()]
            selected_option = st.selectbox(f"검색 결과 ({len(filtered_df)}건)", options)
            
            selected_index = options.index(selected_option)
            selected_item = filtered_df.iloc[selected_index]
        else:
            st.selectbox("검색 결과 (0건)", ["검색 결과가 없습니다"])
            selected_item = None

    # 선택 품목 상세 정보 및 물가지 대조
    if selected_item is not None:
        st.markdown(f"### 📦 선택 품목: **[{selected_item['자재명']}]** `({selected_item['자재규격']})`")
        
        # 사내 과거 구매 단가 지표
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("사내 구매 이력", "1 건")
        c2.metric("사내 평균 단가", f"{selected_item['입고단가']:,} 원")
        c3.metric("과거 최저 단가", f"{selected_item['입고단가']:,} 원")
        c4.metric("과거 최고 단가", f"{selected_item['입고단가']:,} 원")
        
        st.markdown("---")
        st.markdown("### 💡 참조 물가지 자동 탐색 및 추천 단가")
        
        # 물가지 데이터베이스 매칭 수행
        ref_result = find_reference_price(df_mulga, selected_item['자재명'], selected_item['자재규격'])
        
        if ref_result is not None and not ref_result.empty:
            for _, ref in ref_result.iterrows():
                st.success(f"✅ **[물가지 매칭 성공]** 추천 단가: **{ref['추천단가']:,} 원** (출처: {ref['출처']} / 규격: {ref['규격']})")
        else:
            st.info("⭕ 참조 물가지에서 일치하는 자동 추천 단가가 없습니다. 직접 입력해 주세요.")

elif selected_menu == "📄 업체 견적서 일괄 검토":
    st.subheader("📄 업체 견적서 일괄 검토")
    st.info("업체에서 제출한 엑셀 견적서를 업로드하여 사내 이력 및 물가지와 일괄 대조하는 화면입니다.")

elif selected_menu == "📊 자재 데이터 분석":
    st.subheader("📊 자재 데이터 분석")
    st.info("주요 자재별 단가 변동 추이 및 구매 패턴을 분석하는 화면입니다.")