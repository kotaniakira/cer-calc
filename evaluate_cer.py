import sys
import re
import unicodedata
import pykakasi
import Levenshtein

def normalize_text(text):
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
    kana = "".join([item['hira'] for item in res]).replace('\u30fc', '')
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
        elif ci > 0 and dp[ci-1][cj-1] + 1 == cost:
            sub += 1; ci -= 1; cj -= 1
        elif ci > 0 and dp[ci-1][cj] + 1 == cost:
            dele += 1; ci -= 1
        elif cj > 0 and dp[ci][cj-1] + 1 == cost:
            ins += 1; cj -= 1
        else: break
    return ins, dele, sub, dp[n][m]

def align_sentences(ref_list, hyp_full):
    hyp_clean, mapping = normalize_with_mapping(hyp_full)
    n, m = len(ref_list), len(hyp_clean)
    processed_refs = [normalize_text(r) for r in ref_list]
    dp = [[float('inf')] * (m + 1) for _ in range(n + 1)]
    parent = [[-1] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0
    MAX_LEN = 100 
    for i in range(1, n + 1):
        ref_p = processed_refs[i-1]
        for j in range(m + 1):
            for k in range(max(0, j - MAX_LEN), j + 1):
                if dp[i-1][k] == float('inf'): continue
                hyp_segment = hyp_clean[k:j]
                dist = Levenshtein.distance(ref_p, hyp_segment)
                cost = dp[i-1][k] + dist
                if cost < dp[i][j]:
                    dp[i][j] = cost
                    parent[i][j] = k
    curr_j = m
    if dp[n][m] == float('inf'):
        best_val = float('inf')
        for j in range(m, -1, -1):
            if dp[n][j] < best_val: best_val = dp[n][j]; curr_j = j
    splits = [curr_j]
    for i in range(n, 0, -1):
        splits.append(parent[i][splits[-1]])
    splits.reverse()
    raw_chunks = []
    for i in range(n):
        s_clean, e_clean = splits[i], splits[i+1]
        if s_clean == -1: raw_chunks.append(""); continue
        s_raw = mapping[s_clean] if s_clean < len(mapping) else len(hyp_full)
        if i == 0: s_raw = 0
        e_raw = mapping[e_clean] if e_clean < len(mapping) else len(hyp_full)
        raw_chunks.append(hyp_full[s_raw:e_raw])
    return raw_chunks

def main():
    with open('input_data.txt', 'r', encoding='utf-8') as f: txt = f.read()
    r_m = re.search(r'\x5bREF_BEGIN\x5d(.*?)(\x5bREF_END\x5d)', txt, re.DOTALL)
    h_m = re.search(r'\x5bHYP_BEGIN\x5d(.*?)(\x5bHYP_END\x5d)', txt, re.DOTALL)
    if not r_m or not h_m: return
    ref_lines = [l.strip() for l in r_m.group(1).splitlines() if l.strip()]
    hyp_raw = h_m.group(1).strip()
    hyp_chunks = align_sentences(ref_lines, hyp_raw)
    details = []
    for mode in ['char', 'kana']:
        for i, (r_raw, h_raw) in enumerate(zip(ref_lines, hyp_chunks)):
            r_p = normalize_text(r_raw) if mode == 'char' else to_kana(r_raw)
            h_p = normalize_text(h_raw) if mode == 'char' else to_kana(h_raw)
            rl = len(r_p)
            if rl == 0:
                ins, dele, sub, dist, cer = 0, 0, 0, 0, "NA"
            else:
                ins, dele, sub, dist = get_edit_details(r_p, h_p)
                cer = round(dist / rl, 4)
            details.append({'id': i+1, 'mode': mode, 'r_raw': r_raw, 'h_raw': h_raw, 'r_p': r_p, 'h_p': h_p, 'rl': rl, 'hl': len(h_p), 'ins': ins, 'del': dele, 'sub': sub, 'd': dist, 'cer': cer})
    # Write UTF-8 Details
    with open('cer_details.csv', 'w', encoding='utf-8') as f:
        f.write("doc_id,sent_id,mode,ref_raw,hyp_raw_chunk,ref_proc,hyp_proc,ref_len,hyp_len,ins,del,sub,distance,cer,notes\n")
        for d in details:
            f.write(f", {d['id']},{d['mode']},\"{d['r_raw']}\",\"{d['h_raw']}\",{d['r_p']},{d['h_p']},{d['rl']},{d['hl']},{d['ins']},{d['del']},{d['sub']},{d['d']},{d['cer']},\n")

    # Write SJIS Details for Windows/Excel
    with open('cer_details_sjis.csv', 'w', encoding='cp932', errors='replace') as f:
        f.write("doc_id,sent_id,mode,ref_raw,hyp_raw_chunk,ref_proc,hyp_proc,ref_len,hyp_len,ins,del,sub,distance,cer,notes\n")
        for d in details:
            f.write(f", {d['id']},{d['mode']},\"{d['r_raw']}\",\"{d['h_raw']}\",{d['r_p']},{d['h_p']},{d['rl']},{d['hl']},{d['ins']},{d['del']},{d['sub']},{d['d']},{d['cer']},\n")
    with open('cer_summary.csv', 'w', encoding='utf-8') as f:
        f.write("mode,count,valid_count,total_distance,total_ref_len,micro_cer,macro_cer\n")
        for mode in ['char', 'kana']:
            v = [d for d in details if d['mode'] == mode and d['rl'] > 0]
            td, tl = sum(d['d'] for d in v), sum(d['rl'] for d in v)
            mi = round(td / tl, 4) if tl > 0 else 0
            ma = round(sum(d['cer'] for d in v) / len(v), 4) if v else 0
            f.write(f"{mode},{len(ref_lines)},{len(v)},{td},{tl},{mi:.4f},{ma:.4f}\n")

if __name__ == "__main__":
    main()