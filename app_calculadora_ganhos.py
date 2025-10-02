import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import base64
from pathlib import Path

# ====================== CONFIG INICIAL ======================
st.set_page_config(
    page_title="🖩 Calculadora de Ganhos",
    page_icon="📶",  # Ícone do navegador
    layout="wide"
)

# ====================== AUTENTICAÇÃO COM SENHA ======================
def check_password():
    def password_entered():
        if st.session_state["password"] == "claro@123":
            st.session_state["authenticated"] = True
        else:
            st.session_state["authenticated"] = False
            st.error("Senha incorreta. Tente novamente.")

    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.text_input("🔐 Insira a senha para acessar:", type="password", on_change=password_entered, key="password")
        st.stop()

check_password()

# ====================== FUNÇÃO PARA CARREGAR IMAGEM ======================
def _find_asset_bytes(name_candidates):
    exts = [".png", ".jpg", ".jpeg", ".webp"]
    try:
        script_dir = Path(__file__).parent.resolve()
    except NameError:
        script_dir = Path.cwd().resolve()
    search_dirs = [
        script_dir,
        script_dir / "assets",
        script_dir / "static",
        Path.cwd().resolve(),
        Path.cwd().resolve() / "assets",
        Path.cwd().resolve() / "static",
    ]
    for d in search_dirs:
        for base in name_candidates:
            for ext in exts:
                p = d / f"{base}{ext}"
                if p.exists():
                    try:
                        return p.read_bytes()
                    except Exception:
                        pass
    return None

def load_logo_for_title():
    return _find_asset_bytes(["claro_logo", "logo_claro", "claro"])

# ====================== CARREGAR LOGO NO TÍTULO ====================== #vertical-align:middle;
logo_bytes = load_logo_for_title()
if logo_bytes:
    img_b64 = base64.b64encode(logo_bytes).decode()
    st.markdown(
        f"""
        <h1 style='text-align: center; color: #8B0000; font-size: 80px;'>
            Calculadora de Ganhos <img src='data:image/png;base64,{img_b64}' style='height:150px;  margin-right:10px'>
        </h1>
        """,
        unsafe_allow_html=True
    )
else:
    st.markdown(
        "<h1 style='text-align: center; color: #8B0000; font-size: 60px;'>🖩 Calculadora de Ganhos</h1>",
        unsafe_allow_html=True
    )

# ========== FUNÇÃO DE CARGA ==========
@st.cache_data
def carregar_dados():
    url_base = "https://raw.githubusercontent.com/gustavo3-freitas/base_calculadora/main/Tabela_Performance.xlsx"
    df = pd.read_excel(url_base, sheet_name="Tabela Performance")
    df['ANOMES'] = pd.to_datetime(df['ANOMES'].astype(str), format='%Y%m', errors='coerce')
    df['VOL_KPI'] = pd.to_numeric(df['VOL_KPI'], errors='coerce')
    df['CR_DIR'] = pd.to_numeric(df['CR_DIR'], errors='coerce')
    return df

df = carregar_dados()

# ========== TAXAS FIXAS ==========
retido_dict = {
    'App': 0.916893598,
    'Bot': 0.883475537,
    'Web': 0.902710768
}

# ========== FILTROS ========== #
st.markdown("### 🔎 Filtros de Cenário")
col1, col2 = st.columns(2)

mes_atual_str = pd.to_datetime(datetime.today()).strftime('%Y-%m')
anomes = col1.selectbox("🗓️ Mês", sorted(df['ANOMES'].dt.strftime('%Y-%m').dropna().unique()),
                        index=sorted(df['ANOMES'].dt.strftime('%Y-%m').dropna().unique()).index(mes_atual_str)
                        if mes_atual_str in df['ANOMES'].dt.strftime('%Y-%m').dropna().unique() else 0)

segmento = col2.selectbox("📶 Segmento", sorted(df['SEGMENTO'].dropna().unique()))
anomes_dt = pd.to_datetime(anomes)
tp_meta = "Real"

df_segmento = df[
    (df['ANOMES'] == anomes_dt) &
    (df['TP_META'] == tp_meta) &
    (df['SEGMENTO'] == segmento)
]

subcanais_disponiveis = sorted(df_segmento['NM_SUBCANAL'].dropna().unique())
subcanal = st.selectbox("📌 Subcanal", subcanais_disponiveis)

df_subcanal = df_segmento[df_segmento['NM_SUBCANAL'] == subcanal]
tribo_detectada = df_subcanal['NM_TORRE'].dropna().unique()
tribo = tribo_detectada[0] if len(tribo_detectada) > 0 else "Indefinido"

