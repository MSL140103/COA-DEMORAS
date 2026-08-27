import VoyageDetail from "@/components/VoyageDetail";

export default async function VoyagePage(props: PageProps<"/voyages/[id]">) {
  const { id } = await props.params;
  return <VoyageDetail voyageId={id} />;
}
