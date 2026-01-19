import streamlit as st
import json
import pandas as pd
from pathlib import Path

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(page_title="Special Pool Settlement Tool", layout="wide")

# --------------------------------------------------
# THEME (GREY + BLUE)
# --------------------------------------------------
st.markdown("""
<style>
body { background-color: #f2f4f7; }
.card {
    background:#ffffff;
    padding:18px;
    border-radius:10px;
    border-left:5px solid #1f4fd8;
    box-shadow:0px 2px 6px rgba(0,0,0,0.08);
    margin-bottom:15px;
}
.kpi {
    background:#eef2ff;
    padding:16px;
    border-radius:10px;
    text-align:center;
}
.kpi h3 { margin:0; color:#1f4fd8; }
.kpi .count { font-size:18px; font-weight:700; }
.kpi .amount { font-size:15px; margin-top:4px; }
.big-text { font-size:20px; font-weight:600; }
</style>
""", unsafe_allow_html=True)

st.title("📊 Special Pool – Contract Settlement Tool")
st.caption("Search by Contract ID to view linked contracts and settlement eligibility")

# --------------------------------------------------
# LOAD JSON
# --------------------------------------------------
json_path = Path("output.json")
if not json_path.exists():
    st.error("❌ output.json not found")
    st.stop()

with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

df = pd.DataFrame(data["contracts"])

# --------------------------------------------------
# DATA CLEANING
# --------------------------------------------------
df["contract_no"] = df["contract_no"].astype(str)
df["gnpa_flag"] = df["gnpa_flag"].astype(str).str.upper().str.strip()

def clean_seasoning(v):
    if pd.isna(v): return 0.0
    return float(str(v).replace("%","").strip())

df["seasoning_pct"] = df["seasoning_pct"].apply(clean_seasoning)

for c in ["finance_amount","od_principal","od_interest","contract_balance_jan_26"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

# --------------------------------------------------
# SETTLEMENT LOGIC
# --------------------------------------------------
def settlement_offer(flag, seasoning, bal):
    if flag == "LSA": return "Contact Manager"
    if seasoning >= 60: return round(bal*0.75,2)
    if seasoning >= 30: return round(bal*0.55,2)
    return round(bal*0.40,2)

# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------
if "contract_id" not in st.session_state:
    st.session_state.contract_id = ""

def reset_app():
    st.session_state.clear()
    st.rerun()

# --------------------------------------------------
# SEARCH INPUT
# --------------------------------------------------
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2 = st.columns([4,1])
    with c1:
        st.session_state.contract_id = st.text_input(
            "🔍 Enter Contract ID",
            st.session_state.contract_id
        )
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("🔄 Reset", on_click=reset_app)
    st.markdown('</div>', unsafe_allow_html=True)

contract_id = st.session_state.contract_id.strip()

# --------------------------------------------------
# SEARCH RESULT
# --------------------------------------------------
if contract_id:
    found = df[df["contract_no"].str.upper() == contract_id.upper()]

    if found.empty:
        st.error("❌ Contract not found")
    else:
        row = found.iloc[0]
        customer_id = row["customer_id"]
        customer_name = row["customer_name"]

        linked = df[df["customer_id"] == customer_id].copy()

        # ---------------- CUSTOMER SUMMARY ----------------
        st.markdown(f"""
        <div class="card">
            <div class="big-text">👤 {customer_name}</div>
            <div>Customer ID: <b>{customer_id}</b></div>
        </div>
        """, unsafe_allow_html=True)

        # ---------------- FLAG-WISE COUNTS + AMOUNTS ----------------
        def block(title, count, amount):
            return f"""
            <div class="kpi">
                <h3>{title}</h3>
                <div class="count">{count} Contracts</div>
                <div class="amount">₹{amount:,.2f}</div>
            </div>
            """

        g_df = linked[linked["gnpa_flag"]=="GNPA"]
        n_df = linked[linked["gnpa_flag"]=="NON GNPA"]
        l_df = linked[linked["gnpa_flag"]=="LSA"]

        k1, k2, k3 = st.columns(3)
        k1.markdown(block("GNPA", len(g_df), g_df["contract_balance_jan_26"].sum()), unsafe_allow_html=True)
        k2.markdown(block("Non GNPA", len(n_df), n_df["contract_balance_jan_26"].sum()), unsafe_allow_html=True)
        k3.markdown(block("LSA", len(l_df), l_df["contract_balance_jan_26"].sum()), unsafe_allow_html=True)

        # ---------------- CONTRACT DETAILS ----------------
        linked["Outstanding Amount"] = (linked["od_principal"] + linked["od_interest"]).round(2)

        linked["Settlement Offer"] = linked.apply(
            lambda r: settlement_offer(r["gnpa_flag"], r["seasoning_pct"], r["contract_balance_jan_26"]),
            axis=1
        )

        linked["Seasoning (%)"] = linked["seasoning_pct"].apply(
            lambda x: "-" if x==0 else f"{x:.0f}%"
        )

        display = linked[
            ["contract_no","gnpa_flag","Seasoning (%)","od_principal","od_interest",
             "Outstanding Amount","contract_balance_jan_26","Settlement Offer"]
        ]

        # ---------------- TOTAL ROW ----------------
        total = {
            "contract_no":"TOTAL",
            "gnpa_flag":"",
            "Seasoning (%)":"",
            "od_principal":display["od_principal"].sum(),
            "od_interest":display["od_interest"].sum(),
            "Outstanding Amount":display["Outstanding Amount"].sum(),
            "contract_balance_jan_26":display["contract_balance_jan_26"].sum(),
            "Settlement Offer":""
        }

        display = pd.concat([display, pd.DataFrame([total])], ignore_index=True)

        st.markdown("### 📄 Contract-wise Details")

        st.dataframe(
            display.style.format({
                "od_principal":"₹{:,.2f}",
                "od_interest":"₹{:,.2f}",
                "Outstanding Amount":"₹{:,.2f}",
                "contract_balance_jan_26":"₹{:,.2f}",
                "Settlement Offer":lambda x: f"₹{x:,.2f}" if isinstance(x,(int,float)) else x
            }),
            use_container_width=True
        )

st.caption("ⓘ LSA settlements require manager approval. Amounts are indicative.")
