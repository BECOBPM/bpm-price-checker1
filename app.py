import streamlit as st
import pandas as pd
import re

try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

# 1. 페이지 설정 (넓게, 타이틀 깔끔하게)
st.set_page_config(page_title="BPM 자재 단가 검증 시스템", layout="wide", page_icon="📈")

# 맞춤형 CSS로 디자인 커스터마이징
st.markdown("""
    <style>
    /* 상단 여백 제거 및 전체 배경색 */
    .block-container {
        padding-top: 1rem;
        background-color: #f8f9fa;
    }
    /* 타이틀 디자인 */
    .stTitle {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        font-weight: 800;
        letter-spacing: -0.05rem;
        margin-bottom: 0.5rem;
    }
    .stCaption {
        margin-bottom: 2rem;
    }
    /* 섹션 제목 디자인 */
    h3 {
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 0.8rem;
    }
    /* 정보 카드 디자인 */
    .info-card {
        background-color: white;
        border-radius: 10px;
        padding: 1rem;
        border: 1px solid #e9ecef;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
    }
    .info-card h4 {
        margin: 0;
        color: #6c757d;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .info-card p {
        margin: 0.2rem 0 0 0;
        font-size: 1.2rem;
        font-weight: 700;
    }
    /* 파일 업로드 Expander 디자인 */
    .stExpander {
        border-radius: 10px;
    }
    /* 표 디자인 최적화 */
    [data-testid="stTable"] {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #e9ecef;
    }
    </style>
""", unsafe_allow_html=True)

