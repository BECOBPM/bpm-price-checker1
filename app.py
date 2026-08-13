import streamlit as st
import pandas as pd
import numpy as np
import re
import io
import requests
import urllib.parse

# ==========================================
# 1. 페이지 기본 설정
# ==========================================
st.set_page_config(page_title="BECO BPM - 부산환경공단", layout="wide")

# ==========================================
# 2. Custom CSS
# ==========================================
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


# ==========================================
# 3. 데이터 로드 함수 (GitHub Raw URL 연동)
# ==========================================
GITHUB_USER = "BECOBPM"
REPO_NAME = "bpm-price-checker1"
BRANCH = "main"

FILE_MASTER = "2025년 자재원본.xlsx"
FILE_PRICE_INDEX = "종합물가정보 2026년 08월호-기계.xlsx"

# 한글 및 공백 파일명 URL 인코딩 처리
url_master_filename = urllib.parse.quote(FILE_MASTER)
url_price_filename = urllib.parse.quote(FILE_PRICE_INDEX)

GITHUB_MASTER_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/{BRANCH}/{url_master_filename}"
GITHUB_PRICE_INDEX_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/{BRANCH}/{url_price_filename}"


@st.cache_data(ttl=3600)  # 1시간 캐시 갱신
def load_data_from_github(url):
    """GitHub Raw URL에서 엑셀 파일 로드"""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        df = pd.read_excel(io.BytesIO(response.content))
        return df
    except Exception as e:
        st.error(f"❌ GitHub 데이터 로드 실패: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_default_history():
    """GitHub 기반 사내 자재 입고 이력 DB 로드"""
    df = load_data_from_github(GITHUB_MASTER_URL)
    
    if not df.empty and '입고단가' in df.columns and '수량' in df.columns:
        df['입고단가'] = pd.to_numeric(df['입고단가'], errors='coerce').fillna(0)
        df['수량'] = pd.to_numeric(df['수량'], errors='coerce').fillna(0)
        df['총구매금액'] = df['입고단가'] * df['수량']
    return df


@st.cache_data(ttl=3600)
def load_default_price_index():
    """GitHub 기반 물가지/추천단가 DB 로드"""
    df = load_data_from_github(GITHUB_PRICE_INDEX_URL)
    
    if not df.empty and '추천단가' in df.columns:
        df['추천단가'] = pd.to_numeric(df['추천단가'], errors='coerce').fillna(0)
    return df


# ==========================================
# 4. 검색 및 일괄 검토 엔진
# ==========================================
def search_materials(df, query):
    """자재명 또는 규격 통합 검색"""
    if not query or not query.strip():
        return df
    tokens = query.strip().lower().split()
    
    combined_target = (
        df['자재명'].astype(str) + " " + 
        df['자재규격'].astype(str) + " " + 
        df.get('분류', pd.Series(['']*len(df))).astype(str)
    ).str.lower()
    
    mask = pd.Series(True, index=df.index)
    for token in tokens:
        mask &= combined_target.str.contains(re.escape(token), regex=True, na=False)
    return df[mask]

def batch_process_quote(quote_df, ref_df, col_name, col_spec, col_qty, col_price):
    """8,000+ 대용량 견적 데이터 고속 대조/분석 엔진"""
    df_work = quote_df.copy()
    
    df_work[col_qty] = pd.to_numeric(df_work[col_qty], errors='coerce').fillna(0)
    df_work[col_price] = pd.to_numeric(df_work[col_price], errors='coerce').fillna(0)
    
    df_work['_match_key'] = df_work[col_name].astype(str).str.strip().str.lower() + "_" + df_work[col_spec].astype(str).str.strip().str.lower()
    
    if ref_df is not None and not ref_df.empty:
        ref_temp = ref_df.copy()
        ref_name_col = '품목명' if '품목명' in ref_temp.columns else ref_temp.columns[0]
        ref_spec_col = '규격' if '규격' in ref_temp.columns else ref_temp.columns[1]
        ref_price_col = '추천단가' if '추천단가' in ref_temp.columns else ref_temp.columns[2]
        
        ref_temp['_match_key'] = ref_temp[ref_name_col].astype(str).str.strip().str.lower() + "_" + ref_temp[ref_spec_col].astype(str).str.strip().str.lower()
        ref_temp = ref_temp.drop_duplicates(subset=['_match_key'])
        
        merged = pd.merge(df_work, ref_temp[['_match_key', ref_price_col]], on='_match_key', how='left')
        merged['추천단가'] = merged[ref_price_col]
    else:
        merged = df_work
        merged['추천단가'] = np.nan
        
    merged['추천단가_최종'] = merged['추천단가'].fillna(merged[col_price])
    merged['견적합계'] = merged[col_qty] * merged[col_price]
    merged['추천합계'] = merged[col_qty] * merged['추천단가_최종']
    
    merged['단가차율(%)'] = np.where(
        merged['추천단가_최종'] > 0,
        ((merged[col_price] - merged['추천단가_최종']) / merged['추천단가_최종'] * 100).round(1),
        0.0
    )
    
    merged['예상절감액'] = np.where(
        merged['견적합계'] > merged['추천합계'],
        merged['견적합계'] - merged['추천합계'],
        0
    )
    
    def assign_status(row):
        if pd.isna(row['추천단가']):
            return "⚪ 기준미확인"
        diff = row['단가차율(%)']
        if diff <= 0:
            return "🟢 적정"
        elif diff <= 10:
            return "🟡 검토필요 (+10% 이내)"
        else:
            return "🔴 단가초과 (+10% 초과)"
            
    merged['판정'] = merged.apply(assign_status, axis=1)
    
    merged = merged.drop(columns=['_match_key', '추천단가'], errors='ignore')
    merged = merged.rename(columns={'추천단가_최종': '추천단가'})
    
    return merged


# ==========================================
# 5. 사이드바 구성
# ==========================================
with st.sidebar:
    st.title("🥬 BECO BPM 메뉴")
    st.caption("기능 및 데이터베이스 선택")
    
    selected_menu = st.radio(
        "메뉴 선택",
        [
            "🔍 단 품목 단가 검증", 
            "📈 자재 데이터 요약 (TOP 50)",
            "📊 자재 데이터 분석", 
            "📄 업체 견적서 일괄 검토 (대용량)"
        ],
        index=0,
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("### 📁 커스텀 DB 업로드 (선택)")
    st.caption("GitHub 데이터 대신 로컬 엑셀을 업로드하여 테스트할 수 있습니다.")
    
    custom_master_file = st.file_uploader("사내 자재 DB (.xlsx)", type=["xlsx", "xls"], key="master_db")
    custom_ref_file = st.file_uploader("물가지/추천단가 DB (.xlsx)", type=["xlsx", "xls"], key="ref_db")
    
    st.markdown("---")
    st.markdown("### ⭐ 다빈도 구매 자재")
    top30_options = ["선택 안함", "스텐 배관 파이프", "배관용 플랜지", "볼베어링"]
    quick_selected = st.selectbox("빠른 선택", top30_options, label_visibility="collapsed")


# 데이터 로드 (업로드 파일 우선, 없으면 GitHub 연동)
if custom_master_file:
    df_history = pd.read_excel(custom_master_file)
    if '입고단가' in df_history.columns and '수량' in df_history.columns:
        df_history['총구매금액'] = pd.to_numeric(df_history['입고단가'], errors='coerce').fillna(0) * pd.to_numeric(df_history['수량'], errors='coerce').fillna(0)
else:
    df_history = load_default_history()

if custom_ref_file:
    df_mulga = pd.read_excel(custom_ref_file)
else:
    df_mulga = load_default_price_index()


# ==========================================
# 6. 메인 화면 헤더
# ==========================================
st.markdown("""
    <div class="top-header-banner">
        <h1>🌿 부산환경공단 BPM (Beco Parts Master)</h1>
        <p>자재 수불 이력 기반 공정·투명 계약지원 시스템 | 8,000+ 대용량 자재 견적 일괄 심사</p>
    </div>
""", unsafe_allow_html=True)


# ==========================================
# [메뉴 1] 단 품목 단가 검증
# ==========================================
if selected_menu == "🔍 단 품목 단가 검증":
    default_search_val = "" if quick_selected == "선택 안함" else quick_selected
    
    col_search, col_select = st.columns([1, 1])
    with col_search:
        search_input = st.text_input("🔍 자재명 또는 규격 검색", value=default_search_val, placeholder="예: 배관, 스텐 파이프, 베어링")
    
    filtered_df = search_materials(df_history, search_input)
    
    if not filtered_df.empty and '자재명' in filtered_df.columns and '자재규격' in filtered_df.columns:
        unique_items = filtered_df[['자재명', '자재규격']].drop_duplicates()
    else:
        unique_items = pd.DataFrame()
    
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
        
        min_price = item_records['입고단가'].min()
        max_price = item_records['입고단가'].max()
        avg_price = item_records['입고단가'].mean()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("사내 구매 이력", f"{len(item_records)} 건")
        c2.metric("사내 평균 단가", f"{int(avg_price):,} 원")
        c3.metric("과거 최저 단가", f"{int(min_price):,} 원")
        c4.metric("과거 최고 단가", f"{int(max_price):,} 원")
        
        st.markdown("---")
        st.markdown("#### 📜 사내 과거 납품 상세 이력")
        
        display_cols = [col for col in ['입고일자', '수량', '입고단가', '총구매금액'] if col in item_records.columns]
        display_df = item_records[display_cols].sort_values(by=display_cols[0], ascending=False) if display_cols else item_records
        st.dataframe(
            display_df.style.format({'입고단가': '{:,} 원', '수량': '{:,} 개', '총구매금액': '{:,} 원'}),
            use_container_width=True,
            hide_index=True
        )


# ==========================================
# [메뉴 2] 📈 자재 데이터 요약 (TOP 50)
# ==========================================
elif selected_menu == "📈 자재 데이터 요약 (TOP 50)":
    st.subheader("📈 부산환경공단 자재 데이터 요약 (TOP 50)")
    st.write("사내 입고 이력을 바탕으로 최다 구매 자재 순위를 집계 및 분석합니다.")
    
    category_filter = st.radio("🏷️ 분야 선택", ["전체", "⚙️ 기계", "⚡ 전기", "🌿 환경"], horizontal=True)
    
    filtered_summary_df = df_history.copy()
    if category_filter != "전체" and '분류' in filtered_summary_df.columns:
        cat_name = category_filter.replace("⚙️ ", "").replace("⚡ ", "").replace("🌿 ", "")
        filtered_summary_df = filtered_summary_df[filtered_summary_df['분류'] == cat_name]
    
    group_cols = [c for c in ['분류', '자재명', '자재규격'] if c in filtered_summary_df.columns]
    
    if group_cols and '총구매금액' in filtered_summary_df.columns:
        grouped_df = filtered_summary_df.groupby(group_cols).agg(
            총구매금액=('총구매금액', 'sum'),
            총구매수량=('수량', 'sum'),
            구매건수=('입고단가', 'count'),
            평균입고단가=('입고단가', 'mean')
        ).reset_index()
        
        top50_df = grouped_df.sort_values(by='총구매금액', ascending=False).head(50)
        top50_df.insert(0, '순위', range(1, len(top50_df) + 1))
        
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        col_stat1.metric("분석 대상 자재 종류", f"{len(top50_df)} 개 품목")
        col_stat2.metric("총 집계 구매금액", f"{int(top50_df['총구매금액'].sum()):,} 원")
        col_stat3.metric("총 집계 구매건수", f"{int(top50_df['구매건수'].sum()):,} 건")
        
        st.markdown("---")
        st.markdown("#### 📊 구매금액 상위 품목 TOP 10")
        if not top50_df.empty and '자재명' in top50_df.columns:
            top10_chart_data = top50_df.head(10).set_index('자재명')[['총구매금액']]
            st.bar_chart(top10_chart_data)
        
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
    else:
        st.warning("데이터에 필수 컬럼('총구매금액', '자재명' 등)이 포함되어 있지 않습니다.")


# ==========================================
# [메뉴 3] 📊 자재 데이터 분석
# ==========================================
elif selected_menu == "📊 자재 데이터 분석":
    st.subheader("📊 자재 데이터 분석")
    st.write("선택 품목의 단가 변동 추이 및 수량 분포를 분석합니다.")
    
    if not df_history.empty and '자재명' in df_history.columns and '자재규격' in df_history.columns:
        all_item_list = (df_history['자재명'].astype(str) + " | " + df_history['자재규격'].astype(str)).unique()
        selected_item_for_chart = st.selectbox("🎯 분석할 품목 선택", all_item_list)
        
        if selected_item_for_chart:
            item_name, item_spec = selected_item_for_chart.split(" | ")
            chart_df = df_history[(df_history['자재명'] == item_name) & (df_history['자재규격'] == item_spec)]
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("##### 📈 입고일자별 단가 변동 추이")
                if '입고일자' in chart_df.columns and not chart_df.empty:
                    time_chart = chart_df.sort_values('입고일자').set_index('입고일자')[['입고단가']]
                    st.line_chart(time_chart)
            with c2:
                st.markdown("##### 📦 입고 건별 수량 분포")
                if '수량' in chart_df.columns and not chart_df.empty:
                    st.bar_chart(chart_df['수량'])
    else:
        st.warning("분석할 사내 자재 데이터가 없습니다.")


# ==========================================
# [메뉴 4] 📄 업체 견적서 일괄 검토 (대용량)
# ==========================================
elif selected_menu == "📄 업체 견적서 일괄 검토 (대용량)":
    st.subheader("📄 업체 견적서 일괄 검토 (8,000+ 품목 대용량 지원)")
    st.write("업체에서 제출한 엑셀 견적서를 업로드하면 **전체 품목을 GitHub 기준 물가지 DB와 자동 매칭하여 추천단가 및 적정성을 일괄 산정**합니다.")
    
    uploaded_quote = st.file_uploader("📁 업체 제출 견적서 엑셀 파일 (.xlsx, .xls)", type=["xlsx", "xls"], key="quote_uploader")
    
    if uploaded_quote:
        try:
            quote_raw_df = pd.read_excel(uploaded_quote)
            st.success(f"✅ 견적서 파일 업로드 완료: **{uploaded_quote.name}** (총 {len(quote_raw_df):,}개 품목 감지됨)")
            
            st.markdown("---")
            st.markdown("#### ⚙️ 엑셀 컬럼 매핑 설정")
            
            cols = list(quote_raw_df.columns)
            
            def find_col(keywords, default_idx=0):
                for idx, c in enumerate(cols):
                    if any(k in str(c).lower() for k in keywords):
                        return idx
                return min(default_idx, len(cols) - 1)
            
            mc1, mc2, mc3, mc4 = st.columns(4)
            with mc1:
                c_name = st.selectbox("품목명(자재명) 컬럼", cols, index=find_col(['품목', '자재', '품명', 'item', 'name'], 0))
            with mc2:
                c_spec = st.selectbox("규격 컬럼", cols, index=find_col(['규격', 'spec', 'size'], 1 if len(cols)>1 else 0))
            with mc3:
                c_qty = st.selectbox("수량 컬럼", cols, index=find_col(['수량', 'qty', 'count'], 2 if len(cols)>2 else 0))
            with mc4:
                c_price = st.selectbox("견적단가 컬럼", cols, index=find_col(['단가', '견적', 'price', 'cost'], 3 if len(cols)>3 else 0))
            
            if st.button("🚀 전체 품목 추천단가 일괄 검토 실행"):
                with st.spinner(f"8,000+ 대용량 데이터 고속 검토 중... ({len(quote_raw_df):,}건)"):
                    processed_df = batch_process_quote(quote_raw_df, df_mulga, c_name, c_spec, c_qty, c_price)
                
                total_items = len(processed_df)
                total_quote_amt = processed_df['견적합계'].sum()
                total_rec_amt = processed_df['추천합계'].sum()
                total_savings = processed_df['예상절감액'].sum()
                
                over_price_cnt = len(processed_df[processed_df['판정'].str.contains('🔴', na=False)])
                check_req_cnt = len(processed_df[processed_df['판정'].str.contains('🟡', na=False)])
                
                st.markdown("---")
                st.markdown("### 📊 일괄 검토 결과 요약")
                
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("검토 품목 수", f"{total_items:,} 건")
                s2.metric("총 견적 금액", f"{int(total_quote_amt):,} 원")
                s3.metric("추천 기준 총액", f"{int(total_rec_amt):,} 원")
                s4.metric("총 예상 절감액", f"{int(total_savings):,} 원", delta=f"초과 {over_price_cnt}건 / 주의 {check_req_cnt}건")
                
                st.markdown("---")
                st.markdown("#### 📋 상세 검토 및 추천단가 내역")
                
                filter_status = st.radio(
                    "판정 필터", 
                    ["전체 보기", "🔴 단가초과만 보기", "🟡 검토필요만 보기", "🟢 적정만 보기", "⚪ 기준미확인만 보기"], 
                    horizontal=True
                )
                
                display_result_df = processed_df.copy()
                if "🔴" in filter_status:
                    display_result_df = display_result_df[display_result_df['판정'].str.contains('🔴', na=False)]
                elif "🟡" in filter_status:
                    display_result_df = display_result_df[display_result_df['판정'].str.contains('🟡', na=False)]
                elif "🟢" in filter_status:
                    display_result_df = display_result_df[display_result_df['판정'].str.contains('🟢', na=False)]
                elif "⚪" in filter_status:
                    display_result_df = display_result_df[display_result_df['판정'].str.contains('⚪', na=False)]
                
                show_cols = [c_name, c_spec, c_qty, c_price, '추천단가', '견적합계', '추천합계', '단가차율(%)', '판정', '예상절감액']
                final_table = display_result_df[[c for c in show_cols if c in display_result_df.columns]]
                
                st.dataframe(
                    final_table.style.format({
                        c_qty: '{:,}',
                        c_price: '{:,} 원',
                        '추천단가': '{:,.0f} 원',
                        '견적합계': '{:,} 원',
                        '추천합계': '{:,.0f} 원',
                        '단가차율(%)': '{:+.1f}%',
                        '예상절감액': '{:,} 원'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    processed_df.to_excel(writer, index=False, sheet_name='견적검토결과')
                
                st.download_button(
                    label="📥 검토 완료 결과 엑셀 파일 다운로드",
                    data=buffer.getvalue(),
                    file_name=f"BECO_견적검토결과_{uploaded_quote.name}",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
        except Exception as e:
            st.error(f"파일을 읽는 도중 오류가 발생했습니다: {e}")