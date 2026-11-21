import { redirect } from "next/navigation";

// /subjects/:s -> W01
export default async function Page({ params }: { params: Promise<{ s: string }> }) {
  const { s } = await params;
  redirect(`/subjects/${s}/roadmap`);
}
