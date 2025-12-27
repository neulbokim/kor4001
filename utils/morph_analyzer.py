#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MorphAnalyzer: 후처리용 형태소 분석 유틸리티

`BareunAnalyzer`가 반환한 토큰을 받아 종결어미, 기호, 문장분리, 반말 판단 등을 수행합니다.
"""

import re


class MorphAnalyzer:
    """MorphAnalyzer: Bareun 결과를 기반으로 종결어미/기호 정보를 뽑아줍니다."""
    
    # EF: 종결 어미만 수집 (ETN:명사형, ETM:관형사형 제외)
    FINAL_ENDING_TAGS = {'EF', 'ECF'}
    SPLIT_ENDING_TAGS = {'EF'}
    SENTENCE_SPLIT_REGEX = r'(?<=[.!?])\s+'

    # 모든 한글 자음 반복 패턴 포착 (ㅋㅋ, ㅎㅎ, ㅠㅠ, ㅅㅂ, ㅈㄴ 등)
    EMOTION_REGEX = re.compile(r'[ㄱ-ㅎㅏ-ㅣ]+')
    PUNCTUATION_REGEX = re.compile(r'[?!~…\.]+')

    def extract_final_endings(self, tokens):
        """
        Bareun 토큰 리스트에서 종결 어미(및 그 뒤의 보조사)를 추출합니다.
        """
        if not tokens:
            return []

        endings = []
        idx = 0
        while idx < len(tokens):
            token = tokens[idx]
            if not token or len(token) < 2:
                idx += 1
                continue

            morph, tag = token[0], token[1]
            if tag in self.FINAL_ENDING_TAGS:
                # Append the full token tuple (morph, tag, prob, oov)
                endings.append(token)

                lookahead = idx + 1
                while lookahead < len(tokens):
                    next_token = tokens[lookahead]
                    if not next_token or len(next_token) < 2:
                        lookahead += 1
                        continue
                    next_morph, next_tag = next_token[0], next_token[1]

                    if next_tag.startswith('J') or next_tag == 'EP':
                        endings.append(next_token)
                        lookahead += 1
                        idx = lookahead - 1
                        continue
                    break

            idx += 1

        return endings

    def _token_positions(self, sentence, tokens):
        positions = []
        cursor = 0
        lowered = sentence
        for token in tokens:
            morph = token[0] if token and isinstance(token, (list, tuple)) else ''
            if not morph:
                positions.append((cursor, cursor))
                continue
            idx = lowered.find(morph, cursor)
            if idx == -1:
                idx = lowered.find(morph)
            if idx == -1:
                positions.append((cursor, cursor))
                continue
            end = idx + len(morph)
            positions.append((idx, end))
            cursor = end
        return positions

    def _refine_tokens(self, tokens, sentence=None, callback=None):
        """
        토큰 리스트를 순회하며 특정 조건(예: '긔' + 낮은 확률)일 때 태그를 수정합니다.
        callback이 제공되면 사용자에게 결정을 위임합니다.
        """
        refined = []
        for i, token in enumerate(tokens):
            # token: (morph, tag, prob, oov) or (morph, tag)
            if len(token) >= 3:
                morph, tag, prob = token[0], token[1], token[2]
                oov = token[3] if len(token) >= 4 else 0
                
                new_tag = tag
                
                # 0. ETN 자동 보정 규칙 (사용자 요청)
                # 'ㅁ', '음'이 ETN일 때, 뒤에 조사(J...)가 오지 않으면 EF로 변경
                if tag == 'ETN' and morph in {'ㅁ', '음', '기', '긔'}:
                    is_followed_by_josa = False
                    if i + 1 < len(tokens):
                        next_token = tokens[i+1]
                        if len(next_token) >= 2 and next_token[1].startswith('J'):
                            is_followed_by_josa = True
                    
                    if not is_followed_by_josa:
                        new_tag = 'EF'
                
                # 0-1. 문장 끝 EC 자동 보정
                # 문장의 맨 마지막 토큰이 EC인 경우, 혹은 뒤에 문장부호(S...)만 있는 경우
                # 어차피 ECF로 바뀔 것이므로 미리 ECF로 변경하여 대화형 모드에서 물어보지 않음.
                if tag == 'EC':
                    is_last_meaningful = True
                    for j in range(i + 1, len(tokens)):
                        if not tokens[j][1].startswith('S'):
                            is_last_meaningful = False
                            break
                    
                    if is_last_meaningful:
                        new_tag = 'ECF'

                # 1. 자동 보정 규칙 (기존 로직 유지 + '노' 추가)
                # '긔', '노' 처리: 확률이 0.9 이하이면 EF로 강제 변환 (항상 적용)
                if (morph == '긔' or morph == '노' or morph == '나' or morph == '슨' or morph == '임' ) and prob <= 0.9:
                    new_tag = 'EF'

                # 2. 대화형 보정 (callback 있을 때)
                if callback is not None:
                    # EC 검사 (확률 0.92 이하인 모든 EC)
                    # 단, 위에서 이미 EF로 바뀐 경우(new_tag == 'EF')는 제외될 수 있음
                    # 하지만 사용자는 "자동으로 바뀌었는지" 궁금해할 수 있음.
                    # 만약 자동으로 바뀌었다면 굳이 물어볼 필요 없음.
                    # 따라서 new_tag == 'EC' 조건이 이를 자연스럽게 필터링함.
                    if new_tag == 'EC' and prob <= 0.92:
                        decision = callback(token, tokens, i, sentence)
                        if decision:
                            new_tag = decision
                    
                    # ETN 검사 (모든 'ㅁ', '음')
                    elif new_tag == 'ETN' and morph in {'ㅁ', '음'}:
                        decision = callback(token, tokens, i, sentence)
                        if decision:
                            new_tag = decision
                    
                    # '임' 검사 (태깅/확률 무관하게 모두)
                    elif morph == '임':
                        decision = callback(token, tokens, i, sentence)
                        if decision:
                            new_tag = decision

                if new_tag != tag:
                    refined.append((morph, new_tag, prob, oov))
                else:
                    refined.append(token)
            else:
                refined.append(token)
        return refined

    def segment_sentence_by_endings(self, sentence, tokens, refinement_callback=None):
        """
        하나의 sentence와 토큰 리스트를 받아 종결 어미 기준으로 분할된 문장 목록 생성
        refinement_callback: 토큰 보정 시 호출할 콜백 함수
        """
        if not sentence or not tokens:
            return [(sentence, tokens)]

        # 토큰 보정 (예: '긔' -> EF)
        tokens = self._refine_tokens(tokens, sentence=sentence, callback=refinement_callback)

        positions = self._token_positions(sentence, tokens)
        segments = []
        idx = 0
        buffer_tokens = []
        start_pos = None
        
        # end_pos tracks the end of the matched text for tokens in buffer.
        # However, for irregular conjugations, this might lag behind.
        # We will use explicit split points when flushing.
        end_pos = None 

        def flush_buffer(explicit_end_pos=None):
            nonlocal buffer_tokens, start_pos, end_pos
            if not buffer_tokens or start_pos is None:
                return
            
            # Use explicit_end_pos if provided, otherwise fallback to tracked end_pos
            final_end = explicit_end_pos if explicit_end_pos is not None else end_pos
            if final_end is None:
                final_end = len(sentence)
                
            # Check if the last token of the segment is EC, if so change to ECF
            if buffer_tokens and buffer_tokens[-1][1] == 'EC':
                t = buffer_tokens[-1]
                # Create new tuple with 'ECF' tag, preserving other elements
                buffer_tokens[-1] = (t[0], 'ECF') + t[2:]
            
            text = sentence[start_pos:final_end]
            segments.append((text.strip(), list(buffer_tokens)))
            buffer_tokens = []
            start_pos = None
            end_pos = None

        while idx < len(tokens):
            token = tokens[idx]
            if not token or len(token) < 2:
                idx += 1
                continue

            buffer_tokens.append(token)
            if start_pos is None:
                start_pos = positions[idx][0]
            
            # Update end_pos only if this token was actually found (width > 0)
            # If width is 0 (not found), we don't update end_pos, effectively extending the previous segment
            if positions[idx][1] > positions[idx][0]:
                end_pos = positions[idx][1]
            
            tag = token[1]

            if tag in self.SPLIT_ENDING_TAGS:
                lookahead = idx + 1
                while lookahead < len(tokens):
                    next_token = tokens[lookahead]
                    if not next_token or len(next_token) < 2:
                        lookahead += 1
                        continue
                    next_tag = next_token[1]
                    if next_tag.startswith('J') or next_tag == 'EP' or next_tag.startswith('S'):
                        buffer_tokens.append(next_token)
                        if positions[lookahead][1] > positions[lookahead][0]:
                            end_pos = positions[lookahead][1]
                        lookahead += 1
                        continue
                    break
                
                # Check if there is a space after this block
                should_split = True
                split_end = end_pos # Default split end
                
                if lookahead < len(tokens):
                    # Next token exists. 
                    # We should split up to the start of the next token to capture any irregular forms/spaces.
                    next_start = positions[lookahead][0]
                    
                    # If next_start is valid (not -1/same as cursor), use it.
                    # If end_pos is None (no tokens found yet), assume split_end should be next_start
                    if end_pos is None or next_start >= end_pos:
                        split_end = next_start
                    
                    # Heuristic: if next token starts right after current end (no space), maybe don't split?
                    # But for irregulars, end_pos might be far behind next_start.
                    # So we rely on the tag (EF) to dictate split, unless it's weird.
                    # The original logic checked `next_start == end_pos`.
                    # But with irregulars, `end_pos` is unreliable.
                    # Let's trust the tag.
                    pass
                else:
                    # End of sentence
                    split_end = len(sentence)

                if should_split:
                    flush_buffer(explicit_end_pos=split_end)
                
                idx = lookahead
                continue

            idx += 1

        # Flush any leftover tokens as final sentence
        flush_buffer(explicit_end_pos=len(sentence))
        return segments

    def extract_symbols(self, text):
        """
        텍스트에서 문장부호와 감정 기호를 추출합니다.
        """
        if not isinstance(text, str):
            return [], []

        punctuation = []
        other_symbols = []

        for match in self.EMOTION_REGEX.finditer(text):
            sequence = match.group(0)[:3]
            if sequence and sequence not in other_symbols:
                other_symbols.append(sequence)

        for match in self.PUNCTUATION_REGEX.finditer(text):
            sequence = match.group(0)[:3]
            if sequence and sequence not in punctuation:
                punctuation.append(sequence)

        return punctuation, other_symbols

    def split_sentences(self, text):
        """
        텍스트를 문장 단위로 분리합니다.
        """
        if not isinstance(text, str):
            return []

        sentences = re.split(self.SENTENCE_SPLIT_REGEX, text)
        return [s.strip() for s in sentences if s.strip()]
    
    @staticmethod
    def is_banmal(endings):
        """
        종결 어미 리스트를 보고 반말 여부를 판별합니다.
        
        Args:
            endings (list): 종결 어미 리스트
            
        Returns:
            bool: 반말이면 True, 존댓말이면 False
        """
        if not endings:
            return False
        
        polite_endings = ['요', '죠', '습니다', 'ㅂ니다', '까요', '나요', '인가요']
        
        banmal_score = 0
        polite_score = 0
        
        for ending in endings:
            morph, tag = ending[0], ending[1]
            is_polite = any(p in morph for p in polite_endings)
            
            if is_polite:
                polite_score += 1
            else:
                banmal_score += 1
        
        # 존댓말 비율이 높으면 False 반환
        if polite_score > 0 and polite_score >= banmal_score * 0.5:
            return False
        
        return True
