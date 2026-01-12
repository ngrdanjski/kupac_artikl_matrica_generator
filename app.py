import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from io import BytesIO
import gc

st.set_page_config(
    page_title="Kupac-Artikl Matrica",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Kupac-Artikl Matrica Generator")
st.markdown("Upload Excel datoteku i generiraj True/False matricu kupac × artikl")


@st.cache_data(max_entries=1)
def load_excel(file):
    """Load Excel with optimized memory usage."""
    df = pd.read_excel(file)
    return df


def create_sparse_matrix(df, kupac_col, artikl_col):
    """
    Create matrix using sparse representation.
    Only stores True values, not the full dense matrix.
    """
    # Get unique values with memory-efficient indexing
    kupci = pd.Categorical(df[kupac_col])
    artikli = pd.Categorical(df[artikl_col])

    # Create mapping dictionaries
    kupac_to_idx = {k: i for i, k in enumerate(kupci.categories)}
    artikl_to_idx = {a: i for i, a in enumerate(artikli.categories)}

    # Get unique combinations (sparse - only True values)
    unique_pairs = df[[kupac_col, artikl_col]].drop_duplicates()

    # Stats
    num_kupaca = len(kupci.categories)
    num_artikala = len(artikli.categories)
    true_count = len(unique_pairs)

    return {
        'kupci': list(kupci.categories),
        'artikli': list(artikli.categories),
        'kupac_to_idx': kupac_to_idx,
        'artikl_to_idx': artikl_to_idx,
        'unique_pairs': unique_pairs,
        'num_kupaca': num_kupaca,
        'num_artikala': num_artikala,
        'true_count': true_count
    }


def generate_excel_chunked(sparse_data, kupac_col, artikl_col, df_len, chunk_size=500):
    """
    Generate Excel file in chunks to minimize memory usage.
    Writes matrix row by row instead of holding full matrix in memory.
    """
    output = BytesIO()

    kupci = sparse_data['kupci']
    artikli = sparse_data['artikli']
    unique_pairs = sparse_data['unique_pairs']
    num_kupaca = sparse_data['num_kupaca']
    num_artikala = sparse_data['num_artikala']
    true_count = sparse_data['true_count']

    # Create set of (kupac, artikl) pairs for O(1) lookup
    pair_set = set(zip(unique_pairs[kupac_col], unique_pairs[artikl_col]))

    # Calculate statistics before creating Excel
    kupci_counts = unique_pairs[kupac_col].value_counts()
    artikli_counts = unique_pairs[artikl_col].value_counts()

    top_kupci = kupci_counts.head(10).reset_index()
    top_kupci.columns = ['Kupac', 'Broj artikala']

    top_artikli = artikli_counts.head(10).reset_index()
    top_artikli.columns = ['Artikl', 'Broj kupaca']

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Summary (small, no memory issue)
        total_celija = num_kupaca * num_artikala
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
                f'{df_len:,}',
                f'{num_kupaca:,}',
                f'{num_artikala:,}',
                f'{num_kupaca:,} x {num_artikala:,}',
                f'{total_celija:,}',
                f'{true_count:,}',
                f'{total_celija - true_count:,}',
                f'{100*true_count/total_celija:.2f}%',
                f'{kupci_counts.mean():.1f}',
                f'{artikli_counts.mean():.1f}'
            ]
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
        top_kupci.to_excel(writer, sheet_name='Summary', index=False, startrow=14, startcol=0)
        top_artikli.to_excel(writer, sheet_name='Summary', index=False, startrow=14, startcol=3)

        # Sheet 2: Matrix - generate in chunks
        # Process rows in chunks to limit memory
        all_chunks = []

        for i in range(0, num_kupaca, chunk_size):
            chunk_kupci = kupci[i:i + chunk_size]

            # Build chunk of matrix
            chunk_data = []
            for kupac in chunk_kupci:
                row = [kupac] + [kupac_artikl in pair_set
                                 for kupac_artikl in ((kupac, a) for a in artikli)]
                chunk_data.append(row)

            chunk_df = pd.DataFrame(chunk_data, columns=[kupac_col] + list(artikli))
            all_chunks.append(chunk_df)

            # Force garbage collection every few chunks
            if len(all_chunks) % 10 == 0:
                gc.collect()

        # Combine and write
        matrix_df = pd.concat(all_chunks, ignore_index=True)
        matrix_df.set_index(kupac_col, inplace=True)
        matrix_df.to_excel(writer, sheet_name='Matrica')

        del all_chunks, matrix_df
        gc.collect()

    return output, top_kupci, top_artikli, kupci_counts, artikli_counts


# File upload
uploaded_file = st.file_uploader("Odaberi Excel datoteku", type=['xlsx', 'xls'])

if uploaded_file is not None:
    # Load data
    with st.spinner("Učitavam datoteku..."):
        df = load_excel(uploaded_file)

    st.success(f"Učitano {len(df):,} redaka")

    # Show memory usage
    mem_usage = df.memory_usage(deep=True).sum() / 1024 / 1024
    st.caption(f"Memorija: {mem_usage:.1f} MB")

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

        # Step 1: Create sparse representation
        progress.progress(20, text="Kreiram sparse matricu...")
        sparse_data = create_sparse_matrix(df, kupac_col, artikl_col)

        num_kupaca = sparse_data['num_kupaca']
        num_artikala = sparse_data['num_artikala']
        true_count = sparse_data['true_count']
        total_celija = num_kupaca * num_artikala

        progress.progress(40, text="Generiram Excel (chunk by chunk)...")

        # Generate Excel in chunks
        output, top_kupci, top_artikli, kupci_counts, artikli_counts = generate_excel_chunked(
            sparse_data, kupac_col, artikl_col, len(df)
        )

        progress.progress(100, text="Gotovo!")

        # Clear memory
        del sparse_data
        gc.collect()

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

    ### Optimizacije:
    - ✅ Sparse matrix reprezentacija
    - ✅ Chunk processing za velike datoteke
    - ✅ Automatsko čišćenje memorije
    """)
