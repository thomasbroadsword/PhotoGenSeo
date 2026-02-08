"use client";

import { useState, useCallback } from "react";

const MAX_PRODUCTS = 10;
const API = ""; // względny URL na tym samym hoście (Vercel)

type ProductInfo = {
  name: string;
  ean: string;
  brand?: string;
  categories?: string[];
};

type ImageSource = {
  image_url: string;
  page_url?: string;
  title?: string;
  source_domain?: string;
};

type ProductData = {
  product: ProductInfo;
  sources: ImageSource[];
  error?: string;
};

type SelectedImage = { url: string; type: "url" } | { data: string; type: "upload" };

type ResultRow = {
  ean: string;
  productName: string;
  description: string;
  eanFromImages?: string | null;
  dimensions?: string | null;
  volumeOrWeight?: string | null;
  error?: string;
};

export default function Home() {
  const [eansInput, setEansInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [products, setProducts] = useState<Record<string, ProductData>>({});
  const [selectedByEan, setSelectedByEan] = useState<Record<string, SelectedImage[]>>({});
  const [extraSourcesByEan, setExtraSourcesByEan] = useState<Record<string, ImageSource[]>>({});
  const [step, setStep] = useState<"batch" | "validate" | "generating" | "results">("batch");
  const [results, setResults] = useState<ResultRow[]>([]);

  const eansList = eansInput
    .split(/[\n,;\s]+/)
    .map((e) => e.trim())
    .filter(Boolean)
    .slice(0, MAX_PRODUCTS);

  const loadProducts = useCallback(async () => {
    if (eansList.length === 0) {
      setError("Wpisz co najmniej jeden EAN.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/batch_search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ eans: eansList }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Błąd API");
      setProducts(data.products || {});
      const initial: Record<string, SelectedImage[]> = {};
      const extra: Record<string, ImageSource[]> = {};
      for (const ean of Object.keys(data.products || {})) {
        const p = data.products[ean];
        if (p.error) continue;
        initial[ean] = (p.sources || []).slice(0, 5).map((s: ImageSource) => ({ url: s.image_url, type: "url" as const }));
        extra[ean] = [];
      }
      setSelectedByEan(initial);
      setExtraSourcesByEan(extra);
      setStep("validate");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Błąd ładowania");
    } finally {
      setLoading(false);
    }
  }, [eansList.join(",")]);

  const searchMore = useCallback(async (ean: string, productName: string) => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/search_more`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ean, productName }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Błąd");
      setExtraSourcesByEan((prev) => ({
        ...prev,
        [ean]: [...(prev[ean] || []), ...(data.sources || [])],
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Błąd");
    } finally {
      setLoading(false);
    }
  }, []);

  const toggleImage = useCallback((ean: string, item: SelectedImage) => {
    setSelectedByEan((prev) => {
      const list = prev[ean] || [];
      const idx = list.findIndex(
        (x) =>
          (x.type === "url" && item.type === "url" && x.url === item.url) ||
          (x.type === "upload" && item.type === "upload" && x.data === item.data)
      );
      if (idx >= 0) return { ...prev, [ean]: list.filter((_, i) => i !== idx) };
      return { ...prev, [ean]: [...list, item] };
    });
  }, []);

  const isSelected = useCallback(
    (ean: string, item: SelectedImage) => {
      const list = selectedByEan[ean] || [];
      return list.some(
        (x) =>
          (x.type === "url" && item.type === "url" && x.url === item.url) ||
          (x.type === "upload" && item.type === "upload" && x.data === item.data)
      );
    },
    [selectedByEan]
  );

  const addUpload = useCallback((ean: string, dataUrl: string) => {
    setSelectedByEan((prev) => ({
      ...prev,
      [ean]: [...(prev[ean] || []), { type: "upload", data: dataUrl }],
    }));
  }, []);

  const runGenerate = useCallback(async () => {
    setStep("generating");
    setError(null);
    setLoading(true);
    const rows: ResultRow[] = [];
    const eans = Object.keys(products).filter((e) => !products[e].error);
    for (const ean of eans) {
      const sel = selectedByEan[ean] || [];
      const urls = sel.filter((s): s is { url: string; type: "url" } => s.type === "url").map((s) => s.url);
      const uploads = sel.filter((s): s is { data: string; type: "upload" } => s.type === "upload").map((s) => s.data);
      if (urls.length === 0 && uploads.length === 0) {
        rows.push({ ean, productName: products[ean].product.name, description: "", error: "Brak wybranych zdjęć" });
        setResults([...rows]);
        continue;
      }
      try {
        const res = await fetch(`${API}/api/run_from_images`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ean,
            productName: products[ean].product.name,
            imageUrls: urls,
            uploadedImages: uploads,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Błąd API");
        const verified = data.verified || {};
        rows.push({
          ean: data.ean || ean,
          productName: data.product?.name || products[ean].product.name,
          description: verified.description_verified || data.base_description || "",
          eanFromImages: verified.ean_from_images,
          dimensions: verified.dimensions_from_images,
          volumeOrWeight: verified.volume_or_weight_from_images,
        });
      } catch (e) {
        rows.push({
          ean,
          productName: products[ean].product.name,
          description: "",
          error: e instanceof Error ? e.message : "Błąd generacji",
        });
      }
      setResults([...rows]);
    }
    setStep("results");
    setLoading(false);
  }, [products, selectedByEan]);

  const exportCsv = useCallback(() => {
    const headers = ["EAN", "Nazwa", "Opis", "EAN_ze_zdjęć", "Wymiary", "Objętość/waga", "Błąd"];
    const escape = (s: string) => {
      const t = String(s ?? "").replace(/"/g, '""');
      return `"${t}"`;
    };
    const lines = [
      headers.join(";"),
      ...results.map((r) =>
        [
          r.ean,
          r.productName,
          r.description,
          r.eanFromImages ?? "",
          r.dimensions ?? "",
          r.volumeOrWeight ?? "",
          r.error ?? "",
        ].map(escape).join(";")
      ),
    ];
    const blob = new Blob(["\uFEFF" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "photogen-seo-export.csv";
    a.click();
    URL.revokeObjectURL(a.href);
  }, [results]);

  return (
    <div className="container">
      <h1 style={{ marginBottom: "0.5rem" }}>PhotoGenSeo</h1>
      <p style={{ color: "var(--muted)", marginBottom: "1.5rem" }}>
        Wsadowe generowanie opisów (max {MAX_PRODUCTS} produktów). Walidacja zdjęć → eksport CSV.
      </p>

      {error && (
        <div className="card" style={{ borderColor: "var(--error)", marginBottom: "1rem" }}>
          {error}
        </div>
      )}

      {step === "batch" && (
        <div className="card">
          <label style={{ display: "block", marginBottom: "0.5rem" }}>
            Kody EAN (max {MAX_PRODUCTS}, po jednym w linii lub po przecinku)
          </label>
          <textarea
            value={eansInput}
            onChange={(e) => setEansInput(e.target.value)}
            placeholder="5901234123457&#10;5900870123456"
            rows={6}
            style={{
              width: "100%",
              padding: "0.75rem",
              background: "var(--bg)",
              border: "1px solid var(--border)",
              borderRadius: "8px",
              color: "var(--text)",
            }}
          />
          <div style={{ marginTop: "1rem" }}>
            <button className="btn" onClick={loadProducts} disabled={loading}>
              {loading ? "Ładowanie…" : "Załaduj produkty i zdjęcia"}
            </button>
          </div>
        </div>
      )}

      {step === "validate" && (
        <>
          <div style={{ marginBottom: "1rem", display: "flex", gap: "0.5rem" }}>
            <button className="btn-secondary" onClick={() => setStep("batch")}>
              ← Wróć do EAN
            </button>
            <button className="btn" onClick={() => runGenerate()} disabled={loading}>
              Generuj opisy dla wszystkich
            </button>
          </div>
          {Object.entries(products).map(([ean, data]) => {
            if (data.error) {
              return (
                <div key={ean} className="card">
                  <strong>{ean}</strong> – błąd: {data.error}
                </div>
              );
            }
            const allSources = [...(data.sources || []), ...(extraSourcesByEan[ean] || [])];
            const selected = selectedByEan[ean] || [];
            return (
              <div key={ean} className="card">
                <h3 style={{ marginTop: 0 }}>{data.product.name}</h3>
                <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>EAN: {ean}</p>
                <p style={{ marginBottom: "0.75rem" }}>
                  Wybrane: {selected.length} zdjęć. Zaznacz zdjęcia do opisu, wgraj własne lub szukaj więcej.
                </p>
                <div style={{ marginBottom: "0.75rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => searchMore(ean, data.product.name)}
                    disabled={loading}
                  >
                    Szukaj więcej zdjęć
                  </button>
                  <label className="btn-secondary" style={{ margin: 0 }}>
                    Wgraj zdjęcia
                    <input
                      type="file"
                      accept="image/*"
                      multiple
                      style={{ display: "none" }}
                      onChange={(ev) => {
                        const files = ev.target.files;
                        if (!files) return;
                        for (let i = 0; i < files.length; i++) {
                          const r = new FileReader();
                          r.onload = () => addUpload(ean, r.result as string);
                          r.readAsDataURL(files[i]);
                        }
                        ev.target.value = "";
                      }}
                    />
                  </label>
                </div>
                <div className="grid-images">
                  {allSources.map((s, i) => {
                    const item: SelectedImage = { url: s.image_url, type: "url" };
                    const sel = isSelected(ean, item);
                    return (
                      <div
                        key={`${ean}-${i}-${s.image_url.slice(0, 40)}`}
                        className={`img-wrap ${sel ? "selected" : ""}`}
                        onClick={() => toggleImage(ean, item)}
                      >
                        <img src={s.image_url} alt="" />
                        <input type="checkbox" checked={sel} readOnly />
                      </div>
                    );
                  })}
                  {(selectedByEan[ean] || [])
                    .filter((s): s is { data: string; type: "upload" } => s.type === "upload")
                    .map((s, i) => {
                      const item: SelectedImage = { data: s.data, type: "upload" };
                      const sel = isSelected(ean, item);
                      return (
                        <div
                          key={`up-${ean}-${i}`}
                          className={`img-wrap ${sel ? "selected" : ""}`}
                          onClick={() => toggleImage(ean, item)}
                        >
                          <img src={s.data} alt="Wgrane" />
                          <input type="checkbox" checked={sel} readOnly />
                        </div>
                      );
                    })}
                </div>
              </div>
            );
          })}
        </>
      )}

      {step === "generating" && (
        <div className="card">
          <p>Generowanie opisów… ({results.length} / {Object.keys(products).filter((e) => !products[e].error).length})</p>
        </div>
      )}

      {step === "results" && (
        <>
          <div style={{ marginBottom: "1rem", display: "flex", gap: "0.5rem" }}>
            <button className="btn-secondary" onClick={() => setStep("validate")}>
              ← Walidacja zdjęć
            </button>
            <button className="btn" onClick={exportCsv}>
              Eksportuj CSV
            </button>
          </div>
          <div className="card table-wrap">
            <table>
              <thead>
                <tr>
                  <th>EAN</th>
                  <th>Nazwa</th>
                  <th>Opis</th>
                  <th>EAN (zdjęcia)</th>
                  <th>Wymiary</th>
                  <th>Obj./waga</th>
                  <th>Błąd</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r, i) => (
                  <tr key={i}>
                    <td>{r.ean}</td>
                    <td>{r.productName}</td>
                    <td style={{ maxWidth: 320, whiteSpace: "pre-wrap", fontSize: "0.9rem" }}>{r.description.slice(0, 300)}{r.description.length > 300 ? "…" : ""}</td>
                    <td>{r.eanFromImages ?? "—"}</td>
                    <td>{r.dimensions ?? "—"}</td>
                    <td>{r.volumeOrWeight ?? "—"}</td>
                    <td style={{ color: "var(--error)" }}>{r.error ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
