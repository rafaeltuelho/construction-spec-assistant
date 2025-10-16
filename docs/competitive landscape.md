Here’s a one-page market snapshot to frame your prototype against existing AEC solutions:

⸻

🏗️ Competitive Landscape (Specs ↔ Submittals ↔ Drawings)

Vendor / Product	Spec Parsing	Submittal Comparison	Drawing / Plan Understanding	Code Compliance	Explainable Output (citations)	Human-in-Loop Emphasis	Integration Focus
Autodesk Pype AutoSpecs	✅ auto-submittal log from specs	❌ (register only, no deep compare)	❌	❌	Limited	Medium (review log)	Autodesk Construction Cloud
Procore Submittal Builder	✅ auto log	❌	❌	❌	Limited	Medium	Procore ecosystem
Document Crunch (CrunchAI)	✅ spec review	Partial (flags risks, not full matching)	❌	❌	Limited transparency	❌ (black-box AI)	Contracts + Specs
UpCodes Copilot	❌	❌	❌	✅ code Q&A	Partial (text refs)	Medium	Code databases
Togal.AI	❌	❌	✅ (drawing takeoffs, measurements)	❌	❌	❌	Estimating workflows
Part3 – Submittal Assistant	✅	✅ highlights mismatches vs specs	❌	❌	Unclear	Medium (architect checks)	Procore import
Your Agentic Prototype	✅ (via Docling)	✅ (LLM compares)	✅ (vision model path)	Future extension	✅ full citations (spec para + submittal table + drawing callout)	✅ explicit SME-in-loop	Neutral (file upload first; ACC/Procore later)


⸻

✅ Pilot Success Checklist (for your SME engagement)
	1.	Narrow Scope Defined
	•	Pick 1 CSI division (e.g., 07 21 00 Insulation).
	•	1 spec section + 1 submittal + 1 drawing detail.
	2.	Baseline Ground Truth
	•	SME manually flags 2–3 mismatches/validations in these docs.
	•	This becomes your evaluation benchmark.
	3.	Pipeline Working
	•	Docling successfully parses spec + submittal into structured form.
	•	Vision model extracts at least one usable element from drawing.
	•	Comparison agent produces compliance result with citations.
	4.	Human-in-the-Loop UX
	•	SME sees extracted data side-by-side.
	•	Can mark results as Correct/Incorrect.
	•	Feedback stored for retraining.
	5.	Value Metrics Captured
	•	Time taken vs manual baseline.
	•	% of true mismatches caught.
	•	SME trust/confidence rating.
	6.	Demo-Ready UI
	•	Clean web interface (upload → preview → suggest actions → results).
	•	Citations displayed clearly (section/table/detail refs).

⸻

👉 With this matrix + checklist, you can position your prototype as the first system that truly bridges text specs, submittals, and drawings, with explainability and human-in-loop review.

Do you want me to also map out a 2-phase roadmap (PoC → MVP) showing which features to implement in each phase so you don’t overbuild too early?