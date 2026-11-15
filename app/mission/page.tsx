import { existsSync } from "node:fs";
import { join } from "node:path";
import type { Metadata } from "next";
import { MissionShell } from "@/components/mission/MissionShell";
import { FILES_META, OPTIONAL_FILES } from "@/lib/trends/load";

const present = OPTIONAL_FILES.filter((file) => existsSync(join(process.cwd(), "public", file)));

export const metadata: Metadata = { other: { [FILES_META]: present.join(" ") || "none" } };

export default function MissionPage() {
  return <MissionShell />;
}
