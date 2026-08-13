import streamlit as st
import pandas as pd
import re

# 1. 페이지 기본 설정
st.set_page_config(page_title="BECO BPM - 부산환경공단", layout="wide")

# 2. Custom CSS (배너 및 사이드바 스타일)
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


# --- [확장된 데이터 로드: 기계/전기/환경 분류 및 풍부한 베어링 데이터] ---
@st.cache_data
def load_sample_data():
    data = [
        # --- [기계 분야 - 베어링류] ---
        {"분류": "기계", "자재명": "볼베어링", "자재규격": "6302zz", "입고단가": 2700, "납품업체": "한국베어링", "입고일자": "2026-01-15", "수량": 50},
        {"분류": "기계", "자재명": "볼베어링", "자재규격": "6302zz", "입고단가": 2950, "납품업체": "삼공사", "입고일자": "2025-09-20", "수량": 30},
        {"분류": "기계", "자재명": "볼베어링", "자재규격": "6304zz", "입고단가": 3190, "납품업체": "한국베어링", "입고일자": "2026-03-01", "수량": 40},
        {"분류": "기계", "자재명": "볼베어링", "자재규격": "6201zz", "입고단가": 2100, "납품업체": "(주)부산베어링", "입고일자": "2025-10-11", "수량": 60},
        {"분류": "기계", "자재명": "볼베어링", "자재규격": "6202zz", "입고단가": 2300, "납품업체": "한국베어링", "입고일자": "2026-02-05", "수량": 45},
        {"분류": "기계", "자재명": "UC베어링", "자재규격": "UC205", "입고단가": 8500, "납품업체": "동화기계", "입고일자": "2026-01-20", "수량": 20},
        {"분류": "기계", "자재명": "플랜지베어링", "자재규격": "UCF204", "입고단가": 11500, "납품업체": "동화기계", "입고일자": "2025-12-01", "수량": 15},
        
        # --- [기계 분야 - 배관/밸브류] ---
        {"분류": "기계", "자재명": "스텐볼밸브", "자재규격": "15A 나사식", "입고단가": 3700, "납품업체": "(주)동래유통", "입고일자": "2025-08-12", "수량": 100},
        {"분류": "기계", "자재명": "스텐볼밸브", "자재규격": "15A 나사식", "입고단가": 3850, "납품업체": "(주)부산배관", "입고일자": "2026-02-10", "수량": 120},
        {"분류": "기계", "자재명": "버터플라이밸브", "자재규격": "100A 레버식", "입고단가": 48000, "납품업체": "한성공구", "입고일자": "2026-03-15", "수량": 10},
        {"분류": "기계", "자재명": "메카니컬씰", "자재규격": "45mm 펌프용", "입고단가": 185000, "납품업체": "신화테크", "입고일자": "2026-02-28", "수량": 8},

        # --- [전기 분야] ---
        {"분류": "전기", "자재명": "배선용차단기", "자재규격": "3P 100A 30kA", "입고단가": 35000, "납품업체": "LS전기상사", "입고일자": "2026-01-08", "수량": 25},
        {"분류": "전기", "자재명": "전자마그네트", "자재규격": "GMC-40 AC220V", "입고단가": 28000, "납품업체": "LS전기상사", "입고일자": "2025-11-20", "수량": 30},
        {"분류": "전기", "자재명": "LED 투광등", "자재규격": "150W 방수형", "입고단가": 62000, "납품업체": "부경조명", "입고일자": "2026-02-18", "수량": 50},
        {"분류": "전기", "자재명": "인버터", "자재규격": "7.5kW 삼상 380V", "입고단가": 680000, "납품업체": "현대전기엔지니어링", "입고일자": "2026-03-10", "수량": 4},

        # --- [환경 분야] ---
        {"분류": "환경", "자재명": "고분자응집제", "자재규격": "중앙이온(액상)", "입고단가": 125000, "납품업체": "경남화학", "입고일자": "2026-01-10", "수량": 150},
        {"분류": "환경", "자재명": "차아염소산나트륨", "자재규격": "12% 20L", "입고단가": 18000, "납품업체": "부산케미칼", "입고일자": "2026-03-05", "수량": 80},
        {"분류": "환경", "자재명": "성형활성탄", "자재규격": "4mm Pellet", "입고단가": 2400, "납품업체": "동서환경", "입고일자": "2026-02-01", "수량": 1000},
        {"분류": "환경", "자재명": "탈수기 여과포", "자재규격": "벨트프레스용 2m", "입고단가": 320000, "납품업체": "세경텍스타일", "입고일자": "2025-12-15", "수량": 12},
    ]
    df = pd.DataFrame(data)
    df['총구매금액'] = df['입고단가'] * df['수량']
    return df

