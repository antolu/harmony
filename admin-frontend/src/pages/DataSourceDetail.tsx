import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ProviderConfigForm } from "@/components/data-sources/ProviderConfigForm";
import { LastRunSummary } from "@/components/data-sources/LastRunSummary";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/api/client";

export function DataSourceDetail() {
  const { id } = useParams<{ id: string }>();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: source } = useQuery({
    queryKey: ["dataSource", id],
    queryFn: () => api.getDataSource(id!),
    enabled: !!id,
  });

  const { data: providerTypesData } = useQuery({
    queryKey: ["providerTypes"],
    queryFn: () => api.listProviderTypes(),
  });

  const [config, setConfig] = useState<Record<string, unknown>>({});

  useEffect(() => {
    if (source) {
      setConfig(source.config);
    }
  }, [source]);

  const matchingProviderType = providerTypesData?.types.find(
    (t) => t.type === source?.provider_type,
  );

  const saveMutation = useMutation({
    mutationFn: () =>
      api.updateDataSource(id!, config, source?.description ?? undefined),
    onSuccess: () => {
      toast({ title: "Saved" });
      queryClient.invalidateQueries({ queryKey: ["dataSource", id] });
    },
    onError: () => {
      toast({
        title: "Failed to save. Check the fields below and try again.",
        variant: "destructive",
      });
    },
  });

  return (
    <div className="space-y-6">
      <div className="text-sm text-muted-foreground">
        <Link to="/admin/data-sources" className="hover:underline">
          Data Sources
        </Link>
        {" / "}
        {source?.name}
      </div>

      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">{source?.name}</h1>
        {source && <Badge variant="outline">{source.provider_type}</Badge>}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {matchingProviderType && (
            <ProviderConfigForm
              schema={matchingProviderType.schema}
              value={config}
              onChange={setConfig}
            />
          )}
          <div className="flex justify-end">
            <Button
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending}
            >
              {saveMutation.isPending ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <LastRunSummary
        status={source?.last_run_status ?? null}
        docCount={source?.last_run_doc_count ?? null}
        lastRunAt={source?.last_run_at ?? null}
      />
    </div>
  );
}
