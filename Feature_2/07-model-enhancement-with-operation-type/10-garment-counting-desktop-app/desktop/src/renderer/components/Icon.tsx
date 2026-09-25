import type { ReactElement } from "react";

export type IconName =
  | "activity"
  | "arrow-right"
  | "bluetooth"
  | "camera"
  | "check"
  | "chip"
  | "clock"
  | "close"
  | "download"
  | "edit"
  | "database"
  | "file"
  | "folder"
  | "history"
  | "layers"
  | "lock"
  | "maximize"
  | "minimize"
  | "monitor"
  | "pause"
  | "play"
  | "plus"
  | "refresh"
  | "report"
  | "settings"
  | "shield"
  | "spark"
  | "target"
  | "trash"
  | "users"
  | "warning";

const iconPaths: Record<IconName, ReactElement> = {
  activity: <path d="M3 12h4l3-8 4 16 3-8h4" />,
  "arrow-right": <path d="M5 12h14m-7-7 7 7-7 7" />,
  bluetooth: <path d="m7 7 10 10-5 5V2l5 5L7 17" />,
  camera: (
    <>
      <path d="M14 4H9L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3z" />
      <circle cx="12" cy="13" r="3" />
    </>
  ),
  check: <path d="m5 12 4 4L19 6" />,
  chip: (
    <>
      <rect x="5" y="5" width="14" height="14" rx="2" />
      <path d="M9 9h6v6H9zM9 1v4m6-4v4M9 19v4m6-4v4M1 9h4m-4 6h4m14-6h4m-4 6h4" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  close: <path d="m6 6 12 12M18 6 6 18" />,
  download: <path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4" />,
  edit: <path d="m14 5 5 5M4 20l4.3-1L19 8.3a2.1 2.1 0 0 0-3-3L5.3 16 4 20z" />,
  database: (
    <>
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
    </>
  ),
  file: (
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6M8 13h8m-8 4h8" />
    </>
  ),
  folder: <path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />,
  history: (
    <>
      <path d="M3 12a9 9 0 1 0 2.6-6.4L3 8" />
      <path d="M3 3v5h5m4-1v5l4 2" />
    </>
  ),
  layers: <path d="m12 2 9 5-9 5-9-5 9-5zm-9 9 9 5 9-5m-18 6 9 5 9-5" />,
  lock: (
    <>
      <rect x="4" y="11" width="16" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </>
  ),
  maximize: <rect x="4" y="4" width="16" height="16" rx="2" />,
  minimize: <path d="M5 12h14" />,
  monitor: (
    <>
      <rect x="3" y="4" width="18" height="13" rx="2" />
      <path d="M8 21h8m-4-4v4" />
    </>
  ),
  pause: <path d="M8 5h3v14H8zm6 0h3v14h-3z" />,
  play: <path d="m8 5 12 7-12 7V5z" />,
  plus: <path d="M12 5v14m-7-7h14" />,
  refresh: (
    <>
      <path d="M20 7v5h-5M4 17v-5h5" />
      <path d="M6 9a7 7 0 0 1 12-2l2 5M4 12l2 5a7 7 0 0 0 12-2" />
    </>
  ),
  report: (
    <>
      <path d="M3 3v18h18" />
      <path d="m7 14 4-4 4 3 5-7" />
    </>
  ),
  settings: (
    <>
      <path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z" />
      <path d="m19.4 15 1.4 1.1-1.5 2.6-1.8-.7-1.3.8-.3 1.9h-3l-.3-1.9-1.3-.8-1.8.7L8 16.1 9.4 15l-.1-1.5L8 12.4l1.5-2.6 1.8.7 1.3-.8.3-1.9h3l.3 1.9 1.3.8 1.8-.7 1.5 2.6-1.4 1.1.1 1.5z" />
    </>
  ),
  shield: (
    <>
      <path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  spark: <path d="m12 2 2.6 7.4L22 12l-7.4 2.6L12 22l-2.6-7.4L2 12l7.4-2.6L12 2z" />,
  target: (
    <>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1" />
    </>
  ),
  trash: (
    <>
      <path d="M3 6h18m-2 0-1 14H6L5 6m4 0V4h6v2" />
      <path d="M10 10v6m4-6v6" />
    </>
  ),
  users: (
    <>
      <path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2m16 0v-2a4 4 0 0 0-3-3.9" />
      <circle cx="10" cy="7" r="4" />
      <path d="M16 3.2a4 4 0 0 1 0 7.7" />
    </>
  ),
  warning: (
    <>
      <path d="m12 3 10 18H2L12 3z" />
      <path d="M12 9v4m0 4h.01" />
    </>
  ),
};

export function Icon({
  name,
  size = 18,
  className,
}: {
  name: IconName;
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {iconPaths[name]}
    </svg>
  );
}
