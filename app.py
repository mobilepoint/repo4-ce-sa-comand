import math
import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Recomandări comandă stoc", layout="wide")

st.title("Recomandări comandă pe baza mișcărilor de stoc (.xls)")
st.caption("Anteturi așteptate: Produs, Cod, Stoc initial, Intrari, Iesiri, Stoc final")

# ---- Parametri ----
colp = st.columns(4)
with colp[0]:
    zile_perioada = st.number_input("Zile în perioada analizată", min_value=1, value=45, step=1,
                                    help="01 Aug – 14 Sep = 45 zile")
with colp[1]:
    zile_tinta = st.number_input("Zile acoperire țintă (cerere viitoare)", min_value=1, value=30, step=1)
with colp[2]:
    lead_time = st.number_input("Lead time aprovizionare (zile)", min_value=0, value=0, step=1)
with colp[3]:
    buffer_siguranta = st.number_input("Buffer siguranță (zile)", min_value=0, value=0, step=1)

total_zile_cerere = zile_tinta + lead_time + buffer_siguranta

st.write(f"**Total zile cerere folosite în calcul:** {total_zile_cerere}")

uploaded = st.file_uploader("Încarcă fișierul .xls", type=["xls"])

def normalize_cols(cols):
    return [c.strip().lower().replace("  ", " ") for c in cols]

expected = {
    "produs": ["produs", "nume", "product", "denumire"],
    "cod": ["cod", "sku", "product code", "cod produs"],
    "stoc_initial": ["stoc initial", "stoc_initial", "initial stock"],
    "intrari": ["intrari", "entries", "in"],
    "iesiri": ["iesiri", "iesire", "out", "vanzari"],
    "stoc_final": ["stoc final", "stoc_final", "final stock", "stoc"]
}

def map_columns(df):
    lower_map = {col: col for col in df.columns}
    norm = {col: col.strip().lower() for col in df.columns}
    mapped = {}
    for need, aliases in expected.items():
        found = None
        for col, n in norm.items():
            if n in aliases:
                found = col
                break
        if not found:
            raise ValueError(f"Coloana lipsă: {need} (aliasuri acceptate: {', '.join(aliases)})")
        mapped[need] = found
    return mapped

if uploaded:
    try:
        df = pd.read_excel(uploaded, engine="xlrd")
    except Exception as e:
        st.error(f"Nu am putut citi fișierul .xls. Asigură-te că ai încărcat un XLS clasic. Eroare: {e}")
        st.stop()

    # Validare / mapare coloane
    try:
        colmap = map_columns(df)
    except ValueError as ve:
        st.error(str(ve))
        st.write("Coloane găsite:", list(df.columns))
        st.stop()

    # Curățare & tipuri
    def num(x):
        try:
            return float(str(x).replace(",", "."))
        except:
            return 0.0

    work = pd.DataFrame({
        "Produs": df[colmap["produs"]].astype(str).fillna(""),
        "Cod": df[colmap["cod"]].astype(str).fillna("")
    })
    work["Stoc initial"] = df[colmap["stoc_initial"]].apply(num).fillna(0.0)
    work["Intrari"] = df[colmap["intrari"]].apply(num).fillna(0.0)
    work["Iesiri"] = df[colmap["iesiri"]].apply(num).fillna(0.0)
    work["Stoc final"] = df[colmap["stoc_final"]].apply(num).fillna(0.0)

    # Consistență: Stoc_final ≈ Stoc_initial + Intrari − Iesiri
    work["Reconciliere"] = work["Stoc initial"] + work["Intrari"] - work["Iesiri"] - work["Stoc final"]
    inconsist = work[work["Reconciliere"].round(3) != 0]
    if not inconsist.empty:
        with st.expander("⚠️ Rânduri care nu se reconciliază (verifică datele)"):
            st.dataframe(inconsist)

    # Rată zilnică de vânzare (din Iesiri)
    work["Vanzari/zi"] = (work["Iesiri"] / max(zile_perioada, 1)).round(4)

    # Cerere viitoare pentru fereastra selectată
    work["Cerere viitoare"] = (work["Vanzari/zi"] * total_zile_cerere).round(2)

    # Recomandare comandă
    work["Cantitate de comandat"] = (
        (work["Cerere viitoare"] - work["Stoc final"]).apply(lambda x: max(0, math.ceil(x)))
    )

    # Filtrăm doar ce trebuie comandat
    comanda = work[work["Cantitate de comandat"] > 0].copy()

    # Ordine utilă
    comanda = comanda.sort_values(["Cantitate de comandat", "Vanzari/zi"], ascending=[False, False])

    st.subheader("📦 Produse de comandat")
    st.dataframe(comanda[[
        "Cod", "Produs", "Stoc final", "Iesiri", "Vanzari/zi", "Cerere viitoare", "Cantitate de comandat"
    ]], use_container_width=True)

    # Export CSV
    out_cols = ["Cod", "Produs", "Cantitate de comandat", "Stoc final", "Iesiri", "Vanzari/zi", "Cerere viitoare"]
    csv = comanda[out_cols].to_csv(index=False)
    st.download_button("⬇️ Descarcă CSV (comandă)", data=csv, file_name="comanda_recomandata.csv", mime="text/csv")

    # Rezumat
    st.write(f"**Total SKU-uri de comandat:** {len(comanda)}")
    st.write(f"**Total Iesiri (toată perioada):** {work['Iesiri'].sum():.0f}")
    st.write(f"**Total Stoc final (toate SKU-urile):** {work['Stoc final'].sum():.0f}")
else:
    st.info("Încarcă fișierul .xls cu mișcările de stoc ca să vezi recomandările.")
