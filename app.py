import streamlit as st
import pandas as pd
import io
import re

try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

st.set_page_config(page_title="BPM 자재 단가 검증 시스템 (2025~2026년 데이터 기준)", layout="wide", page_icon="⚙️")

@st.cache_data
def load_bpm_data():
    # 2025~2026년 최신 자재 수불 원본 데이터 로드 (header=2 지정)
    df = pd.read_excel('2025년 자재원본.xlsx', sheet_name='Data', header=2)
    
    # 입고단가가 존재하는 유효 데이터만 필터링
    df = df[df['입고단가'].notnull() & (df['입고단가'] > 0)]
    
    # 그룹별 절사평균(5건 이상 시 최상위 1개, 최하위 1개 제외) 계산
    def calc_trimmed_stats(g):
        prices = g['입고단가'].dropna().tolist()
        prices.sort()
        n = len(prices)
        
        if n == 0:
            return pd.Series({'이력건수': 0, '평균단가': 0, '최소단가': 0, '최대단가': 0, '절사적용': False})
        
        min_p = prices[0]
        max_p = prices[-1]
        
        # 5건 이상일 경우 최고/최저 각 1개씩 제외 후 평균 계산 (심사 방식)
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
    # 📌 사이드바: 메뉴 선택
    # ----------------------------------------------------
    st.sidebar.title("📌 메뉴 선택")
    page = st.sidebar.radio(
        "원하는 기능을 선택하세요", 
        ["🔍 단 품목 단가 검증", "📄 업체 견적서 일괄 검토", "📊 자재 데이터 분석"]
    )
    st.sidebar.caption("💡 DB 기준: 2025~2026년 자재 수불 이력")
    st.sidebar.markdown("---")

    # ====================================================
    # 🌟 PAGE 1: 단 품목 단가 검증
    # ====================================================
    if page == "🔍 단 품목 단가 검증":
        st.sidebar.title("⭐ 자주 산 자재 (TOP 30)")
        top30_df = stats_df.sort_values(by='이력건수', ascending=False).head(30)
        selected_from_sidebar = st.sidebar.selectbox("목록에서 바로 선택", top30_df['검색용'].tolist())

        st.sidebar.markdown("---")
        with st.sidebar.expander("📁 물가자료 PDF/Excel 첨부 (선택)", expanded=False):
            uploaded_files = st.file_uploader(
                "물가지 파일 첨부",
                type=['pdf', 'xlsx', 'xls'],
                accept_multiple_files=True
            )

        st.title("⚙️ BPM 자재 단가 검증 시스템 (2025~2026년 데이터 기준)")
        
        c_search1, c_search2 = st.columns([1.5, 1.5])
        with c_search1:
            search_kw = st.text_input("🔍 자재명 / 규격 키워드 검색", "", placeholder="예: 구리스, 고분자, 밸브, 50A").strip()
        
        with c_search2:
            if search_kw:
                search_filtered = stats_df[stats_df['검색용'].str.contains(search_kw, case=False, na=False)]
                if len(search_filtered) > 0:
                    selected_item = st.selectbox(f"검색결과 ({len(search_filtered)}건) 중 선택", search_filtered['검색용'].tolist())
                else:
                    st.warning("일치하는 자재가 없습니다. TOP 30 선택 품목으로 표시합니다.")
                    selected_item = selected_from_sidebar
            else:
                selected_item = selected_from_sidebar
                st.selectbox("선택된 자재 (TOP 30 연동)", [selected_item], disabled=True)

        target_data = stats_df[stats_df['검색용'] == selected_item].iloc[0]
        selected_material = target_data['자재명']
        selected_spec = target_data['자재규격']
        bpm_count = int(target_data['이력건수'])
        bpm_avg = int(target_data['평균단가'])
        bpm_max = int(target_data['최대단가'])
        bpm_min = int(target_data['최소단가'])
        is_trimmed = bool(target_data['절사적용'])

        st.divider()
        st.subheader(f"📌 선택 자재: [{selected_material}] ({selected_spec})")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("사내 구매 이력", f"{bpm_count:,} 건")
        
        if is_trimmed:
            m2.metric("사내 평균 단가 (절사평균)", f"{bpm_avg:,.0f} 원", help="구매이력 5건 이상: 최고가 1개, 최저가 1개를 제외한 평균값입니다.")
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

        col_input, col_result = st.columns([1, 1.2])
        with col_input:
            st.markdown("### 💳 단가 입력")
            price_gov = st.number_input("📑 물가자료 공인 단가 (원)", min_value=0, value=auto_price_price, step=1000)
            price_quote = st.number_input("💵 구매/견적 예정 단가 (원)", min_value=0, value=bpm_avg, step=1000)

        with col_result:
            st.markdown("### 🎯 적정성 판정 결과")
            if price_quote == 0:
                st.info("견적 단가를 입력해 주세요.")
            else:
                diff_bpm = price_quote - bpm_avg
                rate_bpm = (diff_bpm / bpm_avg) * 100
                
                if price_quote <= bpm_avg:
                    st.success(f"🟢 **[사내 이력]** 평균가({bpm_avg:,.0f}원) 대비 **{abs(rate_bpm):.1f}% 저렴 (적정)**")
                elif price_quote <= bpm_max:
                    st.warning(f"🟡 **[사내 이력]** 평균가 대비 **{rate_bpm:.1f}% 높음** (과거 최고가 {bpm_max:,.0f}원 이내)")
                else:
                    st.error(f"🔴 **[사내 이력]** 과거 최고가({bpm_max:,.0f}원) 초과 **(고가 주의)**")

                if price_gov > 0:
                    diff_gov = price_quote - price_gov
                    rate_gov = (diff_gov / price_gov) * 100
                    if price_quote <= price_gov:
                        st.success(f"🟢 **[물가자료]** 공인가({price_gov:,.0f}원) 대비 **{abs(rate_gov):.1f}% 저렴 (적정)**")
                    else:
                        st.error(f"🔴 **[물가자료]** 공인가({price_gov:,.0f}원) 대비 **{rate_gov:.1f}% 비쌈**")

        st.divider()

        st.subheader("📊 단가 데이터 종합 비교")
        comp_data = {
            "구분": ["사내 최저가", f"사내 평균가 ({bpm_count}건)", "사내 최고가", "물가자료 단가", "구매 견적가"],
            "단가 (원)": [bpm_min, bpm_avg, bpm_max, price_gov, price_quote]
        }

        comp_df = pd.DataFrame(comp_data)
        tbl_col, chart_col = st.columns([1, 1])
        with tbl_col:
            st.table(comp_df.assign(단가=comp_df["단가 (원)"].apply(lambda x: f"{x:,.0f}원"))[["구분", "단가"]])
        with chart_col:
            st.bar_chart(comp_df[comp_df["단가 (원)"] > 0].set_index("구분"))

    # ====================================================
    # 📄 PAGE 2: 업체 견적서 일괄 검토
    # ====================================================
    elif page == "📄 업체 견적서 일괄 검토":
        st.title("📄 업체 제출 견적서 일괄 검토 (2025~2026년 데이터 기준)")
        st.caption("업체에서 제출한 엑셀 견적서를 업로드하면, 사내 단가 DB와 자동으로 비교하여 적정성을 일괄 심사합니다.")
        st.divider()

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
            label="📥 견적서 업로드 양식(샘플 Excel) 다운로드",
            data=buffer.getvalue(),
            file_name="견적서_업로드_양식.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.markdown("<br>", unsafe_allow_html=True)

        quote_file = st.file_uploader("업체 견적서 엑셀 파일(.xlsx)을 첨부해 주세요", type=['xlsx', 'xls'])

        if quote_file:
            try:
                q_df = pd.read_excel(quote_file)
                
                required_cols = ['자재명', '자재규격', '수량', '견적단가']
                if not all(col in q_df.columns for col in required_cols):
                    st.error("엑셀 파일에 '자재명', '자재규격', '수량', '견적단가' 열이 포함되어 있어야 합니다.")
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

                    st.subheader("📋 견적 검토 총괄 요약")
                    
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

                    st.subheader("🔍 품목별 상세 검토 결과")
                    
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
                        file_name="BPM_견적검토_결과보고서.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

            except Exception as e:
                st.error(f"견적서 처리 중 오류가 발생했습니다: {e}")

    # ====================================================
    # 📈 PAGE 3: 자재 데이터 분석
    # ====================================================
    else:
        st.title("📊 사내 자재 데이터 종합 분석 (2025~2026년 데이터 기준)")
        st.caption("누적된 2025~2026년도 자재 구매 이력을 바탕으로 자주 구매하는 자재와 단가 형성 추이를 분석합니다.")
        st.divider()

        a_col1, a_col2 = st.columns(2)
        with a_col1:
            st.metric("총 등록 자재 품목 수", f"{len(stats_df):,} 개")
        with a_col2:
            high_vol_count = len(stats_df[stats_df['이력건수'] >= 5])
            st.metric("주요 관리 자재 (5건 이상 구매)", f"{high_vol_count:,} 개")

        st.subheader("🔥 최다 구매 자재 TOP 20")
        top_analysis = stats_df.sort_values(by='이력건수', ascending=False).head(20)
        st.dataframe(
            top_analysis[['자재명', '자재규격', '이력건수', '평균단가', '최소단가', '최대단가']],
            use_container_width=True
        )

        st.subheader("💡 연간 단가계약 추천 품목 (구매건수 10건 이상)")
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