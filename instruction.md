# Medical Research Paper Processing Guide

## Overview
This system processes medical research papers provided in PDF format and registers them into a Notion database.

## Processing Workflow

### 1. PMID Search
- Use PubMed MCP server
- Search PMID using article's metadata (title, authors, etc.)

### 2. Information Extraction
Extract and summarize the following key information:
- Title
- Authors
- Publication year
- Journal name
- Volume
- Issue number
- Page numbers
- DOI
- Summary
- Keywords

### 3. Notion API Registration
- **Database ID**: `3567584d934242a2b85acd3751b3997b`
- Register extracted information into Notion database

## Processing Requirements

### Information Handling
- **Accuracy**: Ensure all information is accurately extracted, summarized, and formatted
- **Multiple Authors**: Handle multiple authors appropriately
- **Missing Information**: Leave blank without making assumptions if any information is missing

### Abstract Structure
Structure the abstract to include:
- Research background
- Purpose
- Methods
- Results
- Conclusion
- Significance
- Limitations

### Summary Requirements
- **Language**: Japanese
- **Style**: Formal and concise
- **Length**: Around 2,000-3,000 characters
- **Content**: Summarize main points from the entire document rather than just translating the abstract

### PubMed Link Construction
- **Format**: `https://pubmed.ncbi.nlm.nih.gov/[PMID]/`
- **When PMID is missing**: `null`
- **Notion Property Name**: "PubMed"

### Other Fields
- Input as is from the original text without translation

## Notion Posting Process

### 1. Generate JSON Content
Create JSON content based on the provided template

### 2. Post to Notion
- Use the generated JSON to post to Notion via notion MCP server

## Multiple PDF Processing
- **Individual Processing**: Process each PDF separately
- **Individual Posting**: Post the information to Notion individually
- **Principle**: Ensure that one Notion entry is created for each PDF document

## Response Requirements
- Brief and to the point