"use client";
import { useParams } from "next/navigation";
import { RoadmapView } from "@/components/Roadmap";
import "../../../roadmap-journey.css";

export default function Page() {
  const { s } = useParams<{ s: string }>();
  return <RoadmapView subjectId={s} />;
}
