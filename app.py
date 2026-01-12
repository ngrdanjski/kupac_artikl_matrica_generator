import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from io import BytesIO

st.set_page_config(
    page_title="Kupac-Artikl Matrica",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Kupac-Artikl Matrica Generator")
st.markdown("Upload Excel datoteku i generiraj True/False matricu kupac × artikl")

# File upload
uploaded_file = st.file_uploader("Odaberi Excel datoteku", type=['xlsx', 'xls'])

if uploaded_file is not None:
    # Load data
    with st.spinner("Učitavam datoteku..."):
        df = pd.read_excel(uploaded_file)

    st.success(f"Učitano {len(df):,} redaka")

    # Show columns and let user select
    st.subheader("1. Odaberi stupce")
    col1, col2 = st.columns(2)

    with col1:
        kupac_col = st.selectbox(
            "Stupac s kupcima:",
            options=df.columns,
            index=0 if len(df.columns) > 0 else None
        )

    with col2:
        artikl_col = st.selectbox(
            "Stupac s artiklima:",
            options=df.columns,
            index=2 if len(df.columns) > 2 else None
        )

    # Preview data
    with st.expander("Pregled podataka (prvih 100 redaka)"):
        st.dataframe(df.head(100))

    # Generate matrix button
    if st.button("🚀 Generiraj matricu", type="primary"):

        progress = st.progress(0, text="Početak...")

        # Step 1: Create combinations
        progress.progress(20, text="Kreiram kombinacije kupac-artikl...")
        kombinacije = df.groupby([kupac_col, artikl_col]).size().reset_index(name='count')

        # Step 2: Create matrix
        progress.progress(40, text="Kreiram matricu...")
        matrix = kombinacije.pivot_table(
            index=kupac_col,
            columns=artikl_col,
            values='count',
            aggfunc='sum',
            fill_value=0
        )
        matrix = matrix > 0

        # Stats
        num_kupaca = matrix.shape[0]
        num_artikala = matrix.shape[1]
        total_celija = num_kupaca * num_artikala
        true_count = int(matrix.sum().sum())

        progress.progress(60, text="Kreiram summary...")

        # Top 10
        kupci_po_artiklima = matrix.sum(axis=1).sort_values(ascending=False)
        top_kupci = kupci_po_artiklima.head(10).reset_index()
        top_kupci.columns = ['Kupac', 'Broj artikala']

        artikli_po_kupcima = matrix.sum(axis=0).sort_values(ascending=False)
        top_artikli = artikli_po_kupcima.head(10).reset_index()
        top_artikli.columns = ['Artikl', 'Broj kupaca']

        progress.progress(80, text="Spremam Excel...")

        # Create Excel in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = {
                'Metrika': [
                    'Datum generiranja',
                    'Ukupno redaka u izvoru',
                    'Broj unikatnih kupaca',
                    'Broj unikatnih artikala',
                    'Veličina matrice',
                    'Ukupno ćelija',
                    'TRUE vrijednosti',
                    'FALSE vrijednosti',
                    '% popunjenosti',
                    'Prosjek artikala po kupcu',
                    'Prosjek kupaca po artiklu'
                ],
                'Vrijednost': [
                    datetime.now().strftime('%Y-%m-%d %H:%M'),
                    f'{len(df):,}',
                    f'{num_kupaca:,}',
                    f'{num_artikala:,}',
                    f'{num_kupaca:,} x {num_artikala:,}',
                    f'{total_celija:,}',
                    f'{true_count:,}',
                    f'{total_celija - true_count:,}',
                    f'{100*true_count/total_celija:.2f}%',
                    f'{kupci_po_artiklima.mean():.1f}',
                    f'{artikli_po_kupcima.mean():.1f}'
                ]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
            top_kupci.to_excel(writer, sheet_name='Summary', index=False, startrow=14, startcol=0)
            top_artikli.to_excel(writer, sheet_name='Summary', index=False, startrow=14, startcol=3)

            # Matrix sheet
            matrix.to_excel(writer, sheet_name='Matrica')

        progress.progress(100, text="Gotovo!")

        # Show results
        st.subheader("2. Rezultati")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Kupaca", f"{num_kupaca:,}")
        col2.metric("Artikala", f"{num_artikala:,}")
        col3.metric("TRUE", f"{true_count:,}")
        col4.metric("Popunjenost", f"{100*true_count/total_celija:.2f}%")

        # Top 10 tables
        st.subheader("3. Top 10")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Top 10 kupaca** (po broju artikala)")
            st.dataframe(top_kupci, hide_index=True)
        with col2:
            st.markdown("**Top 10 artikala** (po broju kupaca)")
            st.dataframe(top_artikli, hide_index=True)

        # Download button
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
    ### Očekivani format datoteke:
    Excel s podacima o kupovinama gdje postoje stupci za:
    - **Kupac** (naziv kupca/korisnika)
    - **Artikl** (šifra ili naziv artikla)

    ### Rezultat:
    - **Sheet 1 (Summary)**: Statistike + Top 10 liste
    - **Sheet 2 (Matrica)**: Kupac × Artikl matrica (True/False)
    """)
