import streamlit as st
import pandas as pd
import re

try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

st.set_page_config(page_title="자재 단가 & 물가자료 통합 비교 시스템", layout="wide")

# 1. 사내 엑셀 데이터 로드 함수
@st.cache_data
def load_bpm_data():
    df = pd.read_excel('BPM 자재 금액대 형성_자재_규격검색기능.xlsx', sheet_name='Data')
    stats = df.groupby(['자재명', '자재규격'])['입고단가'].agg(
        이력건수='count',
        평균단가='mean',
        최소단가='min',
        최대단가='max'
    ).reset_index()
    stats['평균단가'] = stats['평균단가'].round(0)
    stats['검색용'] = stats['자재명'].astype(str) + " | " + stats['자재규격'].astype(str)
    return stats

# 2. PDF 내 실시간 단가 추출 함수
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

# ----------------------------------------------------
# 📌 왼쪽 사이드바: 목차 (Table of Contents) 구성
# ----------------------------------------------------
st.sidebar.title("📋 시스템 목차")
st.sidebar.markdown("---")

nav_choice = st.sidebar.radio(
    "이동할 화면을 선택하세요:",
    [
        "🖥️ 전체 통합 대시보드",
        "🔍 1. 자재 검색 및 이력 조회",
        "💳 2. 단가 입력 및 3중 비교 판정",
        "📊 3. 종합 비교표 및 그래프",
        "📁 4. 물가자료 PDF 관리"
    ]
)

st.sidebar.markdown("---")
st.sidebar.caption("💡 **BPM 자재 시스템 v2.0**")
st.sidebar.caption("사내 거래가 + 물가자료 + 견적가 3중 검증")

