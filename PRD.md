# Product Requirements Document (PRD)

## Vehicle Document RAG Application with Group-Based Access Control

---

## 1. Project Overview

### 1.1 Participants

- **Product Owner:** Arpit Nema
- **Development Team:** Backend, Frontend, AI/ML Engineers
- **Stakeholders:** Vehicle Development Center, Quality Assurance Teams

### 1.2 Status

New Project - Requirements Definition Phase

### 1.3 Target Release

[Define your timeline]

---

## 2. Objective & Goals

Build a robust, scalable RAG (Retrieval Augmented Generation) application that enables vehicle engineering teams to securely access, search, and interact with large-scale vehicle validation reports and technical documents through natural language queries.

### Key Success Metrics

- Support 500+ GB of vehicle test documentation
- Response time <3 seconds for queries
- Retrieval accuracy >90% for domain-specific queries
- Support 100+ concurrent users across multiple groups
- Zero unauthorized data access incidents

---

## 3. Background & Strategic Fit

Vehicle Development Centers generate extensive validation reports (ETRs) containing critical test data for gradability, brake performance, noise measurements, cooling systems, and regulatory compliance. Currently, engineers manually search through hundreds of reports to find relevant historical data, leading to inefficiencies.

This RAG application will enable semantic search across all validation reports, allowing engineers to ask natural language questions like "Show me all Pro 2118 CNG models that failed gradability tests" and receive precise, cited answers from the document corpus.

---

## 4. Technical Architecture

### 4.1 Core Components

- **Vector Database:** QDrant (self-hosted)
- **LLM:** Ollama (self-hosted models on-premise)
- **Backend:** FastAPI with Python
- **Frontend:** React/Next.js
- **Authentication:** Email/Password + OTP verification
- **Database:** PostgreSQL for user/group management

### 4.2 Infrastructure Requirements

- Minimum 1TB storage for vector embeddings and documents
- GPU support for embedding generation and LLM inference
- Redis for caching and session management
- Message queue (RabbitMQ/Cellar) for async document processing

---

## 5. Features & Requirements

### 5.1 Authentication & Authorization

**Feature 1: Email/Password Authentication**

- User registration with email verification
- Secure password storage (bcrypt/argon2)
- Password reset via OTP
- JWT-based session management
- MFA support (optional)

**Feature 2: OTP-Based Login**

- Time-based OTP generation (6-digit, 5-minute validity)
  - Email delivery of OTP codes
  - Rate limiting to prevent brute force attacks

**Feature 3: Role-Based Access Control (RBAC)**

- Roles: Admin, Group Manager, Member
- Admin: Create groups, assign users, manage permissions
- Group Manager: Upload documents, manage group members
- Member: Read and query group documents

---

### 5.2 Group Management

**Feature 4: Group Creation & Assignment**

- Admins can create groups (e.g., "Pro 2118 CNG Team", "Brake Testing Unit")
- Users can be assigned to multiple groups
- Group-level document isolation using metadata filtering
- Hierarchical group structures (optional Phase 2)

**Feature 5: Document Scoping**

- Documents uploaded to a group are accessible only to group members
- QDrant collection partitioning by group_id for data isolation
- Metadata filtering during query: `filter: {group_id: [user_groups]}`

---

### 5.3 Document Ingestion & Processing

**Feature 6: Multi-Format Support**

**Phase 1 (MVP):**

- PDF documents (ETR reports)
- Plain text documents (.txt, .md)

**Phase 2:**

- Microsoft PowerPoint (.pptx)
- Images (OCR extraction for charts/tables)
- Excel spreadsheets (.xlsx) for tabular data

**Feature 7: Intelligent Chunking Strategy**

**Chunking Approach:**

- **Hybrid chunking** combining fixed-size and semantic boundaries
- **Chunk size:** 512 tokens with 100-token overlap
- **Structure-aware splitting:** Preserve section headers, tables, and test parameter boundaries
- **Metadata preservation:** Maintain document structure context in each chunk

**Example Chunk Metadata:**

```json
{
  "doc_id": "ETR_07_24_61",
  "group_id": "pro2118_team",
  "chunk_id": "ETR_07_24_61_chunk_12",
  "test_type": "gradability",
  "vehicle_model": "Pro 2118 CNG E494 110kW",
  "chassis_no": "MC2EVHRC0RC233300",
  "test_date": "2024-08-29",
  "page_number": 3,
  "section": "Grade ability",
  "compliance_status": "pass",
  "standard": "AIS-003-1999",
  "test_parameters": ["grade_restart", "parking_hold"],
  "source_file": "ETR_07_24_61.pdf"
}
```

**Feature 8: Metadata Extraction & Tagging**

**Automated Extraction:**

- **Vehicle identifiers:** Model, chassis number, registration number
- **Test metadata:** Test type, date, engineer name, location
- **Compliance data:** Standard (IS/AIS), pass/fail status
- **Performance metrics:** Numerical values (MFDD, gradability %, noise levels)
- **Component details:** Engine model, transmission type, tire specifications

**Tagging Strategy:**

- Use regex patterns and NLP to extract structured data from headers
- Tag each chunk with relevant filters for granular retrieval
- Index nested metadata in QDrant for multi-level filtering

---

### 5.4 RAG Query & Chat Interface

**Feature 9: Strict Data Grounding**

The RAG system must be **strictly grounded** in the document corpus:

