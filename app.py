# -*- coding: utf-8 -*-
"""
Streamlit Web Application for Pisan Medieval Politician Database (1344-1392)
Academic & Professional Edition (No Emojis, Pastel & Neutral Color Systems)
"""

import streamlit as st
import pandas as pd
import numpy as np
import io
import zipfile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta

# Import standardization backend and helpers
from standardize import robust_standardize_excel, extract_year_range
# Import Savi processing functions
from savi_process import clean_and_pivot_savi, compute_circles_of_power, precompute_and_save_savi_data

# Page configuration
st.set_page_config(
    page_title="Pisa Medieval Politician Database",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

def compute_turnover_metrics(df, selected_roles, start_mandate, end_mandate, step_size=1, column_name='nome'):
    """
    Computes turnover metrics for a given set of roles and window of mandates.
    """
    if not selected_roles or df is None or df.empty:
        return None
        
    df_role_filtered = df[df['ruolo'].isin(selected_roles)].copy()
    df_window = df_role_filtered[
        (df_role_filtered['numero mandato'] >= start_mandate) &
        (df_role_filtered['numero mandato'] <= end_mandate)
    ]
    
    active_mandates = sorted(df_window['numero mandato'].dropna().unique())
    if len(active_mandates) < 1:
        return None
        
    members_counts = df_window[column_name].value_counts().dropna()
    
    start_members = set(df_role_filtered[df_role_filtered['numero mandato'] == start_mandate][column_name].dropna().unique())
    end_members = set(df_role_filtered[df_role_filtered['numero mandato'] == end_mandate][column_name].dropna().unique())
    shared_members = start_members & end_members
    pct_overlap_start = (len(shared_members) / len(start_members)) * 100 if start_members else 0.0
    
    turnovers = []
    turnover_chart_data = []
    
    df_councils = df[['numero mandato', 'anno', 'mesi']].dropna(subset=['anno', 'mesi']).drop_duplicates().sort_values(by='numero mandato')
    
    for i in range(len(active_mandates)):
        if i + step_size < len(active_mandates):
            m_curr = active_mandates[i]
            m_next = active_mandates[i + step_size]
            members_curr = set(df_role_filtered[df_role_filtered['numero mandato'] == m_curr][column_name].dropna().unique())
            members_next = set(df_role_filtered[df_role_filtered['numero mandato'] == m_next][column_name].dropna().unique())
            if members_curr and members_next:
                new_members = members_next - members_curr
                turnval = len(new_members) / len(members_next)
                turnovers.append(turnval)
                
                m_next_rows = df_councils[df_councils['numero mandato'] == m_next]
                if not m_next_rows.empty:
                    m_next_row = m_next_rows.iloc[0]
                    m_next_label = f"{m_next}. {m_next_row['anno']} ({m_next_row['mesi']})"
                else:
                    m_next_label = f"Mandato {m_next}"
                    
                turnover_chart_data.append({
                    'Consiglio': m_next_label,
                    'Ricambio (%)': turnval * 100
                })
            
    avg_turnover = np.mean(turnovers) * 100 if turnovers else 0.0
    
    durations = []
    for i in range(len(active_mandates)):
        m_curr = active_mandates[i]
        members_curr = set(df_role_filtered[df_role_filtered['numero mandato'] == m_curr][column_name].dropna().unique())
        if not members_curr:
            continue
        for j in range(i + 1, len(active_mandates)):
            m_next = active_mandates[j]
            members_next = set(df_role_filtered[df_role_filtered['numero mandato'] == m_next][column_name].dropna().unique())
            if not members_next:
                continue
            if not (members_curr & members_next):
                durations.append(j - i)
                break
                
    avg_steps = np.mean(durations) if durations else None
    
    return {
        'avg_turnover': avg_turnover,
        'avg_steps': avg_steps,
        'pct_overlap_start': pct_overlap_start,
        'shared_members': shared_members,
        'start_members': start_members,
        'end_members': end_members,
        'top_members': members_counts,
        'turnover_chart_data': turnover_chart_data
    }

# Professional Academic styling (slate and steel blue color system, desaturated card elements, no emojis)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Inter:wght@300;400;500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main-title {
        font-family: 'Outfit', sans-serif;
        font-weight: 800;
        background: linear-gradient(135deg, #1e293b, #475569);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        margin-bottom: 0.5rem;
    }
    
    .sub-title {
        font-family: 'Outfit', sans-serif;
        font-weight: 400;
        color: #475569;
        font-size: 1.1rem;
        margin-bottom: 2rem;
        border-bottom: 2px solid #e2e8f0;
        padding-bottom: 1rem;
    }
    
    .card {
        background-color: #f8fafc;
        padding: 1.25rem;
        border-radius: 8px;
        box-shadow: none;
        border: 1px solid #e2e8f0;
        margin-bottom: 1.5rem;
    }
    
    .stButton>button, .stDownloadButton>button {
        background: linear-gradient(135deg, #334155, #475569);
        color: white;
        border-radius: 6px;
        border: none;
        padding: 0.5rem 1.5rem;
        font-weight: 500;
        font-family: 'Inter', sans-serif;
        transition: all 0.2s ease;
    }
    
    .stButton>button:hover, .stDownloadButton>button:hover {
        background: linear-gradient(135deg, #1e293b, #334155);
        box-shadow: 0 2px 8px rgba(30, 41, 59, 0.25);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        font-family: 'Outfit', sans-serif;
        color: #0f172a;
    }
    
    .metric-label {
        font-size: 0.85rem;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 500;
    }
    
    /* Sidebar container styling */
    section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div {
        background-color: #f1f5f9 !important;
        border-right: 1px solid #cbd5e1 !important;
    }
    
    /* Style the sidebar collapse/expand buttons to be highly visible and cool */
    button[data-testid="collapse-button"],
    button[data-testid="stSidebarCollapseButton"] {
        background-color: #ffffff !important;
        color: #475569 !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 50% !important;
        padding: 6px !important;
        width: 36px !important;
        height: 36px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.25s ease !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05) !important;
    }
    button[data-testid="collapse-button"]:hover,
    button[data-testid="stSidebarCollapseButton"]:hover {
        background-color: #e2e8f0 !important;
        color: #0f172a !important;
        border-color: #94a3b8 !important;
        transform: scale(1.1) rotate(5deg);
    }
    button[data-testid="collapse-button"] svg,
    button[data-testid="stSidebarCollapseButton"] svg {
        fill: #475569 !important;
        stroke: #475569 !important;
        color: #475569 !important;
    }
    button[data-testid="collapse-button"]:hover svg,
    button[data-testid="stSidebarCollapseButton"]:hover svg {
        fill: #0f172a !important;
        stroke: #0f172a !important;
        color: #0f172a !important;
    }

    /* Style the title inside the sidebar */
    .sidebar-title {
        font-family: 'Outfit', sans-serif;
        font-size: 1.1rem;
        font-weight: 800;
        color: #0f172a;
        letter-spacing: 0.1rem;
        text-transform: uppercase;
        padding: 24px 14px 16px 14px;
        margin-bottom: 24px;
        text-align: center;
        border-bottom: 1px solid #cbd5e1;
        background: linear-gradient(135deg, #0f172a, #334155);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    /* Style all buttons inside the sidebar as flat menu items blending with the sidebar background */
    section[data-testid="stSidebar"] div[data-testid="stButton"] button,
    section[data-testid="stSidebar"] div.stButton button,
    section[data-testid="stSidebar"] button:not([data-testid="stSidebarCollapseButton"]):not([data-testid="collapse-button"]) {
        background: #f1f5f9 !important; /* exactly sidebar background */
        background-image: none !important;
        color: #475569 !important;
        border: 1px solid transparent !important;
        box-shadow: none !important;
        padding: 10px 16px !important;
        width: 100% !important;
        text-align: center !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        border-radius: 8px !important;
        font-family: 'Outfit', sans-serif !important;
        font-size: 1.05rem !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button *,
    section[data-testid="stSidebar"] div.stButton button *,
    section[data-testid="stSidebar"] button:not([data-testid="stSidebarCollapseButton"]):not([data-testid="collapse-button"]) * {
        color: #475569 !important;
        font-weight: 500 !important;
    }

    /* Focus & Active States for unselected button to prevent Streamlit default blue/red/dark styles */
    section[data-testid="stSidebar"] div[data-testid="stButton"] button:focus,
    section[data-testid="stSidebar"] div[data-testid="stButton"] button:active,
    section[data-testid="stSidebar"] button:not([data-testid="stSidebarCollapseButton"]):not([data-testid="collapse-button"]):focus,
    section[data-testid="stSidebar"] button:not([data-testid="stSidebarCollapseButton"]):not([data-testid="collapse-button"]):active {
        background: #f1f5f9 !important;
        background-image: none !important;
        color: #475569 !important;
        border-color: transparent !important;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button:focus *,
    section[data-testid="stSidebar"] div[data-testid="stButton"] button:active *,
    section[data-testid="stSidebar"] button:not([data-testid="stSidebarCollapseButton"]):not([data-testid="collapse-button"]):focus *,
    section[data-testid="stSidebar"] button:not([data-testid="stSidebarCollapseButton"]):not([data-testid="collapse-button"]):active * {
        color: #475569 !important;
    }

    /* Hover State for unselected button: light illumination */
    section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover,
    section[data-testid="stSidebar"] button:not([data-testid="stSidebarCollapseButton"]):not([data-testid="collapse-button"]):hover {
        background: #ffffff !important; /* pure white for clean illumination on #f1f5f9 */
        background-image: none !important;
        color: #0f172a !important;
        border-color: #cbd5e1 !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05) !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover *,
    section[data-testid="stSidebar"] button:not([data-testid="stSidebarCollapseButton"]):not([data-testid="collapse-button"]):hover * {
        color: #0f172a !important;
    }

    /* Selected State (primary button) */
    section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"],
    section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="stBaseButton-primary"],
    section[data-testid="stSidebar"] button[kind="primary"],
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
        background: #cbd5e1 !important; /* distinct light gray selection color */
        background-image: none !important;
        color: #0f172a !important;
        border-color: #94a3b8 !important;
        font-weight: 700 !important;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] *,
    section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="stBaseButton-primary"] *,
    section[data-testid="stSidebar"] button[kind="primary"] *,
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] * {
        color: #0f172a !important;
        font-weight: 700 !important;
    }

    /* Hover State for selected button */
    section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"]:hover,
    section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="stBaseButton-primary"]:hover,
    section[data-testid="stSidebar"] button[kind="primary"]:hover,
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:hover {
        background: #cbd5e1 !important;
        background-image: none !important;
        color: #0f172a !important;
        border-color: #94a3b8 !important;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"]:hover *,
    section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="stBaseButton-primary"]:hover *,
    section[data-testid="stSidebar"] button[kind="primary"]:hover *,
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:hover * {
        color: #0f172a !important;
    }

    /* Focus & Active States for selected button */
    section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"]:focus,
    section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"]:active,
    section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="stBaseButton-primary"]:focus,
    section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="stBaseButton-primary"]:active,
    section[data-testid="stSidebar"] button[kind="primary"]:focus,
    section[data-testid="stSidebar"] button[kind="primary"]:active,
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:focus,
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:active {
        background: #cbd5e1 !important;
        background-image: none !important;
        color: #0f172a !important;
        border-color: #94a3b8 !important;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"]:focus *,
    section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"]:active *,
    section[data-testid="stSidebar"] button[kind="primary"]:focus *,
    section[data-testid="stSidebar"] button[kind="primary"]:active * {
        color: #0f172a !important;
    }





    .section-header {
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        font-size: 1.5rem;
        color: #0f172a;
        border-left: 4px solid #475569;
        padding-left: 0.75rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

def generate_markdown_report(start_yr, end_yr, filtered_time_df, active_page_or_tab):
    import pandas as pd
    import os
    
    if active_page_or_tab == 'Famiglie e Individui':
        # 1. Top Families Table
        fam_counts = filtered_time_df['Famiglia'].value_counts().dropna()
        top_fam_df = pd.DataFrame({
            'Posizione': range(1, len(fam_counts.head(20)) + 1),
            'Famiglia': fam_counts.head(20).index,
            'Occorrenze (Cariche)': fam_counts.head(20).values,
            'Percentuale su Totale (%)': (fam_counts.head(20).values / len(filtered_time_df) * 100).round(2) if len(filtered_time_df) > 0 else 0
        })
        top_fam_md = top_fam_df.to_markdown(index=False) if not top_fam_df.empty else "Nessun dato."
        
        # 2. Top Individuals Table
        ind_counts = filtered_time_df['nome'].value_counts().dropna()
        ind_details = []
        for pos, (name, count) in enumerate(ind_counts.head(20).items(), 1):
            sub_df = filtered_time_df[filtered_time_df['nome'] == name]
            fam = sub_df['Famiglia'].iloc[0] if not sub_df.empty and 'Famiglia' in sub_df.columns else ''
            ind_details.append({
                'Posizione': pos,
                'Nome': name,
                'Famiglia': fam,
                'Presenze nel Consiglio': count
            })
        top_ind_df = pd.DataFrame(ind_details)
        top_ind_md = top_ind_df.to_markdown(index=False) if ind_details else "Nessun dato."
        
        report_content = f"""# Pisa Medieval Politician Database - Report Famiglie e Individui

**Periodo di Analisi selezionato:** {start_yr} - {end_yr}

Questo report raccoglie le tabelle delle famiglie e degli individui più attivi nel consiglio nel periodo selezionato.

---

### 1. Egemonia Familiare (Top 20 Famiglie per Occorrenze)
{top_fam_md}

### 2. Rappresentazione degli Individui (Top 20 Politici per Occorrenze)
{top_ind_md}
"""
        return report_content

    elif active_page_or_tab == 'Categorie Professionali':
        prof_counts = filtered_time_df['Professione'].value_counts().dropna()
        top_prof_df = pd.DataFrame({
            'Posizione': range(1, len(prof_counts.head(20)) + 1),
            'Professione': prof_counts.head(20).index,
            'Occorrenze (Cariche)': prof_counts.head(20).values,
            'Percentuale su Totale (%)': (prof_counts.head(20).values / len(filtered_time_df) * 100).round(2) if len(filtered_time_df) > 0 else 0
        })
        top_prof_md = top_prof_df.to_markdown(index=False) if not top_prof_df.empty else "Nessun dato."
        
        report_content = f"""# Pisa Medieval Politician Database - Report Categorie Professionali

**Periodo di Analisi selezionato:** {start_yr} - {end_yr}

Questo report raccoglie le tabelle di rappresentazione professionale nel consiglio nel periodo selezionato.

---

### 1. Distribuzione delle Professioni (Top 20 Categorie)
{top_prof_md}
"""
        return report_content

    elif active_page_or_tab == 'Distribuzione Cariche':
        role_counts = filtered_time_df['ruolo'].value_counts().dropna()
        roles_df = pd.DataFrame({
            'Ruolo': role_counts.index,
            'Occorrenze (Cariche)': role_counts.values,
            'Percentuale su Totale (%)': (role_counts.values / len(filtered_time_df) * 100).round(2) if len(filtered_time_df) > 0 else 0
        })
        roles_md = roles_df.to_markdown(index=False) if not roles_df.empty else "Nessun dato."
        
        report_content = f"""# Pisa Medieval Politician Database - Report Distribuzione Cariche

**Periodo di Analisi selezionato:** {start_yr} - {end_yr}

Questo report raccoglie le tabelle relative alla distribuzione delle cariche e dei ruoli nel consiglio per il periodo selezionato.

---

### 1. Frequenza dei Ruoli
{roles_md}
"""
        return report_content

    elif active_page_or_tab == 'Ricambio nel Tempo':
        analysis_unit = st.session_state.get("turnover_analysis_unit", "Individui (singoli politici)")
        cb_anz1 = st.session_state.get("cb_turnover_anz1", True)
        cb_anz2 = st.session_state.get("cb_turnover_anz2", True)
        cb_priore = st.session_state.get("cb_turnover_priore", False)
        cb_notaio = st.session_state.get("cb_turnover_notaio", False)
        cb_canc = st.session_state.get("cb_turnover_canc", False)
        selected_step_label = st.session_state.get("turnover_step_slider", "6 mesi (3 consigli)")
        block_size = st.session_state.get("turnover_cohort_block_size", 5)

        unit_mapping = {
            "Individui (singoli politici)": "nome",
            "Famiglie (cognomi/casate)": "Famiglia",
            "Quartieri (provenienza geografica)": "quartiere"
        }
        column_name = unit_mapping.get(analysis_unit, "nome")
        
        unit_names_pl = {
            "nome": {
                "singular": "politico",
                "plural": "politici",
                "capital_plural": "Politici",
                "agreement_noun": "persone",
                "agreement_adj": "nuove"
            },
            "Famiglia": {
                "singular": "famiglia",
                "plural": "famiglie",
                "capital_plural": "Famiglie",
                "agreement_noun": "famiglie",
                "agreement_adj": "nuove"
            },
            "quartiere": {
                "singular": "quartiere",
                "plural": "quartieri",
                "capital_plural": "Quartieri",
                "agreement_noun": "quartieri",
                "agreement_adj": "nuovi"
            }
        }
        u_info = unit_names_pl.get(column_name, unit_names_pl["nome"])

        selected_roles = []
        if cb_anz1: selected_roles.append("anziano #1")
        if cb_anz2: selected_roles.append("anziano #2")
        if cb_priore: selected_roles.append("priore")
        if cb_notaio: selected_roles.append("notaio anziani")
        if cb_canc: selected_roles.append("canc. maior")
        
        roles_str = ", ".join([r.capitalize() for r in selected_roles]) if selected_roles else "Nessuno"
        
        df = st.session_state.get('standardized_df')
        if df is None or df.empty:
            return "# Pisa Medieval Politician Database\n\nErrore: Database non disponibile."
            
        active_mandates_filtered = []
        if not filtered_time_df.empty:
            active_mandates_filtered = sorted(filtered_time_df['numero mandato'].dropna().unique())
            
        if active_mandates_filtered:
            start_mandate = int(active_mandates_filtered[0])
            end_mandate = int(active_mandates_filtered[-1])
        else:
            start_mandate = 1
            end_mandate = 1

        df_councils = df[['numero mandato', 'anno', 'mesi']].dropna(subset=['anno', 'mesi']).drop_duplicates().sort_values(by='numero mandato')
        def get_council_label(m_num):
            rows = df_councils[df_councils['numero mandato'] == m_num]
            if not rows.empty:
                r = rows.iloc[0]
                return f"{m_num}. {r['anno']} ({r['mesi']})"
            return f"Mandato {m_num}"

        start_council_lbl = get_council_label(start_mandate)
        end_council_lbl = get_council_label(end_mandate)

        # 1. Confronto Rolling
        option_to_step = {
            "6 mesi (3 consigli)": 3,
            "1 anno (6 consigli)": 6,
            "2 anni (12 consigli)": 12,
            "3 anni (18 consigli)": 18,
            "4 anni (24 consigli)": 24,
            "5 anni (30 consigli)": 30,
            "6 anni (36 consigli)": 36,
            "7 anni (42 consigli)": 42,
            "8 anni (48 consigli)": 48,
            "9 anni (54 consigli)": 54,
            "10 anni (60 consigli)": 60,
            "15 anni (90 consigli)": 90,
            "20 anni (120 consigli)": 120,
            "25 anni (150 consigli)": 150,
            "30 anni (180 consigli)": 180
        }
        step_size = option_to_step.get(selected_step_label, 3)
        
        metrics = compute_turnover_metrics(df, selected_roles, start_mandate, end_mandate, step_size=step_size, column_name=column_name)
        
        rolling_md = ""
        if metrics is None:
            rolling_md = "Nessun dato trovato per i ruoli e periodo selezionati nel confronto rolling."
        else:
            avg_turnover = metrics['avg_turnover']
            avg_steps = metrics['avg_steps']
            pct_overlap_start = metrics['pct_overlap_start']
            shared_members = metrics['shared_members']
            start_members = metrics['start_members']
            end_members = metrics['end_members']
            top_members = metrics['top_members']
            
            if avg_steps is not None:
                avg_months = avg_steps * 2
                complete_turnover_str = f"{avg_steps:.1f} Consigli (~{avg_months:.1f} Mesi)"
            else:
                complete_turnover_str = "Non raggiungibile nel periodo"
                
            start_lbls = ", ".join(sorted(list(start_members))) if start_members else "Nessuno"
            end_lbls = ", ".join(sorted(list(end_members))) if end_members else "Nessuno"
            shared_lbls = ", ".join(sorted(list(shared_members))) if shared_members else "Nessuno"
            
            df_top_members = pd.DataFrame({
                'Soggetto': top_members.index,
                'Partecipazioni (mandati)': top_members.values
            }).head(20)
            top_members_md = df_top_members.to_markdown(index=False) if not df_top_members.empty else "Nessun dato."
            
            rolling_md = f"""#### Metriche Generali (Confronto Rolling)
- **Tasso di Ricambio Medio**: {avg_turnover:.1f}% (Intervallo: {selected_step_label})
- **Tempo Stimato per Ricambio Completo**: {complete_turnover_str}
- **Tasso di Sovrapposizione Inizio-Fine**: {pct_overlap_start:.1f}%

#### Dettaglio Sovrapposizione Estremi (Inizio vs Fine)
- **Soggetti presenti all'inizio ({start_council_lbl})**: {start_lbls}
- **Soggetti presenti alla fine ({end_council_lbl})**: {end_lbls}
- **Soggetti condivisi (In comune)**: {shared_lbls}

#### Top 20 {u_info['capital_plural']} per Partecipazioni nel Periodo
{top_members_md}"""

        # 2. Confronto per Finestre (Coorti)
        blocks = []
        curr_yr = start_yr
        while curr_yr <= end_yr:
            next_yr = min(curr_yr + block_size - 1, end_yr)
            blocks.append((curr_yr, next_yr))
            curr_yr += block_size
            
        cohort_turnovers = []
        cohort_chart_data = []
        block_members = {}
        for b_start, b_end in blocks:
            b_df = filtered_time_df[
                (filtered_time_df['start_year'] >= b_start) & 
                (filtered_time_df['start_year'] <= b_end) &
                (filtered_time_df['ruolo'].isin(selected_roles))
            ]
            members = set(b_df[column_name].dropna().unique())
            block_members[(b_start, b_end)] = members
            
        for i in range(len(blocks) - 1):
            b1 = blocks[i]
            b2 = blocks[i+1]
            m1 = block_members[b1]
            m2 = block_members[b2]
            if m1 and m2:
                new_m = m2 - m1
                turnval = (len(new_m) / len(m2)) * 100
                cohort_turnovers.append(turnval)
                label = f"{b1[0]}-{b1[1]} vs {b2[0]}-{b2[1]}"
                cohort_chart_data.append({
                    'Finestre a Confronto': label,
                    'Ricambio (%)': round(turnval, 2)
                })
                
        if cohort_chart_data:
            df_cohort_c = pd.DataFrame(cohort_chart_data)
            avg_cohort_t = np.mean(cohort_turnovers)
            cohort_table_md = df_cohort_c.to_markdown(index=False)
            cohort_md = f"""- **Ricambio Medio tra Coorti**: {avg_cohort_t:.1f}% (Finestre di {block_size} anni)

#### Tabella Confronto Coorti:
{cohort_table_md}"""
        else:
            cohort_md = f"Periodo troppo breve per creare almeno due finestre temporali da {block_size} anni ciascuna."

        # 3. Analisi di Ricorrenza (Carriere)
        df_rec = filtered_time_df[filtered_time_df['ruolo'].isin(selected_roles)].copy()
        service_counts = df_rec[column_name].value_counts().dropna()
        
        if not service_counts.empty:
            total_unique = len(service_counts)
            more_than_once = (service_counts > 1).sum()
            rec_rate = (more_than_once / total_unique) * 100
            
            bins = [0, 1, 2, 4, 100]
            labels_bins = ["1 sola volta", "2 volte", "3-4 volte", "5+ volte"]
            categorized = pd.cut(service_counts, bins=bins, labels=labels_bins).value_counts().reindex(labels_bins)
            categorized.index.name = 'Frequenza di ritorno'
            df_cat = categorized.reset_index(name='Numero di soggetti')
            df_cat_md = df_cat.to_markdown(index=False)
            
            top_n_rec = 20
            top_recurrent = service_counts.head(top_n_rec)
            df_top_rec = pd.DataFrame({
                'Soggetto': top_recurrent.index,
                'Numero di Mandati': top_recurrent.values
            })
            df_top_rec_md = df_top_rec.to_markdown(index=False)
            
            recurrence_md = f"""- **Tasso di Ricorrenza (Ritorno al potere)**: {rec_rate:.1f}% (Percentuale di soggetti con più di un mandato nel periodo)

#### Frequenza di Ritorno delle Carriere:
{df_cat_md}

#### Dettaglio dei Soggetti più Ricorrenti (Top {top_n_rec}):
{df_top_rec_md}"""
        else:
            recurrence_md = "Nessun dato di ricorrenza disponibile per il periodo e ruoli selezionati."

        # 4. Indice di Concentrazione (Oligarchia)
        if not service_counts.empty:
            counts = service_counts.values
            counts_sorted = sorted(counts, reverse=True)
            
            def gini_coef(array):
                if len(array) == 0 or np.sum(array) == 0:
                    return 0.0
                array = np.array(array, dtype=np.float64)
                array = np.sort(array)
                index = np.arange(1, array.shape[0] + 1)
                n = array.shape[0]
                return ((2 * index - n - 1) * array).sum() / (n * array.sum())
                
            gini_v = gini_coef(counts)
            
            total_seats = sum(counts_sorted)
            cum_seats = np.cumsum(counts_sorted)
            cum_percent_seats = (cum_seats / total_seats) * 100
            
            top_10_pct_count = max(1, int(len(counts_sorted) * 0.1))
            top_10_pct_share = cum_percent_seats[top_10_pct_count - 1]
            
            concentration_md = f"""- **Indice di Gini**: {gini_v:.4f} *(0 = perfetta uguaglianza/rotazione, 1 = massima concentrazione)*
- **Quota del 10% dei soggetti più attivi**: {top_10_pct_share:.1f}% delle cariche totali nel periodo"""
        else:
            concentration_md = "Nessun dato di concentrazione disponibile."

        report_content = f"""# Pisa Medieval Politician Database - Report Ricambio nel Tempo
        
**Periodo di Analisi selezionato:** {start_yr} - {end_yr}
**Unità di Analisi:** {analysis_unit}
**Ruoli Analizzati:** {roles_str}

---

### 1. Confronto Rolling (Consiglio vs Consiglio)
{rolling_md}

---

### 2. Confronto per Finestre Temporali (Coorti)
{cohort_md}

---

### 3. Analisi di Ricorrenza (Carriere)
{recurrence_md}

---

### 4. Concentrazione del Potere (Oligarchia)
{concentration_md}
"""
        return report_content

    elif active_page_or_tab == 'Classifiche Personalizzate':
        fam_counts = filtered_time_df['Famiglia'].value_counts().dropna().head(20)
        top_fam_df = pd.DataFrame({
            'Posizione': range(1, len(fam_counts) + 1),
            'Famiglia': fam_counts.index,
            'Frequenza (Occorrenze)': fam_counts.values
        })
        top_fam_md = top_fam_df.to_markdown(index=False)

        prof_counts = filtered_time_df['Professione'].value_counts().dropna().head(20)
        top_prof_df = pd.DataFrame({
            'Posizione': range(1, len(prof_counts) + 1),
            'Professione': prof_counts.index,
            'Frequenza (Occorrenze)': prof_counts.values
        })
        top_prof_md = top_prof_df.to_markdown(index=False)

        q_counts = filtered_time_df['quartiere'].value_counts().dropna()
        q_df = pd.DataFrame({
            'Posizione': range(1, len(q_counts) + 1),
            'Quartiere': [str(x).strip().capitalize() for x in q_counts.index],
            'Frequenza (Occorrenze)': q_counts.values
        })
        q_md = q_df.to_markdown(index=False)

        report_content = f"""# Pisa Medieval Politician Database - Report Classifiche e Graduatorie

**Periodo di Analisi selezionato:** {start_yr} - {end_yr}

Questo report raccoglie le graduatorie di frequenza complete per Famiglie, Professioni e Quartieri relative al periodo selezionato.

---

### 1. Classifica delle Famiglie (Top 20)
{top_fam_md}

### 2. Classifica delle Professioni (Top 20)
{top_prof_md}

### 3. Classifica dei Quartieri
{q_md}
"""
        return report_content

    elif active_page_or_tab == 'savi':
        savi_excel = os.path.join("data", "Lista di Savi e Cerchi di potere.xlsx")
        if os.path.exists(savi_excel):
            try:
                from savi_process import clean_and_pivot_savi, compute_circles_of_power
                df_savi_raw = clean_and_pivot_savi(savi_excel)
                circles_data = compute_circles_of_power(df_savi_raw, filtered_time_df)
                
                c0 = circles_data['cerchio_0']
                c1 = circles_data['cerchio_1']
                c2 = circles_data['cerchio_2']
                c3 = circles_data['cerchio_3']
                c4 = circles_data['cerchio_4']
                
                df_savi_std = circles_data['df_savi']
                df_anziani_unici = circles_data['df_anziani_unici']
                
                def get_family_counts_md(names, source_df):
                    df_sub = source_df[source_df['nome'].isin(names)].copy()
                    counts = df_sub.drop_duplicates(subset=['nome'])['famiglia'].value_counts().reset_index()
                    counts.columns = ['Famiglia', 'Numero Individui']
                    return counts.head(10).to_markdown(index=False) if not counts.empty else "Nessun dato."
                    
                c0_fam_md = get_family_counts_md(c0, df_savi_std)
                c2_fam_md = get_family_counts_md(c2, df_anziani_unici)
                c3_fam_md = get_family_counts_md(c3, df_anziani_unici)
                c4_fam_md = get_family_counts_md(c4, df_anziani_unici)
                
                def get_members_list_md(names, source_df, is_noble_source=False):
                    df_sub = source_df[source_df['nome'].isin(names)].copy().drop_duplicates(subset=['nome'])
                    cols = ['nome', 'famiglia', 'quartiere']
                    if is_noble_source and 'Nobile' in df_sub.columns:
                        cols.append('Nobile')
                    if df_sub.empty:
                        return "Nessun individuo registrato."
                    df_sub = df_sub[cols].reset_index(drop=True)
                    df_sub.columns = [c.capitalize() for c in cols]
                    return df_sub.to_markdown(index=False)
                    
                c0_members_md = get_members_list_md(c0, df_savi_std, is_noble_source=True)
                c1_members_md = get_members_list_md(c1, df_savi_std, is_noble_source=True)
                c2_members_md = get_members_list_md(c2, df_anziani_unici)
                c3_members_md = get_members_list_md(c3, df_anziani_unici)
                c4_members_md = get_members_list_md(c4, df_anziani_unici)
                
                report_content = f"""# Pisa Medieval Politician Database - Report Consiglio dei Savi

**Periodo degli Anziani di riferimento:** {start_yr} - {end_yr}

Questo report raccoglie tutte le tabelle dei Cerchi di Potere per il Consiglio dei Savi relative all'intervallo temporale selezionato.

---

### 1. Sintesi delle Dimensioni dei Cerchi
| Cerchio di Potere | Numero di Individui Unici |
| --- | --- |
| C0: Aristocrazia (Solo Savi) | {len(c0)} |
| C1: Nobiltà Istituzionale (Entrambi) | {len(c1)} |
| C2: Elite (Entrambi) | {len(c2)} |
| C3: Rete Consorterie (Parenti C2) | {len(c3)} |
| C4: Nuovi Attori (Esterni) | {len(c4)} |

### 2. Top 10 Famiglie per Cerchio di Potere

#### C0: Aristocrazia
{c0_fam_md}

#### C2: Elite
{c2_fam_md}

#### C3: Rete Consorterie
{c3_fam_md}

#### C4: Nuovi Attori
{c4_fam_md}

### 3. Elenco Completo dei Membri dei Cerchi di Potere

#### C0: Aristocrazia (Solo Savi)
{c0_members_md}

#### C1: Nobiltà Istituzionale (Entrambi)
{c1_members_md}

#### C2: Elite (Entrambi)
{c2_members_md}

#### C3: Rete Consorterie (Parenti C2)
{c3_members_md}

#### C4: Nuovi Attori (Esterni)
{c4_members_md}
"""
                return report_content
            except Exception as ex:
                return f"# Pisa Medieval Politician Database - Report Consiglio dei Savi\n\n*Errore durante il calcolo dei Cerchi di Potere: {ex}*"
        else:
            return "# Pisa Medieval Politician Database - Report Consiglio dei Savi\n\n*Dati del Consiglio dei Savi non caricati.*"
    return ""


# App Header
st.markdown('<div class="main-title">Anziani del Comune di Pisa</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Database delle Cariche Politiche Medievali (1344-1392) • Standardizzazione & Analytics</div>', unsafe_allow_html=True)



# Initialize session state for processed DataFrame
if 'raw_file_name' not in st.session_state:
    st.session_state['raw_file_name'] = None
if 'standardized_df' not in st.session_state:
    st.session_state['standardized_df'] = None
if 'sheet_used' not in st.session_state:
    st.session_state['sheet_used'] = None

import os
DEFAULT_EXCEL_PATH = os.path.join("data", "Anziani del Comune di Pisa 1344-1392.xlsx")

# Automatically load the default excel file if it exists and session is empty
if st.session_state['standardized_df'] is None:
    csv_target = os.path.join("data", "total_df.csv")
    
    # 1. Fallback: Try loading from the CSV first if it exists
    if os.path.exists(csv_target):
        try:
            std_df = pd.read_csv(csv_target)
            # Convert date columns back to datetime.date objects to prevent TypeError
            from datetime import date
            for col in ['data inizio mandato', 'data fine mandato']:
                if col in std_df.columns:
                    std_df[col] = std_df[col].apply(
                        lambda x: date(*map(int, str(x).strip().split('-'))) if (isinstance(x, str) and len(str(x).strip().split('-')) == 3) else None
                    )
            st.session_state['standardized_df'] = std_df
            st.session_state['raw_file_name'] = "total_df.csv"
            st.session_state['sheet_used'] = "CSV pre-elaborato"
        except Exception as ex:
            st.warning(f"Errore nel caricamento del CSV pre-elaborato: {ex}")
            
    # 2. Excel standard path loading (if CSV was missing or failed)
    if st.session_state['standardized_df'] is None:
        if os.path.exists(DEFAULT_EXCEL_PATH):
            try:
                from standardize import find_data_sheet
                std_df = robust_standardize_excel(DEFAULT_EXCEL_PATH)
                st.session_state['standardized_df'] = std_df
                st.session_state['raw_file_name'] = os.path.basename(DEFAULT_EXCEL_PATH)
                xls_file = pd.ExcelFile(DEFAULT_EXCEL_PATH)
                st.session_state['sheet_used'] = find_data_sheet(xls_file)
                # Auto-save to CSV
                os.makedirs(os.path.dirname(csv_target), exist_ok=True)
                std_df.to_csv(csv_target, index=False)
            except Exception as ex:
                st.error(f"Errore nel caricamento del file Excel predefinito ({DEFAULT_EXCEL_PATH}): {ex}")
        else:
            # 3. Fallback: Search for any backup/alternative excel files in the folder
            import glob
            excel_files = glob.glob(os.path.join("data", "Anziani del Comune di Pisa*.xlsx"))
            if excel_files:
                alternative_excel = excel_files[0]
                try:
                    from standardize import find_data_sheet
                    std_df = robust_standardize_excel(alternative_excel)
                    st.session_state['standardized_df'] = std_df
                    st.session_state['raw_file_name'] = os.path.basename(alternative_excel)
                    xls_file = pd.ExcelFile(alternative_excel)
                    st.session_state['sheet_used'] = find_data_sheet(xls_file)
                    # Auto-save to CSV
                    std_df.to_csv(csv_target, index=False)
                except Exception as ex:
                    st.error(f"Errore nel caricamento del file Excel alternativo ({alternative_excel}): {ex}")
            else:
                st.error(f"Il database predefinito non è stato trovato in: {DEFAULT_EXCEL_PATH}. Carica un file nella pagina di Download per crearlo.")

# Check and precompute Savi CSVs if missing on app startup
csv_target = os.path.join("data", "total_df.csv")
SAVI_EXCEL_PATH = os.path.join("data", "Lista di Savi e Cerchi di potere.xlsx")
savi_std_csv = os.path.join("data", "savi_standardized.csv")
savi_circ_csv = os.path.join("data", "savi_circles.csv")

if os.path.exists(csv_target) and os.path.exists(SAVI_EXCEL_PATH):
    if not os.path.exists(savi_std_csv) or not os.path.exists(savi_circ_csv):
        try:
            precompute_and_save_savi_data(SAVI_EXCEL_PATH, csv_target)
        except Exception as ex:
            st.warning(f"Errore nella pre-elaborazione dei dati dei Savi all'avvio: {ex}")


# Show success toast exactly once after a successful upload/standardize run
if st.session_state.get('just_uploaded', False):
    st.toast("File caricato e standardizzato con successo!")
    st.session_state['just_uploaded'] = False
if st.session_state.get('just_uploaded_savi', False):
    st.toast("File dei Savi caricato e Cerchi di Potere ricalcolati con successo!")
    st.session_state['just_uploaded_savi'] = False

# Processed Data Dashboard
if st.session_state['standardized_df'] is not None:
    df = st.session_state['standardized_df'].copy()
    
    # Sanitize and convert anno and mesi to string to prevent Arrow serialization crash
    def to_clean_str(x):
        if pd.isna(x):
            return ""
        s = str(x).strip()
        if s.endswith('.0'):
            return s[:-2]
        return s
        
    for col in ['anno', 'mesi']:
        if col in df.columns:
            df[col] = df[col].apply(to_clean_str)
    
    # Rename columns to match requested analysis schema
    df = df.rename(columns={'nota': 'Famiglia', 'altra nota': 'Professione'})
    analysis_df = df.copy() # Simply analyze everything

    # Extract years globally for filtering
    df_fam_time = analysis_df.copy()
    df_fam_time['start_year'] = df_fam_time['anno'].apply(lambda x: extract_year_range(x)[0])
    df_fam_time = df_fam_time.dropna(subset=['start_year'])
    df_fam_time['start_year'] = df_fam_time['start_year'].astype(int)
    
    if not df_fam_time.empty:
        min_year = int(df_fam_time['start_year'].min())
        max_year = int(df_fam_time['start_year'].max())
    else:
        min_year, max_year = 1300, 1400

    # Initialize/sync selected year range in session state
    if 'last_processed_file' not in st.session_state or st.session_state['last_processed_file'] != st.session_state['raw_file_name']:
        st.session_state['last_processed_file'] = st.session_state['raw_file_name']
        st.session_state['selected_year_range'] = (min_year, max_year)
    if 'selected_year_range' not in st.session_state:
        st.session_state['selected_year_range'] = (min_year, max_year)
        
    start_yr, end_yr = st.session_state['selected_year_range']

    # Initialize separate tab slider keys to match selected_year_range
    for k in ['selected_years_fam', 'selected_years_prof', 'selected_years_roles', 'selected_years_turnover', 'ranking_year_range_slider', 'selected_years_download']:
        if k not in st.session_state or st.session_state.get('last_processed_file_sliders') != st.session_state['raw_file_name']:
            st.session_state[k] = st.session_state['selected_year_range']
    st.session_state['last_processed_file_sliders'] = st.session_state['raw_file_name']

    def sync_years(source_key):
        # Guard: source_key may have been garbage-collected by Streamlit
        # when the widget was not rendered (e.g. after page navigation)
        if source_key not in st.session_state:
            return
        val = st.session_state[source_key]
        st.session_state['selected_year_range'] = val
        for k in ['selected_years_fam', 'selected_years_prof', 'selected_years_roles', 'selected_years_turnover', 'ranking_year_range_slider', 'selected_years_download']:
            if k in st.session_state:
                st.session_state[k] = val

    # Sidebar Navigation Section (dashboard vs download vs savi) using Clickable Buttons (containers) instead of radio/checkboxes
    if 'page_option' not in st.session_state:
        st.session_state['page_option'] = 'dashboard'
        
    page_option = st.session_state['page_option']
    with st.sidebar:
        st.markdown('<div class="sidebar-title">Pisa Medieval Database</div>', unsafe_allow_html=True)
        is_dash = st.session_state['page_option'] == 'dashboard'
        is_savi = st.session_state['page_option'] == 'savi'
        is_down = st.session_state['page_option'] == 'download'
        
        if st.button("Dashboard Anziani", key="nav_dashboard", width='stretch', type="primary" if is_dash else "secondary"):
            if st.session_state['page_option'] != 'dashboard':
                st.session_state['page_option'] = 'dashboard'
                st.rerun()
                
        if st.button("Consiglio dei Savi", key="nav_savi", width='stretch', type="primary" if is_savi else "secondary"):
            if st.session_state['page_option'] != 'savi':
                st.session_state['page_option'] = 'savi'
                st.rerun()
                
        if st.button("Download", key="nav_download", width='stretch', type="primary" if is_down else "secondary"):
            if st.session_state['page_option'] != 'download':
                st.session_state['page_option'] = 'download'
                st.rerun()

    page_option = st.session_state['page_option']

    # Only run heavy Dashboard/Download precomputations when actually on those pages.
    # The Savi page doesn't need any of these variables, so skip them entirely for speed.
    if page_option == "savi":
        # Provide defaults so any stale references don't crash
        filtered_time_df = pd.DataFrame()
        family_counts_filtered = pd.Series(dtype=int)
        top_10_f_filtered = pd.Series(dtype=int)
        fig_cumulative = None
        cumulative_melted = None
        fig_prof = None
        prof_role_top10 = None
        fig_roles = go.Figure()
        role_distribution = pd.DataFrame()
        all_families = []
        selected_family = None
        family_members_df = pd.DataFrame()
        family_individuals = []
        selected_individual = None
        table_display = pd.DataFrame()
        family_role_counts = pd.Series(dtype=int)
        total_family_roles = 0
        family_quartiere_counts = pd.Series(dtype=int)
        total_family_q = 0
        ind_df = pd.DataFrame()
        fig_timeline = None
        ind_prof_str = "Non identificata"
        total_entries = 0
        identified_prof_count = 0
        pct_identified = 0
        profession_counts = pd.Series(dtype=int)
        top_10_p_names = []
        priori_df = pd.DataFrame()
        total_priori = 0
        priori_identified = 0
        priori_top = pd.Series()
        anz1_df = pd.DataFrame()
        total_anz1 = 0
        anz1_identified = 0
        anz1_top = pd.Series()
        anz2_df = pd.DataFrame()
        total_anz2 = 0
        anz2_identified = 0
        anz2_top = pd.Series()
        total_records = 0
        unique_names = 0
        unique_families = 0
        unique_professions = 0
        total_mandates = 0
    else:
        # Global computations matching the slider range (so they are always available for both Dashboard and Download)
        filtered_time_df = df_fam_time[(df_fam_time['start_year'] >= start_yr) & (df_fam_time['start_year'] <= end_yr)].copy()
        family_counts_filtered = filtered_time_df['Famiglia'].value_counts().dropna()
        top_10_f_filtered = family_counts_filtered.head(10)

        # Precompute global socio-professional metrics for both Dashboard and Download pages based on filtered data
        total_entries = len(filtered_time_df)
        identified_prof_count = filtered_time_df['Professione'].dropna().count()
        pct_identified = (identified_prof_count / total_entries) * 100 if total_entries > 0 else 0
    
        # Define top 10 overall professions first based on filtered data
        profession_counts = filtered_time_df['Professione'].value_counts().dropna()
        top_10_p_names = profession_counts.head(10).index.tolist()
    
        priori_df = filtered_time_df[filtered_time_df['ruolo'] == 'priore']
        total_priori = len(priori_df)
        priori_identified = priori_df['Professione'].dropna().count()
        priori_top = priori_df[priori_df['Professione'].isin(top_10_p_names)]['Professione'].value_counts().dropna().head(3) if priori_identified > 0 else pd.Series()
    
        anz1_df = filtered_time_df[filtered_time_df['ruolo'] == 'anziano #1']
        total_anz1 = len(anz1_df)
        anz1_identified = anz1_df['Professione'].dropna().count()
        anz1_top = anz1_df[anz1_df['Professione'].isin(top_10_p_names)]['Professione'].value_counts().dropna().head(3) if anz1_identified > 0 else pd.Series()
    
        anz2_df = filtered_time_df[filtered_time_df['ruolo'] == 'anziano #2']
        total_anz2 = len(anz2_df)
        anz2_identified = anz2_df['Professione'].dropna().count()
        anz2_top = anz2_df[anz2_df['Professione'].isin(top_10_p_names)]['Professione'].value_counts().dropna().head(3) if anz2_identified > 0 else pd.Series()
    
        # Main Metrics Grid based on filtered data
        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
    
        total_records = len(filtered_time_df)
        unique_names = filtered_time_df['nome'].dropna().nunique()
        unique_families = filtered_time_df['Famiglia'].dropna().nunique()
        unique_professions = filtered_time_df['Professione'].dropna().nunique()
        total_mandates = filtered_time_df['numero mandato'].dropna().nunique()
    
        fig_cumulative = None
        cumulative_melted = None
        if not top_10_f_filtered.empty:
            top_10_f_names = top_10_f_filtered.index.tolist()
            years_range = list(range(start_yr, end_yr + 1))
        
            df_top_f = filtered_time_df[filtered_time_df['Famiglia'].isin(top_10_f_names)]
            occ_by_year = df_top_f.groupby(['start_year', 'Famiglia']).size().unstack(fill_value=0)
            occ_by_year = occ_by_year.reindex(years_range, fill_value=0)
            cumulative_counts = occ_by_year.cumsum()
        
            cumulative_counts = cumulative_counts.reset_index().rename(columns={'start_year': 'Anno'})
            cumulative_melted = cumulative_counts.melt(id_vars='Anno', var_name='Famiglia', value_name='Conteggio Cumulativo')
        
            fig_cumulative = px.line(
                cumulative_melted,
                x='Anno',
                y='Conteggio Cumulativo',
                color='Famiglia',
                title=f"Conteggio cumulativo delle occorrenze nel tempo ({start_yr}-{end_yr})",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_cumulative.update_layout(
                template="plotly_white",
                legend_title="Famiglia",
                xaxis_title="Anno",
                yaxis_title="Conteggio Cumulativo"
            )
        
        fig_prof = None
        prof_role_top10 = None
        if top_10_p_names:
            prof_role_counts = filtered_time_df.groupby(['Professione', 'ruolo']).size().unstack(fill_value=0)
        
            # Ensure only existing columns/roles are used to avoid errors
            existing_top_p = [p for p in top_10_p_names if p in prof_role_counts.index]
            if existing_top_p:
                prof_role_top10 = prof_role_counts.loc[existing_top_p]
                prof_role_top10_melted = prof_role_top10.reset_index().melt(
                    id_vars='Professione',
                    var_name='Ruolo',
                    value_name='Frequenza'
                )
                fig_prof = px.bar(
                    prof_role_top10_melted,
                    x='Professione',
                    y='Frequenza',
                    color='Ruolo',
                    title="Top 10 Categorie Professionali per Ruolo",
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                    barmode='stack'
                )
                fig_prof.update_layout(
                    template="plotly_white",
                    legend_title="Ruolo",
                    xaxis={'categoryorder': 'array', 'categoryarray': existing_top_p},
                    xaxis_title="Professione",
                    yaxis_title="Numero di Cariche"
                )
        
        top_overall_families = filtered_time_df['Famiglia'].value_counts().dropna().head(10).index.tolist()
        role_distribution = pd.DataFrame()
        if top_overall_families:
            filtered_df_families = filtered_time_df[filtered_time_df['Famiglia'].isin(top_overall_families)]
            role_distribution = filtered_df_families.groupby(['Famiglia', 'ruolo']).size().unstack(fill_value=0)
    
        fig_roles = go.Figure()
        if not role_distribution.empty:
            colors_map = px.colors.qualitative.Pastel
            for idx, role in enumerate(role_distribution.columns):
                fig_roles.add_trace(go.Bar(
                    name=role,
                    x=role_distribution.index,
                    y=role_distribution[role],
                    marker_color=colors_map[idx % len(colors_map)]
                ))
            fig_roles.update_layout(
                barmode='stack',
                title="Distribuzione dei Ruoli per le 10 Famiglie Principali",
                xaxis_title="Famiglia",
                yaxis_title="Numero di Cariche",
                template="plotly_white",
                legend_title="Ruolo"
            )

    
        # Track selected family and individual in session_state to survive tab/navigation changes
        all_families = sorted(df['Famiglia'].dropna().unique())
        if 'persisted_family' not in st.session_state:
            st.session_state['persisted_family'] = all_families[0] if all_families else None
    
        selected_family = st.session_state['persisted_family']
        if selected_family not in all_families and all_families:
            selected_family = all_families[0]
            st.session_state['persisted_family'] = selected_family
        
        family_members_df = df_fam_time[
            (df_fam_time['Famiglia'] == selected_family) & 
            (df_fam_time['start_year'] >= start_yr) & 
            (df_fam_time['start_year'] <= end_yr)
        ].dropna(subset=['nome'])
        family_individuals = sorted(family_members_df['nome'].dropna().unique()) if not family_members_df.empty else []
    
        if 'persisted_individual' not in st.session_state:
            st.session_state['persisted_individual'] = family_individuals[0] if family_individuals else None
        
        selected_individual = st.session_state['persisted_individual']
        if selected_individual not in family_individuals and family_individuals:
            selected_individual = family_individuals[0]
            st.session_state['persisted_individual'] = selected_individual
        
        # Precompute Family and Individual timelines/KPIs
        family_members_df = family_members_df.sort_values(by='data inizio mandato', ascending=True)
        table_display = family_members_df[['nome', 'ruolo', 'quartiere', 'anno', 'mesi']].copy()
        table_display.columns = ['Nome', 'Ruolo', 'Quartiere', 'Anno', 'Mesi']
    
        family_role_counts = family_members_df['ruolo'].value_counts()
        total_family_roles = family_role_counts.sum()
    
        family_quartiere_counts = family_members_df['quartiere'].value_counts(dropna=True)
        total_family_q = family_quartiere_counts.sum()
    
        ind_df = pd.DataFrame()
        fig_timeline = None
        ind_prof_str = "Non identificata"
    
        if selected_individual:
            ind_df = df_fam_time[
                (df_fam_time['nome'] == selected_individual) &
                (df_fam_time['start_year'] >= start_yr) &
                (df_fam_time['start_year'] <= end_yr)
            ].copy()
        
            if not ind_df.empty:
                ind_professions = ind_df['Professione'].dropna().unique()
                ind_prof_str = ", ".join(ind_professions) if len(ind_professions) > 0 else "Non identificata"
            
                starts = []
                finishes = []
                for _, row in ind_df.iterrows():
                    s = row['data inizio mandato']
                    f = row['data fine mandato']
                    if pd.isna(s) or s is None:
                        try:
                            s = date(int(row['start_year']), 4, 1)
                        except Exception:
                            s = date(1300, 1, 1)
                    if pd.isna(f) or f is None or f == s:
                        from datetime import timedelta
                        f = s + timedelta(days=60)
                    starts.append(s)
                    finishes.append(f)
                
                ind_df['Start'] = starts
                ind_df['Finish'] = finishes
                ind_df['Start_Str'] = ind_df['Start'].apply(lambda x: x.isoformat() if hasattr(x, 'isoformat') else str(x))
                ind_df['Finish_Str'] = ind_df['Finish'].apply(lambda x: x.isoformat() if hasattr(x, 'isoformat') else str(x))
                ind_df['Duration_Ms'] = ind_df.apply(lambda r: (r['Finish'] - r['Start']).total_seconds() * 1000, axis=1)
            
                ind_df['Periodo'] = ind_df['anno'].astype(str) + " (" + ind_df['mesi'].astype(str) + ")"
                ind_df['Ruolo e Quartiere'] = ind_df['ruolo'].astype(str) + ind_df['quartiere'].apply(lambda x: f" ({x})" if pd.notna(x) else "")
                ind_df = ind_df.sort_values(by='Start')
            
                fig_timeline = go.Figure()
                roles_in_ind = ind_df['ruolo'].unique()
                colors_map = px.colors.qualitative.Pastel
                role_colors = {r: colors_map[i % len(colors_map)] for i, r in enumerate(roles_in_ind)}
            
                for role in roles_in_ind:
                    df_role = ind_df[ind_df['ruolo'] == role]
                    fig_timeline.add_trace(go.Bar(
                        name=role,
                        y=df_role['Ruolo e Quartiere'],
                        x=df_role['Duration_Ms'],
                        base=df_role['Start_Str'],
                        orientation='h',
                        marker_color=role_colors[role],
                        customdata=df_role[['Periodo', 'Professione', 'Start_Str', 'Finish_Str']],
                        hovertemplate=(
                            "<b>%{y}</b><br>"
                            "Periodo: %{customdata[0]}<br>"
                            "Professione: %{customdata[1]}<br>"
                            "Inizio: %{customdata[2]}<br>"
                            "Fine: %{customdata[3]}<br>"
                            "<extra></extra>"
                        )
                    ))
                
                xaxis_start = f"{start_yr}-01-01"
                xaxis_end = f"{end_yr}-12-31"
                fig_timeline.update_layout(
                    xaxis_type='date',
                    xaxis_range=[xaxis_start, xaxis_end],
                    template="plotly_white",
                    xaxis_title="Cronologia dei mandati",
                    yaxis_title="",
                    barmode='stack',
                    showlegend=True,
                    legend_title="Ruolo",
                    title=f"Timeline delle partecipazioni al consiglio di {selected_individual} ({start_yr}-{end_yr})"
                )

    # === PAGES ROUTING ===
    if page_option == "dashboard":
        # Tabs for Dashboard page
        tab_families, tab_professions, tab_roles, tab_turnover, tab_rankings = st.tabs([
            "Famiglie e Individui",
            "Categorie Professionali",
            "Distribuzione Cariche",
            "Ricambio nel Tempo",
            "Classifiche Personalizzate"
        ])
        
        # Rendering code for Rappresentazione Familiare
        with tab_families:
            # 1. Year Range Slider (moved to this tab page)
            if not df_fam_time.empty:
                st.slider(
                    "Seleziona l'arco temporale per l'analisi delle famiglie",
                    min_value=min_year,
                    max_value=max_year,
                    key="selected_years_fam",
                    on_change=sync_years,
                    args=("selected_years_fam",),
                    step=1
                )

            st.markdown("### Analisi delle Famiglie e degli Individui")

                
            st.markdown('<div class="section-header">1. Trend temporale</div>', unsafe_allow_html=True)
                    
            if not top_10_f_filtered.empty:
                col_fam1, col_fam2 = st.columns([2, 1])
                with col_fam1:
                    st.plotly_chart(fig_cumulative, width='stretch')
                    # Simple explanation of the cumulative chart for non-statistical users
                    st.markdown("""
                    <div style="margin-top: 1rem; padding: 1.25rem; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;">
                        <h5 style="margin-top: 0; color: #0f172a; font-family: 'Outfit', sans-serif; font-size: 1.1rem; border-bottom: 1px solid #cbd5e1; padding-bottom: 0.5rem;">Guida Semplice al Grafico</h5>
                        <p style="font-size: 0.9rem; color: #334155; line-height: 1.5; margin: 0.5rem 0 0 0;">
                            Questo grafico mostra quante cariche hanno ricoperto complessivamente nel tempo le prime 10 famiglie:
                        </p>
                        <ul style="margin: 0.5rem 0 0 0; padding-left: 1.25rem; font-size: 0.85rem; color: #334155; line-height: 1.5;">
                            <li style="margin-bottom: 0.4rem;"><strong>Crescita della linea:</strong> ogni volta che la linea sale, significa che un membro di quella famiglia ha ottenuto una nuova carica in quell'anno.</li>
                            <li style="margin-bottom: 0.4rem;"><strong>Tratto piatto (orizzontale):</strong> indica che in quegli anni la famiglia non ha ricoperto ruoli nei consigli.</li>
                            <li style="margin-bottom: 0.4rem;"><strong>Pendenza ripida:</strong> indica un periodo di forte presenza e concentrazione di potere per quella specifica famiglia.</li>
                        </ul>
                    </div>
                    """, unsafe_allow_html=True)
                with col_fam2:
                    st.markdown(f"**Occorrenze Famiglie ({start_yr}-{end_yr})**")
                    family_table_df = pd.DataFrame({
                        'Famiglia': family_counts_filtered.index,
                        'Attestazioni': family_counts_filtered.values
                    })
                    st.dataframe(family_table_df, width='stretch', hide_index=True)
            else:
                st.info("Nessuna occorrenza di famiglia rilevata per l'arco temporale selezionato.")
                
            st.markdown("<hr style='border: 0; height: 1px; background: #cbd5e1; margin: 2rem 0;' />", unsafe_allow_html=True)
            st.markdown('<div class="section-header">2. Dettaglio della Famiglia Selezionata</div>', unsafe_allow_html=True)
            if all_families:
                # Define callbacks for selectbox changes to update persistent keys instantly
                def on_family_change():
                    st.session_state['persisted_family'] = st.session_state['family_widget_key']
                    # Reset individual for the new family
                    st.session_state['persisted_individual'] = None
                    
                def on_individual_change():
                    st.session_state['persisted_individual'] = st.session_state['individual_widget_key']
                
                selected_family = st.selectbox(
                    "Seleziona una famiglia per visualizzare i dettagli",
                    options=all_families,
                    key="family_widget_key",
                    index=all_families.index(selected_family) if selected_family in all_families else 0,
                    on_change=on_family_change
                )
                
                if not family_members_df.empty:
                    # 1. Family metrics cards row above the table
                    col_fam_m1, col_fam_m2 = st.columns(2)
                    with col_fam_m1:
                        st.markdown(f'<div class="card"><div class="metric-value">{len(family_members_df)}</div><div class="metric-label">Partecipazioni Totali ({start_yr}-{end_yr})</div></div>', unsafe_allow_html=True)
                    with col_fam_m2:
                        st.markdown(f'<div class="card"><div class="metric-value">{family_members_df["nome"].nunique()}</div><div class="metric-label">Individui Distinti ({start_yr}-{end_yr})</div></div>', unsafe_allow_html=True)
                    
                    # 2. Render individuals list
                    st.markdown(f"**Partecipazioni della famiglia {selected_family} al consiglio ({start_yr}-{end_yr})**")
                    st.dataframe(table_display, width='stretch', hide_index=True)
                    
                    # KPIs text cards
                    col_det1, col_det2 = st.columns(2)
                    with col_det1:
                        st.markdown(f"**Ruoli ricoperti in questo periodo ({start_yr}-{end_yr})**")
                        if total_family_roles > 0:
                            role_kpi_text = ""
                            for role, count in family_role_counts.items():
                                pct = (count / total_family_roles) * 100
                                role_kpi_text += f"- **{role}**: {count} cariche ({pct:.1f}%)\n"
                            st.markdown(role_kpi_text)
                        else:
                            st.write("Nessuna carica registrata in questo arco temporale.")
                            
                    with col_det2:
                        st.markdown(f"**Quartieri rappresentati in questo periodo ({start_yr}-{end_yr})**")
                        if total_family_q > 0:
                            q_kpi_text = ""
                            for q, count in family_quartiere_counts.items():
                                pct = (count / total_family_q) * 100
                                q_kpi_text += f"- **{q}**: {count} attestazioni ({pct:.1f}%)\n"
                            st.markdown(q_kpi_text)
                        else:
                            st.write("Nessun quartiere associato in questo arco temporale.")
                            
                    # Section 3 (Individual drill-down) removed by request
                else:
                    st.info(f"Nessuna partecipazione registrata per la famiglia {selected_family} nell'arco temporale selezionato ({start_yr}-{end_yr}).")
            else:
                st.info("Nessuna famiglia rilevata nel dataset.")
            
            st.write("---")
            fam_report_content = generate_markdown_report(start_yr, end_yr, filtered_time_df, 'Famiglie e Individui')
            st.download_button(
                label="📥 Scarica Report Famiglie e Individui (.MD)",
                data=fam_report_content,
                file_name=f"report_famiglie_individui_{start_yr}_{end_yr}.md",
                mime="text/markdown",
                key="download_report_md_families"
            )
                
        # Rendering code for Categorie Professionali
        with tab_professions:
            if not df_fam_time.empty:
                st.slider(
                    "Seleziona l'arco temporale per l'analisi delle professioni",
                    min_value=min_year,
                    max_value=max_year,
                    key="selected_years_prof",
                    on_change=sync_years,
                    args=("selected_years_prof",),
                    step=1
                )
            
            st.markdown("### Analisi della Rappresentazione Professionale")
            
            st.markdown("**Ruoli da analizzare (selezionabili singolarmente o in combinazione)**")
            col_prof_cb1, col_prof_cb2, col_prof_cb3, col_prof_cb4, col_prof_cb5 = st.columns(5)
            with col_prof_cb1:
                cb_prof_anz1 = st.checkbox("Anziano #1", value=True, key="cb_prof_anz1")
            with col_prof_cb2:
                cb_prof_anz2 = st.checkbox("Anziano #2", value=True, key="cb_prof_anz2")
            with col_prof_cb3:
                cb_prof_priore = st.checkbox("Priore", value=False, key="cb_prof_priore")
            with col_prof_cb4:
                cb_prof_notaio = st.checkbox("Notaio Anziani", value=False, key="cb_prof_notaio")
            with col_prof_cb5:
                cb_prof_canc = st.checkbox("Canc. Maggiore", value=False, key="cb_prof_canc")
            
            selected_prof_roles = []
            if cb_prof_anz1: selected_prof_roles.append("anziano #1")
            if cb_prof_anz2: selected_prof_roles.append("anziano #2")
            if cb_prof_priore: selected_prof_roles.append("priore")
            if cb_prof_notaio: selected_prof_roles.append("notaio anziani")
            if cb_prof_canc: selected_prof_roles.append("canc. maior")
            
            if not selected_prof_roles:
                st.warning("Seleziona almeno un ruolo da analizzare.")
            else:
                # Dynamically filter df by selected roles AND year range
                df_prof_filtered = filtered_time_df[filtered_time_df['ruolo'].isin(selected_prof_roles)].copy()
                profession_counts_f = df_prof_filtered['Professione'].value_counts().dropna()
                top_10_p_names_f = profession_counts_f.head(10).index.tolist()

                
                fig_prof_f = None
                if top_10_p_names_f:
                    # Filter and group
                    prof_role_counts_f = df_prof_filtered.groupby(['Professione', 'ruolo']).size().unstack(fill_value=0)
                    prof_role_top10_f = prof_role_counts_f.loc[top_10_p_names_f]
                    prof_role_top10_melted_f = prof_role_top10_f.reset_index().melt(
                        id_vars='Professione',
                        var_name='Ruolo',
                        value_name='Frequenza'
                    )
                    fig_prof_f = px.bar(
                        prof_role_top10_melted_f,
                        x='Professione',
                        y='Frequenza',
                        color='Ruolo',
                        title="Top 10 Categorie Professionali per Ruolo",
                        color_discrete_sequence=px.colors.qualitative.Pastel,
                        barmode='stack'
                    )
                    fig_prof_f.update_layout(
                        template="plotly_white",
                        legend_title="Ruolo",
                        xaxis={'categoryorder': 'array', 'categoryarray': top_10_p_names_f},
                        xaxis_title="Professione",
                        yaxis_title="Numero di Cariche"
                    )
                
                col_prof1, col_prof2 = st.columns([2, 1])
                with col_prof1:
                    if top_10_p_names_f and fig_prof_f is not None:
                        st.plotly_chart(fig_prof_f, width='stretch')
                        # Simple explanation of the professions chart
                        st.markdown("""
                        <div style="margin-top: 1rem; padding: 1.25rem; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;">
                            <h5 style="margin-top: 0; color: #0f172a; font-family: 'Outfit', sans-serif; font-size: 1.1rem; border-bottom: 1px solid #cbd5e1; padding-bottom: 0.5rem;">Guida Semplice al Grafico</h5>
                            <p style="font-size: 0.9rem; color: #334155; line-height: 1.5; margin: 0.5rem 0 0 0;">
                                Questo grafico mostra quali erano i mestieri o le corporazioni (es. mercanti, notai, lanaioli) più rappresentati tra le persone che hanno ricoperto le cariche selezionate:
                            </p>
                            <ul style="margin: 0.5rem 0 0 0; padding-left: 1.25rem; font-size: 0.85rem; color: #334155; line-height: 1.5;">
                                <li style="margin-bottom: 0.4rem;"><strong>Altezza delle colonne:</strong> indica il numero totale di cariche politiche ricoperte da esponenti di quel mestiere. Più la colonna è alta, più quella professione era politicamente influente.</li>
                                <li style="margin-bottom: 0.4rem;"><strong>I diversi colori all'interno di una colonna:</strong> indicano come si dividevano le cariche per quella professione (ad esempio, quanti erano Anziani #1 e quanti Anziani #2).</li>
                            </ul>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.info("Nessun dato sulle professioni disponibile per i ruoli selezionati.")
                with col_prof2:
                    st.markdown("**Top 10 Professioni (Tabella)**")
                    if top_10_p_names_f:
                        prof_table_df = pd.DataFrame({
                            'Professione': top_10_p_names_f,
                            'Frequenza': profession_counts_f.head(10).values
                        })
                        st.dataframe(prof_table_df, width='stretch', hide_index=True)
                    else:
                        st.write("Nessun dato.")
                    
            st.write("---")
            st.markdown("### Statistiche Socio-Professionali")
            
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            with col_stat1:
                st.markdown(f"""
                <div class="card" style="height: 100%; display: flex; flex-direction: column; justify-content: space-between; margin-bottom: 0;">
                    <div>
                        <div class="metric-label" style="margin-bottom: 0.25rem;">Tasso di Identificazione</div>
                        <div class="metric-value">{pct_identified:.1f}%</div>
                        <div style="background-color: #e2e8f0; border-radius: 4px; height: 6px; width: 100%; overflow: hidden; margin: 0.75rem 0;">
                            <div style="background-color: #475569; height: 100%; width: {pct_identified}%;"></div>
                        </div>
                    </div>
                    <div style="font-size: 0.85rem; color: #475569; line-height: 1.6; border-top: 1px solid #e2e8f0; padding-top: 0.75rem; margin-top: auto;">
                        • Identificate: <strong>{identified_prof_count}</strong> cariche<br>
                        • Non identificate: <strong>{total_entries - identified_prof_count}</strong> ({100.0 - pct_identified:.1f}%)<br>
                        • Totale record: <strong>{total_entries}</strong>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            with col_stat2:
                priori_html = ""
                if priori_identified > 0:
                    for prof, val in priori_top.items():
                        pct = (val / priori_identified) * 100
                        priori_html += f'<div style="margin-bottom: 0.6rem;"><div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.25rem;"><span style="font-weight: 500; color: #1e293b;">{prof}</span><span style="font-weight: 600; color: #475569;">{val} ({pct:.1f}%)</span></div><div style="background-color: #e2e8f0; border-radius: 4px; height: 6px; width: 100%; overflow: hidden;"><div style="background-color: #64748b; height: 100%; width: {pct}%;"></div></div></div>'
                else:
                    priori_html = "<div style='color: #64748b; font-size: 0.9rem;'>Nessuna professione identificata.</div>"
                
                st.markdown(f"""
                <div class="card" style="height: 100%; display: flex; flex-direction: column; justify-content: space-between; margin-bottom: 0;">
                    <div>
                        <div class="metric-label" style="margin-bottom: 0.75rem;">Professioni Priori (Top 3)</div>
                        {priori_html}
                    </div>
                    <div style="font-size: 0.85rem; color: #475569; line-height: 1.6; border-top: 1px solid #e2e8f0; padding-top: 0.75rem; margin-top: auto;">
                        Identificate <strong>{priori_identified}</strong> su {total_priori} cariche totali di Priore.
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            with col_stat3:
                anz1_html = ""
                if anz1_identified > 0:
                    for prof, val in anz1_top.items():
                        pct = (val / anz1_identified) * 100
                        anz1_html += f'<div style="margin-bottom: 0.6rem;"><div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.25rem;"><span style="font-weight: 500; color: #1e293b;">{prof}</span><span style="font-weight: 600; color: #475569;">{val} ({pct:.1f}%)</span></div><div style="background-color: #e2e8f0; border-radius: 4px; height: 6px; width: 100%; overflow: hidden;"><div style="background-color: #64748b; height: 100%; width: {pct}%;"></div></div></div>'
                else:
                    anz1_html = "<div style='color: #64748b; font-size: 0.9rem;'>Nessuna professione identificata.</div>"
                
                st.markdown(f"""
                <div class="card" style="height: 100%; display: flex; flex-direction: column; justify-content: space-between; margin-bottom: 0;">
                    <div>
                        <div class="metric-label" style="margin-bottom: 0.75rem;">Professioni Anziano #1 (Top 3)</div>
                        {anz1_html}
                    </div>
                    <div style="font-size: 0.85rem; color: #475569; line-height: 1.6; border-top: 1px solid #e2e8f0; padding-top: 0.75rem; margin-top: auto;">
                        Identificate <strong>{anz1_identified}</strong> su {total_anz1} cariche totali di Anziano #1.
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            with col_stat4:
                anz2_html = ""
                if anz2_identified > 0:
                    for prof, val in anz2_top.items():
                        pct = (val / anz2_identified) * 100
                        anz2_html += f'<div style="margin-bottom: 0.6rem;"><div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.25rem;"><span style="font-weight: 500; color: #1e293b;">{prof}</span><span style="font-weight: 600; color: #475569;">{val} ({pct:.1f}%)</span></div><div style="background-color: #e2e8f0; border-radius: 4px; height: 6px; width: 100%; overflow: hidden;"><div style="background-color: #64748b; height: 100%; width: {pct}%;"></div></div></div>'
                else:
                    anz2_html = "<div style='color: #64748b; font-size: 0.9rem;'>Nessuna professione identificata.</div>"
                
                st.markdown(f"""
                <div class="card" style="height: 100%; display: flex; flex-direction: column; justify-content: space-between; margin-bottom: 0;">
                    <div>
                        <div class="metric-label" style="margin-bottom: 0.75rem;">Professioni Anziano #2 (Top 3)</div>
                        {anz2_html}
                    </div>
                    <div style="font-size: 0.85rem; color: #475569; line-height: 1.6; border-top: 1px solid #e2e8f0; padding-top: 0.75rem; margin-top: auto;">
                        Identificate <strong>{anz2_identified}</strong> su {total_anz2} cariche totali di Anziano #2.
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.write("---")
            prof_report_content = generate_markdown_report(start_yr, end_yr, filtered_time_df, 'Categorie Professionali')
            st.download_button(
                label="📥 Scarica Report Categorie Professionali (.MD)",
                data=prof_report_content,
                file_name=f"report_categorie_professionali_{start_yr}_{end_yr}.md",
                mime="text/markdown",
                key="download_report_md_professions"
            )
                    
        # Rendering code for Distribuzione Cariche
        with tab_roles:
            if not df_fam_time.empty:
                st.slider(
                    "Seleziona l'arco temporale per l'analisi della distribuzione delle cariche",
                    min_value=min_year,
                    max_value=max_year,
                    key="selected_years_roles",
                    on_change=sync_years,
                    args=("selected_years_roles",),
                    step=1
                )
            
            st.markdown("### Distribuzione delle Cariche per le Famiglie Principali")

            st.write(
                "Visualizzazione di come le cariche principali (priore, anziano #1, anziano #2, "
                "notaio anziani, canc. maior) si distribuiscono tra le 10 famiglie più rappresentate complessivamente."
            )
            st.plotly_chart(fig_roles, width='stretch')
            
            # Simple explanation of the roles distribution chart
            st.markdown("""
            <div style="margin-top: 1rem; margin-bottom: 1.5rem; padding: 1.25rem; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;">
                <h5 style="margin-top: 0; color: #0f172a; font-family: 'Outfit', sans-serif; font-size: 1.1rem; border-bottom: 1px solid #cbd5e1; padding-bottom: 0.5rem;">Guida Semplice al Grafico</h5>
                <p style="font-size: 0.9rem; color: #334155; line-height: 1.5; margin: 0.5rem 0 0 0;">
                    Questo grafico mostra in che modo i vari ruoli del governo (priore, anziano, notaio, cancelliere) si ripartivano all'interno delle 10 famiglie più influenti di Pisa:
                </p>
                <ul style="margin: 0.5rem 0 0 0; padding-left: 1.25rem; font-size: 0.85rem; color: #334155; line-height: 1.5;">
                    <li style="margin-bottom: 0.4rem;"><strong>Ogni colonna rappresenta una famiglia:</strong> l'altezza totale indica il numero complessivo di cariche che quella famiglia ha ricoperto in totale nel database.</li>
                    <li style="margin-bottom: 0.4rem;"><strong>I diversi colori all'interno di una colonna:</strong> indicano in che misura la famiglia otteneva specifici ruoli. Ad esempio, permette di notare a colpo d'occhio se una determinata casata deteneva soprattutto ruoli da "Priore" o da "Anziano", svelando le loro sfere di influenza politica.</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("**Dati della Distribuzione (Tabella)**")
            st.dataframe(role_distribution, width='stretch')
            
            st.write("---")
            roles_report_content = generate_markdown_report(start_yr, end_yr, filtered_time_df, 'Distribuzione Cariche')
            st.download_button(
                label="📥 Scarica Report Distribuzione Cariche (.MD)",
                data=roles_report_content,
                file_name=f"report_distribuzione_cariche_{start_yr}_{end_yr}.md",
                mime="text/markdown",
                key="download_report_md_roles"
            )

        # Rendering code for Ricambio nel Tempo
        with tab_turnover:
            if not df_fam_time.empty:
                st.slider(
                    "Seleziona l'arco temporale per l'analisi del ricambio",
                    min_value=min_year,
                    max_value=max_year,
                    key="selected_years_turnover",
                    on_change=sync_years,
                    args=("selected_years_turnover",),
                    step=1
                )
            
            st.markdown("### Analisi del Ricambio dei Gruppi nel Tempo")
                
            st.write(
                "Questa sezione analizza il tasso di ricambio e la stabilità delle cariche politiche "
                "confrontando la composizione dei membri dei vari consigli storici nel tempo."
            )
            
            # Select what to analyze
            analysis_unit = st.selectbox(
                "Cosa desideri analizzare?",
                options=["Individui (singoli politici)", "Famiglie (cognomi/casate)", "Quartieri (provenienza geografica)"],
                index=0,
                key="turnover_analysis_unit"
            )
            
            unit_mapping = {
                "Individui (singoli politici)": "nome",
                "Famiglie (cognomi/casate)": "Famiglia",
                "Quartieri (provenienza geografica)": "quartiere"
            }
            column_name = unit_mapping[analysis_unit]
            
            # Define names for plain-language text interpolation
            unit_names_pl = {
                "nome": {
                    "singular": "persona",
                    "plural": "persone",
                    "capital_plural": "Politici",
                    "prefix": "dei singoli politici",
                    "agreement_noun": "persone",
                    "agreement_adj": "nuove"
                },
                "Famiglia": {
                    "singular": "famiglia",
                    "plural": "famiglie",
                    "capital_plural": "Famiglie",
                    "prefix": "delle famiglie/casate",
                    "agreement_noun": "famiglie",
                    "agreement_adj": "nuove"
                },
                "quartiere": {
                    "singular": "quartiere",
                    "plural": "quartieri",
                    "capital_plural": "Quartieri",
                    "prefix": "dei quartieri di provenienza",
                    "agreement_noun": "quartieri",
                    "agreement_adj": "nuovi"
                }
            }
            u_info = unit_names_pl[column_name]
            
            # Council IDs computed from 'numero mandato', 'anno', and 'mesi'
            df_councils = df[['numero mandato', 'anno', 'mesi']].dropna(subset=['anno', 'mesi']).drop_duplicates().sort_values(by='numero mandato')
            councils_list = []
            for _, row in df_councils.iterrows():
                c_id = f"{row['numero mandato']}. {row['anno']} ({row['mesi']})"
                councils_list.append(c_id)
            
            if not councils_list:
                st.info("Carica un file valido contenente informazioni sui mandati.")
            else:
                st.write("---")
                
                # Checkboxes that do not exclude each other
                st.markdown("**Ruoli da analizzare (selezionabili singolarmente o in combinazione)**")
                col_cb1, col_cb2, col_cb3, col_cb4, col_cb5 = st.columns(5)
                with col_cb1:
                    cb_anz1 = st.checkbox("Anziano #1", value=True, key="cb_turnover_anz1")
                with col_cb2:
                    cb_anz2 = st.checkbox("Anziano #2", value=True, key="cb_turnover_anz2")
                with col_cb3:
                    cb_priore = st.checkbox("Priore", value=False, key="cb_turnover_priore")
                with col_cb4:
                    cb_notaio = st.checkbox("Notaio Anziani", value=False, key="cb_turnover_notaio")
                with col_cb5:
                    cb_canc = st.checkbox("Canc. Maggiore", value=False, key="cb_turnover_canc")
                
                selected_roles = []
                if cb_anz1: selected_roles.append("anziano #1")
                if cb_anz2: selected_roles.append("anziano #2")
                if cb_priore: selected_roles.append("priore")
                if cb_notaio: selected_roles.append("notaio anziani")
                if cb_canc: selected_roles.append("canc. maior")
                
                if not selected_roles:
                    st.warning("Seleziona almeno un ruolo da analizzare.")
                else:
                    # Determine start and end mandates dynamically from the year-filtered dataset
                    if not filtered_time_df.empty:
                        active_mandates_filtered = sorted(filtered_time_df['numero mandato'].dropna().unique())
                        if active_mandates_filtered:
                            start_mandate = int(active_mandates_filtered[0])
                            end_mandate = int(active_mandates_filtered[-1])
                        else:
                            start_mandate = 1
                            end_mandate = 1
                    else:
                        start_mandate = 1
                        end_mandate = 1

                    # Helper to get council labels
                    def get_council_label(m_num):
                        rows = df_councils[df_councils['numero mandato'] == m_num]
                        if not rows.empty:
                            r = rows.iloc[0]
                            return f"{m_num}. {r['anno']} ({r['mesi']})"
                        return f"Mandato {m_num}"

                    start_council_lbl = get_council_label(start_mandate)
                    end_council_lbl = get_council_label(end_mandate)

                    # Sub-tabs for the different types of analysis
                    subtab_rolling, subtab_cohorts, subtab_recurrence, subtab_concentration = st.tabs([
                        "Confronto Rolling (Consiglio vs Consiglio)",
                        "Confronto per Finestre (Coorti)",
                        "Analisi di Ricorrenza (Carriere)",
                        "Indice di Concentrazione (Oligarchia)"
                    ])

                    with subtab_rolling:
                        st.markdown("### 1. Confronto Rolling (Consiglio vs Consiglio)")
                        st.write(
                            "Questo metodo confronta di volta in volta ogni singolo consiglio con quello "
                            "successivo a distanza di una determinata soglia (gap). "
                            "Fornisce una misura dettagliata della rotazione a brevissimo termine."
                        )
                        
                        st.warning("""
                        **Nota Storico-Metodologica:** In questa vista rolling, il ricambio medio rimane costantemente prossimo al 100%. 
                        Ciò è dovuto alla **regola del divieto (o contumacia)** in vigore a Pisa (che vietava la rielezione immediata) e al fatto che ciascun consiglio ha pochissimi seggi (es. 8) rispetto alle centinaia di cittadini eleggibili. 
                        Per osservare dinamiche di medio-lungo termine e aggirare questo effetto contumacia, ti consigliamo di esplorare le schede **Confronto per Finestre (Coorti)** e **Analisi di Ricorrenza (Carriere)**.
                        """)

                        # Step slider for custom interval gap
                        turnover_step_options = [
                            "6 mesi (3 consigli)",
                            "1 anno (6 consigli)",
                            "2 anni (12 consigli)",
                            "3 anni (18 consigli)",
                            "4 anni (24 consigli)",
                            "5 anni (30 consigli)",
                            "6 anni (36 consigli)",
                            "7 anni (42 consigli)",
                            "8 anni (48 consigli)",
                            "9 anni (54 consigli)",
                            "10 anni (60 consigli)",
                            "15 anni (90 consigli)",
                            "20 anni (120 consigli)",
                            "25 anni (150 consigli)",
                            "30 anni (180 consigli)"
                        ]
                        
                        selected_step_label = st.select_slider(
                            "Seleziona l'intervallo temporale per il calcolo del ricambio",
                            options=turnover_step_options,
                            value="6 mesi (3 consigli)",
                            key="turnover_step_slider"
                        )
                        
                        option_to_step = {
                            "6 mesi (3 consigli)": 3,
                            "1 anno (6 consigli)": 6,
                            "2 anni (12 consigli)": 12,
                            "3 anni (18 consigli)": 18,
                            "4 anni (24 consigli)": 24,
                            "5 anni (30 consigli)": 30,
                            "6 anni (36 consigli)": 36,
                            "7 anni (42 consigli)": 42,
                            "8 anni (48 consigli)": 48,
                            "9 anni (54 consigli)": 54,
                            "10 anni (60 consigli)": 60,
                            "15 anni (90 consigli)": 90,
                            "20 anni (120 consigli)": 120,
                            "25 anni (150 consigli)": 150,
                            "30 anni (180 consigli)": 180
                        }
                        step_size = option_to_step[selected_step_label]
                        
                        # Run helper metrics (passing step_size!)
                        metrics = compute_turnover_metrics(df, selected_roles, start_mandate, end_mandate, step_size=step_size, column_name=column_name)
                        
                        if metrics is None:
                            st.info("Nessun dato trovato per i ruoli e periodo selezionati.")
                        else:
                            avg_turnover = metrics['avg_turnover']
                            avg_steps = metrics['avg_steps']
                            pct_overlap_start = metrics['pct_overlap_start']
                            shared_members = metrics['shared_members']
                            start_members = metrics['start_members']
                            end_members = metrics['end_members']
                            top_members = metrics['top_members']
                            
                            if avg_steps is not None:
                                avg_months = avg_steps * 2
                                complete_turnover_str = f"{avg_steps:.1f} Consigli (~{avg_months:.1f} Mesi)"
                            else:
                                complete_turnover_str = "Non raggiungibile nel periodo"
                                
                            # Render KPI Grid
                            col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
                            with col_kpi1:
                                st.markdown(f'<div class="card"><div class="metric-value">{avg_turnover:.1f}%</div><div class="metric-label">Ricambio Medio (Intervallo: {selected_step_label})</div></div>', unsafe_allow_html=True)
                            with col_kpi2:
                                st.markdown(f'<div class="card"><div class="metric-value">{complete_turnover_str}</div><div class="metric-label">Tempo per Ricambio Completo</div></div>', unsafe_allow_html=True)
                            with col_kpi3:
                                st.markdown(f'<div class="card"><div class="metric-value">{pct_overlap_start:.1f}%</div><div class="metric-label">Sovrapposizione Inizio-Fine ({len(shared_members)} comm.)</div></div>', unsafe_allow_html=True)
                                
                            st.write("---")

                            # Render Charts and Explanations Row
                            col_chart1, col_explain = st.columns([1, 1])
                            with col_chart1:
                                if not top_members.empty:
                                    top_n = 10
                                    fig_top_members = px.bar(
                                        x=top_members.head(top_n).values,
                                        y=top_members.head(top_n).index,
                                        orientation='h',
                                        title=f"Top {top_n} {u_info['capital_plural']} per Numero di Partecipazioni ({start_yr}-{end_yr})",
                                        labels={'x': 'Partecipazioni (mandati)', 'y': u_info['singular'].capitalize()},
                                        color_discrete_sequence=px.colors.qualitative.Pastel
                                    )
                                    fig_top_members.update_layout(
                                        yaxis={'categoryorder': 'total ascending'},
                                        template="plotly_white",
                                        height=400
                                    )
                                    st.plotly_chart(fig_top_members, width='stretch')
                                else:
                                    st.info("Nessun dato registrato in questo periodo.")
                                    
                            with col_explain:
                                st.markdown(f"""
                                <div class="card" style="padding: 1.5rem; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;">
                                    <h4 style="margin-top:0; color: #0f172a; font-family: 'Outfit', sans-serif; font-size: 1.2rem; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.5rem;">Guida Semplice alle Statistiche</h4>
                                    <p style="font-size: 0.95rem; line-height: 1.5; color: #334155; margin-bottom: 1rem;">
                                        Questi numeri ti aiutano a capire quanto velocemente cambiava il gruppo di potere nei consigli di Pisa nell'arco selezionato ({start_yr}-{end_yr}):
                                    </p>
                                    <ul style="padding-left: 1.25rem; margin: 0; font-size: 0.95rem; color: #334155;">
                                        <li style="margin-bottom: 0.75rem;">
                                            <strong>Ricambio Medio ({avg_turnover:.1f}%):</strong> 
                                            Indica quante facce nuove entravano in consiglio a distanza di <strong>{selected_step_label}</strong>. 
                                            Un valore di <strong>{avg_turnover:.1f}%</strong> significa che, in media, confrontando due consigli a distanza di {selected_step_label}, quasi 
                                            {int(avg_turnover)} su 100 {u_info['plural']} erano nuovi ingressi rispetto al consiglio di confronto.
                                        </li>
                                        <li style="margin-bottom: 0.75rem;">
                                            <strong>Tempo per Ricambio Completo ({complete_turnover_str}):</strong> 
                                            Rappresenta il tempo medio necessario affinché <strong>tutti</strong> i membri di un consiglio venissero sostituiti da persone nuove. 
                                            Ci dice quindi dopo quanti consigli (e quanti mesi stimati) non era rimasta in carica nessuna delle vecchie persone del consiglio di partenza.
                                        </li>
                                        <li style="margin-bottom: 0.75rem;">
                                            <strong>Sovrapposizione Inizio-Fine ({pct_overlap_start:.1f}%):</strong> 
                                            Mette a confronto il consiglio iniziale ({start_council_lbl}) e quello finale ({end_council_lbl}) del periodo selezionato. 
                                            La percentuale del <strong>{pct_overlap_start:.1f}%</strong> indica la porzione di {u_info['plural']} che sono riusciti a rimanere 
                                            (o a ritornare) al potere tra l'inizio e la fine del periodo. Più è alta, più il potere è rimasto nelle mani degli stessi gruppi.
                                        </li>
                                    </ul>
                                </div>
                                """, unsafe_allow_html=True)
                                    
                            st.write("---")
                            
                            # Detailed Overlap Section
                            st.markdown(f"### Dettaglio Sovrapposizione Estremi (Inizio vs Fine)")
                            col_start_list, col_end_list = st.columns(2)
                            with col_start_list:
                                st.markdown(f"**{u_info['capital_plural']} presenti all'inizio ({start_council_lbl})**")
                                if start_members:
                                    st.write(", ".join(sorted(list(start_members))))
                                else:
                                    st.write(f"*Nessun {u_info['singular']} registrato per questi ruoli*")
                            with col_end_list:
                                st.markdown(f"**{u_info['capital_plural']} presenti alla fine ({end_council_lbl})**")
                                if end_members:
                                    st.write(", ".join(sorted(list(end_members))))
                                else:
                                    st.write(f"*Nessun {u_info['singular']} registrato per questi ruoli*")
                                    
                            st.markdown(f"**{u_info['capital_plural']} condivisi (in comune tra l'inizio e la fine del periodo):**")
                            if shared_members:
                                st.success(", ".join(sorted(list(shared_members))))
                            else:
                                st.info(f"Nessun {u_info['singular']} in comune tra l'inizio e la fine del periodo selezionato.")

                    with subtab_cohorts:
                        st.markdown("### 2. Confronto per Finestre Temporali (Coorti)")
                        st.write(
                            "Questo metodo raggruppa tutti i consigli in blocchi pluriennali (coorti) consecutivi. "
                            "Filtra la rotazione a breve termine (contumacia) per analizzare la circolazione della classe politica nel medio-lungo termine."
                        )
                        
                        # Determine block size
                        block_size = st.slider("Dimensione della finestra temporale (in anni)", min_value=2, max_value=10, value=5, step=1, key="turnover_cohort_block_size")
                        
                        # Split active year range into blocks
                        blocks = []
                        curr_yr = start_yr
                        while curr_yr <= end_yr:
                            next_yr = min(curr_yr + block_size - 1, end_yr)
                            blocks.append((curr_yr, next_yr))
                            curr_yr += block_size
                            
                        # Calculate turnover between consecutive blocks
                        cohort_turnovers = []
                        cohort_chart_data = []
                        
                        # Store unique members per block
                        block_members = {}
                        for b_start, b_end in blocks:
                            b_df = filtered_time_df[
                                (filtered_time_df['start_year'] >= b_start) & 
                                (filtered_time_df['start_year'] <= b_end) &
                                (filtered_time_df['ruolo'].isin(selected_roles))
                            ]
                            members = set(b_df[column_name].dropna().unique())
                            block_members[(b_start, b_end)] = members
                            
                        for i in range(len(blocks) - 1):
                            b1 = blocks[i]
                            b2 = blocks[i+1]
                            m1 = block_members[b1]
                            m2 = block_members[b2]
                            if m1 and m2:
                                new_m = m2 - m1
                                turnval = (len(new_m) / len(m2)) * 100
                                cohort_turnovers.append(turnval)
                                label = f"{b1[0]}-{b1[1]} vs {b2[0]}-{b2[1]}"
                                cohort_chart_data.append({
                                    'Confronto': label,
                                    'Ricambio Coorti (%)': turnval
                                })
                                
                        if cohort_chart_data:
                            df_cohort_c = pd.DataFrame(cohort_chart_data)
                            avg_cohort_t = np.mean(cohort_turnovers)
                            
                            col_c1, col_c2 = st.columns([2, 1])
                            with col_c1:
                                fig_cohort = px.line(
                                    df_cohort_c,
                                    x='Confronto',
                                    y='Ricambio Coorti (%)',
                                    title=f"Ricambio tra Finestre Temporali di {block_size} anni (Media: {avg_cohort_t:.1f}%)",
                                    markers=True,
                                    color_discrete_sequence=px.colors.qualitative.Pastel
                                )
                                fig_cohort.update_layout(template="plotly_white", yaxis_range=[0, 105])
                                st.plotly_chart(fig_cohort, width='stretch')
                            with col_c2:
                                st.markdown(f'<div class="card"><div class="metric-value">{avg_cohort_t:.1f}%</div><div class="metric-label">Ricambio Medio Coorti</div></div>', unsafe_allow_html=True)
                                st.markdown(f"""
                                <div style="font-size: 0.95rem; color: #334155; line-height: 1.6; padding: 1.5rem; border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc;">
                                    <h5 style="margin: 0 0 0.75rem 0; font-family: 'Outfit', sans-serif; font-size: 1.1rem; color: #0f172a;">Spiegazione Intuitiva</h5>
                                    Invece di confrontare singoli consigli consecutivi (che mostrano tassi di ricambio vicini al 100% a causa delle regole di contumacia/divieto), raggruppiamo i mandati in blocchi di <strong>{block_size} anni</strong> (coorti).
                                    <br><br>
                                    Un ricambio medio delle coorti del <strong>{avg_cohort_t:.1f}%</strong> indica che, passando da un blocco di {block_size} anni al successivo:
                                    <ul style="margin: 0.5rem 0; padding-left: 1.25rem;">
                                        <li>Circa il <strong>{avg_cohort_t:.1f}%</strong> di {u_info['agreement_noun']} è composto da <strong>{u_info['agreement_adj']} entrate</strong> (soggetti mai apparsi nel blocco precedente).</li>
                                        <li>Il restante <strong>{100.0 - avg_cohort_t:.1f}%</strong> di {u_info['agreement_noun']} rappresenta la <strong>continuità</strong> (soggetti già attivi nel periodo precedente che ritornano in carica).</li>
                                    </ul>
                                    Se questo tasso scende sensibilmente rispetto al confronto rolling, significa che la classe politica pisa era controllata da un nucleo stabile di persone o famiglie che si alternavano regolarmente al potere nel medio-lungo termine.
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.info("Periodo selezionato troppo breve per creare almeno due coorti successive di questa dimensione. Allarga il filtro degli anni in cima alla pagina.")

                    with subtab_recurrence:
                        st.markdown("### 3. Analisi di Ricorrenza (Carriere Politiche)")
                        st.write(
                            "Questo metodo analizza quante volte i singoli individui o famiglie "
                            "ritornano a ricoprire le cariche politiche nel periodo selezionato. "
                            "Rivela se il potere tende a concentrarsi ciclicamente sempre nelle stesse mani."
                        )
                        
                        df_rec = filtered_time_df[filtered_time_df['ruolo'].isin(selected_roles)].copy()
                        service_counts = df_rec[column_name].value_counts().dropna()
                        
                        if not service_counts.empty:
                            total_unique = len(service_counts)
                            more_than_once = (service_counts > 1).sum()
                            rec_rate = (more_than_once / total_unique) * 100
                            
                            bins = [0, 1, 2, 4, 100]
                            labels = ["1 sola volta", "2 volte", "3-4 volte", "5+ volte"]
                            categorized = pd.cut(service_counts, bins=bins, labels=labels).value_counts().reindex(labels)
                            
                            categorized.index.name = 'Frequenza di ritorno'
                            df_cat = categorized.reset_index(name='Numero di soggetti')
                            
                            col_r1, col_r2 = st.columns([2, 1])
                            with col_r1:
                                fig_rec = px.bar(
                                    df_cat,
                                    x='Frequenza di ritorno',
                                    y='Numero di soggetti',
                                    title=f"Frequenza di ritorno al potere ({start_yr}-{end_yr})",
                                    text_auto=True,
                                    color_discrete_sequence=px.colors.qualitative.Pastel
                                )
                                fig_rec.update_layout(template="plotly_white")
                                st.plotly_chart(fig_rec, width='stretch')
                            with col_r2:
                                st.markdown(f'<div class="card"><div class="metric-value">{rec_rate:.1f}%</div><div class="metric-label">Tasso di Ricorrenza (Ritorno al potere)</div></div>', unsafe_allow_html=True)
                                st.markdown(f"""
                                <div style="font-size: 0.95rem; color: #334155; line-height: 1.6; padding: 1.5rem; border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc;">
                                    <h5 style="margin: 0 0 0.75rem 0; font-family: 'Outfit', sans-serif; font-size: 1.1rem; color: #0f172a;">Spiegazione Intuitiva</h5>
                                    Questa sezione mostra quante volte gli stessi soggetti (singole persone o intere famiglie) riescono a tornare al potere durante il periodo selezionato.
                                    <br><br>
                                    Un tasso di ricorrenza del <strong>{rec_rate:.1f}%</strong> indica che {int(rec_rate)} su 100 {u_info['agreement_noun']} unici presenti nel periodo sono <strong>ritornati in carica almeno una seconda volta</strong>.
                                    <br><br>
                                    Se le categorie "3-4 volte" o "5+ volte" sono molto popolate, abbiamo la prova empirica di una <em>classe politica professionale e persistente</em>, che aggira il divieto di rielezione immediata ritornando al potere non appena scade il periodo obbligatorio di contumacia.
                                </div>
                                """, unsafe_allow_html=True)
                                
                            st.markdown("---")
                            st.markdown(f"### Dettaglio dei Soggetti più Ricorrenti ({start_yr}-{end_yr})")
                            top_n_rec = 10
                            top_recurrent = service_counts.head(top_n_rec)
                            df_top_rec = pd.DataFrame({
                                u_info['singular'].capitalize(): top_recurrent.index,
                                'Numero di Mandati': top_recurrent.values
                            })
                            st.dataframe(df_top_rec, hide_index=True, width='stretch')
                        else:
                            st.info("Nessun dato disponibile per i filtri selezionati.")

                    with subtab_concentration:
                        st.markdown("### 4. Indice di Concentrazione (Concentrazione del Potere)")
                        st.write(
                            "Questo metodo misura la distribuzione della quota di cariche detenuta dai diversi soggetti. "
                            "Usa l'indice di Gini (standard internazionale per la misurazione della diseguaglianza) e la curva di concentrazione per mostrare il livello di monopolizzazione."
                        )
                        
                        df_rec = filtered_time_df[filtered_time_df['ruolo'].isin(selected_roles)].copy()
                        service_counts = df_rec[column_name].value_counts().dropna()
                        
                        if not service_counts.empty:
                            counts = service_counts.values
                            counts_sorted = sorted(counts, reverse=True)
                            total_seats = sum(counts_sorted)
                            cum_seats = np.cumsum(counts_sorted)
                            cum_percent_seats = (cum_seats / total_seats) * 100
                            percent_pop = (np.arange(1, len(counts_sorted) + 1) / len(counts_sorted)) * 100
                            
                            percent_pop = np.insert(percent_pop, 0, 0.0)
                            cum_percent_seats = np.insert(cum_percent_seats, 0, 0.0)
                            
                            def gini_coef(array):
                                if len(array) == 0 or np.sum(array) == 0:
                                    return 0.0
                                array = np.array(array, dtype=np.float64)
                                array = np.sort(array)
                                index = np.arange(1, array.shape[0] + 1)
                                n = array.shape[0]
                                return ((2 * index - n - 1) * array).sum() / (n * array.sum())
                                
                            gini_v = gini_coef(counts)
                            
                            top_10_pct_count = max(1, int(len(counts_sorted) * 0.1))
                            top_10_pct_share = cum_percent_seats[top_10_pct_count]
                            
                            df_lorenz = pd.DataFrame({
                                'Percentuale Soggetti': percent_pop,
                                'Percentuale Cumulata Seggi': cum_percent_seats
                            })
                            
                            col_o1, col_o2 = st.columns([2, 1])
                            with col_o1:
                                fig_lorenz = px.area(
                                    df_lorenz,
                                    x='Percentuale Soggetti',
                                    y='Percentuale Cumulata Seggi',
                                    title=f"Curva di Concentrazione delle Cariche ({start_yr}-{end_yr})",
                                    labels={'Percentuale Soggetti': '% dei Soggetti (ordinati dal più potente al meno potente)', 'Percentuale Cumulata Seggi': '% Cumulata delle cariche detenute'},
                                    color_discrete_sequence=px.colors.qualitative.Pastel
                                )
                                fig_lorenz.add_trace(go.Scatter(
                                    x=[0, 100],
                                    y=[0, 100],
                                    mode='lines',
                                    name='Perfetta Uguaglianza (Rotazione Completa)',
                                    line=dict(color='#94a3b8', dash='dash', width=2)
                                ))
                                fig_lorenz.update_layout(
                                    template="plotly_white",
                                    yaxis_range=[0, 105],
                                    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
                                )
                                st.plotly_chart(fig_lorenz, width='stretch')
                            with col_o2:
                                st.markdown(f'<div class="card"><div class="metric-value">{gini_v:.2f}</div><div class="metric-label">Indice di Gini (0 = Uguaglianza, 1 = Monopolio)</div></div>', unsafe_allow_html=True)
                                st.markdown(f'<div class="card"><div class="metric-value">{top_10_pct_share:.1f}%</div><div class="metric-label">Quota Detenuta dal Top 10%</div></div>', unsafe_allow_html=True)
                                st.markdown(f"""
                                <div style="font-size: 0.95rem; color: #334155; line-height: 1.6; padding: 1.5rem; border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc;">
                                    <h5 style="margin: 0 0 0.75rem 0; font-family: 'Outfit', sans-serif; font-size: 1.1rem; color: #0f172a;">Spiegazione Intuitiva</h5>
                                    L\'<strong>Indice di Gini</strong> è un coefficiente standard utilizzato per misurare la concentrazione o la diseguaglianza nella distribuzione di una risorsa (in questo caso, il potere politico misurato in cariche ricoperte):
                                    <ul style="margin: 0.5rem 0; padding-left: 1.25rem;">
                                        <li><strong>Valore pari a 0 (Perfetta Distribuzione):</strong> Tutti i soggetti ricoprono le cariche lo stesso numero di volte (es. una volta ciascuno).</li>
                                        <li><strong>Valore vicino a 1 (Monopolizzazione Totale):</strong> Una sola persona o famiglia ricopre quasi tutte le cariche, escludendo gli altri.</li>
                                    </ul>
                                    In questo arco temporale, l\'indice è pari a <strong>{gini_v:.2f}</strong>.
                                    <br><br>
                                    Inoltre, il grafico mostra che il <strong>top 10%</strong> dei soggetti più influenti (pari a <strong>{top_10_pct_count}</strong> {u_info['agreement_noun']}) monopolizza ben il <strong>{top_10_pct_share:.1f}%</strong> del totale delle cariche disponibili. Questo indica una forte natura oligarchica della politica pisana nel periodo.
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.info("Nessun dato disponibile.")
            
            st.write("---")
            turnover_report_content = generate_markdown_report(start_yr, end_yr, filtered_time_df, 'Ricambio nel Tempo')
            st.download_button(
                label="📥 Scarica Report Ricambio nel Tempo (.MD)",
                data=turnover_report_content,
                file_name=f"report_ricambio_tempo_{start_yr}_{end_yr}.md",
                mime="text/markdown",
                key="download_report_md_turnover"
            )



        # Rendering code for Classifiche Personalizzate (Top N)
        with tab_rankings:
            if not df_fam_time.empty:
                ranking_selected_years = st.slider(
                    "Seleziona l'arco temporale per la classifica",
                    min_value=min_year,
                    max_value=max_year,
                    key="ranking_year_range_slider",
                    on_change=sync_years,
                    args=("ranking_year_range_slider",),
                    step=1
                )
                start_yr_rank, end_yr_rank = ranking_selected_years
            else:
                start_yr_rank, end_yr_rank = min_year, max_year

            st.markdown("### Generatore di Classifiche Personalizzate (Top N)")
            st.write(
                "Questa sezione consente di calcolare le graduatorie delle cariche politiche per "
                "scoprire chi ha ricoperto il maggior numero di ruoli nel Comune di Pisa, "
                "filtrando per variabile, limite delle posizioni (N) e arco temporale."
            )
            
            # Setup columns for the selectors
            col_rank1, col_rank2 = st.columns(2)
            
            with col_rank1:
                selected_variable = st.selectbox(
                    "Seleziona la variabile da analizzare",
                    options=["Individuo", "Famiglia", "Quartiere", "Professione"],
                    index=0,
                    key="ranking_variable_selector"
                )
            
            with col_rank2:
                ranking_n_limit = st.slider(
                    "Seleziona il limite della classifica (N)",
                    min_value=5,
                    max_value=100,
                    value=10,
                    step=5,
                    key="ranking_n_selector"
                )

                
            st.write("---")
            
            # Perform calculations
            var_col_mapping = {
                "Individuo": "nome",
                "Famiglia": "Famiglia",
                "Quartiere": "quartiere",
                "Professione": "Professione"
            }
            target_col = var_col_mapping[selected_variable]
            
            # Filter the time-sorted dataset
            df_rank_filtered = df_fam_time[
                (df_fam_time['start_year'] >= start_yr_rank) &
                (df_fam_time['start_year'] <= end_yr_rank)
            ].copy()
            
            if df_rank_filtered.empty:
                st.info("Nessun dato registrato nell'arco temporale selezionato.")
            else:
                # Group and count occurrences
                occurrences = df_rank_filtered[target_col].value_counts().dropna()
                
                if occurrences.empty:
                    st.info(f"Nessuna occorrenza trovata per la variabile '{selected_variable}' nel periodo selezionato.")
                else:
                    # Form the final dataframe
                    ranking_results_df = occurrences.reset_index()
                    ranking_results_df.columns = [selected_variable, 'Occorrenze (Numero di Cariche)']
                    ranking_results_df.index = ranking_results_df.index + 1  # 1-based ranking index
                    ranking_results_df = ranking_results_df.head(ranking_n_limit)
                    
                    st.markdown(f"### Classifica: Top {len(ranking_results_df)} {selected_variable} ({start_yr_rank}-{end_yr_rank})")
                    st.dataframe(ranking_results_df, width='stretch', hide_index=False)
                    
                    # CSV Download Button
                    csv_rank_data = ranking_results_df.to_csv(index=True).encode('utf-8')
                    st.download_button(
                        label=f"Scarica Classifica come CSV",
                        data=csv_rank_data,
                        file_name=f"classifica_{selected_variable.lower()}_top{ranking_n_limit}_{start_yr_rank}_{end_yr_rank}.csv",
                        mime="text/csv",
                        key="download_custom_ranking_btn"
                    )
            
            st.write("---")
            rankings_report_content = generate_markdown_report(start_yr_rank, end_yr_rank, df_rank_filtered, 'Classifiche Personalizzate')
            st.download_button(
                label="📥 Scarica Report Classifiche Personalizzate (.MD)",
                data=rankings_report_content,
                file_name=f"report_classifiche_personalizzate_{start_yr_rank}_{end_yr_rank}.md",
                mime="text/markdown",
                key="download_report_md_rankings"
            )

    elif page_option == "savi":
        st.markdown('<div class="section-header">Analisi del Consiglio dei Savi</div>', unsafe_allow_html=True)
        st.write(
            "Il Consiglio dei Savi costituiva l'organo decisionale di vertice (l'élite decisionale) della Pisa "
            "medievale, operante a stretto contatto con il Consiglio degli Anziani. "
            "Questa dashboard mappa le dinamiche di potere e le reti di consorterie (parentele) suddivise in 5 Cerchi di Potere."
        )

        SAVI_EXCEL_PATH = os.path.join("data", "Lista di Savi e Cerchi di potere.xlsx")
        savi_std_csv = os.path.join("data", "savi_standardized.csv")
        savi_circ_csv = os.path.join("data", "savi_circles.csv")
        csv_target = os.path.join("data", "total_df.csv")

        # Check if precomputed CSV files exist, if not, generate them on the fly (first-time fallback)
        if not os.path.exists(savi_std_csv) or not os.path.exists(savi_circ_csv):
            if os.path.exists(csv_target) and os.path.exists(SAVI_EXCEL_PATH):
                try:
                    with st.spinner("Calcolo iniziale dei Cerchi di Potere in corso..."):
                        precompute_and_save_savi_data(SAVI_EXCEL_PATH, csv_target)
                except Exception as ex:
                    st.error(f"Errore nella generazione dei file pre-elaborati dei Savi: {ex}")
                    st.stop()
            else:
                st.info(f"Il database dei Savi predefinito non è stato trovato in '{SAVI_EXCEL_PATH}'. Per favore, carica un file Excel nella pagina di Download per iniziare.")
                st.stop()

        # Load precomputed data
        if True: # Keep block structure for indentation compatibility
            try:
                df_savi = pd.read_csv(savi_std_csv)
                df_circles = pd.read_csv(savi_circ_csv)
                
                c0 = df_circles[df_circles['cerchio'] == 'C0']['nome'].dropna().tolist()
                c1 = df_circles[df_circles['cerchio'] == 'C1']['nome'].dropna().tolist()
                c2 = df_circles[df_circles['cerchio'] == 'C2']['nome'].dropna().tolist()
                c3 = df_circles[df_circles['cerchio'] == 'C3']['nome'].dropna().tolist()
                c4 = df_circles[df_circles['cerchio'] == 'C4']['nome'].dropna().tolist()
                
                df_anziani_unici = df_circles[df_circles['cerchio'].isin(['C2', 'C3', 'C4'])].copy()
                
                # 3. KPI Metrics
                st.markdown('<div class="section-header">1. Dimensioni dei Cerchi di Potere (Individui Fisici Unici)</div>', unsafe_allow_html=True)
                col_c0, col_c1, col_c2, col_c3, col_c4 = st.columns(5)
                with col_c0:
                    st.markdown(f'<div class="card"><div class="metric-value">{len(c0)}</div><div class="metric-label">C0: Aristocrazia (Solo Savi)</div></div>', unsafe_allow_html=True)
                with col_c1:
                    st.markdown(f'<div class="card"><div class="metric-value">{len(c1)}</div><div class="metric-label">C1: Nobiltà Ist. (Entrambi)</div></div>', unsafe_allow_html=True)
                with col_c2:
                    st.markdown(f'<div class="card"><div class="metric-value">{len(c2)}</div><div class="metric-label">C2: Elite (Entrambi)</div></div>', unsafe_allow_html=True)
                with col_c3:
                    st.markdown(f'<div class="card"><div class="metric-value">{len(c3)}</div><div class="metric-label">C3: Consorterie (Parenti C2)</div></div>', unsafe_allow_html=True)
                with col_c4:
                    st.markdown(f'<div class="card"><div class="metric-value">{len(c4)}</div><div class="metric-label">C4: Nuovi Attori (Esterni)</div></div>', unsafe_allow_html=True)
                
                st.write("---")
                
                # Precompute Neighborhood Composition Chart
                df_circles_clean = df_circles.copy()
                df_circles_clean['quartiere'] = df_circles_clean['quartiere'].astype(str).str.strip().str.capitalize()
                
                circle_name_map = {
                    'C0': 'C0: Aristocrazia',
                    'C1': 'C1: Nobiltà Ist.',
                    'C2': 'C2: Elite',
                    'C3': 'C3: Consorterie',
                    'C4': 'C4: Nuovi Attori'
                }
                df_circles_clean['cerchio_desc'] = df_circles_clean['cerchio'].map(circle_name_map)
                df_q = df_circles_clean.groupby(['cerchio_desc', 'quartiere']).size().reset_index(name='Individui')
                category_order = ['C0: Aristocrazia', 'C1: Nobiltà Ist.', 'C2: Elite', 'C3: Consorterie', 'C4: Nuovi Attori']
                
                fig_neighborhoods = px.bar(
                    df_q,
                    x='cerchio_desc',
                    y='Individui',
                    color='quartiere',
                    barmode='stack',
                    title="Composizione per Quartiere nei Cerchi di Potere",
                    labels={'cerchio_desc': 'Cerchio di Potere', 'Individui': 'Numero di Individui', 'quartiere': 'Quartiere'},
                    color_discrete_sequence=['#94a3b8', '#818cf8', '#34d399', '#f87171']
                )
                fig_neighborhoods.update_layout(
                    template="plotly_white",
                    xaxis={'categoryorder': 'array', 'categoryarray': category_order},
                    xaxis_title="",
                    yaxis_title="Numero di Individui"
                )

                # 4. Side-by-side charts
                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    fig_circles = px.bar(
                        x=['C0: Aristocrazia', 'C1: Nobiltà Ist.', 'C2: Elite', 'C3: Consorterie', 'C4: Nuovi Attori'],
                        y=[len(c0), len(c1), len(c2), len(c3), len(c4)],
                        labels={'x': 'Cerchio di Potere', 'y': 'Persone Fisiche (Uniche)'},
                        title="Distribuzione Finale degli Individui per Cerchi di Potere",
                        color_discrete_sequence=['#475569']
                    )
                    fig_circles.update_layout(
                        template="plotly_white",
                        yaxis_title="Numero di Individui Fisici",
                        xaxis_title=""
                    )
                    st.plotly_chart(fig_circles, width='stretch')
                
                with col_chart2:
                    st.plotly_chart(fig_neighborhoods, width='stretch')
                
                # Definitions box below the charts (full width)
                st.markdown("""
                <div class="card" style="padding: 1.25rem; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-top: 1rem;">
                    <h5 style="margin-top: 0; color: #0f172a; font-family: 'Outfit', sans-serif; font-size: 1.1rem; border-bottom: 1px solid #cbd5e1; padding-bottom: 0.5rem;">Definizione dei Cerchi di Potere</h5>
                    <ul style="margin: 0.5rem 0 0 0; padding-left: 1.25rem; font-size: 0.85rem; color: #334155; line-height: 1.6;">
                        <li style="margin-bottom: 0.5rem;"><strong>C0: Nobili Solo Savi</strong>. Esponenti dell'aristocrazia pura che mantengono cariche solo in seno al Consiglio dei Savi.</li>
                        <li style="margin-bottom: 0.5rem;"><strong>C1: Nobili in Entrambi</strong>. Nobili che siedono contemporaneamente o in tempi diversi in entrambi i consigli (fenomeno quasi inesistente).</li>
                        <li style="margin-bottom: 0.5rem;"><strong>C2: Elite (Non Nobili)</strong>. Uomini nuovi o popolari emergenti presenti sia nei Savi che negli Anziani.</li>
                        <li style="margin-bottom: 0.5rem;"><strong>C3: Parenti dell'Elite (Consorterie)</strong>. Anziani che non siedono nei Savi, ma appartengono alle stesse casate/famiglie del Cerchio 2.</li>
                        <li style="margin-bottom: 0.5rem;"><strong>C4: Uomini Nuovi Esterni</strong>. Membri del consiglio degli Anziani che non hanno alcun legame diretto o parentale con i Savi.</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
                
                st.write("---")
                
                # 5. Top Families Rankings (2x2 Grid)
                st.markdown('<div class="section-header">2. Egemonia Familiare per Cerchio (Top 10)</div>', unsafe_allow_html=True)
                
                def get_family_counts_for_names(names, source_df):
                    df_sub = source_df[source_df['nome'].isin(names)].copy()
                    counts = df_sub.drop_duplicates(subset=['nome'])['famiglia'].value_counts().reset_index()
                    counts.columns = ['Famiglia', 'Numero Individui']
                    return counts.head(10)
                
                stats_c0 = get_family_counts_for_names(c0, df_savi)
                stats_c2 = get_family_counts_for_names(c2, df_anziani_unici)
                stats_c3 = get_family_counts_for_names(c3, df_anziani_unici)
                stats_c4 = get_family_counts_for_names(c4, df_anziani_unici)
                
                # Row 1: C0 and C2
                col_f0, col_f2 = st.columns(2)
                with col_f0:
                    st.markdown("**Top Famiglie Aristocratiche (C0)**")
                    if not stats_c0.empty:
                        fig_f0 = px.bar(
                            stats_c0, x='Numero Individui', y='Famiglia', orientation='h',
                            color_discrete_sequence=['#94a3b8']
                        )
                        fig_f0.update_layout(yaxis={'categoryorder': 'total ascending'}, template="plotly_white", margin=dict(l=10, r=10, t=10, b=10), height=300)
                        st.plotly_chart(fig_f0, width='stretch', config={'displayModeBar': False})
                    else:
                        st.write("Nessun dato.")
                        
                with col_f2:
                    st.markdown("**Top Famiglie: Elite (C2)**")
                    if not stats_c2.empty:
                        fig_f2 = px.bar(
                            stats_c2, x='Numero Individui', y='Famiglia', orientation='h',
                            color_discrete_sequence=['#76D7C4']
                        )
                        fig_f2.update_layout(yaxis={'categoryorder': 'total ascending'}, template="plotly_white", margin=dict(l=10, r=10, t=10, b=10), height=300)
                        st.plotly_chart(fig_f2, width='stretch', config={'displayModeBar': False})
                    else:
                        st.write("Nessun dato.")
                
                # Row 2: C3 and C4
                col_f3, col_f4 = st.columns(2)
                with col_f3:
                    st.markdown("**Top Famiglie: Rete Consorterie (C3)**")
                    if not stats_c3.empty:
                        fig_f3 = px.bar(
                            stats_c3, x='Numero Individui', y='Famiglia', orientation='h',
                            color_discrete_sequence=['#F1948A']
                        )
                        fig_f3.update_layout(yaxis={'categoryorder': 'total ascending'}, template="plotly_white", margin=dict(l=10, r=10, t=10, b=10), height=300)
                        st.plotly_chart(fig_f3, width='stretch', config={'displayModeBar': False})
                    else:
                        st.write("Nessun dato.")
                        
                with col_f4:
                    st.markdown("**Top Famiglie: Nuovi Attori (C4)**")
                    if not stats_c4.empty:
                        fig_f4 = px.bar(
                            stats_c4, x='Numero Individui', y='Famiglia', orientation='h',
                            color_discrete_sequence=['#B0C4DE']
                        )
                        fig_f4.update_layout(yaxis={'categoryorder': 'total ascending'}, template="plotly_white", margin=dict(l=10, r=10, t=10, b=10), height=300)
                        st.plotly_chart(fig_f4, width='stretch', config={'displayModeBar': False})
                    else:
                        st.write("Nessun dato.")
                        
                st.write("---")
                
                # 6. Interactive Circle Explorer & Export
                st.markdown('<div class="section-header">3. Esplora i Membri dei Cerchi di Potere</div>', unsafe_allow_html=True)
                selected_circle = st.selectbox(
                    "Seleziona un cerchio da esplorare:",
                    options=['C0: Aristocrazia (Solo Savi)', 'C1: Nobiltà Istituzionale (Entrambi)', 'C2: Elite (Entrambi)', 'C3: Rete Consorterie (Parenti C2)', 'C4: Nuovi Attori (Esterni)']
                )
                
                circle_mapping = {
                    'C0: Aristocrazia (Solo Savi)': (c0, df_savi, "C0_Aristocrazia"),
                    'C1: Nobiltà Istituzionale (Entrambi)': (c1, df_savi, "C1_Nobilta_Istituzionale"),
                    'C2: Elite (Entrambi)': (c2, df_anziani_unici, "C2_Elite"),
                    'C3: Rete Consorterie (Parenti C2)': (c3, df_anziani_unici, "C3_Rete_Consorterie"),
                    'C4: Nuovi Attori (Esterni)': (c4, df_anziani_unici, "C4_Uomini_Nuovi")
                }
                
                names_in_circle, df_source, file_suffix = circle_mapping[selected_circle]
                
                # Filter rows in source df
                df_members = df_source[df_source['nome'].isin(names_in_circle)].copy()
                # Deduplicate members by name
                df_members = df_members.drop_duplicates(subset=['nome'])
                
                if df_members.empty:
                    st.info(f"Nessun individuo registrato nel {selected_circle}.")
                else:
                    # Select specific columns to show
                    cols_to_show = ['nome', 'famiglia', 'quartiere']
                    if 'Nobile' in df_members.columns:
                        cols_to_show.append('Nobile')
                    
                    df_members_show = df_members[cols_to_show].reset_index(drop=True)
                    df_members_show.columns = [c.capitalize() for c in cols_to_show]
                    
                    # Display count
                    st.markdown(f"**Trovati {len(df_members_show)} individui unici**")
                    st.dataframe(df_members_show, width='stretch', hide_index=True)
                    
                    # Download CSV
                    csv_members = df_members_show.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label=f"Scarica elenco {selected_circle} come CSV",
                        data=csv_members,
                        file_name=f"elenco_{file_suffix.lower()}.csv",
                        mime="text/csv"
                    )
                
                st.write("---")
                st.markdown("### 📥 Esporta Report Consiglio dei Savi")
                savi_report_content = generate_markdown_report(start_yr, end_yr, filtered_time_df, 'savi')
                st.download_button(
                    label="Scarica Report Savi (.MD)",
                    data=savi_report_content,
                    file_name=f"report_savi_{start_yr}_{end_yr}.md",
                    mime="text/markdown",
                    key="download_report_md_savi"
                )
            except Exception as e:
                st.error(f"Errore nel caricamento o elaborazione dei dati dei Savi: {e}")
        else:
            pass

    else: # download
        if not df_fam_time.empty:
            st.slider(
                "Seleziona l'arco temporale per l'esportazione dei dati",
                min_value=min_year,
                max_value=max_year,
                key="selected_years_download",
                on_change=sync_years,
                args=("selected_years_download",),
                step=1
            )
        st.markdown("### Gestione Database & Esportazione Report")
        subpage = st.radio("Seleziona l'azione", ["Download Report e Grafici", "Aggiorna Database (Upload Excel)"], horizontal=True, label_visibility="collapsed")
        
        if subpage == "Aggiorna Database (Upload Excel)":
            st.markdown("### Aggiorna il database dei mandati (Excel)")
            st.write(
                "In questa sezione puoi caricare una nuova versione del file Excel per aggiornare il database dell'applicazione. "
                "Il file caricato verrà verificato e standardizzato. Se la procedura va a buon fine, il file corrente "
                "in `data/Anziani del Comune di Pisa 1344-1392.xlsx` verrà sovrascritto e tutte le schede verranno aggiornate automaticamente. "
                "Per sicurezza, una copia di backup del file precedente verrà salvata con un timestamp."
            )
            
            uploaded_file = st.file_uploader(
                "Scegli un file Excel (.xlsx, .xls)",
                type=["xlsx", "xls"],
                help="Trascina o seleziona il file Excel dei mandati da importare.",
                key="excel_db_uploader"
            )
            
            if uploaded_file is not None:
                upload_key = f"{uploaded_file.name}_{uploaded_file.size}"
                if st.session_state.get("last_saved_upload") != upload_key:
                    try:
                        with st.spinner("Verifica e standardizzazione del file in corso..."):
                            # Attempt to standardize the uploaded file in memory first
                            std_df = robust_standardize_excel(uploaded_file)
                            if std_df is None or std_df.empty:
                                raise ValueError("Il file standardizzato risulta vuoto.")
                            
                            # Backup the current file if it exists
                            import shutil
                            from datetime import datetime
                            if os.path.exists(DEFAULT_EXCEL_PATH):
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                backup_path = DEFAULT_EXCEL_PATH.replace(".xlsx", f"_backup_{timestamp}.xlsx")
                                shutil.copy(DEFAULT_EXCEL_PATH, backup_path)
                                
                            # Overwrite the default file
                            os.makedirs(os.path.dirname(DEFAULT_EXCEL_PATH), exist_ok=True)
                            with open(DEFAULT_EXCEL_PATH, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                                
                            # Update session state
                            st.session_state['standardized_df'] = std_df
                            st.session_state['raw_file_name'] = uploaded_file.name
                            xls_file = pd.ExcelFile(DEFAULT_EXCEL_PATH)
                            from standardize import find_data_sheet
                            st.session_state['sheet_used'] = find_data_sheet(xls_file)
                            
                            # Overwrite the total_df.csv file in data folder
                            csv_target = os.path.join("data", "total_df.csv")
                            std_df.to_csv(csv_target, index=False)
                            
                            # Also recompute Savi data in background or inline
                            SAVI_EXCEL_PATH = os.path.join("data", "Lista di Savi e Cerchi di potere.xlsx")
                            if os.path.exists(SAVI_EXCEL_PATH):
                                precompute_and_save_savi_data(SAVI_EXCEL_PATH, csv_target)
                            
                            st.session_state['just_uploaded'] = True
                            st.session_state['last_saved_upload'] = upload_key
                            
                        st.success("Database aggiornato con successo! Tutte le schede sono state ricalcolate.")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Errore durante l'aggiornamento (nessuna modifica apportata): {ex}")
            else:
                st.session_state['last_saved_upload'] = None
                
            st.markdown("---")
            st.markdown("### Aggiorna il database dei Savi (Excel)")
            st.write(
                "In questa sezione puoi caricare una nuova versione del file Excel dei Savi per aggiornare la dashboard e ricalcolare i Cerchi di Potere. "
                "Il file caricato verrà verificato. Se la procedura va a buon fine, il file corrente "
                "in `data/Lista di Savi e Cerchi di potere.xlsx` verrà sovrascritto e i dati precalcolati verranno rigenerati automaticamente. "
                "Per sicurezza, una copia di backup del file precedente verrà salvata con un timestamp."
            )
            
            uploaded_savi_file = st.file_uploader(
                "Scegli un file Excel dei Savi (.xlsx, .xls)",
                type=["xlsx", "xls"],
                help="Trascina o seleziona il file Excel dei Savi da importare.",
                key="savi_db_uploader"
            )
            
            if uploaded_savi_file is not None:
                savi_upload_key = f"{uploaded_savi_file.name}_{uploaded_savi_file.size}"
                if st.session_state.get("last_savi_upload") != savi_upload_key:
                    try:
                        with st.spinner("Elaborazione e standardizzazione del file dei Savi..."):
                            # Dry run check
                            test_df = clean_and_pivot_savi(uploaded_savi_file)
                            if test_df.empty:
                                raise ValueError("Il file Excel dei Savi non ha prodotto dati validi.")
                            
                            # Backup and write
                            SAVI_EXCEL_PATH = os.path.join("data", "Lista di Savi e Cerchi di potere.xlsx")
                            if os.path.exists(SAVI_EXCEL_PATH):
                                import shutil
                                from datetime import datetime
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                backup_path = SAVI_EXCEL_PATH.replace(".xlsx", f"_backup_{timestamp}.xlsx")
                                shutil.copy(SAVI_EXCEL_PATH, backup_path)
                                
                            with open(SAVI_EXCEL_PATH, "wb") as f:
                                f.write(uploaded_savi_file.getbuffer())
                                
                            # Recompute Savi data CSVs
                            csv_target = os.path.join("data", "total_df.csv")
                            if os.path.exists(csv_target):
                                precompute_and_save_savi_data(SAVI_EXCEL_PATH, csv_target)
                                
                            st.session_state["last_savi_upload"] = savi_upload_key
                            st.session_state['just_uploaded_savi'] = True
                            
                        st.success("Database dei Savi e Cerchi di Potere aggiornati con successo!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Errore durante l'aggiornamento dei Savi (nessuna modifica apportata): {ex}")
            else:
                st.session_state["last_savi_upload"] = None
            
            st.stop()
            
        preview_df = df.copy()
        
        # Rendering code for Generazione Report
        st.markdown("### Generatore di Report Storici Completi")
        with st.container():
            st.write(
                "Questa sezione consente di scaricare un pacchetto ZIP contenente tutti i dati puliti, "
                "le tabelle in formato Markdown, i grafici interattivi HTML (Plotly), i grafici pronti per la stampa "
                "PNG (Seaborn) e un documento riassuntivo."
            )
            
            # Prepare data for report summary
            overall_families_df = pd.DataFrame({'Famiglia': family_counts_filtered.head(10).index, 'Attestazioni': family_counts_filtered.head(10).values})
            overall_professions_df = pd.DataFrame({'Professione': top_10_p_names, 'Frequenza': profession_counts.head(10).values}) if top_10_p_names else pd.DataFrame()
            
            # Translate families cumulative line chart to structured text narrative
            family_trends_text = ""
            if not top_10_f_filtered.empty:
                for fam in top_10_f_filtered.index:
                    fam_df = filtered_time_df[filtered_time_df['Famiglia'] == fam]
                    fam_years = sorted(fam_df['start_year'].unique())
                    first_yr_app = fam_years[0] if fam_years else "N/D"
                    last_yr_app = fam_years[-1] if fam_years else "N/D"
                    total_c = len(fam_df)
                    
                    year_counts = fam_df['start_year'].value_counts()
                    peak_year = year_counts.idxmax() if not year_counts.empty else "N/D"
                    peak_val = year_counts.max() if not year_counts.empty else 0
                    
                    family_trends_text += f"- **{fam}**:\n"
                    family_trends_text += f"  - Attestazioni totali nel periodo: {total_c}\n"
                    family_trends_text += f"  - Primo anno di comparsa: {first_yr_app} | Ultimo anno di comparsa: {last_yr_app}\n"
                    family_trends_text += f"  - Anno di picco cariche: {peak_year} ({peak_val} cariche)\n"
                    family_trends_text += f"  - Anni con presenza attiva: {', '.join(map(str, fam_years))}\n\n"
            else:
                family_trends_text = "*Nessun trend disponibile.*"
                
            # Translate professions stacked chart to a structured table
            prof_role_table_md = ""
            if prof_role_top10 is not None and not prof_role_top10.empty:
                prof_role_table_md = prof_role_top10.to_markdown()
            else:
                prof_role_table_md = "*Nessuna ripartizione per ruolo disponibile.*"
            
            # 1. Seaborn overall families
            fig_sns_fam, ax_sns_fam = plt.subplots(figsize=(10, 5))
            sns.set_theme(style="whitegrid", palette="pastel")
            sns.barplot(x=top_10_f_filtered.head(10).values, y=top_10_f_filtered.head(10).index, ax=ax_sns_fam, hue=top_10_f_filtered.head(10).index, legend=False)
            ax_sns_fam.set_title(f"Top 10 Famiglie ({start_yr}-{end_yr})")
            ax_sns_fam.set_xlabel("Attestazioni")
            ax_sns_fam.set_ylabel("Famiglia")
            plt.tight_layout()
            buf_sns_fam = io.BytesIO()
            fig_sns_fam.savefig(buf_sns_fam, format='png', dpi=300)
            plt.close(fig_sns_fam)
            
            # 2. Seaborn cumulative families
            buf_sns_cum = io.BytesIO()
            if cumulative_melted is not None:
                fig_sns_cum, ax_sns_cum = plt.subplots(figsize=(10, 5))
                sns.set_theme(style="whitegrid", palette="pastel")
                sns.lineplot(data=cumulative_melted, x='Anno', y='Conteggio Cumulativo', hue='Famiglia', ax=ax_sns_cum)
                ax_sns_cum.set_title(f"Conteggio cumulativo delle occorrenze ({start_yr}-{end_yr})")
                ax_sns_cum.set_xlabel("Anno")
                ax_sns_cum.set_ylabel("Conteggio Cumulativo")
                plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
                plt.tight_layout()
                fig_sns_cum.savefig(buf_sns_cum, format='png', dpi=300)
                plt.close(fig_sns_cum)
                
            # 3. Seaborn Professions
            fig_sns_prof, ax_sns_prof = plt.subplots(figsize=(10, 6))
            if prof_role_top10 is not None and not prof_role_top10.empty:
                prof_role_top10.plot(kind='bar', stacked=True, ax=ax_sns_prof, colormap="Pastel1")
                ax_sns_prof.set_title("Top 10 Professioni per Ruolo")
                ax_sns_prof.set_xlabel("Professione")
                ax_sns_prof.set_ylabel("Frequenza")
                plt.xticks(rotation=45, ha='right')
            else:
                ax_sns_prof.text(0.5, 0.5, "Nessun dato", ha='center', va='center')
            plt.tight_layout()
            buf_sns_prof = io.BytesIO()
            fig_sns_prof.savefig(buf_sns_prof, format='png', dpi=300)
            plt.close(fig_sns_prof)
            
            # 4. Seaborn Roles Stacked
            fig_sns_roles, ax_sns_roles = plt.subplots(figsize=(10, 6))
            role_distribution.plot(kind='bar', stacked=True, ax=ax_sns_roles, colormap="Pastel1")
            ax_sns_roles.set_title("Distribuzione Ruoli per le Famiglie Principali")
            ax_sns_roles.set_xlabel("Famiglia")
            ax_sns_roles.set_ylabel("Numero di Cariche")
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            buf_sns_roles = io.BytesIO()
            fig_sns_roles.savefig(buf_sns_roles, format='png', dpi=300)
            plt.close(fig_sns_roles)
            
            # Generate Plotly HTML strings
            html_fam = fig_cumulative.to_html(full_html=True, include_plotlyjs='cdn') if fig_cumulative is not None else ""
            html_prof = fig_prof.to_html(full_html=True, include_plotlyjs='cdn') if fig_prof is not None else ""
            html_roles = fig_roles.to_html(full_html=True, include_plotlyjs='cdn')
            html_ind_timeline = fig_timeline.to_html(full_html=True, include_plotlyjs='cdn') if fig_timeline is not None else ""
            
            # Create Markdown text summary
            now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            
            md_summary = f"""# Report di Analisi: Cariche Politiche del Comune di Pisa (1344-1392)
Generato il: {now_str}
File sorgente: {st.session_state['raw_file_name']}
Foglio Excel rilevato: {st.session_state['sheet_used']}
Filtro applicato: Nessuno (Tutti i Ruoli)

## Informazioni Generali
- **Righe totali processate (melted)**: {total_records}
- **Mandati totali**: {total_mandates}
- **Esponenti politici rilevati**: {unique_names}
- **Famiglie uniche**: {unique_families}
- **Professioni uniche**: {unique_professions}

## 1. Trend Temporale della Rappresentazione Familiare ({start_yr}-{end_yr})
Le 10 famiglie più rappresentate all'interno del database:

{overall_families_df.to_markdown(index=False)}

### Analisi dettagliata dell'attività e crescita delle famiglie (Trend temporale):
{family_trends_text}

## 2. Prevalenza Professionale per Ruolo
Le 10 professioni/corporazioni più attive nel periodo (complessivo):

{overall_professions_df.to_markdown(index=False) if not overall_professions_df.empty else "Nessun dato."}

### Ripartizione dei ruoli politici per ciascuna professione principale:
{prof_role_table_md}

## 3. Distribuzione delle Cariche per le Famiglie Principali
Distribuzione dei ruoli per le 10 famiglie più frequenti (complessivo):

{role_distribution.to_markdown()}

## 4. Statistiche Socio-Professionali
- **Tasso di identificazione delle professioni**: {pct_identified:.1f}% ({identified_prof_count} cariche su {total_entries} totali)
- **Professioni non identificate/mancanti**: {100.0 - pct_identified:.1f}% ({total_entries - identified_prof_count} cariche)
"""
            if priori_identified > 0:
                md_summary += f"\n- **Principali professioni tra i Priori (Identificati, top 3 di top 10)**:\n"
                for idx, (prof, val) in enumerate(priori_top.items()):
                    md_summary += f"  {idx+1}. {prof}: {val} attestazioni ({val/priori_identified:.1%})\n"
            if anz1_identified > 0:
                md_summary += f"\n- **Principali professioni tra gli Anziani #1 (Identificati, top 3 di top 10)**:\n"
                for idx, (prof, val) in enumerate(anz1_top.items()):
                    md_summary += f"  {idx+1}. {prof}: {val} attestazioni ({val/anz1_identified:.1%})\n"
            if anz2_identified > 0:
                md_summary += f"\n- **Principali professioni tra gli Anziani #2 (Identificati, top 3 di top 10)**:\n"
                for idx, (prof, val) in enumerate(anz2_top.items()):
                    md_summary += f"  {idx+1}. {prof}: {val} attestazioni ({val/anz2_identified:.1%})\n"

            # Add the selected family details to the report
            if selected_family and not family_members_df.empty:
                md_summary += f"""
## 5. Dettaglio Famiglia selezionata ({selected_family}, arco temporale: {start_yr}-{end_yr})
- **Partecipazioni Totali**: {len(family_members_df)}
- **Individui Distinti**: {family_members_df["nome"].nunique()}

### Elenco cronologico delle partecipazioni al consiglio:

{table_display.to_markdown(index=False) if not table_display.empty else "Nessuna partecipazione registrata in questo arco temporale."}

#### Distribuzione dei Ruoli ({selected_family})
"""
                if not family_role_counts.empty:
                    for r, cnt in family_role_counts.items():
                        md_summary += f"- {r}: {cnt} cariche ({cnt/total_family_roles:.1%})\n"
                else:
                    md_summary += "Nessun ruolo registrato.\n"
                    
                md_summary += f"\n#### Distribuzione dei Quartieri ({selected_family})\n"
                if not family_quartiere_counts.empty:
                    for q, cnt in family_quartiere_counts.items():
                        md_summary += f"- {q}: {cnt} attestazioni ({cnt/total_family_q:.1%})\n"
                else:
                    md_summary += "Nessun quartiere registrato.\n"

            # Add the selected individual details to the report
            if selected_individual and not ind_df.empty:
                md_summary += f"""
## 6. Dettaglio Politico selezionato ({selected_individual}, arco temporale: {start_yr}-{end_yr})
- **Professione registrata**: {ind_prof_str}
- **Numero di partecipazioni nel periodo**: {len(ind_df)}

### Elenco cronologico delle cariche e periodi:
"""
                for idx, row in ind_df.iterrows():
                    q_suffix = f" ({row['quartiere']})" if pd.notna(row['quartiere']) else ""
                    md_summary += f"- Mandato #{row['numero mandato']}: **{row['ruolo']}**{q_suffix} nel periodo {row['anno']} ({row['mesi']})\n"

            # Compute turnover details for the report
            rep_selected_roles = []
            cb_anz1_state = st.session_state.get("cb_turnover_anz1", True)
            cb_anz2_state = st.session_state.get("cb_turnover_anz2", True)
            cb_priore_state = st.session_state.get("cb_turnover_priore", False)
            cb_notaio_state = st.session_state.get("cb_turnover_notaio", False)
            cb_canc_state = st.session_state.get("cb_turnover_canc", False)
            
            if cb_anz1_state: rep_selected_roles.append("anziano #1")
            if cb_anz2_state: rep_selected_roles.append("anziano #2")
            if cb_priore_state: rep_selected_roles.append("priore")
            if cb_notaio_state: rep_selected_roles.append("notaio anziani")
            if cb_canc_state: rep_selected_roles.append("canc. maior")
            
            df_councils = df[['numero mandato', 'anno', 'mesi']].dropna(subset=['anno', 'mesi']).drop_duplicates().sort_values(by='numero mandato')
            councils_list = []
            for _, row in df_councils.iterrows():
                c_id = f"{row['numero mandato']}. {row['anno']} ({row['mesi']})"
                councils_list.append(c_id)
                
            if councils_list and rep_selected_roles:
                start_c = st.session_state.get("turnover_start_council", councils_list[0])
                if start_c not in councils_list:
                    start_c = councils_list[0]
                start_idx = councils_list.index(start_c)
                
                end_options = councils_list[start_idx:]
                end_c = st.session_state.get("turnover_end_council", end_options[-1])
                if end_c not in end_options:
                    end_c = end_options[-1]
                    
                start_m = int(start_c.split('.')[0])
                end_m = int(end_c.split('.')[0])
                
                rep_analysis_unit = st.session_state.get("turnover_analysis_unit", "Individui (singoli politici)")
                unit_mapping = {
                    "Individui (singoli politici)": "nome",
                    "Famiglie (cognomi/casate)": "Famiglia",
                    "Quartieri (provenienza geografica)": "quartiere"
                }
                rep_column_name = unit_mapping.get(rep_analysis_unit, "nome")
                
                t_metrics = compute_turnover_metrics(df, rep_selected_roles, start_m, end_m, column_name=rep_column_name)
                if t_metrics:
                    avg_t = t_metrics['avg_turnover']
                    avg_s = t_metrics['avg_steps']
                    pct_o = t_metrics['pct_overlap_start']
                    shared_m = t_metrics['shared_members']
                    
                    unit_names_pl = {
                        "nome": {"plural": "politici", "shared": "membri"},
                        "Famiglia": {"plural": "famiglie", "shared": "famiglie"},
                        "quartiere": {"plural": "quartieri", "shared": "quartieri"}
                    }
                    u_names = unit_names_pl[rep_column_name]
                    
                    if avg_s is not None:
                        complete_t_str = f"{avg_s:.1f} Consigli (~{avg_s*2:.1f} Mesi)"
                    else:
                        complete_t_str = "Nessun ricambio completo rilevato"
                        
                    md_summary += f"""
## 7. Analisi del Ricambio dei Gruppi ({start_c} a {end_c})
- **Unità di analisi**: {rep_analysis_unit}
- **Ruoli analizzati**: {", ".join(rep_selected_roles)}
- **Ricambio Medio Consecutivo**: {avg_t:.1f}%
- **Tempo per Ricambio Completo**: {complete_t_str}
- **Percentuale di Sovrapposizione Estremi**: {pct_o:.1f}% ({len(shared_m)} {u_names['shared']} in comune)
- **Elementi condivisi tra inizio e fine**: {", ".join(sorted(list(shared_m))) if shared_m else "Nessuno"}
"""

            # Add general rankings to the report summary
            md_summary += f"""
## 8. Classifiche Generali del Database
Le prime 10 posizioni per ciascuna variabile chiave (complessivo, intero database):

### Top 10 Politici (per numero di cariche)
{pd.DataFrame({'Politico': df['nome'].value_counts().head(10).index, 'Cariche': df['nome'].value_counts().head(10).values}).to_markdown(index=False)}

### Top 10 Famiglie
{pd.DataFrame({'Famiglia': df['Famiglia'].value_counts().head(10).index, 'Cariche': df['Famiglia'].value_counts().head(10).values}).to_markdown(index=False)}

### Top 10 Quartieri
{pd.DataFrame({'Quartiere': df['quartiere'].value_counts().head(10).index, 'Cariche': df['quartiere'].value_counts().head(10).values}).to_markdown(index=False)}

### Top 10 Professioni
{pd.DataFrame({'Professione': df['Professione'].value_counts().head(10).index, 'Cariche': df['Professione'].value_counts().head(10).values}).to_markdown(index=False) if not df['Professione'].dropna().empty else "*Nessun dato sulle professioni.*"}
"""

            md_summary += "\n---\n*Fine del report generato automaticamente.*\n"
            
            prompt_md_content = """# Istruzioni per l'Assistente AI (Prompt di Sistema)

Sei un esperto Data Scientist specializzato in Analisi Storica e Umanistica Digitale (Digital Humanities), al servizio di uno studente di storia medievale italiana. Il tuo obiettivo è assistere lo studente nell'analisi e interpretazione dei dati relativi ai membri del consiglio (Anziani, Priori, ecc.) del Comune di Pisa nel periodo medievale (1344-1392).

Hai a disposizione due allegati principali:
1. `dati_standardizzati.csv`: un dataframe strutturato e standardizzato contenente i record dei mandati e degli esponenti politici.
2. `report_summary.md`: un report in formato markdown che riassume le analisi globali pre-computate dall'applicazione.

## 1. STRUTTURA DEI DATI E VARIABILI DISPONIBILI
Nel file `dati_standardizzati.csv` troverai le seguenti colonne standardizzate e pulite:
- `numero mandato`: Identificativo incrementale del consiglio storico.
- `anno`: Anno o periodo in formato testuale (es. "1345").
- `mesi`: Mesi di durata del mandato (es. "marzo-aprile").
- `nome`: Nome completo standardizzato dell'esponente politico.
- `ruolo`: Ruolo politico ricoperto (es. 'anziano #1', 'anziano #2', 'priore', 'notaio anziani', 'canc. maior').
- `quartiere`: Il quartiere di Pisa associato all'esponente (es. 'Mezzo', 'Ponte', 'Fuoriporta', 'Kinzica').
- `Famiglia`: Il cognome o casata dell'esponente (derivato dalla colonna note/famiglia).
- `Professione`: La categoria professionale o corporazione associata (derivata dalla colonna altra nota/professione).
- `data inizio mandato` / `data fine mandato`: Date stimate del mandato.

## 2. COMPORTAMENTO E METODOLOGIA DI ANALISI
- Comportati come un consulente metodologico e analitico. Traduci le domande storiche dello studente in query di dati, grafici o indicatori quantitativi.
- Combina la sensibilità storica (es. contestualizzazione politica, importanza delle parentele, fazioni nobiliari o popolari) con il rigore statistico (frequenze, tassi di ricambio, analisi delle reti).
- Effettua analisi autonome scrivendo ed eseguendo codice Python se necessario. Riporta sempre le conclusioni storiche e il codice utilizzato per la trasparenza.

## 3. GUIDA ALLE DASHBOARD DELL'APPLICAZIONE STREAMLIT
L'applicazione Streamlit usata per esplorare questi dati ha 5 dashboard principali. Se lo studente ti chiede informazioni che possono essere visualizzate direttamente nell'app, digli esattamente come comportarsi (quali filtri impostare o dove cliccare). Di seguito trovi i dettagli tecnici e i criteri di implementazione di ogni dashboard:

### A. Dashboard "Famiglie e Individui"
- **Cosa fa**: Analizza la presenza delle famiglie nel tempo e permette di fare un drill-down sui singoli politici.
- **Logica e Codice**:
  - Calcola il trend temporale cumulativo delle occorrenze delle top 10 famiglie:
    ```python
    df_top_f = filtered_time_df[filtered_time_df['Famiglia'].isin(top_10_f_names)]
    occ_by_year = df_top_f.groupby(['start_year', 'Famiglia']).size().unstack(fill_value=0)
    cumulative_counts = occ_by_year.cumsum()
    ```
  - Permette di selezionare una famiglia da un menu a tendina per vedere la lista delle cariche e la distribuzione dei ruoli e quartieri.
  - Consente di scegliere un singolo esponente per vedere la sua cronologia testuale di partecipazioni.
- **Istruzioni per l'utente**: "Vai alla scheda 'Famiglie e Individui', usa lo slider temporale per scegliere l'arco di anni, seleziona la famiglia dal menu a tendina 'Seleziona una famiglia...' e poi seleziona l'esponente desiderato in 'Seleziona un esponente...' per vederne la cronologia dettagliata."

### B. Dashboard "Categorie Professionali"
- **Cosa fa**: Mostra la rappresentanza delle corporazioni/professioni per i vari ruoli.
- **Logica e Codice**:
  - Genera un istogramma a barre sovrapposte per le top 10 professioni filtrate in base ai ruoli selezionati tramite checkbox (`anziano #1`, `anziano #2`, `priore`, ecc.):
    ```python
    prof_role_counts = df_filtered.groupby(['Professione', 'ruolo']).size().unstack(fill_value=0)
    ```
  - Mostra i tassi di identificazione e le top 3 professioni per ciascun ruolo.
- **Istruzioni per l'utente**: "Vai alla scheda 'Categorie Professionali', spunta o deseleziona i ruoli tramite i checkbox in alto (es. spunta 'Priore' e deseleziona gli altri) e leggi la tabella o il grafico a barre per vedere la ripartizione."

### C. Dashboard "Distribuzione Cariche"
- **Cosa fa**: Mostra l'equilibrio dei ruoli tra le 10 famiglie più rappresentate.
- **Logica e Codice**:
  - Raggruppa i dati per Famiglia e Ruolo per produrre un grafico a barre impilate.
- **Istruzioni per l'utente**: "Vai alla scheda 'Distribuzione Cariche' per visualizzare il grafico a barre sovrapposte e la tabella dei dati per verificare quali famiglie controllavano determinati ruoli istituzionali."

### D. Dashboard "Ricambio nel Tempo" (Turnover)
- **Cosa fa**: Calcola la mobilità politica e la stabilità del gruppo dirigente.
- **Logica e Codice**:
  - **Ricambio Medio Consecutivo**: Per ogni coppia di mandati consecutivi, calcola quanti membri del secondo mandato non erano presenti nel primo, rapportato al totale del secondo mandato:
    ```python
    new_members = members_next - members_curr
    turnover_rate = len(new_members) / len(members_next)
    ```
  - **Tempo per Ricambio Completo (in Mandati)**: Numero medio di mandati consecutivi necessari per far sì che l'intersezione tra il consiglio di partenza e quello corrente sia vuota (0 membri in comune).
  - **Percentuale di Sovrapposizione Estremi**: La percentuale di membri del consiglio iniziale che si ritrova anche nel consiglio finale selezionato.
- **Istruzioni per l'utente**: "Vai alla scheda 'Ricambio nel Tempo', seleziona se vuoi analizzare Individui, Famiglie o Quartieri, spunta i ruoli che ti interessano, imposta il consiglio di inizio e fine tramite i due menu a tendina, e guarda la griglia dei KPI per i risultati."

### E. Dashboard "Classifiche Personalizzate"
- **Cosa fa**: Genera graduatorie dinamiche (Top N) per le variabili chiave.
- **Logica e Codice**:
  - Filtra il dataset per l'arco temporale selezionato, calcola i conteggi (`value_counts()`), limita il risultato alle prime N righe selezionate dallo slider e fornisce il download in formato CSV.
- **Istruzioni per l'utente**: "Vai alla scheda 'Classifiche Personalizzate', scegli la variabile (es. 'Professione'), imposta il limite N tramite lo slider e imposta gli anni desiderati nel secondo slider temporale."

## 4. PROPOSTE DI ANALISI AVANZATE (AUTONOME CON CODICE PYTHON)
Se lo studente ha dubbi o desidera analisi più profonde, puoi scrivere ed eseguire script Python sui dati del file `dati_standardizzati.csv`. Ecco alcune analisi consigliate:
1. **Analisi di Rete (Network Analysis)**: Studiare le co-occorrenze di famiglie o quartieri all'interno dello stesso mandato per individuare fazioni storiche o alleanze strutturali.
2. **Carriere Politiche (Career Paths)**: Calcolare la sequenza temporale dei ruoli ricoperti dagli individui (es. si partiva come Anziano per poi diventare Priore? Qual era la durata media di una carriera politica?).
3. **Concentrazione del Potere (Indice di Gini / Herfindahl-Hirschman)**: Misurare quantitativamente se la distribuzione delle cariche tra le famiglie o i quartieri fosse concentrata o diffusa, e come questo indice varia nei diversi decenni (es. prima e dopo la rivoluzione del 1369 o il cambio di regime).
4. **Analisi Geografica**: Analizzare la provenienza geografica (quartieri) in relazione ai ruoli ricoperti per vedere se esistevano quartieri storicamente associati a determinate cariche o corporazioni.

Usa sempre un tono rigoroso, accademico e collaborativo. Buon lavoro!"""
            
            # Build Zip archive in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr("dati/total_df_cleaned.csv", preview_df.to_csv(index=False))
                
                excel_buf_in_zip = io.BytesIO()
                with pd.ExcelWriter(excel_buf_in_zip, engine='openpyxl') as writer:
                    preview_df.to_excel(writer, index=False)
                zip_file.writestr("dati/total_df_cleaned.xlsx", excel_buf_in_zip.getvalue())
                
                # Markdown summary
                zip_file.writestr("report_summary.md", md_summary)
                
                # Seaborn plots (PNG)
                zip_file.writestr("grafici_seaborn/top_famiglie_occorrenze.png", buf_sns_fam.getvalue())
                if buf_sns_cum.getvalue():
                    zip_file.writestr("grafici_seaborn/top_famiglie_cumulativo.png", buf_sns_cum.getvalue())
                zip_file.writestr("grafici_seaborn/top_professioni.png", buf_sns_prof.getvalue())
                zip_file.writestr("grafici_seaborn/distribuzione_ruoli.png", buf_sns_roles.getvalue())
                
                # Plotly plots (HTML)
                if html_fam:
                    zip_file.writestr("grafici_interactive_plotly/top_famiglie_cumulativo.html", html_fam)
                if html_prof:
                    zip_file.writestr("grafici_interactive_plotly/top_professioni.html", html_prof)
                zip_file.writestr("grafici_interactive_plotly/distribuzione_ruoli.html", html_roles)
                if html_ind_timeline:
                    zip_file.writestr("grafici_interactive_plotly/timeline_individuale.html", html_ind_timeline)
                    
            # Build AI Zip archive in memory
            ai_zip_buffer = io.BytesIO()
            with zipfile.ZipFile(ai_zip_buffer, 'w', zipfile.ZIP_DEFLATED) as ai_zip_file:
                ai_zip_file.writestr("dati_standardizzati.csv", preview_df.to_csv(index=False))
                ai_zip_file.writestr("report_summary.md", md_summary)
                ai_zip_file.writestr("prompt.md", prompt_md_content)
                
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    label="Scarica Report Completo",
                    data=zip_buffer.getvalue(),
                    file_name="Report_Cariche_Pisa.zip",
                    mime="application/zip",
                    width='stretch'
                )
            with col_dl2:
                st.download_button(
                    label="Scarica contesto per AI",
                    data=ai_zip_buffer.getvalue(),
                    file_name="Contesto_AI_Pisa.zip",
                    mime="application/zip",
                    width='stretch'
                )
else:
    st.info("Carica un file Excel per iniziare a elaborare i dati e visualizzare il pannello di analisi.")
