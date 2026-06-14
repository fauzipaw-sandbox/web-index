import streamlit as st
import pandas as pd
import plotly.express as px
import os
import io
import datetime
import gc
import re

st.set_page_config(page_title="Network Loss Impact Analyzer", layout="wide")

# --- INJEKSI KUSTOM CSS ---
st.markdown("""
<style>
    .stApp > header { background-color: transparent; border-top: 5px solid #EC2028; }
    [data-testid="stMetric"] { background-color: #ffffff; padding: 15px 20px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08); transition: transform 0.2s ease-in-out; }
    [data-testid="stMetric"]:hover { transform: translateY(-5px); }
    [data-testid="column"]:nth-child(1) [data-testid="stMetric"] { border-left: 5px solid #28a745 !important; }
    [data-testid="column"]:nth-child(1) [data-testid="stMetricValue"] { color: #28a745 !important; }
    [data-testid="column"]:nth-child(2) [data-testid="stMetric"] { border-left: 5px solid #EC2028 !important; }
    [data-testid="column"]:nth-child(2) [data-testid="stMetricValue"] { color: #EC2028 !important; }
    [data-testid="column"]:nth-child(3) [data-testid="stMetric"] { border-left: 5px solid #0056b3 !important; }
    [data-testid="column"]:nth-child(3) [data-testid="stMetricValue"] { color: #0056b3 !important; }
    [data-testid="stFileUploadDropzone"] { border: 2px dashed #EC2028; border-radius: 10px; background-color: #FCF4F4; }
</style>
""", unsafe_allow_html=True)

# --- HEADER LOGO ---
col_title, col_logo = st.columns([15, 1])
with col_title:
    st.markdown("<h1 style='margin-top: -15px;'>💸📉 Network Loss Impact Analyzer</h1>", unsafe_allow_html=True)
with col_logo:
    if os.path.exists("logo.png"): st.image("logo.png", width=60)
    else: st.markdown("<h1 style='margin-top: -15px; color: #EC2028; text-align: right;'>🔴</h1>", unsafe_allow_html=True)

st.write("Pantau Aktual, Potensi (Gain), dan *Lost* performa site secara real-time (Pure Local Memory Mode).")

def clean_column_names(df):
    cols = df.columns.astype(str).str.lower()
    cols = cols.str.replace(' ', '_')
    cols = cols.str.replace(r'[^a-zA-Z0-9_]', '', regex=True)
    return cols

st.divider()

# --- 1. PANEL UPLOAD LANGSUNG (PENGGANTI DATABASE) ---
st.write("### 📂 Upload Data Sumber")
col_up1, col_up2, col_up3 = st.columns(3)

with col_up1:
    file_rev = st.file_uploader("📦 1. Data Revenue (Bisa Banyak File)", type=["csv", "xlsx", "xls"], accept_multiple_files=True)
with col_up2:
    file_avail = st.file_uploader("📡 2. Data Availability / UME", type=["csv", "xlsx", "xls"], accept_multiple_files=True)
with col_up3:
    file_dapot = st.file_uploader("📋 3. Data Dapot Master (Wajib)", type=["csv", "xlsx", "xls"])

# Cek Apakah file sudah diupload semua
if not file_rev or not file_avail or not file_dapot:
    st.info("👋 Halo Bos! Silakan upload ketiga jenis data di atas terlebih dahulu untuk memulai analisis area secara aman.")
    st.stop()

