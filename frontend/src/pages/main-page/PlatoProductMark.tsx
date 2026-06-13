import platoProductMarkUrl from "../../assets/icons/plato-product-mark.svg";

export type PlatoProductMarkProps = {
  className?: string;
  title?: string;
};

export function PlatoProductMark({
  className,
  title = "Plato product mark",
}: PlatoProductMarkProps) {
  return <img alt={title} className={className} src={platoProductMarkUrl} />;
}
