import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Download, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import { api, ExportDomain } from "@/api/client";

export function Export() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedDomains, setSelectedDomains] = useState<Set<string>>(
    new Set(),
  );
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const {
    data: domains,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["exportDomains"],
    queryFn: () => api.listExportDomains(),
  });

  const allSelected =
    !!domains && domains.length > 0 && selectedDomains.size === domains.length;
  const partiallySelected = selectedDomains.size > 0 && !allSelected;

  function toggleDomain(domain: string) {
    setSelectedDomains((prev) => {
      const next = new Set(prev);
      if (next.has(domain)) {
        next.delete(domain);
      } else {
        next.add(domain);
      }
      return next;
    });
  }

  function toggleAll() {
    if (!domains) return;
    if (allSelected) {
      setSelectedDomains(new Set());
    } else {
      setSelectedDomains(new Set(domains.map((d: ExportDomain) => d.domain)));
    }
  }

  async function handleExport() {
    if (selectedDomains.size === 0 || exporting) return;
    setExporting(true);
    toast({ title: `Exporting ${selectedDomains.size} domain(s)…` });
    try {
      const blob = await api.exportArchive([...selectedDomains]);
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = "harmony-export.tar.gz";
      a.click();
      URL.revokeObjectURL(objectUrl);
      toast({ title: "Export complete — harmony-export.tar.gz downloaded" });
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Export failed",
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setExporting(false);
    }
  }

  async function handleImport() {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      toast({ title: "Select a .tar.gz file first" });
      return;
    }
    setImporting(true);
    toast({ title: "Importing…" });
    try {
      const result = await api.importArchive(file);
      toast({
        title: `Import complete — ${result.imported_docs} documents restored`,
      });
      await queryClient.invalidateQueries({ queryKey: ["exportDomains"] });
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Import failed",
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setImporting(false);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Export / Import</h2>
        <p className="text-muted-foreground">
          Snapshot selected domains and restore them on another Harmony
          instance.
        </p>
      </div>

      {isError && (
        <Alert variant="destructive">
          <AlertDescription>
            Failed to load domains. Check that the API is reachable.
          </AlertDescription>
        </Alert>
      )}

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <input
                  type="checkbox"
                  checked={allSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = partiallySelected;
                  }}
                  onChange={toggleAll}
                  aria-label="Select all domains"
                  className="cursor-pointer"
                />
              </TableHead>
              <TableHead>Domain</TableHead>
              <TableHead className="text-right">Document Count</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={3} className="h-24 text-center">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : !domains || domains.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={3}
                  className="h-24 text-center text-muted-foreground"
                >
                  No domains indexed yet.
                </TableCell>
              </TableRow>
            ) : (
              domains.map((d: ExportDomain) => (
                <TableRow
                  key={d.domain}
                  className="cursor-pointer"
                  onClick={() => toggleDomain(d.domain)}
                >
                  <TableCell>
                    <input
                      type="checkbox"
                      checked={selectedDomains.has(d.domain)}
                      onChange={() => toggleDomain(d.domain)}
                      onClick={(e) => e.stopPropagation()}
                      className="cursor-pointer"
                    />
                  </TableCell>
                  <TableCell className="font-mono text-sm">
                    {d.domain}
                  </TableCell>
                  <TableCell className="text-right text-sm">
                    {d.doc_count.toLocaleString()}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Button
        onClick={handleExport}
        disabled={selectedDomains.size === 0 || exporting}
      >
        {exporting ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <Download className="mr-2 h-4 w-4" />
        )}
        Export Selected ({selectedDomains.size})
      </Button>

      <Separator />

      <div className="space-y-3">
        <Label className="text-base font-semibold">
          Import Archive (.tar.gz)
        </Label>
        <div className="flex items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept=".tar.gz,.gz"
            className="hidden"
            onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
          />
          <Button
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
          >
            <Upload className="mr-2 h-4 w-4" />
            {selectedFile ? selectedFile.name : "Choose file…"}
          </Button>
          <Button onClick={handleImport} disabled={!selectedFile || importing}>
            {importing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Upload &amp; Import
          </Button>
        </div>
      </div>
    </div>
  );
}
