import google.generativeai as genai
import json
import streamlit as st

def parse_emails(emails, log_fn=print):
    # Streamlit Secrets से API Key लें
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    
    if not api_key:
        raise ValueError("GEMINI_API_KEY Secrets में नहीं मिली!")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    parsed_results = []
    log_fn(f"Gemini AI से {len(emails)} ईमेल्स का डेटा प्रोसेस किया जा रहा है...")

    for idx, email_data in enumerate(emails, 1):
        prompt = f"""
        Extract the following information from the email content in JSON format:
        - name: Sender or client name
        - email: Sender email address
        - phone: Phone number if mentioned, else ""
        - query: Summary of user query or request

        Email Subject: {email_data.get('subject', '')}
        Email Body: {email_data.get('body', '')}

        Return ONLY a raw JSON object with keys: name, email, phone, query. Do not wrap in markdown or backticks.
        """

        try:
            response = model.generate_content(prompt)
            text_response = response.text.strip().replace("```json", "").replace("```", "").strip()
            data = json.loads(text_response)

            data["raw_subject"] = email_data.get("subject", "")
            data["raw_date"] = email_data.get("date", "")
            parsed_results.append(data)
            log_fn(f"✅ Email {idx} सफलतापूर्वक पार्स (Parse) हो गया।")

        except Exception as e:
            log_fn(f"⚠️ Email {idx} पार्स करने में गलती हुई: {e}")
            parsed_results.append({
                "name": email_data.get("from", ""),
                "email": "",
                "phone": "",
                "query": email_data.get("body", "")[:100],
                "raw_subject": email_data.get("subject", ""),
                "raw_date": email_data.get("date", "")
            })

    return parsed_results
  
