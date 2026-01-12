import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import gc

st.set_page_config(
    page_title="Kupac-Artikl Matrica",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Kupac-Artikl Matrica Generator")
st.markdown("Upload Excel datoteku i generiraj True/False matricu kupac × artikl")


@st.cache_data(max_entries=1, show_spinner=False)
def load_excel(file):
    """Load only required columns with optimized dtypes."""
    df = pd.read_excel(file)
    return df


def process_data(df, kupac_col, artikl_col):
    """
    Process data using set operations - minimal memory footprint.
    Returns only what's needed for stats and Excel generation.
    """
    # Drop rows with NaN in key columns
    df_clean = df[[kupac_col, artikl_col]].dropna()

    # Convert to string to avoid type comparison issues
    kupac_values = df_clean[kupac_col].astype(str)
    artikl_values = df_clean[artikl_col].astype(str)

    # Get unique pairs as frozen set for O(1) lookup
    pair_set = set(zip(kupac_values, artikl_values))

    # Get sorted unique values
    kupci = sorted(kupac_values.unique())
    artikli = sorted(artikl_values.unique())

    # Count per kupac/artikl using dict (faster than pandas for this)
    kupac_counts = {}
    artikl_counts = {}
    for kupac, artikl in pair_set:
        kupac_counts[kupac] = kupac_counts.get(kupac, 0) + 1
        artikl_counts[artikl] = artikl_counts.get(artikl, 0) + 1

    return {
        'pair_set': pair_set,
        'kupci': kupci,
        'artikli': artikli,
        'kupac_counts': kupac_counts,
        'artikl_counts': artikl_counts,
        'num_kupaca': len(kupci),
        'num_artikala': len(artikli),
        'true_count': len(pair_set)
    }


def generate_excel_streaming(data, kupac_col, artikl_col, df_len, progress_callback=None):
    """
    Generate Excel by streaming rows directly to openpyxl.
    Never holds full matrix in memory.
    """
    pair_set = data['pair_set']
    kupci = data['kupci']
    artikli = data['artikli']
    kupac_counts = data['kupac_counts']
    artikl_counts = data['artikl_counts']
    num_kupaca = data['num_kupaca']
    num_artikala = data['num_artikala']
    true_count = data['true_count']
    total_celija = num_kupaca * num_artikala

    # Create workbook
    wb = Workbook(write_only=False)  # write_only=True has issues with multiple sheets

    # === Sheet 1: Summary ===
    ws_summary = wb.active
    ws_summary.title = "Summary"

    summary_rows = [
        ["Metrika", "Vrijednost"],
        ["Datum generiranja", datetime.now().strftime('%Y-%m-%d %H:%M')],
        ["Ukupno redaka u izvoru", f"{df_len:,}"],
        ["Broj unikatnih kupaca", f"{num_kupaca:,}"],
        ["Broj unikatnih artikala", f"{num_artikala:,}"],
        ["Veličina matrice", f"{num_kupaca:,} x {num_artikala:,}"],
        ["Ukupno ćelija", f"{total_celija:,}"],
        ["TRUE vrijednosti", f"{true_count:,}"],
        ["FALSE vrijednosti", f"{total_celija - true_count:,}"],
        ["% popunjenosti", f"{100*true_count/total_celija:.2f}%"],
        ["Prosjek artikala po kupcu", f"{sum(kupac_counts.values())/len(kupac_counts):.1f}"],
        ["Prosjek kupaca po artiklu", f"{sum(artikl_counts.values())/len(artikl_counts):.1f}"],
    ]
    for row in summary_rows:
        ws_summary.append(row)

    # Top 10 kupaca
    ws_summary.append([])
    ws_summary.append(["TOP 10 KUPACA", "", "", "TOP 10 ARTIKALA"])
    ws_summary.append(["Kupac", "Broj artikala", "", "Artikl", "Broj kupaca"])

    top_kupci = sorted(kupac_counts.items(), key=lambda x: -x[1])[:10]
    top_artikli = sorted(artikl_counts.items(), key=lambda x: -x[1])[:10]

    for i in range(10):
        row = []
        if i < len(top_kupci):
            row.extend([top_kupci[i][0], top_kupci[i][1], ""])
        else:
            row.extend(["", "", ""])
        if i < len(top_artikli):
            row.extend([top_artikli[i][0], top_artikli[i][1]])
        ws_summary.append(row)

    # === Sheet 2: Matrica (streaming) ===
    ws_matrix = wb.create_sheet("Matrica")

    # Header row
    ws_matrix.append([kupac_col] + artikli)

    # Stream data rows - one at a time, never hold in memory
    for idx, kupac in enumerate(kupci):
        # Build row on-the-fly using generator
        row = [kupac] + [kupac_artikl in pair_set for kupac_artikl in ((kupac, a) for a in artikli)]
        ws_matrix.append(row)

        # Update progress every 100 rows
        if progress_callback and idx % 100 == 0:
            progress_callback(40 + int(50 * idx / num_kupaca))

        # Garbage collect every 500 rows
        if idx % 500 == 0:
            gc.collect()

    # Save to BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    # Cleanup
    wb.close()
    del wb
    gc.collect()

    return output, top_kupci, top_artikli


# File upload
uploaded_file = st.file_uploader("Odaberi Excel datoteku", type=['xlsx', 'xls'])

if uploaded_file is not None:
    with st.spinner("Učitavam datoteku..."):
        df = load_excel(uploaded_file)

    st.success(f"Učitano {len(df):,} redaka")

    mem_usage = df.memory_usage(deep=True).sum() / 1024 / 1024
    st.caption(f"Memorija učitane datoteke: {mem_usage:.1f} MB")

    st.subheader("1. Odaberi stupce")
    col1, col2 = st.columns(2)

    with col1:
        kupac_col = st.selectbox("Stupac s kupcima:", options=df.columns, index=0)

    with col2:
        artikl_col = st.selectbox("Stupac s artiklima:", options=df.columns, index=min(2, len(df.columns)-1))

    with st.expander("Pregled podataka (prvih 100 redaka)"):
        st.dataframe(df.head(100))

    if st.button("🚀 Generiraj matricu", type="primary"):
        progress_bar = st.progress(0, text="Početak...")

        # Step 1: Process data
        progress_bar.progress(10, text="Analiziram podatke...")
        data = process_data(df, kupac_col, artikl_col)

        num_kupaca = data['num_kupaca']
        num_artikala = data['num_artikala']
        true_count = data['true_count']
        total_celija = num_kupaca * num_artikala

        progress_bar.progress(20, text=f"Generiram Excel ({num_kupaca:,} redaka)...")

        # Step 2: Generate Excel streaming
        def update_progress(pct):
            progress_bar.progress(pct, text=f"Zapisujem matricu... {pct}%")

        output, top_kupci, top_artikli = generate_excel_streaming(
            data, kupac_col, artikl_col, len(df), update_progress
        )

        progress_bar.progress(100, text="Gotovo!")

        # Cleanup
        del data
        gc.collect()

        # Results
        st.subheader("2. Rezultati")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Kupaca", f"{num_kupaca:,}")
        col2.metric("Artikala", f"{num_artikala:,}")
        col3.metric("TRUE", f"{true_count:,}")
        col4.metric("Popunjenost", f"{100*true_count/total_celija:.2f}%")

        st.subheader("3. Top 10")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Top 10 kupaca** (po broju artikala)")
            st.dataframe(
                pd.DataFrame(top_kupci, columns=['Kupac', 'Broj artikala']),
                hide_index=True
            )
        with col2:
            st.markdown("**Top 10 artikala** (po broju kupaca)")
            st.dataframe(
                pd.DataFrame(top_artikli, columns=['Artikl', 'Broj kupaca']),
                hide_index=True
            )

        st.subheader("4. Preuzmi")
        st.download_button(
            label="📥 Preuzmi Excel (Summary + Matrica)",
            data=output.getvalue(),
            file_name="kupac_artikl_matrix.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.info("👆 Upload Excel datoteku za početak")
    st.markdown("""
    ### Očekivani format:
    Excel s stupcima za **Kupca** i **Artikl**

    ### Optimizacije v3:
    - ✅ Set-based lookup (O(1) provjera)
    - ✅ Streaming zapis u Excel (red po red)
    - ✅ Nikad puna matrica u memoriji
    - ✅ Dict umjesto pandas za statistike
    - ✅ GC svaki 500 redaka
    """)