col1, col2, col3, col4 = st.columns(4)
col1.metric("Tribo", tribo)
col2.metric("Canal", tribo)
col3.metric("Segmento", segmento)
col4.metric("Subcanal", subcanal)

retido_pct = retido_dict.get(tribo, 1.0)

# ========== PARÂMETROS DE SIMULAÇÃO ==========
st.markdown("---")
st.markdown("### ➗ Parâmetros para Simulação")
col1, _ = st.columns([2, 1])
volume_esperado = col1.number_input("📥 Volume de Transações Esperado", min_value=0, value=10000)

# ========== CÁLCULO ==========
if st.button("🚀 Calcular Transações Evitadas"):
    df_final = df_subcanal[df_subcanal['SEGMENTO'] == segmento]

    if df_final.empty:
        st.warning("❌ Nenhum dado encontrado com os filtros selecionados.")
        st.stop()

    cr_segmento = 0.494699284 if segmento == "Móvel" else 0.498877199 if segmento == "Residencial" else df_final['CR_DIR'].mean()
    df_acessos = df_final[df_final['NM_KPI'].str.contains("6 - Acessos", case=False, na=False)]
    df_transacoes = df_final[df_final['NM_KPI'].str.contains("7.1 - Transações", case=False, na=False)]

    vol_acessos = df_acessos['VOL_KPI'].sum()
    vol_transacoes = df_transacoes['VOL_KPI'].sum()
    tx_trans_acessos = vol_transacoes / vol_acessos if vol_acessos > 0 else 1.75
    tx_trans_acessos = tx_trans_acessos if tx_trans_acessos > 0 else 1.75

    transacoes_esperadas = (volume_esperado / tx_trans_acessos) * cr_segmento * retido_pct

    st.markdown("---")
    st.markdown("### 📊 Resultados da Simulação")
    col1, col2, col3 = st.columns(3)
    col1.metric("Transações / Acessos", f"{tx_trans_acessos:.2f}")
    col2.metric("CR Segmento (%)", f"{cr_segmento*100:.2f}")
    col3.metric(f"% Retido ({tribo})", f"{retido_pct*100:.2f}")

    valor_formatado = f"{transacoes_esperadas:,.0f}".replace(",", ".")
    st.success(f"✅ Transações Evitadas: **{valor_formatado}**")
    st.caption("Fórmula: Volume Esperado ÷ (Transações / Acessos) × CR Segmento × % Retido")

    # DASHBOARD POR SUBCANAIS
    st.markdown("---")
    st.markdown("### 📄 Simulação para Todos os Subcanais")
    resultados_lote = []

    for sub in subcanais_disponiveis:
        df_sub = df_segmento[df_segmento['NM_SUBCANAL'] == sub]
        tribo_lote = df_sub['NM_TORRE'].dropna().unique()
        tribo_lote = tribo_lote[0] if len(tribo_lote) > 0 else "Indefinido"
        ret_lote = retido_dict.get(tribo_lote, 1.0)
        df_acessos_lote = df_sub[df_sub['NM_KPI'].str.contains("6 - Acessos", case=False, na=False)]
        df_trans_lote = df_sub[df_sub['NM_KPI'].str.contains("7.1 - Transações", case=False, na=False)]

        acessos = df_acessos_lote['VOL_KPI'].sum()
        transacoes = df_trans_lote['VOL_KPI'].sum()
        tx = transacoes / acessos if acessos > 0 else 1.75
        tx = tx if tx > 0 else 1.75
        cr = 0.494699284 if segmento == "Móvel" else 0.498877199 if segmento == "Residencial" else df_sub['CR_DIR'].mean()
        estimado = (volume_esperado / tx) * cr * ret_lote

        resultados_lote.append({
            "Subcanal": sub,
            "Tribo": tribo_lote,
            "Transações / Acessos": round(tx, 2),
            "% Retido": round(ret_lote*100, 2),
            "% CR": round(cr*100, 2),
            "Transações Evitadas": round(estimado)
        })

    df_lote = pd.DataFrame(resultados_lote)
    st.dataframe(df_lote, use_container_width=True)

    csv = df_lote.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar Simulação Completa (CSV)", csv, "simulacao_transacoes.csv", "text/csv")

    import plotly.express as px
    fig = px.bar(df_lote.sort_values("Transações Evitadas", ascending=False),
                 x="Subcanal", y="Transações Evitadas",
                 title="📊 Transações Evitadas por Subcanal",
                 color="Tribo",
                 text_auto=True)
    st.plotly_chart(fig, use_container_width=True)




