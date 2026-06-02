import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { useToast } from "@/hooks/use-toast";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const ROLES = ["admin", "operator", "read_only"] as const;

export function Users() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: currentUser } = useQuery({
    queryKey: ["currentUser"],
    queryFn: api.getCurrentUser,
  });

  const { data: users, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: api.listUsers,
    select: (data) => data.users,
  });

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      api.updateUserRole(userId, role),
    onSuccess: (_, { role }) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      const user = users?.find((u) => u.id === _?.id);
      toast({
        title: `Role updated to ${role} for ${user?.email ?? "user"}`,
      });
    },
    onError: (e) => {
      toast({
        title: "Failed to update role",
        description: (e as Error).message,
        variant: "destructive",
      });
    },
  });

  const isAdmin = currentUser?.harmony_role === "admin";

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Users</h2>
          <p className="text-muted-foreground">
            OIDC-synced users and their roles.
          </p>
        </div>
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Users</h2>
        <p className="text-muted-foreground">
          OIDC-synced users and their roles.
        </p>
      </div>

      {!users || users.length === 0 ? (
        <div className="text-sm text-muted-foreground">
          <p>No users yet.</p>
          <p>Users appear here after their first OIDC login.</p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Email</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Joined</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((user) => (
              <TableRow key={user.id}>
                <TableCell>{user.email}</TableCell>
                <TableCell>{user.name ?? "—"}</TableCell>
                <TableCell>
                  {isAdmin ? (
                    <Select
                      value={user.harmony_role}
                      onValueChange={(role) =>
                        roleMutation.mutate({ userId: user.id, role })
                      }
                    >
                      <SelectTrigger
                        className="w-32"
                        aria-label={`Role for ${user.email}`}
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ROLES.map((r) => (
                          <SelectItem key={r} value={r}>
                            {r}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <span className="text-sm">{user.harmony_role}</span>
                  )}
                </TableCell>
                <TableCell>
                  {new Date(user.created_at).toLocaleDateString()}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
