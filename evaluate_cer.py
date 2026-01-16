import sys
import re
import unicodedata
import pykakasi
import Levenshtein

# --- Preprocessing ---

def normalize_text(text):
    # NFKC -> Remove whitespace -> Remove punctuations
    text = unicodedata.normalize('NFKC', text)
    text = "".join(text.split())
    res = []
    jp_puncts = "\u3002\u3001\uff0c\uff0e\u30fb\u300c\u300d\u300e\u300f\uff08\uff09\uff3b\uff3d\u3010\u3011\u2026\u2014"
    for char in text:
        if unicodedata.category(char).startswith('P') or char in jp_puncts: continue
        res.append(char)
    return "".join(res)

def normalize_with_mapping(text):
    clean_chars, mapping = [], []
    jp_puncts = "\u3002\u3001\uff0c\uff0e\u30fb\u300c\u300d\u300e\u300f\uff08\uff09\uff3b\uff3d\u3010\u3011\u2026\u2014"
    for i, c in enumerate(text):
        nc = unicodedata.normalize('NFKC', c)
        if nc.strip() == "": continue
        if unicodedata.category(nc).startswith('P') or nc in jp_puncts: continue
        for sub_c in nc:
            clean_chars.append(sub_c)
            mapping.append(i)
    return "".join(clean_chars), mapping

kks = pykakasi.kakasi()
def to_kana(text):
    res = kks.convert(text)
    parts = [item['hira'] for item in res]
    kana = "".join(parts).replace('\u30fc', '')
    return normalize_text(kana)

def get_edit_details(ref, hyp):
    n, m = len(ref), len(hyp)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1): dp[i][0] = i
    for j in range(m + 1): dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref[i-1] == hyp[j-1]: dp[i][j] = dp[i-1][j-1]
            else: dp[i][j] = min(dp[i-1][j-1], dp[i-1][j], dp[i][j-1]) + 1
    ins, dele, sub = 0, 0, 0
    ci, cj = n, m
    while ci > 0 or cj > 0:
        cost = dp[ci][cj]
        if ci > 0 and cj > 0 and ref[ci-1] == hyp[cj-1]: ci -= 1; cj -= 1
        elif ci > 0 and cj > 0 and dp[ci-1][cj-1] + 1 == cost: sub += 1; ci -= 1; cj -= 1
        elif ci > 0 and dp[ci-1][cj] + 1 == cost: dele += 1; ci -= 1
        else: ins += 1; cj -= 1
    return ins, dele, sub, dp[n][m]

