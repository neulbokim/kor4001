#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DataPipeline: 전처리 파이프라인 클래스

데이터 로드, 분석, 필터링, 저장 등 전처리 파이프라인을
체계적으로 관리합니다.
"""

import json
import pandas as pd
from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from collections import Counter

from utils.morph_analyzer import MorphAnalyzer


class DataPipeline:
    """전처리 파이프라인 관리 클래스"""
    
    def __init__(self, max_workers=20):
        """
        DataPipeline 초기화
        
        Args:
            max_workers (int): 병렬 처리 워커 수
        """
        self.analyzer = MorphAnalyzer()
        self.max_workers = max_workers
        self.df = None
    
    def load_data(self, file_path):
        """
        CSV 파일에서 데이터를 로드합니다.
        
        Args:
            file_path (str or Path): CSV 파일 경로
            
        Returns:
            DataPipeline: 메서드 체이닝을 위한 self 반환
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"❌ 오류: {file_path}가 존재하지 않습니다.")
        
        print(f"\\n데이터 로드 중: {file_path}")
        self.df = pd.read_csv(file_path)
        print(f"로드된 행 수: {len(self.df)}")
        
        return self
    
    def analyze_morphology(self):
        """
        텍스트에 대해 형태소 분석을 수행합니다.
        
        Returns:
            DataPipeline: 메서드 체이닝을 위한 self 반환
        """
        if self.df is None:
            raise ValueError("데이터가 로드되지 않았습니다. load_data()를 먼저 호출하세요.")
        
        print("\\n" + "=" * 60)
        print("형태소 분석, 문형 분류, 기호 추출 중 (Bareun - 병렬 처리)...")
        print("=" * 60)
        
        texts = self.df['full_text'].tolist()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = list(tqdm(
                executor.map(self.analyzer.analyze_text, texts),
                total=len(texts),
                desc="분석 진행"
            ))
        
        # 결과를 JSON 형태로 저장
        self.df['sentence_results'] = [json.dumps(r, ensure_ascii=False) for r in results]
        
        return self
    
    def filter_banmal(self):
        """
        반말 게시글만 필터링합니다.
        
        Returns:
            DataPipeline: 메서드 체이닝을 위한 self 반환
        """
        if self.df is None:
            raise ValueError("데이터가 로드되지 않았습니다.")
        
        if 'sentence_results' not in self.df.columns:
            raise ValueError("형태소 분석이 완료되지 않았습니다. analyze_morphology()를 먼저 호출하세요.")
        
        print("\\n반말 글 필터링 중...")
        initial_count = len(self.df)
        
        # sentence_results에서 첫 번째 문장의 endings를 추출하여 반말 여부 판별
        def check_banmal(sentence_results_json):
            try:
                results = json.loads(sentence_results_json)
                if results and len(results) > 0:
                    endings = results[0].get('endings', [])
                    return MorphAnalyzer.is_banmal(endings)
                return False
            except:
                return False
        
        self.df['is_banmal'] = self.df['sentence_results'].apply(check_banmal)
        self.df = self.df[self.df['is_banmal'] == True].copy()
        
        removed_count = initial_count - len(self.df)
        print(f"제거된 존댓말 글: {removed_count}개")
        print(f"남은 반말 글: {len(self.df)}개")
        
        return self
    
    def report_neologisms(self, neologisms=['긔', '노', '슨']):
        """
        신조어 종결 어미 빈도를 출력합니다.
        
        Args:
            neologisms (list): 확인할 신조어 리스트
            
        Returns:
            DataPipeline: 메서드 체이닝을 위한 self 반환
        """
        if self.df is None or 'sentence_results' not in self.df.columns:
            raise ValueError("분석 데이터가 없습니다.")
        
        print("\\n" + "=" * 60)
        print("신조어 종결 어미 확인 중...")
        neo_counts = {neo: 0 for neo in neologisms}
        
        for sentence_results_json in self.df['sentence_results']:
            try:
                results = json.loads(sentence_results_json)
                for sent_res in results:
                    for morph, tag in sent_res.get('endings', []):
                        if morph in neologisms:
                            neo_counts[morph] += 1
            except:
                continue
        
        print("\\n신조어 빈도:")
        for neo, count in neo_counts.items():
            print(f"  '{neo}': {count}회")
        
        return self
    
    def save(self, output_path):
        """
        처리된 데이터를 CSV 파일로 저장합니다.
        
        Args:
            output_path (str or Path): 저장 경로
            
        Returns:
            DataPipeline: 메서드 체이닝을 위한 self 반환
        """
        if self.df is None:
            raise ValueError("저장할 데이터가 없습니다.")
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # is_banmal 컬럼 제거 (임시 컬럼)
        if 'is_banmal' in self.df.columns:
            self.df = self.df.drop('is_banmal', axis=1)
        
        self.df.to_csv(output_path, index=False, encoding='utf-8')
        
        print("\\n" + "=" * 60)
        print("✅ 형태소 분석 완료!")
        print("=" * 60)
        print(f"📁 저장 경로: {output_path}")
        print(f"최종 행 수: {len(self.df)}")
        
        return self
