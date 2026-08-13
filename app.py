import streamlit as st
import pandas as pd

# ==========================================
# 1. 페이지 기본 설정 및 스타일 정의
# ==========================================
st.set_page_config(page_title="부산환경공단 BPM", page_icon="🌿", layout="wide")

# ==========================================
# 2. 데이터 로드 및 초기화 (캐싱)
# ==========================================
@st.cache_data
def load_history_data():
    """2025년 사내 납품 이력 샘플 데이터"""
    data = [
        {"자재명": "배관용 스텐 파이프", "자재규격": "STS304 50A Sch10 6m", "입고일자": "2025-03-12", "납품업체": "미기재 (향후 개선 예정)", "수량": "20 개", "입고단가": 122000},
        {"자재명": "더블 피치 체인", "자재규격": "HC2040 1열", "입고일자": "2025-02-10", "납품업체": "대동모빌리티", "수량": "10 개", "입고단가": 3910},
        {"자재명": "롤러 체인", "자재규격": "HC40 1열", "입고일자": "2025-01-15", "납품업체": "대동모빌리티", "수량": "5 개", "입고단가": 3740},
        {"자재명": "볼베어링", "자재규격": "6302ZZ", "입고일자": "2025-04-01", "납품업체": "NSK코리아", "수량": "50 개", "입고단가": 2700},
        {"자재명": "배관용 스텐 엘보", "자재규격": "STS304 50A", "입고일자": "2025-03-20", "납품업체": "부산배관", "수량": "30 개", "입고단가": 8200},
    ]
    # 페이지네이션 테스트용 가상 데이터 생성 (총 15건 이상)
    for i in range(1, 12):
        data.append({
            "자재명": f"테스트 자재 {i}",
            "자재규격": f"규격-{i}00A",
            "입고일자": f"2025-05-{i:02d}",
            "납품업체": f"공급업체 {i}",
            "수량": "10 개",
            "입고단가": 10000 * i
        })
    return pd.DataFrame(data)

@st.cache_data
def load_price_index_data():
    """참조 물가지 데이터 (책자/PDF 페이지 정보 포함)"""
    price_data = [
        {"품목명": "배관용 스텐 파이프", "규격": "STS304 50A", "추천단가": 120000, "출처": "거래가격 2025년 기준", "페이지": "845p"},
        {"품목명": "더블 피치 체인", "규격": "HC2040 1열", "추천단가": 3910, "출처": "종합물가정보 2026년 8월호", "페이지": "1068p"},
        {"품목명": "롤러 체인", "규격": "HC40 1열", "추천단가": 3740, "출처": "종합물가정보 2026년 8월호", "페이지": "1068p"},
        {"품목명": "배관용 스텐 엘보", "규격": "STS304 50A", "추천단가": 8200, "출처": "종합물가정보 2025년 8월호", "페이지": "912p"},
        {"품목명": "볼베어링", "규격": "6302ZZ", "추천단가": 2700, "출처": "물가자료 2025년 8월호", "페이지": "1120p"},
    ]
    return pd.DataFrame(price_data)

df_history = load_history_data()
df_mulga = load_price_index_data()

# ==========================================
# 3. 주요 검색 및 탐색 함수 선언
# ==========================================
def search_materials(df, keyword):
    """자재명 및 규격 기반 검색 함수"""
    if not keyword:
        return df
    kw = keyword.strip()
    return df[df['자재명'].str.contains(kw, case=False, na=False) | df['자재규격'].str.contains(kw, case=False, na=False)]

def find_reference_price(df_mulga_data, name, spec):
    """물가지 데이터 매칭 탐색 함수"""
    if df_mulga_data is None or df_mulga_data.empty or not name:
        return None
    matched = df_mulga_data[df_mulga_data['품목명'].apply(lambda x: str(x) in str(name) or str(name) in str(x))]
    return matched if not matched.empty else None

# ==========================================
# 4. 화면 레이아웃 및 헤더
# ==========================================
# 상단 타이틀 바
st.markdown("""
    <div style="background-color: #0b6b5d; color: white; padding: 16px 20px; border-radius: 6px;">
        <h2 style="margin:0; padding:0; font-size:24px;">🌿 부산환경공단 BPM <span style="font-size:16px; font-weight:normal;">(Beco Parts Master)</span></h2>
        <p style="margin:6px 0 0 0; font-size:13px; color:#d0f0eb;">2025년 자재 수불 이력 기반 공정·투명 계약지원 시스템 | 기술개발 및 단가심사 자동화</p>
    </div>
""", unsafe_allow_html=True)

st.write("")

