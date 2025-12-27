#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BareunAnalyzer: Bareun API 관리 클래스 (Singleton)

Bareun 형태소 분석기 인스턴스를 Singleton 패턴으로 관리하여
불필요한 재초기화를 방지합니다.
"""

import os
from bareunpy import Tagger
from dotenv import load_dotenv


class BareunAnalyzer:
    """Bareun API Singleton 클래스"""
    
    _instance = None
    _tagger = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Bareun Tagger 초기화"""
        load_dotenv()
        api_key = os.getenv('BAREUN_API_KEY')
        
        if not api_key:
            raise ValueError("BAREUN_API_KEY not found in .env file")
        
        server = 'api.bareun.ai'
        print(f"Bareun Tagger 초기화 중... ({server})")
        
        self._tagger = Tagger(api_key, server, 443)
        print("✅ Bareun Tagger 초기화 완료")
    
    @property
    def tagger(self):
        """Tagger 인스턴스 반환"""
        return self._tagger
    
    def analyze(self, text):
        """
        텍스트를 형태소 분석합니다.
        
        Args:
            text (str): 분석할 텍스트
            
        Returns:
            list: Bareun 분석 결과
        """
        if not isinstance(text, str) or not text.strip():
            return []
        
        try:
            # Use tags() to enable auto_spacing and auto_split
            tagged = self._tagger.tags([text.strip()], auto_spacing=True, auto_split=True)
            
            if not tagged:
                return []
                
            # Flatten results into a single list of tokens with details
            results = []
            sentences = tagged.sentences() if callable(tagged.sentences) else tagged.sentences
            
            if not sentences:
                return []
                
            for sent in sentences:
                for token in sent.tokens:
                    for morph in token.morphemes:
                        # (morph, tag, probability, out_of_vocab)
                        prob = getattr(morph, 'probability', 0.0)
                        oov = getattr(morph, 'out_of_vocab', 0)
                        
                        # Convert integer tag to string (e.g., 25 -> "NNP")
                        tag_str = type(morph).Tag.Name(morph.tag)
                        
                        results.append((morph.text.content, tag_str, prob, oov))
            
            return results
        except Exception as e:
            print(f"⚠️  Bareun 분석 오류: {e}")
            return []
