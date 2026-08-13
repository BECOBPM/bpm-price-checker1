import streamlit as st
import pandas as pd
import re

# 1. 페이지 기본 설정
st.set_page_config(page_title="BECO BPM - 부산환경공단", layout="wide")

# 2. Custom CSS (배너 및 레이아웃 개선)
st.markdown("""
    <style>
        .block-container {
            padding-top: 1.2rem !important;
            padding-bottom: 2rem !important;
            max-width: 98% !important;
        }
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
        section[data-testid="stSidebar"] {
            background-color: #f8f9fa;
        }
    </style>
""", unsafe_allow_html=True)


# --- [데이터 로드: 납품업체 및 입고일자 포함] ---
@st.cache_data
def load_sample_data():
    # 같은 자재라도 과거 복수 구매 이력(업체/단가/일자)을 가질 수 있도록 구성
    data = [
        {"자재명": "스텐볼밸브", "자재규격": "15A 나사식", "입고단가": 3700, "납품업체": "(주)동래유통", "입고일자": "2025-08-12", "수량": 10},
        {"자재명": "스텐볼밸브", "자재규격": "15A 나사식", "입고단가": 3850, "납품업체": "(주)부산배관", "입고일자": "2026-02-10", "수량": 15},
        {"자재명": "스텐볼밸브", "자재규격": "15A 나사식", "입고단가": 4200, "납품업체": "한성공구", "입고일자": "2025-11-05", "수량": 5},
        {"자재명": "볼베어링", "자재규격": "6302zz", "입고단가": 2700, "납품업체": "한국베어링", "입고일자": "2026-01-15", "수량": 50},
        {"자재명": "볼베어링", "자재규격": "6302zz", "입고단가": 2950, "납품업체": "삼공사", "입고일자": "2025-09-20", "수량": 30},
        {"자재명": "볼베어링", "자재규격": "6304zz", "입고단가": 3190, "납품업체": "한국베어링", "입고일자": "2026-03-01", "수량": 20},
        {"자재명": "고분자응집제", "자재규격": "중앙이온(액상)", "입고단가": 125000, "납품업체": "경남화학", "입고일자": "2026-01-10", "수량": 2},
    ]
    return pd.DataFrame(data)

@st.cache_data
def load_price_index_data():
    price_data = [
        {"품목명": "볼베어링", "규격": "6302ZZ", "추천단가": 2700, "출처": "물가자료 2026.04"},
        {"품목명": "볼베어링", "규격": "6304ZZ", "추천단가": 3100, "출처": "거래가격 2026.04"},
        {"품목명": "스텐볼밸브", "규격": "15A 나사식", "추천단가": 3800, "출처": "거래가격 2026.04"},
        {"품목명": "고분자응집제", "규격": "중앙이온", "추천단가": 120000, "출처": "물가자료 2026.04"},
    ]
    return pd.DataFrame(price_data)

df_history = load_sample_data()
df_mulga = load_price_index_data()


# --- [검색 및 매칭 로직] ---
def search_materials(df, query):
    if not query or not query.strip():
        return df
    tokens = query.strip().lower().split()
    combined_target = (df['자재명'].astype(str) + " " + df['자재규격'].astype(str)).str.lower()
    
    mask = pd.Series(True, index=df.index)
    for token in tokens:
        mask &= combined_target.str.contains(re.escape(token), regex=True, na=False)
    return df[mask]

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
            
    return pd.DataFrame(matched_rows) if matched_rows else None


# ==========================================
# 3. 사이드바 메뉴
# ==========================================
with st.sidebar:
    st.title("🥬 BECO BPM 메뉴")
    st.caption("기능을 선택하세요")
    
    selected_menu = st.radio(
        "메뉴 선택",
        ["🔍 단 품목 단가 검증", "📄 업체 견적서 일괄 검토", "📊 자재 데이터 분석"],
        index=0,
        label_visibility="collapsed"
    )
    
    st.caption("DB 기준: 자재 실시간 입고이력")
    st.markdown("---")
    
    st.markdown("### ⭐ 다빈도 구매 자재 (TOP 30)")
    st.caption("목록에서 빠른 선택")
    
    top30_options = [
        "선택 안함",
        "스텐볼밸브 | 15A 나사식",
        "볼베어링 | 6302zz",
        "볼베어링 | 6304zz",
        "고분자응집제 | 중앙이온(액상)"
    ]
    quick_selected = st.selectbox("TOP 30 목록", top30_options, label_visibility="collapsed")


# ==========================================
# 4. 메인 화면
# ==========================================
st.markdown("""
    <div class="top-header-banner">
        <h1>🌿 부산환경공단 BPM (Beco Parts Master)</h1>
        <p>자재 수불 이력 기반 공정·투명 계약지원 시스템 | 기술개발 및 단가심사 자동화</p>
    </div>
""", unsafe_allow_html=True)


