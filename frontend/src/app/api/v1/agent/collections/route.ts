import { NextRequest, NextResponse } from "next/server";
import { backendFetch, BackendApiError } from "@/lib/server-api";

// GET /api/v1/agent/collections - List available RAG collections for chat retrieval
export async function GET(request: NextRequest) {
    try {
        const headers: Record<string, string> = {};
        const accessToken = request.cookies.get("access_token")?.value;
        if (accessToken) {
            headers["Authorization"] = `Bearer ${accessToken}`;
        }

        const data = await backendFetch("/api/v1/agent/collections", { headers });
        return NextResponse.json(data);
    } catch (error) {
        if (error instanceof BackendApiError) {
            return NextResponse.json(
                { detail: error.message || "Failed to fetch collections" },
                { status: error.status }
            );
        }
        return NextResponse.json({ detail: "Internal server error" }, { status: 500 });
    }
}
