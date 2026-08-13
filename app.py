import streamlit as st
import pandas as pd
import re
import os
import glob

# 1. PAGE CONFIG (반드시 최상단에 위치)
st.set_page_config(
    page_title="BECO BPM - 자재 단가 검증 시스템", 
    layout="wide", 
    page_icon="🌿",
    initial_sidebar_state="expanded"
)

# pdfplumber 안전 로드
try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

# ----------------------------------------------------
# 🎨 CSS 스타일링
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
# 📦 사내 자재 DB 로드 (안전 처리)
# ----------------------------------------------------
@st.cache_data(show_spinner=False)
def load_bpm_data():
    excel_path = '2025년 자재원본.xlsx'
    if not os.path.exists(excel_path):
        return None, f"❌ '{excel_path}' 파일을 찾을 수 없습니다. GitHub 저장소 루트에 업로드되어 있는지 확인해 주세요."

    try:
        df = pd.read_excel(excel_path, sheet_name='Data', header=2)
        df = df[df['입고단가'].notnull() & (df['입고단가'] > 0)]
        
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

        stats = df.groupby(['자재명', '자재규격']).apply(calc_trimmed_stats).reset_index()
        stats['검색용'] = stats['자재명'].astype(str) + " | " + stats['자재규격'].astype(str)
        return stats, None
    except Exception as e:
        return None, f"❌ 엑셀 데이터 읽기 오류: {str(e)}"


