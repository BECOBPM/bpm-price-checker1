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

# PAGE CONFIG (BPM 명칭 적용)
st.set_page_config(
    page_title="BECO BPM (Beco Parts Master) - 자재 단가 검증 시스템", 
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
    .vendor-subtext { font-size: 12px; color: #555555; margin-top: -8px; margin-bottom: 8px; }
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
# 📦 사내 자재 DB 로드 (최저가 업체명 추출)
# ----------------------------------------------------
@st.cache_data
def load_bpm_data():
    df = pd.read_excel('2025년 자재원본.xlsx', sheet_name='Data', header=2)
    df = df[df['입고단가'].notnull() & (df['입고단가'] > 0)]
    
    # 업체명 관련 컬럼 탐색
    vendor_col = None
    for col in ['업체명', '거래처명', '계약상호', '공급업체명', '공급업체', '상호', '업체']:
        if col in df.columns:
            vendor_col = col
            break

    def calc_trimmed_stats(g):
        prices = g['입고단가'].dropna().tolist()
        prices.sort()
        n = len(prices)
        if n == 0:
            return pd.Series({'이력건수': 0, '평균단가': 0, '최소단가': 0, '최대단가': 0, '최저가업체': '', '절사적용': False})
        
        min_p, max_p = prices[0], prices[-1]
        
        # 최저가 납품 업체 추출
        min_vendor = ""
        if vendor_col and vendor_col in g.columns:
            min_rows = g[g['입고단가'] == min_p]
            if not min_rows.empty:
                v_val = str(min_rows.iloc[0][vendor_col]).strip()
                if v_val and v_val.lower() != 'nan':
                    min_vendor = v_val

        if n >= 5:
            avg_p = sum(prices[1:-1]) / len(prices[1:-1])
            is_trimmed = True
        else:
            avg_p = sum(prices) / n
            is_trimmed = False
            
        return pd.Series({
            '이력건수': n, 
            '평균단가': round(avg_p), 
            '최소단가': min_p, 
            '최대단가': max_p, 
            '최저가업체': min_vendor,
            '절사적용': is_trimmed
        })

    stats = df.groupby(['자재명', '자재규격'], group_keys=False).apply(calc_trimmed_stats).reset_index()
    stats['검색용'] = stats['자재명'].astype(str) + " | " + stats['자재규격'].astype(str)
    return stats


# ----------------------------------------------------
# 📚 폴더 내 물가지 PDF 전체 자동 색인
# ----------------------------------------------------
@st.cache_data
def load_and_index_reference_pdfs():
    pdf_files = glob.glob("종합물가정보*.pdf") + glob.glob("*.pdf")
    pdf_files = sorted(list(set(pdf_files)))
    
    indexed_data = []
    if not HAS_PDF or not pdf_files:
        return indexed_data
    
    for f_path in pdf_files:
        if '2025년 자재원본' in f_path:
            continue
        try:
            file_name = os.path.basename(f_path)
            with pdfplumber.open(f_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        lines = text.split('\n')
                        
                        # 인쇄 페이지 번호 파싱
                        printed_page = f"{page_num}p"
                        for head_line in lines[:3]:
                            page_match = re.search(r'\b([1-9]\d{2,3})\b', head_line)
                            if page_match:
                                printed_page = f"페이지 {page_match.group(1)}"
                                break

                        current_header = ""
                        for line in lines:
                            clean_line = line.strip()
                            if clean_line:
                                norm_line = re.sub(r'\s+', '', clean_line).upper()
                                
                                # 자재 그룹 헤더 추적 (예: "볼 베 어 링")
                                ko_chars = re.findall(r'[가-힣]', norm_line)
                                digits = re.findall(r'\d', norm_line)
                                if len(ko_chars) >= 2 and len(digits) <= 2:
                                    current_header = norm_line

                                indexed_data.append({
                                    'file': file_name,
                                    'page_str': printed_page,
                                    'text': clean_line,
                                    'norm_text': norm_line,
                                    'header': current_header
                                })
        except Exception:
            continue
            
    return indexed_data


# ----------------------------------------------------
# 🔍 정교한 키워드 필터링 검색 (품목명 필수 검증)
# ----------------------------------------------------
def search_in_indexed_pdfs(target_material, target_spec):
    indexed_lines = load_and_index_reference_pdfs()
    if not indexed_lines:
        return []

    ko_raw = re.findall(r'[가-힣]+', target_material)
    ko_keywords = []
    for k in ko_raw:
        k_norm = re.sub(r'\s+', '', k)
        if len(k_norm) >= 2:
            ko_keywords.append(k_norm)
            if '베어링' in k_norm:
                ko_keywords.append('베어링')
            if '밸브' in k_norm:
                ko_keywords.append('밸브')
    ko_keywords = list(set(ko_keywords))

    spec_numbers = re.findall(r'\d+', target_spec)
    spec_letters = re.findall(r'[a-zA-Z]+', target_spec)

    candidates = []
    
    for item in indexed_lines:
        norm_line = item['norm_text']
        header = item['header']
        orig_text = item['text']
        
        # 1. 품목 한글 키워드가 본문/헤더에 존재해야 함
        if ko_keywords:
            has_ko_match = any(k in norm_line or k in header for k in ko_keywords)
            if not has_ko_match:
                continue

        # 2. 규격 숫자 매칭
        score = 10
        if spec_numbers:
            matched_num_count = 0
            for num in spec_numbers:
                pattern = r'(?<!\d)' + re.escape(num) + r'(?!\d)'
                if re.search(pattern, norm_line):
                    matched_num_count += 1
                    score += 10
            if matched_num_count == 0:
                continue

        # 3. 영문 규격 매칭
        for a in spec_letters:
            if a.upper() in norm_line:
                score += 5

        # 4. 단가 추출
        numbers = re.findall(r'\b\d{1,3}(?:,\d{3})+\b|\b\d{4,9}\b', orig_text)
        clean_nums = [int(n.replace(',', '')) for n in numbers if int(n.replace(',', '')) >= 500]
        
        if clean_nums:
            short_fname = item['file'].replace('종합물가정보', '').replace('.pdf', '').strip(' 2026년 08월호-_')
            if not short_fname:
                short_fname = item['file']

            selected_price = clean_nums[0]
            upper_spec = target_spec.upper()
            if 'ZZ' in upper_spec and len(clean_nums) >= 2:
                selected_price = clean_nums[1]
            elif 'DD' in upper_spec and len(clean_nums) >= 3:
                selected_price = clean_nums[2]

            candidates.append({
                'title': f"📄 [{short_fname} | {item['page_str']}] {orig_text}",
                'price': selected_price,
                'score': score
            })

    candidates.sort(key=lambda x: (x['score'], x['price']), reverse=True)
    
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

    # 상단 헤더 (BPM 명칭 반영)
    st.markdown("""
    <div class="beco-header">
        <h1>🌿 부산환경공단 BPM (Beco Parts Master)</h1>
        <p>자재 수불 이력 기반 공정·투명 계약지원 시스템 | 기술개발 및 단가심사 자동화</p>
    </div>
    """, unsafe_allow_html=True)

    # 사이드바 (BECO BPM 반영)
    st.sidebar.markdown("## 🌿 BECO BPM 메뉴")
    page = st.sidebar.radio("기능을 선택하세요", ["🔍 단 품목 단가 검증", "📄 업체 견적서 일괄 검토", "📊 자재 데이터 분석"])
    st.sidebar.caption("DB 기준: 자재 실시간 입고이력")
    st.sidebar.markdown("---")
    
    indexed_pdfs = list(set([item['file'] for item in load_and_index_reference_pdfs()]))
    st.sidebar.markdown("### 📚 참조 물가지 DB 현황")
    if indexed_pdfs:
        st.sidebar.success(f"총 {len(indexed_pdfs)}개 물가지 PDF 자동 로드 완료")
        with st.sidebar.expander("로드된 파일 목록 보기"):
            for f_name in indexed_pdfs:
                st.write(f"• {f_name}")
    else:
        st.sidebar.warning("폴더 내 물가지 PDF 파일이 없습니다.")

    # PAGE 1: 단 품목 단가 검증
    if page == "🔍 단 품목 단가 검증":
        st.sidebar.markdown("---")
        st.sidebar.markdown("### ⭐ 다빈도 구매 자재 (TOP 30)")
        top30_df = stats_df.sort_values(by='이력건수', ascending=False).head(30)
        selected_from_sidebar = st.sidebar.selectbox("목록에서 빠른 선택", top30_df['검색용'].tolist())

        # 검색 영역
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        c_search1, c_search2 = st.columns([1.5, 1.5])
        with c_search1:
            search_kw = st.text_input("🔍 자재명 또는 규격 검색", "", placeholder="예: 게이트밸브, 베어링, 6307").strip()
        
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
        min_vendor = str(target_data.get('최저가업체', ''))
        is_trimmed = bool(target_data['절사적용'])

        st.markdown(f"### 📦 선택 품목: **[{selected_material}]** `({selected_spec})`")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("사내 구매 이력", f"{bpm_count:,} 건")
        m2.metric("사내 평균 단가" + (" (절사평균)" if is_trimmed else ""), f"{bpm_avg:,.0f} 원")
        
        # 과거 최저 단가 + 최저가 납품 업체 소형 표기
        m3.metric("과거 최저 단가", f"{bpm_min:,.0f} 원")
        if min_vendor:
            m3.caption(f"🏢 최저가 납품: **{min_vendor}**")
        else:
            m3.caption("🏢 최저가 납품: 업체 정보 없음")
            
        m4.metric("과거 최고 단가", f"{bpm_max:,.0f} 원")

        st.markdown("<br>", unsafe_allow_html=True)

        # 로컬 PDF 참조 단가 탐색
        smart_hits = search_in_indexed_pdfs(selected_material, selected_spec)
        auto_selected_price = 0

        st.markdown('<div class="custom-card" style="border-left: 5px solid #1e88e5;">', unsafe_allow_html=True)
        st.markdown("#### 💡 참조 물가지 자동 탐색 및 추천 단가")
        
        if smart_hits:
            st.success(f"🟢 **총 {len(smart_hits)}건의 정확한 물가지 추천 단가를 찾았습니다.**")
            hit_options = [f"{item['title']} ➔ [{item['price']:,}원]" for item in smart_hits]
            hit_options.insert(0, "선택 안 함 (직접 입력)")
            
            selected_hit = st.selectbox("가장 적합한 물가지 항목을 선택하시면 단가에 자동 입력됩니다.", hit_options)
            if selected_hit != "선택 안 함 (직접 입력)":
                hit_idx = hit_options.index(selected_hit) - 1
                auto_selected_price = smart_hits[hit_idx]['price']
                st.info(f"선택한 추천 단가 **{auto_selected_price:,.0f}원**이 물가정보 단가란에 자동 설정되었습니다.")
        else:
            st.warning("⚪ **참조 물가지에서 일치하는 추천 단가를 찾지 못했습니다.** (아래에서 직접 입력해 주세요)")
            
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
                
                diff_bpm = price_quote - bpm_avg
                rate_bpm = (diff_bpm / bpm_avg) * 100
                if price_quote <= bpm_avg:
                    st.success(f"🟢 **[사내 이력 대비]** 평균가({bpm_avg:,.0f}원) 대비 **{abs(rate_bpm):.1f}% 저렴 (적정)**")
                elif price_quote <= bpm_max:
                    st.warning(f"🟡 **[사내 이력 대비]** 평균가 대비 **{rate_bpm:.1f}% 높음** (과거 최고가 이내)")
                else:
                    st.error(f"🔴 **[사내 이력 대비]** 과거 최고가({bpm_max:,.0f}원) 초과 **(고가 주의)**")

                if price_info > 0:
                    diff_info = price_quote - price_info
                    rate_info = (diff_info / price_info) * 100
                    if price_quote <= price_info:
                        st.success(f"🟢 **[물가정보]** 공인가({price_info:,.0f}원) 대비 **{abs(rate_info):.1f}% 저렴 (적정)**")
                    else:
                        st.error(f"🔴 **[물가정보]** 공인가({price_info:,.0f}원) 대비 **{rate_info:.1f}% 비쌈**")

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

    elif page == "📄 업체 견적서 일괄 검토":
        st.subheader("📄 업체 제출 견적서 자동 일괄 검토")
        st.caption("업체에서 제출한 엑셀 견적서를 업로드하면, 공단 사내 단가 DB와 비교하여 적정성을 검토합니다.")
        
    else:
        st.subheader("📊 사내 자재 현황 및 데이터 분석")

except Exception as e:
    st.error(f"시스템 오류 발생: {e}")