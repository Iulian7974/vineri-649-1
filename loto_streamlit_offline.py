import streamlit as st
import pandas as pd
import json
import sqlite3
import os

st.set_page_config(page_title="Loto 6/49 Offline", layout="centered")
st.title("📊 Loto 6/49 - Vizualizare Offline")

# === Frecvență din JSON ===
st.subheader("🔢 Frecvența numerelor (all time)")
try:
    with open("loto_frequency.json") as f:
        freq = json.load(f)
    df_freq = pd.DataFrame({"Număr": freq["labels"], "Frecvență": freq["values"]})
    df_freq = df_freq.sort_values("Frecvență", ascending=False)
    st.bar_chart(df_freq.set_index("Număr"))
except Exception as e:
    st.warning(f"Nu s-a putut încărca frecvența: {e}")

# === Microtrend ultimele 20 ===
st.subheader("📈 Microtrend pe ultimele 20 extrageri")
try:
    with open("microtrend_20.json") as f:
        trends = json.load(f)
    numar_ales = st.number_input("Alege un număr (1-49)", min_value=1, max_value=49, value=17)
    trend = next((item for item in trends if item["number"] == numar_ales), None)
    if trend:
        df_trend = pd.DataFrame(trend["trend"])
        st.line_chart(df_trend.set_index("x"))
except Exception as e:
    st.warning(f"Eroare la trend: {e}")

# === Co-apariții ===
st.subheader("🔗 Matrice co-apariții")
try:
    with open("coappear_matrix.json") as f:
        matrix = json.load(f)
    df_matrix = pd.DataFrame(matrix["matrix"], index=matrix["labels"], columns=matrix["labels"])
    st.dataframe(df_matrix)
except Exception as e:
    st.warning(f"Eroare la matrice: {e}")

# === Filtrare locală din baza de date ===
st.subheader("🎯 Filtrare extrageri locale")
an = st.selectbox("Alege anul", ["2023", "2024", "2025"])
numar = st.number_input("Număr de urmărit", min_value=1, max_value=49, value=17, key="numar_urmarit")

try:
    with sqlite3.connect("loto_data.db") as conn:
        query = f"""
            SELECT * FROM loto_draws
            WHERE strftime('%Y', Data) = '{an}'
            AND ({' OR '.join([f'"Nr.{i}" = {numar}' for i in range(1, 7)])})
            ORDER BY Data DESC
        """
        df_filtrat = pd.read_sql(query, conn)
        st.dataframe(df_filtrat)
except Exception as e:
    st.warning(f"Nu s-au putut încărca extragerile. Baza de date va fi creată la prima încărcare a unui fișier Excel.")


# === Predicții generate automat ===
st.subheader("🔮 Cele mai bune 5 predicții (din top 20 frecvente)")
try:
    with open("predictii_top5.json") as f:
        pred_data = json.load(f)
    st.markdown(f"**Top 20 numere frecvente:** {sorted(pred_data['top20'])}")
    for i, pred in enumerate(pred_data["predictii"], 1):
        st.markdown(f"**Predicția {i}:** 🎯 {sorted(pred)}")
except Exception as e:
    st.warning(f"Nu s-au putut încărca predicțiile: {e}")


# === Predicție ML pe baza celor mai recente 20 de extrageri ===
st.subheader("🔬 Predicție ML (ultimele 20 extrageri)")
try:
    with open("predictie_ml_rf_20draws.json") as f:
        ml20 = json.load(f)
    st.success(f"📈 Predicție ML: {ml20['predictie_model_20draws']}")
except Exception as e:
    st.warning(f"Predicția nu este disponibilă: {e}")