# --- 2. PROSES DATA REAKTIF DI RAM ---
try:
    with St.spinner("Sedang memproses data langsung di memori lokal..."):
        # A. Baca Data Dapot Master
        df_dapot = pd.read_csv(file_dapot) if file_dapot.name.endswith('.csv') else pd.read_excel(file_dapot)
        df_dapot.columns = clean_column_names(df_dapot)
        if 'site_id' in df_dapot.columns: 
            df_dapot['site_id'] = df_dapot['site_id'].astype(str).str.strip().str.upper()
        
        col_name = [c for c in df_dapot.columns if 'name' in c.lower()][0] if any('name' in c.lower() for c in df_dapot.columns) else 'site_id'
        name_mapping = dict(zip(df_dapot['site_id'], df_dapot[col_name].astype(str)))
        
        # Mapping Radar Anakan dari Dapot
        site_mapping_temp = {}
        col_simpul = [c for c in df_dapot.columns if ('simpul' in c.lower() or 'hub' in c.lower() or 'induk' in c.lower()) and 'jumlah' not in c.lower()]
        for c_simpul in col_simpul:
            for _, row in df_dapot.dropna(subset=[c_simpul]).iterrows():
                parent_raw = str(row[c_simpul]).upper()
                child_site = str(row['site_id']).strip().upper()
                match = re.search(r'([A-Z]{3}\d{3})', parent_raw)
                if match:
                    parent_code = match.group(1)
                    if parent_code != child_site:
                        if parent_code not in site_mapping_temp: site_mapping_temp[parent_code] = set()
                        site_mapping_temp[parent_code].add(child_site)

        col_anakan = [c for c in df_dapot.columns if 'anakan' in c.lower() and 'jumlah' not in c.lower()]
        for c_anak in col_anakan:
            for _, row in df_dapot.dropna(subset=[c_anak]).iterrows():
                parent_site = str(row['site_id']).strip().upper()
                anak_raw = str(row[c_anak]).upper()
                anak_list = [x.strip() for x in anak_raw.split(',')]
                if parent_site not in site_mapping_temp: site_mapping_temp[parent_site] = set()
                for a in anak_list:
                    match = re.search(r'([A-Z]{3}\d{3})', a)
                    if match: site_mapping_temp[parent_site].add(match.group(1))
        site_mapping = {k: list(v) for k, v in site_mapping_temp.items()}

        # B. Baca & Gabung Data Revenue
        dfs_rev = [pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f) for f in file_rev]
        df_rev_raw = pd.concat(dfs_rev, ignore_index=True)
        df_rev_raw.columns = clean_column_names(df_rev_raw)
        
        rev_date = [c for c in df_rev_raw.columns if 'periode' in c.lower() or 'tanggal' in c.lower() or 'date' in c.lower()][0]
        rev_site = [c for c in df_rev_raw.columns if 'site' in c.lower()][0]
        rev_rev = [c for c in df_rev_raw.columns if 'revenue' in c.lower()][0]
        rev_pay = [c for c in df_rev_raw.columns if 'payload' in c.lower()][0]
        
        df_rev = pd.DataFrame()
        df_rev['Date'] = pd.to_datetime(df_rev_raw[rev_date], errors='coerce').dt.date
        df_rev['Site_ID'] = df_rev_raw[rev_site].astype(str).str.strip().str.upper()
        df_rev['Actual_Revenue'] = pd.to_numeric(df_rev_raw[rev_rev], errors='coerce').fillna(0).astype('float32')
        df_rev['Actual_Payload'] = (pd.to_numeric(df_rev_raw[rev_pay], errors='coerce').fillna(0) / 1024).astype('float32')
        df_rev = df_rev.drop_duplicates(subset=['Site_ID', 'Date'], keep='last')
        
        del df_rev_raw

        # C. Baca & Gabung Data Availability
        dfs_avail = []
        for f in file_avail:
            if f.name.endswith('.csv'): df_t = pd.read_csv(f)
            else:
                xls_avail = pd.ExcelFile(f)
                sheet_target = xls_avail.sheet_names[0]
                for sheet in xls_avail.sheet_names:
                    df_cek = pd.read_excel(xls_avail, sheet_name=sheet, nrows=1)
                    if any('Begin Time' in col or 'begin' in str(col).lower() for col in df_cek.columns):
                        sheet_target = sheet
                        break
                df_t = pd.read_excel(xls_avail, sheet_name=sheet_target)
            dfs_avail.append(df_t)
            
        df_avail_raw = pd.concat(dfs_avail, ignore_index=True)
        df_avail_raw.columns = clean_column_names(df_avail_raw)
        
        avail_date = [c for c in df_avail_raw.columns if 'begin' in c.lower() or 'time' in c.lower() or 'date' in c.lower()][0]
        avail_site = 'managed_element' if 'managed_element' in df_avail_raw.columns else [c for c in df_avail_raw.columns if ('element' in c.lower() or 'site' in c.lower()) and 'id' not in c.lower()][0]
        avail_val = [c for c in df_avail_raw.columns if 'availability' in c.lower() or 'avail' in c.lower()][0]
        loss_val_list = [c for c in df_avail_raw.columns if 'loss' in c.lower()]
        avail_loss = loss_val_list[0] if loss_val_list else None
        
        df_avail = pd.DataFrame()
        df_avail['Date'] = pd.to_datetime(df_avail_raw[avail_date], errors='coerce').dt.date
        df_avail['Site_ID'] = df_avail_raw[avail_site].astype(str).str.extract(r'([A-Z]{3}\d{3})')
        df_avail['Availability'] = pd.to_numeric(df_avail_raw[avail_val], errors='coerce').fillna(0.0).astype('float32')
        if avail_loss: df_avail['Packet_Loss'] = pd.to_numeric(df_avail_raw[avail_loss], errors='coerce').fillna(1.0).astype('float32')
        else: df_avail['Packet_Loss'] = 1.0
        df_avail = df_avail.drop_duplicates(subset=['Site_ID', 'Date'], keep='last')
        
        del df_avail_raw
        gc.collect()

        # D. Outer Join Data
        df_merged = pd.merge(df_rev, df_avail, on=['Site_ID', 'Date'], how='outer')
        df_merged['Actual_Revenue'] = df_merged['Actual_Revenue'].fillna(0)
        df_merged['Actual_Payload'] = df_merged['Actual_Payload'].fillna(0)
        df_merged['Availability'] = df_merged['Availability'].fillna(0.0)
        df_merged['Packet_Loss'] = df_merged['Packet_Loss'].fillna(1.0)
        df_merged = df_merged.dropna(subset=['Date'])
        
        # Tempel Meta Data dari Dapot Master
        if not df_dapot.empty:
            dept_col = [c for c in df_dapot.columns if 'nop' in c.lower() or 'dept' in c.lower() or 'departemen' in c.lower()]
            dept_col = dept_col[0] if dept_col else None
            kab_col = [c for c in df_dapot.columns if 'kab' in c.lower() or 'kota' in c.lower()]
            kab_col = kab_col[0] if kab_col else None
            kec_col = [c for c in df_dapot.columns if 'kec' in c.lower()]
            kec_col = kec_col[0] if kec_col else None
            
            extra_cols = ['site_name', 'site_class', 'pln__non_pln', 'power_classification', 'site_simpul', 'hub_site']
            cols_to_merge = ['site_id'] + [c for c in extra_cols if c in df_dapot.columns]
            if dept_col: cols_to_merge.append(dept_col)
            if kab_col: cols_to_merge.append(kab_col)
            if kec_col: cols_to_merge.append(kec_col)
            
            df_dapot_u = df_dapot[cols_to_merge].drop_duplicates(subset=['site_id'], keep='last')
            df_merged = pd.merge(df_merged, df_dapot_u, left_on='Site_ID', right_on='site_id', how='left')
            
            if dept_col: df_merged.rename(columns={dept_col: 'Departemen'}, inplace=True)
            if kab_col: df_merged.rename(columns={kab_col: 'Kabupaten'}, inplace=True)
            if kec_col: df_merged.rename(columns={kec_col: 'Kecamatan'}, inplace=True)

        df_merged['Departemen'] = df_merged.get('Departemen', pd.Series('UNKNOWN', index=df_merged.index)).fillna('UNKNOWN').astype(str).str.upper()
        df_merged['Kabupaten'] = df_merged.get('Kabupaten', pd.Series('UNKNOWN', index=df_merged.index)).fillna('UNKNOWN').astype(str).str.upper()
        df_merged['Kecamatan'] = df_merged.get('Kecamatan', pd.Series('UNKNOWN', index=df_merged.index)).fillna('UNKNOWN').astype(str).str.upper()

        # E. Auto Correction Scale
        if df_merged['Availability'].max() > 1.0: df_merged['Availability'] = df_merged['Availability'] / 100.0
        if df_merged['Packet_Loss'].max() > 1.0: df_merged['Packet_Loss'] = df_merged['Packet_Loss'] / 100.0
        df_merged['Availability'] = df_merged['Availability'].clip(0.0, 1.0)
        df_merged['Packet_Loss'] = df_merged['Packet_Loss'].clip(0.0, 1.0)

        # F. Hitung Matematika Cerdas (Healthy Baseline Proxy)
        healthy_mask = (df_merged['Availability'] >= 0.95) & (df_merged['Packet_Loss'] <= 0.05) & (df_merged['Actual_Revenue'] > 0)
        baseline_rev = df_merged[healthy_mask].groupby('Site_ID')['Actual_Revenue'].mean()
        baseline_pay = df_merged[healthy_mask].groupby('Site_ID')['Actual_Payload'].mean()
        fallback_rev = df_merged[df_merged['Actual_Revenue'] > 0].groupby('Site_ID')['Actual_Revenue'].mean()
        fallback_pay = df_merged[df_merged['Actual_Payload'] > 0].groupby('Site_ID')['Actual_Payload'].mean()

        df_merged['Potential_Revenue'] = df_merged['Actual_Revenue']
        df_merged['Potential_Payload'] = df_merged['Actual_Payload']
        
        mask_active_rev = (df_merged['Availability'] > 0) & (df_merged['Actual_Revenue'] > 0)
        df_merged.loc[mask_active_rev, 'Potential_Revenue'] = df_merged['Actual_Revenue'] / (df_merged['Availability'] * (1 - df_merged['Packet_Loss']))
        mask_active_pay = (df_merged['Availability'] > 0) & (df_merged['Actual_Payload'] > 0)
        df_merged.loc[mask_active_pay, 'Potential_Payload'] = df_merged['Actual_Payload'] / (df_merged['Availability'] * (1 - df_merged['Packet_Loss']))
        
        mask_degraded = (df_merged['Availability'] < 0.95) | (df_merged['Packet_Loss'] > 0.05)
        mapped_rev = df_merged['Site_ID'].map(baseline_rev).fillna(df_merged['Site_ID'].map(fallback_rev)).fillna(0)
        mapped_pay = df_merged['Site_ID'].map(baseline_pay).fillna(df_merged['Site_ID'].map(fallback_pay)).fillna(0)
        df_merged.loc[mask_degraded, 'Potential_Revenue'] = df_merged.loc[mask_degraded, 'Potential_Revenue'].combine(mapped_rev, max)
        df_merged.loc[mask_degraded, 'Potential_Payload'] = df_merged.loc[mask_degraded, 'Potential_Payload'].combine(mapped_pay, max)

        df_merged['Lost_Revenue'] = df_merged['Actual_Revenue'] - df_merged['Potential_Revenue']
        df_merged['Lost_Payload'] = df_merged['Actual_Payload'] - df_merged['Potential_Payload']
        df_merged['Availability_Pct'] = df_merged['Availability'] * 100
        df_merged['Packet_Loss_Pct'] = df_merged['Packet_Loss'] * 100

