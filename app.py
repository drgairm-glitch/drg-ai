import os
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="DRG asistent", page_icon="🩺", layout="wide")

st.title("DRG asistent")
st.caption("Vlož epikrízu, operačný protokol alebo otázku na DRG pravidlá.")

SYSTEM_PROMPT = """
Si skúsený DRG kóder pre slovenský systém DRG (2025) so silným klinickým porozumením naprieč medicínskymi odbormi.

Tvoj hlavný cieľ je správne kódovanie (diagnózy, výkony, pripočítateľné položky).
Klinické myslenie používaj na presnú interpretáciu textu, ako skúsený lekár v danom odbore.

Používaj výhradne údaje z nahratých dokumentov.
Nevymýšľaj kódy ani názvy.
Ak informáciu nenájdeš → "nenájdené v dokumentoch".

Každú otázku vyhodnocuj samostatne.

Rozpoznaj typ otázky:
1. DRG ANALÝZA
2. OPERAČNÝ PROTOKOL
3. RÝCHLE VYHĽADÁVANIE
4. DRG PRAVIDLÁ
5. CASE MIX INDEX / OPTIMALIZÁCIA

Pri dlhom klinickom texte odpovedz štruktúrovane:

HLAVNÁ DIAGNÓZA:
VEDĽAJŠIE DIAGNÓZY:
HLAVNÝ VÝKON:
VÝKONY:
PRIPOČÍTATEĽNÉ POLOŽKY:
ODÔVODNENIE:
CONFIDENCE:
MOŽNÉ DOPLNENIA:
KONTROLA KONZISTENCIE:
CHÝBAJÚCE INFORMÁCIE:
POTENCIÁLNY DOPAD NA CASE MIX INDEX:
ZDROJ:

Pri krátkej otázke odpovedz stručne.
"""

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("Chýba OPENAI_API_KEY v Streamlit Secrets.")
    st.stop()

client = OpenAI(api_key=api_key)

user_text = st.text_area(
    "Sem vlož text",
    height=300,
    placeholder="Sem vlož epikrízu, operačný protokol alebo otázku..."
)

if st.button("Analyzovať", type="primary"):
    if not user_text.strip():
        st.warning("Najprv vlož text.")
        st.stop()

    with st.spinner("Analyzujem..."):
        response = client.responses.create(
    model="gpt-5.4",
    tools=[
        {
            "type": "file_search",
            "vector_store_ids": ["vs_69e35e655f248191b7d868d72e0186d5"]
        }
    ],
    input=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ],
)

    st.subheader("Výsledok")
    st.write(response.output_text)
