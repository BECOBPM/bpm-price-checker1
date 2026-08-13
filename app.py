import streamlit as st
import pandas as pd
import re

# ... [기존 CSS 및 기본 설정 유지] ...

# --- [물가지 DB에 페이지(Page) 정보 반영] ---
@st.cache_data
def load_price_index_data():
    price_data = [
        {
            "품목명": "더블 피치 체인 / 롤러 체인", 
            "규격": "HC40 1열", 
            "추천단가": 3740, 
            "출처": "종합물가정보 2026년 8월호", 
            "페이지": "1068p"
        },
        {
            "품목명": "배관용 스텐 파이프", 
            "규격": "STS304 50A", 
            "추천단가": 120000, 
            "출처": "거래가격 2025년 8월호", 
            "페이지": "845p"
        },
        {
            "품목명": "배관용 스텐 엘보", 
            "규격": "STS304 50A", 
            "추천단가": 8200, 
            "출처": "종합물가정보 2025년 8월호", 
            "페이지": "912p"
        },
        {
            "품목명": "배관용 스텐볼밸브", 
            "규격": "15A 나사식", 
            "추천단가": 3800, 
            "출처": "거래가격 2025년 8월호", 
            "페이지": "530p"
        },
        {
            "품목명": "볼베어링", 
            "규격": "6302ZZ", 
            "추천단가": 2700, 
            "출처": "물가자료 2025년 8월호", 
            "페이지": "1120p"
        },
    ]
    return pd.DataFrame(price_data)

df_mulga = load_price_index_data()

# ==========================================
# 참조 물가지 자동 탐색 및 추천 단가 출력 부분
# ==========================================
# (단 품목 단가 검증 메뉴 내부)

st.markdown("#### 💡 참조 물가지 자동 탐색 및 추천 단가")
ref_result = find_reference_price(df_mulga, target_name, target_spec)

if ref_result is not None and not ref_result.empty:
    for _, ref in ref_result.iterrows():
        # 📄 페이지 번호 유무 체크 및 표시
        page_info = f" | 📄 **페이지: {ref['페이지']}**" if '페이지' in ref and pd.notna(ref['페이지']) else ""
        
        st.success(
            f"✅ **[물가지 매칭 성공]** 추천 단가: **{ref['추천단가']:,} 원** "
            f"(출처: {ref['출처']}{page_info} / 규격: {ref['규격']})"
        )
else:
    st.info("⭕ 참조 물가지에서 일치하는 자동 추천 단가가 없습니다.")