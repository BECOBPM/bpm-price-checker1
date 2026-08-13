import streamlit as st
import pandas as pd
import io
import re
import os
import glob

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
    .main { background-color: #f8f9fa; }
    .beco-header {
        background: linear-gradient(135deg, #0f4c81 0%, #1e88e5 60%, #2e7d32 100%);
        padding: 24px 28px;
        border-radius: 12px;
        color: white;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }
    .beco-header h1 { color: #ffffff !important; font-size: 26px !important; font-weight: 700 !important; margin-bottom: 6px !important; }
    .beco-header p { color: #e0f2fe !important; font-size: 14px !important; margin: 0 !important; }
    .custom-card {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 20px;
        border: 1px solid #e9ecef;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        margin-bottom: 15px;
    }
    .quote-box {
        background-color: #ebf5ff;
        border-left: 6px solid #1565c0;
        padding: 12px 16px;
        border-radius: 8px;
        margin-top: 10px;
        margin-bottom: 10px;
    }
    .quote-title { color: #0d47a1; font-weight: 700; font-size: 15px; }
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------
# 🔔 물가정보/물가자료 미입력 팝업 (Modal Dialog)
# ----------------------------------------------------
@st.dialog("⚠️ 물가자료 및 물가정보 검토 알림")
def show_missing_price_dialog():
    st.warning("💡 **물가정보 및 물가자료 단가가 입력되지 않았습니다.**")
    st.write("공인 단가지(물가정보, 물가자료 등)를 검토하셨는지 다시 한번 확인해 주세요.")
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("확인 및 검토 진행", use_container_width=True):
        st.session_state['dialog_dismissed'] = True
        st.rerun()


# ----------------------------------------------------
# 📦 사내 자재 DB 로드
# ----------------------------------------------------
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
        min_p, max_p = prices[0], prices[-1]
        if n >= 5:
            avg_p = sum(prices[1:-1]) / len(prices[1:-1])
            is_trimmed = True
        else:
            avg_p = sum(prices) / n
            is_trimmed = False
            
        return pd.Series({
            '이력건수': n, '평균단가': round(avg_p), '최소단가': min_p, '최대단가': max_p, '절사적용': is_trimmed
        })

    stats = df.groupby(['자재명', '자재규격'], group_keys=False).apply(calc_trimmed_stats).reset_index()
    stats['검색용'] = stats['자재명'].astype(str) + " | " + stats['자재규격'].astype(str)
    return stats


# ----------------------------------------------------
# 📚 폴더 내 물가지 PDF 전체 자동 색인 및 캐싱
# ----------------------------------------------------
@st.cache_data
def load_and_index_reference_pdfs():
    """같은 폴더에 있는 모든 종합물가정보 PDF 텍스트를 미리 읽어서 캐시합니다."""
    pdf_files = glob.glob("종합물가정보*.pdf") + glob.glob("*.pdf")
    pdf_files = sorted(list(set(pdf_files)))
    
    indexed_data = []
    if not HAS_PDF or not pdf_files:
        return indexed_data
    
    for f_path in pdf_files:
        # 사내 DB 파일은 제외
        if '2025년 자재원본' in f_path:
            continue
        try:
            file_name = os.path.basename(f_path)
            with pdfplumber.open(f_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        for line in text.split('\n'):
                            clean_line = line.strip()
                            if clean_line:
                                indexed_data.append({
                                    'file': file_name,
                                    'page': page_num,
                                    'text': clean_line
                                })
        except Exception:
            continue
            
    return indexed_data


# ----------------------------------------------------
# 🔍 스마트 키워드 토큰 기반 검색 함수
# ----------------------------------------------------
def search_in_indexed_pdfs(target_material, target_spec):
    indexed_lines = load_and_index_reference_pdfs()
    if not indexed_lines:
        return []

    # 검색어 토큰화 (예: '게이트밸브', '주철, 80A10k' -> ['게이트', '밸브', '주철', '80A', '10K'])
    raw_str = f"{target_material} {target_spec}"
    tokens = [t.upper() for t in re.findall(r'[가-힣a-zA-Z0-9]+', raw_str) if len(t) >= 2 or t.isdigit()]
    
    candidates = []
    for item in indexed_lines:
        line_upper = item['text'].upper()
        
        # 토큰 포함 개수 측정
        match_count = sum(1 for token in tokens if token in line_upper)
        
        # 2개 이상 토큰이 일치하거나, 토큰이 적은 경우 최소 1개 일치 시
        if match_count >= 2 or (len(tokens) < 2 and match_count >= 1):
            # 단가 숫출 (100원 초과)
            numbers = re.findall(r'\b\d{1,3}(?:,\d{3})+\b|\b\d{4,9}\b', item['text'])
            clean_nums = []
            for n in numbers:
                val = int(n.replace(',', ''))
                if val >= 500: # 의미 있는 최소 단가 기준
                    clean_nums.append(val)
            
            if clean_nums:
                # 파일명 단순화 (예: 종합물가정보 2026년 08월호-기계.pdf -> 기계)
                short_fname = re.sub(r'종합물가정보.*?-', '', item['file']).replace('.pdf', '')
                if short_fname == item['file']:
                    short_fname = item['file'][:15]
                    
                candidates.append({
                    'title': f"📄 [{short_fname} {item['page']}p] {item['text']}",
                    'price': clean_nums[0],
                    'score': match_count
                })

    # 적합도 높은 순 정렬
    candidates.sort(key=lambda x: (x['score'], x['price']), reverse=True)
    
    # 중복 제거
    seen = set()
    unique_candidates = []
    for c in candidates:
        key = (c['title'], c['price'])
        if key not in seen:
            seen.add(key)
            unique_candidates.append(c)
            
    return unique_candidates[:5]


try:
    stats_df = load_bpm_data()

    # 상단 헤더
    st.markdown("""
    <div class="beco-header">
        <h1>🌿 부산환경공단 (BECO) 자재 단가 검증 시스템</h1>
        <p>자재 수불 이력 기반 공정·투명 계약지원 시스템 | 기술개발 및 단가심사 자동화</p>
    </div>
    """, unsafe_allow_html=True)

    # 사이드바
    st.sidebar.markdown("## 🌿 BECO 메뉴")
    page = st.sidebar.radio("기능을 선택하세요", ["🔍 단 품목 단가 검증", "📄 업체 견적서 일괄 검토", "📊 자재 데이터 분석"])
    st.sidebar.caption("DB 기준: 자재 실시간 입고이력")
    st.sidebar.markdown("---")
    
    # 감지된 물가지 파일 현황 표시
    indexed_pdfs = list(set([item['file'] for item in load_and_index_reference_pdfs()]))
    st.sidebar.markdown("### 📚 참조 물가지 DB 현황")
    if indexed_pdfs:
        st.sidebar.success(f"총 {len(indexed_pdfs)}개 물가지 PDF 자동 로드 완료")
        with st.sidebar.expander("로드된 파일 목록 보기"):
            for f_name in indexed_pdfs:
                st.write(f"• {f_name}")
    else:
        st.sidebar.warning("폴더 내 물가지 PDF 파일이 없습니다.")

    # ====================================================
    # 🌟 PAGE 1: 단 품목 단가 검증
    # ====================================================
    if page == "🔍 단 품목 단가 검증":
        st.sidebar.markdown("---")
        st.sidebar.markdown("### ⭐ 다빈도 구매 자재 (TOP 30)")
        top30_df = stats_df.sort_values(by='이력건수', ascending=False).head(30)
        selected_from_sidebar = st.sidebar.selectbox("목록에서 빠른 선택", top30_df['검색용'].tolist())

        # 검색 영역
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        c_search1, c_search2 = st.columns([1.5, 1.5])
        with c_search1:
            search_kw = st.text_input("🔍 자재명 또는 규격 검색", "", placeholder="예: 게이트밸브, 볼밸브, 80A").strip()
        
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
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("사내 구매 이력", f"{bpm_count:,} 건")
        m2.metric("사내 평균 단가" + (" (절사평균)" if is_trimmed else ""), f"{bpm_avg:,.0f} 원")
        m3.metric("과거 최저 단가", f"{bpm_min:,.0f} 원")
        m4.metric("과거 최고 단가", f"{bpm_max:,.0f} 원")

        st.markdown("<br>", unsafe_allow_html=True)

        # 🔍 로컬 PDF 내 유사 항목 자동 탐색
        smart_hits = search_in_indexed_pdfs(selected_material, selected_spec)
        auto_selected_price = 0

        if smart_hits:
            st.markdown('<div class="custom-card" style="border-left: 5px solid #2e7d32;">', unsafe_allow_html=True)
            st.markdown("#### 💡 참조 물가지 내 유사 규격/단가 검색 결과 (자동 추천)")
            hit_options = [f"{item['title']} ➔ [{item['price']:,}원]" for item in smart_hits]
            hit_options.insert(0, "선택 안 함 (직접 입력)")
            
            selected_hit = st.selectbox("가장 적합한 물가지 항목을 선택하시면 단가에 자동 입력됩니다.", hit_options)
            if selected_hit != "선택 안 함 (직접 입력)":
                hit_idx = hit_options.index(selected_hit) - 1
                auto_selected_price = smart_hits[hit_idx]['price']
                st.success(f"선택한 물가정보 단가 **{auto_selected_price:,.0f}원**이 물가정보 단가란에 자동 반영되었습니다.")
            st.markdown('</div>', unsafe_allow_html=True)

        # 비교 단가 입력 레이아웃
        col_input, col_result = st.columns([1, 1.2])
        
        with col_input:
            st.markdown('<div class="custom-card">', unsafe_allow_html=True)
            st.markdown("#### 💳 비교 단가 입력")
            
            with st.form(key='price_input_form'):
                price_info = st.number_input("📑 물가정보 공인 단가 (원)", min_value=0, value=auto_selected_price, step=1000)
                price_data = st.number_input("📑 물가자료 공인 단가 (원)", min_value=0, value=0, step=1000)
                
                if price_info == 0 and price_data == 0:
                    st.info("💡 **물가정보 및 물가자료는 검토하셨습니까?** (미입력 상태)")

                st.markdown("""
                <div class="quote-box">
                    <div class="quote-title">🟦 구매 / 견적 예정 단가 (검토 대상)</div>
                </div>
                """, unsafe_allow_html=True)
                
                price_quote = st.number_input("구매견적가 입력 (원)", min_value=0, value=bpm_avg, step=1000, label_visibility="collapsed")
                submit_button = st.form_submit_button("🔍 단가 검토 및 팝업 확인 (Enter)", use_container_width=True)

            st.markdown('</div>', unsafe_allow_html=True)

            if submit_button:
                if price_quote > 0 and price_info == 0 and price_data == 0:
                    show_missing_price_dialog()

        with col_result:
            st.markdown('<div class="custom-card">', unsafe_allow_html=True)
            st.markdown("#### 🎯 적정성 종합 판정 결과")
            
            if price_quote == 0:
                st.info("검토할 구매견적 단가를 입력해 주세요.")
            else:
                st.markdown(f"##### 🟦 **검토 구매견적가: <span style='color:#1565C0; font-size:22px;'>{price_quote:,.0f}원</span>**", unsafe_allow_html=True)
                st.markdown("---")
                
                # 사내 이력 비교
                diff_bpm = price_quote - bpm_avg
                rate_bpm = (diff_bpm / bpm_avg) * 100
                if price_quote <= bpm_avg:
                    st.success(f"🟢 **[사내 이력 대비]** 평균가({bpm_avg:,.0f}원) 대비 **{abs(rate_bpm):.1f}% 저렴 (적정)**")
                elif price_quote <= bpm_max:
                    st.warning(f"🟡 **[사내 이력 대비]** 평균가 대비 **{rate_bpm:.1f}% 높음** (과거 최고가 이내)")
                else:
                    st.error(f"🔴 **[사내 이력 대비]** 과거 최고가({bpm_max:,.0f}원) 초과 **(고가 주의)**")

                # 물가정보 비교
                if price_info > 0:
                    diff_info = price_quote - price_info
                    rate_info = (diff_info / price_info) * 100
                    if price_quote <= price_info:
                        st.success(f"🟢 **[물가정보]** 공인가({price_info:,.0f}원) 대비 **{abs(rate_info):.1f}% 저렴 (적정)**")
                    else:
                        st.error(f"🔴 **[물가정보]** 공인가({price_info:,.0f}원) 대비 **{rate_info:.1f}% 비쌈**")

                # 물가자료 비교
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
            "구분": ["사내 최저가", f"사내 평균가 ({bpm_count}건)", "사내 최고가", "물가정보 단가", "물가자료 단가", "🟦 구매견적가"],
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

    # PAGE 2 & 3
    elif page == "📄 업체 견적서 일괄 검토":
        st.subheader("📄 업체 제출 견적서 자동 일괄 검토")
        st.caption("업체에서 제출한 엑셀 견적서를 업로드하면, 공단 사내 단가 DB와 비교하여 적정성을 검토합니다.")
        
    else:
        st.subheader("📊 사내 자재 현황 및 데이터 분석")

except Exception as e:
    st.error(f"시스템 오류 발생: {e}")