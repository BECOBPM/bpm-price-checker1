import streamlit as st
import pandas as pd
import io
import re

try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

# PAGE CONFIG
st.set_page_config(
    page_title="부산환경공단 자재 단가 검증 시스템", 
    layout="wide", 
    page_icon="🌿",
    initial_sidebar_state="expanded"
)

# ----------------------------------------------------
# 🎨 부산환경공단(BECO) 맞춤형 CSS 스타일링
# ----------------------------------------------------
st.markdown("""
<style>
    /* 메인 배경 및 기본 폰트 설정 */
    .main {
        background-color: #f8f9fa;
    }
    
    /* 공단 상단 헤더 스타일 */
    .beco-header {
        background: linear-gradient(135deg, #0f4c81 0%, #1e88e5 60%, #2e7d32 100%);
        padding: 24px 28px;
        border-radius: 12px;
        color: white;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }
    .beco-header h1 {
        color: #ffffff !important;
        font-size: 26px !important;
        font-weight: 700 !important;
        margin-bottom: 6px !important;
    }
    .beco-header p {
        color: #e0f2fe !important;
        font-size: 14px !important;
        margin: 0 !important;
    }

    /* 카드 컨테이너 스타일 */
    .custom-card {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 20px;
        border: 1px solid #e9ecef;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        margin-bottom: 15px;
    }
    
    /* 강조 파란색 구매견적가 박스 */
    .quote-box {
        background-color: #ebf5ff;
        border-left: 6px solid #1565c0;
        padding: 16px;
        border-radius: 8px;
        margin-top: 10px;
        margin-bottom: 15px;
    }
    .quote-title {
        color: #0d47a1;
        font-weight: 700;
        font-size: 15px;
        margin-bottom: 5px;
    }
    
    /* 버튼 스타일 */
    .stButton>button {
        background-color: #0f4c81;
        color: white;
        border-radius: 6px;
        border: none;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #1565c0;
        color: white;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_bpm_data():
    df = pd.read_excel('2025년 자재원본.xlsx', sheet_name='Data', header=2)
    df = df[df['입고단가'].notnull() & (df['입고단가'] > 0)]
    
    def calc_trimmed_stats(g):
        prices = g['입고단가'].dropna().tolist()
        prices.sort()
        n = len(prices)
        
        if n == 0:
            return pd.Series({'이력건수': 0, '평균단가': 0, '최소단가': 0, '최대단가': 0, '절사적용': False})
        
        min_p = prices[0]
        max_p = prices[-1]
        
        if n >= 5:
            trimmed_prices = prices[1:-1]
            avg_p = sum(trimmed_prices) / len(trimmed_prices)
            is_trimmed = True
        else:
            avg_p = sum(prices) / n
            is_trimmed = False
            
        return pd.Series({
            '이력건수': n,
            '평균단가': round(avg_p),
            '최소단가': min_p,
            '최대단가': max_p,
            '절사적용': is_trimmed
        })

    stats = df.groupby(['자재명', '자재규격'], group_keys=False).apply(calc_trimmed_stats).reset_index()
    stats['검색용'] = stats['자재명'].astype(str) + " | " + stats['자재규격'].astype(str)
    return stats

def search_in_pdf(pdf_file, keyword):
    results = []
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text and keyword.lower() in text.lower():
                    lines = text.split('\n')
                    for line in lines:
                        if keyword.lower() in line.lower():
                            numbers = re.findall(r'\b\d{1,3}(?:,\d{3})+\b|\b\d{4,9}\b', line)
                            clean_nums = []
                            for n in numbers:
                                val = int(n.replace(',', ''))
                                if val > 100:
                                    clean_nums.append(val)
                            results.append({
                                '파일명': pdf_file.name,
                                '페이지': f"{page_num} page",
                                '내용': line.strip(),
                                '단가후보': clean_nums
                            })
    except Exception as e:
        pass
    return results

try:
    stats_df = load_bpm_data()

    # ----------------------------------------------------
    # 🌿 상단 헤더 패널
    # ----------------------------------------------------
    st.markdown("""
    <div class="beco-header">
        <h1>🌿 부산환경공단 (BECO) 자재 단가 검증 시스템</h1>
        <p>자재 수불 이력 기반 공정·투명 계약지원 시스템 | 기술개발 및 단가심사 자동화</p>
    </div>
    """, unsafe_allow_html=True)

    # ----------------------------------------------------
    # 📌 사이드바 메뉴
    # ----------------------------------------------------
    st.sidebar.markdown("## 🌿 BECO 메뉴")
    page = st.sidebar.radio(
        "기능을 선택하세요", 
        ["🔍 단 품목 단가 검증", "📄 업체 견적서 일괄 검토", "📊 자재 데이터 분석"]
    )
    st.sidebar.caption("DB 기준: 자재 실시간 입고이력")
    st.sidebar.markdown("---")

    # ====================================================
    # 🌟 PAGE 1: 단 품목 단가 검증
    # ====================================================
    if page == "🔍 단 품목 단가 검증":
        st.sidebar.markdown("### ⭐ 다빈도 구매 자재 (TOP 30)")
        top30_df = stats_df.sort_values(by='이력건수', ascending=False).head(30)
        selected_from_sidebar = st.sidebar.selectbox("목록에서 빠른 선택", top30_df['검색용'].tolist())

        st.sidebar.markdown("---")
        with st.sidebar.expander("📁 물가자료/정보 PDF·Excel 첨부", expanded=False):
            uploaded_files = st.file_uploader(
                "물가지 파일 첨부",
                type=['pdf', 'xlsx', 'xls'],
                accept_multiple_files=True
            )

        # 검색 영역 카드
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        c_search1, c_search2 = st.columns([1.5, 1.5])
        with c_search1:
            search_kw = st.text_input("🔍 자재명 또는 규격 검색", "", placeholder="예: 볼밸브, 고분자, 가스켓, 50A").strip()
        
        with c_search2:
            if search_kw:
                search_filtered = stats_df[stats_df['검색용'].str.contains(search_kw, case=False, na=False)]
                if len(search_filtered) > 0:
                    selected_item = st.selectbox(f"검색 결과 ({len(search_filtered)}건)", search_filtered['검색용'].tolist())
                else:
                    st.warning("일치하는 자재가 없습니다. TOP 30 항목으로 설정됩니다.")
                    selected_item = selected_from_sidebar
            else:
                selected_item = selected_from_sidebar
                st.selectbox("선택 자재 (TOP 30 연동)", [selected_item], disabled=True)
        st.markdown('</div>', unsafe_allow_html=True)

        target_data = stats_df[stats_df['검색용'] == selected_item].iloc[0]
        selected_material = target_data['자재명']
        selected_spec = target_data['자재규격']
        bpm_count = int(target_data['이력건수'])
        bpm_avg = int(target_data['평균단가'])
        bpm_max = int(target_data['최대단가'])
        bpm_min = int(target_data['최소단가'])
        is_trimmed = bool(target_data['절사적용'])

        st.markdown(f"### 📦 선택 품목: **[{selected_material}]** `({selected_spec})`")
        
        # 사내 이력 메트릭 카드
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("사내 구매 이력", f"{bpm_count:,} 건")
        
        if is_trimmed:
            m2.metric("사내 평균 단가 (절사평균)", f"{bpm_avg:,.0f} 원", help="5건 이상 구매 품목: 최고/최저가 각 1건을 제외한 공정 평균값입니다.")
        else:
            m2.metric("사내 평균 단가", f"{bpm_avg:,.0f} 원")
            
        m3.metric("과거 최저 단가", f"{bpm_min:,.0f} 원")
        m4.metric("과거 최고 단가", f"{bpm_max:,.0f} 원")

        st.markdown("<br>", unsafe_allow_html=True)

        auto_price_price = 0
        if 'uploaded_files' in locals() and uploaded_files:
            pdf_hits = []
            for f in uploaded_files:
                if f.name.lower().endswith('.pdf') and HAS_PDF:
                    pdf_hits.extend(search_in_pdf(f, selected_material))
            if pdf_hits and pdf_hits[0]['단가후보']:
                auto_price_price = pdf_hits[0]['단가후보'][0]

        # 단가 입력 및 적정성 판정 2열 레이아웃
        col_input, col_result = st.columns([1, 1.2])
        
        with col_input:
            st.markdown('<div class="custom-card">', unsafe_allow_html=True)
            st.markdown("#### 💳 비교 단가 입력")
            
            price_info = st.number_input("📑 물가정보 공인 단가 (원)", min_value=0, value=0, step=1000)
            price_data = st.number_input("📑 물가자료 공인 단가 (원)", min_value=0, value=auto_price_price, step=1000)
            
            # 물가자료/정보 미입력 팝업 안내
            if price_info == 0 and price_data == 0:
                st.info("💡 **물가정보 및 물가자료는 검토하셨습니까?** (미입력 상태)")

            # 구매견적가 파란색 강조 UI
            st.markdown("""
            <div class="quote-box">
                <div class="quote-title">🟦 구매 / 견적 예정 단가 (검토 대상)</div>
            </div>
            """, unsafe_allow_html=True)
            price_quote = st.number_input("구매견적가 입력 (원)", min_value=0, value=bpm_avg, step=1000, label_visibility="collapsed")
            st.markdown('</div>', unsafe_allow_html=True)

        with col_result:
            st.markdown('<div class="custom-card">', unsafe_allow_html=True)
            st.markdown("#### 🎯 적정성 종합 판정 결과")
            
            if price_quote == 0:
                st.info("검토할 구매견적 단가를 입력해 주세요.")
            else:
                st.markdown(f"##### 🟦 **검토 구매견적가: <span style='color:#1565C0; font-size:22px;'>{price_quote:,.0f}원</span>**", unsafe_allow_html=True)
                st.markdown("---")
                
                # 1. 사내 이력 비교
                diff_bpm = price_quote - bpm_avg
                rate_bpm = (diff_bpm / bpm_avg) * 100
                
                if price_quote <= bpm_avg:
                    st.success(f"🟢 **[사내 이력 대비]** 평균가({bpm_avg:,.0f}원) 대비 **{abs(rate_bpm):.1f}% 저렴 (적정)**")
                elif price_quote <= bpm_max:
                    st.warning(f"🟡 **[사내 이력 대비]** 평균가 대비 **{rate_bpm:.1f}% 높음** (과거 최고가 {bpm_max:,.0f}원 이내)")
                else:
                    st.error(f"🔴 **[사내 이력 대비]** 과거 최고가({bpm_max:,.0f}원) 초과 **(고가 주의/네고 필요)**")

                # 2. 물가정보 비교
                if price_info > 0:
                    diff_info = price_quote - price_info
                    rate_info = (diff_info / price_info) * 100
                    if price_quote <= price_info:
                        st.success(f"🟢 **[물가정보]** 공인가({price_info:,.0f}원) 대비 **{abs(rate_info):.1f}% 저렴 (적정)**")
                    else:
                        st.error(f"🔴 **[물가정보]** 공인가({price_info:,.0f}원) 대비 **{rate_info:.1f}% 비쌈**")

                # 3. 물가자료 비교
                if price_data > 0:
                    diff_data = price_quote - price_data
                    rate_data = (diff_data / price_data) * 100
                    if price_quote <= price_data:
                        st.success(f"🟢 **[물가자료]** 공인가({price_data:,.0f}원) 대비 **{abs(rate_data):.1f}% 저렴 (적정)**")
                    else:
                        st.error(f"🔴 **[물가자료]** 공인가({price_data:,.0f}원) 대비 **{rate_data:.1f}% 비쌈**")

            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("📊 단가 데이터 종합 비교 차트 및 표")
        
        comp_data = {
            "구분": [
                "사내 최저가", 
                f"사내 평균가 ({bpm_count}건)", 
                "사내 최고가", 
                "물가정보 단가", 
                "물가자료 단가", 
                "🟦 구매견적가 (검토대상)"
            ],
            "단가 (원)": [bpm_min, bpm_avg, bpm_max, price_info, price_data, price_quote]
        }

        comp_df = pd.DataFrame(comp_data)
        tbl_col, chart_col = st.columns([1, 1.2])
        
        with tbl_col:
            disp_df = comp_df.copy()
            disp_df["단가"] = disp_df["단가 (원)"].apply(lambda x: f"{x:,.0f}원" if x > 0 else "미입력")
            st.table(disp_df[["구분", "단가"]])
            
        with chart_col:
            chart_df = comp_df[comp_df["단가 (원)"] > 0].set_index("구분")
            st.bar_chart(chart_df)

    # ====================================================
    # 📄 PAGE 2: 업체 견적서 일괄 검토
    # ====================================================
    elif page == "📄 업체 견적서 일괄 검토":
        st.subheader("📄 업체 제출 견적서 자동 일괄 검토")
        st.caption("업체에서 제출한 엑셀 견적서를 업로드하면, 공단 사내 단가 DB와 비교하여 적정성을 한눈에 검토합니다.")
        st.markdown("<br>", unsafe_allow_html=True)

        sample_df = pd.DataFrame({
            "자재명": ["볼밸브", "고분자응집제", "가스켓"],
            "자재규격": ["50A", "분말", "100A"],
            "수량": [10, 5, 20],
            "견적단가": [45000, 120000, 8000]
        })
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            sample_df.to_excel(writer, index=False, sheet_name='견적서')
        
        st.download_button(
            label="📥 견적서 업로드 양식 (샘플 Excel) 다운로드",
            data=buffer.getvalue(),
            file_name="BECO_견적서_업로드_양식.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.markdown("<br>", unsafe_allow_html=True)

        quote_file = st.file_uploader("업체 제출 견적서(.xlsx) 파일을 첨부하세요", type=['xlsx', 'xls'])

        if quote_file:
            try:
                q_df = pd.read_excel(quote_file)
                
                required_cols = ['자재명', '자재규격', '수량', '견적단가']
                if not all(col in q_df.columns for col in required_cols):
                    st.error("엑셀 파일에 '자재명', '자재규격', '수량', '견적단가' 열이 포함되어야 합니다.")
                else:
                    q_df['수량'] = pd.to_numeric(q_df['수량'], errors='coerce').fillna(0)
                    q_df['견적단가'] = pd.to_numeric(q_df['견적단가'], errors='coerce').fillna(0)
                    q_df['견적금액'] = q_df['수량'] * q_df['견적단가']

                    merged = pd.merge(q_df, stats_df, on=['자재명', '자재규격'], how='left')

                    merged['사내평균단가'] = merged['평균단가'].fillna(0)
                    merged['사내예상금액'] = merged['수량'] * merged['사내평균단가']
                    merged['단가차액'] = merged['견적단가'] - merged['사내평균단가']
                    
                    def judge_row(row):
                        if row['사내평균단가'] == 0:
                            return "⚪ 이력없음"
                        ratio = ((row['견적단가'] - row['사내평균단가']) / row['사내평균단가']) * 100
                        if ratio <= 0:
                            return "🟢 적정"
                        elif ratio <= 10:
                            return "🟡 주의 (+10% 이내)"
                        else:
                            return "🔴 고가 (네고필요)"

                    merged['판정'] = merged.apply(judge_row, axis=1)

                    total_quote = merged['견적금액'].sum()
                    total_expected = merged['사내예상금액'].sum()
                    diff_total = total_quote - total_expected
                    diff_rate = (diff_total / total_expected * 100) if total_expected > 0 else 0

                    st.markdown("#### 📋 견적 검토 총괄 요약")
                    
                    q1, q2, q3, q4 = st.columns(4)
                    q1.metric("업체 제출 총 금액", f"{total_quote:,.0f} 원")
                    q2.metric("사내 이력 기준 금액", f"{total_expected:,.0f} 원")
                    
                    if diff_total > 0:
                        q3.metric("사내 기준 대비 차액", f"+{diff_total:,.0f} 원", delta=f"+{diff_rate:.1f}%", delta_color="inverse")
                    else:
                        q3.metric("사내 기준 대비 차액", f"{diff_total:,.0f} 원", delta=f"{diff_rate:.1f}%")

                    over_items = merged[merged['판정'] == '🔴 고가 (네고필요)']
                    q4.metric("네고 필요 고가 품목", f"{len(over_items)} 건")

                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown("#### 🔍 품목별 상세 검토 결과")
                    
                    show_cols = ['자재명', '자재규격', '수량', '견적단가', '사내평균단가', '견적금액', '사내예상금액', '판정']
                    result_table = merged[show_cols].copy()
                    
                    for col in ['견적단가', '사내평균단가', '견적금액', '사내예상금액']:
                        result_table[col] = result_table[col].apply(lambda x: f"{x:,.0f}원")

                    st.dataframe(result_table, use_container_width=True)

                    out_buffer = io.BytesIO()
                    with pd.ExcelWriter(out_buffer, engine='openpyxl') as writer:
                        merged[show_cols].to_excel(writer, index=False, sheet_name='견적검토결과')
                    
                    st.download_button(
                        label="📥 견적 검토 결과서 (Excel) 다운로드",
                        data=out_buffer.getvalue(),
                        file_name="BECO_견적검토_결과보고서.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

            except Exception as e:
                st.error(f"견적서 처리 중 오류가 발생했습니다: {e}")

    # ====================================================
    # 📈 PAGE 3: 자재 데이터 분석
    # ====================================================
    else:
        st.subheader("📊 사내 자재 현황 및 데이터 분석")
        st.caption("자재 수불 이력을 기반으로 최다 구매 품목과 단가 계약 대상 후보를 분석합니다.")
        st.markdown("<br>", unsafe_allow_html=True)

        a_col1, a_col2 = st.columns(2)
        with a_col1:
            st.metric("총 등록 자재 품목 수", f"{len(stats_df):,} 개")
        with a_col2:
            high_vol_count = len(stats_df[stats_df['이력건수'] >= 5])
            st.metric("주요 관리 대상 품목 (5건 이상 구매)", f"{high_vol_count:,} 개")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 🔥 다빈도 구매 자재 TOP 20")
        top_analysis = stats_df.sort_values(by='이력건수', ascending=False).head(20)
        st.dataframe(
            top_analysis[['자재명', '자재규격', '이력건수', '평균단가', '최소단가', '최대단가']],
            use_container_width=True
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 💡 연간 단가계약 추천 품목 (구매건수 10건 이상)")
        contract_candidates = stats_df[stats_df['이력건수'] >= 10].sort_values(by='이력건수', ascending=False)
        if len(contract_candidates) > 0:
            st.dataframe(
                contract_candidates[['자재명', '자재규격', '이력건수', '평균단가']],
                use_container_width=True
            )
        else:
            st.info("10건 이상 구매된 단가계약 후보 자재가 없습니다.")

except Exception as e:
    st.error(f"시스템 오류 발생: {e}")