import { redirect } from "next/navigation";

// /subjects/:s -> My path (roadmap, level, summary, next step)
export default async function Page({ params }: { params: Promise<{ s: string }> }) {
  const { s } = await params;
  redirect(`/subjects/${s}/start`);
}
