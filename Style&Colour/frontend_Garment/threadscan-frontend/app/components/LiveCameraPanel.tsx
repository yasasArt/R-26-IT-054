"use client";
import { ScanLine, Camera, CheckCircle2 } from "lucide-react";
import { FabricSwatch, colorHex } from "./FabricSwatch";

export interface ScanResult {
  style_name: string;
  confidence: number;
  main_color: string;
  other_colors?: string;
  image_base64?: string;
}

export default function LiveCameraPanel({ scan }: { scan: ScanResult | null }) {
  return (
    <div className="bg-panel border border-borderStrong rounded-lg flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-borderSoft flex justify-between items-center bg-panelRaised">
        <h3 className="text-textDim font-bold text-[11px] tracking-widest uppercase flex items-center gap-2">
          <ScanLine size={14} className="text-brandGreen" />
          Live AI Recognition Floor
        </h3>
        {scan && (
          <span className="font-mono text-[10px] text-brandGreen border border-brandGreen/30 px-2 py-1 rounded flex items-center gap-1">
            <CheckCircle2 size={12} /> {scan.confidence}% CONF
          </span>
        )}
      </div>

      <div className="flex flex-col xl:flex-row divide-y xl:divide-y-0 xl:divide-x divide-borderSoft">
        
        {/* වම් පස: Python AI Video Stream එක මෙහි Mount වේ */}
        <div className="relative aspect-video xl:w-[65%] bg-[#060A08] overflow-hidden flex items-center justify-center">
          <div className="absolute inset-0 bg-[radial-gradient(rgba(63,224,161,0.08)_1px,transparent_1px)] [background-size:18px_18px] pointer-events-none z-10" />

          {/* Python එකෙන් එන Live Video එක */}
          <img 
            src="http://127.0.0.1:5000/video_feed" 
            alt="AI Live Feed" 
            className="w-full h-full object-cover relative z-0"
            onError={(e) => {
                e.currentTarget.style.display = 'none';
                e.currentTarget.nextElementSibling?.classList.remove('hidden');
            }}
          />
          
          <div className="hidden absolute inset-0 flex flex-col items-center justify-center gap-2 text-textFaint font-mono text-xs z-20 bg-[#060A08] text-center px-6">
              AI Camera Feed Offline... Make sure python code is running.
          </div>
        </div>

        {/* දකුණු පස: AI එකෙන් අල්ලගන්න Best Frame එක */}
        <div className="flex-1 bg-panel flex flex-col p-5">
          <h4 className="text-[10px] uppercase font-bold tracking-widest text-textFaint mb-4 flex items-center gap-2">
            <Camera size={12} /> Best Frame Capture
          </h4>

          {scan ? (
            <div className="flex flex-col gap-5">
              <div className="w-full aspect-square bg-[#060A08] border border-borderStrong rounded-md overflow-hidden relative shadow-[inset_0_0_10px_rgba(0,0,0,0.5)]">
                 {scan.image_base64 ? (
                    <img src={`data:image/jpeg;base64,${scan.image_base64}`} alt="Captured Garment" className="w-full h-full object-cover" />
                 ) : (
                    <div className="w-full h-full flex items-center justify-center font-mono text-brandGreen/30 text-3xl font-bold uppercase">
                      {scan.style_name}
                    </div>
                 )}
              </div>

              <div className="flex flex-col gap-4">
                <div className="flex flex-col gap-1">
                  <div className="text-textFaint text-[10px] uppercase tracking-widest font-bold">Detected Style</div>
                  <div className="font-mono text-xl font-bold text-textMain">{scan.style_name}</div>
                </div>

                <div className="flex flex-col gap-2">
                  <div className="text-textFaint text-[10px] uppercase tracking-widest font-bold">Color Palette</div>
                  <div className="flex flex-wrap gap-3">
                    <FabricSwatch label={scan.main_color} hex={colorHex(scan.main_color)} />
                    {scan.other_colors
                      ?.split(",")
                      .map((c) => c.trim())
                      .filter(Boolean)
                      .map((c) => (
                        <FabricSwatch key={c} label={c} hex={colorHex(c)} />
                      ))}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-textFaint font-mono text-xs gap-3">
               <div className="w-16 h-16 border border-dashed border-borderStrong rounded flex items-center justify-center">
                 <Camera size={18} className="opacity-50" />
               </div>
               Waiting for garment...
            </div>
          )}
        </div>
        
      </div>
    </div>
  );
}