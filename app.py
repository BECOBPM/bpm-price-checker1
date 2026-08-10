import streamlit as st
import pandas as pd
import re

try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

st.set_page_config(page_title="BPM 자재 단가 검증 시스템", layout="wide", page_icon="⚙️")

# 단가계약 성격 자재 자동 분류 함수
def classify_contract_type(name):
    name_str = str(name)
    # 연간 단가계약 대표 키워드
    contract_keywords = [
        '응집제', '약품', '가성소다', '염소', '소독제', '활성탄', 
        '가스', '질소', '산소', '아세틸렌', '오일', '윤활유', '구리스', 
        '필터', '용역', '위탁'
    ]
    for kw in contract_keywords:
        if kw in name_str:
            return '단가계약'
    return '일반구매'

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
    stats['계약유형'] = stats['자재명'].apply(classify_contract_type)
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
    # 📌 1. 왼쪽 사이드바: 구매 유형 필터 및 TOP 자재
    # ----------------------------------------------------
    st.sidebar.title("📦 구매 유형 선택")
    
    # [새로운 기능] 단가계약 vs 일반구매 필터
    contract_filter = st.sidebar.radio(
        "분류 기준 선택",
        ["📂 전체 품목", "💳 연간 단가계약 품목", "🛒 일반 구매 자재"],
        index=0
    )

    # 선택된 필터에 따라 데이터 프레임 걸러내기
    if contract_filter == "💳 연간 단가계약 품목":
        view_df = stats_df[stats_df['계약유형'] == '단가계약']
    elif contract_filter == "🛒 일반 구매 자재":
        view_df = stats_df[stats_df['계약유형'] == '일반구매']
    else:
        view_df = stats_df

    st.sidebar.markdown("---")
    st.sidebar.title("⭐ 자주 산 자재 (TOP 30)")
    st.sidebar.caption(f"[{contract_filter}] 기준 구매 이력 상위 품목입니다.")
    
    # 걸러진 데이터에서 이력건수 순 내림차순
    top30_df = view_df.sort_values(by='이력건수', ascending=False).head(30)
    
    if len(top30_df) > 0:
        top30_list = top30_df['검색용'].tolist()
        selected_from_sidebar = st.sidebar.selectbox("목록에서 바로 선택", top30_list)
    else:
        st.sidebar.warning("해당 유형의 자재가 없습니다.")
        selected_from_sidebar = stats_df['검색용'].iloc[0]

    st.sidebar.markdown("---")
    
    # 부가 기능 (물가자료 첨부) 접이식
    with st.sidebar.expander("📁 물가자료 PDF/Excel 첨부 (선택)", expanded=False):
        uploaded_files = st.file_uploader(
            "물가지 파일 첨부",
            type=['pdf', 'xlsx', 'xls'],
            accept_multiple_files=True
        )

    # ----------------------------------------------------
    # 🌟 2. 메인 화면: 키워드 검색 & 선택
    # ----------------------------------------------------
    st.title("⚙️ BPM 자재 단가 검증 시스템")
    
    c_search1, c_search2 = st.columns([1.5, 1.5])
    
    with c_search1:
        search_kw = st.text_input("🔍 자재명 / 규격 키워드 검색", "", placeholder="예: 응집제, 구리스, 밸브, 50A").strip()
    
    with c_search2:
        if search_kw:
            # 검색 시에도 선택된 구매 유형 내에서 검색
            search_filtered = view_df[view_df['검색용'].str.contains(search_kw, case=False, na=False)]
            if len(search_filtered) > 0:
                selected_item = st.selectbox(f"검색결과 ({len(search_filtered)}건) 중 선택", search_filtered['검색용'].tolist())
            else:
                st.warning("일치하는 자재가 없습니다. TOP 30 선택 품목으로 표시합니다.")
                selected_item = selected_from_sidebar
        else:
            selected_item = selected_from_sidebar
            st.selectbox("선택된 자재 (TOP 30 연동)", [selected_item], disabled=True)

    # 선택된 자재 데이터 가공
    target_data = stats_df[stats_df['검색용'] == selected_item].iloc[0]
    selected_material = target_data['자재명']
    selected_spec = target_data['자재규격']
    bpm_count = int(target_data['이력건수'])
    bpm_avg = int(target_data['평균단가'])
    bpm_max = int(target_data['최대단가'])
    bpm_min = int(target_data['최소단가'])
    contract_type = target_data['계약유형']

    st.divider()

    # ----------------------------------------------------
    # 3. 핵심 정보 및 3중 비교 판정
    # ----------------------------------------------------
    type_badge = "💳 [연간 단가계약 품목]" if contract_type == '단가계약' else "🛒 [일반 구매 품목]"
    st.subheader(f"📌 선택 자재: [{selected_material}] ({selected_spec})  {type_badge}")
    
    # 4대 수치 카드
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("사내 구매 이력", f"{bpm_count:,} 건")
    m2.metric("사내 평균 단가", f"{bpm_avg:,.0f} 원")
    m3.metric("과거 최저 단가", f"{bpm_min:,.0f} 원")
    m4.metric("과거 최고 단가", f"{bpm_max:,.0f} 원")

    st.markdown("<br>", unsafe_allow_html=True)

    # PDF/엑셀 자동 파싱
    auto_price_price = 0
    if 'uploaded_files' in locals() and uploaded_files:
        pdf_hits = []
        for f in uploaded_files:
            if f.name.lower().endswith('.pdf') and HAS_PDF:
                pdf_hits.extend(search_in_pdf(f, selected_material))
        if pdf_hits and pdf_hits[0]['단가후보']:
            auto_price_price = pdf_hits[0]['단가후보'][0]

    # 입력 & 판정 레이아웃
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
            
            # 사내 이력 비교
            if price_quote <= bpm_avg:
                st.success(f"🟢 **[사내 이력]** 평균가({bpm_avg:,.0f}원) 대비 **{abs(rate_bpm):.1f}% 저렴 (적정)**")
            elif price_quote <= bpm_max:
                st.warning(f"🟡 **[사내 이력]** 평균가 대비 **{rate_bpm:.1f}% 높음** (과거 최고가 {bpm_max:,.0f}원 이내)")
            else:
                st.error(f"🔴 **[사내 이력]** 과거 최고가({bpm_max:,.0f}원) 대비 **{rate_bpm:.1f}% 초과 (고가)**")

            # 물가자료 비교
            if price_gov > 0:
                diff_gov = price_quote - price_gov
                rate_gov = (diff_gov / price_gov) * 100
                if price_quote <= price_gov:
                    st.success(f"🟢 **[물가자료]** 공인가({price_gov:,.0f}원) 대비 **{abs(rate_gov):.1f}% 저렴 (적정)**")
                else:
                    st.error(f"🔴 **[물가자료]** 공인가({price_gov:,.0f}원) 대비 **{rate_gov:.1f}% 비쌈**")

    st.divider()

    # ----------------------------------------------------
    # 4. 하단 데이터 종합 비교
    # ----------------------------------------------------
    st.subheader("📊 단가 데이터 종합 비교")
    
    comp_df = pd.DataFrame({
        "구분": ["사내 최저가", f"사내 평균가 ({bpm_count}건)", "사내 최고가", "물가자료 단가", "구매 견적가"],
        "단가 (원)": [bpm_min, bpm_avg, bpm_max, price_gov, price_quote]
    })
    
    tbl_col, chart_col = st.columns([1, 1])
    with tbl_col:
        st.table(comp_df.assign(단가=comp_df["단가 (원)"].apply(lambda x: f"{x:,.0f}원"))[["구분", "단가"]])
    
    with chart_col:
        st.bar_chart(comp_df[comp_df["단가 (원)"] > 0].set_index("구분"))

except Exception as e:
    st.error(f"시스템 오류 발생: {e}")