# Synapx-Agent
This Repository is a task from Synapx for the role of Junior Software Engineer


# 🛡️ Insurance Claims Processing Agent

An autonomous AI agent that reads First Notice of Loss (FNOL) documents in bulk, extracts all relevant claim information, identifies any missing fields, and decides the best routing path for each claim — all powered by **Gemini 2.5 Flash**.

---

## 🧠 Approach

Processing insurance claim documents manually is slow and error-prone. This agent automates the entire pipeline for multiple files at once:

### Step 1 — Auto-Discover and Read Documents
The agent scans its folder for any `.pdf` or `.txt` files. It opens each file and extracts the raw text. PDF parsing is handled by **PyMuPDF**, while text files are read natively.

### Step 2 — Extract Structured Fields using Gemini
The raw text of each document is sent to **Gemini 2.5 Flash** with a structured prompt. The LLM is instructed to fill in a predefined schema covering:
- **Policy Information** (policy number, policyholder name, effective dates)
- **Incident Information** (date, time, location, description)
- **Involved Parties** (claimant, third parties, contact details)
- **Asset Details** (asset type, ID, estimated damage)
- **Claim Type, Attachments, and Initial Estimate**

The response is validated using **Pydantic** models so we always get clean, typed data back.

### Step 3 — Identify Missing Fields
After extraction, the agent scans every field in the schema. Any field that came back as empty or null is flagged as missing. This gives a clear list of what information is still needed for that specific claim.

### Step 4 — Route the Claim
Based on the extracted data and missing fields, the agent applies a rule-based engine to decide where each claim should go:

| Condition | Route |
|---|---|
| Any mandatory fields are missing | **Manual Review** |
| Incident description contains fraud-related keywords | **Investigation Flag** |
| Claim type involves injury | **Specialist Queue** |
| Estimated damage is under $25,000 | **Fast-track** |
| None of the above | **Standard Processing** |

### Output
The final result is saved to a single `output.json` file as a list containing the results for every document processed. A summary is also printed to the terminal showing how many succeeded, failed, and a breakdown of the routing decisions.

---

## 🗂️ Project Structure

```text
.
├── agent.py                                # Main batch processing script
├── Automobile Loss Notice Dec 5 2016.pdf   # Sample FNOL document (add more here)
├── output.json                             # Generated batch results
└── README.md
```

---

## ⚙️ Prerequisites

- Python 3.9 or higher
- A **Google Gemini API Key** (Free tier works perfectly)

---

## 🚀 Steps to Run

### 1. Clone the repository

```bash
git clone git@github.com:morsegupta/Synapx-Agent.git
cd <repo-folder>
```

### 2. Set up the environment and install dependencies

It is highly recommended to use a virtual environment:

```bash
# Activate your virtual environment (if you have one)
source venv/bin/activate

# Install the required libraries
pip install pymupdf pydantic litellm
```

### 3. Add your Gemini API Key

Open `agent.py` in your text editor. Around line 185, you will find this section:

```python
    API_KEY = "YOUR_API_KEY_HERE" #Enter Your Gemini API Key here
```

Replace `"YOUR_API_KEY_HERE"` with your actual Gemini API key and save the file.

### 4. Place your FNOL documents in the folder

Drop any number of `.pdf` or `.txt` claim documents directly into the same directory as `agent.py`. The script will automatically find them.

### 5. Run the batch agent

```bash
python agent.py
```

The script runs silently without asking for any interactive input. It processes all documents and prints a final summary.

---

## 📄 Sample Output Format

The `output.json` will contain a list of all processed files. Example:

```json
[
    {
        "file": "Automobile Loss Notice Dec 5 2016.pdf",
        "status": "success",
        "extractedFields": {
            "policy_information": {
                "policy_number": "ABC-123",
                ...
            },
            ...
        },
        "missingFields": [
            "incident_information.time",
            "asset_details.asset_id"
        ],
        "recommendedRoute": "Manual review",
        "reasoning": "Missing mandatory fields: incident_information.time, asset_details.asset_id"
    },
    {
        "file": "claim2.txt",
        "status": "success",
        ...
    }
]
```

---

## 📦 Dependencies

| Library | Purpose |
|---|---|
| `pymupdf` | Extract text from PDF documents |
| `pydantic` | Define and validate the claim data schema |
| `litellm` | Interface to communicate with the Gemini API using structured outputs |
