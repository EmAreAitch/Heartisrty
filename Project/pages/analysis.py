import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from prediction_model import predict_heart_disease
from db import get_db_connection  # Assuming you have a function to get DB connection


def get_user_details(user_id):
    # Establish a connection to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Query the database for the user's details based on user_id
        cursor.execute("""
            SELECT 
                Age, Sex, ChestPainType, RestingBP, Cholesterol, FastingBS, RestingECG, 
                MaxHR, ExerciseAngina, Oldpeak, ST_Slope
            FROM heart_patient_data 
            WHERE user_id = %s
        """, (user_id,))
        user_data = cursor.fetchone()  # Fetch the user's data

        if user_data:
            # Map fetched data into dictionary with appropriate mappings for categorical values

            # ChestPainType Mapping
            chest_pain_type_map = {
                "Typical Angina": "TA",
                "Atypical Angina": "ATA",
                "Non-Anginal Pain": "NAP",
                "Asymptomatic": "ASY"
            }

            # RestingECG Mapping
            resting_ecg_map = {
                "Normal": "Normal",
                "ST-T Wave Abnormality": "ST",
                "Left Ventricular Hypertrophy": "LVH"
            }

            # ST_Slope Mapping
            st_slope_map = {
                "Upsloping": "Up",
                "Flat": "Flat",
                "Downsloping": "Down"
            }

            # FastingBS Mappign
            fasting_bs = 0 if user_data[5] < 120 else 1

            # Map fetched data into a dictionary with appropriate mappings
            user_details = {
                "Age": user_data[0],
                "Sex": user_data[1],  # No mapping needed since it's already 'Male' or 'Female'
                "ChestPainType": chest_pain_type_map.get(user_data[2], user_data[2]),  # Apply mapping
                "RestingBP": user_data[3],
                "Cholesterol": user_data[4],
                "FastingBS": fasting_bs,  # Fasting BS is already a numeric value (0 or 1)
                "RestingECG": resting_ecg_map.get(user_data[6], user_data[6]),  # Apply mapping
                "MaxHR": user_data[7],
                "ExerciseAngina": user_data[8],  # Apply mapping
                "Oldpeak": user_data[9],
                "ST_Slope": st_slope_map.get(user_data[10], user_data[10]),  # Apply mapping                
            }
            return user_details
        else:
            st.error("User details not found in the database.")
            return None
    except Exception as e:
        st.error(f"Error fetching user details: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

col1, col2 = st.columns([8, 1])  # Adjust the middle ratio as needed

with col1:
    st.markdown("# 💓 Heart Disease Risk Analysis")  # Title on the left

with col2:
    if "user" in st.session_state and "id" in st.session_state["user"]:
        if st.button("Log out"):
            del st.session_state["user"]
            st.switch_page("pages/login.py")

# Get the user_id from session state (make sure this is set after login)
if "user" not in st.session_state or "id" not in st.session_state["user"]:
    st.error("You are not logged in!")
    if st.button("Go to Login"):
        st.switch_page("pages/login.py")
else:
    user_id = st.session_state["user"]["id"]
    user_data = get_user_details(user_id)
    if user_data:
        st.markdown("### 👤 User Profile Summary")

        cols = st.columns(2)

        for i, (key, value) in enumerate(user_data.items()):
            cols[i % 2].markdown(f"**{key}**: {value}")
        
        if st.button("Analyze"):
            actual, predicted, probability, risk_level, flagged = predict_heart_disease(user_data)  
            # 🌟 Save the predicted risk percentage to the database
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                  UPDATE heart_patient_data
                  SET risk_percentage = %s
                  WHERE user_id = %s
                  ORDER BY id DESC
                  LIMIT 1
                  """, (float(probability * 100), user_id))
                conn.commit()
                cursor.close()
                conn.close()
                st.success("✅ Risk percentage saved successfully in your profile!")
            except Exception as e:
                st.warning(f"⚠️ Could not save risk percentage: {e}")
    
            # 🌡️ Probability Gauge Chart
            gauge = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=probability * 100,
                title={'text': "Heart Disease Risk %"},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "crimson" if probability > 0.6 else "orange" if probability > 0.3 else "green"},
                    'steps': [
                        {'range': [0, 30], 'color': "lightgreen"},
                        {'range': [30, 60], 'color': "yellow"},
                        {'range': [60, 100], 'color': "lightcoral"},
                    ],
                }
            ))    

            # 📊 Bar Chart: User Metrics vs Normal
            normal_ranges = {
                "RestingBP": 120,
                "Cholesterol": 200,
                "MaxHR": 170,
                "Oldpeak": 1.0
            }

            metrics_df = pd.DataFrame({
                "Metric": list(normal_ranges.keys()),
                "User": [user_data[k] for k in normal_ranges],
                "Normal": list(normal_ranges.values())
            })

            bar_chart = go.Figure()
            bar_chart.add_trace(go.Bar(x=metrics_df["Metric"], y=metrics_df["User"], name="User", marker_color="indianred"))
            bar_chart.add_trace(go.Bar(x=metrics_df["Metric"], y=metrics_df["Normal"], name="Normal", marker_color="lightgray"))
            bar_chart.update_layout(title="📈 Vital Signs Comparison", barmode='group')    

            # 🕸️ Radar Chart for Risk Profile (Optional)
            radar_metrics = ["Age", "RestingBP", "Cholesterol", "MaxHR", "Oldpeak"]
            user_radar = [user_data[m] for m in radar_metrics]
            norm_radar = [50, 120, 200, 170, 1.0]

            radar_chart = go.Figure()
            radar_chart.add_trace(go.Scatterpolar(r=user_radar, theta=radar_metrics, fill='toself', name='User'))
            radar_chart.add_trace(go.Scatterpolar(r=norm_radar, theta=radar_metrics, fill='toself', name='Normal'))
            radar_chart.update_layout(polar=dict(radialaxis=dict(visible=True)), title="🕸️ Radar View of Health Profile")

            st.subheader("🧠 Heart Disease Prediction Summary")

            st.markdown(f"### 💬 Risk Interpretation")
            if predicted == 1:
                st.error(f"**High Risk Detected:** You have a **{int(probability * 100)}%** chance of heart disease.")
            else:
                st.success(f"**Low Risk:** Based on your data, the model predicts a low likelihood of heart disease (**{int(probability * 100)}%**).")

            st.markdown("### 📌 Health Risk Level")
            st.info(f"**Your Risk Level:** `{risk_level}`\n\nThis level is determined based on a combination of vitals and lifestyle indicators.")

            if flagged:
                st.warning("⚠️ **Areas of Concern Detected:**")
                for flag in flagged:
                    st.markdown(f"- {flag}")
            else:
                st.success("✅ All your vital signs appear to be within healthy ranges.")

            # Show bar chart
            st.markdown("### 📊 Vital Signs vs Normal Ranges")
            st.plotly_chart(bar_chart, use_container_width=True)

            # Show gauge chart
            st.markdown("### 🌡️ Estimated Risk Gauge")
            st.plotly_chart(gauge, use_container_width=True)

            # Show radar chart
            st.markdown("### 🕸️ Health Profile Overview")
            st.plotly_chart(radar_chart, use_container_width=True)

            st.markdown("### 🩺 Personalized Health Tips")

            if user_data["Cholesterol"] > 200:
                st.markdown("- Your cholesterol is high. Consider reducing saturated fats, exercising regularly, and speaking to your doctor about treatment.")

            if user_data["RestingBP"] > 120:
                st.markdown("- Elevated blood pressure can increase your risk. Reduce salt intake, manage stress, and follow medical guidance.")

            if user_data["MaxHR"] > 100:
                st.markdown("- Your maximum heart rate is elevated. While this can be normal for active individuals, consistently high MaxHR may indicate overexertion or cardiovascular stress. Monitor during workouts and consult a healthcare professional if concerned.")

            if user_data["Oldpeak"] > 1.0:
                st.markdown("- Your ST depression is higher than normal. This may indicate heart strain. Consider a follow-up with your healthcare provider.")

            if user_data["FastingBS"] == 1:
                st.markdown("- High fasting blood sugar is a diabetes risk. Consider cutting back on sugar and refined carbs.")

            st.markdown("🧘‍♀️ _Regular checkups, lifestyle changes, and early detection can greatly reduce your risk._")

    else:
        st.error("You havent filled you health data")
        if st.button("Go to Dashboard"):
            st.switch_page("pages/dashboard.py")