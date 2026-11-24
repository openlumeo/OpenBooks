import { jsonError, NO_STORE_HEADERS } from "@/lib/http";
import { LEADERBOARD_CACHE, loadLeaderboard } from "@/lib/benchmark/runtime";

export async function GET() {
  try {
    const entries = await loadLeaderboard();
    return Response.json(
      { entries, generated_at: new Date().toISOString() },
      { headers: { "cache-control": LEADERBOARD_CACHE } },
    );
  } catch {
    return jsonError(503, "leaderboard_unavailable", "The leaderboard is unavailable.", NO_STORE_HEADERS);
  }
}
