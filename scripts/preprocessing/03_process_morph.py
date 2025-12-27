#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
03. Morph 후처리

Bareun 태깅 결과에서 종결어미/문장부호/기호를 추출하여
`morph_results`를 생성합니다.

Input: data/processed/all_communities_tagged.csv
Output: data/processed/all_communities_morph.csv
"""

import json
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from utils.morph_analyzer import MorphAnalyzer


import argparse
import sys

# Interactive decision cache
# Key: (morph, tag), Value: 'EF' (change) or 'KEEP' (keep) or 'SKIP' (skip all)
decision_cache = {}
stats = {'corrections': 0}

def interactive_callback(token, context_tokens, index, sentence=None):
    """
    MorphAnalyzer에서 호출하는 대화형 콜백 함수
    """
    morph, tag, prob = token[0], token[1], token[2]
    cache_key = (morph, tag)
    
    if cache_key in decision_cache:
        decision = decision_cache[cache_key]
        if decision == 'KEEP':
            return None
        elif decision == 'SKIP':
            return None
        else:
            # decision is the new tag (e.g., 'EF', 'JX')
            stats['corrections'] += 1
            return decision

    # Show context
    start = max(0, index - 3)
    end = min(len(context_tokens), index + 4)
    context_str = ""
    for i in range(start, end):
        t = context_tokens[i]
        t_str = f"{t[0]}/{t[1]}"
        if i == index:
            t_str = f"[{t_str}]"
        context_str += t_str + " "
    
    print(f"\n[Interactive Check] Ambiguous Token: '{morph}' ({tag}) prob={prob:.4f}")
    if sentence:
        print(f"Full Sentence: \"{sentence}\"")
    print(f"Context: ... {context_str} ...")
    
    while True:
        print("Options:")
        print("  [e] Change to EF")
        print("  [k] Keep (Don't change)")
        print("  [c] Custom Tag")
        print("  [d] Delete Sentence (Remove from dataset)")
        print("  [s] Skip (Don't ask again for this morph)")
        print("  Add 'a' to apply to all (e.g., 'ea', 'ka', 'ca')")
        
        choice = input("Choice: ").strip().lower()
        
        apply_all = False
        if len(choice) > 1 and choice.endswith('a'):
            apply_all = True
            choice = choice[:-1]
            
        if choice == 'e':
            new_tag = 'EF'
            if apply_all:
                decision_cache[cache_key] = new_tag
            stats['corrections'] += 1
            return new_tag
            
        elif choice == 'k':
            if apply_all:
                decision_cache[cache_key] = 'KEEP'
            return None
            
        elif choice == 'd':
            # Delete sentence
            stats['deletions'] = stats.get('deletions', 0) + 1
            return 'DELETE'
            
        elif choice == 's':
            decision_cache[cache_key] = 'SKIP'
            return None
            
        elif choice == 'c':
            new_tag = input("Enter new tag (e.g., JX, MAG): ").strip().upper()
            if not new_tag:
                print("Invalid tag.")
                continue
            if apply_all:
                decision_cache[cache_key] = new_tag
            stats['corrections'] += 1
            return new_tag
            
        else:
            print("Invalid choice.")

def main():
    parser = argparse.ArgumentParser(description="Morph 후처리 스크립트")
    parser.add_argument("--interactive", action="store_true", help="대화형 모드로 실행하여 애매한 태그를 직접 확인합니다.")
    parser.add_argument("--gallery", type=str, help="특정 갤러리/커뮤니티만 처리 (파일명에 포함된 문자열)")
    args = parser.parse_args()

    print("=" * 60)
    print("Morph 후처리 시작")
    if args.interactive:
        print("📢 대화형 모드 활성화: 확률 0.92 이하인 EC 태그에 대해 확인을 요청합니다.")
    if args.gallery:
        print(f"필터 적용: '{args.gallery}'")
    print("=" * 60)

    input_dir = Path("data/processed/tagged")
    output_dir = Path("data/processed/morph")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_files = list(input_dir.glob("tagged_*.csv"))
    if args.gallery:
        input_files = [f for f in all_files if args.gallery in f.name]
    else:
        input_files = all_files
    
    if not input_files:
        print(f"\n❌ 오류: 처리할 파일이 없습니다. (필터: {args.gallery})")
        return

    print(f"발견된 파일: {len(input_files)}개")
    analyzer = MorphAnalyzer()

    for input_path in input_files:
        print(f"\n처리 중: {input_path.name}")
        
        community_name = input_path.stem.replace("tagged_", "")
        output_filename = f"morph_{community_name}.csv"
        output_path = output_dir / output_filename
        
        df = pd.read_csv(input_path)
        
        # Deduplication: Remove rows with duplicate 'sentence' (if exists) or 'content'
        # Check available columns
        target_col = 'content' if 'content' in df.columns else 'sentence'
        if target_col in df.columns:
            initial_len = len(df)
            df.drop_duplicates(subset=[target_col], inplace=True)
            removed_len = initial_len - len(df)
            if removed_len > 0:
                print(f"  - 중복 제거됨: {removed_len}개 행 (기준: {target_col})")
        
        processed_rows = []
        
        # Use callback only if interactive mode is on
        callback = interactive_callback if args.interactive else None
        
        # Incremental saving setup
        save_interval = 100
        output_path_partial = output_path.with_suffix('.partial.csv')
        
        # If resuming (partial file exists), load it to count processed rows
        start_idx = 0
        if output_path_partial.exists():
            try:
                partial_df = pd.read_csv(output_path_partial)
                start_idx = len(partial_df)
                print(f"  🔄 이전 작업 발견: {start_idx}개 행 처리됨. 이어서 작업을 시작합니다.")
            except Exception as e:
                print(f"  ⚠️ 부분 파일 읽기 실패 (새로 시작): {e}")
        
        # Slice df to skip processed rows
        if start_idx > 0:
            if start_idx >= len(df):
                print("  ✅ 모든 데이터가 이미 처리되었습니다.")
                # Rename partial to final if needed?
                # If final doesn't exist but partial does and is complete.
                if not output_path.exists():
                    output_path_partial.replace(output_path)
                    print(f"  -> 저장 완료: {output_path}")
                continue
            
            df = df.iloc[start_idx:]
            print(f"  -> 남은 {len(df)}개 행을 처리합니다.")

        for idx, row in tqdm(df.iterrows(), total=len(df), desc=f"{community_name} Morph"):
            segments = []
            try:
                segments = json.loads(row.get('sentence_segments', '[]') or '[]')
            except json.JSONDecodeError:
                segments = []
    
            morph_results = []
            skip_row = False
            
            for segment in segments:
                base_sentence = segment.get('sentence', '')
                tokens = segment.get('tokens', [])
                
                # Pass callback to segment_sentence_by_endings
                try:
                    segmented = analyzer.segment_sentence_by_endings(base_sentence, tokens, refinement_callback=callback)
                except Exception as e:
                    print(f"Error processing row {idx}: {e}")
                    continue
                    
                for piece_text, piece_tokens in segmented:
                    # Check for DELETE signal
                    if any(t[1] == 'DELETE' for t in piece_tokens):
                        skip_row = True
                        break
                        
                    ending_tokens = analyzer.extract_final_endings(piece_tokens)
                    punctuation, other_symbols = analyzer.extract_symbols(piece_text)
    
                    # Calculate min probability
                    probs = [t[2] for t in piece_tokens if len(t) >= 3]
                    min_prob = min(probs) if probs else 0.0
                    last_token_prob = piece_tokens[-1][2] if piece_tokens and len(piece_tokens[-1]) >= 3 else 0.0
                    
                    # Check for OOV
                    has_oov = any(len(t) >= 4 and t[3] > 0 for t in piece_tokens)
                    
                    # Manual intent check logic (simplified)
                    needs_manual_intent = False
                    if min_prob < 0.95 or has_oov:
                        needs_manual_intent = True
    
                    morph_results.append({
                        "sentence": piece_text,
                        "endings": ending_tokens,
                        "punctuation": punctuation,
                        "other_symbols": other_symbols,
                        "min_prob": min_prob,
                        "last_token_prob": last_token_prob,
                        "has_oov": has_oov,
                        "needs_manual_intent": needs_manual_intent
                    })
    
            if skip_row:
                continue

            if not morph_results:
                morph_results.append({
                    'sentence': row.get('full_text', ''),
                    'endings': [],
                    'punctuation': [],
                    'other_symbols': [],
                    'min_prob': 1.0,
                    'last_token_prob': 1.0,
                    'has_oov': False,
                    'needs_manual_intent': True
                })
    
            row['morph_results'] = json.dumps(morph_results, ensure_ascii=False)
            processed_rows.append(row)
            
            # Incremental saving
            if len(processed_rows) >= save_interval:
                partial_df = pd.DataFrame(processed_rows)
                # Append to partial file
                header = not output_path_partial.exists()
                partial_df.to_csv(output_path_partial, mode='a', header=header, index=False, encoding='utf-8-sig')
                processed_rows = [] # Clear buffer
        
        # Save remaining rows
        if processed_rows:
            partial_df = pd.DataFrame(processed_rows)
            header = not output_path_partial.exists()
            partial_df.to_csv(output_path_partial, mode='a', header=header, index=False, encoding='utf-8-sig')
        
        # Rename partial to final
        if output_path_partial.exists():
            output_path_partial.replace(output_path)
            print(f"  -> 저장 완료: {output_path}")
        else:
            print("  -> 저장할 데이터가 없습니다.")

    print("\n" + "=" * 60)
    print("✅ Morph 후처리 완료")
    if args.interactive:
        print(f"📊 대화형 수정 완료: 총 {stats['corrections']}개 태그 변경됨")
    print("=" * 60)


if __name__ == "__main__":
    main()
