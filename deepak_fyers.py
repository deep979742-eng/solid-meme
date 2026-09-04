import streamlit as st
import pandas as pd
import datetime
import time
import json
import requests
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components  

st.set_page_config(page_title="F&O LIVE Dashboard", layout="wide", initial_sidebar_state="collapsed")

components.html(
    """
    <script>
    const targetNode = window.parent.document.body;
    const config = { childList: true, subtree: true };
    const callback = function(mutationsList, observer) {
        const deployBtn = window.parent.document.querySelector('[data-testid="stAppDeployButton"]');
        if (deployBtn) { deployBtn.style.display = 'none'; }
        const toolbar = window.parent.document.querySelector('[data-testid="stToolbar"]');
        if (toolbar) { toolbar.style.display = 'none'; }
        const header = window.parent.document.querySelector('header');
        if (header) { header.style.display = 'none'; }
    };
    const observer = new MutationObserver(callback);
    observer.observe(targetNode, config);
    callback();
    </script>
    """, height=0, width=0
)

css_str = """
<style>
header, footer, [data-testid="stAppDeployButton"], [data-testid="stToolbar"] { display: none !important; visibility: hidden !important; opacity: 0 !important; }
.block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; padding-left: 0.5rem !important; padding-right: 0.5rem !important; margin-top: -20px !important; } 
.time-box { border: 1px solid rgba(128, 128, 128, 0.4); padding: 0px 15px; border-radius: 6px; background-color: rgba(128, 128, 128, 0.1); text-align: center; font-weight: bold; font-size: 13px; color: #00BFFF; margin: 0; display: flex; align-items: center; justify-content: center; height: 36px; white-space: nowrap; width: max-content; }
div[data-testid="stToggle"] label { flex-direction: row-reverse !important; justify-content: flex-end !important; gap: 8px !important; margin-top: 5px; }
div[data-testid="stToggle"] label p { font-weight: 700 !important; font-size: 14px !important; color: #FF4B4B !important; }
.stRadio div[role='radiogroup'] > label { flex: 1 1 0px !important; border: 1px solid rgba(128, 128, 128, 0.4) !important; border-radius: 6px !important; background-color: rgba(128, 128, 128, 0.1) !important; cursor: pointer !important; display: flex !important; align-items: center !important; justify-content: center !important; font-weight: 600 !important; height: 36px !important; }
.stRadio div[role='radiogroup'] > label > div:first-child { display: none !important; }
@media (max-width: 768px) { 
    .block-container { padding-top: 0.5rem !important; margin-top: -30px !important; } 
    .stRadio div[role='radiogroup'] > label { font-size: 12px !important; height: 34px !important; }
    .time-box { font-size: 11px !important; height: 34px !important; }
    div[data-testid="stColumns"] { display: flex !important; flex-direction: row !important; align-items: center !important; flex-wrap: nowrap !important; }
    div[data-testid="stColumns"] > div:nth-child(3) { display: none !important; } 
}
</style>
"""
st.markdown(css_str, unsafe_allow_html=True)

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
today_str = datetime.datetime.now(IST).strftime("%Y-%m-%d")
FIREBASE_URL = "https://fyers-bot-606b9-default-rtdb.firebaseio.com"

st_autorefresh(interval=5000, limit=100000, key="viewer_fetch_loop") 

try:
    dash_resp = requests.get(f"{FIREBASE_URL}/Dashboard/Latest.json", timeout=4)
    if dash_resp.status_code == 200 and dash_resp.json():
        shared_pack = dash_resp.json()
        st.session_state.cached_data = shared_pack.get("data", [])
        st.session_state.last_api_call = datetime.datetime.fromtimestamp(shared_pack.get("time", time.time()), IST)
except: pass

@st.cache_data(ttl=60)
def fetch_chart_history():
    try:
        r = requests.get(f'{FIREBASE_URL}/ChartHistory.json?orderBy="$key"&limitToLast=100', timeout=10)
        if r.status_code == 200 and r.json():
            all_rows = []
            for doc_id, batch in r.json().items():
                if str(doc_id).startswith(today_str.replace("-", "")) and 'data' in batch: all_rows.extend(batch['data'])
            return all_rows
    except: pass
    return []

st.session_state.chart_df = pd.DataFrame(fetch_chart_history())

# 🚀 100% DYNAMIC STOCK LIST LOGIC (No Hardcoding) 
dynamic_symbols = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]
if 'cached_data' in st.session_state and st.session_state.cached_data:
    fetched_syms = sorted(list(set([item['SYMBOL'] for item in st.session_state.cached_data])))
    if fetched_syms: dynamic_symbols = fetched_syms