except Exception as e:
    st.error(f"Gagal memproses file upload. Pastikan format kolom sesuai. Log: {e}")
    st.stop()

# --- 3. UI: FILTER MULTILEVEL ---
st.write("---")
st.write("### ⚙️ Filter Analisis Area & Site")
col_f1, col_f2, col_f3, col_f4 = st.columns(4)

with col_f1:
    min_date, max_date = df_merged['Date'].min(), df_merged['Date'].max()
    default_start = max_date - datetime.timedelta(days=7)
    if default_start < min_date: default_start = min_date
    selected_dates = st.date_input("📅 Tanggal:", value=(default_start, max_date), min_value=min_date, max_value=max_date)

start_date, end_date = selected_dates if len(selected_dates) == 2 else (selected_dates[0], selected_dates[0])
df_date_filtered = df_merged[(df_merged['Date'] >= start_date) & (df_merged['Date'] <= end_date)].copy()
df_periode = df_date_filtered.copy()

with col_f2:
    if 'Departemen' in df_periode.columns:
        list_nop = sorted(df_periode[df_periode['Departemen'] != 'UNKNOWN']['Departemen'].unique().tolist())
        default_nop = [n for n in list_nop if 'PALANGKARAYA' in n.upper()]
        selected_nop = st.multiselect("🏢 NOP / Dept:", options=list_nop, default=default_nop)
    else: selected_nop = []

