"use client";
import { useParams } from "next/navigation";
import { RoadmapView } from "@/components/Roadmap";

export default function Page() {
  const { s, c } = useParams<{ s: string; c: string }>();
  return <RoadmapView subjectId={s} conceptId={c} />;
}
