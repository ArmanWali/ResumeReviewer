import csv
import json
import re

csv_file_path = 'jobs1.csv'
json_file_path = 'jobs_context.json'

jobs_data = []

def extract_skills_heuristic(description):
    """
    Attempts to condense a job description into a list of skills.
    This is a basic heuristic that splits by newlines/bullets and cleans up the text.
    """
    if not description:
        return "N/A"
    
    # Split by newlines or common delimiters
    lines = re.split(r'[\n\r•·]+', description)
    
    skills = []
    for line in lines:
        clean_line = line.strip()
        # Filter out empty lines or very short lines
        if len(clean_line) > 3:
            # Basic cleanup: remove starting "to " or "- "
            clean_line = re.sub(r'^[-*➢➣]\s*', '', clean_line)
            skills.append(clean_line)
    
    # Take top 10 items to keep it concise
    return ", ".join(skills[:10])

try:
    with open(csv_file_path, mode='r', encoding='latin-1') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            # Robust handling: Default to "N/A" if key is missing
            job_title = row.get("Job Type", "N/A").strip() or "N/A"
            company_name = row.get("Company", "N/A").strip() or "N/A"
            raw_description = row.get("Description", "").strip()
            
            # Explicit Skill Extraction
            required_skills = extract_skills_heuristic(raw_description)

            job_entry = {
                "job_title": job_title,
                "company_name": company_name,
                "required_skills": required_skills
            }
            jobs_data.append(job_entry)

    with open(json_file_path, mode='w', encoding='utf-8') as json_file:
        json.dump(jobs_data, json_file, indent=4)

    print(f"Successfully converted {csv_file_path} to {json_file_path}")

except Exception as e:
    print(f"Error converting CSV to JSON: {e}")
