export type PlatoProductMarkProps = {
  className?: string;
  title?: string;
};

export function PlatoProductMark({
  className,
  title = "Plato product mark",
}: PlatoProductMarkProps) {
  return (
    <svg
      aria-label={title}
      className={className}
      fill="none"
      role="img"
      viewBox="240 180 380 340"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M284.204 487.833V286.953C284.204 232.167 324.785 197.673 383.629 197.673H460.735C531.753 197.673 578.422 244.342 578.422 311.302C578.422 378.262 531.753 424.931 460.735 424.931H379.571V362.029H454.647C487.113 362.029 511.462 341.738 511.462 311.302C511.462 280.865 487.113 260.574 454.647 260.574H383.629C361.309 260.574 349.135 274.778 349.135 297.098V487.833C349.135 502.036 332.902 510.153 322.756 500.007L292.32 469.571C286.233 463.484 284.204 457.396 284.204 447.251V487.833Z"
        fill="url(#plato-mark-paint0)"
      />
      <path
        d="M383.629 197.673H460.735C531.753 197.673 578.422 244.342 578.422 311.302C578.422 378.262 531.753 424.931 460.735 424.931H379.571V362.029H454.647C487.113 362.029 511.462 341.738 511.462 311.302C511.462 280.865 487.113 260.574 454.647 260.574H383.629C361.309 260.574 349.135 274.778 349.135 297.098V349.854H284.204V286.953C284.204 232.167 324.785 197.673 383.629 197.673Z"
        fill="url(#plato-mark-paint1)"
        opacity="0.96"
      />
      <path
        d="M284.204 380.291V447.251C284.204 457.396 286.233 463.483 292.32 469.571L322.756 500.007C332.902 510.152 349.135 502.036 349.135 487.832V380.291H284.204Z"
        fill="url(#plato-mark-paint2)"
      />
      <path
        d="M432.327 295.069H395.804C390.201 295.069 385.658 299.611 385.658 305.215V341.738C385.658 347.341 390.201 351.884 395.804 351.884H432.327C437.931 351.884 442.473 347.341 442.473 341.738V305.215C442.473 299.611 437.931 295.069 432.327 295.069Z"
        fill="#28C7E8"
      />
      <defs>
        <linearGradient
          gradientUnits="userSpaceOnUse"
          id="plato-mark-paint0"
          x1="243.622"
          x2="519.578"
          y1="502.036"
          y2="222.022"
        >
          <stop stopColor="#29C7E7" />
          <stop offset="0.52" stopColor="#3268FF" />
          <stop offset="1" stopColor="#6657FF" />
        </linearGradient>
        <linearGradient
          gradientUnits="userSpaceOnUse"
          id="plato-mark-paint1"
          x1="324.785"
          x2="535.811"
          y1="266.662"
          y2="388.407"
        >
          <stop stopColor="#435EFF" />
          <stop offset="1" stopColor="#775EFF" stopOpacity="0.78" />
        </linearGradient>
        <linearGradient
          gradientUnits="userSpaceOnUse"
          id="plato-mark-paint2"
          x1="286.233"
          x2="328.844"
          y1="441.163"
          y2="530.443"
        >
          <stop stopColor="#35B9F5" />
          <stop offset="1" stopColor="#25D0DD" />
        </linearGradient>
      </defs>
    </svg>
  );
}
