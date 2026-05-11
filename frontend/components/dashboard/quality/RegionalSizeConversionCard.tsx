import { Panel, StatusPill } from "@/components/industrial/Primitives";

type RegionalSizeMapping = {
  region: string;
  expected: string;
  detected: string;
  status: "Match";
};

const regionalSizeMappings: RegionalSizeMapping[] = [
  { region: "Alpha", expected: "M", detected: "M", status: "Match" },
  { region: "UK", expected: "12", detected: "12", status: "Match" },
  { region: "US", expected: "8", detected: "8", status: "Match" },
  { region: "EUR", expected: "40", detected: "40", status: "Match" },
];

export function RegionalSizeConversionCard() {
  return (
    <Panel title="Regional Size Conversion" eyebrow="International size mapping">
      <div className="table-wrap">
        <table className="data-table" style={{ minWidth: 0, tableLayout: "fixed" }}>
          <thead>
            <tr>
              <th>Region</th>
              <th>Expected</th>
              <th>Detected</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {regionalSizeMappings.map(mapping => (
              <tr key={mapping.region}>
                <td>{mapping.region}</td>
                <td>{mapping.expected}</td>
                <td>{mapping.detected}</td>
                <td>
                  <StatusPill label={mapping.status} tone="ok" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
