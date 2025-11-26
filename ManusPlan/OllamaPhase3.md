# StatMusePicksV2 AI Service - Implementation Roadmap & Progress Tracker

**Version:** 3.0 (Updated with Ollama Integration Requirements)
**Last Updated:** November 24, 2025
**Estimated Timeline:** 6-9 months
**Status:** 🟡 In Progress

---

## 📊 Overall Progress Tracker

| Phase | Status | Progress | Start Date | End Date | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1: Foundation** | 🟢 Completed | 100% | - | - | Backend & Data Infrastructure |
| **Phase 2: Core ML** | 🟡 In Progress | 80% | - | - | Per-Player Models & Calibration (High-priority tasks remaining) |
| **Phase 3: Advanced Features** | 🔴 Not Started | 0% | - | - | **Ollama Integration** & Feature Engineering |
| **Phase 4: Production** | 🔴 Not Started | 0% | - | - | MLOps & Automation |

**Legend:**
- 🔴 Not Started
- 🟡 In Progress
- 🟢 Completed
- ⚠️ Blocked
- ⏸️ On Hold

---

*(... Content from Phase 1 and Phase 2 remains the same ...)*

---

# PHASE 3: ADVANCED FEATURES & OLLAMA INTEGRATION (2-3 Months)

**Objective:** Implement advanced feature engineering, ensemble models, and integrate Ollama for qualitative analysis.
**Status:** 🔴 Not Started

## 3.1 Feature Engineering & Ensemble

### Task 3.1.1: Implement Advanced Feature Engineering

*(... Original sub-tasks remain ...)*

### Task 3.1.2: Implement Ensemble Stacking

*(... Original sub-tasks remain ...)*

## 3.2 Ollama LLM Integration (New Focus Area)

**Objective:** Integrate Ollama to provide qualitative features and enhanced analysis, leveraging its advanced capabilities.

### Task 3.2.1: Ollama Client Setup and Basic Connectivity

| Sub-Task | Status | Exact Instruction for AI Partner | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **Install Ollama Client** | 🔴 Pending | **1. Install Ollama Python Client:** `pip install ollama` | ✅ `ollama` package installed. |
| **Client Initialization** | 🔴 Pending | **2. Initialize Client:** Create `backend/services/ollama_client.py` and initialize the client, ensuring it can connect to the Ollama server (local or cloud). | ✅ Client connects and can list available models. |
| **Basic Call** | 🔴 Pending | **3. Test Basic Generation:** Implement a simple `ollama.chat()` call and verify response. | ✅ Successful text generation. |

### Task 3.2.2: Structured Output for Qualitative Features

| Sub-Task | Status | Exact Instruction for AI Partner | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **JSON Schema Definition** | 🔴 Pending | **1. Define Schema:** Create a Pydantic schema for qualitative features (e.g., `InjuryStatus: str`, `MoraleScore: int`, `NewsSentiment: float`). | ✅ Pydantic schema defined for feature extraction. |
| **Structured Call** | 🔴 Pending | **2. Implement Structured Call:** Use `ollama.generate(..., format='json', model='llama3')` to force the LLM to return a JSON object matching the Pydantic schema. | ✅ LLM output is a valid JSON object matching the schema. |
| **Feature Integration** | 🔴 Pending | **3. Integrate into FE:** Update `feature_engineering.py` to call this structured output function and add the resulting fields as new features. | ✅ Qualitative features added to the ML feature set. |

### Task 3.2.3: Tool Calling for Web Search (RAG)

| Sub-Task | Status | Exact Instruction for AI Partner | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **Tool Definition** | 🔴 Pending | **1. Define Web Search Tool:** Define a function (e.g., `web_search(query: str) -> str`) and expose it to Ollama as a tool. | ✅ Tool definition is correctly formatted for Ollama. |
| **Tool Calling Logic** | 🔴 Pending | **2. Implement Tool Calling:** Use Ollama's tool-calling capability to have the model autonomously decide to search for recent injury news or player quotes. | ✅ Ollama correctly calls the `web_search` tool when prompted with a question requiring external knowledge. |
| **Result Integration** | 🔴 Pending | **3. Integrate Search Results:** Use the search results to inform the qualitative feature generation (Task 3.2.2). | ✅ Qualitative features are grounded in real-time web search results. |

### Task 3.2.4: Embeddings for Similarity Search

| Sub-Task | Status | Exact Instruction for AI Partner | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **Embedding Generation** | 🔴 Pending | **1. Generate Embeddings:** Use `ollama.embeddings()` to generate vector representations for player news articles and historical game summaries. | ✅ Embeddings generated successfully. |
| **Vector Store Setup** | 🔴 Pending | **2. Set up Vector Store:** Integrate with a vector database (e.g., ChromaDB, or a simple in-memory store for dev) to store the embeddings. | ✅ Player news embeddings are searchable. |
| **Similarity Feature** | 🔴 Pending | **3. Implement Similarity Feature:** Create a feature that measures the similarity between the current game's context and historical games/news. | ✅ New feature based on vector similarity added to the ML feature set. |

### Task 3.2.5: Streaming for Frontend Analysis

| Sub-Task | Status | Exact Instruction for AI Partner | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **Streaming Endpoint** | 🔴 Pending | **1. Create Streaming Endpoint:** Implement a new FastAPI endpoint (e.g., `/api/ollama_stream`) that uses `ollama.generate(..., stream=True)` and returns a Server-Sent Events (SSE) response. | ✅ FastAPI endpoint streams the LLM response. |
| **Frontend Integration** | 🔴 Pending | **2. Integrate Frontend:** Update `aiService.v2.ts` and the UI component to consume the SSE stream for a real-time analysis display. | ✅ LLM analysis appears word-by-word in the UI. |

*(... Phase 4 content remains the same ...)*