def find_divergence_stocks(chart_df, latest_data_list):
    bullish_list, bearish_list = [], []
    if chart_df.empty or not latest_data_list: return pd.DataFrame(bullish_list), pd.DataFrame(bearish_list)
    latest_lookup = {item['SYMS']: item for item in latest_data_list}
    day_df = chart_df[chart_df['Date'].astype(str).str.strip() == today_str]

    for sym in day_df['Symbol'].unique():
        sdf = day_df[day_df['Symbol'] == sym].sort_values(by='Time')
        if len(sdf) < 5: continue 
        
        vol_series, pcr_series, ltp_series = pd.to_numeric(sdf['VOL CPR'], errors='coerce').dropna(), pd.to_numeric(sdf['OPT PCR'], errors='coerce').dropna(), pd.to_numeric(sdf['LTP'], errors='coerce').dropna()
        if vol_series.empty or pcr_series.empty or ltp_series.empty: continue

        first_vol, first_pcr, first_ltp = vol_series.iloc[:4].mean(), pcr_series.iloc[:4].mean(), ltp_series.iloc[:4].mean()
        last_vol, last_pcr, last_ltp = vol_series.iloc[-1], pcr_series.iloc[-1], ltp_series.iloc[-1]
        
        if first_vol == 0 or first_ltp == 0: continue
        if abs((last_ltp - first_ltp) / first_ltp) * 100 > 1.5: continue 

        linfo = latest_lookup.get(sym, {})
        ce_con, pe_con = float(linfo.get('CE_CON', 0)), float(linfo.get('PE_CON', 0))
        
        if (last_vol > first_vol) and (last_vol >= vol_series.max() * 0.75) and (last_pcr >= first_pcr * 0.90) and (ce_con >= 70):
            bullish_list.append({'SYMBOL': sym, 'CHANGE %': float(linfo.get('CHG_%', 0)), 'OPT PCR': float(linfo.get('O_PCR', 0)), 'VOL CPR': float(linfo.get('V_CPR', 0)), 'CE CONTRACT': ce_con})
        elif (last_vol < first_vol) and (last_vol <= vol_series.min() * 1.25 if vol_series.min() > 0.1 else last_vol <= 0.5) and (last_pcr <= first_pcr * 1.10) and (pe_con >= 70):
            bearish_list.append({'SYMBOL': sym, 'CHANGE %': float(linfo.get('CHG_%', 0)), 'OPT PCR': float(linfo.get('O_PCR', 0)), 'VOL CPR': float(linfo.get('V_CPR', 0)), 'PE CONTRACT': pe_con})

    return pd.DataFrame(bullish_list), pd.DataFrame(bearish_list)