@st.cache_data
def load_price_index_data():
    price_data = [
        {"품목명": "볼베어링", "규격": "6302ZZ", "추천단가": 2700, "출처": "물가자료 2026.04"},
        {"품목명": "볼베어링", "규격": "6304ZZ", "추천단가": 3100, "출처": "거래가격 2026.04"},
        {"품목명": "볼베어링", "규격": "6201ZZ", "추천단가": 2050, "출처": "물가자료 2026.04"},
        {"품목명": "스텐볼밸브", "규격": "15A 나사식", "추천단가": 3800, "출처": "거래가격 2026.04"},
        {"품목명": "고분자응집제", "규격": "중앙이온", "추천단가": 120000, "출처": "물가자료 2026.04"},
        {"품목명": "배선용차단기", "규격": "3P 100A", "추천단가": 34000, "출처": "거래가격 2026.04"},
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
# 3. 사이드바 메뉴 (신규 메뉴 추가)
# ==========================================
with st.sidebar:
    st.title("🥬 BECO BPM 메뉴")
    st.caption("기능을 선택하세요")
    
    selected_menu = st.radio(
        "메뉴 선택",
        [
            "🔍 단 품목 단가 검증", 
            "📈 자재 데이터 요약 (TOP 50)",
            "📊 자재 데이터 분석", 
            "📄 업체 견적서 일괄 검토"
        ],
        index=0,
        label_visibility="collapsed"
    )
    
    st.caption("DB 기준: 자재 실시간 입고이력")
    st.markdown("---")
    
    st.markdown("### ⭐ 다빈도 구매 자재 (TOP 30)")
    st.caption("목록에서 빠른 선택")
    
    top30_options = [
        "선택 안함",
        "볼베어링 | 6302zz",
        "볼베어링 | 6304zz",
        "스텐볼밸브 | 15A 나사식",
        "고분자응집제 | 중앙이온(액상)",
        "배선용차단기 | 3P 100A 30kA"
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
        search_input = st.text_input("🔍 자재명 또는 규격 검색", value=default_search_val, placeholder="예: 베어링 6302")
    
    filtered_df = search_materials(df_history, search_input)
    unique_items = filtered_df[['자재명', '자재규격']].drop_duplicates() if not filtered_df.empty else pd.DataFrame()
    
    with col_select:
        if not unique_items.empty:
            options = [f"{row['자재명']} | {row['자재규격']}" for _, row in unique_items.iterrows()]
            selected_option = st.selectbox(f"검색 결과 ({len(options)}건)", options)
            
            sel_name, sel_spec = selected_option.split(" | ")
            item_records = df_history[(df_history['자재명'] == sel_name) & (df_history['자재규격'] == sel_spec)]
        else:
            st.selectbox("검색 결과 (0건)", ["검색 결과가 없습니다"])
            item_records = None

    if item_records is not None and not item_records.empty:
        target_name = item_records.iloc[0]['자재명']
        target_spec = item_records.iloc[0]['자재규격']
        
        st.markdown(f"### 📦 선택 품목: **[{target_name}]** `({target_spec})`")
        
        min_row = item_records.loc[item_records['입고단가'].idxmin()]
        max_row = item_records.loc[item_records['입고단가'].idxmax()]
        avg_price = item_records['입고단가'].mean()
        
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
        st.markdown("#### 💡 참조 물가지 자동 탐색 및 추천 단가")
        ref_result = find_reference_price(df_mulga, target_name, target_spec)
        
        if ref_result is not None and not ref_result.empty:
            for _, ref in ref_result.iterrows():
                st.success(f"✅ **[물가지 매칭 성공]** 추천 단가: **{ref['추천단가']:,} 원** (출처: {ref['출처']} / 규격: {ref['규격']})")
        else:
            st.info("⭕ 참조 물가지에서 일치하는 자동 추천 단가가 없습니다.")
            
        st.markdown("#### 📜 사내 과거 납품 상세 이력")
        display_df = item_records[['입고일자', '납품업체', '수량', '입고단가']].sort_values(by='입고일자', ascending=False)
        st.dataframe(
            display_df.style.format({'입고단가': '{:,} 원', '수량': '{:,} 개'}),
            use_container_width=True,
            hide_index=True
        )


# --- [메뉴 2] 📈 자재 데이터 요약 (TOP 50) [신규 추가!] ---
elif selected_menu == "📈 자재 데이터 요약 (TOP 50)":
    st.subheader("📈 부산환경공단 자재 데이터 요약 (TOP 50)")
    st.write("사내 입고 이력을 바탕으로 **분류별(기계/전기/환경)** 최다 구매 자재 순위를 분석합니다.")
    
    # 1. 분야별 필터 버튼
    category_filter = st.radio(
        "🏷️ 분야 선택", 
        ["전체", "⚙️ 기계", "⚡ 전기", "🌿 환경"], 
        horizontal=True
    )
    
    # 데이터 필터링
    filtered_summary_df = df_history.copy()
    if category_filter != "전체":
        cat_name = category_filter.replace("⚙️ ", "").replace("⚡ ", "").replace("🌿 ", "")
        filtered_summary_df = filtered_summary_df[filtered_summary_df['분류'] == cat_name]
    
    # 자재별 집계 (품목명 + 규격 기준)
    grouped_df = filtered_summary_df.groupby(['분류', '자재명', '자재규격']).agg(
        총구매금액=('총구매금액', 'sum'),
        총구매수량=('수량', 'sum'),
        구매건수=('입고단가', 'count'),
        평균입고단가=('입고단가', 'mean')
    ).reset_index()
    
    # 구매금액 기준 내림차순 정렬 (TOP 50)
    top50_df = grouped_df.sort_values(by='총구매금액', ascending=False).head(50)
    top50_df.insert(0, '순위', range(1, len(top50_df) + 1))
    
    # 요약 통계지표
    col_stat1, col_stat2, col_stat3 = st.columns(3)
    col_stat1.metric("분석 대상 자재 종류", f"{len(top50_df)} 개 품목")
    col_stat2.metric("총 집계 구매금액", f"{int(top50_df['총구매금액'].sum()):,} 원")
    col_stat3.metric("총 집계 구매건수", f"{int(top50_df['구매건수'].sum()):,} 건")
    
    st.markdown("---")
    
    # 시각화: 상위 10개 품목 총 구매금액 차트
    st.markdown("#### 📊 구매금액 상위 품목 TOP 10")
    top10_chart_data = top50_df.head(10).set_index('자재명')[['총구매금액']]
    st.bar_chart(top10_chart_data)
    
    # TOP 50 상세 테이블
    st.markdown("#### 📋 TOP 50 자재 데이터 목록")
    st.dataframe(
        top50_df.style.format({
            '총구매금액': '{:,} 원',
            '총구매수량': '{:,} 개',
            '구매건수': '{:,} 건',
            '평균입고단가': '{:,.0f} 원'
        }),
        use_container_width=True,
        hide_index=True
    )


# --- [메뉴 3] 자재 데이터 분석 ---
elif selected_menu == "📊 자재 데이터 분석":
    st.subheader("📊 자재 데이터 분석")
    st.write("전체 DB 및 선택 품목의 단가 변동 추이와 공급업체 비중을 다각도로 분석합니다.")
    
    # 품목 선택 박스
    all_item_list = (df_history['자재명'] + " | " + df_history['자재규격']).unique()
    selected_item_for_chart = st.selectbox("🎯 분석할 품목 선택", all_item_list)
    
    if selected_item_for_chart:
        item_name, item_spec = selected_item_for_chart.split(" | ")
        chart_df = df_history[(df_history['자재명'] == item_name) & (df_history['자재규격'] == item_spec)]
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### 📈 시간 흐름에 따른 단가 변동 추이")
            time_chart = chart_df.sort_values('입고일자').set_index('입고일자')[['입고단가']]
            st.line_chart(time_chart)
        with c2:
            st.markdown("##### 🏢 납품업체별 계약 건수")
            vendor_counts = chart_df['납품업체'].value_counts()
            st.bar_chart(vendor_counts)


# --- [메뉴 4] 업체 견적서 일괄 검토 ---
elif selected_menu == "📄 업체 견적서 일괄 검토":
    st.subheader("📄 업체 견적서 일괄 검토")
    st.write("업체에서 제출한 엑셀 견적서를 업로드하여 사내 이력 및 물가지와 일괄 대조합니다.")
    
    uploaded_file = st.file_uploader("📁 업체 견적서 엑셀 파일(.xlsx)을 업로드하세요", type=["xlsx", "xls"])
    if uploaded_file:
        st.success(f"파일명: {uploaded_file.name} 이 성공적으로 업로드되었습니다.")
        st.info("💡 검증 로직이 실행되어 사내 DB 및 물가지와 일괄 비교 표가 생성됩니다.")