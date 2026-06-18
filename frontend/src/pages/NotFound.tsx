import { Link } from "react-router-dom";
import { FileQuestion } from "lucide-react";
import { Button } from "@/components/ui/button";

export function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 py-24 text-center">
      <FileQuestion className="h-12 w-12 text-muted-foreground" />
      <div>
        <h2 className="text-2xl font-semibold">Page not found</h2>
        <p className="text-muted-foreground mt-1">
          This page doesn't exist or was moved.
        </p>
      </div>
      <Button asChild variant="outline">
        <Link to="/admin">Back to Dashboard</Link>
      </Button>
    </div>
  );
}
