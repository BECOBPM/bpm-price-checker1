import streamlit as st
import pandas as pd
import re

try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

st.set_page_config(page_title="자재 단가 & 물가자료 통합 비교 시스템", layout="wide")

st.title("📦 사내 이력 & 물가자료 통합 비교 판정 시스템")
st.caption("사내 거래가 + 물가자료 단가 + 견적 단가를 한 화면에서 직접 교차 분석합니다.")

# 1. 사내 엑셀 데이터 로드
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

# 2. PDF 내 실시간 단가 추출
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
                                if val > 100: # 단순 페이지수 등 제외
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

    # 사이드바 PDF 업로드
    st.sidebar.header("📁 물가자료/물가정보 첨부")
    uploaded_files = st.sidebar.file_uploader(
        "한국물가정보/물가자료 파일 첨부 (PDF, Excel)",
        type=['pdf', 'xlsx', 'xls'],
        accept_multiple_files=True
    )

    # 메인 레이아웃 (3컬럼 비교)
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
        bpm_avg = int(target_data['평균단가'])
        bpm_max = int(target_data['최대단가'])
        bpm_min = int(target_data['최소단가'])

    # PDF/엑셀 자동 검색 단가 파싱
    auto_price_price = 0
    if uploaded_files:
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
        
        # 3가지 기준 종합 판정 로직
        if price_quote == 0:
            st.info("견적 단가를 입력해 주세요.")
        else:
            diff_bpm = price_quote - bpm_avg
            rate_bpm = (diff_bpm / bpm_avg) * 100
            
            st.markdown("#### **[사내 거래가 대비]**")
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

    st.divider()

    # 4. 한눈에 보는 비교 표 & 그래프
    st.subheader(f"📊 [{selected_material} - {selected_spec}] 단가 종합 비교표")
    
    comp_data = {
        "구분": ["사내 최저가", "사내 평균가", "사내 최고가", "물가자료 단가", "구매 견적가"],
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
        # 막대 그래프로 한눈에 비교
        chart_df = comp_df[comp_df["단가 (원)"] > 0].set_index("구분")
        st.bar_chart(chart_df["단가 (원)"])

    # 하단 물가자료 원본 근거 레퍼런스
    if uploaded_files:
        st.divider()
        st.subheader("📑 첨부 파일 내 검색된 물가자료 원본 구절")
        pdf_results = []
        for f in uploaded_files:
            if f.name.lower().endswith('.pdf') and HAS_PDF:
                res = search_in_pdf(f, selected_material)
                pdf_results.extend(res)
        if pdf_results:
            st.dataframe(pd.DataFrame(pdf_results), use_container_width=True)

except Exception as e:
    st.error(f"실행 중 오류 발생: {e}")