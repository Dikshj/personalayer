// Real, scannable QR code (qrcode.react) on a white quiet-zone background so
// it scans reliably against the app's surfaces.

import { QRCodeSVG } from "qrcode.react";

export function Qr({ value, size = 180, className = "" }: { value: string; size?: number; className?: string }) {
  return (
    <div className={`inline-block rounded-lg bg-white p-3 ${className}`}>
      <QRCodeSVG value={value} size={size} level="M" marginSize={2} />
    </div>
  );
}
