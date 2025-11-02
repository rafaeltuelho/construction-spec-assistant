---
type: "always_apply"
---

### Rules for the Backend

 - The backend use Python.
 - Use uv tool to manage Python dependencies and venv.
 - The tech stack for the backend implementations is:
   * Use FastAPI to implement the backend API endpoints. 
   * Aways document the endpoints using the OpenAPI spec.
   * Docling for document parsing (unstructured.io can also be an option)
   * LangChain and LangGraph for the Agentic system/workflow
   * Qdrant inmemory as a VectorDB
 - If any other framework or library is needed, favor the ones that integrates well with the rest of the stack.
 - In case of error handling, always try to return meaningful messages to the client. 
 - Use logging instead of print. Avoid adding too much logging and use DEBUG level when useful for debugging, tracing and troubleshooting.