if selected_nop: df_periode = df_periode[df_periode['Departemen'].isin(selected_nop)]

with col_f3:
    if 'Kabupaten' in df_periode.columns:
        list_kab = sorted(df_periode[df_periode['Kabupaten'] != 'UNKNOWN']['Kabupaten'].unique().tolist())
        selected_kab = st.multiselect("🏙️ Kabupaten:", options=list_kab)
    else: selected_kab = []

if selected_kab: df_periode = df_periode[df_periode['Kabupaten'].isin(selected_kab)]

with col_f4:
    if 'Kecamatan' in df_periode.columns:
        list_kec = sorted(df_periode[df_periode['Kecamatan'] != 'UNKNOWN']['Kecamatan'].unique().tolist())
        selected_kec = st.multiselect("🏘️ Kecamatan:", options=list_kec)
    else: selected_kec = []

if selected_kec: df_periode = df_periode[df_periode['Kecamatan'].isin(selected_kec)]

# --- 4. POP-UP RADAR INDUK & ANAKAN ---
list_sites = sorted(df_periode['Site_ID'].dropna().unique().tolist())
dropdown_options = [f"{s} - {name_mapping.get(s, 'Unknown')}" for s in list_sites]

selected_parents = st.multiselect("🔍 Cari & Pilih Site Induk:", options=dropdown_options)

