# Kupac-Artikl Matrica Generator

Web aplikacija za generiranje True/False matrice kupac × artikl iz Excel podataka.

## Opis

Aplikacija uzima Excel datoteku s podacima o kupovinama i generira matricu koja pokazuje koji kupac je kupio koji artikl (True/False).

### Funkcionalnosti:
- Upload Excel datoteke
- Automatsko prepoznavanje stupaca
- Generiranje matrice kupac × artikl
- Summary statistike + Top 10 liste
- Download rezultata kao Excel

## Instalacija

```bash
pip install -r requirements.txt
```

## Pokretanje lokalno

```bash
streamlit run app.py
```

Aplikacija će biti dostupna na: http://localhost:8501

## Deploy na Streamlit Cloud

1. Fork ovaj repo
2. Idi na [share.streamlit.io](https://share.streamlit.io)
3. Poveži GitHub račun
4. Odaberi repo i `app.py`
5. Deploy!

## Očekivani format ulazne datoteke

Excel s podacima o kupovinama gdje postoje stupci za:
- **Kupac** (naziv kupca/korisnika)
- **Artikl** (šifra ili naziv artikla)

## Rezultat

Excel datoteka s 2 sheeta:
- **Summary**: Statistike + Top 10 kupaca/artikala
- **Matrica**: Kupac × Artikl matrica (True/False)

## Tehnologije

- Python 3.8+
- Streamlit
- Pandas
- OpenPyXL
