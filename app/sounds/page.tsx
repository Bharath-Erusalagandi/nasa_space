import type { Metadata } from "next";
import { SoundBoard } from "@/components/sounds/SoundBoard";
import { PRODUCT_NAME } from "@/lib/brand";

export const metadata: Metadata = { title: `Mosquito sounds, ${PRODUCT_NAME}` };

export default function SoundsPage() {
  return <SoundBoard />;
}
