if uploaded_file is not None:
    try:
        # Pasul 1: Procesează fișierul încărcat
        new_df = pd.read_excel(uploaded_file)
        draw_cols = ['Nr.1', 'Nr.2', 'Nr.3', 'Nr.4', 'Nr.5', 'Nr.6']
        new_df['Data'] = pd.to_datetime(new_df['Data'], errors='coerce')
        new_df = new_df.dropna(subset=['Data'])
        new_df[draw_cols] = new_df[draw_cols].astype(int)

        with sqlite3.connect("loto_data.db") as conn:
            try:
                existing_df = pd.read_sql("SELECT * FROM loto_draws", conn)
            except pd.io.sql.DatabaseError:
                existing_df = pd.DataFrame(columns=['Data'] + draw_cols)

            combined_df = pd.concat([existing_df, new_df], ignore_index=True).drop_duplicates(subset=["Data"] + draw_cols)
            combined_df.to_sql("loto_draws", conn, if_exists="replace", index=False)
        st.success(f"✅ {len(new_df)} extrageri noi au fost adăugate. Total actual: {len(combined_df)}.")

        # Pasul 2: Dacă procesarea a reușit, încearcă recalcularea predicției ML
        try:
            recent_df = combined_df.sort_values("Data", ascending=False).head(20)
            if len(recent_df) >= 20:
                X_train = recent_df[draw_cols].astype(int)
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

                # Pasul 3: Dacă recalcularea ML a reușit, încearcă salvarea în istoric
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
                    st.warning(f"A apărut o eroare la salvarea în istoric: {e_hist}")
            
            else:
                st.warning("Nu există suficiente date (minim 20 de extrageri) pentru a recalcula predicția ML.")
        
        except Exception as e_ml:
            st.warning(f"Nu s-a putut recalcula predicția ML: {e_ml}")

    except Exception as e_main:
        st.error(f"Eroare la procesarea fișierului: {e_main}")