# 안내문구
st.markdown("""
    <div style="background-color: #fff8e6; border: 1px solid #ffe58f; padding: 10px 15px; border-radius: 4px; font-size: 14px; color: #8c6b00;">
        📌 <b>시스템 안내:</b> 현재 2025년 자재 DB의 '납품업체명' 항목은 데이터 수집 진행 중(미기재)이며, 향후 시스템 고도화 시 추가 업데이트 예정입니다.
    </div>
""", unsafe_allow_html=True)

st.write("")

# ==========================================
# 5. 검색 및 페이지네이션 (Pagination)
# ==========================================
col_search, col_page, col_select = st.columns([2.5, 1.2, 2.5])

with col_search:
    search_input = st.text_input("🔍 자재명 또는 규격 검색", value="", placeholder="예: 배관, 파이프, 베어링 6302")

# 데이터 필터링
filtered_df = search_materials(df_history, search_input)
unique_items = filtered_df[['자재명', '자재규격']].drop_duplicates() if not filtered_df.empty else pd.DataFrame()

# 페이지 수 계산 (페이지당 10개)
PAGE_SIZE = 10
total_items = len(unique_items)
total_pages = (total_items - 1) // PAGE_SIZE + 1 if total_items > 0 else 1

with col_page:
    if total_pages > 1:
        current_page = st.number_input(
            f"📄 Page (총 {total_pages}P)", 
            min_value=1, 
            max_value=total_pages, 
            value=1, 
            step=1
        )
    else:
        current_page = 1
        st.markdown(f"<div style='padding-top:28px; color:#555;'>📄 <b>1 / 1 Page</b></div>", unsafe_allow_html=True)

selected_item_records = None
sel_name, sel_spec = "", ""

with col_select:
    if not unique_items.empty:
        start_idx = (current_page - 1) * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE
        paged_items = unique_items.iloc[start_idx:end_idx]
        
        options = [f"{row['자재명']} | {row['자재규격']}" for _, row in paged_items.iterrows()]
        select_label = f"검색 결과 (총 {total_items}건 | {current_page}/{total_pages} Page)"
        selected_option = st.selectbox(select_label, options)
        
        if selected_option:
            sel_name, sel_spec = selected_option.split(" | ")
            selected_item_records = df_history[(df_history['자재명'] == sel_name) & (df_history['자재규격'] == sel_spec)]
    else:
        st.selectbox("검색 결과 (0건)", ["검색 결과가 없습니다"])

st.write("---")

# ==========================================
# 6. 선택 품목 단가 분석 및 물가지 탐색
# ==========================================
if selected_item_records is not None and not selected_item_records.empty:
    st.markdown(f"### 📦 선택 품목: **[{sel_name}]** <span style='color:#0b6b5d; font-size:20px;'>({sel_spec})</span>", unsafe_allow_html=True)
    st.write("")

    # 카드 통계 요약
    c1, c2, c3, c4 = st.columns(4)
    item_count = len(selected_item_records)
    avg_price = selected_item_records['입고단가'].mean()
    min_price = selected_item_records['입고단가'].min()
    max_price = selected_item_records['입고단가'].max()

    with c1:
        st.caption("2025년 구매 이력")
        st.subheader(f"{item_count} 건")
    with c2:
        st.caption("사내 평균 단가")
        st.subheader(f"{int(avg_price):,} 원")
    with c3:
        st.caption("2025년 최저 단가")
        st.subheader(f"{int(min_price):,} 원")
        st.caption("↑ 납품업체: 향후 개선 예정")
    with c4:
        st.caption("2025년 최고 단가")
        st.subheader(f"{int(max_price):,} 원")
        st.caption("↑ 납품업체: 향후 개선 예정")

    st.write("")
    st.write("---")

    # 참조 물가지 자동 탐색 및 근거 페이지 표시
    st.markdown("#### 💡 참조 물가지 자동 탐색 및 추천 단가")
    
    ref_result = find_reference_price(df_mulga, sel_name, sel_spec)

    if ref_result is not None and not ref_result.empty:
        for _, ref in ref_result.iterrows():
            page_val = ref.get('페이지', '페이지 정보 없음')
            st.success(
                f"✅ **[물가지 매칭 성공]** 추천 단가: **{ref['추천단가']:,} 원** "
                f"(출처: {ref['출처']} | 📄 **페이지: {page_val}** / 규격: {ref['규격']})"
            )
    else:
        st.info("⭕ 참조 물가지에서 일치하는 자동 추천 단가가 없습니다.")

    st.write("")
    st.write("---")

    # 상세 납품 이력 테이블
    st.markdown("#### 📜 2025년 사내 납품 상세 이력")
    st.dataframe(
        selected_item_records[['입고일자', '납품업체', '수량', '입고단가']],
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("검색 결과를 선택하면 상세 단가 및 물가지 추천 정보가 표시됩니다.")