def align_sentences(ref_list, hyp_full):
    # Master alignment based on CHARACTER mode (visual representation)
    # This ensures "段取り画面" matches "段取り画面" best.
    hyp_clean, mapping = normalize_with_mapping(hyp_full)
    n, m = len(ref_list), len(hyp_clean)
    processed_refs = [normalize_text(r) for r in ref_list]
    
    inf = float('inf')
    dp = [[inf] * (m + 1) for _ in range(n + 1)]
    parent = [[-1] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0
    MAX_LEN = 150 
    
    for i in range(1, n + 1):
        ref_p = processed_refs[i-1]
        for j in range(m + 1):
            start_k = max(0, j - MAX_LEN)
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
            if dp[n][j] < min_c: min_c = dp[n][j]; curr_j = j
    splits = [curr_j]
    for i in range(n, 0, -1):
        splits.append(parent[i][splits[-1]])
    splits.reverse()
    
    aligned_chunks = []
    for i in range(n):
        s_clean, e_clean = splits[i], splits[i+1]
        if s_clean == -1: aligned_chunks.append(""); continue
        s_raw = mapping[s_clean] if s_clean < len(mapping) else len(hyp_full)
        if i == 0: s_raw = 0
        e_raw = mapping[e_clean] if e_clean < len(mapping) else len(hyp_full)
        aligned_chunks.append(hyp_full[s_raw:e_raw])
    return aligned_chunks

def main():
    if len(sys.argv) == 3:
        try:
            with open(sys.argv[1], 'r', encoding='utf-8') as f: ref_lines = [l.strip() for l in f.read().splitlines() if l.strip()]
            with open(sys.argv[2], 'r', encoding='utf-8') as f: hyp_raw_full = f.read().strip()
        except Exception as e: print(f"Error: {e}"); return
    else:
        try:
            with open('input_data.txt', 'r', encoding='utf-8') as f: txt = f.read()
            rm = re.search(r'\[REF_BEGIN\](.*?)\[REF_END\]', txt, re.DOTALL)
            hm = re.search(r'\[HYP_BEGIN\](.*?)\[HYP_END\]', txt, re.DOTALL)
            if not rm or not hm: return
            ref_lines = [l.strip() for l in rm.group(1).splitlines() if l.strip()]
            hyp_raw_full = hm.group(1).strip()
        except: return

    # Align
    hyp_chunks = align_sentences(ref_lines, hyp_raw_full)
    
    results = []
    
    # Calculate both char and kana stats for each aligned pair
    for i, (r_raw, h_raw) in enumerate(zip(ref_lines, hyp_chunks)):
        # Char metrics
        c_ref = normalize_text(r_raw)
        c_hyp = normalize_text(h_raw)
        c_len = len(c_ref)
        if c_len > 0:
            c_ins, c_del, c_sub, c_dist = get_edit_details(c_ref, c_hyp)
            c_cer = round(c_dist / c_len, 4)
        else:
            c_ins, c_del, c_sub, c_dist, c_cer = 0, 0, 0, 0, "NA"
            
        # Kana metrics
        k_ref = to_kana(r_raw)
        k_hyp = to_kana(h_raw)
        k_len = len(k_ref)
        if k_len > 0:
            k_ins, k_del, k_sub, k_dist = get_edit_details(k_ref, k_hyp)
            k_cer = round(k_dist / k_len, 4)
        else:
            k_ins, k_del, k_sub, k_dist, k_cer = 0, 0, 0, 0, "NA"
            
        results.append({
            'id': i + 1,
            'ref_raw': r_raw, 'hyp_raw': h_raw,
            'c_ref': c_ref, 'c_hyp': c_hyp, 'c_len': c_len, 'c_hyp_len': len(c_hyp),
            'c_ins': c_ins, 'c_del': c_del, 'c_sub': c_sub, 'c_dist': c_dist, 'c_cer': c_cer,
            'k_ref': k_ref, 'k_hyp': k_hyp, 'k_len': k_len, 'k_hyp_len': len(k_hyp),
            'k_ins': k_ins, 'k_del': k_del, 'k_sub': k_sub, 'k_dist': k_dist, 'k_cer': k_cer
        })

    # Header with Japanese descriptions
    header = [
        "ID", 
        "正解文(Original)", "仮説文(Original)", 
        "評価文(Char)", "評価文(Char_Hyp)", "文字数(Char)", "挿入(Char)", "削除(Char)", "置換(Char)", "距離(Char)", "CER(Char)",
        "評価文(Kana)", "評価文(Kana_Hyp)", "文字数(Kana)", "挿入(Kana)", "削除(Kana)", "置換(Kana)", "距離(Kana)", "CER(Kana)"
    ]
    
    # Save CSVs
    def write_csv(filename, encoding):
        with open(filename, 'w', encoding=encoding, errors='replace') as f:
            f.write(",".join(header) + "\n")
            for r in results:
                row = [
                    str(r['id']),
                    '"{}"'.format(r['ref_raw'].replace('"', '""')),
                    '"{}"'.format(r['hyp_raw'].replace('"', '""')),
                    r['c_ref'], r['c_hyp'], str(r['c_len']), str(r['c_ins']), str(r['c_del']), str(r['c_sub']), str(r['c_dist']), str(r['c_cer']),
                    r['k_ref'], r['k_hyp'], str(r['k_len']), str(r['k_ins']), str(r['k_del']), str(r['k_sub']), str(r['k_dist']), str(r['k_cer'])
                ]
                f.write(",".join(row) + "\n")

    write_csv('cer_details.csv', 'utf-8')
    write_csv('cer_details_sjis.csv', 'cp932')
    
    # Summary
    valid_c = [r for r in results if isinstance(r['c_cer'], float)]
    valid_k = [r for r in results if isinstance(r['k_cer'], float)]
    
    def calc_summary(items, key_dist, key_len, key_cer):
        if not items: return 0, 0, 0, 0
        td = sum(i[key_dist] for i in items)
        tl = sum(i[key_len] for i in items)
        mi = td / tl if tl else 0
        ma = sum(i[key_cer] for i in items) / len(items)
        return td, tl, mi, ma

    ctd, ctl, cmi, cma = calc_summary(valid_c, 'c_dist', 'c_len', 'c_cer')
    ktd, ktl, kmi, kma = calc_summary(valid_k, 'k_dist', 'k_len', 'k_cer')
    
    with open('cer_summary.csv', 'w', encoding='utf-8') as f:
        f.write("Type,Count,Total_Dist,Total_Len,Micro_CER,Macro_CER\n")
        f.write(f"Char,{len(valid_c)},{ctd},{ctl},{cmi:.4f},{cma:.4f}\n")
        f.write(f"Kana,{len(valid_k)},{ktd},{ktl},{kmi:.4f},{kma:.4f}\n")

if __name__ == "__main__":
    main()
