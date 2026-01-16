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
    # Remove punctuation
    res = []
    jp_puncts = "\u3002\u3001\uff0c\uff0e\u30fb\u300c\u300d\u300e\u300f\uff08\uff09\uff3b\uff3d\u3010\u3011\u2026\u2014"
    for char in text:
        cat = unicodedata.category(char)
        if cat.startswith('P'):
            continue
        if char in jp_puncts:
            continue
        res.append(char)
    return "".join(res)

def normalize_with_mapping(text):
    """Returns (normalized_text, mapping_to_original_indices)"""
    clean_chars = []
    mapping = []
    jp_puncts = "\u3002\u3001\uff0c\uff0e\u30fb\u300c\u300d\u300e\u300f\uff08\uff09\uff3b\uff3d\u3010\u3011\u2026\u2014"
    
    for i, c in enumerate(text):
        nc = unicodedata.normalize('NFKC', c)
        if nc.strip() == "":
            continue
        cat = unicodedata.category(nc)
        if cat.startswith('P') or nc in jp_puncts:
            continue
        for sub_c in nc:
            clean_chars.append(sub_c)
            mapping.append(i)
    return "".join(clean_chars), mapping

kks = pykakasi.kakasi()

def to_kana(text):
    result = kks.convert(text)
    kana = "".join([item['hira'] for item in result])
    kana = kana.replace('\u30fc', '') # Remove long vowel mark
    return normalize_text(kana)

# --- Alignment Logic ---