# 함수 정의 (이전과 동일)
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
    # 🌟 메인 화면 시작: 타이틀
    # ----------------------------------------------------
    st.title("📈 BPM 자재 단가 검증 대시보드")
    st.caption("사내 거래가 + 물가자료 + 견적가 데이터를 기반으로 구매 단가의 적정성을 다각도로 검증합니다.")

    # ----------------------------------------------------
    # [섹션 0] 물가자료 관리 (Expander)
    # ----------------------------------------------------
    with st.expander("📁 [물가자료 파일 등록] 한국물가정보 / 물가자료 PDF·엑셀 관리", expanded=False):
        uploaded_files = st.file_uploader(
            "공인 물가지 PDF 또는 엑셀 파일들을 선택해 주세요 (다중 선택 가능)",
            type=['pdf', 'xlsx', 'xls'],
            accept_multiple_files=True
        )
        if uploaded_files:
            st.success(f"총 {len(uploaded_files)}개의 물가자료 파일이 성공적으로 등록되었습니다.")

    st.divider()

    # 데이터 변수 초기화
    filtered_df = stats_df

    # ----------------------------------------------------
    # [섹션 1] 자재 검색 (메인 화면 중앙에 배치)
    # ----------------------------------------------------
    c1, _ = st.columns([1, 2])
    with c1:
        st.subheader("1. 대상 자재 검색")
        search_keyword = st.text_input("🔍 자재명 또는 규격 키워드 입력", "구리스").strip()
        
        filtered_df = stats_df[stats_df['검색용'].str.contains(search_keyword, case=False, na=False)] if search_keyword else stats_df

        if len(filtered_df) == 0:
            st.error("❌ 해당 검색어의 사내 자재가 없습니다.")
            st.stop()
            
        selected_item = st.selectbox("검색 결과에서 자재 선택", filtered_df['검색용'].tolist())
        target_data = filtered_df[filtered_df['검색용'] == selected_item].iloc[0]
        
        selected_material = target_data['자재명']
        selected_spec = target_data['자재규격']
        bpm_count = int(target_data['이력건수'])
        bpm_avg = int(target_data['평균단가'])
        bpm_max = int(target_data['최대단가'])
        bpm_min = int(target_data['최소단가'])

    st.divider()

    # ----------------------------------------------------
    # [섹션 2] 핵심 정보 카드 및 단가 입력 (세련된 레이아웃)
    # ----------------------------------------------------
    
    # PDF/엑셀 자동 검색 단가 파싱
    auto_price_price = 0
    if 'uploaded_files' in locals() and uploaded_files:
        pdf_hits = []
        for f in uploaded_files:
            if f.name.lower().endswith('.pdf') and HAS_PDF:
                pdf_hits.extend(search_in_pdf(f, selected_material))
        
        if pdf_hits and pdf_hits[0]['단가후보']:
            auto_price_price = pdf_hits[0]['단가후보'][0]

    # 화면 구성: 정보 카드 / 입력 / 판정
    row1_c1, row1_c2, row1_c3, row1_c4 = st.columns([1.2, 1.2, 1, 1.5])

    with row1_c1:
        st.markdown(f"""
            <div class="info-card">
                <h4>선택된 자재명</h4>
                <p>📊 {selected_material}</p>
            </div>
            <div class="info-card">
                <h4>규격</h4>
                <p>📋 {selected_spec}</p>
            </div>
        """, unsafe_allow_html=True)

    with row1_c2:
        st.markdown(f"""
            <div class="info-card">
                <h4>사내 구매 이력</h4>
                <p>✅ 총 {bpm_count:,}건</p>
            </div>
            <div class="info-card" style="background-color: #e9ecef; border-color: #dee2e6;">
                <h4>사내 평균 단가</h4>
                <p style="color: #495057;">💰 {bpm_avg:,.0f}원</p>
            </div>
        """, unsafe_allow_html=True)

    with row1_c3:
        st.subheader("2. 단가 정보 입력")
        price_gov = st.number_input(
            "📑 물가자료 단가 (원)", 
            min_value=0, 
            value=auto_price_price, 
            step=1000
        )
        price_quote = st.number_input(
            "💳 구매 견적 단가 (원)", 
            min_value=0, 
            value=bpm_avg, 
            step=1000
        )

    with row1_c4:
        st.subheader("3. 🎯 통합 단가 검증 판정")
        if price_quote == 0:
            st.info("견적 단가를 입력해 주세요.")
        else:
            diff_bpm = price_quote - bpm_avg
            rate_bpm = (diff_bpm / bpm_avg) * 100
            
            bpm_text = ""
            if price_quote <= bpm_avg:
                bpm_text = f"<span style='color: green;'>🟢 사내 평균가 대비 {abs(rate_bpm):.1f}% 저렴 (적정)</span>"
            elif price_quote <= bpm_max:
                bpm_text = f"<span style='color: orange;'>🟡 사내 평균가 대비 {rate_bpm:.1f}% 높음 (과거 최고가 이내)</span>"
            else:
                bpm_text = f"<span style='color: red;'>🔴 사내 최고가({bpm_max:,.0f}원) 대비 {rate_bpm:.1f}% 초과 (고가)</span>"
            
            st.markdown(f"**[사내 이력 분석]**<br>{bpm_text}", unsafe_allow_html=True)

            gov_text = ""
            if price_gov == 0:
                gov_text = "⚪ 물가자료 단가 미입력"
            else:
                diff_gov = price_quote - price_gov
                rate_gov = (diff_gov / price_gov) * 100
                if price_quote <= price_gov:
                    gov_text = f"<span style='color: green;'>🟢 물가자료가 대비 {abs(rate_gov):.1f}% 저렴 (적정)</span>"
                else:
                    gov_text = f"<span style='color: red;'>🔴 물가자료가 대비 {rate_gov:.1f}% 높음</span>"
            
            st.markdown(f"**[물가자료 분석]**<br>{gov_text}", unsafe_allow_html=True)

    st.divider()

    # ----------------------------------------------------
    # [섹션 3] 종합 비교표 및 그래프
    # ----------------------------------------------------
    st.subheader("📊 단가 종합 비교 및 차트")
    
    comp_data = {
        "구분": ["사내 최저가", f"사내 평균가 ({bpm_count}건)", "사내 최고가", "물가자료 단가", "구매 견적가"],
        "단가 (원)": [f"{bpm_min:,.0f}원", f"{bpm_avg:,.0f}원", f"{bpm_max:,.0f}원", f"{price_gov:,.0f}원", f"{price_quote:,.0f}원"],
        "비고": ["과거 최저 거래가", "과거 평균 거래가", "과거 최고 거래가", "공인 물가지 단가", "업체 견적/구매가"]
    }
    comp_df = pd.DataFrame(comp_data)
    
    col_tbl, col_chart = st.columns([1.5, 1])
    with col_tbl:
        st.table(comp_df)
    
    with col_chart:
        # 차트용 데이터는 숫자형으로 다시 계산
        chart_data = {
            "구분": ["최저가", "평균가", "최고가", "물가자료", "견적가"],
            "단가": [bpm_min, bpm_avg, bpm_max, price_gov, price_quote]
        }
        chart_df = pd.DataFrame(chart_data).set_index("구분")
        st.bar_chart(chart_df["단가"])

except Exception as e:
    st.error(f"시스템 실행 중 예기치 않은 오류가 발생했습니다. 데이터를 확인해 주세요.\n\n오류 내용: {e}")