import os
import pandas as pd
from typing import Optional

# ==========================================
# 1. 설정 및 메인 실행부
# ==========================================
def main():
    # 파일 경로 및 설정
    file_path: str = "data.csv"  # 대상 파일 경로
    encoding: str = "utf-8"     # 파일 인코딩 (한글 환경에 따라 'utf-8-sig' 또는 'euc-kr' 변경 가능)

    # 데이터 로드
    df: Optional[pd.DataFrame] = load_data(file_path, encoding=encoding)

    if df is not None:
        # 데이터 전처리 및 변환
        processed_df: pd.DataFrame = process_data(df)

        # 결과 출력 및 저장
        print("=== 처리 완료 데이터 상위 5건 ===")
        print(processed_df.head())

        # 결과 파일 저장
        output_path: str = "processed_data.csv"
        save_data(processed_df, output_path, encoding=encoding)


# ==========================================
# 2. 데이터 입출력 함수
# ==========================================
def load_data(file_path: str, encoding: str = "utf-8") -> Optional[pd.DataFrame]:
    """
    지정한 경로에서 데이터를 읽어와 DataFrame으로 반환합니다.
    """
    if not os.path.exists(file_path):
        print(f"[Error] 파일을 찾을 수 없습니다: {file_path}")
        return None

    try:
        df = pd.read_csv(file_path, encoding=encoding)
        print(f"[Success] 데이터 로드 성공: {df.shape[0]}행 {df.shape[1]}열")
        return df
    except Exception as e:
        print(f"[Error] 데이터 읽기 실패: {e}")
        return None


def save_data(df: pd.DataFrame, output_path: str, encoding: str = "utf-8") -> None:
    """
    DataFrame을 CSV 파일로 저장합니다.
    """
    try:
        df.to_csv(output_path, index=False, encoding=encoding)
        print(f"[Success] 저장 완료: {output_path}")
    except Exception as e:
        print(f"[Error] 데이터 저장 실패: {e}")


# ==========================================
# 3. 데이터 처리 핵심 로직
# ==========================================
def process_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    데이터 정제, 가공 및 계산 로직을 수행합니다.
    """
    # 원본 보호를 위한 복사본 생성
    df_clean = df.copy()

    # 1) 결측치 처리 (필요에 따라 수정)
    df_clean = df_clean.dropna(subset=df_clean.columns[:1])  # 주요 컬럼 결측치 제거
    df_clean = df_clean.fillna(0)                           # 수치형 결측치 0 채움

    # 2) 데이터 타입 정리 및 가공 예시
    # (프로젝트 요구사항에 맞는 로직을 이곳에 추가하시면 됩니다)

    return df_clean


if __name__ == "__main__":
    main()