# === Simulare inteligentă: Predicții pe baza scorurilor de probabilitate ===
st.subheader("🎯 Simulare inteligentă: predicții bazate pe probabilitate")
try:
    with open("simulare_predictii_interactive.json") as f:
        simulare = json.load(f)
    st.image("heatmap_probabilitati_20.png", caption="📊 Heatmap scoruri pe ultimele 20 extrageri", use_container_width=True)
    st.markdown(f"**🔝 Top 20 scoruri:** {simulare['top20_probabilitati']}")
    st.markdown("**🎰 Combinații sugerate (aleator din top 20):**")
    for idx, combo in enumerate(simulare['combinatii_sugerate'], 1):
        st.markdown(f"{idx}. {combo}")
except Exception as e:
    st.warning(f"Simularea nu este disponibilă: {e}")


# === Actualizare bază de date din fișier Excel nou ===
st.subheader("📤 Actualizează extragerile din fișier Excel")
uploaded_file = st.file_uploader("Încarcă un fișier Excel cu extrageri noi", type=["xlsx"])

if uploaded_file is not None:
    try:
        new_df = pd.read_excel(uploaded_file)
        draw_cols = ['Nr.1', 'Nr.2', 'Nr.3', 'Nr.4', 'Nr.5', 'Nr.6']
        new_df['Data'] = pd.to_datetime(new_df['Data'], errors='coerce')
        new_df[draw_cols] = new_df[draw_cols].map(int) # .map() is the modern replacement for .applymap()
        new_df = new_df.dropna(subset=['Data'])

        with sqlite3.connect("loto_data.db") as conn:
            try:
                # Check if table exists, if not, create an empty DataFrame
                existing_df = pd.read_sql("SELECT * FROM loto_draws", conn)
            except pd.io.sql.DatabaseError:
                existing_df = pd.DataFrame(columns=['Data'] + draw_cols)

            combined_df = pd.concat([existing_df, new_df], ignore_index=True).drop_duplicates(subset=["Data"] + draw_cols)
            combined_df.to_sql("loto_draws", conn, if_exists="replace", index=False)
            st.success(f"✅ {len(new_df)} extrageri noi au fost adăugate. Total actual: {len(combined_df)}.")
            
            # Recalculare și salvare doar dacă actualizarea a avut succes
            # === Recalculare automată a predicției ML după actualizare ===
            try:
                recent_df = combined_df.sort_values("Data", ascending=False).head(20)
                if len(recent_df) >= 20:
                    X_train = recent_df[draw_cols]
                    y_preds = []

                    from sklearn.ensemble import RandomForestClassifier
                    for col in draw_cols:
                        model = RandomForestClassifier(n_estimators=100, random_state=42)
                        model.fit(X_train.drop(columns=[col]), X_train[col])
                        pred = model.predict([X_train.drop(columns=[col]).iloc[-1]])[0]
                        y_preds.append(int(pred))

                    with open("predictie_ml_rf_20draws.json", "w") as f:
                        json.dump({"predictie_model_20draws": y_preds}, f)

                    st.success(f"🔁 Predicția ML a fost recalculată: {y_preds}")

                    # === Salvare istoric predicții ML ===
                    try:
                        istoric_path = "istoric_predictii_ml.json"
                        if os.path.exists(istoric_path):
                            with open(istoric_path, "r") as f:
                                istoric = json.load(f)
                        else:
                            istoric = []

                        istoric.append({
                            "data": str(pd.Timestamp.now().date()),
                            "predictie": y_preds
                        })

                        with open(istoric_path, "w") as f:
                            json.dump(istoric, f, indent=2)

                        st.info("📚 Predicția ML a fost salvată în istoric.")
                    except Exception as e_hist:
                        st.warning(f"Eroare la salvarea în istoric: {e_hist}")
                else:
                    st.warning("Nu există suficiente date (minim 20 de extrageri) pentru a recalcula predicția ML.")
            except Exception as e_ml:
                st.warning(f"Nu s-a putut recalcula predicția ML: {e_ml}")

    except Exception as e_main:
        st.error(f"Eroare la procesarea fișierului: {e_main}")