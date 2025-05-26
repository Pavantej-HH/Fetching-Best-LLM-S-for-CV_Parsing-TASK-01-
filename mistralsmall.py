import streamlit as st
import fitz  
import requests
import json
import time
import pandas as pd
import io
import pytesseract
from PIL import Image
import re

API_KEY = "SWzirv7uBdklaJ8ltKnunstKbwwrhSHf"
API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODELS = ["mistral-small"]

def extract_text_from_pdf(pdf_bytes):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = "\n".join(page.get_text("text") for page in doc)
        return text.strip()
    except Exception as e:
        return f"Error reading PDF: {e}"

def extract_text_from_pdf_ocr(pdf_bytes):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        ocr_text = ""
        for page in doc:
            pix = page.get_pixmap()
            img_bytes = pix.tobytes()  
            image = Image.open(io.BytesIO(img_bytes))
            page_text = pytesseract.image_to_string(image)
            ocr_text += page_text + "\n"
        return ocr_text.strip()
    except Exception as e:
        return f"Error reading PDF OCR: {e}"

def parse_resume(resume_text, model_name):
    print(f"Model selected: {model_name}")
    print(f"Resume text length: {len(resume_text)}")
    
    template = {
        "parsed_resume": {
            "ResumeParserData": {}
        }
    }

    prompt = (
        "You are a resume parser. Extract the following details from the resume and format according to this JSON structure:\n"
        f"{json.dumps(template, indent=2)}\n\n"
        f"Resume Content:\n{resume_text}\n\n"
        "Provide output in JSON format."
    )
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are an AI that extracts structured information from resumes."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 2000
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        print("API Response:", response.status_code, response.text)
        
        if response.status_code == 200:
            try:
                resp_json = response.json()
                if "choices" in resp_json and isinstance(resp_json["choices"], list) and len(resp_json["choices"]) > 0:
                    choice = resp_json["choices"][0]
                    if isinstance(choice, dict) and "message" in choice and "content" in choice["message"]:
                        content = choice["message"]["content"]
                        try:
                            content = content.replace('\\"', '"').replace('\\n', '').replace('\\_', '_').strip()
                            
                            if content.startswith('"') and content.endswith('"'):
                                content = content[1:-1]
                            
                            return json.loads(content)
                        except json.JSONDecodeError as e:
                            return {
                                "error": f"Failed to parse response content as JSON: {str(e)}", 
                                "raw_content": content
                            }
                    else:
                        return {"error": "Unexpected structure in API choices"}
                else:
                    return {"error": "Unexpected response format"}
            except Exception as e:
                return {"error": f"Failed to process API response: {str(e)}"}
        else:
            return {"error": f"API Error: {response.status_code}, {response.text}"}
    except Exception as e:
        return {"error": f"API Request Failed: {str(e)}"}

st.title("Mistral Resume Parser")
uploaded_file = st.file_uploader("Upload a Resume (PDF)", type=["pdf"])

if uploaded_file:
    file_bytes = uploaded_file.read()
    st.write("Extracting text from the resume...")
    resume_text = extract_text_from_pdf(file_bytes)
    
    if resume_text and not resume_text.startswith("Error reading PDF"):
        st.write("Resume text extracted successfully!")
        st.write("Processing resume...")
        
        for model in MISTRAL_MODELS:
            start_time = time.time()
            parsed_data = parse_resume(resume_text, model)
            end_time = time.time()
            execution_time = round(end_time - start_time, 2)
            
            st.subheader(f"Extracted Resume Information ({model})")
            st.json(parsed_data)
            st.subheader("Execution Time")
            st.write(f"{execution_time} seconds")
            
            if "error" in parsed_data:
                st.error(f"{parsed_data['error']}")
            else:
                st.success(f"Resume processed successfully with {model}!")
    else:
        st.error("No text extracted. Please check the file.")