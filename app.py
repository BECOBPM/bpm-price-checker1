import streamlit as st
import pandas as pd
import numpy as np
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
    page_title="BECO BPM - 부산환경공단 자재 단가 심사 시스템", 
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
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------
# 📦 1순위: 사내 자재 입고 원본 DB 로드 (2025년 자재원본.xlsx)
# ----------------------------------------------------
@st.cache_data
def load_bpm_master_data():
    file_path = '2025년 자재원본.xlsx'
    if not os.path.exists(file_path):
        return pd.DataFrame(), pd.DataFrame()
        
    df = pd.read_excel(file_path, sheet_name='Data', header=2)
    df = df[df['입고단가'].notnull() & (df['입고단가'] > 0)]
    
    # 분야(기계/전기/환경) 자동 분류 컬럼 생성
    def classify_category(row):
        name = str(row['자재명'])
        code = str(row['자재코드'])
        if '전기' in name or code.startswith('02'):
            return '전기'
        elif '환경' in name or '약품' in name or '응집제' in name or code.startswith('03'):
            return '환경'
        else:
            return '기계'

    df['분류'] = df.apply(classify_category, axis=1)
    
    def calc_trimmed_stats(g):
        prices = g['입고단가'].dropna().tolist()
        prices.sort()
        n = len(prices)
        if n == 0:
            return pd.Series({'이력건수': 0, '평균단가': 0, '최소단가': 0, '최대단가': 0, '대표분류': '기계'})
        min_p, max_p = prices[0], prices[-1]
        
        if n >= 5:
            avg_p = sum(prices[1:-1]) / len(prices[1:-1])
        else:
            avg_p = sum(prices) / n
            
        cat = g['분류'].iloc[0]
        return pd.Series({
            '이력건수': n, '평균단가': round(avg_p), '최소단가': min_p, '최대단가': max_p, '대표분류': cat
        })

    stats = df.groupby(['자재명', '자재규격'], group_keys=False).apply(calc_trimmed_stats).reset_index()
    stats['검색용'] = stats['자재명'].astype(str) + " | " + stats['자재규격'].astype(str)
    return stats, df


# ----------------------------------------------------
# 📚 2순위: 물가지 백그라운드 자동 로드 (엑셀 및 PDF 통합)
# ----------------------------------------------------
@st.cache_data
def load_price_index_db():
    mulga_dict = {}
    excel_files = glob.glob("종합물가정보*.xlsx") + glob.glob("*.xlsx")
    for f in excel_files:
        if '2025년 자재원본' in f:
            continue
        try:
            xls = pd.ExcelFile(f)
            for sheet in xls.sheet_names:
                df_s = pd.read_excel(xls, sheet_name=sheet)
                for _, row in df_s.iterrows():
                    row_str = " ".join([str(val) for val in row.values if pd.notna(val)])
                    nums = re.findall(r'\b\d{1,3}(?:,\d{3})+\b|\b\d{4,9}\b', row_str)
                    if nums:
                        price_val = int(nums[-1].replace(',', ''))
                        if price_val >= 500:
                            mulga_dict[row_str[:50]] = price_val
        except Exception:
            continue
    return mulga_dict


