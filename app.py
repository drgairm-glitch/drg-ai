import os
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="DRG asistent", page_icon="🩺", layout="wide")

VECTOR_STORE_ID = "vs_69e35e655f248191b7d868d72e0186d5"

st.title("DRG asistent")
st.caption("Vlož epikrízu, operačný protokol alebo otázku. Systém najprv vyhľadá v dokumentoch a až potom odpovie.")

SYSTEM_PROMPT = """
Si skúsený DRG kóder pre slovenský systém DRG (2025) so silným klinickým porozumením naprieč medicínskymi odbormi.

Tvoj cieľ:
- správne navrhovať diagnózy, výkony a pripočítateľné položky
- používať výhradne nahraté dokumenty
- nevymýšľať kódy
- pri neistote uviesť alternatívy
- pri krátkej otázke odpovedať stručne
- pri epikríze alebo operačnom protokole odpovedať štruktúrovane

DÔLEŽITÉ:
Pred odpoveďou vždy využi nahraté dokumenty. Nepoužívaj vlastnú pamäť, ak odpoveď má byť v dokumentoch.
Ak informáciu nenájdeš v dokumentoch, napíš: "nenájdené v dokumentoch".

SYNONYMÁ:
Prepájaj latinské, slovenské, české a opisné názvy.
Príklady:
- cholecystolitiáza = cholelitiáza = žlčníkové kamene = kameň v žlčníku
- choledocholitiáza = kameň v žlčových cestách
- appendicitída = zápal appendixu = zápal slepého čreva
- ileus = nepriechodnosť čreva
- peritonitída = zápal pobrušnice
- pankreatitída = zápal pankreasu

PRESNOSŤ KÓDOV:
Vždy uvádzaj najpresnejší dostupný úplný kód podľa dokumentov.
Nikdy neskracuj MKCH kódy.
Ak existuje K80.20, neodpovedaj iba K80.2.
Ak nevieš určiť presný podkód, napíš: "presný podkód neviem určiť z dostupného textu".

KLINICKÁ INTERPRETÁCIA:
Pri výkonoch rozlišuj:
- resekcia = odstránenie tkaniva
- bypass = obchádzka
- anastomóza = spojenie
- drenáž = odvod
- revízia = kontrola alebo reoperácia
- sutúra = uzáver
- adhéziolýza = uvoľnenie zrastov
- diagnostický výkon
- terapeutický výkon

Zakázané chyby:
- bypass ≠ resekcia
- drenáž ≠ resekcia
- revízia ≠ primárny výkon
- diagnostický ≠ terapeutický výkon

ROZPOZNAJ TYP VSTUPU:
1. DRG ANALÝZA: epikríza / prepúšťacia správa / klinický prípad
2. OPERAČNÝ PROTOKOL
3. RÝCHLE VYHĽADÁVANIE: diagnóza / výkon / položka
4. DRG PRAVIDLÁ
5. CASE MIX INDEX / OPTIMALIZÁCIA

PRI KRÁTKOM DOTAZE:
Odpovedz stručne:
- najpravdepodobnejší úplný kód – názov
- max 3 alternatívy
- bez dlhého vysvetlenia

PRI EPIKRÍZE:
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

PRI OPERAČNOM PROTOKOLE:
TYP VÝKONU:
STRUČNÁ INTERPRETÁCIA:
HLAVNÝ VÝKON:
VÝKONY:
DOPLNKOVÉ VÝKONY:
PRIPOČÍTATEĽNÉ POLOŽKY:
CONFIDENCE:
CHÝBAJÚCE INFORMÁCIE:
ZDROJ:

PRI DRG PRAVIDLÁCH:
ODPOVEĎ:
PRAKTICKÝ ZÁVER:
PRÍKLAD:
ZDROJ:
"""


def classify_input(text: str) -> str:
    t = text.lower()

    op_words = [
        "operačný protokol", "operačný nález", "operácia", "laparotóm",
        "laparoskop", "resek", "anastom", "drenáž", "laváž", "sutúr",
        "adhéziolý", "implant", "stóm", "bypass"
    ]

    rule_words = [
        "môžem", "mozem", "spolu", "kombin", "koľko", "kolko",
        "pravidlo", "pravidlá", "kodov", "kódov", "zadať", "zadat",
        "hlavná diagnóza", "hlavna diagnoza"
    ]

    cmi_words = [
        "case mix", "cmi", "podkód", "podkod", "výnos", "vynos",
        "optimaliz", "čo chýba", "co chyba", "nezachyten"
    ]

    diagnosis_words = [
        "chole", "append", "ileus", "periton", "pankreat", "hernia",
        "seps", "diabet", "renal", "zlyhanie", "nádor", "nador",
        "karcin", "liti", "lith", "diagnóz", "diagnoz", "mkch"
    ]

    if any(w in t for w in cmi_words):
        return "CMI / optimalizácia"
    if any(w in t for w in op_words) and len(t) > 200:
        return "Operačný protokol"
    if any(w in t for w in rule_words):
        return "DRG pravidlá"
    if len(t) < 160 or any(w in t for w in diagnosis_words):
        return "Rýchle vyhľadávanie"
    return "DRG analýza"


def build_search_instruction(user_text: str, input_type: str) -> str:
    return f"""
TYP VSTUPU: {input_type}

PRED ODPOVEĎOU UROB TOTO:
1. Najprv vyhľadaj relevantné pasáže v nahratých dokumentoch.
2. Ak ide o diagnózu, hľadaj najmä v MKCH TXT súboroch a preferuj úplný najdlhší kód.
3. Ak ide o výkon, hľadaj najmä vo výkonových / ZZV / DRG dokumentoch.
4. Ak ide o pravidlá, hľadaj najmä v metodike a pravidlách kódovania.
5. Ak ide o epikrízu, vyhľadaj samostatne diagnózy, výkony a možné položky.
6. Nepouži vlastnú pamäť namiesto dokumentov.
7. Ak nájdeš viac kandidátov, vyber najpravdepodobnejší a uveď max 3 alternatívy.

TEXT POUŽÍVATEĽA:
{user_text}
"""


api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("Chýba OPENAI_API_KEY v Streamlit Secrets.")
    st.stop()

client = OpenAI(api_key=api_key)

user_text = st.text_area(
    "Sem vlož text",
    height=320,
    placeholder="Sem vlož epikrízu, operačný protokol alebo otázku..."
)

col1, col2 = st.columns([1, 3])
with col1:
    analyze = st.button("Analyzovať", type="primary")

if analyze:
    if not user_text.strip():
        st.warning("Najprv vlož text.")
        st.stop()

    input_type = classify_input(user_text)
    enriched_query = build_search_instruction(user_text, input_type)

    st.info(f"Rozpoznaný typ vstupu: {input_type}")

    with st.spinner("Vyhľadávam v dokumentoch a analyzujem..."):
        response = client.responses.create(
            model="gpt-5.4",
            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [VECTOR_STORE_ID],
                    "max_num_results": 12
                }
            ],
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": enriched_query},
            ],
        )

    st.subheader("Výsledok")
    st.write(response.output_text)
