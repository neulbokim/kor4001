
import sys
import pandas as pd
import json
from pathlib import Path
import uuid

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

def main():
    print("=" * 60)
    print("검토용 엑셀 파일 생성 (Export for Review)")
    print("=" * 60)

    processed_dir = Path("data/processed/morph")
    output_dir = Path("data/review")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "review_dataset.xlsx"

    input_files = list(processed_dir.glob("morph_*.csv"))
    
    if not input_files:
        print(f"❌ No morph_*.csv files found in {processed_dir}")
        return

    print(f"Found {len(input_files)} files. Loading...")
    
    all_dfs = []
    for input_path in input_files:
        print(f"  - {input_path.name}")
        df = pd.read_csv(input_path)
        
        # Add a unique ID if not present
        if 'id' not in df.columns:
            print(f"    Generating unique IDs for {input_path.name}...")
            df['id'] = [str(uuid.uuid4()) for _ in range(len(df))]
            # Save back to file
            df.to_csv(input_path, index=False, encoding='utf-8')
        
        all_dfs.append(df)
    
    if not all_dfs:
        print("No data loaded.")
        return
        
    df = pd.concat(all_dfs, ignore_index=True)

    review_rows = []
    
    print("Processing rows...")
    for _, row in df.iterrows():
        try:
            sentence_results = json.loads(row['sentence_results'])
        except:
            sentence_results = []
            
        # Join sentences with newline for easy editing in Excel
        sentences_text = "\n".join([res['sentence'] for res in sentence_results])
        
        # Aggregate flags
        needs_manual = False
        has_oov = False
        min_prob = 1.0
        
        for res in sentence_results:
            if res.get('needs_manual_intent'):
                needs_manual = True
            if res.get('has_oov'):
                has_oov = True
            prob = res.get('min_prob', 1.0)
            if prob < min_prob:
                min_prob = prob
        
        review_rows.append({
            'id': row['id'],
            'community': row.get('community', ''),
            'posted_at': row.get('posted_at', ''),
            'full_text': row.get('full_text', ''),
            'sentences_text': sentences_text, # Editable column
            'needs_manual_intent': needs_manual,
            'has_oov': has_oov,
            'min_prob': min_prob
        })

    review_df = pd.DataFrame(review_rows)
    
    # Sort by needs_manual_intent (True first) to prioritize review
    review_df = review_df.sort_values(by=['needs_manual_intent', 'min_prob'], ascending=[False, True])

    print(f"Saving to {output_path}...")
    try:
        review_df.to_excel(output_path, index=False)
        print("✅ Export successful!")
        print(f"Total rows: {len(review_df)}")
        print(f"Rows needing manual review: {len(review_df[review_df['needs_manual_intent'] == True])}")
    except ImportError:
        print("❌ Error: 'openpyxl' library is required to save as Excel.")
        print("Please run: pip install openpyxl")
    except Exception as e:
        print(f"❌ Error saving Excel: {e}")

if __name__ == "__main__":
    main()
