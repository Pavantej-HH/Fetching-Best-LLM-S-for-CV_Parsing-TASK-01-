import streamlit as st
import fitz  
import requests
import json
import time
import re

API_KEY = "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"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "qwen/qwen2.5-vl-3b-instruct:free"


TEMPLATE = {
    "parsed_resume": {
        "ResumeParserData": {
            "ResumeLanguage": {"Language": "", "LanguageCode": ""},
            "ResumeCountry": {
                "Country": "",
                "CountryCode": {"IsoAlpha2": "", "IsoAlpha3": "", "UNCode": ""}
            },
            "Name": {
                "FullName": "", "TitleName": "", "FirstName": "", "MiddleName": "",
                "LastName": "", "FormattedName": ""
            },
            "DateOfBirth": "",
            "Gender": "",
            "FatherName": "",
            "MotherName": "",
            "MaritalStatus": "",
            "Nationality": "",
            "LanguageKnown": [],
            "UniqueID": "",
            "LicenseNo": "",
            "PassportDetail": {
                "PassportNumber": "",
                "DateOfExpiry": "",
                "DateOfIssue": "",
                "PlaceOfIssue": ""
            },
            "PanNo": "",
            "VisaStatus": "",
            "Email": [],
            "PhoneNumber": [],
            "WebSite": [],
            "Address": [],
            "Category": "",
            "SubCategory": "",
            "CurrentSalary": {"Amount": "", "Symbol": "", "Currency": "", "Unit": "", "Text": ""},
            "ExpectedSalary": {"Amount": "", "Symbol": "", "Currency": "", "Unit": "", "Text": ""},
            "Qualification": "",
            "SegregatedQualification": [],
            "Certification": "",
            "SegregatedCertification": [],
            "SkillBlock": "",
            "SkillKeywords": "",
            "SegregatedSkill": [],
            "Experience": "",
            "SegregatedExperience": []
        }
    }
}

def extract_text_from_pdf(pdf_bytes):
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            return "\n".join([page.get_text("text") for page in doc]).strip()
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return None

def clean_json_content(text):
    """Clean and validate JSON content from API response"""
    try:
       
        text = re.sub(r'```(?:json)?', '', text)
        text = text.replace('\\"', '"').replace('\\n', ' ').replace('\\_', '_')
        
        text = text.strip()
        if not text.startswith('{'):
            match = re.search(r'({.*})', text, re.DOTALL)
            if match:
                text = match.group(1)
        
        open_braces = text.count('{')
        close_braces = text.count('}')
        if open_braces > close_braces:
            text += '}' * (open_braces - close_braces)
        
        return text
    except Exception as e:
        print(f"Error in clean_json_content: {str(e)}")
        return None

def deep_merge(template, data):
    if isinstance(template, dict) and isinstance(data, dict):
        for key in template:
            if key in data:
                template[key] = deep_merge(template[key], data[key])
        return {**template, **{k: v for k, v in data.items() if k not in template}}
    else:
        return data
           
def parse_resume(resume_text, model_name):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://python.langchain.com",
        "X-Title": "Resume Parser"
    }

    prompt = (
        "Extract information from this resume into JSON format. "
        "Follow these rules:\n"
        "1. Return only valid JSON\n"
        "2. Do not include any explanation text\n"
        "3. Use exactly the structure provided\n"
        f"\nTemplate structure:\n{json.dumps(TEMPLATE, indent=2)}"
        f"\n\nResume text:\n{resume_text}"
    )

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": "You are a precise resume parser that returns only valid JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 2000
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        print(f"API Status Code: {response.status_code}")
        print(f"API Response Headers: {response.headers}")  
        
        if response.status_code != 200:
            return {"error": f"API Error: {response.status_code}", "raw_content": response.text[:1000]}

        resp_json = response.json()
        
        if resp_json.get("choices"):
            content = resp_json["choices"][0]["message"]["content"]
        elif resp_json.get("message"):
            content = resp_json["message"]
        else:
            return {"error": "Unexpected API response structure", "raw_content": resp_json}
            
        print(f"Raw content received: {content[:200]}...")  # Debug info

       
        cleaned = clean_json_content(content)
        if not cleaned:
            return {"error": "No JSON content found in response"}

        try:
            
            parsed_values = json.loads(cleaned)
        except json.JSONDecodeError as e:
            print(f"First parse attempt failed: {str(e)}")
            try:
                
                cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)  # Remove trailing commas
                cleaned = re.sub(r':\s*([^"][^,}\]\n]+)([,}\]])', r': "\1"\2', cleaned)  # Quote unquoted values
                parsed_values = json.loads(cleaned)
            except json.JSONDecodeError as e2:
                print(f"Second parse attempt failed: {str(e2)}")
                print(f"Problematic content: {cleaned[:500]}")  # Debug info
                return {
                    "error": f"JSON parsing failed: {str(e2)}",
                    "raw_content": cleaned[:1000]
                }

        if "parsed_resume" not in parsed_values:
            parsed_values = {"parsed_resume": {"ResumeParserData": parsed_values}}

        final_output = deep_merge(TEMPLATE.copy(), parsed_values)
        return final_output

    except Exception as e:
        print(f"Exception in parse_resume: {str(e)}")
        return {"error": f"Request error: {str(e)}"}

st.set_page_config(page_title="Resume Parser", page_icon="📄", layout="wide")
st.title("Resume Parser with OpenRouter AI")

uploaded_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"])

if uploaded_file:
    start_time = time.time()

    progress_bar = st.progress(0)
    status_text = st.empty()

    status_text.text("Extracting text from PDF...")
    progress_bar.progress(25)

    pdf_content = uploaded_file.read()
    resume_text = extract_text_from_pdf(pdf_content)

    if resume_text:
        status_text.text("Processing with AI...")
        progress_bar.progress(50)

        parsed_data = parse_resume(resume_text, MODEL_NAME)
        execution_time = round(time.time() - start_time, 2)

        progress_bar.progress(100)
        status_text.text("Processing complete!")

        tab1, tab2, tab3 = st.tabs([" Parsed Data", "Metrics", "Raw Text"])

        with tab1:
            st.subheader("Extracted Information")
            if "error" in parsed_data:
                st.error(parsed_data["error"])
            else:
                st.json(parsed_data)

        with tab2:
            st.subheader("Processing Metrics")
            col1, col2 = st.columns(2)
            col1.metric("Execution Time", f"{execution_time} seconds")
            col2.metric("Text Length", len(resume_text))

        with tab3:
            st.subheader("Extracted Raw Text")
            st.text_area("Resume Content", resume_text, height=300)

    else:
        st.error("No text could be extracted from the PDF. Please ensure it's readable and not password protected.")
        progress_bar.empty()
        status_text.empty()