try:
    stats_df, raw_history_df = load_bpm_master_data()
    mulga_database = load_price_index_db()

    # 사이드바 메뉴
    st.sidebar.markdown("## 🌿 BECO BPM 메뉴")
    page = st.sidebar.radio(
        "기능을 선택하세요", 
        [
            "🔍 단 품목 단가 검증", 
            "📈 분야별 다빈도 자재 (TOP 30)", 
            "📋 단가계약 가능 품목 리스트", 
            "📄 업체 견적서 일괄 심사",
            "📊 사내 자재 현황 분석"
        ]
    )
    st.sidebar.caption("DB 기준: 2025년 자재 수불 원본 이력 (8,418건)")
    st.sidebar.markdown("---")
    st.sidebar.success(f"사내 마스터 DB 연동 완료 ({len(stats_df):,}개 품목)")

    # 상단 배너 (BPM 타이틀 적용)
    st.markdown("""
    <div class="beco-header">
        <h1>🌿 부산환경공단 BPM (Beco Parts Master)</h1>
        <p>자재 수불 이력 기반 공정·투명 계약지원 시스템 | 기술개발 및 단가심사 자동화</p>
    </div>
    """, unsafe_allow_html=True)

    # ====================================================
    # 🌟 1. 단 품목 단가 검증
    # ====================================================
    if page == "🔍 단 품목 단가 검증":
        if stats_df.empty:
            st.warning("사내 자재 DB 파일('2025년 자재원본.xlsx')을 찾을 수 없습니다.")
        else:
            st.sidebar.markdown("### ⭐ 다빈도 구매 자재 (TOP 30)")
            top30_sidebar = stats_df.sort_values(by='이력건수', ascending=False).head(30)
            selected_from_sidebar = st.sidebar.selectbox("빠른 선택", top30_sidebar['검색용'].tolist())

            st.markdown('<div class="custom-card">', unsafe_allow_html=True)
            c1, c2 = st.columns([1.5, 1.5])
            with c1:
                search_kw = st.text_input("🔍 자재명 또는 규격 검색", "", placeholder="예: 파이프, 엘보, 볼베어링, 밸브").strip()
            with c2:
                if search_kw:
                    filtered = stats_df[stats_df['검색용'].str.contains(search_kw, case=False, na=False)]
                    selected_item = st.selectbox(f"검색 결과 ({len(filtered)}건)", filtered['검색용'].tolist()) if not filtered.empty else selected_from_sidebar
                else:
                    selected_item = selected_from_sidebar
                    st.selectbox("선택 자재 (TOP 30 연동)", [selected_item], disabled=True)
            st.markdown('</div>', unsafe_allow_html=True)

            target = stats_df[stats_df['검색용'] == selected_item].iloc[0]
            mat_name, mat_spec = target['자재명'], target['자재규격']
            cnt, avg_p, min_p, max_p, cat = int(target['이력건수']), int(target['평균단가']), int(target['최소단가']), int(target['최대단가']), target['대표분류']

            st.markdown(f"### 📦 선택 품목: **[{mat_name}]** `({mat_spec})` — <span style='color:#1e88e5; font-size:18px;'>[{cat} 분야]</span>", unsafe_allow_html=True)
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("사내 구매 이력", f"{cnt:,} 건")
            m2.metric("사내 평균 단가 (절사)", f"{avg_p:,.0f} 원")
            m3.metric("과거 최저 단가", f"{min_p:,.0f} 원")
            m4.metric("과거 최고 단가", f"{max_p:,.0f} 원")

            st.markdown("<br>", unsafe_allow_html=True)

            col_in, col_out = st.columns([1, 1.2])
            with col_in:
                st.markdown('<div class="custom-card">', unsafe_allow_html=True)
                st.markdown("#### 💳 비교 및 검토 단가 입력")
                with st.form(key='single_check'):
                    p_info = st.number_input("📑 물가정보/물가자료 단가 (원)", min_value=0, value=0, step=1000)
                    p_quote = st.number_input("🟦 구매 견적 예정 단가 (원)", min_value=0, value=avg_p, step=1000)
                    sub_btn = st.form_submit_button("🔍 적정성 판정 실행", use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

            with col_out:
                st.markdown('<div class="custom-card">', unsafe_allow_html=True)
                st.markdown("#### 🎯 적정성 종합 판정")
                if p_quote > 0:
                    diff = p_quote - avg_p
                    rate = (diff / avg_p) * 100
                    if p_quote <= avg_p:
                        st.success(f"🟢 **적정**: 사내 평균가({avg_p:,.0f}원) 대비 **{abs(rate):.1f}% 저렴**합니다.")
                    elif p_quote <= max_p:
                        st.warning(f"🟡 **검토필요**: 사내 평균가 대비 **{rate:.1f}% 높음** (과거 최고가 이내)")
                    else:
                        st.error(f"🔴 **단가초과**: 과거 최고가({max_p:,.0f}원)를 초과하여 고가 주의 대상입니다.")
                        
                    if p_info > 0:
                        diff_i = p_quote - p_info
                        rate_i = (diff_i / p_info) * 100
                        if p_quote <= p_info:
                            st.success(f"🟢 물가정보 공인가({p_info:,.0f}원) 대비 적정 범위입니다.")
                        else:
                            st.error(f"🔴 물가정보 공인가 대비 **{rate_i:.1f}% 비쌉니다.**")
                else:
                    st.info("검토할 구매견적 단가를 입력해 주세요.")
                st.markdown('</div>', unsafe_allow_html=True)

    # ====================================================
    # 🌟 2. 분야별 다빈도 자재 (기계/전기/환경 TOP 30)
    # ====================================================
    elif page == "📈 분야별 다빈도 자재 (TOP 30)":
        st.subheader("📈 분야별 최다 구매 자재 순위 (기계 / 전기 / 환경 TOP 30)")
        st.write("사내 입고 이력을 바탕으로 각 분야별 가장 빈번하게 수급되는 핵심 자재를 집계합니다.")
        
        tab_mech, tab_elec, tab_env = st.tabs(["⚙️ 기계 분야", "⚡ 전기 분야", "🌿 환경 분야"])
        
        def show_top30_table(category_name):
            sub_df = stats_df[stats_df['대표분류'] == category_name].sort_values(by='이력건수', ascending=False).head(30).copy()
            sub_df.insert(0, '순위', range(1, len(sub_df) + 1))
            st.dataframe(
                sub_df[['순위', '자재명', '자재규격', '이력건수', '평균단가', '최소단가', '최대단가']].style.format({
                    '이력건수': '{:,} 건',
                    '평균단가': '{:,.0f} 원',
                    '최소단가': '{:,.0f} 원',
                    '최대단가': '{:,.0f} 원'
                }),
                use_container_width=True,
                hide_index=True
            )

        with tab_mech:
            show_top30_table('기계')
        with tab_elec:
            show_top30_table('전기')
        with tab_env:
            show_top30_table('환경')

    # ====================================================
    # 🌟 3. 단가계약 가능 품목 리스트
    # ====================================================
    elif page == "📋 단가계약 가능 품목 리스트":
        st.subheader("📋 공단 단가계약 추천 대상 품목 리스트")
        st.write("연간 반복 구매 횟수가 많거나(3회 이상) 수급 빈도가 높은 자재를 추출하여 단가계약 체결 검토를 지원합니다.")
        
        contract_targets = stats_df[stats_df['이력건수'] >= 3].sort_values(by='이력건수', ascending=False).copy()
        contract_targets.insert(0, 'NO', range(1, len(contract_targets) + 1))
        
        st.metric("단가계약 검토 대상 품목 수", f"{len(contract_targets):,} 개 품목")
        st.markdown("---")
        
        st.dataframe(
            contract_targets[['NO', '대표분류', '자재명', '자재규격', '이력건수', '평균단가', '최소단가', '최대단가']].style.format({
                '이력건수': '{:,} 회',
                '평균단가': '{:,.0f} 원',
                '최소단가': '{:,.0f} 원',
                '최대단가': '{:,.0f} 원'
            }),
            use_container_width=True,
            hide_index=True
        )

    # ====================================================
    # 🌟 4. 업체 견적서 일괄 심사 (표준 양식 기반)
    # ====================================================
    elif page == "📄 업체 견적서 일괄 심사":
        st.subheader("📄 업체 제출 견적서 표준 양식 일괄 심사")
        st.write("업체가 제출한 견적서 엑셀을 업로드하면, 사내 마스터 DB(8,418건)와 즉시 교차 대조하여 적정성을 판정하고 예상 예산 절감액을 산출합니다.")
        
        sample_template = pd.DataFrame({
            "품목명": ["스텐 배관 파이프", "볼베어링"],
            "규격": ["STS304 50A", "6302ZZ"],
            "수량": [10, 50],
            "견적단가": [125000, 2800]
        })
        buffer_tpl = io.BytesIO()
        with pd.ExcelWriter(buffer_tpl, engine='openpyxl') as writer:
            sample_template.to_excel(writer, index=False, sheet_name='견적서양식')
        
        st.download_button(
            label="📥 [표준 견적서 양식 엑셀 다운로드]",
            data=buffer_tpl.getvalue(),
            file_name="BECO_표준견적서_양식.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.markdown("---")
        uploaded_quote = st.file_uploader("📁 작성된 업체 견적서 엑셀 업로드 (.xlsx)", type=["xlsx", "xls"])
        
        if uploaded_quote:
            try:
                q_df = pd.read_excel(uploaded_quote)
                st.success(f"견적서 파일 업로드 완료: {uploaded_quote.name} (총 {len(q_df):,}개 품목)")
                
                cols = list(q_df.columns)
                def get_col_idx(kws):
                    for i, c in enumerate(cols):
                        if any(w in str(c).lower() for w in kws):
                            return i
                    return 0

                c1, c2, c3, c4 = st.columns(4)
                with c1: col_name = st.selectbox("품목명 컬럼", cols, index=get_col_idx(['품목', '자재', '품명', 'name']))
                with c2: col_spec = st.selectbox("규격 컬럼", cols, index=get_col_idx(['규격', 'spec']))
                with c3: col_qty = st.selectbox("수량 컬럼", cols, index=get_col_idx(['수량', 'qty']))
                with c4: col_price = st.selectbox("견적단가 컬럼", cols, index=get_col_idx(['단가', '견적', 'price']))
                
                if st.button("🚀 견적서 적정성 일괄 심사 실행", use_container_width=True):
                    results = []
                    for _, row in q_df.iterrows():
                        name = str(row[col_name]).strip()
                        spec = str(row[col_spec]).strip()
                        qty = float(row[col_qty]) if pd.notna(row[col_qty]) else 0
                        q_price = float(row[col_price]) if pd.notna(row[col_price]) else 0
                        
                        match_item = stats_df[(stats_df['자재명'] == name) & (stats_df['자재규격'] == spec)]
                        if match_item.empty:
                            match_item = stats_df[stats_df['자재명'].str.contains(name[:2], na=False)]
                            
                        if not match_item.empty:
                            rec_price = int(match_item.iloc[0]['평균단가'])
                            max_limit = int(match_item.iloc[0]['최대단가'])
                        else:
                            rec_price = q_price
                            max_limit = q_price
                            
                        q_total = qty * q_price
                        rec_total = qty * rec_price
                        saving = max(0, q_total - rec_total)
                        
                        if match_item.empty:
                            status = "⚪ 기준미확인"
                        elif q_price <= rec_price:
                            status = "🟢 적정"
                        elif q_price <= max_limit:
                            status = "🟡 검토필요"
                        else:
                            status = "🔴 단가초과"
                            
                        results.append({
                            "품목명": name, "규격": spec, "수량": qty, "견적단가": q_price,
                            "사내기준단가": rec_price, "견적합계": q_total, "기준합계": rec_total,
                            "판정": status, "예상절감액": saving
                        })
                        
                    res_df = pd.DataFrame(results)
                    
                    tot_q_amt = res_df['견적합계'].sum()
                    tot_r_amt = res_df['기준합계'].sum()
                    tot_saving = res_df['예상절감액'].sum()
                    
                    st.markdown("### 📊 일괄 심사 결과 요약 (KPI)")
                    k1, k2, k3 = st.columns(3)
                    k1.metric("총 견적 금액", f"{int(tot_q_amt):,} 원")
                    k2.metric("사내 기준 총액", f"{int(tot_r_amt):,} 원")
                    k3.metric("총 예상 절감액", f"{int(tot_saving):,} 원", delta="예산 최적화 성과")
                    
                    st.markdown("---")
                    st.dataframe(
                        res_df.style.format({
                            '수량': '{:,}', '견적단가': '{:,} 원', '사내기준단가': '{:,} 원',
                            '견적합계': '{:,} 원', '기준합계': '{:,} 원', '예상절감액': '{:,} 원'
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
            except Exception as e:
                st.error(f"견적서 처리 중 오류 발생: {e}")

    # ====================================================
    # 🌟 5. 사내 자재 현황 분석
    # ====================================================
    else:
        st.subheader("📊 사내 자재 수불 이력 종합 분석")
        c1, c2, c3 = st.columns(3)
        c1.metric("총 입고 이력 건수", f"{len(raw_history_df):,} 건")
        c2.metric("등록된 고유 자재 품목", f"{len(stats_df):,} 개")
        c3.metric("총 입고 금액", f"{raw_history_df['입고금액'].sum():,.0f} 원" if '입고금액' in raw_history_df.columns else "계산 중")

except Exception as e:
    st.error(f"시스템 초기화 중 오류 발생: {e}")