if selected_parents:
    all_related = set()
    for s in selected_parents:
        site_code = s.split(" - ")[0]
        all_related.add(site_code)
        all_related.update(site_mapping.get(site_code, []))
        
    list_site_terlibat = sorted(list(all_related))
    opsi_fokus = [f"{s} - {name_mapping.get(s, 'Unknown')}" for s in list_site_terlibat]
    fokus_site_selection = st.multiselect("🎯 Spesifik Site (Induk & Anakan) yang Dianalisis:", options=opsi_fokus, default=opsi_fokus)
    
    if not fokus_site_selection:
        st.info("⚠️ Silakan pilih minimal satu site.")
        st.stop()
        
    site_fokus_ids = [s.split(" - ")[0] for s in fokus_site_selection]
    impact_df = df_date_filtered[df_date_filtered['Site_ID'].isin(site_fokus_ids)].copy()
    parent_codes = [s.split(" - ")[0] for s in selected_parents]
    impact_df['Keterangan'] = impact_df['Site_ID'].apply(lambda x: 'Induk (Parent)' if x in parent_codes else 'Anakan (Child)')
else:
    impact_df = df_periode.copy()
    impact_df['Keterangan'] = 'Terfilter dari Area'

if impact_df.empty:
    st.warning("⚠️ Data tidak ditemukan untuk filter tersebut.")
    st.stop()

# --- 5. DASHBOARD WORST CONTRIBUTOR ---
st.write("---")
st.write(f"### 🚨 Top Worst Contributor ({start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')})")
col_w1, col_w2, col_w3 = st.columns(3)

with col_w1:
    if 'Kabupaten' in impact_df.columns:
        worst_kab = impact_df[impact_df['Kabupaten'] != 'UNKNOWN'].groupby('Kabupaten')['Lost_Revenue'].sum().nsmallest(5).abs().sort_values()
        if not worst_kab.empty:
            fig_kab = px.bar(worst_kab, x=worst_kab.values, y=worst_kab.index, orientation='h', title='Top 5 Worst Kabupaten', color_discrete_sequence=['#EC2028'])
            fig_kab.update_traces(hovertemplate="<b>%{y}</b><br>Lost Revenue: Rp %{x:,.0f}<extra></extra>")
            fig_kab.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0), plot_bgcolor='white')
            st.plotly_chart(fig_kab, use_container_width=True)

with col_w2:
    if 'Kecamatan' in impact_df.columns:
        worst_kec = impact_df[impact_df['Kecamatan'] != 'UNKNOWN'].groupby('Kecamatan')['Lost_Revenue'].sum().nsmallest(5).abs().sort_values()
        if not worst_kec.empty:
            fig_kec = px.bar(worst_kec, x=worst_kec.values, y=worst_kec.index, orientation='h', title='Top 5 Worst Kecamatan', color_discrete_sequence=['#ff7f0e'])
            fig_kec.update_traces(hovertemplate="<b>%{y}</b><br>Lost Revenue: Rp %{x:,.0f}<extra></extra>")
            fig_kec.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0), plot_bgcolor='white')
            st.plotly_chart(fig_kec, use_container_width=True)