# --- [메뉴 1] 단 품목 단가 검증 ---
if selected_menu == "🔍 단 품목 단가 검증":
    
    default_search_val = ""
    if quick_selected != "선택 안함":
        default_search_val = quick_selected.replace(" | ", " ")
    
    col_search, col_select = st.columns([1, 1])
    
    with col_search:
        search_input = st.text_input("🔍 자재명 또는 규격 검색", value=default_search_val, placeholder="예: 스텐볼밸브 15A")
    
    filtered_df = search_materials(df_history, search_input)
    
    # 중복 제거된 품목 리스트
    unique_items = filtered_df[['자재명', '자재규격']].drop_duplicates() if not filtered_df.empty else pd.DataFrame()
    
    with col_select:
        if not unique_items.empty:
            options = [f"{row['자재명']} | {row['자재규격']}" for _, row in unique_items.iterrows()]
            selected_option = st.selectbox(f"검색 결과 ({len(options)}건)", options)
            
            sel_name, sel_spec = selected_option.split(" | ")
            # 해당 품목의 모든 구매 이력 추출
            item_records = df_history[(df_history['자재명'] == sel_name) & (df_history['자재규격'] == sel_spec)]
        else:
            st.selectbox("검색 결과 (0건)", ["검색 결과가 없습니다"])
            item_records = None

    # 선택한 품목 정보 및 납품업체 분석 표시
    if item_records is not None and not item_records.empty:
        target_name = item_records.iloc[0]['자재명']
        target_spec = item_records.iloc[0]['자재규격']
        
        st.markdown(f"### 📦 선택 품목: **[{target_name}]** `({target_spec})`")
        
        # 최저가 / 최고가 납품업체 계산
        min_row = item_records.loc[item_records['입고단가'].idxmin()]
        max_row = item_records.loc[item_records['입고단가'].idxmax()]
        avg_price = item_records['입고단가'].mean()
        
        # 지표 카드 (납품업체 정보 추가)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("사내 구매 이력", f"{len(item_records)} 건")
        c2.metric("사내 평균 단가", f"{int(avg_price):,} 원")
        c3.metric(
            "과거 최저 단가", 
            f"{min_row['입고단가']:,} 원", 
            delta=f"최저업체: {min_row['납품업체']}",
            delta_color="normal"
        )
        c4.metric(
            "과거 최고 단가", 
            f"{max_row['입고단가']:,} 원", 
            delta=f"최고업체: {max_row['납품업체']}",
            delta_color="inverse"
        )
        
        st.markdown("---")
        
        # 물가지 추천 단가
        st.markdown("#### 💡 참조 물가지 자동 탐색 및 추천 단가")
        ref_result = find_reference_price(df_mulga, target_name, target_spec)
        
        if ref_result is not None and not ref_result.empty:
            for _, ref in ref_result.iterrows():
                st.success(f"✅ **[물가지 매칭 성공]** 추천 단가: **{ref['추천단가']:,} 원** (출처: {ref['출처']} / 규격: {ref['규격']})")
        else:
            st.info("⭕ 참조 물가지에서 일치하는 자동 추천 단가가 없습니다.")
            
        # 과거 구매 이력 상세 테이블 (납품업체명 포함)
        st.markdown("#### 📜 사내 과거 납품 상세 이력")
        display_df = item_records[['입고일자', '납품업체', '수량', '입고단가']].sort_values(by='입고일자', ascending=False)
        st.dataframe(
            display_df.style.format({'입고단가': '{:,} 원', '수량': '{:,} 개'}),
            use_container_width=True,
            hide_index=True
        )


# --- [메뉴 2] 업체 견적서 일괄 검토 (기능 UI 구현) ---
elif selected_menu == "📄 업체 견적서 일괄 검토":
    st.subheader("📄 업체 견적서 일괄 검토")
    st.write("업체에서 제출한 엑셀 견적서를 업로드하여 사내 이력 및 물가지와 일괄 대조합니다.")
    
    uploaded_file = st.file_uploader("📁 업체 견적서 엑셀 파일(.xlsx)을 업로드하세요", type=["xlsx", "xls"])
    if uploaded_file:
        st.success(f"파일명: {uploaded_file.name} 이 성공적으로 업로드되었습니다.")
        st.info("💡 검증 로직이 실행되어 사내 DB 및 물가지와 일괄 비교 표가 생성됩니다.")


# --- [메뉴 3] 자재 데이터 분석 (기능 UI 구현) ---
elif selected_menu == "📊 자재 데이터 분석":
    st.subheader("📊 자재 데이터 분석")
    st.write("주요 자재별 단가 변동 추이 및 구매 패턴 분석 결과입니다.")
    
    # 간단한 추이 차트 시각화 예시
    chart_data = df_history[['입고일자', '자재명', '입고단가']].copy()
    st.line_chart(data=chart_data, x='입고일자', y='입고단가', color='자재명')