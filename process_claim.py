import os
import json
import pymupdf
from pydantic import BaseModel, Field
from typing import Optional
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# 1. Schema Definition (Pydantic Models for Google GenAI)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# 2. Extract Text from PDF
# ---------------------------------------------------------------------------
def extract_text_from_pdf(pdf_path: str) -> str:
    print(f"Extracting text from {pdf_path}...")
    text = ""
    try:
        doc = pymupdf.open(pdf_path)
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""

# ---------------------------------------------------------------------------
# 3. Extract Fields using LLM
# ---------------------------------------------------------------------------
def extract_fields_with_llm(text: str) -> ClaimData:
    print("Extracting fields using Gemini...")
    client = genai.Client() # Assumes GEMINI_API_KEY is in environment
    
    prompt = f"""
    You are an autonomous insurance claims processing agent. 
    Extract the required fields from the following First Notice of Loss (FNOL) document text.
    If a field is not present or cannot be determined, return null.
    
    Document Text:
    {text}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ClaimData,
        ),
    )
    
    # Parse the response into our Pydantic model
    claim_data_dict = json.loads(response.text)
    return ClaimData(**claim_data_dict)

# ---------------------------------------------------------------------------
# 4. Check Missing Fields
# ---------------------------------------------------------------------------
def identify_missing_fields(claim_data: ClaimData) -> list:
    missing_fields = []
    
    # We will check all fields defined in the schema
    for section_name, section_data in claim_data.model_dump().items():
        if isinstance(section_data, dict):
            for field_name, value in section_data.items():
                if value is None or str(value).strip() == "":
                    missing_fields.append(f"{section_name}.{field_name}")
        else:
            if section_data is None or str(section_data).strip() == "":
                missing_fields.append(section_name)
                
    return missing_fields

# ---------------------------------------------------------------------------
# 5. Routing Logic
# ---------------------------------------------------------------------------
def route_claim(claim_data: ClaimData, missing_fields: list):
    route = ""
    reason = ""
    
    # Rule 1: Missing Mandatory Fields
    if len(missing_fields) > 0:
        return "Manual review", f"Missing mandatory fields: {', '.join(missing_fields)}"
        
    # Rule 2: Investigation Flag
    description = claim_data.incident_information.description or ""
    description_lower = description.lower()
    flag_words = ["fraud", "inconsistent", "staged"]
    if any(word in description_lower for word in flag_words):
        return "Investigation Flag", "Incident description contains flagged keywords."
        
    # Rule 3: Specialist Queue
    claim_type = claim_data.claim_type or ""
    if "injury" in claim_type.lower():
        return "Specialist Queue", "Claim type involves injury."
        
    # Rule 4: Fast-track
    est_damage = claim_data.asset_details.estimated_damage
    if est_damage is not None and est_damage < 25000:
        return "Fast-track", f"Estimated damage (${est_damage}) is less than $25,000."
        
    # Default Route
    return "Standard Processing", "No special routing rules triggered."

# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------
def main():
    pdf_path = "Automobile Loss Notice Dec 5 2016.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return
        
    # 1. Extract Text
    pdf_text = extract_text_from_pdf(pdf_path)
    if not pdf_text:
        print("Failed to extract text. Exiting.")
        return
        
    # 2. Extract Fields (Requires GEMINI_API_KEY)
    try:
        claim_data = extract_fields_with_llm(pdf_text)
    except Exception as e:
        print(f"Error extracting fields with LLM: {e}")
        print("Please ensure your GEMINI_API_KEY environment variable is set.")
        return
        
    # 3. Identify Missing Fields
    missing_fields = identify_missing_fields(claim_data)
    
    # 4. Route Claim
    route, reason = route_claim(claim_data, missing_fields)
    
    # 5. Format Output
    output = {
        "extractedFields": claim_data.model_dump(),
        "missingFields": missing_fields,
        "recommendedRoute": route,
        "reasoning": reason
    }
    
    # Save to file
    with open("output.json", "w") as f:
        json.dump(output, f, indent=4)
        
    # Print to console
    print("\n--- Output ---")
    print(json.dumps(output, indent=4))
    print("\nProcessing complete. Results saved to output.json")

if __name__ == "__main__":
    main()
