"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuth } from "@/hooks";
import { Button, Input, Label, Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui";
import { ApiError } from "@/lib/api-client";
import { ROUTES } from "@/lib/constants";
import { Check, X } from "lucide-react";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function getPasswordStrength(pw: string): { score: number; label: string; color: string } {
  if (!pw) return { score: 0, label: "", color: "" };
  let score = 0;
  if (pw.length >= 8) score++;
  if (pw.length >= 12) score++;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++;
  if (/\d/.test(pw)) score++;
  if (/[^a-zA-Z0-9]/.test(pw)) score++;

  if (score <= 1) return { score: 1, label: "Weak", color: "bg-red-500" };
  if (score <= 2) return { score: 2, label: "Fair", color: "bg-orange-500" };
  if (score <= 3) return { score: 3, label: "Good", color: "bg-yellow-500" };
  return { score: 4, label: "Strong", color: "bg-green-500" };
}

export function RegisterForm() {
  const router = useRouter();
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [emailTouched, setEmailTouched] = useState(false);

  const emailValid = !email || EMAIL_RE.test(email);
  const strength = useMemo(() => getPasswordStrength(password), [password]);
  const passwordsMatch = !confirmPassword || password === confirmPassword;
  const passwordLongEnough = !password || password.length >= 8;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!EMAIL_RE.test(email)) {
      setError("Please enter a valid email address");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      toast.error("Passwords do not match");
      return;
    }

    setIsLoading(true);

    try {
      await register({ email, password, name: name || undefined });
      toast.success("Account created! Please log in.");
      router.push(ROUTES.LOGIN + "?registered=true");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Registration failed. Please try again.";
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="w-full max-w-md mx-auto">
      <CardHeader>
        <CardTitle className="text-2xl text-center">Create Account</CardTitle>
      </CardHeader>
      <CardContent>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name (optional)</Label>
            <Input
              id="name"
              type="text"
              placeholder="John Doe"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={isLoading}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onBlur={() => setEmailTouched(true)}
              required
              disabled={isLoading}
              className={emailTouched && email && !emailValid ? "border-destructive" : ""}
            />
            {emailTouched && email && !emailValid && (
              <p className="text-destructive text-xs">Please enter a valid email address</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={isLoading}
              className={password && !passwordLongEnough ? "border-destructive" : ""}
            />
            {password && (
              <div className="space-y-1.5">
                <div className="flex gap-1">
                  {[1, 2, 3, 4].map((i) => (
                    <div
                      key={i}
                      className={`h-1 flex-1 rounded-full transition-colors ${
                        i <= strength.score ? strength.color : "bg-muted"
                      }`}
                    />
                  ))}
                </div>
                <div className="flex items-center justify-between">
                  <p className="text-muted-foreground text-xs">{strength.label}</p>
                  <div className="flex items-center gap-1.5 text-xs">
                    {password.length >= 8 ? (
                      <span className="flex items-center gap-0.5 text-green-500"><Check className="h-3 w-3" />8+ chars</span>
                    ) : (
                      <span className="flex items-center gap-0.5 text-muted-foreground"><X className="h-3 w-3" />8+ chars</span>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirmPassword">Confirm Password</Label>
            <Input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              disabled={isLoading}
              className={confirmPassword && !passwordsMatch ? "border-destructive" : ""}
            />
            {confirmPassword && (
              <p className={`flex items-center gap-1 text-xs ${passwordsMatch ? "text-green-500" : "text-destructive"}`}>
                {passwordsMatch ? <><Check className="h-3 w-3" />Passwords match</> : <><X className="h-3 w-3" />Passwords do not match</>}
              </p>
            )}
          </div>
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? "Creating account..." : "Register"}
          </Button>
        </form>
      </CardContent>
      <CardFooter className="justify-center">
        <p className="text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link href={ROUTES.LOGIN} className="text-primary hover:underline">
            Login
          </Link>
        </p>
      </CardFooter>
    </Card>
  );
}