try:
    stats_df = load_bpm_data()

    st.title("📦 사내 이력 & 물가자료 통합 비교 판정 시스템")
    st.caption("사내 거래가 + 구매 이력 건수 + 물가자료 단가 + 견적 단가를 한 화면에서 교차 분석합니다.")

    # ----------------------------------------------------
    # 상단 물가자료 파일 업로드 접이식 섹션
    # ----------------------------------------------------
    with st.expander("📁 [클릭] 한국물가정보 / 물가자료 PDF·엑셀 파일 등록 및 관리", expanded=False):
        uploaded_files = st.file_uploader(
            "공인 물가지 PDF 또는 엑셀 파일들을 선택해 주세요 (다중 선택 가능)",
            type=['pdf', 'xlsx', 'xls'],
            accept_multiple_files=True
        )
        if uploaded_files:
            st.success(f"총 {len(uploaded_files)}개의 물가자료 파일이 성공적으로 등록되었습니다.")
        else:
            st.info("파일을 등록하시면 자재 검색 시 물가자료 단가가 자동으로 추출되어 매칭됩니다.")

    st.divider()

    # 데이터 변수 초기화
    search_keyword = "구리스"
    filtered_df = stats_df

    # ----------------------------------------------------
    # 화면 1: 자재 검색 및 단가 입력 세션
    # ----------------------------------------------------
    if nav_choice in ["🖥️ 전체 통합 대시보드", "🔍 1. 자재 검색 및 이력 조회", "💳 2. 단가 입력 및 3중 비교 판정"]:
        c1, c2, c3 = st.columns([1.2, 1, 1.2])

        with c1:
            st.subheader("1. 대상 자재 검색")
            search_keyword = st.text_input("🔍 자재명/규격 키워드", "구리스").strip()
            
            filtered_df = stats_df[stats_df['검색용'].str.contains(search_keyword, case=False, na=False)] if search_keyword else stats_df

            if len(filtered_df) == 0:
                st.error("❌ 해당 검색어의 사내 자재가 없습니다.")
                st.stop()
                
            selected_item = st.selectbox("자재 선택", filtered_df['검색용'].tolist())
            target_data = filtered_df[filtered_df['검색용'] == selected_item].iloc[0]
            
            selected_material = target_data['자재명']
            selected_spec = target_data['자재규격']
            bpm_count = int(target_data['이력건수'])
            bpm_avg = int(target_data['평균단가'])
            bpm_max = int(target_data['최대단가'])
            bpm_min = int(target_data['최소단가'])

            st.info(f"📊 **[{selected_material}]** 의 사내 구매 이력: 총 **{bpm_count:,}건**")

        # PDF/엑셀 자동 검색 단가 파싱
        auto_price_price = 0
        if 'uploaded_files' in locals() and uploaded_files:
            pdf_hits = []
            for f in uploaded_files:
                if f.name.lower().endswith('.pdf') and HAS_PDF:
                    pdf_hits.extend(search_in_pdf(f, selected_material))
            
            if pdf_hits and pdf_hits[0]['단가후보']:
                auto_price_price = pdf_hits[0]['단가후보'][0]

        with c2:
            st.subheader("2. 단가 정보 입력")
            price_gov = st.number_input(
                "📑 물가자료 공인 단가 (원)", 
                min_value=0, 
                value=auto_price_price, 
                step=1000,
                help="PDF 등 물가자료 책자에 표기된 고시 단가를 입력하거나 자동 매칭된 값입니다."
            )
            
            price_quote = st.number_input(
                "💳 구매/견적 예정 단가 (원)", 
                min_value=0, 
                value=bpm_avg, 
                step=1000,
                help="업체에서 제출받았거나 구매하려는 단가를 입력하세요."
            )

        with c3:
            st.subheader("3. 🎯 통합 단가 비교 판정")
            
            if price_quote == 0:
                st.info("견적 단가를 입력해 주세요.")
            else:
                diff_bpm = price_quote - bpm_avg
                rate_bpm = (diff_bpm / bpm_avg) * 100
                
                st.markdown(f"#### **[사내 거래가 대비 (총 {bpm_count:,}건 이력)]**")
                if price_quote <= bpm_avg:
                    st.success(f"🟢 사내 평균가({bpm_avg:,.0f}원) 대비 **{abs(rate_bpm):.1f}% 저렴/적정**")
                elif price_quote <= bpm_max:
                    st.warning(f"🟡 사내 평균가 대비 **{rate_bpm:.1f}% 높으나**, 과거 최고가({bpm_max:,.0f}원) 이내")
                else:
                    st.error(f"🔴 사내 최고가({bpm_max:,.0f}원)보다 **{rate_bpm:.1f}% 초과 (고가)**")

                st.markdown("#### **[공인 물가자료 대비]**")
                if price_gov == 0:
                    st.caption("⚪ 물가자료 단가를 입력하시면 교차 판정이 표시됩니다.")
                else:
                    diff_gov = price_quote - price_gov
                    rate_gov = (diff_gov / price_gov) * 100
                    if price_quote <= price_gov:
                        st.success(f"🟢 물가자료가({price_gov:,.0f}원) 대비 **{abs(rate_gov):.1f}% 저렴 (적정)**")
                    else:
                        st.error(f"🔴 물가자료가({price_gov:,.0f}원) 대비 **{rate_gov:.1f}% 비쌈**")

    # ----------------------------------------------------
    # 화면 2: 종합 비교표 및 차트
    # ----------------------------------------------------
    if nav_choice in ["🖥️ 전체 통합 대시보드", "📊 3. 종합 비교표 및 그래프"]:
        st.divider()
        st.subheader(f"📊 [{selected_material} - {selected_spec}] 단가 종합 비교표 (사내 구매 이력: 총 {bpm_count:,}건)")
        
        comp_data = {
            "구분": ["사내 최저가", f"사내 평균가 ({bpm_count}건 평균)", "사내 최고가", "물가자료 단가", "구매 견적가"],
            "단가 (원)": [bpm_min, bpm_avg, bpm_max, price_gov, price_quote],
            "견적가 대비 차액": [
                f"{price_quote - bpm_min:+,.0f}원" if price_quote else "-",
                f"{price_quote - bpm_avg:+,.0f}원" if price_quote else "-",
                f"{price_quote - bpm_max:+,.0f}원" if price_quote else "-",
                f"{price_quote - price_gov:+,.0f}원" if (price_quote and price_gov) else "-",
                "기준 (0원)"
            ]
        }
        
        comp_df = pd.DataFrame(comp_data)
        
        col_tbl, col_chart = st.columns([1, 1])
        with col_tbl:
            st.table(comp_df)
        
        with col_chart:
            chart_df = comp_df[comp_df["단가 (원)"] > 0].set_index("구분")
            st.bar_chart(chart_df["단가 (원)"])

    # ----------------------------------------------------
    # 화면 3: PDF 파일 세부 검색 내역
    # ----------------------------------------------------
    if nav_choice in ["🖥️ 전체 통합 대시보드", "📁 4. 물가자료 PDF 관리"]:
        if 'uploaded_files' in locals() and uploaded_files:
            st.divider()
            st.subheader("📑 첨부 파일 내 검색된 물가자료 원본 구절")
            pdf_results = []
            for f in uploaded_files:
                if f.name.lower().endswith('.pdf') and HAS_PDF:
                    res = search_in_pdf(f, selected_material)
                    pdf_results.extend(res)
            if pdf_results:
                st.dataframe(pd.DataFrame(pdf_results), use_container_width=True)
            else:
                st.warning("등록된 물가자료에서 해당 자재와 일치하는 키워드를 찾지 못했습니다.")

except Exception as e:
    st.error(f"실행 중 오류 발생: {e}")