if 'cached_data' in st.session_state and len(st.session_state.cached_data) > 0:
    col_menu, col_tim, col_space, col_tog = st.columns([1.5, 1.2, 5.8, 1.5])
    with col_menu: selected_tab = st.radio("Menu", ["📊 Dash", "📈 CHART", "🚀 TREND"], horizontal=True, label_visibility="collapsed")
    with col_tim:
        if selected_tab == "📊 Dash": st.markdown(f"<div class='time-box'>⏱️ {st.session_state.last_api_call.strftime('%H:%M:%S') if 'last_api_call' in st.session_state else ''}</div>", unsafe_allow_html=True)
    with col_tog:
        if selected_tab == "📊 Dash": show_pct = st.toggle("SHOW %", value=True)

    if selected_tab == "📊 Dash":
        # Hata diya Warning box!
        def color_num(val, is_pct=False):
            try: return f"<span style='color: {'#00AA00' if float(val)>0 else '#FF0000' if float(val)<0 else '#888'};'>{float(val):+.2f}{'%' if is_pct else ''}</span>"
            except: return str(val)
        
        df = pd.DataFrame(st.session_state.cached_data)
        if not df.empty:
            df['Conv_Rank'] = df['CE_CON'].abs() + df['PE_CON'].abs()
            df = df.sort_values(by='Conv_Rank', ascending=False)
            df['VOL CHECKER'] = df['VOL_PCT'] if show_pct else df['VOL_ABS']
            df['PCR CHECKER'] = df['PCR_PCT'] if show_pct else df['PCR_ABS']
            df = df[['SYMS', 'OPEN_STATUS', 'V_PCR', 'O_PCR', 'V_CPR', 'LTP_CH', 'CHG_%', 'LTP', 'CE_CON', 'PE_CON', 'PCR CHECKER', 'VOL CHECKER']]
            df = df.rename(columns={'SYMS': 'SYMBOL', 'OPEN_STATUS': 'OPENING', 'V_PCR': 'VOL<br>PCR', 'O_PCR': 'OPTION<br>PCR', 'V_CPR': 'VOL<br>CPR', 'LTP_CH': 'LTP<br>CHANGE', 'CHG_%': 'CHANGE<br>%', 'LTP': 'LTP', 'CE_CON': 'CE<br>CONTRACT', 'PE_CON': 'PE<br>CONTRACT', 'PCR CHECKER': 'PCR<br>CHECKER', 'VOL CHECKER': 'VOL<br>CHECKER'})
            
            df['LTP<br>CHANGE'] = df['LTP<br>CHANGE'].apply(lambda x: color_num(x, False))
            df['CHANGE<br>%'] = df['CHANGE<br>%'].apply(lambda x: color_num(x, True))
            df['CE<br>CONTRACT'] = df['CE<br>CONTRACT'].apply(lambda x: color_num(x, True))
            df['PE<br>CONTRACT'] = df['PE<br>CONTRACT'].apply(lambda x: color_num(x, True))
            df['PCR<br>CHECKER'] = df['PCR<br>CHECKER'].apply(lambda x: color_num(x, show_pct))
            df['VOL<br>CHECKER'] = df['VOL<br>CHECKER'].apply(lambda x: color_num(x, show_pct))
            
            components.html(f"""
            <style>
                table {{ width: 100%; border-collapse: collapse; font-size: 12px; font-family: sans-serif; }}
                th {{ background: darkblue; color: white; padding: 8px; position: sticky; top: 0; }}
                td {{ text-align: center; padding: 6px; border-bottom: 1px solid #eee; font-weight: bold; }}
            </style>
            <div style="height:800px; overflow:auto;">{df.to_html(escape=False, index=False)}</div>
            """, height=800)

    elif selected_tab == "📈 CHART":
        col_c1, col_c2 = st.columns([1, 1])
        with col_c1: sel_stock = st.selectbox("Stock:", dynamic_symbols, index=0, label_visibility="collapsed")
        with col_c2: chart_mode = st.radio("View:", ["Vol CPR", "OPT PCR"], horizontal=True, label_visibility="collapsed")

        if not st.session_state.chart_df.empty and sel_stock:
            df_sym = st.session_state.chart_df[(st.session_state.chart_df['Date'].astype(str).str.strip() == today_str) & (st.session_state.chart_df['Symbol'].astype(str).str.strip() == sel_stock)].sort_values(by='Time')
            if not df_sym.empty:
                apex_html = f"""
                <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
                <div id="chart"></div>
                <script>
                    new ApexCharts(document.querySelector("#chart"), {{
                        series: [{{ name: '{chart_mode}', type: 'area', data: {pd.to_numeric(df_sym['VOL CPR' if chart_mode == 'Vol CPR' else 'OPT PCR'], errors='coerce').fillna(0).tolist()} }}, 
                                 {{ name: 'LTP', type: 'line', data: {pd.to_numeric(df_sym['LTP'], errors='coerce').fillna(0).tolist()} }}],
                        chart: {{ height: 400, type: 'line', toolbar: {{ show: false }} }},
                        colors: ['{'#FF4D4D' if chart_mode == 'Vol CPR' else '#00BFFF'}', '#00CC66'],
                        stroke: {{ width: [3, 3], curve: 'smooth' }},
                        xaxis: {{ categories: {df_sym['Time'].tolist()}, tickAmount: 10 }},
                        yaxis: [{{ title: {{text: '{chart_mode}'}} }}, {{ opposite: true, title: {{text: 'LTP'}} }}]
                    }}).render();
                </script>
                """
                components.html(apex_html, height=450)

    elif selected_tab == "🚀 TREND":
        df_bullish, df_bearish = find_divergence_stocks(st.session_state.get('chart_df', pd.DataFrame()), st.session_state.get('cached_data', []))

        def generate_trend_html(df, tab_type="Bullish"):
            if df.empty: return "<div style='text-align:center; padding: 20px; font-weight:bold;'>⏳ No Data</div>"
            df = df.copy()
            df['CHANGE %'] = df['CHANGE %'].apply(lambda v: f"<span style='color:{'#00AA00' if float(v)>=0 else '#FF0000'}; font-weight:bold;'>{float(v):+.2f}%</span>")
            df['OPT PCR'] = df['OPT PCR'].apply(lambda v: f"<span style='color:{'#00AA00' if float(v)>=1 else '#FF0000'}; font-weight:bold;'>{float(v):.2f}</span>")
            df['VOL CPR'] = df['VOL CPR'].apply(lambda v: f"<span style='color:{'#00AA00' if float(v)>=1 else '#FF0000'}; font-weight:bold;'>{float(v):.2f}</span>")
            if tab_type == "Bullish": df['CE CONTRACT'] = df['CE CONTRACT'].apply(lambda v: f"<span style='color:{'#00AA00' if float(v)>=70 else '#888'}; font-weight:bold;'>{float(v):+.1f}%</span>")
            else: df['PE CONTRACT'] = df['PE CONTRACT'].apply(lambda v: f"<span style='color:{'#FF0000' if float(v)<=-70 else '#888'}; font-weight:bold;'>{float(v):+.1f}%</span>")
            
            return f"""<style>table {{ width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 13px; }} th {{ background: {'#00AA00' if tab_type=='Bullish' else '#FF0000'}; color: white; padding: 8px; }} td {{ text-align: center; padding: 7px; border-bottom: 1px solid #eee; }}</style> {df.to_html(escape=False, index=False)}"""

        tab_bullish, tab_bearish = st.tabs(["🟢 Bullish Stocks", "🔴 Bearish Stocks"])
        with tab_bullish: components.html(generate_trend_html(df_bullish.sort_values(by='CE CONTRACT', ascending=False), "Bullish"), height=600, scrolling=True)
        with tab_bearish: components.html(generate_trend_html(df_bearish.sort_values(by='PE CONTRACT', ascending=False), "Bearish"), height=600, scrolling=True)
else:
    st.info("⏳ Booting up... Waiting for Engine to push data.")
