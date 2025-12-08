import os
import json
import io
import re
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Key Initialization Check
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing from environment variables. Server cannot start.")

app = FastAPI(title="BehterCV Backend")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load General Industry Job Context
JOBS_CONTEXT = []
try:
    with open("jobs_context.json", "r", encoding="utf-8") as f:
        JOBS_CONTEXT = json.load(f)
except Exception as e:
    print(f"Warning: Could not load jobs_context.json: {e}")

client = genai.Client(api_key=GEMINI_API_KEY)

def extract_text_from_pdf(pdf_file: bytes) -> str:
    """
    Utility function to securely and accurately extract all text content 
    from the uploaded PDF resume file.
    Includes filtering for excessively long lines of non-alphabetic characters.
    """
    try:
        pdf_reader = PdfReader(io.BytesIO(pdf_file))
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                # PDF Text Cleanliness: Filter lines
                lines = page_text.split('\n')
                cleaned_lines = []
                for line in lines:
                    # Check if line is mostly non-alphanumeric (e.g., "......" or "_______")
                    # Calculate ratio of alphanumeric chars to total length
                    clean_chars = len(re.findall(r'[a-zA-Z0-9]', line))
                    total_chars = len(line.strip())
                    
                    if total_chars > 0:
                        ratio = clean_chars / total_chars
                        # Keep line if it has a reasonable amount of text content (e.g., > 30%)
                        # or if it's very short (could be a header/bullet)
                        if ratio > 0.3 or total_chars < 5:
                            cleaned_lines.append(line)
                
                text += "\n".join(cleaned_lines) + "\n"
        return text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading PDF: {str(e)}")

@app.post("/analyze-resume")
async def analyze_resume(
    company_name: Optional[str] = Form(None),
    job_description: str = Form(...),
    resume_pdf: UploadFile = File(...)
):
    # 1. Strict File Validation
    if resume_pdf.content_type != "application/pdf":
        raise HTTPException(
            status_code=400, 
            detail="Invalid file type. Only PDF files (application/pdf) are supported. DOC/DOCX files are not supported."
        )

    # 2. Extract Text from Resume
    try:
        pdf_content = await resume_pdf.read()
        resume_text = extract_text_from_pdf(pdf_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

    # 3. Prepare Context
    general_context_str = json.dumps(JOBS_CONTEXT[:50]) 
    
    # 4. Construct the Prompt
    prompt = f"""
    Analyze the following resume text against the provided Job Description. 
    
    **Goal:** Provide a comprehensive, structured review similar to professional resume audit platforms.

    **General Industry Job Context (JSON):**
    {general_context_str}

    **Specific Job Description:**
    Company: {company_name if company_name else "Not Specified"}
    Description:
    {job_description}

    **Resume Text for Analysis:**
    {resume_text}

    ---

    **Output Format:**
    Return a **strictly valid JSON object** with the following structure:
    {{
        "match_score": 85,
        "sub_scores": {{
            "structure": {{"score": 15, "max": 20}},
            "content": {{"score": 45, "max": 60}},
            "tailoring": {{"level": "High", "feedback": "Well matched to keywords"}}
        }},
        "checklist": [
            {{
                "category": "Resume Format",
                "items": [
                    {{"name": "Length", "status": "pass", "score": "+10 pts", "detail": "1 page, perfect length."}},
                    {{"name": "Formatting", "status": "fail", "score": "-5 pts", "detail": "Inconsistent font sizes."}}
                ]
            }},
            {{
                "category": "Essential Sections",
                "items": [
                    {{"name": "Summary", "status": "warn", "score": "-5 pts", "detail": "Present but generic."}},
                    {{"name": "Experience", "status": "pass", "score": "+10 pts", "detail": "Good use of action verbs."}}
                ]
            }}
        ],
        "annotated_resume": "The full text of the resume with the annotations described below..."
    }}

    **Annotation Instructions (Use these EXACT markers in 'annotated_resume'):**
    1.  **Improvements (Orange):** Wrap text that needs quantification or better wording in `<<<` and `>>>`.
    2.  **Removals (Red):** Wrap text that should be deleted in `~~~` and `~~~`.
    3.  **Additions (Green):** Insert new suggested text wrapped in `+++` and `+++`.

    **Critique Guidelines:**
    *   **Structure:** Check length, readability, and section organization.
    *   **Content:** Check for quantification, action verbs, and clarity.
    *   **Tailoring:** Check for JD keywords and specific skills.
    *   **Annotated Resume:** Rewrite the resume text. **Use Markdown for formatting:**
        - Use `### ` for Section Headers (e.g. ### Experience).
        - Use `**` for bolding key terms (e.g. **Candidate Name**).
        - Use `- ` for bullet points.
        - **Crucial:** Keep the annotation markers (`<<<`, `~~~`, `+++`) as defined previously.

    **Important:** Do not use markdown formatting for the JSON (no ```json). Just return the raw JSON string.
    """

    # 5. Call Gemini API
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        
        # Clean and Parse JSON
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
            
        return json.loads(response_text.strip())
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI returned invalid JSON format.")
    except Exception as e:
        # Error Handling Clarity: 503 for external service errors
        raise HTTPException(status_code=503, detail=f"AI Service Unavailable: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
