# app_calculadora_ganhos.py
import io
import base64
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ====================== CONFIG INICIAL ======================
st.set_page_config(page_title="🖩 Calculadora de Ganhos", page_icon="📶", layout="wide")

# ====================== AUTENTICAÇÃO ======================
def check_password():
    def password_entered():
        st.session_state["authenticated"] = (st.session_state.get("password") == "claro@123")
        if not st.session_state["authenticated"]:
            st.error("Senha incorreta. Tente novamente.")
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if not st.session_state["authenticated"]:
        st.text_input("🔐 Insira a senha para acessar:", type="password",
                      on_change=password_entered, key="password")
        st.stop()

check_password()

# ====================== LOGO/TÍTULO ======================
def _find_asset_bytes(name_candidates):
    exts = [".png", ".jpg", ".jpeg", ".webp"]
    try:
        script_dir = Path(__file__).parent.resolve()
    except NameError:
        script_dir = Path.cwd().resolve()
    for d in [script_dir, script_dir/"assets", script_dir/"static", Path.cwd(), Path.cwd()/ "assets", Path.cwd()/ "static"]:
        for base in name_candidates:
            for ext in exts:
                p = d / f"{base}{ext}"
                if p.exists():
                    return p.read_bytes()
    return None

def load_logo_for_title():
    return _find_asset_bytes(["claro_logo", "logo_claro", "claro"])