def get_edit_details(ref, hyp):
    """Calculate Levenshtein distance and counts with priority: sub > del > ins."""
    n, m = len(ref), len(hyp)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1): dp[i][0] = i
    for j in range(m + 1): dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref[i-1] == hyp[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = min(dp[i-1][j-1], dp[i-1][j], dp[i][j-1]) + 1
    
    ins, dele, sub = 0, 0, 0
    curr_i, curr_j = n, m
    while curr_i > 0 or curr_j > 0:
        cost = dp[curr_i][curr_j]
        if curr_i > 0 and curr_j > 0 and ref[curr_i-1] == hyp[curr_j-1]:
            curr_i -= 1; curr_j -= 1
        elif curr_i > 0 and curr_j > 0 and dp[curr_i-1][curr_j-1] + 1 == cost:
            sub += 1; curr_i -= 1; curr_j -= 1
        elif curr_i > 0 and dp[curr_i-1][curr_j] + 1 == cost:
            dele += 1; curr_i -= 1
        elif curr_j > 0 and dp[curr_i][curr_j-1] + 1 == cost:
            ins += 1; curr_j -= 1
        else: break
    return ins, dele, sub, dp[n][m]

def align_sentences(ref_list, hyp_full):
    """Align hyp to ref sentences using character-level DP on cleaned text."""
    hyp_clean, mapping = normalize_with_mapping(hyp_full)
    n = len(ref_list)
    m = len(hyp_clean)
    
    processed_refs = [normalize_text(r) for r in ref_list]
    
    # dp[i][j] = min total distance
    inf = float('inf')
    dp = [[inf] * (m + 1) for _ in range(n + 1)]
    parent = [[-1] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0
    
    MAX_SENT_LEN = 150 
    
    for i in range(1, n + 1):
        ref_p = processed_refs[i-1]
        for j in range(m + 1):
            start_k = max(0, j - MAX_SENT_LEN)
            for k in range(start_k, j + 1):
                if dp[i-1][k] == inf: continue
                hyp_p = hyp_clean[k:j]
                dist = Levenshtein.distance(ref_p, hyp_p)
                cost = dp[i-1][k] + dist
                if cost < dp[i][j]:
                    dp[i][j] = cost
                    parent[i][j] = k

    curr_j = m
    if dp[n][m] == inf:
        min_c = inf
        for j in range(m, -1, -1):
            if dp[n][j] < min_c:
                min_c = dp[n][j]; curr_j = j
                
    splits = [curr_j]
    for i in range(n, 0, -1):
        splits.append(parent[i][splits[-1]])
    splits.reverse()
    
    aligned_hyp_raw = []
    for i in range(n):
        s_clean, e_clean = splits[i], splits[i+1]
        s_raw = mapping[s_clean] if s_clean < len(mapping) else len(hyp_full)
        if i == 0: s_raw = 0
        e_raw = mapping[e_clean] if e_clean < len(mapping) else len(hyp_full)
        aligned_hyp_raw.append(hyp_full[s_raw:e_raw])
        
    return aligned_hyp_raw

def main():
    if len(sys.argv) == 3:
        # Mode: python evaluate_cer.py ref.txt hyp.txt
        ref_path = sys.argv[1]
        hyp_path = sys.argv[2]
        try:
            with open(ref_path, 'r', encoding='utf-8') as f:
                ref_lines = [l.strip() for l in f.read().splitlines() if l.strip()]
            with open(hyp_path, 'r', encoding='utf-8') as f:
                hyp_raw_full = f.read().strip()
        except Exception as e:
            print("Error reading files: {}".format(e))
            return
    else:
        # Default Mode: read combined input from input_data.txt
        try:
            with open('input_data.txt', 'r', encoding='utf-8') as f:
                input_text = f.read()
            
            ref_match = re.search(r'\[REF_BEGIN\](.*?)\[REF_END\]', input_text, re.DOTALL)
            hyp_match = re.search(r'\[HYP_BEGIN\](.*?)\[HYP_END\]', input_text, re.DOTALL)
            
            if not ref_match or not hyp_match:
                print("Error: Could not find [REF_BEGIN]...[REF_END] or [HYP_BEGIN]...[HYP_END] blocks in input_data.txt")
                return

            ref_lines = [line.strip() for line in ref_match.group(1).splitlines() if line.strip()]
            hyp_raw_full = hyp_match.group(1).strip()
        except FileNotFoundError:
            print("Error: input_data.txt not found. Usage: python evaluate_cer.py [ref_file hyp_file]")
            return

    # Align using char mode (master alignment)
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
            if ref_len == 0:
                ins, dele, sub, dist, cer = 0, 0, 0, 0, "NA"
            else:
                ins, dele, sub, dist = get_edit_details(ref_proc, hyp_proc)
                cer = round(dist / ref_len, 4)
                
            details.append({
                'doc_id': '', 'sent_id': i + 1, 'mode': mode,
                'ref_raw': ref_raw, 'hyp_raw_chunk': hyp_raw,
                'ref_proc': ref_proc, 'hyp_proc': hyp_proc,
                'ref_len': ref_len, 'hyp_len': len(hyp_proc),
                'ins': ins, 'del': dele, 'sub': sub, 'distance': dist, 'cer': cer, 'notes': ''
            })

    # Write UTF-8 Details
    with open('cer_details.csv', 'w', encoding='utf-8') as f:
        f.write("doc_id,sent_id,mode,ref_raw,hyp_raw_chunk,ref_proc,hyp_proc,ref_len,hyp_len,ins,del,sub,distance,cer,notes\n")
        for d in details:
            # Simple CSV quoting for safety
            row = [
                str(d['doc_id']),
                str(d['sent_id']),
                d['mode'],
                '"{}"'.format(d['ref_raw']),
                '"{}"'.format(d['hyp_raw_chunk']),
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
            f.write(",".join(row) + "\n")

    # Write SJIS Details for Windows/Excel
    with open('cer_details_sjis.csv', 'w', encoding='cp932', errors='replace') as f:
        f.write("doc_id,sent_id,mode,ref_raw,hyp_raw_chunk,ref_proc,hyp_proc,ref_len,hyp_len,ins,del,sub,distance,cer,notes\n")
        for d in details:
            row = [
                str(d['doc_id']),
                str(d['sent_id']),
                d['mode'],
                '"{}"'.format(d['ref_raw']),
                '"{}"'.format(d['hyp_raw_chunk']),
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
            f.write(",".join(row) + "\n")

    with open('cer_summary.csv', 'w', encoding='utf-8') as f:
        f.write("mode,count,valid_count,total_distance,total_ref_len,micro_cer,macro_cer\n")
        for mode in modes:
            v = [d for d in details if d['mode'] == mode and d['ref_len'] > 0]
            td = sum(d['distance'] for d in v)
            tl = sum(d['ref_len'] for d in v)
            micro = round(td / tl, 4) if tl > 0 else 0
            macro = round(sum(d['cer'] for d in v) / len(v), 4) if v else 0
            f.write("{},{},{},{},{},{:.4f},{:.4f}\n".format(mode, len(ref_lines), len(v), td, tl, micro, macro))

if __name__ == "__main__":
    main()
