import React, { useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Upload, FileText, CheckCircle2, XCircle, Wand2, Play, Trash2, Image, Table2, RefreshCw, ChevronRight, MessageSquare, Plus, Rocket } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";

// ---------- Types ----------
interface DocItem {
  id: string;
  name: string;
  kind: "spec" | "submittal" | "drawing";
  sizeKB: number;
  parsed: boolean;
  ocr: boolean;
  notes?: string;
  sections?: string[]; // for specs
  tables?: string[]; // for submittals
  figures?: string[]; // for drawings
}

interface SuggestedAction {
  id: string;
  label: string;
  selected: boolean;
  icon: React.ReactNode;
}

interface ResultItem {
  id: string;
  title: string;
  status: "pass" | "fail" | "info";
  details: string;
  citations?: Array<{ doc: string; ref: string }>; // surface provenance to SMEs
}

// ---------- Helpers ----------
const prettyKB = (kb: number) => `${Math.max(1, Math.round(kb))} KB`;
const genId = () => Math.random().toString(36).slice(2);

// ---------- Main Component ----------
export default function ConstructionSpecAssistantPOC() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [docs, setDocs] = useState<DocItem[]>([]);
  const [isParsing, setIsParsing] = useState(false);
  const [useOCR, setUseOCR] = useState(true);
  const [actions, setActions] = useState<SuggestedAction[]>([]);
  const [results, setResults] = useState<ResultItem[]>([]);
  const [chat, setChat] = useState<string>("");
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; text: string }[]>([]);

  // Derive counts for UI badges
  const counts = useMemo(() => {
    const spec = docs.filter((d) => d.kind === "spec").length;
    const sub = docs.filter((d) => d.kind === "submittal").length;
    const drw = docs.filter((d) => d.kind === "drawing").length;
    return { spec, sub, drw };
  }, [docs]);

  const handleLocalAdd = (kind: DocItem["kind"]) => {
    fileInputRef.current?.setAttribute("data-kind", kind);
    fileInputRef.current?.click();
  };

  const onFiles = (files: FileList, kind: DocItem["kind"]) => {
    const next: DocItem[] = [];
    Array.from(files).forEach((f) => {
      next.push({
        id: genId(),
        name: f.name,
        kind,
        sizeKB: f.size / 1024,
        parsed: false,
        ocr: useOCR,
      });
    });
    setDocs((prev) => [...prev, ...next]);
  };

  const simulateParse = async () => {
    if (!docs.length) return;
    setIsParsing(true);
    // Simulate Docling-like extraction with mild delay
    const updated: DocItem[] = JSON.parse(JSON.stringify(docs));
    await new Promise((r) => setTimeout(r, 800));
    for (const d of updated) {
      d.parsed = true;
      if (d.kind === "spec") {
        d.sections = [
          "07 21 00 - Thermal Insulation",
          "07 25 00 - Weather Barriers",
        ];
        d.notes = "Headings, hierarchy, and references preserved; 3 tables detected.";
      } else if (d.kind === "submittal") {
        d.tables = [
          "Product: OwensCorning R-19",
          "Thickness: 8 in",
          "Standard: ASTM C665 Type II",
        ];
        d.notes = "Compliance table normalized (3 rows, 6 columns).";
      } else if (d.kind === "drawing") {
        d.figures = ["Detail A-A (Wall Section)", "Legend: Insulation, Vapor Barrier"];
        d.notes = "Vector/raster layers detected; text labels indexed.";
      }
    }
    setDocs(updated);

    // Auto-suggest actions based on what we see
    const hasSpec = updated.some((d) => d.kind === "spec");
    const hasSub = updated.some((d) => d.kind === "submittal");
    const hasDrw = updated.some((d) => d.kind === "drawing");

    const suggestions: SuggestedAction[] = [];
    if (hasSpec && hasSub) {
      suggestions.push({
        id: genId(),
        label: "Compare Spec Section 07 21 00 with Submittal",
        selected: true,
        icon: <Table2 className="h-4 w-4" />,
      });
    }
    if (hasDrw) {
      suggestions.push({
        id: genId(),
        label: "Extract insulation thickness from Drawing detail A-A",
        selected: hasSpec, // preselect if we also have a spec
        icon: <Image className="h-4 w-4" />,
      });
    }
    suggestions.push({
      id: genId(),
      label: "Ask a question about this spec",
      selected: false,
      icon: <MessageSquare className="h-4 w-4" />,
    });
    setActions(suggestions);
    setIsParsing(false);
  };

  const toggleAction = (id: string) => {
    setActions((prev) => prev.map((a) => (a.id === id ? { ...a, selected: !a.selected } : a)));
  };

  const runActions = async () => {
    const selected = actions.filter((a) => a.selected);
    if (!selected.length) return;
    setResults([]);
    await new Promise((r) => setTimeout(r, 700));

    const synthetic: ResultItem[] = [];
    const specDoc = docs.find((d) => d.kind === "spec");
    const subDoc = docs.find((d) => d.kind === "submittal");
    const drwDoc = docs.find((d) => d.kind === "drawing");

    if (selected.some((s) => s.label.includes("Compare Spec")) && specDoc && subDoc) {
      synthetic.push({
        id: genId(),
        title: "Compliance: Thermal Insulation (R-19)",
        status: "pass",
        details:
          "Spec requires R-19 batt insulation, minimum thickness 6.25 in. Submittal provides OwensCorning R-19 at 8 in thickness. Greater thickness is acceptable; no conflict detected.",
        citations: [
          { doc: specDoc.name, ref: "Section 07 21 00 ¶2.2.A" },
          { doc: subDoc.name, ref: "Table 1, Row ‘Thickness’" },
        ],
      });
    }

    if (selected.some((s) => s.label.startsWith("Extract insulation thickness")) && drwDoc) {
      synthetic.push({
        id: genId(),
        title: "Drawing detail A-A: Insulation thickness",
        status: "info",
        details:
          "Detected note ‘INSUL R-19’ adjacent to stud cavity and hatch pattern matching insulation; inferred thickness callout ‘8\"’ near detail arrow. Confidence: 0.71. Please verify orientation relative to vapor barrier.",
        citations: [
          { doc: drwDoc.name, ref: "Detail A-A, callout (N/E quadrant)" },
        ],
      });
    }

    setResults(synthetic);
  };

  const removeDoc = (id: string) => setDocs((prev) => prev.filter((d) => d.id !== id));

  const handleAsk = async () => {
    if (!chat.trim()) return;
    const q = chat.trim();
    setMessages((m) => [...m, { role: "user", text: q }]);
    setChat("");
    await new Promise((r) => setTimeout(r, 500));
    // Synthetic assistant reply — in real app, call LLM with Docling JSON context
    setMessages((m) => [
      ...m,
      {
        role: "assistant",
        text:
          "Based on the parsed spec: Vapor barrier is required on the warm side for exterior framed walls per §07 25 00. Submittal does not contradict; drawing orientation is ambiguous — recommend SME verification.",
      },
    ]);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 text-slate-800">
      {/* Header */}
      <header className="sticky top-0 z-10 backdrop-blur bg-white/80 border-b border-blue-200 shadow-sm">
        <div className="mx-auto max-w-7xl px-4 py-4 flex items-center gap-3">
          <Rocket className="h-6 w-6 text-blue-600" />
          <h1 className="font-bold text-xl bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">Construction Spec Assistant — PoC</h1>
          <div className="ml-auto flex items-center gap-3">
            <div className="text-xs text-slate-500">OCR</div>
            <Switch checked={useOCR} onCheckedChange={setUseOCR} />
            <Button size="sm" onClick={simulateParse} disabled={!docs.length || isParsing} className="bg-blue-600 hover:bg-blue-700">
              <RefreshCw className="mr-2 h-4 w-4" /> {isParsing ? "Parsing…" : "Parse Documents"}
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl p-4 grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Left column: Upload & Docs */}
        <div className="xl:col-span-1 space-y-4">
          <Card className="shadow-sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Upload className="h-5 w-5"/>Upload</CardTitle>
              <CardDescription>Drag PDFs or use buttons below. Use OCR for scans.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <Button variant="outline" size="sm" onClick={() => handleLocalAdd("spec")} className="text-[10px] px-2 py-1 h-7 border-blue-200 hover:bg-blue-50 hover:border-blue-300">
                  <Plus className="mr-1 h-2.5 w-2.5 text-blue-600"/> Add Spec
                </Button>
                <Button variant="outline" size="sm" onClick={() => handleLocalAdd("submittal")} className="text-[10px] px-2 py-1 h-7 border-green-200 hover:bg-green-50 hover:border-green-300">
                  <Plus className="mr-1 h-2.5 w-2.5 text-green-600"/> Add Submittal
                </Button>
                <Button variant="outline" size="sm" onClick={() => handleLocalAdd("drawing")} className="text-[10px] px-2 py-1 h-7 border-purple-200 hover:bg-purple-50 hover:border-purple-300">
                  <Plus className="mr-1 h-2.5 w-2.5 text-purple-600"/> Add Drawing
                </Button>
              </div>

              <input ref={fileInputRef} type="file" accept="application/pdf" className="hidden" multiple onChange={(e) => {
                const kind = (e.currentTarget.getAttribute("data-kind") as DocItem["kind"]) || "spec";
                if (e.currentTarget.files) onFiles(e.currentTarget.files, kind);
                e.currentTarget.value = ""; // reset
              }} />

              <div className="mt-4 rounded-2xl border-2 border-dashed border-blue-300 bg-blue-50/50 p-6 text-center hover:border-blue-400 hover:bg-blue-50 transition-colors">
                <p className="text-sm text-blue-600 font-medium">Drop PDFs here</p>
                <p className="text-xs text-blue-500 mt-1">or use the buttons above</p>
              </div>
            </CardContent>
            <CardFooter className="justify-between text-xs text-slate-500">
              <div className="flex items-center gap-3">
                <Badge className="bg-blue-100 text-blue-800 hover:bg-blue-200">Specs: {counts.spec}</Badge>
                <Badge className="bg-green-100 text-green-800 hover:bg-green-200">Submittals: {counts.sub}</Badge>
                <Badge className="bg-purple-100 text-purple-800 hover:bg-purple-200">Drawings: {counts.drw}</Badge>
              </div>
              <div className="text-slate-400">PoC • client-side demo</div>
            </CardFooter>
          </Card>

          <Card className="shadow-sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><FileText className="h-5 w-5"/>Documents</CardTitle>
              <CardDescription>Parsed structure preview (Docling-like).</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {!docs.length ? (
                <div className="text-sm text-slate-500">No documents yet. Add a spec, a submittal, and optionally a drawing.</div>
              ) : (
                docs.map((d) => (
                  <motion.div key={d.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="rounded-xl border p-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {d.kind === "spec" && <Badge className="bg-blue-100 text-blue-800">Spec</Badge>}
                        {d.kind === "submittal" && <Badge className="bg-green-100 text-green-800">Submittal</Badge>}
                        {d.kind === "drawing" && <Badge className="bg-purple-100 text-purple-800">Drawing</Badge>}
                        <div className="font-medium">{d.name}</div>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-slate-500">
                        <span>{prettyKB(d.sizeKB)}</span>
                        <Button size="icon" variant="ghost" onClick={() => removeDoc(d.id)} title="Remove">
                          <Trash2 className="h-4 w-4"/>
                        </Button>
                      </div>
                    </div>
                    <div className="mt-2 text-xs text-slate-600">
                      {d.parsed ? (
                        <div className="space-y-1">
                          {d.sections && (
                            <div><span className="font-semibold">Sections:</span> {d.sections.join(", ")}</div>
                          )}
                          {d.tables && (
                            <div><span className="font-semibold">Table:</span> {d.tables.join(" · ")}</div>
                          )}
                          {d.figures && (
                            <div><span className="font-semibold">Figures:</span> {d.figures.join(" · ")}</div>
                          )}
                          <div className="text-slate-500">{d.notes}</div>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 text-slate-400">
                          <Wand2 className="h-4 w-4"/> Not parsed yet {d.ocr && <span className="ml-2">• OCR on</span>}
                        </div>
                      )}
                    </div>
                  </motion.div>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right column: Actions & Results */}
        <div className="xl:col-span-2 space-y-4">
          <Card className="shadow-sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><ChevronRight className="h-5 w-5"/>Suggested Actions</CardTitle>
              <CardDescription>Auto-generated from parsed content; adjust before running.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {!actions.length ? (
                <div className="text-sm text-slate-500">No actions yet. Parse documents to see suggestions.</div>
              ) : (
                actions.map((a) => (
                  <label key={a.id} className="flex items-center gap-3 rounded-xl border p-3 cursor-pointer hover:bg-slate-50">
                    <input type="checkbox" checked={a.selected} onChange={() => toggleAction(a.id)} />
                    <div className="flex items-center gap-2">
                      {a.icon}
                      <span className="text-sm">{a.label}</span>
                    </div>
                  </label>
                ))
              )}
            </CardContent>
            <CardFooter className="justify-between">
              <div className="text-xs text-slate-500">Routing: text→LLM · drawings→VLM (mocked)</div>
              <Button onClick={runActions} disabled={!actions.some((a) => a.selected)} className="bg-green-600 hover:bg-green-700">
                <Play className="mr-2 h-4 w-4"/> Run Selected Action(s)
              </Button>
            </CardFooter>
          </Card>

          <Card className="shadow-sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><CheckCircle2 className="h-5 w-5"/>Results</CardTitle>
              <CardDescription>Discrepancies, compliance checks, and citations.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {!results.length ? (
                <div className="text-sm text-slate-500">No results yet.</div>
              ) : (
                results.map((r) => (
                  <motion.div key={r.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="rounded-xl border p-3">
                    <div className="flex items-center justify-between">
                      <div className="font-medium">{r.title}</div>
                      {r.status === "pass" && <Badge className="bg-emerald-600 hover:bg-emerald-600">Pass</Badge>}
                      {r.status === "fail" && <Badge className="bg-rose-600 hover:bg-rose-600">Fail</Badge>}
                      {r.status === "info" && <Badge variant="outline">Info</Badge>}
                    </div>
                    <div className="mt-2 text-sm text-slate-700">{r.details}</div>
                    {r.citations && (
                      <div className="mt-2 text-xs text-slate-500">
                        Citations: {r.citations.map((c, i) => (
                          <span key={i} className="mr-3">{c.doc} — {c.ref}</span>
                        ))}
                      </div>
                    )}
                    <div className="mt-3 flex items-center gap-2">
                      <Button size="sm" variant="secondary"><CheckCircle2 className="mr-2 h-4 w-4"/> Correct</Button>
                      <Button size="sm" variant="outline"><XCircle className="mr-2 h-4 w-4"/> Incorrect</Button>
                    </div>
                  </motion.div>
                ))
              )}
            </CardContent>
          </Card>

          <Card className="shadow-sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><MessageSquare className="h-5 w-5"/>Assistant</CardTitle>
              <CardDescription>Ask questions or request additional checks.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="h-44 overflow-auto rounded-xl border p-3 bg-white">
                  {!messages.length ? (
                    <div className="text-sm text-slate-500">No conversation yet.</div>
                  ) : (
                    messages.map((m, i) => (
                      <div key={i} className={`mb-2 ${m.role === "user" ? "text-slate-800" : "text-slate-700"}`}>
                        <span className="text-xs uppercase tracking-wide text-slate-400">{m.role}</span>
                        <div className="text-sm">{m.text}</div>
                      </div>
                    ))
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Input placeholder="Ask a question about the spec or submittal…" value={chat} onChange={(e) => setChat(e.target.value)} />
                  <Button onClick={handleAsk} className="bg-indigo-600 hover:bg-indigo-700">Send</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>

      <footer className="mx-auto max-w-7xl p-6 text-xs text-slate-500 flex items-center justify-between">
        <div>Prototype UI • No documents leave your browser in this demo.</div>
        <div>Designed for SME-in-the-loop workflows</div>
      </footer>
    </div>
  );
}