# ----------------------------------------------------
# 📚 참조 물가지 PDF 자동 색인
# ----------------------------------------------------
@st.cache_data(show_spinner=False)
def load_and_index_reference_pdfs():
    if not HAS_PDF:
        return []
        
    pdf_files = glob.glob("*.pdf")
    pdf_files = [f for f in sorted(pdf_files) if '2025년 자재원본' not in f]
    
    indexed_data = []
    for f_path in pdf_files[:2]:  # 메모리 보호를 위해 최대 2개 PDF만 파싱
        try:
            file_name = os.path.basename(f_path)
            with pdfplumber.open(f_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        lines = text.split('\n')
                        printed_page = f"{page_num}p"
                        for head_line in lines[:2]:
                            page_match = re.search(r'\b([1-9]\d{2,3})\b', head_line)
                            if page_match:
                                printed_page = f"페이지 {page_match.group(1)}"
                                break

                        current_header = ""
                        for line in lines:
                            clean_line = line.strip()
                            if clean_line:
                                norm_line = re.sub(r'\s+', '', clean_line).upper()
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


def search_in_indexed_pdfs(target_material, target_spec):
    indexed_lines = load_and_index_reference_pdfs()
    if not indexed_lines:
        return []

    ko_raw = re.findall(r'[가-힣]+', target_material)
    ko_keywords = [re.sub(r'\s+', '', k) for k in ko_raw if len(re.sub(r'\s+', '', k)) >= 2]
    if '볼베어링' in target_material or '베어링' in target_material:
        ko_keywords.append('베어링')

    spec_numbers = re.findall(r'\d+', target_spec)
    spec_letters = re.findall(r'[a-zA-Z]+', target_spec)

    candidates = []
    for item in indexed_lines:
        norm_line = item['norm_text']
        header = item['header']
        orig_text = item['text']
        
        if ko_keywords and not any(k in norm_line or k in header for k in ko_keywords):
            continue

        score = 10
        if spec_numbers:
            matched_num_count = sum(1 for num in spec_numbers if re.search(r'(?<!\d)' + re.escape(num) + r'(?!\d)', norm_line))
            if matched_num_count == 0:
                continue
            score += matched_num_count * 10

        for a in spec_letters:
            if a.upper() in norm_line:
                score += 5

        numbers = re.findall(r'\b\d{1,3}(?:,\d{3})+\b|\b\d{4,9}\b', orig_text)
        clean_nums = [int(n.replace(',', '')) for n in numbers if int(n.replace(',', '')) >= 500]
        
        if clean_nums:
            short_fname = item['file'].replace('.pdf', '')
            selected_price = clean_nums[0]
            if 'ZZ' in target_spec.upper() and len(clean_nums) >= 2:
                selected_price = clean_nums[1]

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


# ----------------------------------------------------
# 🚀 메인 애플리케이션 UI
# ----------------------------------------------------
st.markdown("""
<div class="beco-header">
    <h1>🌿 부산환경공단 BPM (Beco Parts Master)</h1>
    <p>자재 수불 이력 기반 공정·투명 계약지원 시스템 | 기술개발 및 단가심사 자동화</p>
</div>
""", unsafe_allow_html=True)

stats_df, err_msg = load_bpm_data()

if err_msg:
    st.error(err_msg)
    st.info("💡 **조치 필요**: GitHub 저장소에 `2025년 자재원본.xlsx` 파일 및 `requirements.txt` 파일이 정위치에 있는지 확인해 주세요.")
else:
    st.sidebar.markdown("## 🌿 BECO BPM 메뉴")
    page = st.sidebar.radio("기능을 선택하세요", ["🔍 단 품목 단가 검증", "📄 업체 견적서 일괄 검토", "📊 자재 데이터 분석"])
    st.sidebar.caption("DB 기준: 자재 실시간 입고이력")
    st.sidebar.markdown("---")

    if page == "🔍 단 품목 단가 검증":
        st.sidebar.markdown("### ⭐ 다빈도 구매 자재 (TOP 30)")
        top30_df = stats_df.sort_values(by='이력건수', ascending=False).head(30)
        selected_from_sidebar = st.sidebar.selectbox("목록에서 빠른 선택", top30_df['검색용'].tolist())

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
                    st.warning("일치하는 자재가 없습니다.")
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
        m3.metric("과거 최저 단가", f"{bpm_min:,.0f} 원")
        if min_vendor:
            m3.caption(f"🏢 최저가 납품: **{min_vendor}**")
        else:
            m3.caption("🏢 최저가 납품: 정보 없음")
            
        m4.metric("과거 최고 단가", f"{bpm_max:,.0f} 원")

        st.markdown("<br>", unsafe_allow_html=True)

        # PDF 탐색
        smart_hits = search_in_indexed_pdfs(selected_material, selected_spec)
        auto_selected_price = 0

        st.markdown('<div class="custom-card" style="border-left: 5px solid #1e88e5;">', unsafe_allow_html=True)
        st.markdown("#### 💡 참조 물가지 자동 탐색 및 추천 단가")
        
        if smart_hits:
            st.success(f"🟢 **총 {len(smart_hits)}건의 물가지 추천 단가를 찾았습니다.**")
            hit_options = [f"{item['title']} ➔ [{item['price']:,}원]" for item in smart_hits]
            hit_options.insert(0, "선택 안 함 (직접 입력)")
            
            selected_hit = st.selectbox("추천 항목을 선택하시면 단가가 자동 설정됩니다.", hit_options)
            if selected_hit != "선택 안 함 (직접 입력)":
                hit_idx = hit_options.index(selected_hit) - 1
                auto_selected_price = smart_hits[hit_idx]['price']
        else:
            st.info("⚪ 참조 물가지에서 일치하는 자동 추천 단가가 없습니다. 직접 입력해 주세요.")
            
        st.markdown('</div>', unsafe_allow_html=True)

        # 단가 입력 및 판정
        col_input, col_result = st.columns([1, 1.2])
        
        with col_input:
            st.markdown('<div class="custom-card">', unsafe_allow_html=True)
            st.markdown("#### 💳 비교 단가 입력")
            
            price_info = st.number_input("📑 물가정보 공인 단가 (원)", min_value=0, value=auto_selected_price, step=1000)
            price_data = st.number_input("📑 물가자료 공인 단가 (원)", min_value=0, value=0, step=1000)
            
            st.markdown("""
            <div class="quote-box">
                <div class="quote-title">🟦 구매 / 견적 예정 단가 (검토 대상)</div>
            </div>
            """, unsafe_allow_html=True)
            
            price_quote = st.number_input("구매견적가 입력 (원)", min_value=0, value=bpm_avg, step=1000, label_visibility="collapsed")
            
            if price_quote > 0 and price_info == 0 and price_data == 0:
                st.warning("⚠️ **알림**: 물가정보/물가자료 단가가 입력되지 않았습니다. 공인 단가지 검토 여부를 확인해 주세요.")

            st.markdown('</div>', unsafe_allow_html=True)

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

    elif page == "📄 업체 견적서 일괄 검토":
        st.subheader("📄 업체 제출 견적서 자동 일괄 검토")
    else:
        st.subheader("📊 사내 자재 현황 및 데이터 분석")