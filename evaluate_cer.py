import sys
import re
import unicodedata
import pykakasi
import Levenshtein

# --- Preprocessing Functions ---

def normalize_text(text):
    # NFKC Normalization
    text = unicodedata.normalize('NFKC', text)
    # Remove whitespace
    text = "".join(text.split())
    # Remove punctuation (Unicode category P* and specific Japanese marks)
    # Also remove common Japanese punctuation not in P*
    res = []
    for char in text:
        cat = unicodedata.category(char)
        if cat.startswith('P'):
            continue
        # Specific Japanese punctuation check
        if char in "。、，．・「」『』（）［］【】…—":
            continue
        res.append(char)
    return "".join(res)

kks = pykakasi.kakasi()

def to_kana(text):
    # Convert to hiragana
    result = kks.convert(text)
    kana = "".join([item['hira'] for item in result])
    # Remove long vowel mark 'ー' as requested
    kana = kana.replace('ー', '')
    # Re-apply normalization to ensure no stray marks
    return normalize_text(kana)

# --- Alignment Logic ---

def get_edit_details(ref, hyp):
    """Calculate Levenshtein distance and counts (ins, del, sub) with priority: sub > del > ins."""
    n = len(ref)
    m = len(hyp)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
        
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref[i-1] == hyp[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = min(dp[i-1][j-1], dp[i-1][j], dp[i][j-1]) + 1
                
    # Backtrack to find counts
    ins, dele, sub = 0, 0, 0
    curr_i, curr_j = n, m
    while curr_i > 0 or curr_j > 0:
        if curr_i > 0 and curr_j > 0 and ref[curr_i-1] == hyp[curr_j-1]:
            curr_i -= 1
            curr_j -= 1
        else:
            # Priorities: sub > del > ins
            # Check options that lead to min cost
            cost = dp[curr_i][curr_j]
            # Try Sub
            if curr_i > 0 and curr_j > 0 and dp[curr_i-1][curr_j-1] + 1 == cost:
                sub += 1
                curr_i -= 1
                curr_j -= 1
            # Try Del
            elif curr_i > 0 and dp[curr_i-1][curr_j] + 1 == cost:
                dele += 1
                curr_i -= 1
            # Try Ins
            elif curr_j > 0 and dp[curr_i][curr_j-1] + 1 == cost:
                ins += 1
                curr_j -= 1
            else:
                # Should not reach here
                break
                
    return ins, dele, sub, dp[n][m]

def align_sentences(ref_list, hyp_full):
    """
    Align full hyp text to ref sentences using DP.
    Splits hyp into atomic chunks by punctuation/newlines first.
    """
    # Pre-split hyp into chunks to reduce DP state space
    # Split by common sentence delimiters
    hyp_chunks = re.split(r'([。．？！\?!
]+)', hyp_full)
    # Merge delimiter with previous chunk
    merged_chunks = []
    temp = ""
    for c in hyp_chunks:
        if not c: continue
        if re.match(r'[。．？！\?!
]+', c):
            if merged_chunks:
                merged_chunks[-1] += c
            else:
                temp += c
        else:
            if temp:
                merged_chunks.append(temp + c)
                temp = ""
            else:
                merged_chunks.append(c)
    if temp: merged_chunks.append(temp)
    
    n = len(ref_list)
    m = len(merged_chunks)
    
    # dp[i][j] = min cost to align first i ref sentences using first j hyp chunks
    # Store (cost, split_index)
    inf = float('inf')
    dp = [[(inf, -1)] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = (0, 0)
    
    # Precompute costs for efficiency
    # cost_cache[i][start][end]
    processed_refs = [normalize_text(r) for r in ref_list]
    
    for i in range(1, n + 1):
        ref_proc = processed_refs[i-1]
        for j in range(1, m + 1):
            # Try all possible previous split points
            # To avoid huge chunks, we can limit the lookback, 
            # but for a reasonable number of chunks it's okay.
            for k in range(j):
                if dp[i-1][k][0] == inf: continue
                
                # hyp_chunk_raw is chunks from k to j-1
                hyp_chunk_raw = "".join(merged_chunks[k:j])
                hyp_proc = normalize_text(hyp_chunk_raw)
                
                # CER distance
                _, _, _, dist = get_edit_details(ref_proc, hyp_proc)
                
                total_cost = dp[i-1][k][0] + dist
                if total_cost <= dp[i][j][0]:
                    dp[i][j] = (total_cost, k)
                    
    # Backtrack
    aligned_hyp_raw = []
    curr_m = m
    for i in range(n, 0, -1):
        prev_m = dp[i][curr_m][1]
        aligned_hyp_raw.append("".join(merged_chunks[prev_m:curr_m]))
        curr_m = prev_m
    aligned_hyp_raw.reverse()
    
    return aligned_hyp_raw

def main():
    input_text = sys.stdin.read()
    
    ref_match = re.search(r'\[REF_BEGIN\](.*?\[REF_END\]', input_text, re.DOTALL)
    hyp_match = re.search(r'\[HYP_BEGIN\](.*?\[HYP_END\]', input_text, re.DOTALL)
    
    if not ref_match or not hyp_match:
        return

    ref_raw_full = ref_match.group(1).strip()
    hyp_raw_full = hyp_match.group(1).strip()
    
    ref_lines = [line.strip() for line in ref_raw_full.splitlines() if line.strip()]
    
    # Align
    hyp_aligned_raw = align_sentences(ref_lines, hyp_raw_full)
    
    details = []
    
    modes = ['char', 'kana']
    
    for mode in modes:
        for i, (ref_raw, hyp_raw) in enumerate(zip(ref_lines, hyp_aligned_raw)):
            if mode == 'char':
                ref_proc = normalize_text(ref_raw)
                hyp_proc = normalize_text(hyp_raw)
            else:
                ref_proc = to_kana(ref_raw)
                hyp_proc = to_kana(hyp_raw)
                
            ref_len = len(ref_proc)
            hyp_len = len(hyp_proc)
            
            if ref_len == 0:
                ins, dele, sub, dist = 0, 0, 0, 0
                cer = "NA"
            else:
                ins, dele, sub, dist = get_edit_details(ref_proc, hyp_proc)
                cer = round(dist / ref_len, 4)
                
            details.append({
                'doc_id': '',
                'sent_id': i + 1,
                'mode': mode,
                'ref_raw': ref_raw,
                'hyp_raw_chunk': hyp_raw,
                'ref_proc': ref_proc,
                'hyp_proc': hyp_proc,
                'ref_len': ref_len,
                'hyp_len': hyp_len,
                'ins': ins,
                'del': dele,
                'sub': sub,
                'distance': dist,
                'cer': cer,
                'notes': ''
            })

    # Output details.csv
    print("doc_id,sent_id,mode,ref_raw,hyp_raw_chunk,ref_proc,hyp_proc,ref_len,hyp_len,ins,del,sub,distance,cer,notes")
    for d in details:
        # Simple CSV quoting for safety (though fields should be clean)
        row = [
            str(d['doc_id']),
            str(d['sent_id']),
            d['mode'],
            f'"{d["ref_raw"]}" ',
            f'"{d["hyp_raw_chunk"]}" ',
            d['ref_proc'],
            d['hyp_proc'],
            str(d['ref_len']),
            str(d['hyp_len']),
            str(d['ins']),
            str(d['del']),
            str(d['sub']),
            str(d['distance']),
            str(d['cer']),
            d['notes']
        ]
        print(",".join(row))
        
    # Summary
    summary = []
    for mode in modes:
        valid_details = [d for d in details if d['mode'] == mode and d['ref_len'] > 0]
        count = len([d for d in details if d['mode'] == mode])
        valid_count = len(valid_details)
        total_distance = sum(d['distance'] for d in valid_details)
        total_ref_len = sum(d['ref_len'] for d in valid_details)
        
        micro_cer = round(total_distance / total_ref_len, 4) if total_ref_len > 0 else 0
        macro_cer = round(sum(d['cer'] for d in valid_details) / valid_count, 4) if valid_count > 0 else 0
        
        summary.append({
            'mode': mode,
            'count': count,
            'valid_count': valid_count,
            'total_distance': total_distance,
            'total_ref_len': total_ref_len,
            'micro_cer': micro_cer,
            'macro_cer': macro_cer
        })
        
    print("mode,count,valid_count,total_distance,total_ref_len,micro_cer,macro_cer")
    for s in summary:
        row = [
            s['mode'],
            str(s['count']),
            str(s['valid_count']),
            str(s['total_distance']),
            str(s['total_ref_len']),
            f"{s['micro_cer']:.4f}",
            f"{s['macro_cer']:.4f}"
        ]
        print(",".join(row))

if __name__ == "__main__":
    main()