with col_w3:
    worst_site = impact_df.groupby('Site_ID')['Lost_Revenue'].sum().nsmallest(5).abs().sort_values()
    if not worst_site.empty:
        fig_site = px.bar(worst_site, x=worst_site.values, y=worst_site.index, orientation='h', title='Top 5 Worst Site', color_discrete_sequence=['#d62728'])
        fig_site.update_traces(hovertemplate="<b>%{y}</b><br>Lost Revenue: Rp %{x:,.0f}<extra></extra>")
        fig_site.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0), plot_bgcolor='white')
        st.plotly_chart(fig_site, use_container_width=True)

# --- 6. DASHBOARD SUMMARY ---
st.write("---")
st.write(f"### 📈 Ringkasan Performa Keseluruhan Area Terpilih")
tot_act_rev, tot_pot_rev, tot_lost_rev = impact_df['Actual_Revenue'].sum(), impact_df['Potential_Revenue'].sum(), impact_df['Lost_Revenue'].sum()
tot_act_pay, tot_pot_pay, tot_lost_pay = impact_df['Actual_Payload'].sum(), impact_df['Potential_Payload'].sum(), impact_df['Lost_Payload'].sum()

pct_lost_rev = (tot_lost_rev / tot_pot_rev * 100) if tot_pot_rev > 0 else 0
pct_lost_pay = (tot_lost_pay / tot_pot_pay * 100) if tot_pot_pay > 0 else 0
pct_gain_rev = ((tot_pot_rev - tot_act_rev) / tot_act_rev * 100) if tot_act_rev > 0 else 0
pct_gain_pay = ((tot_pot_pay - tot_act_pay) / tot_act_pay * 100) if tot_act_pay > 0 else 0

st.write("##### 💰 Analisis Revenue")
c1, c2, c3 = st.columns(3)
c1.metric("🌟 Potensi Gain (100% Ok)", f"Rp {tot_pot_rev:,.0f}", f"+{pct_gain_rev:,.2f}% Kenaikan")
c2.metric("📉 Lost Revenue", f"-Rp {abs(tot_lost_rev):,.0f}", f"{pct_lost_rev:,.2f}% Loss")
c3.metric("Pendapatan Aktual", f"Rp {tot_act_rev:,.0f}")

st.write("##### 📦 Analisis Payload")
c4, c5, c6 = st.columns(3)
c4.metric("🚀 Potensi Traffic (100% Ok)", f"{tot_pot_pay:,.0f} GB", f"+{pct_gain_pay:,.2f}% Kenaikan")
c5.metric("📉 Lost Payload", f"-{abs(tot_lost_pay):,.0f} GB", f"{pct_lost_pay:,.2f}% Loss")
c6.metric("Traffic Aktual", f"{tot_act_pay:,.0f} GB")

st.divider()

# --- 7. TREND GRAFIK HARIAN ---
st.write("### 📊 Trend Grafik Harian")
trend_df = impact_df.groupby(['Date', 'Site_ID']).agg({
    'Actual_Revenue': 'sum', 'Potential_Revenue': 'sum', 'Lost_Revenue': 'sum',
    'Actual_Payload': 'sum', 'Potential_Payload': 'sum', 'Lost_Payload': 'sum',
    'Availability_Pct': 'mean', 'Packet_Loss_Pct': 'mean'
}).reset_index()
trend_df['Date_Str'] = trend_df['Date'].astype(str)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Gain Rev (Potensi)", "Lost Rev", "Gain Payload (Potensi)", "Lost Payload", "Availability", "Packet Loss"])

def buat_grafik(df, x_col, y_col, tipe):
    if len(df['Site_ID'].unique()) > 20: 
        if tipe in ['rev', 'pay']: df = df.groupby(x_col).sum(numeric_only=True).reset_index()
        else: df = df.groupby(x_col).mean(numeric_only=True).reset_index()
        df['Site_ID'] = 'TOTAL AREA (AGREGAT)'
        
    y_val = df[y_col].abs() if 'Lost' in y_col else df[y_col]
    fig = px.line(df, x=x_col, y=y_val, color='Site_ID', markers=True, line_shape='spline')
    if tipe == 'rev': fig.update_traces(hovertemplate="<b>%{x}</b><br>Nilai: Rp %{y:,.0f}<extra></extra>")
    elif tipe == 'pay': fig.update_traces(hovertemplate="<b>%{x}</b><br>Nilai: %{y:,.0f} GB<extra></extra>")
    else: fig.update_traces(hovertemplate="<b>%{x}</b><br>Nilai: %{y:.2f}%<extra></extra>")
    fig.update_layout(plot_bgcolor='white', xaxis=dict(showgrid=False, linecolor='lightgray'), yaxis=dict(showgrid=True, gridcolor='#f0f0f0'))
    return fig

