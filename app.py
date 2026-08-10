import streamlit as st
import pandas as pd
import re

try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

st.set_page_config(page_title="BPM 자재 단가 검증 시스템", layout="wide", page_icon="⚙️")

# 자재 자동 카테고리 분류 함수
def classify_category(name):
    name_str = str(name)
    mech_keywords = ['밸브', '펌프', '구리스', '배관', '보일러', '압축기', '모터', '가스', '오일', '필터', '패킹', '가스켓', '볼트', '베어링', '배관재', '수동', '유압']
    elec_keywords = ['차단기', '케이블', '전선', '스위치', '조명', '등', '트랜스', '변압기', '센서', '전기', '배전', '콘센트', '소켓']
    civil_keywords = ['시멘트', '아스콘', '골재', '방수', '배수로', '측구', '관', '토목', '페인트', '타일', '철근', '콘크리트']

    for k in elec_keywords:
        if k in name_str:
            return '전기'
    for k in civil_keywords:
        if k in name_str:
            return '토목'
    return '기계' # 기본값 기계

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
    stats['카테고리'] = stats['자재명'].apply(classify_category)
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
    # 📌 1. 왼쪽 사이드바: 분야별 카테고리 & 자주 산 리스트
    # ----------------------------------------------------
    st.sidebar.title("🛠️ 분야별 자재 목차")
    
    # [1] 분야 선택 (기계 / 전기 / 토목 / 전체)
    selected_cat = st.sidebar.radio(
        "분야 선택",
        ["🔧 기계설비", "⚡ 전기설비", "🏗️ 토목/건축", "📂 전체보기"],
        index=0
    )
    
    cat_map = {
        "🔧 기계설비": "기계",
        "⚡ 전기설비": "전기",
        "🏗️ 토목/건축": "토목",
        "📂 전체보기": "전체"
    }
    cat_filter = cat_map[selected_cat]

    if cat_filter == "전체":
        cat_df = stats_df
    else:
        cat_df = stats_df[stats_df['카테고리'] == cat_filter]

    st.sidebar.markdown("---")
    st.sidebar.subheader("🔥 자주 구매한 자재 (TOP)")
    
    # 구매 건수가 많은 순으로 정렬
    top_items_df = cat_df.sort_values(by='이력건수', ascending=False)
    
    if len(top_items_df) > 0:
        top_list = top_items_df['검색용'].tolist()[:15] # 상위 15개
        selected_from_sidebar = st.sidebar.selectbox("자주 산 리스트에서 선택", top_list)
    else:
        st.sidebar.info("해당 카테고리에 등록된 자재가 없습니다.")
        selected_from_sidebar = stats_df['검색용'].iloc[0]

    st.sidebar.markdown("---")
    
    # [2] 파일 업로드는 사이드바 맨 아래 접이식으로 이동
    with st.sidebar.expander("📁 물가자료 PDF/Excel 첨부 (선택)", expanded=False):
        uploaded_files = st.file_uploader(
            "물가지 파일 첨부",
            type=['pdf', 'xlsx', 'xls'],
            accept_multiple_files=True
        )

    # ----------------------------------------------------
    # 🌟 2. 메인 화면: 자재 선택 & 단가 비교
    # ----------------------------------------------------
    st.title("⚙️ BPM 자재 단가 검증 시스템")
    
    # 직접 직접 키워드 검색도 가능하게 상단 배치
    c_search1, c_search2 = st.columns([2, 1])
    with c_search1:
        search_kw = st.text_input("🔍 목록에 없는 자재 직접 키워드 검색 (선택사항)", "").strip()
    
    if search_kw:
        search_filtered = stats_df[stats_df['검색용'].str.contains(search_kw, case=False, na=False)]
        if len(search_filtered) > 0:
            selected_item = st.selectbox("검색 결과 자재 선택", search_filtered['검색용'].tolist())
        else:
            st.warning("검색 결과가 없습니다. 목차에서 선택한 자재로 표시합니다.")
            selected_item = selected_from_sidebar
    else:
        selected_item = selected_from_sidebar

    # 선택된 자재 데이터 가공
    target_data = stats_df[stats_df['검색용'] == selected_item].iloc[0]
    selected_material = target_data['자재명']
    selected_spec = target_data['자재규격']
    bpm_count = int(target_data['이력건수'])
    bpm_avg = int(target_data['평균단가'])
    bpm_max = int(target_data['최대단가'])
    bpm_min = int(target_data['최소단가'])

    st.divider()

    # ----------------------------------------------------
    # 3. 선택 자재 정보 및 3중 비교 레이아웃
    # ----------------------------------------------------
    st.subheader(f"📌 선택 자재: [{selected_material}] ({selected_spec})")
    
    # 핵심 통계 지표 (Metric Cards)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("사내 구매 이력", f"{bpm_count:,} 건")
    m2.metric("사내 평균 단가", f"{bpm_avg:,.0f} 원")
    m3.metric("과거 최저 단가", f"{bpm_min:,.0f} 원")
    m4.metric("과거 최고 단가", f"{bpm_max:,.0f} 원")

    st.markdown("<br>", unsafe_allow_html=True)

    # 단가 입력 및 판정 (2열 구조)
    col_input, col_result = st.columns([1, 1.2])

    # PDF/엑셀 자동 검색 단가 파싱
    auto_price_price = 0
    if 'uploaded_files' in locals() and uploaded_files:
        pdf_hits = []
        for f in uploaded_files:
            if f.name.lower().endswith('.pdf') and HAS_PDF:
                pdf_hits.extend(search_in_pdf(f, selected_material))
        if pdf_hits and pdf_hits[0]['단가후보']:
            auto_price_price = pdf_hits[0]['단가후보'][0]

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
    # 4. 하단 비교표 및 그래프
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