# -*- coding: utf-8 -*-
"""
Robust Excel Standardization Module for Pisan Medieval Politician Database.
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

def find_data_sheet(xls):
    """
    Scans sheets in Excel file and returns the name of the first sheet containing
    the necessary structure (both 'anno' and 'mesi' columns and role indicators).
    """
    for sheet_name in xls.sheet_names:
        try:
            # Read first row to check headers
            df = pd.read_excel(xls, sheet_name=sheet_name, nrows=1)
            cols = [str(c).strip().lower() for c in df.columns if not pd.isna(c)]
            if 'anno' in cols and 'mesi' in cols:
                # Must contain at least one column referencing priore or anziano
                has_roles = any('priore' in c or 'anziano' in c for c in cols)
                if has_roles:
                    return sheet_name
        except Exception:
            continue
    return None

def find_column_match(columns, role, neighborhood=None):
    """
    Finds name, primary note, and secondary note columns in the list of columns
    matching a role and optional neighborhood.
    Returns (name_col, nota_col, altra_nota_col) or (None, None, None)
    """
    name_col = None
    nota_col = None
    altra_nota_col = None
    
    # 1. Identify name column (Must NOT contain 'nota'/'note' keywords unless 'notaio')
    for col in columns:
        col_lower = str(col).lower()
        is_note_keyword = ('nota' in col_lower and 'notaio' not in col_lower) or 'note' in col_lower or 'altra' in col_lower or 'altre' in col_lower
        if is_note_keyword:
            continue
            
        if neighborhood:
            if neighborhood not in col_lower:
                continue
            if role == 'priore':
                if 'priore' in col_lower:
                    name_col = col
                    break
            elif 'anziano' in col_lower:
                if '#1' in role or '1' in role:
                    if '1' in col_lower or '#1' in col_lower:
                        name_col = col
                        break
                elif '#2' in role or '2' in role:
                    if '2' in col_lower or '#2' in col_lower:
                        name_col = col
                        break
        else:
            if role == 'notaio anziani':
                if 'notaio' in col_lower:
                    name_col = col
                    break
            elif role == 'canc. maior':
                if 'canc' in col_lower:
                    name_col = col
                    break
                    
    if name_col:
        # 2. Identify associated notes columns
        for col in columns:
            col_lower = str(col).lower()
            if col == name_col:
                continue
            
            is_note = ('nota' in col_lower and 'notaio' not in col_lower) or 'note' in col_lower
            if not is_note:
                continue
                
            is_other = 'altra' in col_lower or 'altre' in col_lower
            
            # Check context match
            matches_context = False
            if neighborhood:
                matches_context = (neighborhood in col_lower) and (
                    ('priore' in col_lower if role == 'priore' else 'anziano' in col_lower)
                )
                if matches_context and role != 'priore':
                    if '#1' in role or '1' in role:
                        matches_context = '1' in col_lower or '#1' in col_lower
                    elif '#2' in role or '2' in role:
                        matches_context = '2' in col_lower or '#2' in col_lower
            else:
                if role == 'notaio anziani':
                    matches_context = 'notaio' in col_lower
                elif role == 'canc. maior':
                    matches_context = 'canc' in col_lower
            
            if matches_context:
                if is_other:
                    altra_nota_col = col
                else:
                    nota_col = col
                    
    return name_col, nota_col, altra_nota_col

def extract_year_range(anno_val):
    """Parses standard or range years (e.g., 1370-1372 or 1370) into start and end years."""
    if pd.isna(anno_val):
        return None, None
    anno_str = str(anno_val).strip()
    if '-' in anno_str:
        parts = anno_str.split('-')
        try:
            val_start = int(float(parts[0].strip()))
        except ValueError:
            val_start = None
        try:
            val_end = int(float(parts[1].strip()))
        except ValueError:
            val_end = val_start
        return val_start, val_end
    else:
        try:
            val = int(float(anno_str))
            return val, val
        except ValueError:
            return None, None

def extract_month_range(mesi_val):
    """Parses standard or range months (e.g., Aprile-Settembre or Aprile) into start and end months."""
    if pd.isna(mesi_val):
        return None, None
    mesi_str = str(mesi_val).strip()
    if '-' in mesi_str:
        parts = mesi_str.split('-')
        m_start = parts[0].strip()
        m_end = parts[-1].strip()
        return m_start, m_end
    else:
        return mesi_str, mesi_str

def parse_single_medieval_date(month_str, year_val):
    """Creates a datetime.date object using the Pisan medieval calendar month ordering."""
    if pd.isna(month_str) or pd.isna(year_val) or year_val is None:
        return None
    try:
        m_clean = str(month_str).strip().capitalize()
        m_num = mesi_anno_pisano.get(m_clean)
        if m_num is None:
            # Fallback substring match
            for key, val in mesi_anno_pisano.items():
                if key.lower() in m_clean.lower():
                    m_num = val
                    break
            if m_num is None:
                m_num = 1 # Fallback to April
        return date(int(year_val), m_num, 1)
    except Exception:
        return None

def robust_standardize_excel(file_path_or_buffer):
    """
    Standardizes Pisan database excel by finding the proper sheet, resolving role 
    columns dynamically, cleaning dates, and melting roles into a tidy format.
    """
    # 1. Load Excel
    xls = pd.ExcelFile(file_path_or_buffer)
    
    # 2. Find target sheet
    sheet_name = find_data_sheet(xls)
    if not sheet_name:
        raise ValueError("No valid sheet containing 'anno', 'mesi', and role columns found.")
        
    df = pd.read_excel(xls, sheet_name=sheet_name)
    
    # Keep copy of original columns for warning/logging or dynamic mapping
    orig_cols = list(df.columns)
    
    # Lowercase & strip dataframe columns for matching consistency
    df.columns = df.columns.astype(str).str.strip().str.lower()
    cols_lower = list(df.columns)
    
    # 3. Build Mandate dates
    date_inizio_mandato = []
    date_fine_mandato = []
    numero_mandato = []
    
    for idx, row in df.iterrows():
        numero_mandato.append(idx + 1)
        
        anno_val = row.get('anno')
        mesi_val = row.get('mesi')
        
        anno_start, anno_end = extract_year_range(anno_val)
        m_start, m_end = extract_month_range(mesi_val)
        
        dt_start = parse_single_medieval_date(m_start, anno_start)
        dt_end = parse_single_medieval_date(m_end, anno_end)
        
        date_inizio_mandato.append(dt_start)
        date_fine_mandato.append(dt_end)
        
    df['data inizio mandato'] = date_inizio_mandato
    df['data fine mandato'] = date_fine_mandato
    df['numero mandato'] = numero_mandato
    
    # Ensure 'note data' exists, fill with NaN if missing
    if 'note data' not in df.columns:
        df['note data'] = np.nan
        
    # 4. Standardize Columns Melting
    quartieri = ['ponte', 'medio', 'foriporta', 'kinzica']
    ruoli = ['priore', 'anziano #1', 'anziano #2']
    altri_ruoli = ['notaio anziani', 'canc. maior']
    
    dfs_dict = {}
    
    # Neighborhood roles
    for quartiere in quartieri:
        for ruolo in ruoli:
            name_col, nota_col, altra_col = find_column_match(df.columns, ruolo, quartiere)
            if not name_col:
                # Skip this role/neighborhood combo if it's missing in the sheet
                continue
                
            # Construct subset dataframe
            col_data = {
                'numero mandato': df['numero mandato'],
                'data inizio mandato': df['data inizio mandato'],
                'data fine mandato': df['data fine mandato'],
                'nome': df[name_col],
                'nota': df[nota_col] if (nota_col and nota_col in df.columns) else np.nan,
                'altra nota': df[altra_col] if (altra_col and altra_col in df.columns) else np.nan,
                'anno': df['anno'],
                'mesi': df['mesi'],
                'note data': df['note data']
            }
            column_df = pd.DataFrame(col_data)
            column_df['ruolo'] = ruolo
            column_df['quartiere'] = quartiere
            
            dfs_dict[f"{ruolo}_{quartiere}"] = column_df
            
    # Other administrative roles
    for ruolo in altri_ruoli:
        name_col, nota_col, altra_col = find_column_match(df.columns, ruolo)
        if not name_col:
            continue
            
        col_data = {
            'numero mandato': df['numero mandato'],
            'data inizio mandato': df['data inizio mandato'],
            'data fine mandato': df['data fine mandato'],
            'nome': df[name_col],
            'nota': df[nota_col] if (nota_col and nota_col in df.columns) else np.nan,
            'altra nota': df[altra_col] if (altra_col and altra_col in df.columns) else np.nan,
            'anno': df['anno'],
            'mesi': df['mesi'],
            'note data': df['note data']
        }
        column_df = pd.DataFrame(col_data)
        column_df['ruolo'] = ruolo
        column_df['quartiere'] = np.nan
        
        dfs_dict[ruolo] = column_df
        
    if not dfs_dict:
        raise ValueError("Could not extract any role data columns from the sheet. Check column headers.")
        
    # Concatenate all subsets
    total_df = pd.concat(dfs_dict.values(), axis=0, ignore_index=True)
    
    # Strip any potential leading/trailing space in the extracted names
    if 'nome' in total_df.columns:
        total_df['nome'] = total_df['nome'].astype(str).str.strip()
        # Clean null-like strings like "nan"
        total_df.loc[total_df['nome'].str.lower() == 'nan', 'nome'] = np.nan
        total_df.loc[total_df['nome'] == '', 'nome'] = np.nan
        
    return total_df
