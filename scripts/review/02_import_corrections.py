
import sys
import pandas as pd
import json
from pathlib import Path
from tqdm import tqdm
import ast

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from utils.bareun_analyzer import BareunAnalyzer
from utils.morph_analyzer import MorphAnalyzer

def main():
    print("=" * 60)
    print("수정된 데이터 반영 (Import Corrections)")
    print("=" * 60)

    # Paths
    processed_dir = Path("data/processed")
    corrected_xlsx_path = Path("data/review/review_dataset_corrected.xlsx")
    
    if not corrected_xlsx_path.exists():
        print(f"❌ Corrected file not found: {corrected_xlsx_path}")
        print("Please save your corrections as 'data/review/review_dataset_corrected.xlsx'")
        return

    print("Loading original data from morph_*.csv files...")
    input_files = list(processed_dir.glob("morph_*.csv"))
    if not input_files:
        print("❌ No morph_*.csv files found.")
        return

    # Load all dataframes and map ID to (file_path, index)
    id_map = {} # id -> (file_path, index)
    dfs = {} # file_path -> dataframe
    
    for file_path in input_files:
        print(f"  - Loading {file_path.name}...")
        df = pd.read_csv(file_path)
        dfs[file_path] = df
        
        if 'id' in df.columns:
            for idx, row in df.iterrows():
                id_map[row['id']] = (file_path, idx)
    
    print(f"Loaded {len(id_map)} rows across {len(dfs)} files.")
    
    print(f"Loading corrected data from {corrected_xlsx_path}...")
    corrected_df = pd.read_excel(corrected_xlsx_path)
    
    # Ensure ID column exists
    if 'id' not in corrected_df.columns:
        print("❌ 'id' column missing in corrected file.")
        return
    
    analyzer = BareunAnalyzer()
    morph_analyzer = MorphAnalyzer()
    
    updated_count = 0
    files_to_save = set()
    
    print("\nApplying corrections...")
    for _, row in tqdm(corrected_df.iterrows(), total=len(corrected_df)):
        row_id = row['id']
        if row_id not in id_map:
            continue
            
        file_path, original_idx = id_map[row_id]
        df = dfs[file_path]
        original_row = df.loc[original_idx]
        
        # Check if sentences changed
        new_sentences_text = str(row['sentences_text']) if pd.notna(row['sentences_text']) else ""
        
        # Reconstruct original text for comparison (normalization might be needed)
        try:
            orig_results = json.loads(original_row['sentence_results'])
            orig_sentences_text = "\n".join([res['sentence'] for res in orig_results])
        except:
            orig_sentences_text = ""
            
        # Normalize line endings and strip
        if new_sentences_text.strip().replace('\r\n', '\n') == orig_sentences_text.strip().replace('\r\n', '\n'):
            continue
            
        # If changed, re-process
        new_sentences = [s.strip() for s in new_sentences_text.split('\n') if s.strip()]
        new_results = []
        
        for sent in new_sentences:
            # Re-analyze with Bareun
            try:
                tokens = analyzer.analyze(sent)
                # tokens: [(morph, tag, prob, oov), ...]
                
                # Re-run MorphAnalyzer logic
                # Note: We don't need to split again because the user manually split/merged
                # But we need to extract endings and symbols from the tokens
                
                # Extract endings
                # Tokens for morph analyzer need to be just (morph, tag) or full tuple?
                # My updated MorphAnalyzer handles full tuples.
                ending_tokens = morph_analyzer.extract_final_endings(tokens)
                punctuation, other_symbols = morph_analyzer.extract_symbols(sent)
                
                # Calculate stats
                min_prob = 1.0
                has_oov = False
                last_token_prob = 1.0
                
                for t in tokens:
                    if len(t) >= 3:
                        if t[2] < min_prob: min_prob = t[2]
                    if len(t) >= 4:
                        if t[3] == 1: has_oov = True
                        
                if tokens:
                    last_t = tokens[-1]
                    if len(last_t) >= 3:
                        last_token_prob = last_t[2]
                
                needs_manual = False
                if last_token_prob < 0.7 or min_prob < 0.3:
                    needs_manual = True
                    
                new_results.append({
                    'sentence': sent,
                    'endings': ending_tokens,
                    'punctuation': punctuation,
                    'other_symbols': other_symbols,
                    'min_prob': min_prob,
                    'last_token_prob': last_token_prob,
                    'has_oov': has_oov,
                    'needs_manual_intent': needs_manual
                })
                
            except Exception as e:
                print(f"Error analyzing sentence '{sent}': {e}")
                # Fallback to empty result?
                new_results.append({
                    'sentence': sent,
                    'endings': [],
                    'punctuation': [],
                    'other_symbols': [],
                    'min_prob': 0.0,
                    'last_token_prob': 0.0,
                    'has_oov': False,
                    'needs_manual_intent': True
                })

        # Update DataFrame
        df.at[original_idx, 'sentence_results'] = json.dumps(new_results, ensure_ascii=False)
        updated_count += 1
        files_to_save.add(file_path)

    print(f"\n✅ Updated {updated_count} rows.")
    
    # Save updated CSVs
    print("Saving updated files...")
    for file_path in files_to_save:
        print(f"  - Saving {file_path.name}...")
        dfs[file_path].to_csv(file_path, index=False, encoding='utf-8')
        
    print("Done.")
    print("⚠️  Don't forget to run 'scripts/preprocessing/04_expand_sentences.py' to apply changes to the final dataset.")

if __name__ == "__main__":
    main()
