#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
05. Intent 정리

문장 단위 확장 결과에서 종결 어미 목록을 보강하고,
라벨링/분석에 쓸 `real_ending`을 추가합니다.

Input: data/processed/all_communities_expanded.csv
Output: data/processed/all_communities_intent.csv
"""

import json
import re
from pathlib import Path

import pandas as pd
from tqdm import tqdm


def strip_trailing_punct(text):
    """문장 끝의 공백/문장부호를 제거한 문자열 반환"""
    if not isinstance(text, str):
        return ''
    return re.sub(r'[\.!?~…]+$', '', text.strip()).rstrip()


def build_real_ending(endings):
    """마지막 종결/보조어미 시퀀스를 real_ending으로 묶어줌"""
    if not endings:
        return []
    if endings[-1][1] == 'JX' and len(endings) >= 2:
        return endings[-2:]
    return [endings[-1]]


def normalize_list_column(value):
    if pd.isna(value) or value == '':
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    return []


def main():
    print("=" * 60)
    print("Intent 데이터 생성 시작")
    print("=" * 60)

    expanded_path = Path("data/processed/all_communities_expanded.csv")
    output_path = Path("data/processed/all_communities_intent.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not expanded_path.exists():
        print(f"\n❌ 오류: {expanded_path}가 존재하지 않습니다.")
        print("먼저 scripts/preprocessing/04_expand_sentences.py를 실행하세요.")
        return

    print(f"\n데이터 로드 중: {expanded_path}")
    df = pd.read_csv(expanded_path)
    print(f"로드된 행 수: {len(df)}")

    rows = []
    print("\nIntent 데이터 정리 중...")
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Intent 준비"):
        sentence = row.get('sentence', '')
        endings = normalize_list_column(row.get('all_endings', '[]'))
        real_ending = build_real_ending(endings)

        rows.append({
            'community': row.get('community', ''),
            'full_text': row.get('full_text', ''),
            'timestamp': row.get('timestamp', ''),
            'sentence': sentence,
            'real_ending': json.dumps(real_ending, ensure_ascii=False) if real_ending else '[]',
            'all_endings': json.dumps(endings, ensure_ascii=False),
            'intent': row.get('intent', ''),
            'punctuation': row.get('punctuation', '[]'),
            'symbols': row.get('symbols', '[]'),
        })

    result_df = pd.DataFrame(rows)
    result_df.to_csv(output_path, index=False, encoding='utf-8')

    print("\n" + "=" * 60)
    print("✅ Intent 데이터 준비 완료")
    print("=" * 60)
    print(f"📁 저장 경로: {output_path}")


if __name__ == "__main__":
    main()
