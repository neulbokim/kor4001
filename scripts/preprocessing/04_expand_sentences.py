#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
04. 문장 단위 확장 (Sentence Expansion)

03_process_morph.py에서 생성한 문장별 분석 결과를
개별 행으로 확장합니다.

Input: data/processed/all_communities_morph.csv (sentence_results 컬럼 포함)
Output: data/processed/all_communities_expanded.csv (문장별로 확장된 데이터)
"""

import pandas as pd
import json
from pathlib import Path
from tqdm import tqdm
import sys

import argparse

# 어미 정규화 매핑 (분석 시 같은 것으로 취급할 어미들)
ENDING_MAPPING = {
    'ㅁ': '(으)ㅁ',
    '음': '(으)ㅁ',
    '임': '(으)ㅁ',
    'ㄴ': '(으)ㄴ',
    '은': '(으)ㄴ',
    'ㄹ': '(으)ㄹ',
    '을': '(으)ㄹ',
    'ㄹ까': '(으)ㄹ까',
    '을까': '(으)ㄹ까',
    'ㅂ니다': 'ㅂ니다',
    '습니다': 'ㅂ니다',
    '어라': '어/아라',
    '아라': '어/아라',
    '라': '어/아라',
    '어': '어/아',
    '아': '어/아',
    '은데': '(으)ㄴ데',
    'ㄴ데': '(으)ㄴ데',
    '어서': '어/아서',
    '아서': '어/아서',
}

def normalize_ending(ending):
    """종결 어미를 정규화합니다."""
    return ENDING_MAPPING.get(ending, ending)

print(f"ℹ️ 어미 정규화 매핑 로드 완료: {len(ENDING_MAPPING)}개 패턴")


def main():
    parser = argparse.ArgumentParser(description="문장 단위 확장 스크립트")
    parser.add_argument("--gallery", type=str, help="특정 갤러리/커뮤니티만 처리 (파일명에 포함된 문자열)")
    args = parser.parse_args()

    print("=" * 60)
    print("문장 단위 확장 (Expand Sentences)")
    if args.gallery:
        print(f"필터 적용: '{args.gallery}'")
    print("=" * 60)

    input_dir = Path("data/processed/morph")
    output_dir = Path("data/processed/expanded")
    output_dir.mkdir(parents=True, exist_ok=True)

    all_files = list(input_dir.glob("morph_*.csv"))
    if args.gallery:
        input_files = [f for f in all_files if args.gallery in f.name]
    else:
        input_files = all_files
    
    if not input_files:
        print(f"❌ 처리할 파일이 없습니다. (필터: {args.gallery})")
        print("먼저 scripts/preprocessing/03_process_morph.py를 실행하세요.")
        return
    
    print(f"발견된 파일: {len(input_files)}개")
    
    for input_path in input_files:
        print(f"\n처리 중: {input_path.name}")
        
        community_name = input_path.stem.replace("morph_", "")
        output_filename = f"expanded_{community_name}.csv"
        output_path = output_dir / output_filename
        
        print(f"데이터 로드 중: {input_path}")
        df = pd.read_csv(input_path)
        print(f"로드된 행 수: {len(df)}")
        
        # sentence_results를 파싱하여 개별 행으로 확장
        print("문장 단위로 확장 중...")
        new_rows = []
        
        for _, row in tqdm(df.iterrows(), total=len(df), desc=f"{community_name} 확장"):
            try:
                sentence_results = json.loads(row['morph_results'])
                
                timestamp_value = row.get('timestamp', row.get('posted_at'))
                if timestamp_value is None:
                    timestamp_value = ''
    
                if sentence_results:
                    seen_sentences = set()
                    for sent_res in sentence_results:
                        sentence_text = sent_res.get('sentence', row['full_text'])
                        if sentence_text in seen_sentences:
                            continue
                        seen_sentences.add(sentence_text)
                        # 어미 정규화 적용 (morph, tag, prob, oov)
                        normalized_endings = [
                            (normalize_ending(e[0]), e[1], e[2], e[3]) if len(e) >= 4
                            else (normalize_ending(e[0]), e[1]) if len(e) >= 2
                            else e
                            for e in sent_res['endings']
                        ]
                        new_row = {
                            'community': row['community'],
                            'full_text': row['full_text'],
                            'timestamp': timestamp_value,
                            'sentence': sentence_text,
                            'all_endings': json.dumps(normalized_endings, ensure_ascii=False),
                            'intent': '',
                            'punctuation': json.dumps(sent_res['punctuation'], ensure_ascii=False),
                            'symbols': json.dumps(sent_res['other_symbols'], ensure_ascii=False),
                            'min_prob': sent_res.get('min_prob', 1.0),
                            'last_token_prob': sent_res.get('last_token_prob', 1.0),
                            'has_oov': sent_res.get('has_oov', False),
                            'needs_manual_intent': sent_res.get('needs_manual_intent', False),
                        }
                        new_rows.append(new_row)
                else:
                    # 분석 결과가 없는 경우
                    new_row = {
                        'community': row['community'],
                        'full_text': row['full_text'],
                        'timestamp': timestamp_value,
                        'sentence': row.get('full_text', ''),
                        'all_endings': '[]',
                        'intent': '',
                        'punctuation': '[]',
                        'symbols': '[]',
                        'min_prob': 1.0,
                        'last_token_prob': 1.0,
                        'has_oov': False,
                        'needs_manual_intent': True,
                    }
                    new_rows.append(new_row)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"\n⚠️  경고: 행 파싱 오류 - {e}")
                continue
        
        # 새로운 DataFrame 생성
        expanded_df = pd.DataFrame(new_rows)
        
        print(f"확장 완료:")
        print(f"  원본 행 수: {len(df)}")
        print(f"  확장 후 행 수: {len(expanded_df)}")
        
        # 저장
        expanded_df.to_csv(output_path, index=False, encoding='utf-8')
        print(f"  -> 저장 완료: {output_path}")
    
    print("\n" + "=" * 60)
    print("✅ 문장 단위 확장 완료!")
    print("=" * 60)

if __name__ == "__main__":
    main()