logo_bytes = load_logo_for_title()
if logo_bytes:
    img_b64 = base64.b64encode(logo_bytes).decode()
    st.markdown(
        f"""
        <h1 style='text-align:center;color:#8B0000;font-size:56px;margin:6px 0 10px'>
          <img src='data:image/png;base64,{img_b64}' style='height:70px;vertical-align:middle;margin-right:12px'>
          Calculadora de Ganhos
        </h1>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown("<h1 style='text-align:center;color:#8B0000;font-size:52px'>🖩 Calculadora de Ganhos</h1>", unsafe_allow_html=True)

# ====================== PARÂMETROS FIXOS ======================
RETIDO_DICT = {"App": 0.916893598, "Bot": 0.883475537, "Web": 0.902710768}
CR_SEGMENTO = {"Móvel": 0.4947, "Residencial": 0.4989}
DEFAULT_TX_UU_CPF = 12.28  # usado só como último fallback

# ====================== CARREGAR BASE ======================
URL_PERFORMANCE_RAW = "https://raw.githubusercontent.com/gustavo3-freitas/base_calculadora/main/Tabela_Performance.xlsx"

@st.cache_data(show_spinner=True)
def carregar_dados():
    df = pd.read_excel(URL_PERFORMANCE_RAW, sheet_name="Tabela Performance")
    # filtra só Real
    if "TP_META" in df.columns:
        df = df[df["TP_META"].astype(str).str.lower().eq("real")]
    # numéricos
    for c in ["VOL_KPI"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

df = carregar_dados()

# ====================== HELPERS ======================
def fmt_int(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")

def sum_kpi(df_scope: pd.DataFrame, patterns):
    """Soma VOL_KPI de linhas cujo NM_KPI contenha QUALQUER padrão listado (case-insensitive)."""
    m = False
    for pat in patterns:
        m = m | df_scope["NM_KPI"].str.contains(pat, case=False, na=False, regex=True)
    return df_scope.loc[m, "VOL_KPI"].sum()

def tx_uu_cpf_dyn(df_all: pd.DataFrame, segmento: str, subcanal: str) -> float:
    """
    Tenta TX_UU/CPF no SUBCANAL (Transações ÷ Usuários).
    Se não houver Usuários no subcanal, cai para nível de SEGMENTO.
    Se ainda assim faltar, retorna DEFAULT_TX_UU_CPF.
    """
    df_seg = df_all[df_all["SEGMENTO"] == segmento]

    # --- Subcanal
    df_sub = df_seg[df_seg["NM_SUBCANAL"] == subcanal]
    vt_sub = sum_kpi(df_sub, [r"7\.1\s*-\s*Transa", "Transações"])
    vu_sub = sum_kpi(df_sub, [r"4\.1\s*-\s*Usu", "Usuár", "MAU", "CPF"])
    if vt_sub > 0 and vu_sub > 0:
        return vt_sub / vu_sub

    # --- Segmento (fallback intermediário)
    vt_seg = sum_kpi(df_seg, [r"7\.1\s*-\s*Transa", "Transações"])
    vu_seg = sum_kpi(df_seg, [r"4\.1\s*-\s*Usu", "Usuár", "MAU", "CPF"])
    if vt_seg > 0 and vu_seg > 0:
        return vt_seg / vu_seg

    # --- Fallback último
    return DEFAULT_TX_UU_CPF

def tx_trn_por_acesso(df_scope: pd.DataFrame) -> float:
    vt = sum_kpi(df_scope, [r"7\.1\s*-\s*Transa", "Transações"])
    va = sum_kpi(df_scope, [r"6\s*-\s*Acesso", "Acessos"])
    if va <= 0:
        return 1.0
    tx = vt / va
    return max(tx, 1.0)  # mínimo 1,00

def regra_retido_por_tribo(tribo: str) -> float:
    # DMA usa o retido do BOT
    if str(tribo).strip().lower() == "dma":
        return RETIDO_DICT["Bot"]
    return RETIDO_DICT.get(tribo, RETIDO_DICT["Web"])

# ====================== FILTROS ======================
st.markdown("### 🔎 Filtros de Cenário")
col1, col2 = st.columns(2)
segmentos = sorted(df["SEGMENTO"].dropna().unique().tolist())
segmento = col1.selectbox("📊 Segmento", segmentos)
subcanais = sorted(df.loc[df["SEGMENTO"] == segmento, "NM_SUBCANAL"].dropna().unique())
subcanal = col2.selectbox("📌 Subcanal", subcanais)

df_sub = df[(df["SEGMENTO"] == segmento) & (df["NM_SUBCANAL"] == subcanal)]
tribo = df_sub["NM_TORRE"].dropna().unique().tolist()[0] if not df_sub.empty else "Indefinido"

c1, c2, c3, c4 = st.columns(4)
c1.metric("Tribo", tribo)
c2.metric("Canal", tribo)
c3.metric("Segmento", segmento)
c4.metric("Subcanal", subcanal)

with st.expander("⚙️ Premissas utilizadas (fixas)", expanded=False):
    st.write(
        f"""
- **CR por segmento**: Móvel = {CR_SEGMENTO['Móvel']*100:.2f}%, Residencial = {CR_SEGMENTO['Residencial']*100:.2f}%  
- **% Retido 72h**: App = {RETIDO_DICT['App']*100:.2f}%, Bot = {RETIDO_DICT['Bot']*100:.2f}%, Web = {RETIDO_DICT['Web']*100:.2f}%  
- **TX UU / CPF (dinâmica)** = Transações ÷ Usuários (subcanal → segmento → fallback {DEFAULT_TX_UU_CPF:.2f}).  
- **Regra Retido (Dma)**: usa **%Retido = Bot (88,35%)**.  
- **Transações/Acessos mínimo**: valores < 1,00 → forçados para 1,00.
        """
    )

# ====================== INPUT ======================
st.markdown("---")
st.markdown("### ➗ Parâmetros de Simulação")
volume_trans = st.number_input("📥 Volume de Transações", min_value=0, value=10_000, step=1000)

# ====================== CÁLCULOS ======================
if st.button("🚀 Calcular Ganhos Potenciais"):
    if df_sub.empty:
        st.warning("❌ Nenhum dado encontrado para os filtros selecionados.")
        st.stop()

    cr_segmento = CR_SEGMENTO.get(segmento, 0.50)

    # Tx Transações/Acesso (subcanal)
    tx_trn_acc = tx_trn_por_acesso(df_sub)

    # TX_UU/CPF dinâmico (subcanal -> segmento -> fallback)
    tx_uu_cpf = tx_uu_cpf_dyn(df, segmento, subcanal)

    # % Retido (regra DMA)
    retido_base = regra_retido_por_tribo(tribo)

    # Acessos e MAU
    volume_acessos = volume_trans / tx_trn_acc
    mau_cpf = volume_trans / (tx_uu_cpf if tx_uu_cpf > 0 else DEFAULT_TX_UU_CPF)

    # CR evitado
    cr_evitado = volume_acessos * cr_segmento * retido_base
    cr_evitado_floor = np.floor(cr_evitado + 1e-9)

    # =================== RESULTADOS ===================
    st.markdown("---")
    st.markdown("### 📊 Resultados da Simulação")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Transações / Acessos", f"{tx_trn_acc:.2f}")
    r2.metric("% CR do Segmento", f"{cr_segmento*100:.2f}%")
    r3.metric("% Retido (regra)", f"{retido_base*100:.2f}%")
    r4.metric("MAU (CPF)", fmt_int(mau_cpf))

    st.markdown(
        f"""
        <div style="
            max-width:480px;margin:18px auto;padding:18px 22px;
            background:linear-gradient(90deg,#b31313 0%, #d01f1f 60%, #e23a3a 100%);
            border-radius:18px; box-shadow:0 8px 18px rgba(139,0,0,.25); color:#fff;">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div style="font-weight:700;font-size:20px;">Volume de CR Evitado Estimado</div>
            <div style="font-weight:800;font-size:30px;background:#fff;color:#b31313;
                        padding:6px 16px;border-radius:12px;line-height:1">
              {fmt_int(cr_evitado_floor)}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Fórmulas: Acessos = Transações ÷ (Tx Transações/Acesso).  MAU = Transações ÷ (Transações/Usuários).  CR Evitado = Acessos × CR × %Retido.")

    # =================== TABELA LOTE ===================
    st.markdown("---")
    st.markdown("### 📄 Simulação - Todos os Subcanais")

    resultados = []
    for sub in subcanais:
        df_i = df[(df["SEGMENTO"] == segmento) & (df["NM_SUBCANAL"] == sub)]
        tribo_i = df_i["NM_TORRE"].dropna().unique().tolist()[0] if not df_i.empty else "Indefinido"

        tx_i = tx_trn_por_acesso(df_i)
        tx_uu_i = tx_uu_cpf_dyn(df, segmento, sub)
        ret_i = regra_retido_por_tribo(tribo_i)
        cr_seg_i = CR_SEGMENTO.get(segmento, 0.50)

        vol_acc_i = volume_trans / tx_i
        mau_i = volume_trans / (tx_uu_i if tx_uu_i > 0 else DEFAULT_TX_UU_CPF)
        est_i = np.floor(vol_acc_i * cr_seg_i * ret_i + 1e-9)

        resultados.append({
            "Subcanal": sub,
            "Tribo": tribo_i,
            "Transações / Acessos": round(tx_i, 2),
            "↓ % Retido": round(ret_i*100, 2),
            "% CR": round(cr_seg_i*100, 2),
            "Volume de Acessos": int(vol_acc_i),
            "MAU (CPF)": int(mau_i),
            "Volume de CR Evitado": int(est_i),
        })

    df_lote = pd.DataFrame(resultados)
    st.dataframe(df_lote, use_container_width=False)

    # =================== PARETO ===================
    st.markdown("### 🔎 Análise de Pareto - Potencial de Ganho")
    df_pareto = df_lote.sort_values("Volume de CR Evitado", ascending=False).reset_index(drop=True)
    total = df_pareto["Volume de CR Evitado"].sum()
    if total > 0:
        df_pareto["Acumulado"] = df_pareto["Volume de CR Evitado"].cumsum()
        df_pareto["Acumulado %"] = 100 * df_pareto["Acumulado"] / total
    else:
        df_pareto["Acumulado"] = 0
        df_pareto["Acumulado %"] = 0.0
    df_pareto["Cor"] = np.where(df_pareto["Acumulado %"] <= 80, "crimson", "lightgray")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_pareto["Subcanal"], y=df_pareto["Volume de CR Evitado"],
                         name="Volume de CR Evitado", marker_color=df_pareto["Cor"]))
    fig.add_trace(go.Scatter(x=df_pareto["Subcanal"], y=df_pareto["Acumulado %"],
                             name="Acumulado %", mode="lines+markers",
                             marker=dict(color="royalblue"), yaxis="y2"))
    fig.update_layout(
        title="📈 Pareto - Volume de CR Evitado",
        xaxis=dict(title="Subcanais"),
        yaxis=dict(title="Volume de CR Evitado"),
        yaxis2=dict(title="Acumulado %", overlaying="y", side="right", range=[0, 100]),
        legend=dict(x=0.72, y=1.18, orientation="h"),
        bargap=0.2, margin=dict(l=10, r=10, t=60, b=80)
    )
    st.plotly_chart(fig, use_container_width=False)

    # =================== TOP 80% + INSIGHT ===================
    df_top80 = df_pareto[df_pareto["Acumulado %"] <= 80].copy()
    st.markdown("### 🏆 Subcanais Prioritários (Top 80%)")
    st.dataframe(df_top80[["Subcanal", "Tribo", "Volume de CR Evitado", "Acumulado %"]],
                 use_container_width=False)

    total_ev = int(df_lote["Volume de CR Evitado"].sum())
    top80_names = ", ".join(df_top80["Subcanal"].tolist())
    st.markdown(
        f"""**🧠 Insight Automático**  

- Volume total estimado de **CR evitado**: **{fmt_int(total_ev)}**.  
- **{len(df_top80)} subcanais** concentram **80%** do potencial: **{top80_names}**.  
- **Ação:** priorize estes subcanais para maximizar impacto."""
    )

    # =================== DOWNLOAD ===================
    buffer = io.BytesIO()
    engine = "xlsxwriter"
    try:
        import xlsxwriter  # noqa: F401
    except Exception:
        engine = "openpyxl"
    with pd.ExcelWriter(buffer, engine=engine) as writer:
        df_lote.to_excel(writer, sheet_name="Resultados", index=False)
        df_top80.to_excel(writer, sheet_name="Top_80_Pareto", index=False)
    st.download_button("📥 Baixar Excel Completo", buffer.getvalue(),
                       file_name="simulacao_cr.xlsx",
                       mime="application/vnd.ms-excel")
