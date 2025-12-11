"""
데이터 정제 스크립트
- Raw 데이터에서 영어, 특정 문자열 제거
- 중복 제거
- 정제된 데이터를 data/preprocessed/ 저장
"""
import pandas as pd
import os
import re
from pathlib import Path

def clean_text(text):
    """텍스트에서 영어와 특정 문자열 제거"""
    if not isinstance(text, str):
        return text
    
    # "- dc official App" 제거
    text = re.sub(r'-\s*dc\s+official\s+App', '', text, flags=re.IGNORECASE)
    
    # 영어 알파벳 제거 (한글, 숫자, 특수문자는 유지)
    # 단, URL이나 이메일은 이미 제거되었다고 가정
    text = re.sub(r'[a-zA-Z]+', '', text)
    
    # 연속된 공백을 하나로
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def main():
    print("=" * 60)
    print("데이터 정제 시작")
    print("=" * 60)
    
    # 경로 설정
    raw_dir = Path("data/raw")
    preprocessed_dir = Path("data/preprocessed")
    preprocessed_dir.mkdir(parents=True, exist_ok=True)
    
    # Raw CSV 파일 목록
    csv_files = list(raw_dir.glob("*.csv"))
    
    if not csv_files:
        print(f"오류: {raw_dir}에 CSV 파일이 없습니다.")
        return
    
    print(f"\n발견된 CSV 파일: {len(csv_files)}개")
    
    all_dfs = []
    
    # 각 파일 처리
    for file_path in csv_files:
        print(f"\n처리 중: {file_path.name}")
        try:
            df = pd.read_csv(file_path)
            print(f"  - 로드된 행 수: {len(df)}")
            
            # site와 gallery 컬럼으로 community 생성
            if 'site' in df.columns and 'gallery' in df.columns:
                df['community'] = df['site'] + '_' + df['gallery']
            
            # title과 content 정제
            if 'title' in df.columns:
                df['title'] = df['title'].apply(clean_text)
            
            if 'content' in df.columns:
                df['content'] = df['content'].fillna('')
                df['content'] = df['content'].apply(clean_text)
            
            # full_text 생성 (정제된 title + content)
            df['full_text'] = df['title'].astype(str) + " " + df['content'].astype(str)
            df['full_text'] = df['full_text'].str.strip()
            
            # 필요한 컬럼만 선택
            columns_to_keep = ['community', 'title', 'content', 'full_text', 'posted_at']
            available_columns = [col for col in columns_to_keep if col in df.columns]
            df = df[available_columns]
            
            all_dfs.append(df)
            print(f"  - 정제 완료")
            
        except Exception as e:
            print(f"  - 오류 발생: {e}")
            continue
    
    if not all_dfs:
        print("\n오류: 처리된 데이터가 없습니다.")
        return
    
    # 전체 데이터 병합 (중복 제거를 위해 일단 병합)
    print("\n" + "=" * 60)
    print("데이터 병합 및 중복 제거 중...")
    full_df = pd.concat(all_dfs, ignore_index=True)
    print(f"병합 후 전체 행 수: {len(full_df)}")
    
    # 중복 제거 (전체 기준)
    initial_count = len(full_df)
    full_df = full_df.drop_duplicates(subset=['full_text'], keep='first')
    removed_count = initial_count - len(full_df)
    print(f"제거된 중복 행: {removed_count}개")
    
    # 빈 텍스트 제거
    initial_count = len(full_df)
    full_df = full_df[full_df['full_text'].str.len() > 0]
    removed_count = initial_count - len(full_df)
    print(f"제거된 빈 행: {removed_count}개")
    print(f"최종 전체 행 수: {len(full_df)}")
    
    # 커뮤니티별로 나누어 저장
    print("\n" + "=" * 60)
    print("커뮤니티별 저장 중...")
    
    communities = full_df['community'].unique()
    for community in communities:
        community_df = full_df[full_df['community'] == community]
        safe_community_name = re.sub(r'[^\w\-_]', '_', str(community))
        output_filename = f"cleaned_{safe_community_name}.csv"
        output_path = preprocessed_dir / output_filename
        
        community_df.to_csv(output_path, index=False, encoding='utf-8')
        print(f"  - {community}: {len(community_df)}행 -> {output_path}")

    print("\n" + "=" * 60)
    print("✅ 정제된 데이터 저장 완료")
    print("=" * 60)

if __name__ == "__main__":
    main()
