# -*- coding: utf-8 -*-
"""
Data standardisation, fuzzy matching, and Circles of Power analysis for the Council of Savi.
"""

import pandas as pd
import numpy as np
import re
from datetime import date

# Pisan calendar month map (starts in April)
mesi_anno_pisano = {
    'Aprile': 1,
    'Maggio': 2,
    'Giugno': 3,
    'Luglio': 4,
    'Agosto': 5,
    'Settembre': 6,
    'Ottobre': 7,
    'Novembre': 8,
    'Dicembre': 9,
    'Gennaio': 10,
    'Febbraio': 11,
    'Marzo': 12
}

def levenshtein_distance(s1, s2):
    """Calculates Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def somiglianza_parole(w1, w2):
    """Calculates Levenshtein-based similarity between two words."""
    if w1 == w2:
        return 1.0
    max_len = max(len(w1), len(w2))
    if max_len == 0:
        return 0.0
    return 1.0 - (levenshtein_distance(w1, w2) / max_len)

def confronta_nomi_token(nome1, nome2):
    """
    Compares two names token by token, ignoring common particles and administrative titles,
    applying a length-difference penalty.
    """
    stop_words = {'di', 'ser', 'de', 'da', 'q.', 'fu', 'd.', 'del', 'degli', 'della'}

    def clean_tokens(name):
        tokens = str(name).lower().replace(',', '').split()
        return [t for t in tokens if t not in stop_words]

    parole1 = clean_tokens(nome1)
    parole2 = clean_tokens(nome2)

    len1, len2 = len(parole1), len(parole2)
    if len1 == 0 or len2 == 0:
        return 0.0

    p_corte = parole1 if len1 <= len2 else parole2
    p_lunghe = list(parole2 if len1 <= len2 else parole1)

    somma_somiglianze = 0.0
    for p_c in p_corte:
        miglior_punteggio = 0.0
        miglior_idx = -1
        for i, p_l in enumerate(p_lunghe):
            punteggio = somiglianza_parole(p_c, p_l)
            if punteggio > miglior_punteggio:
                miglior_punteggio = punteggio
                miglior_idx = i

        if miglior_idx != -1:
            somma_somiglianze += miglior_punteggio
            p_lunghe.pop(miglior_idx)

    punteggio_base = somma_somiglianze / len(p_corte)
    fattore_penalita = min(len1, len2) / max(len1, len2)

    return punteggio_base * fattore_penalita

def clean_and_pivot_savi(file_path_or_buffer):
    """
    Reads the Savi Excel file, pivots column groups by quartiere, cleans totals,
    extracts attestations, and explodes Anzianato participations with date parsing.
    """
    df = pd.read_excel(file_path_or_buffer, sheet_name=0)
    
    # Standardize column names
    df.columns = df.columns.astype(str).str.strip().str.lower()
    
    column_groups = [
        (0, 1, 2, 'ponte'),
        (3, 4, 5, 'foriporta'),
        (6, 7, 8, 'medio'),
        (9, 10, 11, 'kinzica')
    ]
    
    pivoted_dfs_list = []
    for col_n, col_n1, col_n2, q_name in column_groups:
        if col_n < len(df.columns) and col_n1 < len(df.columns) and col_n2 < len(df.columns):
            temp_df = df.iloc[:, [col_n, col_n1, col_n2]].copy()
            temp_df.columns = ['nome', 'attestazioni_savi', 'attestazioni_anzianato']
            temp_df['quartiere'] = q_name
            pivoted_dfs_list.append(temp_df)
            
    if not pivoted_dfs_list:
        raise ValueError("Il foglio Excel del Consiglio dei Savi non ha le colonne previste.")
        
    pivot_df = pd.concat(pivoted_dfs_list, ignore_index=True)
    
    # Drop empty name rows and strip names
    pivot_df = pivot_df.dropna(subset=['nome']).reset_index(drop=True)
    pivot_df['nome'] = pivot_df['nome'].astype(str).str.strip()
    
    # Exclude rows representing totals (e.g. Totale Ponte, TOTALE KINZICA)
    pivot_df = pivot_df[~pivot_df['nome'].str.contains('totale', case=False, na=True)].reset_index(drop=True)
    
    # 1. Extract Savi attestations counts for 1372 and 1377
    def extract_attestations(text, year):
        if pd.isna(text):
            return 0
        pattern = rf"X\s*(\d+)\s*=\s*.*?{year}"
        match = re.search(pattern, str(text), re.IGNORECASE)
        return int(match.group(1)) if match else 0

    pivot_df['attestazioni_1372'] = pivot_df['attestazioni_savi'].apply(lambda x: extract_attestations(x, 1372))
    pivot_df['attestazioni_1377'] = pivot_df['attestazioni_savi'].apply(lambda x: extract_attestations(x, 1377))

    # 2. Set Nobile tag
    pivot_df['Nobile'] = pivot_df['attestazioni_anzianato'].astype(str).str.strip().str.lower().apply(
        lambda x: 'Sì' if x == 'nobile' else 'No'
    )

    # 3. Explode Anzianato participations
    def split_anzianato(row):
        text = str(row['attestazioni_anzianato'])
        if row['Nobile'] == 'Sì' or text.lower() in ['nan', 'none'] or not text.strip():
            return [{'anno': None, 'mesi': None}]
        
        parts = [p.strip() for p in text.split('//') if p.strip()]
        results = []
        for part in parts:
            year_match = re.search(r'(\d{4})', part)
            year = year_match.group(1) if year_match else None
            mesi = part.split(year)[0].strip() if year else part
            results.append({'anno': year, 'mesi': mesi})
        return results

    expanded_data = []
    for _, row in pivot_df.iterrows():
        attestazioni = split_anzianato(row)
        for att in attestazioni:
            new_row = row.to_dict()
            new_row.update(att)
            expanded_data.append(new_row)

    final_df = pd.DataFrame(expanded_data)
    if 'attestazioni_anzianato' in final_df.columns:
        final_df = final_df.drop(columns=['attestazioni_anzianato'])
        
    # Normalize month values replacing _ with -
    final_df['mesi'] = final_df['mesi'].astype(str).str.replace('_', '-', regex=False)
    
    # 4. Parse date ranges for mandate timeline
    date_inizio_mandato = []
    date_fine_mandato = []
    for _, row in final_df.iterrows():
        anni = row['anno']
        mesi = row['mesi']
        data_inizio = None
        data_fine = None
        
        if isinstance(mesi, str) and mesi.lower() not in ['none', 'nan']:
            parti_mesi = [m.strip().capitalize() for m in mesi.split('-') if m.strip()]
            if len(parti_mesi) >= 2:
                m_in = mesi_anno_pisano.get(parti_mesi[0])
                m_fi = mesi_anno_pisano.get(parti_mesi[-1])
                if m_in and m_fi and anni:
                    if isinstance(anni, str) and '-' in anni:
                        y_parts = anni.split('-')
                        try:
                            y_in = int(float(y_parts[0]))
                            y_fi = int(float(y_parts[1]))
                        except ValueError:
                            y_in = y_fi = None
                    else:
                        try:
                            y_in = y_fi = int(float(anni))
                        except ValueError:
                            y_in = y_fi = None
                            
                    if y_in and y_fi:
                        try:
                            data_inizio = date(y_in, m_in, 1)
                            data_fine = date(y_fi, m_fi, 1)
                        except ValueError:
                            pass
        date_inizio_mandato.append(data_inizio)
        date_fine_mandato.append(data_fine)
        
    final_df['data inizio mandato'] = date_inizio_mandato
    final_df['data fine mandato'] = date_fine_mandato
    
    return final_df

def compute_circles_of_power(df_savi, df_anziani):
    """
    Aligns Savi names with Anziani names via fuzzy matching and categorizes individuals 
    into five Circles of Power. Sychronizes family names dynamically based on matches.
    """
    # Create clean lowercase/standard 'famiglia' column in Anziani
    df_anziani_clean = df_anziani.copy()
    if 'Famiglia' in df_anziani_clean.columns:
        df_anziani_clean['famiglia'] = df_anziani_clean['Famiglia']
    elif 'nota' in df_anziani_clean.columns:
        df_anziani_clean['famiglia'] = df_anziani_clean['nota']
        
    df_anziani_clean['famiglia'] = df_anziani_clean['famiglia'].astype(str).str.strip()
    
    # Deduplicate Anziani
    df_anziani_unici = df_anziani_clean.drop_duplicates(subset=['nome']).copy()
    
    # Guess initial family names for Savi
    def get_family_guess(name):
        if pd.isna(name):
            return "Ignoto"
        parts = str(name).strip().split()
        return parts[-1] if len(parts) > 1 else parts[0]
        
    df_consiglio_savi = df_savi.copy()
    df_consiglio_savi['famiglia'] = df_consiglio_savi['nome'].apply(get_family_guess)
    
    nomi_savi = set(df_consiglio_savi['nome'].unique())
    nomi_anziani = set(df_anziani_unici['nome'].unique())
    
    # 1. Fuzzy Matching
    mapping_fuzzy = {}
    correzione_famiglia_savi = {}
    
    for ns in nomi_savi:
        miglior_score = 0.0
        miglior_match = None
        for na in nomi_anziani:
            if ns == na:
                miglior_score = 1.0
                miglior_match = na
                break
            score = confronta_nomi_token(ns, na)
            if score > miglior_score:
                miglior_score = score
                miglior_match = na
                
        if miglior_score > 0.857:
            mapping_fuzzy[ns] = miglior_match
            fam_ufficiale = df_anziani_unici[df_anziani_unici['nome'] == miglior_match]['famiglia'].values[0]
            correzione_famiglia_savi[ns] = fam_ufficiale
            
    # Apply corrected families
    for nome_savi, fam_vera in correzione_famiglia_savi.items():
        df_consiglio_savi.loc[df_consiglio_savi['nome'] == nome_savi, 'famiglia'] = fam_vera
        
    # 2. Circle Calculations
    nomi_savi_in_entrambi = set(mapping_fuzzy.keys())
    nobili_savi = set(df_consiglio_savi[df_consiglio_savi['Nobile'] == 'Sì']['nome'].unique())
    
    # C0: Nobili present only in the Savi (not matched to Anziani)
    cerchio_0 = [n for n in nobili_savi if n not in nomi_savi_in_entrambi]
    
    # C1: Nobili present in both councils (matched to Anziani)
    cerchio_1 = [n for n in nobili_savi if n in nomi_savi_in_entrambi]
    
    # C2: Non-noble individuals present in both councils (Anziani match names)
    cerchio_2 = [na for ns, na in mapping_fuzzy.items() if ns not in nobili_savi]
    
    # Families representing C2
    famiglie_cerchio_2 = set(df_anziani_unici[df_anziani_unici['nome'].isin(cerchio_2)]['famiglia'].unique())
    
    # Exclude matched Anziani from C3 and C4
    nomi_anziani_matchati = set(mapping_fuzzy.values())
    anziani_esterni_unici = df_anziani_unici[~df_anziani_unici['nome'].isin(nomi_anziani_matchati)]
    
    # C3: Anziani who did not sit in the Savi themselves, but share a family with C2
    cerchio_3 = anziani_esterni_unici[anziani_esterni_unici['famiglia'].isin(famiglie_cerchio_2)]['nome'].unique().tolist()
    
    # C4: Anziani who did not sit in the Savi themselves, and do not share a family with C2
    cerchio_4 = anziani_esterni_unici[~anziani_esterni_unici['famiglia'].isin(famiglie_cerchio_2)]['nome'].unique().tolist()
    
    # Clean strings and drop nan/non-string values
    c0_clean = sorted(list(set([n for n in cerchio_0 if isinstance(n, str) and n.strip() and n.lower() != 'nan'])))
    c1_clean = sorted(list(set([n for n in cerchio_1 if isinstance(n, str) and n.strip() and n.lower() != 'nan'])))
    c2_clean = sorted(list(set([n for n in cerchio_2 if isinstance(n, str) and n.strip() and n.lower() != 'nan'])))
    c3_clean = sorted(list(set([n for n in cerchio_3 if isinstance(n, str) and n.strip() and n.lower() != 'nan'])))
    c4_clean = sorted(list(set([n for n in cerchio_4 if isinstance(n, str) and n.strip() and n.lower() != 'nan'])))

    return {
        'df_savi': df_consiglio_savi,
        'df_anziani_unici': df_anziani_unici,
        'mapping_fuzzy': mapping_fuzzy,
        'cerchio_0': c0_clean,
        'cerchio_1': c1_clean,
        'cerchio_2': c2_clean,
        'cerchio_3': c3_clean,
        'cerchio_4': c4_clean
    }

def precompute_and_save_savi_data(savi_excel_path, anziani_csv_path, output_dir="data"):
    """
    Runs the standardisation and fuzzy join on the Savi and Anziani databases
    and saves the optimized outputs to CSV files to prevent real-time lag.
    """
    import os
    df_savi_raw = clean_and_pivot_savi(savi_excel_path)
    df_anziani_raw = pd.read_csv(anziani_csv_path)
    
    results = compute_circles_of_power(df_savi_raw, df_anziani_raw)
    
    df_savi_std = results['df_savi']
    df_anz_unici = results['df_anziani_unici']
    
    os.makedirs(output_dir, exist_ok=True)
    df_savi_std.to_csv(os.path.join(output_dir, "savi_standardized.csv"), index=False)
    
    c0 = results['cerchio_0']
    c1 = results['cerchio_1']
    c2 = results['cerchio_2']
    c3 = results['cerchio_3']
    c4 = results['cerchio_4']
    
    records = []
    
    # C0: noble Savi
    for name in c0:
        row = df_savi_std[df_savi_std['nome'] == name].iloc[0]
        records.append({
            'nome': name,
            'famiglia': row['famiglia'],
            'quartiere': row['quartiere'],
            'nobile': 'Sì',
            'cerchio': 'C0'
        })
        
    # C1: noble in both
    for name in c1:
        row = df_savi_std[df_savi_std['nome'] == name].iloc[0]
        records.append({
            'nome': name,
            'famiglia': row['famiglia'],
            'quartiere': row['quartiere'],
            'nobile': 'Sì',
            'cerchio': 'C1'
        })
        
    # C2: non-noble matched Anziani names
    for name in c2:
        row = df_anz_unici[df_anz_unici['nome'] == name].iloc[0]
        records.append({
            'nome': name,
            'famiglia': row['famiglia'],
            'quartiere': row['quartiere'],
            'nobile': 'No',
            'cerchio': 'C2'
        })
        
    # C3: Anziani
    for name in c3:
        row = df_anz_unici[df_anz_unici['nome'] == name].iloc[0]
        records.append({
            'nome': name,
            'famiglia': row['famiglia'],
            'quartiere': row['quartiere'],
            'nobile': 'No',
            'cerchio': 'C3'
        })
        
    # C4: Anziani
    for name in c4:
        row = df_anz_unici[df_anz_unici['nome'] == name].iloc[0]
        records.append({
            'nome': name,
            'famiglia': row['famiglia'],
            'quartiere': row['quartiere'],
            'nobile': 'No',
            'cerchio': 'C4'
        })
        
    df_circles = pd.DataFrame(records)
    df_circles.to_csv(os.path.join(output_dir, "savi_circles.csv"), index=False)
    print("Precomputed Savi data saved successfully!")