- Answers must cite specific document sources (ETR number, page, section)
- If information is not in the corpus, respond: "No data found in uploaded documents"
- No hallucination or external knowledge injection
- Confidence scoring for retrieved chunks (>0.7 threshold)

**Feature 10: Query Interface**

- Natural language chat interface
- Multi-turn conversations with context retention
- Query examples:
  - "What was the brake MFDD for Pro 2118 CNG in August 2024?"
  - "Show all vehicles that failed gradability tests in 2024"
  - "Compare noise levels across Pro 2118 variants"

**Feature 11: Citation & Source Attribution**

- Display source documents with page numbers
- Highlight relevant text snippets from retrieved chunks
- Allow users to navigate to original PDF sections

**Feature 12: Advanced Filtering**
Users can filter queries by metadata:

- Date range: "Show tests from Q3 2024"
- Test type: "Only brake test reports"
- Vehicle model: "Pro 2118 variants"
- Compliance status: "Failed tests only"

---

### 5.5 Vector Database Configuration (QDrant)

**Collection Structure:**

- One collection per group OR metadata-based partitioning
- **Vector dimensions:** Match embedding model (e.g., 768 for nomic-embed-text)
- **Distance metric:** Cosine similarity
- **Indexing:** HNSW for fast approximate search

**Payload Schema:**

```json
{
  "text": "Chunk content",
  "metadata": {
    "group_id": "string",
    "doc_id": "string",
    "test_type": "string",
    "vehicle_model": "string",
    "test_date": "ISO 8601 date",
    "compliance_status": "pass/fail",
    ...
  }
}
```

**Retrieval Configuration:**

- Top-k: 10 chunks per query
- Re-ranking: Use cross-encoder for semantic relevance
- Group-based filtering in query: `must: [{key: "metadata.group_id", match: {any: user_groups}}]`

---

### 5.6 Document Upload & Management

**Feature 13: Async Document Processing**

- Queue-based ingestion pipeline (Celery + Redis)
- Processing stages:

1. File validation & virus scan
2. Text extraction (PyMuPDF for PDFs)
3. Metadata extraction
4. Chunking & embedding generation
5. QDrant indexing

- Status tracking: Pending → Processing → Completed/Failed
- Error handling with retry logic

**Feature 14: Document Versioning**

- Support document updates (e.g., revised ETR reports)
- Maintain version history with timestamps
- Archive old versions but keep searchable

---

## 6. Non-Functional Requirements

### 6.1 Scalability

- Handle 500+ GB of documents (estimated 10M+ chunks)
- Support horizontal scaling for QDrant (sharding/replication)
- Async embedding generation with batch processing
- Caching for frequent queries (Redis)

### 6.2 Performance

- Query response time: <3 seconds (embedding + retrieval + LLM inference)
- Document processing: <5 minutes for 10-page PDF
- Support 100+ concurrent users

### 6.3 Security

- End-to-end encryption for data at rest and in transit
- Group-level data isolation with strict access controls
- Audit logs for all document access and queries
- Regular security audits and vulnerability scanning

### 6.4 Reliability

- 99.5% uptime SLA
- Automated backups for QDrant and PostgreSQL
- Disaster recovery plan with <4 hour RTO

---

## 7. Assumptions

- All vehicle test reports follow a similar structure (as shown in ETR_07_24_61)
- On-premise infrastructure supports GPU acceleration for embeddings/LLM
- Users have basic technical literacy to formulate queries
- Documents are in English (or specify language support)
- Ollama models (e.g., llama3.2, nomic-embed-text) meet performance requirements

---

## 8. Out of Scope (Phase 1)

- Multi-language support
- Advanced analytics dashboards
- Integration with external CAD/PLM systems
- Mobile application
- Voice-based queries
- Real-time collaborative document annotation

---

## 9. User Stories

**US1: Engineer Query**
As a vehicle test engineer, I want to query historical brake test data for Pro 2118 models so that I can compare current results with past performance.

**US2: Group Manager Upload**
As a group manager, I want to upload new ETR reports to my team's document repository so that team members can immediately access and query the data.

**US3: Admin Group Management**
As an admin, I want to create project-specific groups and assign engineers so that document access is properly controlled.

**US4: Compliance Verification**
As a quality assurance lead, I want to filter all failed compliance tests from 2024 so that I can identify recurring issues.

---

## 10. Dependencies

- QDrant deployment and configuration
- Ollama model selection and benchmarking
- GPU infrastructure provisioning
- Email service for OTP delivery (SMTP/SendGrid)
- Storage infrastructure for 500GB+ data

---

## 11. Success Criteria

1. Successfully ingest 500+ GB of vehicle test documents
2. Achieve <3s query response time with 90%+ accuracy
3. Zero unauthorized document access incidents
4. 95% user satisfaction score in pilot testing
5. Support 100+ concurrent users without performance degradation

---

## 12. Open Questions

1. Which specific Ollama models will be used for embeddings and generation?
2. What is the expected growth rate of document corpus?
3. Are there compliance requirements (ISO 27001, GDPR) for data handling?
4. Should the system support federated search across multiple deployment sites?
5. What level of audit logging is required for regulatory compliance?

---

## 13. Timeline & Milestones

**Phase 1 (MVP - 12 weeks):**

- Authentication + Group management
- PDF ingestion with metadata extraction
- QDrant integration with basic RAG
- Web interface for upload and query

**Phase 2 (16 weeks):**

- PPTX and image support
- Advanced metadata filtering
- Performance optimization
- Production deployment
