import os
import json
import glob
import pymupdf
from pydantic import BaseModel, Field
from typing import Optional
from litellm import completion


class PolicyInformation(BaseModel):
    policy_number: Optional[str] = Field(description="Policy Number", default=None)
    policyholder_name: Optional[str] = Field(description="Policyholder Name", default=None)
    effective_dates: Optional[str] = Field(description="Effective Dates", default=None)


class IncidentInformation(BaseModel):
    date: Optional[str] = Field(description="Date of incident", default=None)
    time: Optional[str] = Field(description="Time of incident", default=None)
    location: Optional[str] = Field(description="Location of incident", default=None)
    description: Optional[str] = Field(description="Description of incident", default=None)


class InvolvedParties(BaseModel):
    claimant: Optional[str] = Field(description="Claimant Name", default=None)
    third_parties: Optional[str] = Field(description="Third Parties involved", default=None)
    contact_details: Optional[str] = Field(description="Contact Details of involved parties", default=None)


class AssetDetails(BaseModel):
    asset_type: Optional[str] = Field(description="Asset Type", default=None)
    asset_id: Optional[str] = Field(description="Asset ID (e.g. VIN or License Plate)", default=None)
    estimated_damage: Optional[float] = Field(description="Estimated Damage (numeric value without commas or symbols, null if not present)", default=None)


class ClaimData(BaseModel):
    policy_information: PolicyInformation
    incident_information: IncidentInformation
    involved_parties: InvolvedParties
    asset_details: AssetDetails
    claim_type: Optional[str] = Field(description="Claim Type (e.g. injury, collision, etc.)", default=None)
    attachments: Optional[str] = Field(description="Any attachments listed or mentioned", default=None)
    initial_estimate: Optional[str] = Field(description="Initial Estimate", default=None)


def find_fnol_files(folder: str) -> list[str]:
    """Scan the folder for all .pdf and .txt files."""
    pdf_files = glob.glob(os.path.join(folder, "*.pdf"))
    txt_files = glob.glob(os.path.join(folder, "*.txt"))
    return sorted(pdf_files + txt_files)


def extract_text_from_pdf(file_path: str) -> str:
    print(f"  Reading PDF: {os.path.basename(file_path)}")
    text = ""
    try:
        doc = pymupdf.open(file_path)
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        print(f"  Error reading PDF: {e}")
        return ""


def extract_text_from_txt(file_path: str) -> str:
    print(f"  Reading TXT: {os.path.basename(file_path)}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"  Error reading TXT: {e}")
        return ""


def extract_text(file_path: str) -> str:
    """Route to the right reader based on file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext == ".txt":
        return extract_text_from_txt(file_path)
    return ""


def extract_fields_with_llm(text: str, model_name: str, api_key: str) -> ClaimData:
    print(f"  Extracting fields using {model_name}...")

    prompt = f"""
    You are an autonomous insurance claims processing agent. 
    Extract the required fields from the following First Notice of Loss (FNOL) document text.
    If a field is not present or cannot be determined, return null.
    
    Document Text:
    {text}
    """

    response = completion(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        api_key=api_key,
        response_format=ClaimData,
    )

    content = response.choices[0].message.content

    if content.strip().startswith("```json"):
        content = content.strip()[7:-3].strip()
    elif content.strip().startswith("```"):
        content = content.strip()[3:-3].strip()

    claim_data_dict = json.loads(content)
    return ClaimData(**claim_data_dict)


def identify_missing_fields(claim_data: ClaimData) -> list:
    missing_fields = []
    for section_name, section_data in claim_data.model_dump().items():
        if isinstance(section_data, dict):
            for field_name, value in section_data.items():
                if value is None or str(value).strip() == "":
                    missing_fields.append(f"{section_name}.{field_name}")
        else:
            if section_data is None or str(section_data).strip() == "":
                missing_fields.append(section_name)
    return missing_fields


def route_claim(claim_data: ClaimData, missing_fields: list):
    if len(missing_fields) > 0:
        return "Manual review", f"Missing mandatory fields: {', '.join(missing_fields)}"

    description = claim_data.incident_information.description or ""
    flag_words = ["fraud", "inconsistent", "staged"]
    if any(word in description.lower() for word in flag_words):
        return "Investigation Flag", "Incident description contains flagged keywords."

    claim_type = claim_data.claim_type or ""
    if "injury" in claim_type.lower():
        return "Specialist Queue", "Claim type involves injury."

    est_damage = claim_data.asset_details.estimated_damage
    if est_damage is not None and est_damage < 25000:
        return "Fast-track", f"Estimated damage (${est_damage}) is less than $25,000."

    return "Standard Processing", "No special routing rules triggered."


def process_single_file(file_path: str, model_name: str, api_key: str) -> dict:
    """Process one FNOL file and return its result dict."""
    filename = os.path.basename(file_path)

    text = extract_text(file_path)
    if not text:
        return {
            "file": filename,
            "status": "error",
            "error": "Could not extract text from file."
        }

    try:
        claim_data = extract_fields_with_llm(text, model_name, api_key)
    except Exception as e:
        return {
            "file": filename,
            "status": "error",
            "error": f"LLM extraction failed: {e}"
        }

    missing_fields = identify_missing_fields(claim_data)
    route, reason = route_claim(claim_data, missing_fields)

    return {
        "file": filename,
        "status": "success",
        "extractedFields": claim_data.model_dump(),
        "missingFields": missing_fields,
        "recommendedRoute": route,
        "reasoning": reason
    }


def main():
    folder = os.path.dirname(os.path.abspath(__file__))

    API_KEY = " YOUR_API_KEY_HERE " #Enter Your Gemini API Key here
    model_name = "gemini/gemini-2.5-flash"

    if API_KEY == "YOUR_API_KEY_HERE" or not API_KEY:
        print("Please paste your Gemini API key into the API_KEY variable in agent.py")
        return

    print("Welcome to the Insurance Claims Processing System!")
    print(f"Using model: {model_name}\n")

    files = find_fnol_files(folder)

    excluded = {"output.json", "agent.py", "process_claim.py"}
    files = [f for f in files if os.path.basename(f) not in excluded]

    if not files:
        print("\nNo .pdf or .txt files found in the current folder. Exiting.")
        return

    print(f"\nFound {len(files)} file(s) to process:")
    for f in files:
        print(f"  - {os.path.basename(f)}")

    all_results = []
    success_count = 0
    error_count = 0

    for i, file_path in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] Processing: {os.path.basename(file_path)}")
        result = process_single_file(file_path, model_name, API_KEY)
        all_results.append(result)
        if result["status"] == "success":
            success_count += 1
            print(f"  ✓ Route: {result['recommendedRoute']}")
        else:
            error_count += 1
            print(f"  ✗ Error: {result['error']}")

    with open("output.json", "w") as f:
        json.dump(all_results, f, indent=4)

    print("\n" + "="*50)
    print("BATCH PROCESSING SUMMARY")
    print("="*50)
    print(f"  Total files   : {len(files)}")
    print(f"  Succeeded     : {success_count}")
    print(f"  Failed        : {error_count}")
    if success_count > 0:
        routes = [r["recommendedRoute"] for r in all_results if r["status"] == "success"]
        from collections import Counter
        for route, count in Counter(routes).items():
            print(f"  {route:<25}: {count} claim(s)")
    print("="*50)
    print("\nFull results saved to output.json")


if __name__ == "__main__":
    main()
