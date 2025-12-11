#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02. Bareun 태깅

Cleaned 데이터를 Bareun API로 태깅하여 문장별 토큰을 저장합니다.

Input: data/preprocessed/all_communities_cleaned.csv
Output: data/processed/all_communities_tagged.csv
"""

import json
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from utils.bareun_analyzer import BareunAnalyzer
from utils.morph_analyzer import MorphAnalyzer


import argparse

def main():
    parser = argparse.ArgumentParser(description="Bareun 형태소 분석 태깅 스크립트")
    parser.add_argument("--gallery", type=str, help="특정 갤러리/커뮤니티만 처리 (파일명에 포함된 문자열)")
    args = parser.parse_args()

    print("=" * 60)
    print("Bareun 형태소 분석 태깅")
    if args.gallery:
        print(f"필터 적용: '{args.gallery}'")
    print("=" * 60)

    input_dir = Path("data/preprocessed")
    output_dir = Path("data/processed/tagged")
    output_dir.mkdir(parents=True, exist_ok=True)

    all_files = list(input_dir.glob("cleaned_*.csv"))
    if args.gallery:
        input_files = [f for f in all_files if args.gallery in f.name]
    else:
        input_files = all_files
    
    if not input_files:
        print(f"❌ 처리할 파일이 없습니다. (필터: {args.gallery})")
        print("먼저 scripts/preprocessing/01_clean_data.py를 실행하세요.")
        return

    print(f"발견된 파일: {len(input_files)}개")
    
    analyzer = BareunAnalyzer()
    splitter = MorphAnalyzer()

    for input_path in input_files:
        print(f"\n처리 중: {input_path.name}")
        
        # Extract community name from filename (cleaned_{community}.csv)
        community_name = input_path.stem.replace("cleaned_", "")
        output_filename = f"tagged_{community_name}.csv"
        output_path = output_dir / output_filename
        
        df = pd.read_csv(input_path)
        tagged_rows = []
        
        for _, row in tqdm(df.iterrows(), total=len(df), desc=f"{community_name} 태깅"):
            full_text = str(row.get('full_text', '') or '')
            sentences = splitter.split_sentences(full_text)
    
            sentence_segments = []
            if sentences:
                for sentence in sentences:
                    tokens = analyzer.analyze(sentence)
                    sentence_segments.append({
                        'sentence': sentence,
                        'tokens': [list(token) for token in tokens]
                    })
            elif full_text:
                tokens = analyzer.analyze(full_text)
                sentence_segments.append({
                    'sentence': full_text,
                    'tokens': [list(token) for token in tokens]
                })
    
            tagged_rows.append({
                'community': row.get('community', ''),
                'title': row.get('title', ''),
                'content': row.get('content', ''),
                'full_text': full_text,
                'posted_at': row.get('posted_at', row.get('timestamp', '')),
                'sentence_segments': json.dumps(sentence_segments, ensure_ascii=False)
            })
    
        tagged_df = pd.DataFrame(tagged_rows)
        tagged_df.to_csv(output_path, index=False, encoding='utf-8')
        print(f"  -> 저장 완료: {output_path}")

    print("\n" + "=" * 60)
    print("✅ Bareun 태깅 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()
