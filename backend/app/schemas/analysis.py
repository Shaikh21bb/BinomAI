from typing import List, Optional
from pydantic import BaseModel, Field

class Requirement(BaseModel):
    id: str = Field(description="Unique identifier for this requirement (e.g., req_001)")
    text: str = Field(description="The actual text of the requirement")
    category: str = Field(description="Category of the requirement (e.g., timeline, quality, experience)")
    is_mandatory: bool = Field(description="Whether this requirement is strict/mandatory")
    source_section: Optional[str] = Field(None, description="The section name/number in the tender document where this was found")
    source_page: Optional[int] = Field(None, description="The page number where this was found")

class Risk(BaseModel):
    id: str = Field(description="Unique identifier for this risk (e.g., risk_001)")
    description: str = Field(description="Description of the risk")
    severity: str = Field(description="Severity: Critical, High, Medium, Low")
    risk_type: str = Field(description="Type: legal, financial, technical, qualification")
    mitigation: Optional[str] = Field(None, description="Suggested action to mitigate the risk")
    source_section: Optional[str] = Field(None, description="Section triggering the risk")

class KeyDeadline(BaseModel):
    event: str = Field(description="Name of the event (e.g., Application Deadline, Construction Start)")
    date: str = Field(description="The date or timeframe mentioned")
    is_hard_deadline: bool = Field(description="Is this a strict deadline?")
    source_section: Optional[str] = Field(None, description="Section in the document")

class DocumentRequirement(BaseModel):
    name: str = Field(description="Name of the required document or certificate")
    is_mandatory: bool = Field(description="Is it mandatory for submission?")
    notes: Optional[str] = Field(None, description="Any special conditions for this document")

class MissingInfo(BaseModel):
    description: str = Field(description="What information is missing or ambiguous in the tender?")
    impact: str = Field(description="How does this impact the proposal preparation?")
    clarification_question: str = Field(description="Suggested question to ask the customer")

class TenderAnalysisOutput(BaseModel):
    executive_summary: str = Field(description="A brief 2-3 paragraph summary of the entire tender")
    tender_type: str = Field(description="Type of tender (e.g., EPC, Construction, Supply, Services)")
    complexity_level: str = Field(description="Complexity: low, medium, high")
    estimated_duration_days: int = Field(description="Estimated project duration in days (0 if not specified)")
    
    technical_requirements: List[Requirement] = Field(default_factory=list, description="List of technical requirements")
    commercial_requirements: List[Requirement] = Field(default_factory=list, description="List of commercial/financial requirements")
    legal_requirements: List[Requirement] = Field(default_factory=list, description="List of legal requirements")
    
    required_documents: List[DocumentRequirement] = Field(default_factory=list, description="List of documents the bidder must submit")
    key_deadlines: List[KeyDeadline] = Field(default_factory=list, description="List of important dates")
    
    risks: List[Risk] = Field(default_factory=list, description="List of identified risks")
    
    missing_info_from_tender: List[MissingInfo] = Field(default_factory=list, description="Ambiguities or missing info in the tender docs")
    missing_company_data: List[str] = Field(default_factory=list, description="Information we need from our company to fulfill the tender (e.g., 'Need list of specific equipment')")
