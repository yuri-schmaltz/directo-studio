import { redirect } from "next/navigation";

export default function PresetsRedirectPage() {
  redirect("/settings?tab=presets");
}
