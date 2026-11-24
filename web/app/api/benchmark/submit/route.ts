import { handleBenchmarkSubmit } from "@/lib/benchmark/submit";
import { submitDeps } from "@/lib/benchmark/runtime";

export async function POST(req: Request) {
  return handleBenchmarkSubmit(req, submitDeps());
}