with tab1: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Potential_Revenue', 'rev'), use_container_width=True)
with tab2: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Lost_Revenue', 'rev'), use_container_width=True)
with tab3: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Potential_Payload', 'pay'), use_container_width=True)
with tab4: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Lost_Payload', 'pay'), use_container_width=True)
with tab5: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Availability_Pct', 'pct'), use_container_width=True)
with tab6: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Packet_Loss_Pct', 'pct'), use_container_width=True)

st.divider()

# --- 8. DETAIL DATAFRAME STYLED ---
st.write("### 🗄️ Detail Data Per Site")
base_cols = ['Date', 'Site_ID', 'site_name', 'Keterangan', 'Departemen', 'Kabupaten', 'Kecamatan', 'Availability', 'Packet_Loss', 'Potential_Revenue', 'Lost_Revenue', 'Actual_Revenue', 'Potential_Payload', 'Lost_Payload', 'Actual_Payload']
display_cols = [c for c in base_cols if c in impact_df.columns]

col_t1, col_t2 = st.columns([1, 1])
with col_t1:
    if len(impact_df) > 2000: st.caption("⚠️ *Menampilkan maksimal 2000 baris pertama di layar.*")
with col_t2:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        impact_df.drop(columns=['site_id'], errors='ignore').to_excel(writer, index=False, sheet_name='Data_Loss')
    st.download_button("📥 Download Excel (Filtered)", data=buffer.getvalue(), file_name="Data_Loss_Impact_Area.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def get_red_maroon_style(ratio):
    ratio = max(0, min(1, ratio)) 
    r, g, b = int(255 - 127 * ratio), int(153 - 153 * ratio), int(153 - 153 * ratio)
    txt_color = 'white' if ((0.299 * r + 0.587 * g + 0.114 * b) / 255) < 0.5 else 'black'
    return f'background-color: #{r:02x}{g:02x}{b:02x}; color: {txt_color}; font-weight: bold;'

styled_df = impact_df.head(2000)[display_cols].sort_values(by=['Date', 'Site_ID']).style.format({
    'Availability': '{:.2%}', 'Packet_Loss': '{:.2%}', 'Potential_Revenue': 'Rp {:,.0f}', 'Actual_Revenue': 'Rp {:,.0f}', 'Potential_Payload': '{:,.0f} GB', 'Actual_Payload': '{:,.0f} GB',
    'Lost_Revenue': lambda v: f"-Rp {abs(v):,.0f}" if v < 0 else "Rp 0",
    'Lost_Payload': lambda v: f"-{abs(v):,.0f} GB" if v < 0 else "0 GB"
}).apply(lambda s: ['background-color: #d4edda; color: #155724; font-weight: bold;' if v >= 0.99 else get_red_maroon_style((v - 0.99) / (s.min() - 0.99) if s.min() < 0.99 else 0) if pd.notna(v) else '' for v in s], subset=['Availability']
).apply(lambda s: ['background-color: #d4edda; color: #155724; font-weight: bold;' if v < 0.001 else get_red_maroon_style((v - 0.001) / (s.max() - 0.001) if s.max() > 0.001 else 0) if pd.notna(v) else '' for v in s], subset=['Packet_Loss']
).apply(lambda s: ['background-color: #f8d7da; color: #721c24; font-weight: bold;' if v < 0 else '' for v in s], subset=['Lost_Revenue', 'Lost_Payload'])

st.dataframe(styled_df, use_container_width=True)

# --- FOOTER ---
st.markdown('<div style="text-align: center; margin-top: 50px; padding-top: 20px; border-top: 1px solid #eaeaea; color: #888888; font-size: 14px;">© 2026 | Created with ❤️ by Fauzi Ramdani - 97122</div>', unsafe_allow_html=True)
